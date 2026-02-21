import time
import os
import pandas as pd
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

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
    botones = soup.find_all('div', class_='vm-stats-gamesnav-item')
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
        time.sleep(4)
    except Exception as e:
        print(f"❌ Error cargando URL: {e}")
        return [], []

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    mapas = obtener_mapas(soup, match_id)
    print(f"  🗺️  Mapas: {[m['map_name'] for m in mapas]}")

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
                f"div.vm-stats-gamesnav-item[data-game-id='{game_id}']")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
        except Exception as e:
            print(f"    ⚠️ Error clic mapa: {e}")
            continue

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
                'bank_top':    bank_top,
                'spend_top':   gasto_top,
                'category_top': cat_top,
                'team_bot':    team_bot,
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

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
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