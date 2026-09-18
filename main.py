"""
ALETHEIA - Punto de entrada principal
Ejecuta los scripts de scraping de datos competitivos de Valorant (VCT 2026).
"""

import subprocess
import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output_data')

# Añadir scripts/ al path para poder importar driver_setup directamente
sys.path.insert(0, SCRIPTS_DIR)


def precalentar_chromedriver():
    """Instala (o verifica en caché) chromedriver UNA SOLA VEZ en el proceso
    principal, antes de lanzar el ThreadPoolExecutor.

    Raíz del WinError 5: webdriver-manager hace un os.replace() interno al
    desempaquetar el zip. Cuando 5 subprocesos corren en paralelo y cada uno
    llama a ChromeDriverManager().install() simultáneamente, Windows bloquea
    el .exe mientras otro proceso lo tiene abierto → PermissionError/WinError 5.

    Solución: el proceso padre llama a install() aquí y obtiene la ruta del
    binario. Esa ruta se inyecta como CHROMEDRIVER_PATH en el entorno de cada
    subproceso. driver_setup.py detecta esta variable y se salta install()
    completamente, construyendo Service() directo con la ruta ya conocida.
    """
    try:
        from driver_setup import detectar_chrome_version_y_binario
        from webdriver_manager.chrome import ChromeDriverManager
        version_mayor, _ = detectar_chrome_version_y_binario()
        if version_mayor:
            ruta = ChromeDriverManager(driver_version=version_mayor).install()
        else:
            ruta = ChromeDriverManager().install()
        print(f"✅ ChromeDriver pre-instalado: {ruta}")
        return ruta
    except Exception as e:
        print(f"⚠️  No se pudo pre-instalar ChromeDriver: {e}")
        return None


SCRIPTS = {
    "0": {
        "nombre": "Extractor de enlaces de evento (VLR.gg)",
        "archivo": "scrapear_enlaces_evento.py",
        "salida": [],  # Nombre dinámico según el evento; nunca se omite
    },
    "1": {
        "nombre": "Equipos y jugadores VCT (franquicias)",
        "archivo": "scrapear_equipos_jugadores_franquicia.py",
        "salida": ["vct_equipos.xlsx", "vct_jugadores.xlsx"],
        "env": {"ALETHEIA_VCT_URL": "https://www.vlr.gg/vct"},
    },
    "2": {
        "nombre": "Partidos VCT (VLR.gg)",
        "archivo": "scrapear_partidos.py",
        "salida": ["vct_partidos.xlsx"],
    },
    "3": {
        "nombre": "Mapas y Rondas (VLR.gg)",
        "archivo": "scrapear_vlr_corregido.py",
        "salida": ["vlr_mapas.xlsx", "vlr_rondas.xlsx"],
    },
    "4": {
        "nombre": "Estadísticas por lado ATK/DEF (VLR.gg)",
        "archivo": "scrapear_stats_pro.py",
        "salida": ["vlr_stats_players_sides.xlsx"],
    },
    "5": {
        "nombre": "Enfrentamientos y Multikills (VLR.gg)",
        "archivo": "scrapear_enfrentamientos.py",
        "salida": ["vlr_enfrentamientos.xlsx", "vlr_multikills_clutches.xlsx"],
    },
    "6": {
        "nombre": "Economía por ronda (VLR.gg)",
        "archivo": "scrapear_economia.py",
        "salida": ["vlr_economia_resumen.xlsx", "vlr_economia_rondas.xlsx"],
    },
}

# Scripts que se ejecutan en paralelo al elegir [A]
SCRIPTS_PARALELOS = ["2", "3", "4", "5", "6"]
# Scripts que siempre corren en secuencia (prerequisitos)
SCRIPTS_SECUENCIALES = ["0", "1"]
# Nº máximo de scripts simultáneos. Cada uno abre su propio Chrome, así que
# bajarlo reduce el consumo de RAM (útil en equipos con poca memoria).
MAX_PARALELOS = 5


