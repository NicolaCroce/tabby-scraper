# loader.py
"""
Módulo encargado de la conexión con la base de datos PostgreSQL (Neon),
la validación de duplicados (Failsafe) y la persistencia de los datos procesados.
"""
import re
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import extractor


def verificar_torneo_duplicado(conn, motions_df, log_func=print):
    """
    Verifica si las mociones extraídas ya existen en la base de datos de Neon
    usando una huella digital basada en las primeras 3 mociones.
    """
    if motions_df is None or motions_df.empty:
        log_func("    └> Failsafe: No hay mociones disponibles para verificar huella digital.")
        return False
    
    mociones_prueba = motions_df['motion'].dropna().astype(str).unique()[:3].tolist()
    if not mociones_prueba:
        return False
        
    log_func("    └> Iniciando Failsafe: Verificando huella digital (Mociones)...")
    
    binds = {f"m{i}": m for i, m in enumerate(mociones_prueba)}
    placeholders = ", ".join([f":m{i}" for i in range(len(mociones_prueba))])
    
    query = text(f"SELECT COUNT(*) FROM master_motions WHERE motion IN ({placeholders})")
    
    try:
        coincidencias = conn.execute(query, binds).scalar()
        if coincidencias >= len(mociones_prueba):
            return True # ¡Torneo Duplicado detectado!
        else:
            return False # Torneo limpio
    except Exception as e:
        log_func(f"    [!] Error al ejecutar failsafe (Procediendo con precaución): {e}")
        return False


