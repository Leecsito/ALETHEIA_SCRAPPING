"""
ALETHEIA - Script 1: Catálogo de equipos desde VLR.gg (con team_id nativo)
-------------------------------------------------------------------------
Fuente : VLR.gg (páginas de rankings por región)
Salida : output_data/vct_equipos.xlsx  (team_id, team_name, region, country, url)

Extrae el ID numérico real de cada equipo directamente de VLR.gg, permitiendo
vincularlo directamente con los datos de partidos, rondas, stats y economía.
"""

import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# slug de la URL -> etiqueta legible de región (misma que usa VLR en el h2 de /rankings)
REGIONES = {
    "north-america": "North America",
    "europe": "Europe",
    "brazil": "Brazil",
    "asia-pacific": "Asia-Pacific",
    "korea": "Korea",
    "china": "China",
    "japan": "Japan",
    "la-s": "LA-S",
    "la-n": "LA-N",
    "oceania": "Oceania",
    "mena": "MENA",
    "gc": "GC",
    "collegiate": "Collegiate",
}

BASE_URL = "https://www.vlr.gg/rankings/{slug}"


def crear_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")

    chrome_binary = os.environ.get("CHROME_BINARY_PATH")
    if chrome_binary:
        options.binary_location = chrome_binary

    driver_version = os.environ.get("CHROMEDRIVER_VERSION")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager(driver_version=driver_version).install()),
        options=options,
    )


def parsear_region(html, region_label):
    soup = BeautifulSoup(html, 'html.parser')
    filas = soup.find_all('div', class_='rank-item')

    equipos = []
    for fila in filas:
        a = fila.find('a', class_='rank-item-team')
        if not a or not a.get('href'):
            continue
        m = re.search(r'/team/(\d+)/', a['href'])
        if not m:
            continue
        team_id = int(m.group(1))

        country_div = a.find('div', class_='rank-item-team-country')
        country = country_div.get_text(strip=True) if country_div else None

        strings = list(a.stripped_strings)
        team_name = strings[0] if strings else None

        href = a['href']
        url_completa = "https://www.vlr.gg" + href if href.startswith('/') else href

        equipos.append({
            "team_id": team_id,
            "team_name": team_name,
            "region": region_label,
            "country": country,
            "url": url_completa,
        })
    return equipos


if __name__ == "__main__":
    print("🚀 Scrapeando catálogo de equipos desde VLR.gg (por región)...")
    print("=" * 60)

    driver = crear_driver()
    todos_equipos = []

    try:
        for slug, label in REGIONES.items():
            url = BASE_URL.format(slug=slug)
            print(f"🌐 {label} -> {url}")
            driver.get(url)
            time.sleep(3)
            html = driver.page_source
            equipos = parsear_region(html, label)
            print(f"   ✓ {len(equipos)} equipos encontrados")
            todos_equipos.extend(equipos)

    finally:
        driver.quit()
        print("\n🔒 Driver cerrado correctamente")

    df = pd.DataFrame(todos_equipos)

    antes = len(df)
    df = df.drop_duplicates(subset="team_id", keep="first")
    despues = len(df)
    if antes != despues:
        print(f"⚠️  {antes - despues} duplicados removidos (mismo team_id en 2 regiones)")

    ruta = os.path.join(OUTPUT_DIR, "vct_equipos.xlsx")
    df.to_excel(ruta, index=False, sheet_name="Equipos")

    print("\n📊 RESUMEN:")
    print(f"   • Total equipos: {len(df)}")
    print(df["region"].value_counts().to_string())
    print(f"\n📂 Guardado en: {ruta}")
