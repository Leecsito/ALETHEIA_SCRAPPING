"""
ALETHEIA - [Script 1] Equipos y jugadores franquiciados (VCT standings)
--------------------------------------------------------------------------
Fuente: VLR.gg — recibe la URL base del hub VCT (ej. https://www.vlr.gg/vct)
y navega automáticamente a su pestaña /standings.

Reemplaza a los antiguos scrapear_equipos.py y scrapear_jugadores.py: genera
en una sola pasada ambos catálogos maestros.

Extrae, en una sola pasada:
  - Equipos franquiciados (team_id, team_name, tag, country, region, url)
  - Roster actual de cada equipo (player_id, nickname, real_name, country,
    team_id, team_name)

IMPORTANTE: /vct/standings solo lista los equipos franquiciados (48: 12 por
región). Este script NO incluye equipos Challengers/tier-2 (el antiguo
scrapear_equipos.py los obtenía de /rankings).

URL: si existe la variable de entorno ALETHEIA_VCT_URL se usa esa; si no, se
pide por consola (ejecución manual); y si se omite, se usa https://www.vlr.gg/vct

Salida: output_data/vct_equipos.xlsx   (Hoja: Equipos)
        output_data/vct_jugadores.xlsx (Hoja: Jugadores)
"""

import sys
import os
import re
import time
import pandas as pd
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from driver_setup import crear_driver
from url_utils import normalizar_url

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def construir_url_standings(url_base: str) -> str:
    """Acepta https://www.vlr.gg/vct (o con /standings ya puesto) y
    devuelve siempre la URL de standings."""
    url_base = url_base.rstrip('/')
    if url_base.endswith('/standings'):
        return url_base
    return url_base + '/standings'


def scrapear_standings(driver, url_standings: str):
    print(f"🌐 Cargando standings: {url_standings}")
    driver.get(url_standings)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    equipos = []
    for grupo in soup.find_all('div', class_='eg-standing-group'):
        label = grupo.find('div', class_='wf-label')
        region = label.get_text(strip=True).replace(" Points", "") if label else "Unknown"

        for celda in grupo.find_all('td', class_='eg-standing-group-team'):
            a = celda.find('a', href=True)
            if not a:
                continue
            m = re.search(r'/team/(\d+)/', a['href'])
            if not m:
                continue
            team_id = int(m.group(1))

            nombre_div = a.find('div', style=lambda s: s and 'font-weight: 700' in s)
            team_name = nombre_div.get_text(strip=True) if nombre_div else None

            pais_div = a.find('div', class_='ge-text-light')
            country = pais_div.get_text(strip=True) if pais_div else None

            href = a['href']
            url_completa = "https://www.vlr.gg" + href if href.startswith('/') else href

            equipos.append({
                "team_id": team_id,
                "team_name": team_name,
                "country": country,
                "region": region,
                "url": url_completa,
            })

    return equipos


def scrapear_equipo(driver, url_equipo: str):
    """Devuelve (tag, lista_de_jugadores) para un equipo, visitando su página."""
    driver.get(url_equipo)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    tag_h2 = soup.find('h2', class_='team-header-tag')
    tag = tag_h2.get_text(strip=True) if tag_h2 else None

    jugadores = []
    for item in soup.find_all('div', class_='team-roster-item'):
        a = item.find('a', href=True)
        if not a:
            continue
        m = re.search(r'/player/(\d+)/', a['href'])
        if not m:
            continue
        player_id = int(m.group(1))

        alias_div = item.find('div', class_='team-roster-item-name-alias')
        nickname = alias_div.get_text(strip=True) if alias_div else None

        country = None
        if alias_div:
            flag = alias_div.find('i', class_='flag')
            if flag:
                for c in flag.get('class', []):
                    if c.startswith('mod-'):
                        country = c.replace('mod-', '')

        real_div = item.find('div', class_='team-roster-item-name-real')
        real_name = real_div.get_text(strip=True) if real_div else None

        jugadores.append({
            "player_id": player_id,
            "nickname": nickname,
            "real_name": real_name,
            "country": country,
        })

    return tag, jugadores


if __name__ == "__main__":
    url_input = os.environ.get("ALETHEIA_VCT_URL", "").strip()
    if not url_input:
        try:
            url_input = input("🔗 Pega el enlace base de VCT (ej. https://www.vlr.gg/vct): ").strip()
        except EOFError:
            url_input = ""
    if not url_input:
        url_input = "https://www.vlr.gg/vct"
        print(f"ℹ️  Usando URL por defecto: {url_input}")

    url_standings = construir_url_standings(normalizar_url(url_input))

    print("🚀 ETL: equipos franquiciados VCT + roster oficial")
    print("=" * 60)

    driver = crear_driver()
    todos_equipos = []
    todos_jugadores = []

    try:
        equipos = scrapear_standings(driver, url_standings)
        print(f"✓ {len(equipos)} equipos franquiciados encontrados en standings\n")

        for i, eq in enumerate(equipos):
            print(f"[{i+1}/{len(equipos)}] {eq['team_name']} ({eq['region']}) -> {eq['url']}")
            tag, jugadores = scrapear_equipo(driver, eq['url'])
            eq['tag'] = tag
            print(f"   tag={tag} | {len(jugadores)} jugadores")

            for j in jugadores:
                j['team_id'] = eq['team_id']
                j['team_name'] = eq['team_name']
                todos_jugadores.append(j)

            todos_equipos.append(eq)

    finally:
        driver.quit()
        print("\n🔒 Driver cerrado correctamente")

    df_equipos = pd.DataFrame(todos_equipos)[
        ["team_id", "team_name", "tag", "country", "region", "url"]
    ]
    df_jugadores = pd.DataFrame(todos_jugadores)[
        ["player_id", "nickname", "real_name", "country", "team_id", "team_name"]
    ]

    ruta_equipos = os.path.join(OUTPUT_DIR, "vct_equipos.xlsx")
    ruta_jugadores = os.path.join(OUTPUT_DIR, "vct_jugadores.xlsx")
    df_equipos.to_excel(ruta_equipos, index=False, sheet_name="Equipos")
    df_jugadores.to_excel(ruta_jugadores, index=False, sheet_name="Jugadores")

    print("\n📊 RESUMEN:")
    print(f"   • Equipos: {len(df_equipos)}")
    print(f"   • Jugadores: {len(df_jugadores)}")
    print(f"\n📂 Guardado en: {ruta_equipos}")
    print(f"📂 Guardado en: {ruta_jugadores}")
