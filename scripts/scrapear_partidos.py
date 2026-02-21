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
    """
    Lee las URLs de partidos desde un archivo .txt.
    - Si la variable de entorno ALETHEIA_TXT_FILE está definida (llamada desde main.py),
      usa ese archivo directamente.
    - Si no, busca en output_data/; si hay varios pide al usuario que elija uno.
    Siempre guarda en la subcarpeta derivada del nombre del .txt elegido.
    """
    import glob

    # Prioridad 1: archivo especificado por main.py via variable de entorno
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

    # Carpeta de salida siempre derivada del .txt elegido
    nombre_base = os.path.splitext(os.path.basename(ruta_txt))[0]
    if nombre_base.startswith("enlaces_"):
        nombre_base = nombre_base[len("enlaces_"):]
    carpeta_salida = os.path.join(OUTPUT_DIR, nombre_base)
    os.makedirs(carpeta_salida, exist_ok=True)
    print(f"   Carpeta de salida: {carpeta_salida}")
    return urls, carpeta_salida

URLS_PARTIDOS, OUTPUT_DIR = cargar_urls_desde_txt()

# Alias de equipos para parsear picks/bans
ALIAS_MAP = {
    # AMERICAS
    "SEN": "Sentinels",     "EG": "Evil Geniuses",  "C9": "Cloud9",
    "100T": "100 Thieves",  "MIBR": "MIBR",          "NRG": "NRG",
    "LOUD": "LOUD",         "LEV": "Leviatán",        "KRÜ": "KRÜ Esports",
    "G2": "G2 Esports",     "FUR": "FURIA",           "ENV": "Envy",
    # EMEA
    "M8": "Gentle Mates",   "FNC": "Fnatic",          "NAVI": "Natus Vincere",
    "TL": "Team Liquid",    "VIT": "Team Vitality",   "KC": "Karmine Corp",
    "TH": "Team Heretics",  "BBL": "BBL Esports",     "FUT": "FUT Esports",
    "KOI": "KOI",           "GX": "GiantX",
    # CHINA
    "EDG": "EDward Gaming", "FPX": "FunPlus Phoenix", "BLG": "Bilibili Gaming",
    "JDG": "JD Gaming",     "TE": "Trace Esports",    "AG": "All Gamers",
    "XLG": "Xi Lai Gaming", "WOL": "Wolves Esports",  "TYL": "TYLOO",
    "DRG": "Dragon Ranger Gaming",                    "NOVA": "Nova Esports",
    # PACIFIC
    "PRX": "Paper Rex",     "DRX": "DRX",             "T1": "T1",
    "ZETA": "ZETA DIVISION","GEN": "Gen.G",            "RRQ": "Rex Regum Qeon",
    "DFM": "DetonatioN FocusMe",                      "TLN": "Talon Esports",
    "TS": "Team Secret",    "GE": "Global Esports",   "BLD": "Bleed Esports",
}


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

        # Equipos y score
        team_divs  = soup.select('div.match-header-vs .wf-title-med')
        score_spans = soup.select('div.match-header-vs-score .js-spoiler span')

        if len(team_divs) >= 2 and len(score_spans) >= 3:
            t1_name = team_divs[0].get_text(strip=True)
            t2_name = team_divs[1].get_text(strip=True)
            s1 = score_spans[0].get_text(strip=True)
            s2 = score_spans[2].get_text(strip=True)
        else:
            t1_name = t2_name = "N/A"
            s1 = s2 = "0"

        data['equipo_a'] = t1_name
        data['equipo_b'] = t2_name
        data['score']    = f"{s1}-{s2}"

        # Picks, bans y decider
        note_div = soup.find('div', class_='match-header-note')
        note_text = note_div.get_text(strip=True) if note_div else ""

        picks_a, picks_b = [], []
        bans_a,  bans_b  = [], []
        deciders = []

        if note_text:
            clean_text = note_text.replace("Bo3", "").replace("Bo5", "").strip()
            acciones = [x.strip() for x in clean_text.split(';') if x.strip()]

            for accion in acciones:
                accion_lower = accion.lower()

                if "remains" in accion_lower:
                    deciders.append(accion_lower.replace("remains", "").strip().title())
                    continue

                partes    = accion.split(' ')
                mapa      = partes[-1]
                actor_tag = partes[0].upper()

                es_equipo_a = False
                root_name_a = t1_name.split(' ')[0].lower()

                if t1_name.lower() in accion_lower or root_name_a in accion_lower:
                    es_equipo_a = True
                elif actor_tag in ALIAS_MAP:
                    nombre_alias = ALIAS_MAP[actor_tag].lower()
                    if nombre_alias in t1_name.lower():
                        es_equipo_a = True

                if "ban" in accion_lower:
                    (bans_a if es_equipo_a else bans_b).append(mapa)
                elif "pick" in accion_lower:
                    (picks_a if es_equipo_a else picks_b).append(mapa)

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
    # Eliminar URLs duplicadas manteniendo orden
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
            'equipo_a', 'equipo_b', 'score',
            'pick_a', 'pick_b', 'ban_a', 'ban_b', 'decider', 'patch'
        ]

        df_partidos = pd.DataFrame(datos_acumulados)

        for col in columnas:
            if col not in df_partidos.columns:
                df_partidos[col] = "N/A"

        df_partidos = df_partidos[columnas]

        print("\n✅ DATOS OBTENIDOS (df_partidos):")
        print(df_partidos.to_string(index=False))

        # Guardar Excel
        ruta_excel = os.path.join(OUTPUT_DIR, "vct_partidos.xlsx")
        df_partidos.to_excel(ruta_excel, index=False, sheet_name="Partidos")
        print(f"\n💾 Excel guardado en: {ruta_excel}")

    print("\n🏁 Script finalizado.")
