"""
ALETHEIA - Extractor combinado: eventos VCT -> enlaces de partidos
--------------------------------------------------------------------
[1] Scrapea el hub de VCT (ej. https://www.vlr.gg/vct-2025) y guarda
    los 15 enlaces de eventos tier-1 en output_data/vct.txt
[2] Lee ese vct.txt y, evento por evento, reutiliza la misma lógica de
    scrapear_enlaces_evento.py para generar un enlaces_<slug>_*.txt
    por cada torneo, sin tener que correrlo uno por uno.
"""

import time
import os
import re
import sys
from bs4 import BeautifulSoup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from driver_setup import crear_driver

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# PARTE 1: hub de eventos -> vct.txt
# ─────────────────────────────────────────────────────────────────────────────
def extraer_eventos_hub(driver, url_hub: str) -> list:
    """
    Scrapea una página hub de VCT (ej. vlr.gg/vct-2025, vlr.gg/vct-2026)
    y devuelve la lista de URLs de eventos tier-1 (kickoffs, stages, masters,
    champions), tal como aparecen bajo la clase 'event-item'.
    """
    print(f"🔄 Conectando al hub: {url_hub}")
    try:
        driver.get(url_hub)
        time.sleep(3)
    except Exception as e:
        print(f"❌ Error cargando el hub: {e}")
        return []

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    tags = soup.find_all('a', class_=lambda c: c and 'event-item' in c.split())

    urls, vistos = [], set()
    for tag in tags:
        href = tag.get('href', '')
        if href.startswith('/'):
            href = 'https://www.vlr.gg' + href
        if href and href not in vistos:
            vistos.add(href)
            urls.append(href)

    return urls


def guardar_vct_txt(urls: list) -> str:
    ruta = os.path.join(OUTPUT_DIR, "vct.txt")
    with open(ruta, 'w', encoding='utf-8') as f:
        for u in urls:
            f.write(u + '\n')
    return ruta


# ─────────────────────────────────────────────────────────────────────────────
# PARTE 2: por cada evento -> enlaces de partidos (mismo código que
# scrapear_enlaces_evento.py)
# ─────────────────────────────────────────────────────────────────────────────
def parsear_evento(url: str) -> dict:
    match = re.search(r'vlr\.gg/event/(\d+)/([^/?]+)', url)
    if match:
        return {'id': match.group(1), 'slug': match.group(2)}
    return None


def es_completado(tag) -> bool:
    eta_div = tag.find('div', class_='match-item-eta')
    if not eta_div:
        return False
    ml_div = eta_div.find(
        'div',
        class_=lambda c: c and 'ml' in c.split() and 'mod-completed' in c.split()
    )
    return ml_div is not None


def extraer_enlaces_evento(driver, url: str, solo_completados: bool = False) -> list:
    evento = parsear_evento(url)
    if not evento:
        print("   ❌ No se pudo interpretar la URL del evento.")
        return []

    matches_url = f"https://www.vlr.gg/event/matches/{evento['id']}/{evento['slug']}"
    print(f"   🔄 Conectando a: {matches_url}")

    try:
        driver.get(matches_url)
        time.sleep(3)
    except Exception as e:
        print(f"   ❌ Error cargando la página: {e}")
        return []

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    tags = soup.find_all(
        'a',
        class_=lambda c: c and 'match-item' in c,
        href=re.compile(r'^/\d+/')
    )

    urls, vistos = [], set()
    for tag in tags:
        if solo_completados and not es_completado(tag):
            continue
        href = tag.get('href', '')
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


