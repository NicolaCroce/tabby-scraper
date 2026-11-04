# extractor.py
"""
Módulo encargado de la extracción y parseo de datos desde plataformas Tabbycat.
Contiene la lógica de peticiones HTTP, BeautifulSoup, extracción de objetos JSON (vueData),
resolución de portales de bienvenida y lectura detallada de papeletas (ballots).
"""
import re
from urllib.parse import urljoin, urlparse
import numpy as np
import pandas as pd
import pyjson5
import requests
from bs4 import BeautifulSoup


def resolver_url_base_torneo(base_url, log_func=print):
    """
    Verifica si la URL es un portal de bienvenida de Tabbycat (con múltiples categorías).
    Prioriza estrictamente la categoría 'Open' o la principal antes que masters o alternas.
    """
    try:
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
            
            # Omitir enlaces administrativos o de login
            if 'login' in full_url or 'admin' in full_url:
                continue
                
            # PRIORIDAD MÁXIMA: Si el link o texto contiene explícitamente 'open'
            if 'open' in full_url.lower() or 'open' in text:
                candidato_open = full_url
                break # Encontró el open exacto, salimos de inmediato
                
            # Si no hay 'open' directo, guardamos una opción general o de campeonato
            if any(k in text for k in ['campeonato', 'mundial', 'general']) and not candidato_url:
                candidato_url = full_url
                        
        # Seleccionar primero el open si existe, de lo contrario el candidato general, o la URL original
        url_elegida = candidato_open or candidato_url
        
        if url_elegida and url_elegida != base_url:
            log_func(f"  [i] Portal de bienvenida detectado. Redirigindo a la categoría principal (Open): {url_elegida}")
            return url_elegida
            
        return base_url
    except Exception as e:
        log_func(f"  [!] No se pudo resolver la URL base, usando la original: {e}")
        return base_url

def find_data_links(base_url, log_func=print):
    """Busca enlaces relevantes de oradores, equipos, rondas y mociones en la página del torneo."""
    base_url_efectiva = resolver_url_base_torneo(base_url, log_func)
    
    log_func(f"Buscando enlaces de datos en: {base_url_efectiva}")
    PALABRAS_CLAVE = [
        'speaker', 'team', 'result', 'draw', 'standings', 'tab', 
        'break', 'adjudicator', 'juez', 'motion', 'mocion', 'ballot'
    ]
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
    """Extrae las mociones y cajones informativos (infoslides) de la página de mociones."""
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

            modal = card.find('div', class_='modal-body')
            infoslide_text = modal.get_text(separator='\n', strip=True) if modal else None

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
    """Determina la ronda de eliminación estándar según los equipos que avanzan."""
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


