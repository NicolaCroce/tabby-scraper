# extractor.py
"""
Módulo extractor de datos para Tabbycat (Versión V11 con soporte de URL base, 
control de registros, capa aditiva y mapeo numérico para Breaking Adjudicators).
"""
import re
from urllib.parse import urljoin, urlparse
import numpy as np
import pandas as pd
pyjson5 = None
try:
    import pyjson5
except ImportError:
    import json as pyjson5  # Fallback si pyjson5 no está disponible
import requests
from bs4 import BeautifulSoup


def resolver_url_base_torneo(base_url, log_func=print):
    try:
        parsed = urlparse(base_url)
        response = requests.get(base_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        links = soup.find_all('a', href=True)
        candidato_url = None
        candidato_open = None
        
        for link in links:
            href = link['href']
            text = link.get_text(strip=True).lower()
            full_url = urljoin(base_url, href)
            
            # Ignorar logins, admins y enlaces externos de donación (Open Collective)
            if 'login' in full_url or 'admin' in full_url or 'opencollective.com' in full_url: 
                continue
                
            parsed_full = urlparse(full_url)
            path_lower = parsed_full.path.lower()
            
            # Buscar coincidencia segura de categoría open en el mismo dominio
            if ('/open/' in path_lower or path_lower.endswith('/open') or 'open' in text) and parsed_full.netloc == parsed.netloc:
                candidato_open = full_url
                break 
                
            if any(k in text for k in ['campeonato', 'mundial', 'general']) and not candidato_url:
                if parsed_full.netloc == parsed.netloc:
                    candidato_url = full_url
                        
        url_elegida = candidato_open or candidato_url
        
        if url_elegida and url_elegida != base_url:
            log_func(f"  [i] Portal de bienvenida detectado. Redirigiendo a la categoría principal (Open): {url_elegida}")
            return url_elegida
            
        return base_url
    except Exception as e:
        log_func(f"  [!] No se pudo resolver la URL base, usando la original: {e}")
        return base_url


def find_data_links(base_url, log_func=print):
    base_url_efectiva = resolver_url_base_torneo(base_url, log_func)
    log_func(f"Buscando enlaces de datos en: {base_url_efectiva}")
    PALABRAS_CLAVE = ['speaker', 'team', 'result', 'draw', 'standings', 'tab', 'break', 'adjudicator', 'juez', 'motion', 'mocion']
    found_tab_links = {}
    try:
        response = requests.get(base_url_efectiva, timeout=15)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'lxml')
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link['href']
            if any(keyword in href.lower() for keyword in PALABRAS_CLAVE):
                full_url = urljoin(base_url_efectiva, href)
                if urlparse(full_url).netloc == urlparse(base_url_efectiva).netloc:
                    link_text = link.get_text(strip=True) or "Enlace Genérico"
                    found_tab_links[full_url] = link_text
        log_func(f"  └> Se encontraron {len(found_tab_links)} enlaces relevantes.")
        return found_tab_links 
    except Exception as e:
        log_func(f"  [!] Error al buscar enlaces: {e}")
        return {}