def procesar_todos_los_eventos(driver, urls_eventos: list, solo_completados: bool):
    resumen = []
    for i, url_evento in enumerate(urls_eventos):
        print(f"\n[{i+1}/{len(urls_eventos)}] Evento: {url_evento}")
        urls_partidos = extraer_enlaces_evento(driver, url_evento, solo_completados)

        if not urls_partidos:
            print("   ⚠️  No se encontraron partidos para este evento.")
            resumen.append((url_evento, 0, None))
            continue

        nombre_salida = nombre_archivo_desde_url(url_evento, solo_completados)
        ruta_salida = os.path.join(OUTPUT_DIR, nombre_salida)
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            for u in urls_partidos:
                f.write(u + '\n')

        print(f"   ✅ {len(urls_partidos)} partidos -> {ruta_salida}")
        resumen.append((url_evento, len(urls_partidos), ruta_salida))

    return resumen


# ─────────────────────────────────────────────────────────────────────────────
def leer_txt(ruta: str) -> list:
    with open(ruta, 'r', encoding='utf-8') as f:
        return [linea.strip() for linea in f if linea.strip()]


if __name__ == "__main__":
    print("=" * 60)
    print("  ⚔️  ALETHEIA — Eventos VCT -> Enlaces de partidos")
    print("=" * 60)
    print()
    print("  [1] Scrapear el hub de VCT y generar vct.txt")
    print("  [2] Leer vct.txt y extraer enlaces de partidos de cada evento")
    opcion = input("  Elige [1/2]: ").strip()

    try:
        driver = crear_driver(headless=True)
    except Exception as e:
        print(f"❌ Error inicializando Chrome: {e}")
        exit(1)

    try:
        if opcion == "1":
            print("\n  🔗 Pega los enlaces del hub, uno por uno "
                  "(ej. https://www.vlr.gg/vct-2025, luego vct-2026, etc.)")
            print("     Deja vacío y presiona Enter cuando termines.\n")

            urls_hub = []
            while True:
                url_hub = input(f"  Hub #{len(urls_hub) + 1}: ").strip()
                if not url_hub:
                    break
                urls_hub.append(url_hub)

            if not urls_hub:
                print("❌ No ingresaste ningún enlace. Abortando.")
                exit(1)

            todos_los_eventos = []
            vistos = set()
            for url_hub in urls_hub:
                eventos = extraer_eventos_hub(driver, url_hub)
                print(f"   ✓ {len(eventos)} eventos encontrados en {url_hub}")
                for e in eventos:
                    if e not in vistos:
                        vistos.add(e)
                        todos_los_eventos.append(e)

            if not todos_los_eventos:
                print("⚠️  No se encontraron eventos. Verifica los enlaces del hub.")
            else:
                ruta = guardar_vct_txt(todos_los_eventos)
                print(f"\n✅ {len(todos_los_eventos)} eventos en total ({len(urls_hub)} años)")
                print(f"💾 Guardado en: {ruta}")
                for u in todos_los_eventos:
                    print(f"   {u}")

        elif opcion == "2":
            ruta_vct = os.path.join(OUTPUT_DIR, "vct.txt")
            if not os.path.exists(ruta_vct):
                ruta_vct = input("\n  No encontré output_data/vct.txt. "
                                  "Ingresa la ruta manualmente: ").strip()

            urls_eventos = leer_txt(ruta_vct)
            print(f"\n  -> {len(urls_eventos)} eventos cargados desde {ruta_vct}")

            print("\n  ¿Qué partidos quieres extraer de cada evento?")
            print("    [1] Todos (completados + próximos + TBD)  ← default")
            print("    [2] Solo completados")
            modo = input("  Elige [1/2]: ").strip()
            solo_completados = (modo == "2")

            resumen = procesar_todos_los_eventos(driver, urls_eventos, solo_completados)

            print("\n" + "=" * 60)
            print("📊 RESUMEN FINAL:")
            for url_evento, cantidad, ruta in resumen:
                estado = f"{cantidad} partidos -> {os.path.basename(ruta)}" if ruta else "sin partidos"
                print(f"   • {url_evento}: {estado}")

        else:
            print("❌ Opción inválida.")

    except Exception as e:
        print(f"\n❌ Error durante el scraping: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()
        print("\n🔒 Driver cerrado correctamente")

    print("\n🏁 Script finalizado.")