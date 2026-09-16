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


def esperar_performance_listo(driver, timeout=15):
    """Espera a que la pestaña performance tenga la barra de selección de mapas."""
    return esperar_disponible(
        driver,
        EC.presence_of_element_located((By.CSS_SELECTOR, "a.vm-stats-gamesnav-item")),
        timeout,
    )

def obtener_mapas_jugados(driver, match_id):
    """
    Detecta qué mapas se jugaron en el partido
    """
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # [CORRECCIÓN APLICADA]: En VLR.gg los botones son etiquetas <a>, no <div>
    map_buttons = soup.find_all('a', class_='vm-stats-gamesnav-item')
    
    mapas = []
    for button in map_buttons:
        game_id = button.get('data-game-id')
        is_disabled = button.get('data-disabled') # Ignorar mapas cancelados (ej: en un 3-0)
        
        if game_id and game_id != 'all' and is_disabled != '1':
            # Extraer nombre del mapa
            map_text = button.get_text(strip=True)
            # El texto puede ser algo como "1Bind" o "2Abyss"
            map_name = re.sub(r'^\d+', '', map_text).strip()  # Quitar número inicial
            if map_name:
                mapas.append({
                    'game_id': game_id,
                    'map_name': map_name.lower(),
                    'map_id': f"{match_id}_{map_name.lower()}"
                })
    
    return mapas