def extract_motions_from_url(url, log_func=print):
    def get_std_round(r_name):
        r_low = r_name.strip().lower()
        if m := re.search(r'(?:ronda|round)\s+(\d+)', r_name, flags=re.IGNORECASE): return f"R{m.group(1)}"
        if 'dieciseis' in r_low or 'double' in r_low or 'r32' in r_low: return 'R32'
        if 'pre' in r_low and 'semi' in r_low: return 'PSF'
        if 'parcial' in r_low or 'partial' in r_low: return 'PQF'
        if 'oct' in r_low or r_low == 'of': return 'OF'
        if 'cuarto' in r_low or 'quarter' in r_low or r_low == 'qf': return 'QF'
        if 'semi' in r_low or r_low == 'sf': return 'SF'
        if 'novat' in r_low or 'novice' in r_low: return 'NF'
        if 'final' in r_low or r_low == 'gf': return 'GF'
        return r_name 

    try:
        log_func(f"  └> Analizando página de mociones...")
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        motions_data = []
        
        cards = soup.find_all('div', class_='card')
        for card in cards:
            title_tag = card.find('h4', class_='card-title') or card.find(class_='card-header')
            if not title_tag: continue
            round_name = title_tag.get_text(strip=True)

            lead_div = card.find('div', class_=lambda x: x and 'mr-auto' in x and 'lead' in x)
            if lead_div:
                motion_text = lead_div.get_text(strip=True)
            else:
                h4 = card.find('h4', class_=lambda x: not x or 'card-title' not in x)
                if h4:
                    if h4.find('small'): h4.find('small').decompose()
                    motion_text = h4.get_text(strip=True)
                else:
                    motion_text = ""

            modal = card.find('div', class_='modal-body')
            infoslide_text = modal.get_text(separator='\n', strip=True) if modal else None

            if round_name and motion_text:
                round_std = get_std_round(round_name)
                motions_data.append({'round': round_std, 'motion': motion_text, 'infoslide': infoslide_text})

        if not motions_data:
            round_headers = soup.find_all('div', class_=lambda x: x and 'list-group-item' in x and 'disabled' in x and 'h5' in x)
            for header in round_headers:
                badge = header.find('span', class_='badge')
                if not badge: continue
                round_name = badge.get_text(strip=True)
                content_div = header.find_next_sibling('div', class_='list-group-item')
                if not content_div: continue

                motion_text = ""
                h4_tag = content_div.find('h4')
                if h4_tag:
                    if h4_tag.find('small'): h4_tag.find('small').decompose()
                    motion_text = h4_tag.get_text(strip=True)

                infoslide_text = None
                modal_div = content_div.find('div', class_='modal-body')
                if modal_div: infoslide_text = modal_div.get_text(separator='\n', strip=True)

                if round_name and motion_text:
                    round_std = get_std_round(round_name)
                    motions_data.append({'round': round_std, 'motion': motion_text, 'infoslide': infoslide_text})
        
        if motions_data:
            df = pd.DataFrame(motions_data)
            df['round'] = df['round'].str.strip()
            df['motion'] = df['motion'].str.strip()
            df = df.drop_duplicates(subset=['round', 'motion']).reset_index(drop=True)
            log_func(f"    └> ¡Éxito! {len(df)} mociones extraídas (limpias).")
            return df.to_dict('records')
        
        log_func("    └> No se encontró formato reconocible de mociones.")
        return None

    except Exception as e:
        log_func(f"  [!] Error extrayendo mociones: {e}")
        return None


def get_elim_round_name(advancing_count, json_title="", page_title="", page_subtitle="", link_text=""):
    if advancing_count <= 0: return None 
    t_lower = f"{json_title} {page_title} {page_subtitle} {link_text}".lower()
    if 'pre-semi' in t_lower or 'partial-quarter' in t_lower or 'parcial' in t_lower or 'presemis' in t_lower:
        if advancing_count <= 4: return "PSF"
        if advancing_count <= 8: return "PQF"
    if advancing_count == 1:
        return "NF" if ('novice' in t_lower or 'novata' in t_lower) else "GF"
    if advancing_count == 2: return "PF"
    if advancing_count <= 4: return "PSF" if 'pre' in t_lower else "SF"
    if advancing_count <= 8: return "PQF" if 'pre' in t_lower else "QF"
    if advancing_count <= 16: return "OF"
    if advancing_count <= 32: return "R32"
    return None