def archivos_esperados_evento(nombre_evento):
    """Archivos de salida que debe contener la carpeta de un evento.

    Se derivan de los scripts analíticos 2, 3, 4, 5 y 6 (8 archivos en total).
    Excepción China: VLR.gg no publica enfrentamientos (script 5) ni economía
    (script 6) para esa región, por lo que solo se le exigen los scripts 2, 3
    y 4 (4 archivos).
    """
    keys = ["2", "3", "4"] if "china" in nombre_evento.lower() else ["2", "3", "4", "5", "6"]
    archivos = []
    for k in keys:
        archivos.extend(SCRIPTS[k]["salida"])
    return archivos


def carpeta_evento_completa(nombre_evento, carpeta):
    """Devuelve (completa, faltantes) para la carpeta de un evento.

    `completa` es True solo si TODOS los archivos esperados existen dentro de
    esa carpeta concreta (no en cualquier evento). Así se detectan eventos
    interrumpidos a medias y se reanudan en la siguiente ejecución.
    """
    faltantes = [f for f in archivos_esperados_evento(nombre_evento)
                 if not os.path.exists(os.path.join(carpeta, f))]
    return (not faltantes), faltantes


# ── Control de procesos hijos (evita navegadores huérfanos) ──────────────────
# Al interrumpir con Ctrl+C, subprocess.run() mata solo al script Python hijo,
# NO a sus nietos (chromedriver y chrome.exe). Esos navegadores quedan vivos,
# se acumulan entre corridas y terminan agotando la RAM del equipo. Aquí se
# registran los hijos para poder matar su ÁRBOL completo (taskkill /T).
_PROCESOS_ACTIVOS = {}
_PROCESOS_LOCK = threading.Lock()


def _registrar_proceso(proceso):
    with _PROCESOS_LOCK:
        _PROCESOS_ACTIVOS[proceso.pid] = proceso


def _desregistrar_proceso(proceso):
    with _PROCESOS_LOCK:
        _PROCESOS_ACTIVOS.pop(proceso.pid, None)


def matar_procesos_activos():
    """Termina el árbol de procesos de cada script hijo en ejecución.

    En Windows `taskkill /F /T /PID` elimina también a los descendientes
    (chromedriver y chrome.exe), evitando que queden huérfanos.
    """
    with _PROCESOS_LOCK:
        procesos = list(_PROCESOS_ACTIVOS.values())
    if not procesos:
        return
    print(f"\n⛔ Cerrando {len(procesos)} proceso(s) hijo y sus navegadores...")
    for p in procesos:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                p.kill()
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


def limpiar_navegadores_huerfanos():
    """Mata navegadores headless de Selenium que quedaran huérfanos de corridas
    anteriores interrumpidas.

    Se invoca al arrancar main.py: en ese instante no hay scraping en curso, así
    que cualquier chrome.exe con `--headless`/perfil temporal de WebDriver es
    necesariamente un huérfano. Sin esta limpieza se van acumulando y agotan la
    memoria RAM del equipo.
    """
    if os.name != "nt":
        return 0
    ps = (
        "$hs = Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" "
        "| Where-Object { $_.CommandLine -match '--headless' -or $_.CommandLine -match 'scoped_dir' }; "
        "$n = 0; "
        "foreach ($p in $hs) { taskkill /F /T /PID $p.ProcessId 2>$null | Out-Null; $n++ }; "
        "Write-Output $n"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=90)
        salida = (res.stdout or "").strip()
        return int(salida.splitlines()[-1]) if salida else 0
    except Exception:
        return 0


def mostrar_menu():
    print("\n" + "=" * 60)
    print("  ⚔️  ALETHEIA — Datos Competitivos Valorant VCT 2026")
    print("=" * 60)
    print()
    for key, info in SCRIPTS.items():
        archivos = ", ".join(info["salida"])
        print(f"  [{key}] {info['nombre']}")
        print(f"      → {archivos}")
    print()
    print("  [A] Ejecutar TODOS los scripts  ⚡ (2-6 en paralelo)")
    print("  [Q] Salir")
    print()