def extract_ballot_speakers_from_url(url, log_func=print):
    """
    Extrae los puntajes, nombres y roles exactos de los oradores directamente desde 
    la vista de la papeleta (ballot) de Tabbycat, mapeando el orden estricto de BP.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        scoresheet_divs = soup.find_all('div', class_='list-group')
        if not scoresheet_divs:
            return []

        ballot_records = []
        banco_mapping = [
            ("Opening Government", "PM", "DPM"),
            ("Opening Opposition", "LO", "DLO"),
            ("Closing Government", "MG", "GW"),
            ("Closing Opposition", "MO", "OW")
        ]

        for idx, list_group in enumerate(scoresheet_divs[:4]):
            side_name, role_1, role_2 = banco_mapping[idx]
            items = list_group.find_all('li', class_='list-group-item')
            
            speakers_in_team = []
            team_name = ""
            
            for item in items:
                text_content = item.get_text()
                strong_tag = item.find('strong')
                badge_tag = item.find('span', class_='badge')
                
                if strong_tag and badge_tag:
                    d_role = strong_tag.get_text(strip=True)
                    full_text = item.get_text(" ", strip=True)
                    speaker_name = full_text.replace(d_role, "").replace(badge_tag.get_text(), "").strip()
                    try:
                        score = float(badge_tag.get_text(strip=True))
                    except ValueError:
                        score = np.nan
                    speakers_in_team.append((speaker_name, d_role, score))
                elif "Total for" in text_content:
                    match_team = re.search(r'Total for\s+(.*?)\s+\(', text_content)
                    if match_team:
                        team_name = match_team.group(1).strip()

            if len(speakers_in_team) >= 2 and team_name:
                s1_name, s1_role, s1_score = speakers_in_team[0]
                ballot_records.append({
                    'team': team_name,
                    'Side': side_name,
                    'name': s1_name,
                    'Total': s1_score,
                    'd_role': s1_role,
                    't_role': 'first'
                })
                s2_name, s2_role, s2_score = speakers_in_team[1]
                ballot_records.append({
                    'team': team_name,
                    'Side': side_name,
                    'name': s2_name,
                    'Total': s2_score,
                    'd_role': s2_role,
                    't_role': 'second'
                })

        return ballot_records
    except Exception as e:
        log_func(f"  [!] Error extrayendo ballot de {url}: {e}")
        return []


def extract_tables_from_url(url, link_text="", log_func=print):
    """Extrae las tablas incrustadas en el objeto JavaScript (window.vueData) de Tabbycat limpiando objetos JSON."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'lxml')
        
        page_title_tag = soup.find('title')
        page_title = page_title_tag.get_text(strip=True) if page_title_tag else "" 
        if page_title and '—' in page_title: page_title = page_title.split('—')[-1].strip()
            
        subtitle_tag = soup.find('small', class_='text-muted') 
        page_subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else ""
            
        script_tag = soup.find('script', string=re.compile(r'window\.vueData'))
        if not script_tag: return [] 
        script_content = script_tag.string
        match_start = re.search(r'window\.vueData\s*=\s*\{', script_content)
        if not match_start: return []
        
        start_index = match_start.end() - 1 
        brace_count, end_index = 0, -1
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
            advancing_count = 0
            is_elim_round = False
            for row in table_data.get('data', []):
                for cell in row:
                    if isinstance(cell, dict):
                        status = cell.get('text')
                        if status == 'advancing': advancing_count += 1; is_elim_round = True
                        elif status == 'eliminated': is_elim_round = True
            
            json_title = table_data.get('title', "") 
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
                    # EXTRAER SOLAMENTE EL TEXTO SI VIENE COMO DICCIONARIO COMPLEX DE VUE/TABBYCAT
                    if isinstance(cell_data, dict):
                        value_to_clean = cell_data.get('text', str(cell_data))
                    else:
                        value_to_clean = cell_data

                    if isinstance(value_to_clean, str) and '<' in value_to_clean:
                        row_values.append(BeautifulSoup(value_to_clean, 'lxml').get_text())
                    else:
                        row_values.append(value_to_clean)
                rows_list.append(row_values)
                
            df = pd.DataFrame(rows_list, columns=headers)
            
            # Sanitización global extra para cualquier columna que aún sea dict
            for col in df.columns:
                df[col] = df[col].apply(lambda x: x.get('text') if isinstance(x, dict) and 'text' in x else x)
                df[col] = df[col].replace('—', np.nan) 
                df[col] = pd.to_numeric(df[col], errors='ignore')
                
            extracted_tables.append((final_table_title, df))
            
        return extracted_tables
    except Exception as e:
        log_func(f"  [!] Error extrayendo tabla de {url}: {e}")
        return []

def create_team_round_key(df, team_col, round_col, tourney_col):
    """Crea una llave única combinando equipo, ronda y torneo para control de datos."""
    try:
        t_clean = df[team_col].astype(str).str.replace(r'[\W_]+', '', regex=True)
        r_clean = df[round_col].astype(str).str.replace(r'[\W_]+', '', regex=True)
        tr_clean = df[tourney_col].astype(str).str.replace(r'[\W_]+', '', regex=True)
        return t_clean + r_clean + tr_clean
    except Exception:
        return None