"""
ALETHEIA - scrapear_stats_pro.py  (CORREGIDO)
=======================================================================
PROBLEMAS QUE CORRIGE vs la versión anterior:
  1. map_id incorrecto → "598923_abysspick-"  ahora genera "598923_abyss"
  2. Stats todo en cero → se intentaba leer mod-t/mod-ct que están vacíos.
     Ahora lee mod-both (ALL) que siempre tiene valores.
  3. Divide las stats en Attack y Defense proporcionalmente usando
     las rondas reales ganadas de vlr_mapas.xlsx (score_a, score_b).

SALIDA: vlr_stats_players_sides.xlsx
  Mismas columnas que siempre:
  match_id | map_id | player_name | team_name | side | agent |
  rating | acs | kills | deaths | assists | kast | adr | hs_percent | fk | fd

  Dos filas por jugador por mapa: una Attack, una Defense.

LÓGICA DEL SPLIT:
  vlr_mapas.xlsx tiene score_a="7/6" y score_b="6/1"
  → score_a = rondas ganadas por team_top en ATK / en DEF
  → score_b = rondas ganadas por team_bot en ATK / en DEF

  Rondas JUGADAS por team_top:
    atk_played = sa_atk + sb_def   (sus victorias ATK + victorias DEF del rival)
    def_played = sa_def + sb_atk   (sus victorias DEF + victorias ATK del rival)

  Stats como kills/deaths/assists/fk/fd → se dividen por proporción de rondas.
  Stats promedio como rating/acs/adr/kast/hs% → se conservan igual en ambos lados
  (son promedios del partido completo, no se pueden descomponer sin los datos crudos).
=======================================================================
"""

import time
import os
import re
import glob
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── CARGA DE URLS ────────────────────────────────────────────────────────────
def cargar_enlaces_desde_txt():
    txt_forzado = os.environ.get("ALETHEIA_TXT_FILE")
    if txt_forzado:
        # Llamado desde main.py → usar el archivo que main.py indique
        ruta_txt = txt_forzado
        print(f"Cargando enlaces desde: {os.path.basename(ruta_txt)}")
    else:
        archivos = glob.glob(os.path.join(OUTPUT_DIR, "*.txt"))
        if not archivos:
            # Sin archivos disponibles → error claro, sin pedir input
            raise FileNotFoundError(
                "No se encontro ningun archivo .txt en output_data/. "
                "Ejecuta primero scrapear_enlaces_evento.py para el evento de China."
            )
        elif len(archivos) == 1:
            ruta_txt = archivos[0]
            print(f"Cargando enlaces desde: {os.path.basename(ruta_txt)}")
        else:
            # Varios .txt disponibles → seleccionar automáticamente el de China
            candidatos_china = [
                f for f in archivos
                if "china" in os.path.basename(f).lower()
            ]
            if candidatos_china:
                ruta_txt = candidatos_china[0]
                print(f"🇨🇳  Auto-seleccionado archivo China: {os.path.basename(ruta_txt)}")
            else:
                # Ninguno tiene "china" en el nombre → usar el más reciente
                archivos_ordenados = sorted(archivos, key=os.path.getmtime, reverse=True)
                ruta_txt = archivos_ordenados[0]
                print(f"⚠️  No se encontro archivo con 'china' en el nombre.")
                print(f"   Usando el mas reciente: {os.path.basename(ruta_txt)}")

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


# ─── UTILIDADES ───────────────────────────────────────────────────────────────
def limpiar_map_name(raw_text):
    """
    Convierte el texto crudo del div .map a un nombre limpio en minúsculas.
    Ejemplos:
      "AbyssPICK-"    → "abyss"
      "Haven-"        → "haven"
      "Bind"          → "bind"
      "Split PICK 1"  → "split"
    """
    # Tomar solo letras consecutivas al inicio
    match = re.match(r'([A-Za-z]+)', raw_text.strip())
    if match:
        nombre = match.group(1)
        # Quitar "PICK", "DECIDER" si quedaron pegados
        nombre = re.sub(r'(?i)(pick|decider)$', '', nombre)
        return nombre.lower()
    return raw_text.strip().lower()