def salidas_existen(key):
    """
    Devuelve True si todos los archivos de salida del script ya existen,
    buscando tanto en output_data/ raíz como en sus subcarpetas directas.
    """
    import glob
    info = SCRIPTS[key]
    if not info["salida"]:
        return False  # Sin archivos de salida definidos (ej: script 0) → nunca omitir

    def archivo_existe(nombre):
        # Buscar en raíz
        if os.path.exists(os.path.join(OUTPUT_DIR, nombre)):
            return True
        # Buscar en subcarpetas directas (un nivel)
        patron = os.path.join(OUTPUT_DIR, "*", nombre)
        return bool(glob.glob(patron))

    return all(archivo_existe(archivo) for archivo in info["salida"])


def ejecutar_script(key, omitir_si_existe=False):
    info = SCRIPTS[key]
    ruta = os.path.join(SCRIPTS_DIR, info["archivo"])

    if omitir_si_existe and salidas_existen(key):
        archivos = ", ".join(info["salida"])
        print(f"\n⏭️  Omitiendo '{info['nombre']}' — los archivos ya existen:")
        print(f"   {archivos}")
        return True  # Se considera exitoso (no es un error)

    if not os.path.exists(ruta):
        print(f"  ❌ No se encontró: {ruta}")
        return False

    print(f"\n🚀 Ejecutando: {info['nombre']}...")
    print(f"   Archivo: {info['archivo']}")
    print("-" * 60)

    # Permite que cada script declare variables de entorno propias (ej. la URL
    # base del hub VCT para el catálogo) sin depender de input() interactivo.
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(info.get("env", {}))

    resultado = subprocess.run(
        [sys.executable, ruta],
        cwd=SCRIPTS_DIR,
        env=env,
    )

    if resultado.returncode == 0:
        print(f"\n✅ {info['nombre']} — completado exitosamente")
    else:
        print(f"\n❌ {info['nombre']} — terminó con errores (código {resultado.returncode})")

    return resultado.returncode == 0


