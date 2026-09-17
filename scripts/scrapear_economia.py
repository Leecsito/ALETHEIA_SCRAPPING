import time
import os
import pandas as pd
import re
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from driver_setup import crear_driver
from url_utils import normalizar_url
from equipos_utils import alias_nombres_equipo

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Carpeta de salida relativa al script
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- CARGA DE ENLACES DESDE ARCHIVO .txt  +  CARPETA DE SALIDA DINÁMICA ---
def cargar_enlaces_desde_txt():
    """
    Lee las URLs desde un .txt especifico.
    - Si ALETHEIA_TXT_FILE esta definida (main.py), usa ese archivo.
    - Si no, busca en output_data/; si hay varios pide al usuario elegir.
    Siempre guarda en la subcarpeta del .txt elegido.
    """
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
        urls = [normalizar_url(linea) for linea in f if linea.strip()]
    print(f"   -> {len(urls)} URLs cargadas.")

    nombre_base = os.path.splitext(os.path.basename(ruta_txt))[0]
    if nombre_base.startswith("enlaces_"):
        nombre_base = nombre_base[len("enlaces_"):]
    carpeta_salida = os.path.join(OUTPUT_DIR, nombre_base)
    os.makedirs(carpeta_salida, exist_ok=True)
    print(f"   Carpeta de salida: {carpeta_salida}")
    return urls, carpeta_salida

ENLACES, OUTPUT_DIR = cargar_enlaces_desde_txt()

# Rondas de pistol en Valorant (siempre ronda 1 y 13)
RONDAS_PISTOL = {1, 13}

def k_a_numero(texto):
    """
    Convierte '8.7k' -> 8700, '0.1k' -> 100, '34' -> 34
    """
    texto = texto.strip().lower()
    if 'k' in texto:
        try:
            return int(float(texto.replace('k', '')) * 1000)
        except:
            return 0
    try:
        return int(texto)
    except:
        return 0

def categoria_texto(simbolo):
    """
    Convierte símbolo a texto descriptivo
    '' -> 'eco', '$' -> 'semi_eco', '$$' -> 'semi_buy', '$$$' -> 'full_buy'
    """
    mapa = {
        '':    'eco',
        '$':   'semi_eco',
        '$$':  'semi_buy',
        '$$$': 'full_buy',
    }
    return mapa.get(simbolo.strip(), 'eco')

def obtener_mapas(soup, match_id):
    """Detecta los mapas jugados (excluyendo 'all')"""
    mapas = []
    botones = soup.find_all(['div', 'a'], class_='vm-stats-gamesnav-item')
    for b in botones:
        game_id = b.get('data-game-id')
        if not game_id or game_id == 'all':
            continue
        texto = b.get_text(strip=True)
        map_name = re.sub(r'^\d+', '', texto).strip().lower()
        if map_name:
            mapas.append({
                'game_id':  game_id,
                'map_name': map_name,
                'map_id':   f"{match_id}_{map_name}"
            })
    return mapas