def safe_float(val):
    try:
        v = str(val).replace('%', '').replace('–', '').strip()
        return float(v) if v else None
    except (ValueError, TypeError):
        return None


def safe_int(val):
    try:
        v = str(val).replace('%', '').replace('–', '').strip()
        return int(float(v)) if v else 0
    except (ValueError, TypeError):
        return 0


def extraer_span(celda, clase):
    """Extrae el valor de un span con la clase dada dentro de una celda."""
    span = celda.find('span', class_=lambda c: c and clase in c)
    if span:
        return span.get_text(strip=True).replace('%', '').strip()
    return ''


# ─── EXTRACCIÓN DE STATS ALL POR PARTIDO ─────────────────────────────────────
def obtener_stats_partido(driver, url):
    """
    Extrae stats ALL (mod-both) por jugador por mapa.
    También guarda team_pos (top/bot) para poder vincular con vlr_mapas.
    Retorna lista de dicts con todos los datos crudos.
    """
    print(f"🌐 Procesando: {url}")
    try:
        driver.get(url)
        time.sleep(3)
    except Exception as e:
        print(f"❌ Error cargando URL: {e}")
        return []

    match_id = "Unknown"
    m = re.search(r'vlr\.gg/(\d+)', url)
    if m:
        match_id = m.group(1)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    datos = []
    contenedores = soup.find_all('div', class_='vm-stats-game')

    for contenedor in contenedores:
        game_id = contenedor.get('data-game-id')
        if not game_id or game_id == 'all':
            continue

        # --- Nombre del mapa (CORREGIDO) ---
        map_div = contenedor.find('div', class_='map')
        if not map_div:
            continue

        raw_map = map_div.get_text(" ", strip=True)
        map_name = limpiar_map_name(raw_map)
        map_id = f"{match_id}_{map_name}"

        print(f"  📍 Mapa: {map_name} → map_id: {map_id}")

        # Equipos en posición visual (top / bot) para el split
        team_names = contenedor.find_all('div', class_='team-name')
        team_top = team_names[0].get_text(strip=True) if len(team_names) > 0 else None
        team_bot = team_names[1].get_text(strip=True) if len(team_names) > 1 else None

        # Tablas: primera = team_top, segunda = team_bot
        tablas = contenedor.find_all('table', class_='wf-table-inset')

        for idx_tabla, tabla in enumerate(tablas):
            pos = 'top' if idx_tabla == 0 else 'bot'

            for fila in tabla.find_all('tr'):
                celda_jugador = fila.find('td', class_='mod-player')
                if not celda_jugador:
                    continue

                div_nombre = celda_jugador.find('div', class_='text-of')
                player_name = div_nombre.get_text(strip=True) if div_nombre else "Unknown"

                div_equipo = celda_jugador.find('div', class_='ge-text-light')
                team_name = div_equipo.get_text(strip=True) if div_equipo else "Unknown"

                # Agente
                agent = "Unknown"
                celda_agente = fila.find('td', class_='mod-agents')
                if celda_agente:
                    img = celda_agente.find('img')
                    if img:
                        agent = img.get('title', img.get('alt', 'Unknown'))

                # Stats — leer mod-both (ALL), que siempre tiene datos
                stats_cells = fila.find_all('td', class_='mod-stat')
                if len(stats_cells) < 11:
                    continue

                # INDICES: 0:Rating 1:ACS 2:K 3:D 4:A 5:+/- 6:KAST 7:ADR 8:HS% 9:FK 10:FD
                def get(idx):
                    return extraer_span(stats_cells[idx], 'mod-both') or \
                           stats_cells[idx].get_text(strip=True).replace('%', '').strip()

                datos.append({
                    'match_id':    match_id,
                    'map_id':      map_id,
                    'map_name':    map_name,
                    'player_name': player_name,
                    'team_name':   team_name,
                    'team_pos':    pos,       # auxiliar para el split
                    'team_top':    team_top,  # auxiliar para el split
                    'team_bot':    team_bot,  # auxiliar para el split
                    'agent':       agent,
                    'rating':      safe_float(get(0)),
                    'acs':         safe_float(get(1)),
                    'kills':       safe_int(get(2)),
                    'deaths':      safe_int(get(3)),
                    'assists':     safe_int(get(4)),
                    'kast':        safe_float(get(6)),
                    'adr':         safe_float(get(7)),
                    'hs_percent':  safe_float(get(8)),
                    'fk':          safe_int(get(9)),
                    'fd':          safe_int(get(10)),
                })

    return datos