def ejecutar_script_paralelo(key, ruta_txt=None, carpeta_evento=None):
    """
    Versión para ejecución paralela: lanza el proceso y captura la salida.
    Si ruta_txt está definida, pasa ALETHEIA_TXT_FILE al subproceso para que
    el script guarde los resultados en la carpeta de ese .txt específico.

    Si carpeta_evento se indica y ya contiene TODOS los archivos de salida de
    este script, se omite: así un evento incompleto se reanuda ejecutando
    únicamente los scripts que faltan.
    """
    info = SCRIPTS[key]
    nombre = info["nombre"]

    if carpeta_evento and info["salida"]:
        faltan = [f for f in info["salida"]
                  if not os.path.exists(os.path.join(carpeta_evento, f))]
        if not faltan:
            return True, f"\n⏭️  [{nombre}] omitido — ya existe en {os.path.basename(carpeta_evento)}"

    archivo = info["archivo"]
    ruta = os.path.join(SCRIPTS_DIR, archivo)

    if not os.path.exists(ruta):
        return False, f"❌ [{nombre}] — archivo no encontrado: {ruta}"

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if ruta_txt:
        env["ALETHEIA_TXT_FILE"] = ruta_txt
    # Si el proceso padre ya instaló chromedriver, pasamos la ruta exacta al hijo
    # para que driver_setup.py la use directamente sin llamar a install().
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    if chromedriver_path:
        env["CHROMEDRIVER_PATH"] = chromedriver_path

    proceso = subprocess.Popen(
        [sys.executable, ruta],
        cwd=SCRIPTS_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    _registrar_proceso(proceso)
    try:
        stdout, stderr = proceso.communicate()
    finally:
        _desregistrar_proceso(proceso)

    separador = "=" * 60
    salida = (
        f"\n{separador}\n"
        f"  {nombre}\n"
        f"{separador}\n"
        f"{stdout}"
    )
    if stderr:
        salida += f"\nSTDERR:\n{stderr}"

    exito = proceso.returncode == 0
    salida += f"\n{'OK' if exito else 'ERROR'} [{nombre}] — {'completado' if exito else f'error (codigo {proceso.returncode})'}"
    return exito, salida


def ejecutar_todos():
    """
    Estrategia de ejecución al elegir [A]:
      1. Script 0 (enlaces) → solo si NO hay .txt en output_data/.
         Si ya existen .txt, se usan directamente.
      2. Script 1 (equipos/jugadores) → secuencial, se omite si ya existe.
      3. Scripts 2-6 → EN PARALELO, se omiten si ya existen.
    """
    import glob
    exitos = 0

    # ── PASO 1: Script 0 solo si no hay .txt ────────────────────────────────
    print("\n" + "=" * 60)
    print("  PASO 1/3 — Verificando archivos de enlaces")
    print("=" * 60)

    archivos_txt = glob.glob(os.path.join(OUTPUT_DIR, "*.txt"))

    if archivos_txt:
        print(f"\n📂 Se encontraron {len(archivos_txt)} archivo(s) .txt:")
        for f in archivos_txt:
            print(f"   ✅ {os.path.basename(f)}")
        print("\n⏭️  Saltando extractor de enlaces (ya existen .txt).")
        exitos += 1  # Se cuenta como éxito
    else:
        print("\n⚠️  No se encontraron archivos .txt en output_data/.")
        print("   Ejecutando extractor de enlaces...")
        if ejecutar_script("0", omitir_si_existe=False):
            exitos += 1

    # ── PASO 2: Catálogo maestro secuencial (prerequisitos) ─────────────────
    print("\n" + "=" * 60)
    print("  PASO 2/3 — Catálogo Maestro (Equipos y Jugadores VLR)")
    print("=" * 60)
    if ejecutar_script("1", omitir_si_existe=True):
        exitos += 1

    # ── PASO 3: Por cada .txt pendiente → 5 scripts en PARALELO ─────────────
    print("\n" + "=" * 60)
    print("  PASO 3/3 — Scraping EN PARALELO (scripts 2, 3, 4, 5, 6)")
    print("  Un lote de 5 scripts por cada evento pendiente")
    print("=" * 60)

    # Determinar qué eventos están pendientes: sin carpeta de salida, o con
    # una carpeta a la que le faltan archivos (scraping interrumpido a medias).
    archivos_txt = glob.glob(os.path.join(OUTPUT_DIR, "*.txt"))
    txt_pendientes_rutas = []
    txt_ya_hechos = []

    for ruta_txt in archivos_txt:
        nombre_base = os.path.splitext(os.path.basename(ruta_txt))[0]
        if nombre_base.startswith("enlaces_"):
            nombre_base = nombre_base[len("enlaces_"):]
        carpeta_esperada = os.path.join(OUTPUT_DIR, nombre_base)

        if not os.path.isdir(carpeta_esperada):
            txt_pendientes_rutas.append(ruta_txt)  # nunca se procesó
            continue

        completa, faltantes = carpeta_evento_completa(nombre_base, carpeta_esperada)
        if completa:
            txt_ya_hechos.append(os.path.basename(ruta_txt))
        else:
            print(f"\n⚠️  {nombre_base}: carpeta incompleta "
                  f"({len(faltantes)} archivo(s) faltante(s)) → se reanudará")
            for f in faltantes:
                print(f"      • {f}")
            txt_pendientes_rutas.append(ruta_txt)

    if txt_ya_hechos:
        print(f"\nYa procesados (carpeta completa):")
        for f in txt_ya_hechos:
            print(f"   OK {f}")

    if not txt_pendientes_rutas:
        print("\nTodos los eventos ya fueron scrapeados. No hay nada que hacer.")
        # No sumamos éxitos aquí, ya que los scripts no se ejecutaron.
        # El conteo de éxitos se basa en ejecuciones reales.
    else:
        # ── Pre-instalar chromedriver UNA SOLA VEZ antes del paralelo ────────
        # Evita el WinError 5: cada subproceso recibirá la ruta ya resuelta
        # vía CHROMEDRIVER_PATH y no llamará a install() por su cuenta.
        print("\n🔧 Pre-instalando ChromeDriver (una sola vez antes del paralelo)...")
        ruta_cd = precalentar_chromedriver()
        if ruta_cd:
            os.environ["CHROMEDRIVER_PATH"] = ruta_cd

        for ruta_txt in txt_pendientes_rutas:
            nombre_evento = os.path.splitext(os.path.basename(ruta_txt))[0]
            if nombre_evento.startswith("enlaces_"):
                nombre_evento = nombre_evento[len("enlaces_"):]

            print(f"\n--- Evento: {nombre_evento} ---")

            carpeta_evento = os.path.join(OUTPUT_DIR, nombre_evento)
            os.makedirs(carpeta_evento, exist_ok=True)

            # Informar qué scripts se ejecutarán realmente (los demás se omiten)
            por_ejecutar = []
            for key in SCRIPTS_PARALELOS:
                info = SCRIPTS[key]
                falta = [f for f in info["salida"]
                         if not os.path.exists(os.path.join(carpeta_evento, f))]
                if falta:
                    por_ejecutar.append(info["nombre"])

            if por_ejecutar:
                print(f"    Se ejecutarán: {', '.join(por_ejecutar)}")
                print("    ⏳ Puede tardar varios minutos (Selenium recorre cada mapa y filtro).")
                print("       El detalle de cada script aparecerá al terminar; latido cada 20s.")
            else:
                print("    Nada que ejecutar: la carpeta ya tiene todos sus archivos.")

            executor = ThreadPoolExecutor(max_workers=MAX_PARALELOS)
            try:
                futures = {}
                for key in SCRIPTS_PARALELOS:
                    future = executor.submit(ejecutar_script_paralelo, key, ruta_txt, carpeta_evento)
                    futures[future] = key

                pendientes = set(futures.keys())
                inicio = time.time()
                while pendientes:
                    hechas, pendientes = wait(pendientes, timeout=20,
                                              return_when=FIRST_COMPLETED)
                    for future in hechas:
                        exito, salida = future.result()
                        if salida:
                            print(salida)
                        if exito:
                            exitos += 1
                    if pendientes:
                        transcurrido = time.time() - inicio
                        nombres = ", ".join(
                            SCRIPTS[futures[f]]["nombre"].split(" (")[0]
                            for f in pendientes)
                        print(f"    ⏳ {transcurrido:4.0f}s — aún ejecutando: {nombres}")
            except KeyboardInterrupt:
                # Matar YA los procesos hijos (y sus Chrome) para que los hilos
                # dejen de bloquearse en communicate(); así no se acumulan
                # navegadores huérfanos ni se agota la RAM.
                matar_procesos_activos()
                raise
            finally:
                executor.shutdown(wait=False)

    print(f"\n{'=' * 60}")
    print(f"Resultado: {exitos}/{len(SCRIPTS)} scripts completados")


def main():
    # Limpieza de seguridad: cierra navegadores de Selenium que hayan quedado
    # huérfanos de ejecuciones anteriores interrumpidas (evita fugas de RAM).
    huerfanos = limpiar_navegadores_huerfanos()
    if huerfanos:
        print(f"🧹 Limpieza inicial: {huerfanos} navegador(es) huérfano(s) cerrado(s).")
    try:
        while True:
            mostrar_menu()
            opcion = input("  Selecciona una opción: ").strip().upper()

            if opcion == "Q":
                print("\n👋 ¡Hasta luego!")
                break
            elif opcion == "A":
                print("\n🔄 Ejecutando todos los scripts...")
                print("   (Los scripts que ya generaron sus archivos serán omitidos)")
                ejecutar_todos()
            elif opcion in SCRIPTS:
                ejecutar_script(opcion)
            else:
                print("  ⚠️ Opción no válida. Intenta de nuevo.")
    except KeyboardInterrupt:
        print("\n\n⛔ Interrupción (Ctrl+C). Cerrando navegadores y procesos hijos...")
        matar_procesos_activos()
        print("👋 ¡Hasta luego!")



if __name__ == "__main__":
    main()