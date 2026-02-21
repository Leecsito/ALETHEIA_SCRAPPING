import time
import os
import pandas as pd
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
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

def obtener_datos_partido(driver, url):
    """
    Extrae datos de mapas y rondas de un partido de VLR.gg
    """
    print(f"   🌐 Navegando a: {url}")
    try:
        driver.get(url)
        time.sleep(3) 
        html = driver.page_source
    except Exception as e:
        print(f"   ❌ Error cargando link: {e}")
        return None, None

    soup = BeautifulSoup(html, 'html.parser')
    
    match_id = "Unknown"
    match_search = re.search(r'vlr\.gg/(\d+)', url)
    if match_search: 
        match_id = match_search.group(1)

    # --- 1. LECTURA DEL VETO ---
    veto_text = ""
    note_div = soup.find('div', class_='match-header-note')
    if note_div:
        veto_text = note_div.get_text().lower().strip()
        veto_text = veto_text.replace("\n", " ").replace("\t", " ")
        veto_text = re.sub(r'\s+', ' ', veto_text)

    print(f"   📋 Veto: {veto_text}")

    # --- 2. DETECTAR NOMBRES DE EQUIPOS ---
    teams_header = soup.find_all('div', class_='match-header-link-name')
    if len(teams_header) >= 2:
        global_team_a = teams_header[0].get_text(strip=True)
        global_team_b = teams_header[1].get_text(strip=True)
    else:
        global_team_a, global_team_b = "TeamA", "TeamB"

    print(f"   🎮 Equipos: {global_team_a} vs {global_team_b}")

    # --- 3. DETECTAR ABREVIATURAS EN EL VETO ---

    def generar_abbrev(nombre):
        """
        Genera la abreviatura esperada a partir del nombre real del equipo.
        Ejemplos:
            Cloud9      → c9      (C de Cloud + 9)
            100 Thieves → 100t    (100 + T de Thieves)
            NRG         → nrg     (todo mayúsculas → se conserva completo)
            LOUD        → loud    (todo mayúsculas → se conserva completo)
            Leviatán    → l       (primera letra — pero startswith lo cubre)
        """
        tokens = re.findall(r'\d+|[a-zA-ZÀ-ÿ]+', nombre)
        abbrev = ''
        for token in tokens:
            if token.isdigit():
                abbrev += token          # números completos: 100 → 100
            elif token.isupper():
                abbrev += token          # siglas completas: NRG → NRG
            else:
                abbrev += token[0].upper()  # primera letra: Cloud → C, Thieves → T
        return abbrev.lower()

    veto_words = veto_text.split()
    team_abbrevs = []
    for i, word in enumerate(veto_words):
        if word in ['pick', 'ban'] and i > 0:
            abbrev = veto_words[i-1]
            if abbrev not in team_abbrevs:
                team_abbrevs.append(abbrev)

    team_a_abbrev = None
    team_b_abbrev = None

    for abbrev in team_abbrevs:
        # Criterio 1: startswith  (cubre: loud, nrg, lev, fur, sen, mibr...)
        # Criterio 2: generar_abbrev (cubre: c9→Cloud9, 100t→100 Thieves)
        if global_team_a.lower().startswith(abbrev) or generar_abbrev(global_team_a) == abbrev:
            team_a_abbrev = abbrev
        elif global_team_b.lower().startswith(abbrev) or generar_abbrev(global_team_b) == abbrev:
            team_b_abbrev = abbrev

    print(f"   📝 Abreviaturas: {global_team_a}→{team_a_abbrev}, {global_team_b}→{team_b_abbrev}")

    map_data = []
    round_data = []

    # --- 4. ITERAR SOBRE CADA MAPA ---
    contenedores = soup.find_all('div', class_='vm-stats-game')
    
    for contenedor in contenedores:
        game_id = contenedor.get('data-game-id')
        if not game_id or game_id == 'all': 
            continue

        map_header = contenedor.find('div', class_='map')
        if not map_header: 
            continue
        
        raw_text = map_header.get_text(" ", strip=True)
        map_name = raw_text.split()[0].replace("PICK", "").strip()
        map_lower = map_name.lower()
        
        print(f"   🗺️  Procesando mapa: {map_name}")
        
        # --- ¿QUIÉN ELIGIÓ ESTE MAPA? ---
        picker_team = None
        
        if f"{map_lower} remains" in veto_text:
            picker_team = None
            print(f"      ✓ DECIDER")
        else:
            if team_a_abbrev and f"{team_a_abbrev} pick {map_lower}" in veto_text:
                picker_team = "A"
                print(f"      ✓ {global_team_a} pickeó")
            elif team_b_abbrev and f"{team_b_abbrev} pick {map_lower}" in veto_text:
                picker_team = "B"
                print(f"      ✓ {global_team_b} pickeó")
            elif f"{global_team_a.lower()} pick {map_lower}" in veto_text:
                picker_team = "A"
                print(f"      ✓ {global_team_a} pickeó")
            elif f"{global_team_b.lower()} pick {map_lower}" in veto_text:
                picker_team = "B"
                print(f"      ✓ {global_team_b} pickeó")

        # --- Identificar equipos en posiciones visuales ---
        teams_visual = contenedor.find_all('div', class_='team-name')
        if len(teams_visual) < 2: 
            continue
        team_top_name = teams_visual[0].get_text(strip=True)
        team_bottom_name = teams_visual[1].get_text(strip=True)
        
        dur_div = contenedor.find('div', class_='map-duration')
        duration = dur_div.get_text(strip=True) if dur_div else "00:00"
        
        round_id_val = f"{match_id}_{map_lower}"

        # --- PROCESAR RONDAS ---
        rounds_container = contenedor.find('div', class_='vlr-rounds')
        if not rounds_container: 
            continue

        cols = rounds_container.find_all('div', class_='vlr-rounds-row-col')
        sa_attack, sa_defense, sb_attack, sb_defense = 0, 0, 0, 0
        side_top_start = None  # lado en que team_top empezó el mapa
        side_chosen = None

        # ⚠️ La columna 0 es el header, las rondas empiezan en columna 1
        for idx, col in enumerate(cols):
            if idx == 0:
                continue
                
            num_div = col.find('div', class_='rnd-num')
            if not num_div: 
                continue
            
            try: 
                num = int(num_div.get_text(strip=True))
            except: 
                continue

            squares = col.find_all('div', class_='rnd-sq')
            if len(squares) < 2: 
                continue
            
            sq_top, sq_bottom = squares[0], squares[1]

            # --- DETERMINAR EL LADO EN LA RONDA 1 ---
            if num == 1:
                # Los cuadros solo muestran mod-t o mod-ct cuando ese equipo GANA
                # Necesitamos detectar quién ganó y qué lado tenía
                side_top = None
                side_bottom = None
                
                # Detectar el lado del equipo que ganó la ronda 1
                if "mod-win" in sq_top.get('class', []):
                    # El equipo de arriba ganó
                    if "mod-t" in sq_top.get('class', []):
                        side_top = "attack"
                        side_bottom = "defense"  # El otro equipo estaba en defense
                    elif "mod-ct" in sq_top.get('class', []):
                        side_top = "defense"
                        side_bottom = "attack"  # El otro equipo estaba en attack
                elif "mod-win" in sq_bottom.get('class', []):
                    # El equipo de abajo ganó
                    if "mod-t" in sq_bottom.get('class', []):
                        side_bottom = "attack"
                        side_top = "defense"  # El otro equipo estaba en defense
                    elif "mod-ct" in sq_bottom.get('class', []):
                        side_bottom = "defense"
                        side_top = "attack"  # El otro equipo estaba en attack

                side_top_start = side_top  # guardar siempre, incluyendo decider

                if picker_team is None:
                    side_chosen = "decider"
                    print(f"      → side = decider (team_top empezó en {side_top})")
                
                elif picker_team == "A":
                    # A pickeó → B eligió lado
                    # Guardamos el lado que B empezó jugando (el equipo que NO pickeó)
                    if team_top_name == global_team_b:
                        side_chosen = side_top
                        print(f"      → {global_team_b} eligió {side_top}")
                    elif team_bottom_name == global_team_b:
                        side_chosen = side_bottom
                        print(f"      → {global_team_b} eligió {side_bottom}")

                elif picker_team == "B":
                    # B pickeó → A eligió lado
                    # Guardamos el lado que A empezó jugando (el equipo que NO pickeó)
                    if team_top_name == global_team_a:
                        side_chosen = side_top
                        print(f"      → {global_team_a} eligió {side_top}")
                    elif team_bottom_name == global_team_a:
                        side_chosen = side_bottom
                        print(f"      → {global_team_a} eligió {side_bottom}")

            # --- Determinar ganador de la ronda ---
            winner = ""
            res_type = "elim"
            win_band = ""

            if "mod-win" in sq_top.get('class', []):
                winner = team_top_name
                win_band = "attack" if "mod-t" in sq_top.get('class', []) else "defense"
                img = sq_top.find('img')
                if win_band == "attack": sa_attack += 1
                else: sa_defense += 1
                
            elif "mod-win" in sq_bottom.get('class', []):
                winner = team_bottom_name
                win_band = "attack" if "mod-t" in sq_bottom.get('class', []) else "defense"
                img = sq_bottom.find('img')
                if win_band == "attack": sb_attack += 1
                else: sb_defense += 1
            else:
                continue

            src = img['src'] if img else ""
            if 'time' in src: 
                res_type = 'time'
            elif 'defuse' in src: 
                res_type = 'defuse'
            elif 'deton' in src or 'boom' in src: 
                res_type = 'detonation'

            round_data.append({
                'round_id': round_id_val, 
                'num': num, 
                'win': winner,
                'result': res_type, 
                'band': win_band
            })

        # --- LÓGICA PARA AHORRAR COLUMNAS ---
        # Si A pickea: pick_a=MAPA, pick_b=LADO
        # Si B pickea: pick_a=LADO, pick_b=MAPA
        if picker_team is None:
            pick_a_result = "decider"
            # Para deciders: guardamos el lado en que cada equipo empezó
            pick_b_result = "decider"
            # side_top_start ya tiene el lado de team_top
        elif picker_team == "A":
            pick_a_result = map_name
            pick_b_result = side_chosen
        elif picker_team == "B":
            pick_a_result = side_chosen.capitalize() if side_chosen else "Unknown"
            pick_b_result = map_name

        map_data.append({
            'match_id': match_id,
            'pick_a': pick_a_result,
            'pick_b': pick_b_result,
            'side_top_start': side_top_start,  # lado en que team_top (score_a) empezó
            'score_a': f"{sa_attack}/{sa_defense}",
            'score_b': f"{sb_attack}/{sb_defense}",
            'time': duration,
            'round_id': round_id_val
        })
        
    return map_data, round_data

