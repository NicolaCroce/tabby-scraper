# loader.py
"""
Módulo encargado de la conexión con la base de datos PostgreSQL (Neon),
la resolución de portales, control de registros y la ejecución desacoplada:
Scraping y Pandas en memoria primero, conexión a BD solo al insertar.
"""
import re
import html
from urllib.parse import urlparse
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import extractor


def verificar_torneo_duplicado_por_url(conn, base_url, log_func=print):
    try:
        parsed_url = urlparse(base_url)
        domain_base = f"{parsed_url.scheme}://{parsed_url.netloc}"
        log_func(f"    [Failsafe URL] Verificando si '{domain_base}' ya está registrado...")
        query = text("SELECT COUNT(*) FROM master_torneos_registro WHERE tab_link LIKE :domain")
        coincidencias = conn.execute(query, {"domain": f"%{domain_base}%"}).scalar()
        return coincidencias > 0
    except Exception as e:
        log_func(f"    [!] Error al verificar duplicado por URL: {e}")
        return False


def registrar_torneo_exitoso(conn, slug, base_url, parsed_date, log_func=print):
    try:
        query = text("""
            INSERT INTO master_torneos_registro (tournament_id, tournament_name, tab_link, tournament_date, load_status)
            VALUES (:tid, :tname, :tlink, :tdate, 'Completado')
            ON CONFLICT (tournament_id) DO UPDATE 
            SET tab_link = EXCLUDED.tab_link, load_status = 'Completado';
        """)
        conn.execute(query, {
            "tid": slug,
            "tname": slug,
            "tlink": base_url,
            "tdate": parsed_date
        })
        log_func(f"  [+] Torneo {slug} registrado exitosamente en master_torneos_registro.")
    except Exception as e:
        log_func(f"  [!] No se pudo registrar el torneo en la tabla de control: {e}")


