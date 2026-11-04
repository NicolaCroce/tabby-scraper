# loader.py
"""
Módulo encargado de la conexión con la base de datos PostgreSQL (Neon),
la resolución de portales de bienvenida de Tabbycat, la validación de duplicados
por URL (Failsafe Paso 1), la actualización parcial por columnas vacías (Failsafe Paso 2)
y la limpieza preventiva por torneo para garantizar cargas de datos sin duplicados.
"""
import re
from urllib.parse import urlparse
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import extractor


def verificar_torneo_duplicado_por_url(conn, base_url, log_func=print):
    """
    PASO 1 DEL FAILSAFE:
    Verifica si el dominio/URL base del torneo ya se encuentra registrado.
    """
    try:
        parsed_url = urlparse(base_url)
        domain_base = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        log_func(f"    [Failsafe Paso 1] Verificando URL base '{domain_base}'...")
        
        query = text("SELECT COUNT(*) FROM master_torneos_registro WHERE tab_link LIKE :domain")
        coincidencias = conn.execute(query, {"domain": f"%{domain_base}%"}).scalar()
        
        return coincidencias > 0
    except Exception as e:
        log_func(f"    [!] Error en Paso 1 del Failsafe: {e}")
        return False


def obtener_columnas_vacias_oradores(conn, slug, log_func=print):
    """
    PASO 2 DEL FAILSAFE (Future Proofing):
    Verifica si en las filas cargadas para el torneo en 'master_speakers_ajustado' 
    existen columnas clave que estén completamente NULL.
    """
    try:
        log_func(f"    [Failsafe Paso 2] Inspeccionando si existen columnas NULL para '{slug}'...")
        query = text("""
            SELECT 
                COUNT(*) FILTER (WHERE d_role IS NULL) as null_d_role,
                COUNT(*) FILTER (WHERE t_role IS NULL) as null_t_role,
                COUNT(*) as total_filas
            FROM master_speakers_ajustado 
            WHERE tournament = :slug
        """)
        res = conn.execute(query, {"slug": slug}).fetchone()
        
        if not res or res.total_filas == 0:
            return []
            
        cols_a_actualizar = []
        if res.null_d_role == res.total_filas and res.total_filas > 0:
            cols_a_actualizar.append('d_role')
        if res.null_t_role == res.total_filas and res.total_filas > 0:
            cols_a_actualizar.append('t_role')
            
        return cols_a_actualizar
    except Exception as e:
        log_func(f"    [!] Error en Paso 2 del Failsafe: {e}")
        return []


