r"""
ALETHEIA - Configuración y creación centralizada de Selenium WebDriver
---------------------------------------------------------------------
Detecta automáticamente la versión y ruta de Chrome o Chromium instalados en el sistema
(incluyendo builds de Chromium en %LOCALAPPDATA%\\Chromium), garantizando que
ChromeDriverManager descargue e instale la versión exacta de ChromeDriver compatible.

FileLock: cuando main.py lanza los scripts en paralelo (ThreadPoolExecutor), cada
subproceso llama a ChromeDriverManager().install(). Windows bloquea el binario
mientras un proceso lo renombra → WinError 5. El FileLock garantiza que solo un
proceso a la vez ejecuta install(); los demás esperan y reutilizan la caché.
"""

import os
import sys
import re
import subprocess
from filelock import FileLock
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Asegurar codificación UTF-8 en consolas Windows (evita UnicodeEncodeError con emojis)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_CACHED_VERSION = None
_CACHED_BINARY = None
_CACHE_INITIALIZED = False


def detectar_chrome_version_y_binario():
    r"""
    Detecta la versión mayor y el ejecutable de Chrome o Chromium en Windows.
    Permite anulación manual mediante variables de entorno:
      - CHROMEDRIVER_VERSION (ej: "151")
      - CHROME_BINARY_PATH (ej: "C:\...\chrome.exe")
    """
    global _CACHED_VERSION, _CACHED_BINARY, _CACHE_INITIALIZED
    if _CACHE_INITIALIZED:
        return _CACHED_VERSION, _CACHED_BINARY

    env_ver = os.environ.get("CHROMEDRIVER_VERSION")
    env_bin = os.environ.get("CHROME_BINARY_PATH")

    if env_ver and env_bin and os.path.exists(env_bin):
        _CACHED_VERSION, _CACHED_BINARY = env_ver, env_bin
        _CACHE_INITIALIZED = True
        return _CACHED_VERSION, _CACHED_BINARY

    candidatos = [
        env_bin,
        os.path.expandvars(r"%LOCALAPPDATA%\Chromium\Application\chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
    ]

    binario_encontrado = None
    version_mayor = env_ver

    for ruta in candidatos:
        if ruta and os.path.exists(ruta):
            binario_encontrado = ruta
            if not version_mayor:
                try:
                    cmd = f'(Get-Item "{ruta}").VersionInfo.ProductVersion'
                    res = subprocess.check_output(
                        ["powershell", "-NoProfile", "-Command", cmd],
                        text=True,
                        stderr=subprocess.DEVNULL,
                        timeout=5
                    ).strip()
                    m = re.search(r'^(\d+)', res)
                    if m:
                        version_mayor = m.group(1)
                except Exception:
                    pass
            break

    _CACHED_VERSION = version_mayor
    _CACHED_BINARY = binario_encontrado
    _CACHE_INITIALIZED = True
    return version_mayor, binario_encontrado


def crear_driver(headless=True, start_maximized=True):
    """
    Crea e inicializa una instancia de Selenium WebDriver compatible con la versión de Chrome/Chromium.

    FileLock sobre install(): evita el WinError 5 cuando main.py lanza varios scripts en
    paralelo y todos intentan descargar/renombrar chromedriver.exe al mismo tiempo.
    Solo la llamada a install() está serializada; la creación del WebDriver corre libre.
    """
    options = Options()
    if headless:
        options.add_argument("--headless")
    if start_maximized:
        options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    version_mayor, binario = detectar_chrome_version_y_binario()

    if binario:
        options.binary_location = binario

    # Ruta del archivo de lock: dentro del directorio de caché de WDM (~/.wdm)
    lock_path = os.path.join(os.path.expanduser("~"), ".wdm", "aletheia_driver.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)

    # Si main.py ya corrió precalentar_chromedriver() e inyectó la ruta, la
    # usamos directamente sin llamar a install(). Esto elimina la carrera de
    # archivos (WinError 5) cuando 5 subprocesos paralelos compiten por
    # descargar/renombrar el mismo chromedriver.exe.
    preinstalado = os.environ.get("CHROMEDRIVER_PATH")
    if preinstalado and os.path.isfile(preinstalado):
        driver_path = preinstalado
    else:
        with FileLock(lock_path, timeout=120):
            if version_mayor:
                driver_path = ChromeDriverManager(driver_version=version_mayor).install()
            else:
                driver_path = ChromeDriverManager().install()

    service = Service(driver_path)
    return webdriver.Chrome(service=service, options=options)