def process_single_tournament(base_url, db_url, override_name="", tourney_date="", log_func=print):
    """
    Orquesta el flujo completo de un torneo: extracción web, validación de duplicados 
    y carga transaccional en las tablas relacionales de Neon.
    """
    slug = override_name.strip()
    if not slug:
        try:
            slug = extractor.urlparse(base_url).netloc.split('.')[0].upper()
        except:
            slug = "TORNEO"
    if not slug: slug = "TORNEO"
    
    parsed_date = None
    if tourney_date:
        try:
            parsed_date = pd.to_datetime(tourney_date).date()
        except Exception as e:
            log_func(f"  [!] Advertencia: Fecha inválida '{tourney_date}'. Quedará en blanco. Error: {e}")
            
    log_func(f"\n==================================================")
    log_func(f"Procesando torneo: {slug} ({base_url})")
    if parsed_date: log_func(f"Fecha registrada: {parsed_date}")
    log_func(f"==================================================")
    
    all_rounds_dfs = [] 
    all_speaker_dfs_raw = [] 
    all_breaking_adjs_dfs = []
    all_motions_dfs = []

    links_to_scrape = extractor.find_data_links(base_url, log_func)
    if not links_to_scrape:
        log_func(f"  [!] No se encontraron links para {slug}. Saltando...")
        return False

    mociones_extraidas = False

    for url, link_text in links_to_scrape.items():
        if ("motion" in url.lower() or "mocion" in url.lower()) and not mociones_extraidas:
            m_df_records = extractor.extract_motions_from_url(url, log_func)
            if m_df_records:
                m_df = pd.DataFrame(m_df_records)
                m_df['tournament'] = slug
                if parsed_date: m_df['tournament_date'] = parsed_date
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

    log_func(f"Conectando a Neon para verificar e insertar {slug}...")
    engine = create_engine(db_url, connect_args={"connect_timeout": 300})
    
    MASTER_SPEAKER_COLS = ['Rk', 'Rank', 'Clas.', 'name', 'Nombre', 'team', 'Equipo', 'institution', 'Institución', 'Category', 'Cat.', 'Total', 'Avg', 'Prom.', 'Stdev', 'D.E.', 'Num', 'round', 'speakers', 'tournament', 'teamkey', 'tournament_date']
    MASTER_RESULTS_COLS = ['team', 'institution', 'result', 'Side', 'Adjudicators', 'round', 'tournament', 'teamkey', 'tournament_date']
    MASTER_ADJ_COLS = ['Rank', 'Rk', 'Name', 'Nombre', 'Score', 'Test Score', 'tournament', 'tournament_date']

    with engine.begin() as conn:
        
        # --- FAILSAFE ---
        final_motions = None
        if all_motions_dfs:
            final_motions = pd.concat(all_motions_dfs, ignore_index=True)
            es_duplicado = verificar_torneo_duplicado(conn, final_motions, log_func)
            
            if es_duplicado:
                log_func("\n⚠️ ¡ALERTA DE FAILSAFE ACTIVADA! ⚠️")
                log_func("Este torneo ya parece estar cargado en la base de datos (Las mociones coinciden).")
                log_func("Operación cancelada para evitar datos duplicados.")
                return False 
        
        log_func("✅ Failsafe superado. Ningún torneo duplicado detectado. Procediendo...")

        if final_motions is not None:
            final_motions.to_sql("master_motions", conn, if_exists='append', index=False, chunksize=500)
            log_func(f"  [+] {len(final_motions)} mociones cargadas.")

        if all_speaker_dfs_raw:
            target_df, best_score = None, 9999
            cat_kw = ['novate', 'epl', 'pro-am', 'rookie', 'open', 'novato']
            for title, df_i in all_speaker_dfs_raw:
                score = len(title.lower())
                if all(cat not in title.lower() for cat in cat_kw): score -= 1000
                elif 'open' in title.lower(): score -= 500
                if score < best_score: best_score = score; target_df = df_i
            
            if target_df is not None:
                rp = re.compile(r'^(R\d+|OF|QF|SF|GF|NF|EFL|Octos|Semis|Final|Cuartos|PSF|PQF|PF)$', re.IGNORECASE)
                id_cols = [c for c in target_df.columns if not rp.match(c)]
                val_cols = [c for c in target_df.columns if rp.match(c)]
                if val_cols:
                    df_un = target_df.melt(id_vars=id_cols, value_vars=val_cols, var_name="round", value_name="speakers")
                    df_un['tournament'] = slug
                    if parsed_date: df_un['tournament_date'] = parsed_date
                    team_col = next((c for c in id_cols if c.lower() in ['team', 'equipo']), None)
                    if team_col:
                        df_un['round'] = df_un['round'].str.replace('Ronda ', 'R', case=False)
                        df_un['teamkey'] = extractor.create_team_round_key(df_un, team_col, 'round', 'tournament')
                    final_cols = [c for c in df_un.columns if c.lower() in [m.lower() for m in MASTER_SPEAKER_COLS]]
                    df_un[final_cols].to_sql("master_speakers_ajustado", conn, if_exists='append', index=False, chunksize=500)
                    log_func(f"  [+] Tab de oradores cargado.")

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
                        tmp['Side'] = t_pos; tmp['team'] = df_w[t_pos]; tmp['points'] = df_w[pts] if pts else np.nan
                        long_dfs.append(tmp)
                elif 'team' in df_w.columns and 'Side' in df_w.columns:
                    long_dfs.append(df_w)
            
            if long_dfs:
                final_res = pd.concat(long_dfs, ignore_index=True)
                final_res['tournament'] = slug
                if parsed_date: final_res['tournament_date'] = parsed_date
                if 'team' in final_res.columns:
                    final_res['round'] = final_res['round'].str.replace('Ronda ', 'R', case=False)
                    final_res['teamkey'] = extractor.create_team_round_key(final_res, 'team', 'round', 'tournament')
                final_cols = [c for c in final_res.columns if c.lower() in [m.lower() for m in MASTER_RESULTS_COLS]]
                final_res[final_cols].to_sql("master_consolidado_resultados", conn, if_exists='append', index=False, chunksize=500)
                log_func(f"  [+] Resultados de rondas cargados.")

        if all_breaking_adjs_dfs:
            final_adjs = pd.concat(all_breaking_adjs_dfs, ignore_index=True)
            if parsed_date: final_adjs['tournament_date'] = parsed_date
            final_cols = [c for c in final_adjs.columns if c.lower() in [m.lower() for m in MASTER_ADJ_COLS]]
            final_adjs[final_cols].to_sql("master_breaking_adjudicators", conn, if_exists='append', index=False, chunksize=500)
            log_func(f"  [+] Jueces clasificados cargados.")

    log_func(f"[V] Torneo {slug} completado con éxito.\n")
    return True