def process_single_tournament(base_url, db_url, override_name="", tourney_date="", log_func=print):
    base_url_efectiva = extractor.resolver_url_base_torneo(base_url, log_func)

    slug = override_name.strip()
    if not slug:
        try:
            slug = urlparse(base_url_efectiva).netloc.split('.')[0].upper()
        except Exception:
            slug = "TORNEO"
    if not slug:
        slug = "TORNEO"
    
    parsed_date = None
    if tourney_date:
        try:
            parsed_date = pd.to_datetime(tourney_date).date()
        except Exception as e:
            log_func(f"  [!] Advertencia: Fecha inválida '{tourney_date}'. Quedará en blanco. Error: {e}")
            
    log_func(f"\n==================================================")
    log_func(f"Procesando torneo: {slug} ({base_url_efectiva})")
    if parsed_date:
        log_func(f"Fecha registrada: {parsed_date}")
    log_func(f"==================================================")
    
    # --- 1. VERIFICACIÓN INICIAL DE DUPLICADO (Conexión corta) ---
    engine = create_engine(
        db_url, 
        connect_args={"connect_timeout": 300, "sslmode": "require"},
        pool_pre_ping=True,
        pool_recycle=300
    )

    with engine.begin() as conn_check:
        if verificar_torneo_duplicado_por_url(conn_check, base_url_efectiva, log_func):
            log_func(f"\n⚠️ ¡ALERTA DE FAILSAFE! ⚠️")
            log_func(f"El torneo con dominio '{base_url_efectiva}' ya está registrado en master_torneos_registro.")
            log_func("Operación cancelada para evitar duplicados.")
            return False

    # =========================================================================
    # 2. FASE DE SCRAPING Y PROCESAMIENTO EN MEMORIA (SIN CONEXIÓN A BD ABIERTA)
    # =========================================================================
    all_rounds_dfs = [] 
    all_speaker_dfs_raw = [] 
    all_breaking_adjs_dfs = []
    all_motions_dfs = []
    speaker_tab_url = None

    links_to_scrape = extractor.find_data_links(base_url_efectiva, log_func)
    if not links_to_scrape:
        log_func(f"  [!] No se encontraron links para {slug}. Saltando...")
        return False

    mociones_extraidas = False

    for url, link_text in links_to_scrape.items():
        if 'speaker' in url.lower() or 'orador' in url.lower():
            if not speaker_tab_url:
                speaker_tab_url = url

        if ("motion" in url.lower() or "mocion" in url.lower()) and not mociones_extraidas:
            m_df_records = extractor.extract_motions_from_url(url, log_func)
            if m_df_records:
                m_df = pd.DataFrame(m_df_records)
                m_df['tournament'] = slug
                if parsed_date:
                    m_df['tournament_date'] = parsed_date
                all_motions_dfs.append(m_df)
                mociones_extraidas = True  
            continue

        tables = extractor.extract_tables_from_url(url, link_text, log_func)
        for (table_title, df) in tables:
            t_low = table_title.lower()
            if any(k in t_low for k in ["ronda", "gf", "nf", "sf", "qf", "of", "r32", "psf", "pqf", "pf"]):
                df['round'] = table_title.split(' - ')[0]
                df['tournament'] = slug
                all_rounds_dfs.append(df.copy())
            elif "speaker" in t_low or "orador" in t_low:
                all_speaker_dfs_raw.append((table_title, df.copy()))
            elif ("adjudicator" in t_low or "juez" in t_low) and ("break" in t_low or "corte" in t_low):
                df['tournament'] = slug
                all_breaking_adjs_dfs.append(df.copy())

    # Procesamiento y enriquecimiento en DataFrames puros en memoria
    final_motions_df = None
    final_speakers_df = None
    final_results_df = None
    final_adjs_df = None

    if all_motions_dfs:
        final_motions_df = pd.concat(all_motions_dfs, ignore_index=True)

    if all_speaker_dfs_raw:
        target_df, best_score = None, 9999
        cat_kw = ['novate', 'epl', 'pro-am', 'rookie', 'open', 'novato']
        for title, df_i in all_speaker_dfs_raw:
            score = len(title.lower())
            if all(cat not in title.lower() for cat in cat_kw):
                score -= 1000
            elif 'open' in title.lower():
                score -= 500
            if score < best_score:
                best_score = score
                target_df = df_i
        
        if target_df is not None:
            rp = re.compile(r'^(R\d+|OF|QF|SF|GF|NF|EFL|Octos|Semis|Final|Cuartos|PSF|PQF|PF)$', re.IGNORECASE)
            id_cols = [c for c in target_df.columns if not rp.match(c)]
            val_cols = [c for c in target_df.columns if rp.match(c)]
            if val_cols:
                df_un = target_df.melt(id_vars=id_cols, value_vars=val_cols, var_name="round", value_name="speakers")
                df_un['tournament'] = slug
                if parsed_date:
                    df_un['tournament_date'] = parsed_date
                
                df_un['d_role'] = np.nan

                # Extracción de roles (Web scraping pesado fuera de la BD)
                if speaker_tab_url:
                    log_func(f"  [i] Extrayendo roles y papeletas en memoria (Fase 2)...")
                    # Se pasa 'slug' como segundo parámetro para que el fallback use el nombre correcto del torneo
                    enriched_roles = extractor.extract_speaker_roles_and_ballots_from_speaker_tab(speaker_tab_url, slug, log_func)
                    
                    if enriched_roles:
                        try:
                            df_roles = pd.DataFrame(enriched_roles)
                            
                            df_un['name'] = df_un['name'].apply(lambda x: html.unescape(str(x)).strip())
                            df_roles['name'] = df_roles['name'].apply(lambda x: html.unescape(str(x)).strip())
                            df_un['round'] = df_un['round'].astype(str).str.strip()
                            df_roles['round'] = df_roles['round'].astype(str).str.strip()
                            
                            df_un = df_un.merge(
                                df_roles[['name', 'round', 'd_role']], 
                                on=['name', 'round'], 
                                how='left', 
                                suffixes=('', '_new')
                            )
                            
                            if 'd_role_new' in df_un.columns:
                                df_un['d_role'] = df_un['d_role_new'].combine_first(df_un.get('d_role'))
                                df_un.drop(columns=['d_role_new'], inplace=True, errors='ignore')
                                
                            log_func(f"  [+] Cruce de d_role completado en memoria con éxito.")
                        except Exception as e:
                            log_func(f"  [!] Advertencia al cruzar d_role en memoria: {e}")

                MASTER_SPEAKER_COLS = [
                    'Rk', 'Rank', 'Clas.', 'name', 'Nombre', 'team', 'Equipo', 
                    'institution', 'Institución', 'Category', 'Cat.', 'Total', 
                    'Avg', 'Prom.', 'Stdev', 'D.E.', 'Num', 'round', 'speakers', 
                    'tournament', 'tournament_date', 'd_role'
                ]
                final_cols = [c for c in df_un.columns if c.lower() in [m.lower() for m in MASTER_SPEAKER_COLS]]
                final_speakers_df = df_un[final_cols]

    if all_rounds_dfs:
        long_dfs = []
        for df_w in all_rounds_dfs:
            pos_pat = re.compile(r'^(OG|OO|CG|CO|Aff|Neg|Team 1|Team 2)$', re.IGNORECASE)
            ids = [c for c in df_w.columns if not pos_pat.match(c) and 'Ptos' not in c and 'Pts' not in c]
            teams = [c for c in df_w.columns if pos_pat.match(c)]
            if teams:
                for t_pos in teams:
                    pts = f"Ptos {t_pos}" if f"Ptos {t_pos}" in df_w else (f"Pts {t_pos}" if f"Pts {t_pos}" in df_w else None)
                    tmp = df_w[ids].copy()
                    tmp['Side'] = t_pos
                    tmp['team'] = df_w[t_pos]
                    tmp['points'] = df_w[pts] if pts else np.nan
                    long_dfs.append(tmp)
            elif 'team' in df_w.columns and 'Side' in df_w.columns:
                long_dfs.append(df_w)
        
        if long_dfs:
            final_res = pd.concat(long_dfs, ignore_index=True)
            final_res['tournament'] = slug
            if parsed_date:
                final_res['tournament_date'] = parsed_date
            if 'team' in final_res.columns:
                final_res['round'] = final_res['round'].str.replace('Ronda ', 'R', case=False)
            
            MASTER_RESULTS_COLS = ['team', 'institution', 'result', 'Side', 'Adjudicators', 'round', 'tournament', 'tournament_date']
            final_cols = [c for c in final_res.columns if c.lower() in [m.lower() for m in MASTER_RESULTS_COLS]]
            final_results_df = final_res[final_cols]

    if all_breaking_adjs_dfs:
        final_adjs = pd.concat(all_breaking_adjs_dfs, ignore_index=True)
        if parsed_date:
            final_adjs['tournament_date'] = parsed_date
        MASTER_ADJ_COLS = ['name', 'institution', 'adjcore', 'independent', 'tournament', 'tournament_date']
        final_cols = [c for c in final_adjs.columns if c.lower() in [m.lower() for m in MASTER_ADJ_COLS]]
        final_adjs_df = final_adjs[final_cols]


    # =========================================================================
    # 3. FASE DE CARGA RÁPIDA A NEON (Conexión abierta brevemente solo para insertar)
    # =========================================================================
    log_func(f"Conectando a Neon para insertar la data de {slug}...")
    with engine.begin() as conn:
        if final_motions_df is not None and not final_motions_df.empty:
            final_motions_df.to_sql("master_motions", conn, if_exists='append', index=False, chunksize=500)
            log_func(f"  [+] {len(final_motions_df)} mociones cargadas.")

        if final_speakers_df is not None and not final_speakers_df.empty:
            final_speakers_df.to_sql("master_speakers_ajustado", conn, if_exists='append', index=False, chunksize=500)
            log_func(f"  [+] Tab de oradores cargado.")

        if final_results_df is not None and not final_results_df.empty:
            final_results_df.to_sql("master_consolidado_resultados", conn, if_exists='append', index=False, chunksize=500)
            log_func(f"  [+] Resultados de rondas cargados.")

        if final_adjs_df is not None and not final_adjs_df.empty:
            final_adjs_df.to_sql("master_breaking_adjudicators", conn, if_exists='append', index=False, chunksize=500)
            log_func(f"  [+] Jueces clasificados cargados (con instituciones, adjcore e independent).")

        registrar_torneo_exitoso(conn, slug, base_url_efectiva, parsed_date, log_func)

    log_func(f"[V] Torneo {slug} completado con éxito.\n")
    return True