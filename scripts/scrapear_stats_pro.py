import time
import os
import pandas as pd
import re
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from driver_setup import crear_driver

# Carpeta de salida relativa al script
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- CARGA DE ENLACES DESDE ARCHIVO .txt  +  CARPETA DE SALIDA DINÁMICA ---
def cargar_enlaces_desde_txt():
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

ENLACES, OUTPUT_DIR = cargar_enlaces_desde_txt()


def esperar_disponible(driver, condicion, timeout=15):
    """Espera best-effort a que se cumpla `condicion`.

    Devuelve True si se cumplió, False si expiró. Nunca lanza excepción: si
    expira, el llamador decide si continúa, de modo que un timeout puntual no
    provoca pérdida de datos. Sustituye a los `time.sleep()` fijos: espera
    solo lo necesario cuando la página ya está lista.
    """
    try:
        WebDriverWait(driver, timeout).until(condicion)
        return True
    except Exception:
        return False


def generar_abbrev(nombre):
    """Misma heurística usada en scrapear_vlr_corregido.py para resolver abreviaturas."""
    tokens = re.findall(r'\d+|[a-zA-ZÀ-ÿ]+', nombre)
    abbrev = ''
    for token in tokens:
        if token.isdigit():
            abbrev += token
        elif token.isupper():
            abbrev += token
        else:
            abbrev += token[0].upper()
    return abbrev.lower()


def construir_mapa_tags(div_mapa, global_team_a, global_team_b, team_a_id, team_b_id):
    """Lee el tag REAL de VLR (ej. 'GX') para cada equipo dentro de este mapa,
    desde el bloque vlr-rounds (mismo que usa scrapear_vlr_corregido.py para
    team_top/team_bot), y lo liga a su team_id vía el nombre completo.
    Devuelve {tag: (team_id, team_name)}."""
    nombres = [d.get_text(strip=True) for d in div_mapa.find_all('div', class_='team-name')]
    rc = div_mapa.find('div', class_='vlr-rounds')
    tags = []
    if rc:
        col0 = rc.find_all('div', class_='vlr-rounds-row-col')
        if col0:
            tags = [d.get_text(strip=True) for d in col0[0].find_all('div', class_='team')]

    mapa_tags = {}
    if len(nombres) < 2 or len(tags) < 2:
        return mapa_tags

    for nombre, tag in zip(nombres[:2], tags[:2]):
        if nombre == global_team_a:
            mapa_tags[tag] = (team_a_id, global_team_a)
        elif nombre == global_team_b:
            mapa_tags[tag] = (team_b_id, global_team_b)
    return mapa_tags


