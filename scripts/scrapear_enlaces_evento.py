"""
ALETHEIA - Script: Extractor de enlaces de evento VCT
Fuente : VLR.gg  (página de evento)
Salida : output_data/enlaces_<nombre_evento>.txt

Modos:
  - "all"       → todos los partidos (completados + próximos + TBD)
  - "completed" → solo partidos ya finalizados
"""

import time
import os
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def parsear_evento(url: str) -> dict:
    match = re.search(r'vlr\.gg/event/(\d+)/([^/?]+)', url)
    if match:
        return {'id': match.group(1), 'slug': match.group(2)}
    return None


def es_completado(tag) -> bool:
    """
    VLR.gg marca los partidos finalizados con:
        <div class="ml mod-completed"> dentro de <div class="match-item-eta">
    Partidos futuros o TBD NO tienen esta clase.
    """
    eta_div = tag.find('div', class_='match-item-eta')
    if not eta_div:
        return False
    ml_div = eta_div.find(
        'div',
        class_=lambda c: c and 'ml' in c.split() and 'mod-completed' in c.split()
    )
    return ml_div is not None


def extraer_enlaces_evento(driver, url: str, solo_completados: bool = False) -> list:
    """
    Parámetros:
        driver           : instancia Selenium WebDriver
        url              : URL del evento
        solo_completados : True  → solo partidos finalizados
                           False → todos (completados + próximos + TBD)
    """
    evento = parsear_evento(url)
    if not evento:
        print("❌ No se pudo interpretar la URL del evento.")
        return []

    matches_url = f"https://www.vlr.gg/event/matches/{evento['id']}/{evento['slug']}"
    print(f"🔄 Conectando a: {matches_url}")

    try:
        driver.get(matches_url)
        time.sleep(3)
    except Exception as e:
        print(f"❌ Error cargando la página: {e}")
        return []

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Recoge TODOS los match-item (incluye TBD y futuros)
    tags = soup.find_all(
        'a',
        class_=lambda c: c and 'match-item' in c,
        href=re.compile(r'^/\d+/')
    )

    urls   = []
    vistos = set()

    for tag in tags:
        # Filtro opcional
        if solo_completados and not es_completado(tag):
            continue

        href         = tag.get('href', '')
        url_completa = "https://www.vlr.gg" + href
        if url_completa not in vistos:
            vistos.add(url_completa)
            urls.append(url_completa)

    return urls


def nombre_archivo_desde_url(url: str, solo_completados: bool = False) -> str:
    evento = parsear_evento(url)
    sufijo = "_completed" if solo_completados else "_all"
    if evento:
        return f"enlaces_{evento['slug']}{sufijo}.txt"
    return f"enlaces_evento{sufijo}.txt"


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  ⚔️  ALETHEIA — Extractor de enlaces de evento VLR.gg")
    print("=" * 60)
    print()

    EVENTO_URL = input("  🔗 Pega el enlace del evento: ").strip()
    if not EVENTO_URL:
        print("❌ No ingresaste ningún enlace. Abortando.")
        exit(1)

    print()
    print("  ¿Qué partidos quieres extraer?")
    print("    [1] Todos (completados + próximos + TBD)  ← default")
    print("    [2] Solo completados")
    modo = input("  Elige [1/2]: ").strip()
    SOLO_COMPLETADOS = (modo == "2")

    print()
    print(f"  Modo: {'solo completados ✅' if SOLO_COMPLETADOS else 'todos los partidos 📋'}")
    print()

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    except Exception as e:
        print(f"❌ Error inicializando Chrome: {e}")
        exit(1)

    try:
        urls_partidos = extraer_enlaces_evento(driver, EVENTO_URL, solo_completados=SOLO_COMPLETADOS)

        if not urls_partidos:
            print("⚠️  No se encontraron partidos. Verifica el enlace del evento.")
        else:
            nombre_salida = nombre_archivo_desde_url(EVENTO_URL, SOLO_COMPLETADOS)
            ruta_salida   = os.path.join(OUTPUT_DIR, nombre_salida)

            with open(ruta_salida, 'w', encoding='utf-8') as f:
                for u in urls_partidos:
                    f.write(u + '\n')

            print(f"\n✅ {len(urls_partidos)} partidos encontrados")
            print(f"💾 Guardado en: {ruta_salida}")
            print("\n📋 Lista de URLs:")
            for u in urls_partidos:
                print(f"   {u}")

    except Exception as e:
        print(f"\n❌ Error durante el scraping: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()
        print("\n🔒 Driver cerrado correctamente")

    print("\n🏁 Script finalizado.")


# ─── Función pública para importar ───────────────────────────────────────────
def cargar_enlaces(nombre_archivo: str) -> list:
    ruta = os.path.join(OUTPUT_DIR, nombre_archivo)
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta}")
    with open(ruta, 'r', encoding='utf-8') as f:
        return [linea.strip() for linea in f if linea.strip()]