def obtener_enfrentamientos_por_mapa(driver, url, cargar_pagina=True):
    """
    Extrae las matrices de enfrentamientos por cada mapa jugado.
    Con cargar_pagina=False se asume que el driver ya está en la pestaña
    performance (evita recargarla dos veces por partido).
    """
    print(f"🌐 Procesando enfrentamientos: {url}")
    
    # Obtener Match ID
    match_id = "Unknown"
    match_search = re.search(r'vlr\.gg/(\d+)', url)
    if match_search:
        match_id = match_search.group(1)
    
    # Construir URL de Performance
    if '?' in url:
        performance_url = url.split('?')[0] + '?tab=performance'
    else:
        performance_url = url.rstrip('/') + '/?tab=performance'
    
    if cargar_pagina:
        print(f"  🔗 Navegando a: {performance_url}")
        try:
            driver.get(performance_url)
        except Exception as e:
            print(f"❌ Error cargando URL: {e}")
            return []
        esperar_performance_listo(driver)

    # Detectar mapas jugados
    mapas = obtener_mapas_jugados(driver, match_id)
    print(f"  🗺️ Mapas encontrados: {[m['map_name'] for m in mapas]}")
    
    if not mapas:
        print("  ⚠️ No se encontraron mapas")
        return []

    todos_enfrentamientos = []
    
    # Tipos de kill
    tipos_kill = {
        'all': 'normal',
        'first': 'fkfd',
        'op': 'op'
    }
    
    # Iterar sobre cada mapa
    for mapa_info in mapas:
        map_id = mapa_info['map_id']
        map_name = mapa_info['map_name']
        game_id = mapa_info['game_id']
        
        print(f"\n  📍 Procesando mapa: {map_name} (ID: {game_id})")
        
        # Hacer clic en el botón del mapa
        # [CORRECCIÓN APLICADA]: Selector CSS actualizado a 'a.vm-stats...'
        try:
            map_button = driver.find_element(
                By.CSS_SELECTOR,
                f"a.vm-stats-gamesnav-item[data-game-id='{game_id}']"
            )
            driver.execute_script("arguments[0].click();", map_button)
        except Exception as e:
            print(f"    ⚠️ Error haciendo clic en mapa: {e}")
            continue
        # Best-effort: el contenedor ya está en el DOM (VLR alterna show/hide por JS).
        esperar_disponible(driver, EC.visibility_of_element_located(
            (By.CSS_SELECTOR, f"div.vm-stats-game[data-game-id='{game_id}']")))
        
        # Iterar sobre cada tipo de kill
        for tipo_nombre, data_matrix in tipos_kill.items():
            try:
                print(f"    📊 Procesando: {tipo_nombre}")
                
                # Hacer clic en el filtro de tipo de kill
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "js-matrix-filter")))
                    boton = driver.find_element(
                        By.CSS_SELECTOR,
                        f"div.js-matrix-filter div[data-matrix='{data_matrix}']"
                    )
                    driver.execute_script("arguments[0].click();", boton)
                except Exception as e:
                    print(f"      ⚠️ Error con botón {tipo_nombre}: {e}")
                    continue
                # Best-effort: la matriz ya está en el DOM; el filtro solo la muestra/oculta.
                esperar_disponible(
                    driver,
                    EC.visibility_of_element_located((By.CSS_SELECTOR,
                        f"div.vm-stats-game[data-game-id='{game_id}'] table.mod-matrix.mod-{data_matrix}")),
                    timeout=5)
                
                # Obtener HTML actualizado
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Buscar el contenedor específico del mapa que está activo
                contenedor_mapa = soup.find('div', class_='vm-stats-game', attrs={'data-game-id': game_id})
                if not contenedor_mapa:
                    print(f"      ⚠️ No se encontró contenedor para game_id={game_id}")
                    continue
                
                # Buscar la tabla de matriz DENTRO del contenedor específico
                # La tabla tiene clase según el tipo: mod-normal, mod-fkfd, mod-op
                tabla = contenedor_mapa.find('table', class_=lambda c: c and 'mod-matrix' in c and f'mod-{data_matrix}' in c)
                if not tabla:
                    print(f"      ⚠️ No se encontró tabla mod-{data_matrix} en el contenedor del mapa")
                    continue
                
                filas = tabla.find_all('tr')
                if len(filas) < 2:
                    continue
                
                # Extraer jugadores rivales (columnas)
                jugadores_rivales = []
                primera_fila = filas[0]
                for celda in primera_fila.find_all('td')[1:]:
                    nombre_div = celda.find('div', class_='team')
                    if nombre_div:
                        # Encontrar el div hijo que contiene el nombre
                        div_contenedor = nombre_div.find('div')
                        if div_contenedor:
                            # Extraer solo el texto directo (sin el team-tag)
                            # Eliminar el div del equipo si existe
                            team_tag = div_contenedor.find('div', class_='team-tag')
                            if team_tag:
                                team_tag.decompose()  # Eliminar el div del equipo
                            jugador = div_contenedor.get_text(strip=True)
                            if jugador:
                                jugadores_rivales.append(jugador)
                
                # Procesar filas de jugadores
                for fila in filas[1:]:
                    celdas = fila.find_all('td')
                    if len(celdas) < 2:
                        continue
                    
                    # Extraer jugador sujeto
                    primera_celda = celdas[0]
                    team_div = primera_celda.find('div', class_='team')
                    if not team_div:
                        continue
                    
                    # Encontrar el div hijo que contiene el nombre
                    div_contenedor = team_div.find('div')
                    if not div_contenedor:
                        continue
                    
                    # Eliminar el div del equipo si existe
                    team_tag = div_contenedor.find('div', class_='team-tag')
                    if team_tag:
                        team_tag.decompose()
                    
                    player_a = div_contenedor.get_text(strip=True)
                    if not player_a:
                        continue
                    
                    # Procesar cada enfrentamiento
                    for idx, celda in enumerate(celdas[1:]):
                        if idx >= len(jugadores_rivales):
                            break
                        
                        player_b = jugadores_rivales[idx]
                        
                        # Extraer kills
                        stats_divs = celda.find_all('div', class_='stats-sq')
                        if len(stats_divs) < 2:
                            continue
                        
                        kills_realizadas = stats_divs[0].get_text(strip=True)
                        kills_recibidas = stats_divs[1].get_text(strip=True)
                        
                        # Limpiar valores
                        kills_realizadas = re.sub(r'[^\d]', '', kills_realizadas) if kills_realizadas else "0"
                        kills_recibidas = re.sub(r'[^\d]', '', kills_recibidas) if kills_recibidas else "0"
                        
                        # Solo guardar si hay datos
                        if kills_realizadas != "0" or kills_recibidas != "0":
                            kills_formato = f"{kills_realizadas}/{kills_recibidas}"
                            
                            todos_enfrentamientos.append({
                                'match_id': match_id,
                                'map_id': map_id,
                                'tipo_kill': tipo_nombre,
                                'player_a': player_a,
                                'player_b': player_b,
                                'kills': kills_formato
                            })
            
            except Exception as e:
                print(f"      ⚠️ Error en {tipo_nombre}: {e}")
                continue
    
    return todos_enfrentamientos

