"""
ALETHEIA - Script: Extractor de enlaces de evento VCT
Fuente : VLR.gg  (página de evento)
Salida : output_data/enlaces_<nombre_evento>.txt
         (una URL por línea, listo para ser leído por cualquier script Python)

Ejemplos de URLs válidas:
  https://www.vlr.gg/event/2682/vct-2026-americas-kickoff
  https://www.vlr.gg/event/2683/vct-2026-pacific-kickoff
  https://www.vlr.gg/event/2684/vct-2026-emea-kickoff
  https://www.vlr.gg/event/2685/vct-2026-china-kickoff
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
    """
    Extrae el event_id y slug de cualquier variante de URL del evento.
    Ej: https://www.vlr.gg/event/2682/vct-2026-americas-kickoff/main-event
        → { id: '2682', slug: 'vct-2026-americas-kickoff' }
    """
    match = re.search(r'vlr\.gg/event/(\d+)/([^/?]+)', url)
    if match:
        return {'id': match.group(1), 'slug': match.group(2)}
    return None


def extraer_enlaces_evento(driver, url: str) -> list:
    """
    Dado un enlace de evento VLR.gg, devuelve la lista de URLs
    de todos los partidos.

    URL real de partidos: /event/matches/{id}/{slug}
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
    tags = soup.find_all('a', class_=lambda c: c and 'match-item' in c,
                         href=re.compile(r'^/\d+/'))

    urls   = []
    vistos = set()
    for tag in tags:
        href         = tag.get('href', '')
        url_completa = "https://www.vlr.gg" + href
        if url_completa not in vistos:
            vistos.add(url_completa)
            urls.append(url_completa)

    return urls


def nombre_archivo_desde_url(url: str) -> str:
    evento = parsear_evento(url)
    if evento:
        return f"enlaces_{evento['slug']}.txt"
    return "enlaces_evento.txt"


# ─────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  ⚔️  ALETHEIA — Extractor de enlaces de evento VLR.gg")
    print("=" * 60)
    print()
    print("  Ejemplos de enlace válido:")
    print("    https://www.vlr.gg/event/2682/vct-2026-americas-kickoff")
    print("    https://www.vlr.gg/event/2683/vct-2026-pacific-kickoff")
    print()

    EVENTO_URL = input("  🔗 Pega el enlace del evento: ").strip()

    if not EVENTO_URL:
        print("❌ No ingresaste ningún enlace. Abortando.")
        exit(1)

    # Inicializar Selenium
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
        urls_partidos = extraer_enlaces_evento(driver, EVENTO_URL)

        if not urls_partidos:
            print("⚠️  No se encontraron partidos. Verifica el enlace del evento.")
        else:
            nombre_salida = nombre_archivo_desde_url(EVENTO_URL)
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


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PÚBLICA — para importar desde otros scripts
# ─────────────────────────────────────────────────────────────────────────────
def cargar_enlaces(nombre_archivo: str) -> list:
    """
    Lee un .txt generado por este script y devuelve la lista de URLs.

    Uso:
        from scrapear_enlaces_evento import cargar_enlaces
        urls = cargar_enlaces("enlaces_vct-2026-americas-kickoff.txt")
    """
    ruta = os.path.join(OUTPUT_DIR, nombre_archivo)
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta}")
    with open(ruta, 'r', encoding='utf-8') as f:
        return [linea.strip() for linea in f if linea.strip()]