def extract_tables_from_url(url, link_text="", log_func=print):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'lxml')
        
        page_title_tag = soup.find('title')
        page_title = ""
        if page_title_tag:
            raw_title = page_title_tag.get_text(strip=True)
            for sep in ['|', '—', '-']:
                if sep in raw_title:
                    page_title = raw_title.split(sep)[-1].strip()
                    break
            if not page_title: page_title = raw_title.strip()
            
        subtitle_tag = soup.find('small', class_='text-muted') 
        page_subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else ""
            
        script_tag = soup.find('script', string=re.compile(r'window\.vueData'))
        if not script_tag: return [] 
        script_content = script_tag.string
        match_start = re.search(r'window\.vueData\s*=\s*\{', script_content)
        if not match_start: return []
        start_index = match_start.end() - 1 
        brace_count = 0
        end_index = -1
        for i, char in enumerate(script_content[start_index:]):
            if char == '{': brace_count += 1
            elif char == '}': brace_count -= 1
            if brace_count == 0:
                end_index = start_index + i
                break
        if end_index == -1: return []
        js_object_string = script_content[start_index : end_index + 1]
        data_dict = pyjson5.loads(js_object_string)
        tables_data_list = data_dict.get('tablesData', [])
        if not tables_data_list: return [] 
        
        extracted_tables = [] 
        for i, table_data in enumerate(tables_data_list):
            json_title = table_data.get('title', "")
            t_low_check = f"{url} {link_text} {json_title} {page_title}".lower()
            is_adj_table = ('adjudicator' in t_low_check or 'juez' in t_low_check)

            if is_adj_table:
                rows_list = []
                for row in table_data.get('data', []):
                    nombre = ""
                    institucion = None
                    is_adj_core = 0.0
                    is_independent = 0.0

                    if len(row) > 0 and isinstance(row[0], dict):
                        nombre = row[0].get('text', '')

                    if len(row) > 1:
                        cell_inst = row[1]
                        inst_text = cell_inst.get('text', '') if isinstance(cell_inst, dict) else str(cell_inst)
                        if inst_text and inst_text not in ['—', '']:
                            institucion = inst_text

                    if len(row) > 2 and isinstance(row[2], dict):
                        is_adj_core = 1.0 if row[2].get('icon') == 'check' else 0.0

                    if len(row) > 3 and isinstance(row[3], dict):
                        is_independent = 1.0 if row[3].get('icon') == 'check' else 0.0

                    if nombre:
                        rows_list.append({
                            'name': nombre,
                            'institution': institucion,
                            'adjcore': is_adj_core,
                            'independent': is_independent
                        })

                if rows_list:
                    df_adj = pd.DataFrame(rows_list)
                    final_table_title = json_title or page_title or f"Jueces_{i+1}"
                    extracted_tables.append((final_table_title, df_adj))
                continue

            advancing_count = 0
            is_elim_round = False
            for row in table_data.get('data', []):
                for cell in row:
                    if isinstance(cell, dict):
                        status = cell.get('text')
                        if status == 'advancing': advancing_count += 1; is_elim_round = True
                        elif status == 'eliminated': is_elim_round = True
            
            elim_round_name = get_elim_round_name(advancing_count, json_title, page_title, page_subtitle, link_text)
            
            final_table_title = None
            round_match = re.search(r'/results/round/(\d+)/', url)
            
            if is_elim_round and elim_round_name:
                final_table_title = elim_round_name
                if json_title and json_title.lower() not in final_table_title.lower() and "nov" not in json_title.lower():
                     final_table_title += f" - {json_title}"
            elif round_match:
                round_num = round_match.group(1)
                final_table_title = f"Ronda {round_num}" 
                if json_title: final_table_title += f" - {json_title}"
            
            if final_table_title is None:
                final_table_title = json_title or page_title or f"Datos_{i+1}"

            headers = [h.get('title', h.get('key')) for h in table_data.get('head', [])]
            rows_list = []
            for row_data_list in table_data.get('data', []):
                row_values = []
                for cell_data in row_data_list:
                    value_to_clean = cell_data.get('text') if isinstance(cell_data, dict) else cell_data
                    if isinstance(value_to_clean, str) and '<' in value_to_clean:
                        row_values.append(BeautifulSoup(value_to_clean, 'lxml').get_text())
                    else:
                        row_values.append(cell_data if not isinstance(cell_data, dict) else cell_data.get('text', str(cell_data)))
                rows_list.append(row_values)
            df = pd.DataFrame(rows_list, columns=headers)
            df = df.replace('—', np.nan) 
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col])
                except (ValueError, TypeError):
                    pass
            extracted_tables.append((final_table_title, df))
        return extracted_tables
    except Exception as e:
        log_func(f"  [!] Error extrayendo tabla de {url}: {e}")
        return []


def create_team_round_key(df, team_col, round_col, tourney_col):
    try:
        t_clean = df[team_col].astype(str).str.replace(r'[\W_]+', '', regex=True)
        r_clean = df[round_col].astype(str).str.replace(r'[\W_]+', '', regex=True)
        tr_clean = df[tourney_col].astype(str).str.replace(r'[\W_]+', '', regex=True)
        return t_clean + r_clean + tr_clean
    except Exception:
        return None


# ==============================================================================
# CAPA ADITIVA: EXTRACCIÓN DE PAPELETAS Y ROLES (CON FALLBACK DE TEAM RECORD)
# ==============================================================================

