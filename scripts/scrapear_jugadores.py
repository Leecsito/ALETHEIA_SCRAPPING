"""
ALETHEIA - Script 7: Catálogo de jugadores desde VLR.gg (con team_id nativo)
----------------------------------------------------------------------------
Fuente : VLR.gg (stats por región y visitas a perfiles individuales)
Salida : output_data/vct_jugadores.xlsx (player_id, nickname, team_id, team_name)

Paso 1: Recorre /stats por región (tier=vct, span=90d, min_rounds=100) para listar
        todos los jugadores competitivos activos (player_id + nickname), paginando.
Paso 2: Visita el perfil individual de cada jugador para leer la sección "Current Teams"
        (primer equipo registrado) y asociar su team_id y team_name nativo de VLR.
"""

import sys
import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from driver_setup import crear_driver

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 4 regiones oficiales VCT
REGIONES = ["americas", "emea", "pacific", "china"]

STATS_URL = (
    "https://www.vlr.gg/stats/?region={region}&tier=vct&span=90d"
    "&min_rounds=100&min_rating=0&page={page}"
)


def obtener_jugadores_region(driver, region):
    """Recorre todas las páginas de /stats para una región y devuelve {player_id: (nickname, href)}."""
    jugadores = {}
    page = 1
    while True:
        url = STATS_URL.format(region=region, page=page)
        print(f"   📄 Página {page}: {url}")
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        anchors = soup.select('td.mod-player.mod-a > a[href*="/player/"]')
        if not anchors:
            break

        for a in anchors:
            href = a['href']
            if href.startswith('/'):
                href = 'https://www.vlr.gg' + href
            m = re.search(r'/player/(\d+)/', href)
            if not m:
                continue
            player_id = int(m.group(1))
            name_div = a.find('div', class_='st-pl-name')
            nickname = name_div.get_text(strip=True) if name_div else None
            jugadores[player_id] = (nickname, href)

        # ¿Hay página siguiente?
        siguiente = soup.select_one(f'a.btn.mod-page[href*="page={page + 1}"]')
        if not siguiente:
            break
        page += 1

    return jugadores


def obtener_equipo_actual(driver, player_url):
    """Visita el perfil del jugador y devuelve (team_id, team_name) de su primer 'Current Team'."""
    if not player_url or not isinstance(player_url, str) or not player_url.startswith("http"):
        print(f"      ⚠️  URL inválida, se omite: {player_url!r}")
        return None, None

    try:
        driver.get(player_url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        for h2 in soup.find_all('h2', class_='wf-label'):
            if 'current teams' in h2.get_text(strip=True).lower():
                card = h2.find_next_sibling('div', class_='wf-card')
                if not card:
                    return None, None
                primero = card.find('a', class_='wf-module-item')
                if not primero:
                    return None, None
                m = re.search(r'/team/(\d+)/', primero.get('href', ''))
                team_id = int(m.group(1)) if m else None
                nombre_div = primero.find('div', style=lambda s: s and 'font-weight: 500' in s)
                team_name = nombre_div.get_text(strip=True) if nombre_div else None
                return team_id, team_name

        return None, None  # no tiene equipo actual (agente libre / retirado)

    except Exception as e:
        print(f"      ⚠️  Error en {player_url}: {e}")
        return None, None


if __name__ == "__main__":
    print("🚀 Scrapeando catálogo de jugadores desde VLR.gg...")
    print("=" * 60)

    driver = crear_driver()
    todos_jugadores = {}

    try:
        for region in REGIONES:
            print(f"\n🌐 Región: {region}")
            jugadores_region = obtener_jugadores_region(driver, region)
            print(f"   ✓ {len(jugadores_region)} jugadores encontrados")
            todos_jugadores.update(jugadores_region)

        print(f"\n👥 Total jugadores únicos (4 regiones): {len(todos_jugadores)}")
        print("🔎 Visitando cada perfil para obtener su equipo actual...\n")

        filas = []
        for i, (player_id, (nickname, url)) in enumerate(todos_jugadores.items(), start=1):
            team_id, team_name = obtener_equipo_actual(driver, url)
            print(f"   [{i}/{len(todos_jugadores)}] {nickname} -> {team_name} (id={team_id})")
            filas.append({
                "player_id": player_id,
                "nickname": nickname,
                "team_id": team_id,
                "team_name": team_name,
            })

    finally:
        driver.quit()
        print("\n🔒 Driver cerrado correctamente")

    df = pd.DataFrame(filas)
    ruta = os.path.join(OUTPUT_DIR, "vct_jugadores.xlsx")
    df.to_excel(ruta, index=False, sheet_name="Jugadores")

    print("\n📊 RESUMEN:")
    print(f"   • Total jugadores: {len(df)}")
    print(f"   • Sin equipo actual (agente libre/retirado): {df['team_id'].isna().sum()}")
    print(f"\n📂 Guardado en: {ruta}")