def obtener_stats_detalladas(driver, url):
    print(f"🌐 Procesando: {url}")
    try:
        driver.get(url)
    except Exception as e:
        print(f"❌ Error cargando URL: {e}")
        return []
    # Best-effort: esperar a que la tabla overview (ovw-row) esté en el DOM.
    esperar_disponible(driver, EC.presence_of_element_located(
        (By.CSS_SELECTOR, "div.ovw-row")))
    html = driver.page_source

    soup = BeautifulSoup(html, 'html.parser')

    match_id = "Unknown"
    match_search = re.search(r'vlr\.gg/(\d+)', url)
    if match_search:
        match_id = match_search.group(1)

    # --- Equipos del header (para resolver team_id) ---
    teams_header = soup.find_all('div', class_='match-header-link-name')
    if len(teams_header) >= 2:
        global_team_a = teams_header[0].get_text(strip=True)
        global_team_b = teams_header[1].get_text(strip=True)
    else:
        global_team_a, global_team_b = "TeamA", "TeamB"

    team_a_id, team_b_id = None, None
    for a_tag in soup.find_all('a', class_='match-header-link'):
        clases = a_tag.get('class', [])
        href = a_tag.get('href') or ""
        m_id = re.search(r'/team/(\d+)', href)
        if not m_id:
            continue
        if 'mod-1' in clases:
            team_a_id = int(m_id.group(1))
        elif 'mod-2' in clases:
            team_b_id = int(m_id.group(1))

    print(f"   🎮 {global_team_a}({team_a_id}) vs {global_team_b}({team_b_id})")

    datos_partido = []
    contenedores_mapas = soup.find_all('div', class_='vm-stats-game')

    for div_mapa in contenedores_mapas:
        game_id = div_mapa.get('data-game-id')
        if not game_id or game_id == 'all':
            continue

        map_div = div_mapa.find('div', class_='map')
        if not map_div:
            continue

        map_name_raw = map_div.get_text(strip=True)
        map_name = map_name_raw.split()[0]
        map_id = f"{match_id}_{map_name.lower()}"
        print(f"   📍 Mapa: {map_name} ({map_id})")

        mapa_tags = construir_mapa_tags(div_mapa, global_team_a, global_team_b, team_a_id, team_b_id)
        if len(mapa_tags) < 2:
            print(f"      ⚠️  No se pudo leer el par tag→equipo real de este mapa "
                  f"(nombres/tags insuficientes); los team_id de este mapa quedarán vacíos")

        filas = div_mapa.find_all('div', class_='ovw-row')
        for fila in filas:
            celda_jugador = fila.find('div', class_='ovw-cell mod-player')
            if not celda_jugador:
                continue

            a_tag = celda_jugador.find('a', href=True)
            if not a_tag:
                continue

            m_pid = re.search(r'/player/(\d+)/', a_tag['href'])
            player_id = int(m_pid.group(1)) if m_pid else None

            nombre_div = a_tag.find('div', class_='ovw-player-name')
            player_name = nombre_div.get_text(strip=True) if nombre_div else "Unknown"

            tag_div = a_tag.find('div', class_='ovw-player-tag')
            team_tag = tag_div.get_text(strip=True) if tag_div else ""

            team_id, team_name = mapa_tags.get(team_tag, (None, None))
            if team_id is None:
                print(f"      ⚠️  No se pudo resolver el tag '{team_tag}' de {player_name} "
                      f"contra {global_team_a}/{global_team_b}")

            agente = "Unknown"
            agentes_div = fila.find('div', class_='ovw-agents')
            if agentes_div:
                img = agentes_div.find('img')
                if img and img.get('title'):
                    agente = img['title']

            # Todas las celdas (y sub-celdas de K/D/A) que traen data-col
            celdas_por_col = {}
            for el in fila.find_all(attrs={'data-col': True}):
                celdas_por_col[el['data-col']] = el

            def extraer(col_name, side_class):
                el = celdas_por_col.get(col_name)
                if not el:
                    return None
                span = el.find('span', class_=lambda c: c and side_class in c.split())
                return span.get_text(strip=True).replace('%', '') if span else None

            for nombre_lado, side_class in [('attack', 'mod-t'), ('defense', 'mod-ct')]:
                datos_partido.append({
                    'match_id': match_id,
                    'map_id': map_id,
                    'player_id': player_id,
                    'player_name': player_name,
                    'team_id': team_id,
                    'team_name': team_name,
                    'side': nombre_lado,
                    'agent': agente,
                    'rating': extraer('rating2', side_class),
                    'acs': extraer('acs', side_class),
                    'kills': extraer('kills', side_class),
                    'deaths': extraer('deaths', side_class),
                    'assists': extraer('assists', side_class),
                    'kast': extraer('kast', side_class),
                    'adr': extraer('adr', side_class),
                    'hs_percent': extraer('hsp', side_class),
                    'fk': extraer('fb', side_class),
                    'fd': extraer('fd', side_class),
                })

    return datos_partido


# --- MAIN ---
if __name__ == "__main__":
    print("🚀 Iniciando extracción de estadísticas por lado...")
    print("=" * 60)

    try:
        driver = crear_driver(headless=True)
    except Exception as e:
        print(f"❌ Error inicializando driver: {e}")
        exit()

    todos_los_datos = []

    try:
        for i, link in enumerate(ENLACES):
            print(f"\n[{i+1}/{len(ENLACES)}] Procesando partido...")
            data = obtener_stats_detalladas(driver, link)
            if data:
                todos_los_datos.extend(data)
                print(f"  ✅ {len(data)} filas extraídas")
            else:
                print(f"  ⚠️ No se extrajeron datos")

        if todos_los_datos:
            df = pd.DataFrame(todos_los_datos)

            cols_order = ['match_id', 'map_id', 'player_id', 'player_name', 'team_id', 'team_name',
                          'side', 'agent', 'rating', 'acs', 'kills', 'deaths', 'assists', 'kast',
                          'adr', 'hs_percent', 'fk', 'fd']
            df = df[cols_order]

            archivo_salida = os.path.join(OUTPUT_DIR, "vlr_stats_players_sides.xlsx")
            df.to_excel(archivo_salida, index=False)

            print("\n" + "=" * 60)
            print(f"✅ ¡Éxito! Archivo guardado: {archivo_salida}")
            print(f"\n📊 RESUMEN:")
            print(f"   • Total de filas: {len(df)}")
            print(f"   • Jugadores únicos: {df['player_name'].nunique()}")
            print(f"   • Mapas: {df['map_id'].nunique()}")
            print(f"   • Filas sin team_id resuelto: {df['team_id'].isna().sum()}")
            print("\n📋 Preview (primeras 10 filas):")
            print(df.head(10).to_string(index=False))
        else:
            print("\n⚠️ No se extrajeron datos.")

    except Exception as e:
        print(f"\n❌ Error durante el scraping: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if 'driver' in locals():
            driver.quit()
            print("\n🔒 Driver cerrado correctamente")