def obtener_multikills_por_mapa(driver, url, cargar_pagina=True):
    """
    Extrae multikills y clutches por cada mapa jugado.
    Con cargar_pagina=False se asume que el driver ya está en la pestaña
    performance (evita recargarla dos veces por partido).
    """
    print(f"\n🎯 Procesando multikills y clutches: {url}")
    
    # Obtener Match ID
    match_id = "Unknown"
    match_search = re.search(r'vlr\.gg/(\d+)', url)
    if match_search:
        match_id = match_search.group(1)
    
    # Construir URL de Performance
    if '?' in url:
        performance_url = url.split('?')[0] + '?tab=performance'
    else:
        performance_url = url.rstrip('/') + '/?tab=performance'
    
    if cargar_pagina:
        try:
            driver.get(performance_url)
        except Exception as e:
            print(f"❌ Error cargando URL: {e}")
            return []
        esperar_performance_listo(driver)

    # Detectar mapas
    mapas = obtener_mapas_jugados(driver, match_id)
    
    if not mapas:
        print("  ⚠️ No se encontraron mapas")
        return []

    todos_multikills = []
    
    # Iterar sobre cada mapa
    for mapa_info in mapas:
        map_id = mapa_info['map_id']
        map_name = mapa_info['map_name']
        game_id = mapa_info['game_id']
        
        print(f"  📍 Procesando mapa: {map_name}")
        
        # Hacer clic en el botón del mapa
        # [CORRECCIÓN APLICADA]: Selector CSS actualizado a 'a.vm-stats...'
        try:
            map_button = driver.find_element(
                By.CSS_SELECTOR,
                f"a.vm-stats-gamesnav-item[data-game-id='{game_id}']"
            )
            driver.execute_script("arguments[0].click();", map_button)
        except Exception as e:
            print(f"    ⚠️ Error haciendo clic en mapa: {e}")
            continue
        # Best-effort: el contenedor ya está en el DOM (VLR alterna show/hide por JS).
        esperar_disponible(driver, EC.visibility_of_element_located(
            (By.CSS_SELECTOR, f"div.vm-stats-game[data-game-id='{game_id}']")))
        
        # Obtener HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Buscar el contenedor específico del mapa
        contenedor_mapa = soup.find('div', class_='vm-stats-game', attrs={'data-game-id': game_id})
        if not contenedor_mapa:
            print(f"    ⚠️ No se encontró contenedor para game_id={game_id}")
            continue
        
        # Buscar tabla de stats avanzadas DENTRO del contenedor
        tabla = contenedor_mapa.find('table', class_='mod-adv-stats')
        if not tabla:
            print(f"    ⚠️ No se encontró tabla de stats avanzadas en el contenedor del mapa")
            continue
        
        # Procesar filas
        filas = tabla.find_all('tr')[1:]  # Saltar header
        
        for fila in filas:
            celdas = fila.find_all('td')
            if len(celdas) < 14:
                continue
            
            # Extraer nombre del jugador (sin equipo)
            primera_celda = celdas[0]
            team_div = primera_celda.find('div', class_='team')
            if not team_div:
                continue
            
            # Encontrar el div hijo
            div_contenedor = team_div.find('div')
            if not div_contenedor:
                continue
            
            # Eliminar el div del equipo
            team_tag = div_contenedor.find('div', class_='team-tag')
            if team_tag:
                team_tag.decompose()
            
            player_name = div_contenedor.get_text(strip=True)
            if not player_name:
                continue
            
            # Agente
            agente = "Unknown"
            img_agente = celdas[1].find('img')
            if img_agente and 'src' in img_agente.attrs:
                src = img_agente['src']
                match_agent = re.search(r'/agents/([^.]+)\.png', src)
                if match_agent:
                    agente = match_agent.group(1).capitalize()
            
            # Extraer stats
            def extraer_stat(celda):
                div = celda.find('div', class_='stats-sq')
                if div:
                    # Crear una copia para no modificar el original
                    div_copy = BeautifulSoup(str(div), 'html.parser').find('div')
                    # Eliminar los divs de detalles/popup si existen
                    popup = div_copy.find('div', class_='wf-popable-contents')
                    if popup:
                        popup.decompose()
                    
                    texto = div_copy.get_text(strip=True)
                    return re.sub(r'[^\d]', '', texto) if texto else "0"
                return "0"
            
            k2 = extraer_stat(celdas[2])
            k3 = extraer_stat(celdas[3])
            k4 = extraer_stat(celdas[4])
            k5 = extraer_stat(celdas[5])
            
            v1 = extraer_stat(celdas[6])
            v2 = extraer_stat(celdas[7])
            v3 = extraer_stat(celdas[8])
            v4 = extraer_stat(celdas[9])
            v5 = extraer_stat(celdas[10])
            
            econ = extraer_stat(celdas[11])
            pl = extraer_stat(celdas[12])
            de = extraer_stat(celdas[13])
            
            todos_multikills.append({
                'match_id': match_id,
                'map_id': map_id,
                'player_name': player_name,
                'agent': agente,
                'k2': k2,
                'k3': k3,
                'k4': k4,
                'k5': k5,
                'v1': v1,
                'v2': v2,
                'v3': v3,
                'v4': v4,
                'v5': v5,
                'econ': econ,
                'pl': pl,
                'de': de
            })
    
    return todos_multikills