# --- EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    print("🚀 Iniciando web scraping de VLR.gg...")
    print("="*60)
    
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--headless")
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

    todos_mapas = []
    todas_rondas = []

    try:
        for i, link in enumerate(ENLACES):
            print(f"\n[{i+1}/{len(ENLACES)}] Procesando partido...")
            mapas, rondas = obtener_datos_partido(driver, link)
            
            if mapas: 
                todos_mapas.extend(mapas)
            if rondas: 
                todas_rondas.extend(rondas)
        
        print("\n" + "="*60)
        print("✅ Guardando archivos Excel...")
        
        df_mapas = pd.DataFrame(todos_mapas)
        df_rondas = pd.DataFrame(todas_rondas)
        
        ruta_mapas = os.path.join(OUTPUT_DIR, "vlr_mapas.xlsx")
        ruta_rondas = os.path.join(OUTPUT_DIR, "vlr_rondas.xlsx")
        df_mapas.to_excel(ruta_mapas, index=False)
        df_rondas.to_excel(ruta_rondas, index=False)
        
        print("📂 Archivos guardados:")
        print(f"   • {ruta_mapas}")
        print(f"   • {ruta_rondas}")
        print("\n🎉 ¡Scraping completado exitosamente!")
        
        print("\n📊 RESUMEN:")
        print(f"   • Total de mapas: {len(df_mapas)}")
        print(f"   • Total de rondas: {len(df_rondas)}")
        print("\n" + df_mapas.to_string(index=False))

    except Exception as e:
        print(f"\n❌ Error durante el scraping: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if 'driver' in locals(): 
            driver.quit()
            print("\n🔒 Driver cerrado correctamente")