def construir_siglas_reales(soup, global_team_a, global_team_b):
    """Lee las siglas reales que VLR.gg asigna a cada equipo en este partido
    (ej. 'krx' -> 'A', 'vit' -> 'B') desde la primera columna del bloque
    vlr-rounds del DOM de la pestaña overview. Mismo patrón que
    construir_siglas_reales() en scrapear_vlr_corregido.py.

    Resuelve siglas no derivables del nombre con heurísticas de texto
    (ej. 'KRX' para KIWOOM DRX, 'VIT' para Team Vitality), que antes
    dejaban team_id vacío al no poder resolverse desde el veto.

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
            alias_a = alias_nombres_equipo(global_team_a)
            alias_b = alias_nombres_equipo(global_team_b)
            for nombre, tag in zip(nombres[:2], tags[:2]):
                if nombre.lower() in alias_a:
                    mapa[tag.lower()] = 'A'
                elif nombre.lower() in alias_b:
                    mapa[tag.lower()] = 'B'
            if mapa:
                return mapa
    return {}


def obtener_equipos_header(soup):
    """Extrae nombre completo + team_id de los dos equipos desde el header
    de la página (presente en cualquier pestaña, incluida economía)."""
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

    return global_team_a, global_team_b, team_a_id, team_b_id


def construir_tag_map(soup_overview, global_team_a, global_team_b, team_a_id, team_b_id):
    """Resuelve las siglas reales (ej. 'KRX', 'VIT') que usa la pestaña de
    economía, leyéndolas del DOM de la pestaña overview (bloque vlr-rounds),
    que sí está disponible vía requests. Devuelve
    {sigla_lower: (team_id, team_name)} o {} si no se pueden leer."""
    siglas = construir_siglas_reales(soup_overview, global_team_a, global_team_b)
    tag_map = {}
    for tag, lado in siglas.items():
        if lado == 'A':
            tag_map[tag] = (team_a_id, global_team_a)
        else:
            tag_map[tag] = (team_b_id, global_team_b)
    return tag_map

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


def obtener_economia(driver, url):
    """
    Extrae datos de economía por mapa. Genera dos tablas:
      1. Resumen por equipo
      2. Economía por ronda
    """
    print(f"🌐 Procesando economía: {url}")

    match_id = "Unknown"
    m = re.search(r'vlr\.gg/(\d+)', url)
    if m:
        match_id = m.group(1)

    base_url = url.split('?')[0].rstrip('/')
    economy_url = f"{base_url}/?tab=economy"

    print(f"  🔗 Navegando a: {economy_url}")
    try:
        driver.get(economy_url)
    except Exception as e:
        print(f"❌ Error cargando URL: {e}")
        return [], []
    # Best-effort: esperar a que la pestaña economía renderice sus tablas.
    esperar_disponible(driver, EC.presence_of_element_located(
        (By.CSS_SELECTOR, "div.vm-stats-game table.mod-econ")))

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    mapas = obtener_mapas(soup, match_id)
    print(f"  🗺️  Mapas: {[m['map_name'] for m in mapas]}")

    global_team_a, global_team_b, team_a_id, team_b_id = obtener_equipos_header(soup)

    # Las siglas de la pestaña economy no siempre se derivan del nombre del
    # equipo (ej. 'KRX' para KIWOOM DRX). Se leen del DOM de la pestaña
    # overview (bloque vlr-rounds), disponible vía requests.
    tag_map = {}
    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup_overview = BeautifulSoup(resp.text, 'html.parser')
            tag_map = construir_tag_map(soup_overview, global_team_a,
                                        global_team_b, team_a_id, team_b_id)
    except Exception as e:
        print(f"  ⚠️  Error obteniendo overview para siglas: {e}")
    if len(tag_map) < 2:
        print(f"  ⚠️  No se pudieron resolver las siglas del partido "
              f"(tags vistos: {list(tag_map.keys())}); team_id quedará vacío")

    resumen_rows = []
    rondas_rows  = []

    for mapa in mapas:
        game_id  = mapa['game_id']
        map_id   = mapa['map_id']
        map_name = mapa['map_name']
        print(f"\n  📍 Procesando: {map_name}")

        # Clic en el mapa
        try:
            btn = driver.find_element(By.CSS_SELECTOR,
                f".vm-stats-gamesnav-item[data-game-id='{game_id}']")
            driver.execute_script("arguments[0].click();", btn)
        except Exception as e:
            print(f"    ⚠️ Error clic mapa: {e}")
            continue
        # Best-effort: el contenedor del mapa ya está en el DOM (show/hide por JS).
        esperar_disponible(driver, EC.visibility_of_element_located(
            (By.CSS_SELECTOR, f"div.vm-stats-game[data-game-id='{game_id}']")))

        soup      = BeautifulSoup(driver.page_source, 'html.parser')
        contenedor = soup.find('div', class_='vm-stats-game', attrs={'data-game-id': game_id})
        if not contenedor:
            print(f"    ⚠️ No se encontró contenedor")
            continue

        tablas = contenedor.find_all('table', class_='mod-econ')
        if not tablas:
            print(f"    ⚠️ No se encontraron tablas")
            continue

        # ── TABLA 1: Resumen de economía ─────────────────────────────────────
        # Estructura HTML: Pistol Won | Eco (won) | $ (won) | $$ (won) | $$$ (won)
        # 
        # Pistol Won: solo un número
        # Eco (won): "X (Y)" donde X = rondas eco jugadas, Y = ganadas
        # IMPORTANTE: VLR cuenta la ronda pistol dentro del eco, lo cual es incorrecto.
        #             La corregimos: eco_played = X - pistol_won, eco_won = Y - pistol_won
        #             (si ganaron la pistol, la restan también del eco_won)
        tabla_resumen = tablas[0]
        filas_res = tabla_resumen.find_all('tr')[1:]  # Saltar header

        equipos_orden = []  # Para saber el orden top/bottom en la tabla de rondas

        for fila in filas_res:
            celdas = fila.find_all('td')
            if len(celdas) < 6:
                continue

            team_div = celdas[0].find('div', class_='team')
            if not team_div:
                continue
            equipo = team_div.get_text(strip=True)
            equipos_orden.append(equipo)
            team_id_val, _ = tag_map.get(equipo.lower(), (None, None))

            def get_sq_text(celda):
                sq = celda.find('div', class_='stats-sq')
                return sq.get_text(strip=True) if sq else ""

            # Pistol Won
            pistol_won = int(re.sub(r'[^\d]', '', get_sq_text(celdas[1])) or 0)

            # Eco, $, $$, $$$ → "X (Y)" 
            def parse_jugadas_ganadas(celda):
                texto = get_sq_text(celda)
                nums = re.findall(r'\d+', texto)
                jugadas = int(nums[0]) if len(nums) >= 1 else 0
                ganadas  = int(nums[1]) if len(nums) >= 2 else 0
                return jugadas, ganadas

            eco_j,      eco_g      = parse_jugadas_ganadas(celdas[2])
            semi_eco_j, semi_eco_g = parse_jugadas_ganadas(celdas[3])
            semi_buy_j, semi_buy_g = parse_jugadas_ganadas(celdas[4])
            full_buy_j, full_buy_g = parse_jugadas_ganadas(celdas[5])

            # Corrección: VLR incluye la ronda pistol dentro de eco.
            # La restamos para que eco solo cuente rondas económicas reales.
            # Lógica: de las 2 pistols totales del mapa, cada equipo jugó 1 eco (la pistol).
            # Si la ganó, también suma 1 al eco_won → restamos eso.
            pistol_en_eco_won = pistol_won  # si ganó la pistol, la restamos del eco_won
            eco_real_j = eco_j - 1          # siempre hay 1 pistol contada como eco
            eco_real_g = eco_g - pistol_en_eco_won

            # Asegurar que no quede negativo
            eco_real_j = max(0, eco_real_j)
            eco_real_g = max(0, eco_real_g)

            resumen_rows.append({
                'match_id':        match_id,
                'map_id':          map_id,
                'team':            equipo,
                'team_id':         team_id_val,
                'pistol_won':      pistol_won,
                # Formato "jugadas(ganadas)" como en VLR pero sin las pistols
                'eco':      f"{eco_real_j}({eco_real_g})",
                'semi_eco': f"{semi_eco_j}({semi_eco_g})",
                'semi_buy': f"{semi_buy_j}({semi_buy_g})",
                'full_buy': f"{full_buy_j}({full_buy_g})",
            })

        # ── TABLA 2: Economía por ronda ───────────────────────────────────────
        # Estructura por columna (ronda):
        #   div.round-num         → número de ronda
        #   div.bank [0]          → bank del equipo TOP antes de comprar
        #   div.rnd-sq [0]        → equipo TOP: title=gasto, texto=categoría
        #   div.rnd-sq [1]        → equipo BOT: title=gasto, texto=categoría
        #   div.bank [1]          → bank del equipo BOT antes de comprar
        #   mod-win en algún sq   → quién ganó
        #
        # Categorías: '' → eco, '$' → semi_eco, '$$' → semi_buy, '$$$' → full_buy
        if len(tablas) < 2:
            print(f"    ⚠️ No hay tabla de rondas")
            continue

        tabla_rondas = tablas[1]

        # Identificar equipos (top y bottom) desde la primera columna
        primera_col = tabla_rondas.find('td')
        teams_divs  = primera_col.find_all('div', class_='team') if primera_col else []
        team_top = teams_divs[0].get_text(strip=True) if len(teams_divs) > 0 else "TeamA"
        team_bot = teams_divs[1].get_text(strip=True) if len(teams_divs) > 1 else "TeamB"
        team_top_id, _ = tag_map.get(team_top.lower(), (None, None))
        team_bot_id, _ = tag_map.get(team_bot.lower(), (None, None))

        columnas = tabla_rondas.find_all('td')[1:]  # Saltar primera col (labels)

        for col in columnas:
            num_div = col.find('div', class_='round-num')
            if not num_div:
                continue

            try:
                num_ronda = int(num_div.get_text(strip=True))
            except:
                continue

            banks   = col.find_all('div', class_='bank')
            rnd_sqs = col.find_all('div', class_='rnd-sq')

            if len(banks) < 2 or len(rnd_sqs) < 2:
                continue

            bank_top = k_a_numero(banks[0].get_text(strip=True))
            bank_bot = k_a_numero(banks[1].get_text(strip=True))

            sq_top = rnd_sqs[0]
            sq_bot = rnd_sqs[1]

            # Gasto: en el atributo title (ya viene en números)
            gasto_top = int(sq_top.get('title', '0').replace(',', '') or 0)
            gasto_bot = int(sq_bot.get('title', '0').replace(',', '') or 0)

            # Categoría en texto descriptivo
            cat_top = categoria_texto(sq_top.get_text(strip=True))
            cat_bot = categoria_texto(sq_bot.get_text(strip=True))

            # Es pistol?
            es_pistol = num_ronda in RONDAS_PISTOL

            # Ganador
            if 'mod-win' in sq_top.get('class', []):
                ganador = team_top
            elif 'mod-win' in sq_bot.get('class', []):
                ganador = team_bot
            else:
                ganador = ""

            rondas_rows.append({
                'match_id':    match_id,
                'map_id':      map_id,
                'round':       num_ronda,
                'is_pistol':   1 if es_pistol else 0,
                'team_top':    team_top,
                'team_top_id': team_top_id,
                'bank_top':    bank_top,
                'spend_top':   gasto_top,
                'category_top': cat_top,
                'team_bot':    team_bot,
                'team_bot_id': team_bot_id,
                'bank_bot':    bank_bot,
                'spend_bot':   gasto_bot,
                'category_bot': cat_bot,
                'winner':      ganador,
            })

    return resumen_rows, rondas_rows


# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Iniciando extracción de economía...")
    print("=" * 60)

    try:
        driver = crear_driver(headless=True)
    except Exception as e:
        print(f"❌ Error inicializando driver: {e}")
        exit()

    todos_resumen = []
    todas_rondas  = []

    try:
        for i, link in enumerate(ENLACES):
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(ENLACES)}] Procesando partido...")
            resumen, rondas = obtener_economia(driver, link)
            todos_resumen.extend(resumen)
            todas_rondas.extend(rondas)

        print("\n" + "=" * 60)
        print("💾 Guardando archivos Excel...")

        if todos_resumen:
            df_res = pd.DataFrame(todos_resumen)
            ruta_resumen = os.path.join(OUTPUT_DIR, "vlr_economia_resumen.xlsx")
            df_res.to_excel(ruta_resumen, index=False)
            print(f"\n✅ {ruta_resumen} — {len(df_res)} filas")
            print(df_res.to_string(index=False))

        if todas_rondas:
            df_ron = pd.DataFrame(todas_rondas)
            ruta_rondas = os.path.join(OUTPUT_DIR, "vlr_economia_rondas.xlsx")
            df_ron.to_excel(ruta_rondas, index=False)
            print(f"\n✅ {ruta_rondas} — {len(df_ron)} filas")
            print(df_ron.head(20).to_string(index=False))

        if not todos_resumen and not todas_rondas:
            print("\n⚠️ No se extrajeron datos.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'driver' in locals():
            driver.quit()
            print("\n🔒 Driver cerrado correctamente")