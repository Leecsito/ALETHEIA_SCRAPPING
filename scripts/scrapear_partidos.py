"""
ALETHEIA - Script 2: Partidos VCT 2026
Fuente: VLR.gg
Salida: output_data/vct_partidos.xlsx
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import os

# --- CONFIGURACIÓN ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# CARGA DE URLs DESDE ARCHIVO .txt  +  CARPETA DE SALIDA DINÁMICA
# ---------------------------------------------------------------------------
def cargar_urls_desde_txt():
    import glob

    txt_forzado = os.environ.get("ALETHEIA_TXT_FILE")
    if txt_forzado:
        ruta_txt = txt_forzado
        print(f"Cargando enlaces desde: {os.path.basename(ruta_txt)}")
    else:
        archivos = glob.glob(os.path.join(OUTPUT_DIR, "*.txt"))
        if not archivos:
            print("No se encontro ningun archivo .txt en output_data/.")
            ruta_txt = input("   Ingresa la ruta del archivo .txt: ").strip()
        elif len(archivos) == 1:
            ruta_txt = archivos[0]
            print(f"Cargando enlaces desde: {os.path.basename(ruta_txt)}")
        else:
            print("Se encontraron varios archivos .txt:")
            for i, f in enumerate(archivos):
                print(f"   [{i+1}] {os.path.basename(f)}")
            while True:
                try:
                    sel = int(input("   Selecciona el numero del archivo a usar: ").strip())
                    if 1 <= sel <= len(archivos):
                        ruta_txt = archivos[sel - 1]
                        break
                except ValueError:
                    pass
                print("   Seleccion invalida, intenta de nuevo.")

    with open(ruta_txt, 'r', encoding='utf-8') as f:
        urls = [linea.strip() for linea in f if linea.strip()]
    print(f"   -> {len(urls)} URLs cargadas.")

    nombre_base = os.path.splitext(os.path.basename(ruta_txt))[0]
    if nombre_base.startswith("enlaces_"):
        nombre_base = nombre_base[len("enlaces_"):]
    carpeta_salida = os.path.join(OUTPUT_DIR, nombre_base)
    os.makedirs(carpeta_salida, exist_ok=True)
    print(f"   Carpeta de salida: {carpeta_salida}")
    return urls, carpeta_salida

URLS_PARTIDOS, OUTPUT_DIR = cargar_urls_desde_txt()

def construir_siglas_reales(soup, global_team_a, global_team_b):
    """Lee las siglas reales que VLR.gg asigna a cada equipo en este partido
    (ej. 't1' -> 'A', 'krx' -> 'B') desde la primera columna del bloque
    vlr-rounds del DOM. Mismo patrón que construir_siglas_reales() en
    scrapear_vlr_corregido.py.

    Resuelve siglas no derivables del nombre con heurísticas de texto
    (ej. 'KRX' para KIWOOM DRX), que antes se atribuían al equipo A por
    defecto corrompiendo picks/bans.

    Devuelve {sigla_lower: 'A'|'B'} o {} si no se pueden leer del DOM.
    Solo se necesita el primer mapa disponible: las siglas son idénticas en todos.
    """
    for contenedor in soup.find_all('div', class_='vm-stats-game'):
        if contenedor.get('data-game-id') in (None, 'all'):
            continue
        nombres = [d.get_text(strip=True)
                   for d in contenedor.find_all('div', class_='team-name')]
        rc = contenedor.find('div', class_='vlr-rounds')
        if not rc:
            continue
        col0 = rc.find_all('div', class_='vlr-rounds-row-col')
        if not col0:
            continue
        tags = [d.get_text(strip=True)
                for d in col0[0].find_all('div', class_='team')]
        if len(nombres) >= 2 and len(tags) >= 2:
            mapa = {}
            for nombre, tag in zip(nombres[:2], tags[:2]):
                if nombre == global_team_a:
                    mapa[tag.lower()] = 'A'
                elif nombre == global_team_b:
                    mapa[tag.lower()] = 'B'
            if mapa:
                return mapa
    return {}

# ---------------------------------------------------------------------------
# FUNCIÓN: EXTRAER DATOS DE UN PARTIDO
# ---------------------------------------------------------------------------
def obtener_partido(url):
    print(f"🕵️  Conectando a: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"  ⛔ Error HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        if soup.title and "Access Denied" in soup.title.get_text():
            print("  ⛔ VLR.gg bloqueó la petición.")
            return None

        data = {}

        # ID del partido
        match_id_search = re.search(r'vlr\.gg/(\d+)', url)
        data['match_id'] = match_id_search.group(1) if match_id_search else "Unknown"

        # Torneo y fase
        event_link = soup.find('a', class_='match-header-event')
        if event_link:
            torneo_div = event_link.find('div', style='font-weight: 700;')
            data['torneo'] = torneo_div.get_text(strip=True) if torneo_div else "N/A"
            series_div = event_link.find('div', class_='match-header-event-series')
            data['fase'] = (
                series_div.get_text(separator=' ', strip=True)
                .replace('\t', '').replace('\n', '').strip()
                if series_div else "N/A"
            )
        else:
            data['torneo'] = "N/A"
            data['fase'] = "N/A"

        # Fecha y patch
        date_div = soup.find('div', class_='match-header-date')
        data['fecha'] = "Unknown"
        data['patch'] = "Unknown"
        if date_div:
            moment_div = date_div.find('div', class_='moment-tz-convert')
            data['fecha'] = moment_div.get_text(strip=True) if moment_div else date_div.get_text(strip=True).split("Patch")[0].strip()
            patch_match = re.search(r'Patch\s+(\d+\.\d+)', date_div.get_text(" ", strip=True))
            if patch_match:
                data['patch'] = patch_match.group(0)

        # Equipos e IDs
        team_links = soup.select('div.match-header-vs a.match-header-link')
        team_divs = soup.select('div.match-header-vs .wf-title-med')
        
        t1_name = t2_name = "N/A"
        t1_id = t2_id = "N/A"
        
        if len(team_divs) >= 2:
            t1_name = team_divs[0].get_text(strip=True)
            t2_name = team_divs[1].get_text(strip=True)
            
        if len(team_links) >= 2:
            href_a = team_links[0].get('href', '')
            href_b = team_links[1].get('href', '')
            
            id_a_search = re.search(r'team/(\d+)', href_a)
            id_b_search = re.search(r'team/(\d+)', href_b)
            
            t1_id = id_a_search.group(1) if id_a_search else "N/A"
            t2_id = id_b_search.group(1) if id_b_search else "N/A"

        # Score
        score_container = soup.select_one('div.match-header-vs-score .sp-hide') or soup.select_one('div.match-header-vs-score .js-spoiler')
        s1 = s2 = "0"
        if score_container:
            spans = score_container.find_all('span')
            if len(spans) >= 3:
                s1 = spans[0].get_text(strip=True)
                s2 = spans[2].get_text(strip=True)

        data['equipo_a'] = t1_name
        data['equipo_a_id'] = t1_id
        data['equipo_b'] = t2_name
        data['equipo_b_id'] = t2_id
        data['score']    = f"{s1}-{s2}"

        # Picks, bans y decider
        note_div = soup.find('div', class_='match-header-note')
        note_text = note_div.get_text(strip=True) if note_div else ""

        picks_a, picks_b = [], []
        bans_a,  bans_b  = [], []
        deciders = []

        if note_text:
            # Resolución de siglas del veto directamente desde el DOM
            # (vlr-rounds). Inmune a siglas no derivables del nombre,
            # ej. 'KRX' para KIWOOM DRX.
            siglas_map = construir_siglas_reales(soup, t1_name, t2_name)
            if not siglas_map:
                print("  ⚠️  No se pudieron leer las siglas del DOM; "
                      "picks/bans quedarán vacíos")

            clean_text = note_text.replace("Bo3", "").replace("Bo5", "").strip()
            acciones = [x.strip() for x in clean_text.split(';') if x.strip()]

            for accion in acciones:
                accion_lower = accion.lower()

                if "remains" in accion_lower or "left over" in accion_lower:
                    mapa = accion.split(' ')[0].title()
                    deciders.append(mapa)
                    continue

                partes = accion.split(' ')
                if len(partes) >= 3:
                    actor_tag = partes[0].lower()
                    accion_type = partes[1].lower()
                    mapa = " ".join(partes[2:]).title()

                    lado = siglas_map.get(actor_tag)
                    if lado is None:
                        # No atribuir a ciegas: antes toda sigla no reconocida
                        # caía al equipo A por defecto (bug KRX -> T1).
                        print(f"  ⚠️  Sigla de veto no reconocida: "
                              f"'{partes[0]}' ({accion})")
                        continue

                    es_equipo_a = (lado == 'A')

                    if "ban" in accion_type:
                        if es_equipo_a: bans_a.append(mapa)
                        else: bans_b.append(mapa)
                    elif "pick" in accion_type:
                        if es_equipo_a: picks_a.append(mapa)
                        else: picks_b.append(mapa)

        data['pick_a']   = ", ".join(picks_a)
        data['pick_b']   = ", ".join(picks_b)
        data['ban_a']    = ", ".join(bans_a)
        data['ban_b']    = ", ".join(bans_b)
        data['decider']  = ", ".join(deciders)

        return data

    except Exception as e:
        print(f"  ❌ Error interno procesando {url}: {e}")
        return None

# ---------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    urls_unicas = list(dict.fromkeys(URLS_PARTIDOS))
    print(f"\n🚀 Iniciando extracción de {len(urls_unicas)} partidos...\n")

    datos_acumulados = []

    for link in urls_unicas:
        info = obtener_partido(link)
        if info:
            datos_acumulados.append(info)
        time.sleep(1)

    if not datos_acumulados:
        print("\n⚠️ No se pudo obtener información de ningún partido.")
    else:
        columnas = [
            'match_id', 'torneo', 'fase', 'fecha',
            'equipo_a', 'equipo_a_id', 'equipo_b', 'equipo_b_id', 'score',
            'pick_a', 'pick_b', 'ban_a', 'ban_b', 'decider', 'patch'
        ]

        df_partidos = pd.DataFrame(datos_acumulados)

        for col in columnas:
            if col not in df_partidos.columns:
                df_partidos[col] = "N/A"

        df_partidos = df_partidos[columnas]

        print("\n✅ DATOS OBTENIDOS (df_partidos):")
        print(df_partidos.to_string(index=False))

        ruta_excel = os.path.join(OUTPUT_DIR, "vct_partidos.xlsx")
        df_partidos.to_excel(ruta_excel, index=False, sheet_name="Partidos")
        print(f"\n💾 Excel guardado en: {ruta_excel}")

    print("\n🏁 Script finalizado.")