# ─── SPLIT ATK/DEF ────────────────────────────────────────────────────────────
def construir_lookup_rondas(df_mapas):
    """
    Construye un dict: round_id → (atk_top, def_top, atk_bot, def_bot)
    Donde atk_top = rondas jugadas por team_top en ATK (no solo ganadas).

    Fórmula:
      atk_played_top = sa_atk + sb_def
      def_played_top = sa_def + sb_atk
    """
    lookup = {}
    for _, row in df_mapas.iterrows():
        rid = str(row['round_id'])
        try:
            sa_atk, sa_def = [int(x) for x in str(row['score_a']).split('/')]
            sb_atk, sb_def = [int(x) for x in str(row['score_b']).split('/')]
            atk_top = sa_atk + sb_def
            def_top = sa_def + sb_atk
            atk_bot = sb_atk + sa_def
            def_bot = sb_def + sa_atk
            lookup[rid] = (atk_top, def_top, atk_bot, def_bot)
        except Exception:
            pass
    return lookup


def split_proporcional(total, atk_r, def_r):
    """Divide un valor total en ATK y DEF por proporción de rondas jugadas."""
    total_r = atk_r + def_r
    if total_r == 0:
        return 0, 0
    atk_val = round(total * atk_r / total_r)
    def_val = total - atk_val
    return atk_val, def_val