def registrar_torneo_exitoso(conn, slug, base_url, parsed_date, log_func=print):
    """Registra o actualiza el torneo en la tabla master_torneos_registro."""
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
    """
    Orquesta el flujo completo del torneo aplicando el Failsafe de 2 pasos,
    la resolución de portales de bienvenida y la limpieza preventiva de registros por torneo.
    """
    # 1. Resolver si la URL base ingresada es un portal de bienvenida con múltiples categorías (ej. CMUDE)
    base_url_efectiva = extractor.resolver_url_base_torneo(base_url, log_func)

    slug = override_name.strip()
    if not slug:
        try:
            slug = urlparse(base_url_efectiva).netloc.split('.')[0].upper()
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
    log_func(f"Procesando torneo: {slug} ({base_url_efectiva})")
    if parsed_date: log_func(f"Fecha registrada: {parsed_date}")
    log_func(f"==================================================")
    
    engine = create_engine(db_url, connect_args={"connect_timeout": 300})
    
    solo_actualizar_columnas = False
    columnas_pendientes = []

    # --- EVALUACIÓN DEL FAILSAFE DE 2 PASOS ---
    with engine.begin() as conn_check:
        ya_existe = verificar_torneo_duplicado_por_url(conn_check, base_url_efectiva, log_func)
        
        if ya_existe:
            log_func("  [!] El torneo ya existe por URL. Evaluando Paso 2...")
            columnas_pendientes = obtener_columnas_vacias_oradores(conn_check, slug, log_func)
            
            if not columnas_pendientes:
                log_func("\n⚠️ ¡ALERTA DE FAILSAFE (COMPLETO)! ⚠️")
                log_func("El torneo ya está completamente cargado y con todas las columnas pobladas.")
                log_func("Operación cancelada para evitar duplicaciones.")
                return False
            else:
                log_func(f"\n🔄 Modo Actualización Parcial (Future-Proofing) Activado.")
                log_func(f"Se detectaron columnas vacías a rellenar: {columnas_pendientes}")
                solo_actualizar_columnas = True
        else:
            log_func("✅ Failsafe Paso 1 superado (Torneo Nuevo). Procediendo con carga completa...")

    # --- EXTRACCIÓN Y SCRAPING ---
    all_rounds_dfs = [] 
    all_speaker_records = [] 
    all_breaking_adjs_dfs = []
    all_motions_dfs = []

    links_to_scrape = extractor.find_data_links(base_url_efectiva, log_func)
    if not links_to_scrape:
        log_func(f"  [!] No se encontraron links para {slug}. Saltando...")
        return False

    mociones_extraidas = False

    for url, link_text in links_to_scrape.items():
        if ("motion" in url.lower() or "mocion" in url.lower()) and not mociones_extraidas and not solo_actualizar_columnas:
            m_df_records = extractor.extract_motions_from_url(url, log_func)
            if m_df_records:
                m_df = pd.DataFrame(m_df_records)
                m_df['tournament'] = slug
                if parsed_date: m_df['tournament_date'] = parsed_date
                all_motions_dfs.append(m_df)
                mociones_extraidas = True  
            continue

        if "ballot" in url.lower():
            ballot_speakers = extractor.extract_ballot_speakers_from_url(url, log_func)
            if ballot_speakers:
                for b_rec in ballot_speakers:
                    b_rec['tournament'] = slug
                    if parsed_date: b_rec['tournament_date'] = parsed_date
                    all_speaker_records.append(b_rec)
            continue

        if not solo_actualizar_columnas:
            tables = extractor.extract_tables_from_url(url, link_text, log_func)
            for (table_title, df) in tables:
                t_low = table_title.lower()
                if any(k in t_low for k in ["ronda", "gf", "nf", "sf", "qf", "of", "r32", "psf", "pqf", "pf"]):
                    df['round'] = table_title.split(' - ')[0]
                    df['tournament'] = slug
                    all_rounds_dfs.append(df.copy())
                elif ("adjudicator" in t_low or "juez" in t_low) and ("break" in t_low or "corte" in t_low):
                    df['tournament'] = slug
                    all_breaking_adjs_dfs.append(df.copy())

    MASTER_SPEAKER_COLS = ['name', 'team', 'Total', 'round', 'tournament', 'teamkey', 'tournament_date', 'd_role', 't_role', 'Side']
    MASTER_RESULTS_COLS = ['team', 'institution', 'result', 'Side', 'Adjudicators', 'round', 'tournament', 'teamkey', 'tournament_date']
    MASTER_ADJ_COLS = ['Rank', 'Rk', 'Name', 'Nombre', 'Score', 'Test Score', 'tournament', 'tournament_date']

    # --- PERSISTENCIA EN NEON ---
    with engine.begin() as conn:
        
        # MODO ACTUALIZACIÓN PARCIAL (FUTURE-PROOFING)
        if solo_actualizar_columnas and all_speaker_records:
            log_func("  [+] Modo Actualización Parcial activo: Actualizando únicamente columnas pendientes...")
            df_spk = pd.DataFrame(all_speaker_records)
            df_spk['round'] = df_spk.get('round', 'R1')
            df_spk['teamkey'] = extractor.create_team_round_key(df_spk, 'team', 'round', 'tournament')

            count_updates = 0
            for _, row in df_spk.iterrows():
                query_update = text("""
                    UPDATE master_speakers_ajustado 
                    SET d_role = COALESCE(:d_role, d_role),
                        t_role = COALESCE(:t_role, t_role)
                    WHERE teamkey = :teamkey AND name = :name;
                """)
                res_up = conn.execute(query_update, {
                    "d_role": row.get('d_role'),
                    "t_role": row.get('t_role'),
                    "teamkey": row.get('teamkey'),
                    "name": row.get('name')
                })
                count_updates += res_up.rowcount
                
            log_func(f"  [+] Se actualizaron los roles en {count_updates} registros de oradores exitosamente.")
            
        # MODO CARGA COMPLETA (Con limpieza preventiva por torneo para evitar duplicados)
        else:
            log_func(f"  [+] Aplicando limpieza preventiva de registros previos para el torneo {slug}...")
            conn.execute(text("DELETE FROM master_speakers_ajustado WHERE tournament = :slug"), {"slug": slug})
            conn.execute(text("DELETE FROM master_consolidado_resultados WHERE tournament = :slug"), {"slug": slug})
            conn.execute(text("DELETE FROM master_breaking_adjudicators WHERE tournament = :slug"), {"slug": slug})

            if all_motions_dfs:
                final_motions = pd.concat(all_motions_dfs, ignore_index=True)
                motions_dicts = final_motions.to_dict(orient='records')
                query_motion_upsert = text("""
                    INSERT INTO master_motions (round, motion, infoslide, tournament, tournament_date)
                    VALUES (:round, :motion, :infoslide, :tournament, :tournament_date)
                    ON CONFLICT (motion) DO NOTHING;
                """)
                for row_m in motions_dicts:
                    try:
                        conn.execute(query_motion_upsert, row_m)
                    except Exception:
                        pass
                log_func(f"  [+] Mociones procesadas (evitando duplicados).")

            if all_speaker_records:
                df_speakers = pd.DataFrame(all_speaker_records)
                df_speakers['round'] = df_speakers.get('round', 'R1')
                df_speakers['teamkey'] = extractor.create_team_round_key(df_speakers, 'team', 'round', 'tournament')
                final_speaker_cols = [c for c in df_speakers.columns if c in MASTER_SPEAKER_COLS]
                df_speakers[final_speaker_cols].to_sql("master_speakers_ajustado", conn, if_exists='append', index=False, chunksize=500)
                log_func(f"  [+] Tab de oradores con roles cargado sin duplicados.")

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
                    log_func(f"  [+] Resultados de rondas cargados sin duplicados.")

            if all_breaking_adjs_dfs:
                final_adjs = pd.concat(all_breaking_adjs_dfs, ignore_index=True)
                if parsed_date: final_adjs['tournament_date'] = parsed_date
                final_cols = [c for c in final_adjs.columns if c.lower() in [m.lower() for m in MASTER_ADJ_COLS]]
                final_adjs[final_cols].to_sql("master_breaking_adjudicators", conn, if_exists='append', index=False, chunksize=500)
                log_func(f"  [+] Jueces clasificados cargados sin duplicados.")

        # Registrar o actualizar el torneo en la tabla maestra de control
        registrar_torneo_exitoso(conn, slug, base_url_efectiva, parsed_date, log_func)

    log_func(f"[V] Torneo {slug} procesado correctamente.\n")
    return True