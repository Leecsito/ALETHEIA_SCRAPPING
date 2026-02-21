"""
ALETHEIA - Script 1: Equipos y Jugadores VCT 2026
Fuente: Liquipedia
Salida: output_data/vct_equipos.xlsx
         output_data/vct_jugadores.xlsx
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os

# --- CONFIGURACIÓN ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Carpeta de salida relativa al script
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# FUNCIÓN 1: OBTENER TODOS LOS EQUIPOS (MASTER)
# ---------------------------------------------------------------------------
def obtener_equipos_master():
    url = "https://liquipedia.net/valorant/VCT/2026/Partnered_Teams"
    print(f"🔄 Conectando al Hub VCT 2026: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')

        equipos_data = []
        id_counter = 1

        regiones_objetivo = ["Americas", "EMEA", "Pacific", "China"]
        todos_h3 = soup.find_all('h3')

        for h3 in todos_h3:
            texto_header = h3.get_text().strip()

            region_actual = None
            for region in regiones_objetivo:
                if region in texto_header:
                    region_actual = region
                    break

            if region_actual:
                print(f"  📍 Procesando Región: {region_actual}...")
                tabla = h3.find_next('table', class_='wikitable')

                if tabla:
                    spans_equipo = tabla.find_all('span', class_='team-template-text')
                    for span in spans_equipo:
                        enlace = span.find('a')
                        if enlace:
                            nombre = enlace.get_text().strip()
                            url_equipo = "https://liquipedia.net" + enlace['href']

                            if nombre and nombre != "TBD":
                                equipos_data.append({
                                    'team_id': id_counter,
                                    'team_name': nombre,
                                    'region': region_actual,
                                    'url': url_equipo
                                })
                                id_counter += 1

        return equipos_data

    except Exception as e:
        print(f"❌ Error crítico en equipos: {e}")
        return []


# ---------------------------------------------------------------------------
# FUNCIÓN 2: OBTENER JUGADORES ACTIVOS
# ---------------------------------------------------------------------------
def obtener_jugadores_master(df_equipos):
    print("\n🚀 Iniciando extracción de JUGADORES ACTIVOS...")
    jugadores_data = []
    total_equipos = len(df_equipos)

    for index, fila in df_equipos.iterrows():
        print(f"  ({index + 1}/{total_equipos}) Scrapeando: {fila['team_name']}...")
        time.sleep(0.5)

        try:
            response = requests.get(fila['url'], headers=HEADERS, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')

            header_roster = (
                soup.find(id='Active') or
                soup.find(id='Active_Roster') or
                soup.find(id='Player_Roster')
            )

            if header_roster:
                tabla_roster = header_roster.find_next('table', class_='roster-card')

                if tabla_roster:
                    for f in tabla_roster.select('tr'):
                        celda_id = f.find('td', class_='ID')
                        celda_nombre = f.find('td', class_='Name')

                        if celda_id and celda_nombre:
                            nick = celda_id.get_text(strip=True)
                            nombre_real = (
                                celda_nombre.get_text(strip=True)
                                .replace("(", "").replace(")", "").strip()
                            )

                            if nick:
                                jugadores_data.append({
                                    'nickname': nick,
                                    'real_name': nombre_real,
                                    'team_id': fila['team_id'],
                                    'team_name': fila['team_name']
                                })
                else:
                    print(f"     ⚠️ {fila['team_name']}: Header encontrado pero no la tabla 'roster-card'.")
            else:
                print(f"     ⚠️ {fila['team_name']}: No se encontró header 'Active'. Intentando búsqueda directa...")
                tabla_directa = soup.find('table', class_='roster-card')
                if tabla_directa:
                    print("     ⚠️ Tabla encontrada sin header — omitida por seguridad.")
                else:
                    print(f"     ❌ {fila['team_name']}: Estructura desconocida.")

        except Exception as e:
            print(f"     ❌ Error procesando {fila['team_name']}: {e}")

    return jugadores_data


# ---------------------------------------------------------------------------
# GUARDAR EN EXCEL
# ---------------------------------------------------------------------------
def guardar_excel(df, nombre_archivo, sheet_name="Sheet1"):
    ruta = os.path.join(OUTPUT_DIR, nombre_archivo)
    df.to_excel(ruta, index=False, sheet_name=sheet_name)
    print(f"  💾 Guardado: {ruta}")


# ---------------------------------------------------------------------------
# EJECUCIÓN PRINCIPAL
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 1. Equipos
    lista_equipos = obtener_equipos_master()
    df_equipos_total = pd.DataFrame(lista_equipos)

    if df_equipos_total.empty:
        print("❌ No se pudieron obtener equipos. Abortando.")
        exit(1)

    print(f"\n✅ TABLA EQUIPOS LISTA: {len(df_equipos_total)} registros.")
    guardar_excel(df_equipos_total, "vct_equipos.xlsx", sheet_name="Equipos")

    # 2. Jugadores
    lista_jugadores = obtener_jugadores_master(df_equipos_total)
    df_jugadores_total = pd.DataFrame(lista_jugadores)

    if df_jugadores_total.empty:
        print("⚠️ No se encontraron jugadores. Revisa los selectores.")
    else:
        print(f"\n✅ TABLA JUGADORES LISTA: {len(df_jugadores_total)} registros.")
        print(df_jugadores_total.head(10).to_string(index=False))

        num_equipos = len(df_equipos_total)
        num_jugadores = len(df_jugadores_total)
        promedio = num_jugadores / num_equipos if num_equipos > 0 else 0
        print(f"\n📊 {num_jugadores} jugadores en {num_equipos} equipos.")
        print(f"   Promedio: {promedio:.1f} jugadores/equipo (ideal entre 5.0 y 6.0)")

        guardar_excel(df_jugadores_total, "vct_jugadores.xlsx", sheet_name="Jugadores")

    print("\n🏁 Script finalizado.")