# --- MAIN ---
if __name__ == "__main__":
    print("🚀 Iniciando extracción de datos por mapa...")
    print("="*60)
    
    try:
        driver = crear_driver(headless=True)
    except Exception as e:
        print(f"❌ Error inicializando driver: {e}")
        exit()

    todos_enfrentamientos = []
    todos_multikills = []

    try:
        for i, link in enumerate(ENLACES):
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(ENLACES)}] Procesando partido...")

            # Cargar la pestaña performance UNA sola vez por partido y reutilizarla
            # en los dos pases (enfrentamientos y multikills). Reduce a la mitad
            # las peticiones a VLR.gg.
            if '?' in link:
                performance_url = link.split('?')[0] + '?tab=performance'
            else:
                performance_url = link.rstrip('/') + '/?tab=performance'
            try:
                driver.get(performance_url)
            except Exception as e:
                print(f"  ❌ Error cargando {performance_url}: {e}")
                continue
            esperar_performance_listo(driver)

            # Extraer enfrentamientos
            enfrentamientos = obtener_enfrentamientos_por_mapa(driver, link, cargar_pagina=False)
            if enfrentamientos:
                todos_enfrentamientos.extend(enfrentamientos)
                print(f"\n  ✅ {len(enfrentamientos)} enfrentamientos extraídos")
            
            # Extraer multikills
            multikills = obtener_multikills_por_mapa(driver, link, cargar_pagina=False)
            if multikills:
                todos_multikills.extend(multikills)
                print(f"  ✅ {len(multikills)} filas de multikills extraídas")

        print("\n" + "="*60)
        print("💾 Guardando archivos Excel...")
        
        # Guardar enfrentamientos
        if todos_enfrentamientos:
            df_enfrentamientos = pd.DataFrame(todos_enfrentamientos)
            ruta_enfrentamientos = os.path.join(OUTPUT_DIR, "vlr_enfrentamientos.xlsx")
            df_enfrentamientos.to_excel(ruta_enfrentamientos, index=False)
            print(f"\n✅ Archivo guardado: {ruta_enfrentamientos}")
            print(f"   • Total de enfrentamientos: {len(df_enfrentamientos)}")
            print(f"   • Mapas únicos: {df_enfrentamientos['map_id'].nunique()}")
            print(f"   • Por tipo: {df_enfrentamientos['tipo_kill'].value_counts().to_dict()}")
            print("\n📋 Preview enfrentamientos:")
            print(df_enfrentamientos.head(15).to_string(index=False))
        
        # Guardar multikills
        if todos_multikills:
            df_multikills = pd.DataFrame(todos_multikills)
            ruta_multikills = os.path.join(OUTPUT_DIR, "vlr_multikills_clutches.xlsx")
            df_multikills.to_excel(ruta_multikills, index=False)
            print(f"\n✅ Archivo guardado: {ruta_multikills}")
            print(f"   • Total de filas: {len(df_multikills)}")
            print(f"   • Mapas únicos: {df_multikills['map_id'].nunique()}")
            print("\n📋 Preview multikills:")
            print(df_multikills.head(10).to_string(index=False))
        
        if not todos_enfrentamientos and not todos_multikills:
            print("\n⚠️ No se extrajeron datos.")
            
    except Exception as e:
        print(f"\n❌ Error durante el scraping: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if 'driver' in locals():
            driver.quit()
            print("\n🔒 Driver cerrado correctamente")