def generar_filas_split(datos_all, lookup_rondas):
    """
    Para cada jugador/mapa, genera DOS filas: Attack y Defense.
    Stats contables (kills/deaths/assists/fk/fd) → se dividen proporcionalmente.
    Stats promedio (rating/acs/adr/kast/hs%) → se mantienen igual en ambos lados
    porque son promedios del partido completo y no se pueden descomponer sin datos crudos.
    """
    filas_split = []

    for row in datos_all:
        map_id = row['map_id']
        pos = row['team_pos']  # 'top' o 'bot'
        scores = lookup_rondas.get(map_id)

        if scores:
            atk_top, def_top, atk_bot, def_bot = scores
            if pos == 'top':
                atk_r, def_r = atk_top, def_top
            else:
                atk_r, def_r = atk_bot, def_bot
        else:
            # Sin datos de vlr_mapas → 50/50
            atk_r = def_r = 1

        k_atk, k_def     = split_proporcional(row['kills'],   atk_r, def_r)
        d_atk, d_def     = split_proporcional(row['deaths'],  atk_r, def_r)
        a_atk, a_def     = split_proporcional(row['assists'], atk_r, def_r)
        fk_atk, fk_def   = split_proporcional(row['fk'],      atk_r, def_r)
        fd_atk, fd_def   = split_proporcional(row['fd'],      atk_r, def_r)

        # Fila Attack
        filas_split.append({
            'match_id':   row['match_id'],
            'map_id':     row['map_id'],
            'player_name': row['player_name'],
            'team_name':  row['team_name'],
            'side':       'Attack',
            'agent':      row['agent'],
            'rating':     row['rating'],
            'acs':        row['acs'],
            'kills':      k_atk,
            'deaths':     d_atk,
            'assists':    a_atk,
            'kast':       row['kast'],
            'adr':        row['adr'],
            'hs_percent': row['hs_percent'],
            'fk':         fk_atk,
            'fd':         fd_atk,
        })

        # Fila Defense
        filas_split.append({
            'match_id':   row['match_id'],
            'map_id':     row['map_id'],
            'player_name': row['player_name'],
            'team_name':  row['team_name'],
            'side':       'Defense',
            'agent':      row['agent'],
            'rating':     row['rating'],
            'acs':        row['acs'],
            'kills':      k_def,
            'deaths':     d_def,
            'assists':    a_def,
            'kast':       row['kast'],
            'adr':        row['adr'],
            'hs_percent': row['hs_percent'],
            'fk':         fk_def,
            'fd':         fd_def,
        })

    return filas_split


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Iniciando extracción de estadísticas por lado...")
    print("=" * 60)

    # ── Cargar vlr_mapas para el split ───────────────────────────────────────
    lookup_rondas = {}
    ruta_mapas = os.path.join(OUTPUT_DIR, "vlr_mapas.xlsx")
    if os.path.exists(ruta_mapas):
        df_mapas = pd.read_excel(ruta_mapas)
        lookup_rondas = construir_lookup_rondas(df_mapas)
        print(f"  ✅ vlr_mapas.xlsx cargado → {len(lookup_rondas)} mapas con datos de rondas")
    else:
        print("  ⚠️ vlr_mapas.xlsx no encontrado. Se usará split 50/50.")
        print("     Ejecuta scrapear_vlr_corregido.py primero para mayor precisión.")

    # ── Configurar Selenium ───────────────────────────────────────────────────
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    except Exception as e:
        print(f"❌ Error inicializando driver: {e}")
        exit()

    todos_los_datos_all = []

    try:
        for i, link in enumerate(ENLACES):
            print(f"\n[{i+1}/{len(ENLACES)}] Procesando partido...")
            datos = obtener_stats_partido(driver, link)
            if datos:
                todos_los_datos_all.extend(datos)
                print(f"  ✅ {len(datos)} filas ALL extraídas ({len(datos)//2} jugadores x mapas)")
            else:
                print(f"  ⚠️ No se extrajeron datos")

        if not todos_los_datos_all:
            print("\n⚠️ No se extrajeron datos.")
        else:
            # ── Aplicar split ATK/DEF ─────────────────────────────────────────
            print(f"\n{'='*60}")
            print("📐 Aplicando split ATK/DEF proporcional...")
            filas_finales = generar_filas_split(todos_los_datos_all, lookup_rondas)

            df = pd.DataFrame(filas_finales)

            # Columnas exactas en el orden correcto
            cols = ['match_id', 'map_id', 'player_name', 'team_name', 'side', 'agent',
                    'rating', 'acs', 'kills', 'deaths', 'assists', 'kast', 'adr',
                    'hs_percent', 'fk', 'fd']
            df = df[cols]

            archivo_salida = os.path.join(OUTPUT_DIR, "vlr_stats_players_sides.xlsx")
            df.to_excel(archivo_salida, index=False)

            print(f"\n{'='*60}")
            print(f"✅ Archivo guardado: {archivo_salida}")
            print(f"\n📊 RESUMEN:")
            print(f"   • Total de filas:       {len(df)}")
            print(f"   • Jugadores únicos:     {df['player_name'].nunique()}")
            print(f"   • Mapas únicos:         {df['map_id'].nunique()}")
            print(f"   • Filas Attack:         {(df['side']=='Attack').sum()}")
            print(f"   • Filas Defense:        {(df['side']=='Defense').sum()}")

            print("\n📋 Preview (primeras 10 filas):")
            print(df.head(10).to_string(index=False))

    except Exception as e:
        print(f"\n❌ Error durante el scraping: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if 'driver' in locals():
            driver.quit()
            print("\n🔒 Driver cerrado correctamente")

    print("\n🏁 Script finalizado.")