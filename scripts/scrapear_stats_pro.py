import time
import os
import pandas as pd
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
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

def obtener_stats_detalladas(driver, url):
    print(f"🌐 Procesando: {url}")
    try:
        driver.get(url)
        time.sleep(3) # Espera inicial
    except Exception as e:
        print(f"❌ Error cargando URL: {e}")
        return []

    # Obtener Match ID de la URL
    match_id = "Unknown"
    match_search = re.search(r'vlr\.gg/(\d+)', url)
    if match_search:
        match_id = match_search.group(1)

    datos_partido = []

    # Encontrar contenedores de mapas (excluyendo el general 'all')
    contenedores_mapas = driver.find_elements(By.CSS_SELECTOR, "div.vm-stats-game")

    for div_mapa in contenedores_mapas:
        try:
            game_id = div_mapa.get_attribute("data-game-id")
            
            # Saltamos el resumen general ("all")
            if not game_id or game_id == "all":
                continue

            # Extraer nombre del mapa
            soup_mapa = BeautifulSoup(div_mapa.get_attribute('outerHTML'), 'html.parser')
            map_div = soup_mapa.find('div', class_='map')
            if not map_div:
                continue
                
            map_name_raw = map_div.get_text(strip=True)
            map_name = map_name_raw.split()[0] # Limpieza: "Bind PICK" -> "Bind"
            
            map_id = f"{match_id}_{map_name.lower()}"
            print(f"  📍 Analizando Mapa: {map_name} ({map_id})")

            # --- ESTRATEGIA DE PESTAÑAS (ATTACK / DEFENSE) ---
            # Los botones tienen atributo data-side="t" (Attack) y data-side="ct" (Defend)
            
            pestanas = {
                'Attack': 't',  # Nombre en BD : valor de data-side
                'Defense': 'ct'
            }

            for nombre_lado, data_side_valor in pestanas.items():
                try:
                    # Buscar el botón con data-side dentro de este contenedor
                    # Usamos un selector más específico
                    boton = div_mapa.find_element(
                        By.CSS_SELECTOR, 
                        f"div.js-side-filter div[data-side='{data_side_valor}']"
                    )
                    
                    # Hacer clic con JS (más robusto)
                    driver.execute_script("arguments[0].click();", boton)
                    time.sleep(1) # Pausa para que el DOM cambie
                    
                    # Refrescar el HTML del contenedor
                    soup_actualizado = BeautifulSoup(div_mapa.get_attribute('outerHTML'), 'html.parser')
                    
                    # Buscamos las tablas de estadísticas
                    tablas = soup_actualizado.find_all('table', class_='wf-table-inset')

                    for tabla in tablas:
                        filas = tabla.find_all('tr')

                        for fila in filas:
                            # Verificar si es una fila de jugador
                            celda_jugador = fila.find('td', class_='mod-player')
                            if not celda_jugador: 
                                continue

                            # --- EXTRACCIÓN DE DATOS ---
                            
                            # 1. Nombre Jugador y Equipo
                            div_jugador = celda_jugador.find('div', class_='text-of')
                            player_name = div_jugador.get_text(strip=True) if div_jugador else "Unknown"
                            
                            div_equipo = celda_jugador.find('div', class_='ge-text-light')
                            team_name = div_equipo.get_text(strip=True) if div_equipo else "Unknown"

                            # 2. Agente (desde la imagen)
                            celda_agente = fila.find('td', class_='mod-agents')
                            agent = "Unknown"
                            if celda_agente:
                                img_agente = celda_agente.find('img')
                                if img_agente and 'title' in img_agente.attrs:
                                    agent = img_agente['title']

                            # 3. Estadísticas Numéricas
                            # Cada celda tiene múltiples <span> con clases diferentes:
                            # - mod-both (All), mod-t (Attack), mod-ct (Defense)
                            # Necesitamos extraer solo el valor correcto según el lado
                            
                            # Determinar qué clase buscar según el lado actual
                            side_class = f"mod-{data_side_valor}"  # 't' o 'ct'
                            
                            stats_cells = fila.find_all('td', class_='mod-stat')
                            
                            # Verificar que tenemos suficientes columnas
                            if len(stats_cells) < 11:
                                print(f"    ⚠️ Fila incompleta para {player_name}, saltando...")
                                continue
                            
                            # Función auxiliar para extraer el valor correcto
                            def extraer_stat(cell, side_class):
                                span = cell.find('span', class_=lambda c: c and side_class in c)
                                if span:
                                    return span.get_text(strip=True).replace('%', '')
                                return "0"
                            
                            # INDICES: 0:R, 1:ACS, 2:K, 3:D, 4:A, 5:+/-, 6:KAST, 7:ADR, 8:HS%, 9:FK, 10:FD
                            rating = extraer_stat(stats_cells[0], side_class)
                            acs = extraer_stat(stats_cells[1], side_class)
                            kills = extraer_stat(stats_cells[2], side_class)
                            deaths = extraer_stat(stats_cells[3], side_class)
                            assists = extraer_stat(stats_cells[4], side_class)
                            # diff = stats_cells[5] (LO SALTAMOS)
                            kast = extraer_stat(stats_cells[6], side_class)
                            adr = extraer_stat(stats_cells[7], side_class)
                            hs_perc = extraer_stat(stats_cells[8], side_class)
                            fk = extraer_stat(stats_cells[9], side_class)
                            fd = extraer_stat(stats_cells[10], side_class)

                            # Guardar fila
                            datos_partido.append({
                                'match_id': match_id,
                                'map_id': map_id,
                                'player_name': player_name,
                                'team_name': team_name,
                                'side': nombre_lado,
                                'agent': agent,
                                'rating': rating,
                                'acs': acs,
                                'kills': kills,
                                'deaths': deaths,
                                'assists': assists,
                                'kast': kast,
                                'adr': adr,
                                'hs_percent': hs_perc,
                                'fk': fk,
                                'fd': fd
                            })

                except Exception as e_tab:
                    print(f"    ⚠️ Error en pestaña {nombre_lado} de {map_name}: {e_tab}")
                    import traceback
                    traceback.print_exc()

        except Exception as e_map:
            print(f"  ❌ Error procesando mapa: {e_map}")
            import traceback
            traceback.print_exc()
            continue

    return datos_partido

# --- MAIN ---
if __name__ == "__main__":
    print("🚀 Iniciando extracción de estadísticas por lado...")
    print("="*60)
    
    # Configurar Chrome
    options = Options()
    options.add_argument("--headless")  # Sin ventana visible
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

        # Guardar a Excel
        if todos_los_datos:
            df = pd.DataFrame(todos_los_datos)
            
            # Ordenar columnas
            cols_order = ['match_id', 'map_id', 'player_name', 'team_name', 'side', 'agent', 
                          'rating', 'acs', 'kills', 'deaths', 'assists', 'kast', 'adr', 
                          'hs_percent', 'fk', 'fd']
            
            df = df[cols_order]
            
            archivo_salida = os.path.join(OUTPUT_DIR, "vlr_stats_players_sides.xlsx")
            df.to_excel(archivo_salida, index=False)
            
            print("\n" + "="*60)
            print(f"✅ ¡Éxito! Archivo guardado: {archivo_salida}")
            print(f"\n📊 RESUMEN:")
            print(f"   • Total de filas: {len(df)}")
            print(f"   • Jugadores únicos: {df['player_name'].nunique()}")
            print(f"   • Mapas: {df['map_id'].nunique()}")
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