def extract_ballots_from_team_record(team_record_url, log_func=print):
    try:
        response = requests.get(team_record_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        ballot_mappings = []
        script_tag = soup.find('script', string=re.compile(r'window\.vueData'))
        if script_tag:
            match_start = re.search(r'window\.vueData\s*=\s*\{', script_tag.string)
            if match_start:
                start_index = match_start.end() - 1 
                brace_count, end_index = 0, -1
                for i, char in enumerate(script_tag.string[start_index:]):
                    if char == '{': brace_count += 1
                    elif char == '}': brace_count -= 1
                    if brace_count == 0:
                        end_index = start_index + i
                        break
                if end_index != -1:
                    data_dict = pyjson5.loads(script_tag.string[start_index : end_index + 1])
                    for table_data in data_dict.get('tablesData', []):
                        for row in table_data.get('data', []):
                            round_name, ballot_link = "R1", None
                            for cell in row:
                                if isinstance(cell, dict):
                                    c_text = str(cell.get('text', ''))
                                    if re.match(r'^(R\d+|SF|GF|QF|OF|R32|PSF|PQF|PF)$', c_text, re.IGNORECASE):
                                        round_name = c_text
                                    l_val = cell.get('link')
                                    if l_val and ('scoresheets' in l_val or 'debate' in l_val):
                                        ballot_link = urljoin(team_record_url, l_val)
                            if ballot_link:
                                ballot_mappings.append({'round': round_name, 'ballot_url': ballot_link})
        return ballot_mappings
    except Exception as e:
        return []


def extract_ballot_speakers_from_url(url, round_context="R1", log_func=print):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        scoresheet_divs = soup.find_all('div', class_='list-group')
        if not scoresheet_divs: return []

        ballot_records = []
        banco_mapping = [
            ("Opening Government", "PM", "DPM"),
            ("Opening Opposition", "LO", "DLO"),
            ("Closing Government", "MG", "GW"),
            ("Closing Opposition", "MO", "OW")
        ]

        for idx, list_group in enumerate(scoresheet_divs[:4]):
            if idx >= len(banco_mapping): break
            _, role_1, role_2 = banco_mapping[idx]
            speakers_in_team = []
            
            for item in list_group.find_all('li', class_='list-group-item'):
                strong_tag = item.find('strong')
                badge_tag = item.find('span', class_='badge')
                
                if strong_tag and badge_tag:
                    d_role = strong_tag.get_text(strip=True)
                    full_text = item.get_text(" ", strip=True)
                    speaker_name = full_text.replace(d_role, "").replace(badge_tag.get_text(), "").strip()
                    speaker_name = re.sub(r'\s+\d+(\.\d+)?$', '', speaker_name).strip()
                    
                    try:
                        score = float(badge_tag.get_text(strip=True))
                    except ValueError:
                        score = np.nan
                    speakers_in_team.append((speaker_name, d_role, score))

            if len(speakers_in_team) >= 2:
                for s_name, s_role, _ in speakers_in_team[:2]:
                    ballot_records.append({
                        'name': s_name,
                        'd_role': s_role,
                        'round': round_context
                    })
        return ballot_records
    except Exception as e:
        return []


def extraer_roles_desde_team_record_fallback(team_record_url, torneo_nombre, log_func=print):
    """
    Alternativa robusta: extrae roles y puntajes directamente desde el tooltip y estructura
    de la tabla Team Record cuando las papeletas públicas no están disponibles o vienen vacías.
    """
    MAPEO_ROLES_BP = {
        "Opening Government": ("OG", ["PM", "DPM"]),
        "Opening Opposition": ("OO", ["LO", "DLO"]),
        "Closing Government": ("CG", ["MG", "GW"]),
        "Closing Opposition": ("CO", ["MO", "OW"]),
    }
    registros_recuperados = []
    try:
        response = requests.get(team_record_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        script_tag = soup.find('script', string=re.compile(r'window\.vueData'))
        if not script_tag: return []
        
        match_start = re.search(r'window\.vueData\s*=\s*\{', script_tag.string)
        if not match_start: return []
        start_index = match_start.end() - 1 
        brace_count, end_index = 0, -1
        for i, char in enumerate(script_tag.string[start_index:]):
            if char == '{': brace_count += 1
            elif char == '}': brace_count -= 1
            if brace_count == 0:
                end_index = start_index + i
                break
        if end_index == -1: return []
        
        data_dict = pyjson5.loads(script_tag.string[start_index : end_index + 1])
        for table_data in data_dict.get('tablesData', []):
            for fila in table_data.get('data', []):
                # Validar longitud mínima de celdas en la fila
                if len(fila) < 5: continue
                
                round_name = fila[0].get("text", "").strip() if isinstance(fila[0], dict) else ""
                tooltip_speaks = fila[3].get("tooltip") if isinstance(fila[3], dict) else None
                if not tooltip_speaks: continue

                # 1. Extraer nombre del equipo desde el popover
                popover_data = fila[1].get("popover", {}) if isinstance(fila[1], dict) else {}
                content_list = popover_data.get("content", [])
                equipo = ""
                if content_list and isinstance(content_list[0], dict):
                    popover_html = content_list[0].get("text", "")
                    soup_pop = BeautifulSoup(popover_html, "html.parser")
                    strong_tag = soup_pop.find("strong")
                    if strong_tag:
                        equipo = re.sub(r"\s*\([A-Z]{2}\)$", "", strong_tag.text).strip()

                # 2. Extraer cámara y mapear roles
                camara = fila[4].get("text", "").strip() if isinstance(fila[4], dict) else ""
                if camara not in MAPEO_ROLES_BP: continue
                t_role, d_roles_orden = MAPEO_ROLES_BP[camara]

                # 3. Separar el tooltip por <br> para mantener el orden exacto de intervención
                partes_speakers = re.split(r"<br\s*/?>", tooltip_speaks)
                for idx, parte in enumerate(partes_speakers):
                    if idx >= len(d_roles_orden): break
                    texto_limpio = BeautifulSoup(parte, "html.parser").get_text()
                    match = re.match(r"([\d\.]+)\s+for\s+(.+)", texto_limpio.strip())
                    if match:
                        puntaje = float(match.group(1))
                        nombre_orador = match.group(2).strip()
                        d_role = d_roles_orden[idx]

                        registros_recuperados.append({
                            'tournament': torneo_nombre,
                            'round': round_name,
                            'team': equipo,
                            'name': nombre_orador,
                            'speakers': puntaje,
                            't_role': t_role,
                            'd_role': d_role
                        })
    except Exception as e:
        log_func(f"  [!] Error en fallback Team Record: {e}")
    return registros_recuperados


def extract_speaker_roles_and_ballots_from_speaker_tab(speaker_tab_url, torneo_nombre="Torneo", log_func=print):
    try:
        response = requests.get(speaker_tab_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        script_tag = soup.find('script', string=re.compile(r'window\.vueData'))
        if not script_tag: return []
        
        match_start = re.search(r'window\.vueData\s*=\s*\{', script_tag.string)
        if not match_start: return []
        
        start_index = match_start.end() - 1 
        brace_count, end_index = 0, -1
        for i, char in enumerate(script_tag.string[start_index:]):
            if char == '{': brace_count += 1
            elif char == '}': brace_count -= 1
            if brace_count == 0:
                end_index = start_index + i
                break
        if end_index == -1: return []
        
        data_dict = pyjson5.loads(script_tag.string[start_index : end_index + 1])
        tablesData = data_dict.get('tablesData', [])
        if not tablesData: return []
        
        processed_teams = set()
        all_enriched_roles = []
        seen_ballots = set()
        
        for table_data in tablesData:
            for row in table_data.get('data', []):
                team_link = None
                for cell in row:
                    if isinstance(cell, dict):
                        popover = cell.get('popover', {})
                        for content_item in popover.get('content', []):
                            l_val = content_item.get('link')
                            if l_val and 'team' in l_val:
                                team_link = urljoin(speaker_tab_url, l_val)
                                break
                    if team_link: break
                
                if team_link and team_link not in processed_teams:
                    processed_teams.add(team_link)
                    
                    # 1. Intentar extraer mediante papeletas públicas normales
                    ballot_mappings = extract_ballots_from_team_record(team_link, log_func)
                    ballots_encontradas = False
                    
                    if ballot_mappings:
                        for b_map in ballot_mappings:
                            b_url = b_map['ballot_url']
                            r_ctx = b_map['round']
                            if b_url not in seen_ballots:
                                seen_ballots.add(b_url)
                                ballot_speakers = extract_ballot_speakers_from_url(b_url, r_ctx, log_func)
                                if ballot_speakers:
                                    all_enriched_roles.extend(ballot_speakers)
                                    ballots_encontradas = True
                    
                    # 2. FALLBACK: Si no hay papeletas públicas (ej. PUCP Open o Rosario Open), usar Team Record
                    if not ballots_encontradas:
                        log_func(f"  [i] Papletas no disponibles para equipo en {team_link}. Usando fallback de Team Record...")
                        fallback_records = extraer_roles_desde_team_record_fallback(team_link, torneo_nombre, log_func)
                        if fallback_records:
                            all_enriched_roles.extend(fallback_records)
                            
        return all_enriched_roles
    except Exception as e:
        return []