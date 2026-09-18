# ALETHEIA — Documentación Técnica

**Dominio / Fuentes:** [VLR.gg](https://www.vlr.gg)  
**Tipo:** Pipeline ETL y suite de Web Scraping para analítica y datos competitivos de Valorant Champions Tour (VCT)  
**Entorno de ejecución:** Python 3.8+ (Windows / Linux)  
**Almacenamiento / Salida:** Hojas de cálculo Excel (`.xlsx`) estructuradas jerárquicamente y listas de enlaces (`.txt`)  
**Control de versiones:** Git / GitHub (`Leecsito/ALETHEIA_SCRAPPING`)

---

## 1. Stack Tecnológico

| Capa | Tecnología | Propósito |
|------|------------|-----------|
| **Lenguaje base** | Python 3.8+ | Núcleo del pipeline y scripts de scraping |
| **Scraping HTTP / Estático** | `requests` (con headers de navegador) | Descarga rápida de HTML en páginas de partidos de VLR.gg |
| **Parsing HTML / DOM** | `BeautifulSoup4` con backend `lxml` | Extracción, recorrido de selectores CSS y limpieza de texto |
| **Scraping Dinámico / SPA** | `selenium` + `webdriver-manager` | Automatización de Chrome headless para standings/rankings, stats, perfiles y pestañas |
| **Gestión y Compatibilidad WebDriver** | `driver_setup.py` (Selenium + WDM) | Detección automática de binario/versión Chrome/Chromium (resuelve desfase v151 vs v153) y UTF-8 en consola |
| **Motor de Navegador** | Google Chrome / Chromium (Headless) | Renderizado de scripts cliente de VLR.gg (`--disable-blink-features=AutomationControlled`) |
| **Manipulación de Datos (ETL)** | `pandas` | Limpieza, estructuración, transformaciones proporcionales y agregaciones |
| **Persistencia / Exportación** | `openpyxl` | Generación de libros y hojas de cálculo Excel (`.xlsx`) |
| **Concurrencia & Multiproceso** | `concurrent.futures.ThreadPoolExecutor` + `subprocess` | Paralelización por lotes (hasta 5 scripts simultáneos por evento) |
| **Comunicación inter-procesos** | Variables de entorno (`ALETHEIA_TXT_FILE`, `PYTHONIOENCODING`, `CHROMEDRIVER_VERSION`, `CHROME_BINARY_PATH`) | Inyección dinámica de contexto y compatibilidad entre el orquestador y los subprocesos |

---

## 2. Estructura de Directorios

```
ALETHEIA/
│
├── main.py                          # Orquestador principal y CLI interactivo (flujo secuencial / paralelo)
├── DOCUMENTACION.md                 # Documentación técnica central del proyecto
├── requirements.txt                 # Dependencias del proyecto Python
├── README.md                        # Descripción breve y guía inicial de uso
├── .gitignore                       # Reglas de exclusión de Git (ignora output_data/*, venv, pycache, etc.)
│
├── scripts/                         # Módulos y motores especializados de scraping
│   ├── driver_setup.py              # [Helper Central] Detección de versión Chrome/Chromium y creación de WebDriver
│   ├── url_utils.py                 # [Helper] Normalización de URLs de VLR.gg (antepone https://www. si falta)
│   ├── equipos_utils.py             # [Helper] Alias de nombres de equipo (header 'Nombre(Abrev)' vs scoreboard)
│   ├── scrapear_enlaces_evento.py   # [Script 0] Extrae URLs de partidos desde la página del evento en VLR.gg
│   ├── scrapear_equipos_jugadores_franquicia.py # [Script 1] Catálogo de equipos + roster desde standings VCT (franquiciados)
│   ├── scrapear_partidos.py         # [Script 2] Extrae metadatos del partido, fecha, score, veto y parches
│   ├── scrapear_vlr_corregido.py    # [Script 3] Extrae mapas, rondas, resoluciones y pick de mapa vs lado
│   ├── scrapear_stats_pro.py        # [Script 4] Extrae estadísticas por jugador discriminadas por lado (Attack/Defense)
│   ├── scrapear_enfrentamientos.py  # [Script 5] Extrae matrices de enfrentamientos (H2H) y tabla de multikills/clutches
│   └── scrapear_economia.py         # [Script 6] Extrae resumen económico por equipo y economía ronda a ronda
│
└── output_data/                     # Almacenamiento local de datos generados (ignorado en Git)
    ├── .gitkeep                     # Conserva la estructura de la carpeta en clones limpios
    ├── enlaces_<nombre_evento>.txt  # URLs de partidos de un evento específico (ej: enlaces_vct-2026-americas-kickoff.txt)
    ├── vct_equipos.xlsx             # Catálogo maestro global de equipos VLR.gg
    ├── vct_jugadores.xlsx           # Catálogo maestro global de jugadores profesionales VLR.gg
    │
    └── <nombre_evento>/             # Subcarpeta generada por evento (ej: vct-2026-americas-kickoff/)
        ├── vct_partidos.xlsx        # Metadatos generales y vetos de los partidos del evento
        ├── vlr_mapas.xlsx           # Resultados por mapa, duración, picker y rondas por lado
        ├── vlr_rondas.xlsx          # Desglose ronda a ronda de cada mapa (ganador, método, bando)
        ├── vlr_stats_players_sides.xlsx # Rendimiento individual por jugador dividido por Attack/Defense
        ├── vlr_enfrentamientos.xlsx # Matrices de duelo directo (All, FK/FD, Op) entre jugadores rivales
        ├── vlr_multikills_clutches.xlsx # Multikills (2K-5K), Clutches (1v1-1v5), plantas y desactivaciones
        ├── vlr_economia_resumen.xlsx    # Resumen de pistols y compras (eco, semi-eco, semi-buy, full-buy)
        └── vlr_economia_rondas.xlsx     # Banco inicial, gasto, categoría de compra y ganador por ronda
```

---

## 3. Arquitectura del Sistema

### A. Diagrama Global de Flujo y Orquestación

```
                     ┌──────────────────────────────────────────────┐
                     │          CLI / main.py (Orquestador)         │
                     └──────────────────────┬───────────────────────┘
                                            │
           ┌────────────────────────────────┼────────────────────────────────┐
           ▼                                ▼                                ▼
  [Paso 1: Script 0]            [Paso 2: Script 1]                  [Paso 3: Scripts 2-6]
scrapear_enlaces_evento.py    scrapear_equipos_jugadores_franquicia Ejecución en Paralelo
           │                                │                                │
           ▼                                ▼                                ▼
   VLR.gg Event Page               VLR.gg VCT Standings             ThreadPoolExecutor (max=5)
           │                                │                                │
           ▼                                ▼                                ├── Script 2 (Partidos)
  output_data/                      output_data/                             ├── Script 3 (Mapas/Rondas)
  enlaces_<evento>.txt              ├── vct_equipos.xlsx                     ├── Script 4 (Stats Pro)
                                    └── vct_jugadores.xlsx                   ├── Script 5 (H2H / Multikills)
                                                                             └── Script 6 (Economía)
                                                                                     │
                                                                                     ▼
                                                                             output_data/<evento>/
                                                                             (8 archivos Excel)
```

### B. Ciclo de Ejecución Automático (`Opción [A]`)

Al seleccionar `[A]` en `main.py`, el pipeline evalúa el estado del almacenamiento y ejecuta las fases de forma idempotente:

1. **Paso 1 — Detección de Enlaces:**
   - Comprueba si existe algún archivo `.txt` en `output_data/` (**sin importar su nombre**).
   - Si existe, lo reutiliza y salta al paso 2.
   - Si no existe, lanza interactivamente `scrapear_enlaces_evento.py`.
   - Las URLs de cada `.txt` se normalizan con `normalizar_url()` (`scripts/url_utils.py`): `vlr.gg/123`, `www.vlr.gg/123` o `https://www.vlr.gg/123` se convierten siempre a una URL absoluta válida (evita el `MissingSchema` de `requests`).
2. **Paso 2 — Catálogo Maestro (Prerrequisito Secuencial):**
   - Ejecuta `scrapear_equipos_jugadores_franquicia.py` (catálogo de equipos franquiciados + roster actual, en una sola pasada). La URL base del hub VCT se inyecta vía la variable de entorno `ALETHEIA_VCT_URL` (default `https://www.vlr.gg/vct`), por lo que no requiere input interactivo.
   - Si `vct_equipos.xlsx` **y** `vct_jugadores.xlsx` ya existen, la función `salidas_existen()` **omite** el script automáticamente para ahorrar tiempo de cómputo.
3. **Paso 3 — Scraping Concurrente por Lotes de Eventos:**
   - Recorre los archivos `.txt` de `output_data/` (cualquier nombre) y marca como **pendiente** a todo evento cuya carpeta `output_data/<nombre_evento>/` no exista o **no contenga la totalidad de sus archivos de salida** (evento interrumpido a medias). La comprobación (`carpeta_evento_completa()`) es **por evento**, nunca global.
   - Por cada evento pendiente, genera/asegura la subcarpeta `output_data/<nombre_evento>/`.
   - Lanza en paralelo los 5 scripts analíticos (`2`, `3`, `4`, `5`, `6`) usando `ThreadPoolExecutor(max_workers=MAX_PARALELOS)`. Cada script se omite individualmente si su salida ya existe en la carpeta de ese evento, de modo que un evento incompleto **solo re-ejecuta lo que falta**.
   - Inyecta la variable de entorno `ALETHEIA_TXT_FILE` al entorno de cada subproceso para indicarle la ruta exacta del `.txt` sin requerir inputs manuales por consola.
   - **Excepción China:** VLR.gg no publica enfrentamientos (script 5) ni economía (script 6) para esa región. La carpeta de un evento de China se considera completa con solo 4 archivos (`vct_partidos`, `vlr_mapas`, `vlr_rondas`, `vlr_stats_players_sides`); los eventos no-China exigen los 8.
   - **Retroalimentación de progreso:** como la salida de cada subproceso se captura y solo se imprime al finalizar, `main.py` emite un **latido cada 20 s** con el tiempo transcurrido y los scripts aún en ejecución. Antes de lanzar el lote también informa qué scripts se van a ejecutar realmente (el script 5 de enfrentamientos es el más lento: recorre cada mapa y 3 filtros de matriz con esperas de Selenium).

### C. Motor de Estadísticas por Lado (Script 4)

Todas las regiones —incluida **China**— se procesan con un único motor, `scrapear_stats_pro.py`.

> [!NOTE]
> Existió un motor alternativo para China (`scrapear_stats_pro_china.py`) que aplicaba un **split proporcional** de las métricas globales (`mod-both`) usando las rondas de `vlr_mapas.xlsx`. Fue **eliminado**: (1) VLR.gg ya publica los bandos `mod-t` (Attack) y `mod-ct` (Defense) directamente en el tab Overview, por lo que no se requieren cálculos proporcionales, y (2) sus selectores (`table.wf-table-inset`, `td.mod-stat`) ya no existen en el DOM actual de VLR.gg, por lo que devolvía resultados vacíos.
>
> En partidos donde VLR.gg no dispone del detalle por rondas (el nombre del mapa aparece sin duración, ej. `AbyssPICK-`, y `mod-both` solo trae ACS + K/D/A), los bandos `mod-t`/`mod-ct` vienen vacíos. Es una limitación del origen de datos, no del scraping.

---

## 4. Módulos y Scripts en Detalle

### [Módulo Central] `driver_setup.py`
- **Propósito:** Gestor e inicializador centralizado de Selenium WebDriver para todos los scripts del proyecto (`scrapear_*.py`). Resuelve incompatibilidades entre la versión del navegador instalada localmente y la versión de ChromeDriver que descarga `webdriver-manager`.
- **Problema de Compatibilidad Resuelto:**
  - En entornos Windows donde Google Chrome está ausente en las rutas convencionales de `Program Files`, o donde se utiliza una compilación de Chromium (por ejemplo Chromium v151 en `%LOCALAPPDATA%\Chromium\Application\chrome.exe`), invocar `ChromeDriverManager().install()` de forma genérica provoca que se descargue la versión "latest stable" de Google (ej: v153), generando el error fatal:
    `session not created: This version of ChromeDriver only supports Chrome version 153. Current browser version is 151.x`.
- **Race Condition Resuelta (pre-instalación en proceso padre):**
  - Cuando `main.py` lanza los 5 scripts analíticos en paralelo (`ThreadPoolExecutor`), cada subproceso llamaba a `ChromeDriverManager().install()`. Windows bloquea el binario `chromedriver.exe` durante el `os.replace()` interno de WDM al desempaquetar el zip → `[WinError 5] Acceso denegado`. Un `FileLock` externo no es suficiente porque la carrera ocurre **dentro del código de la librería**, no entre nuestras llamadas.
  - **Solución real (dos capas):**
    1. **`main.py` → `precalentar_chromedriver()`:** Antes de lanzar el `ThreadPoolExecutor`, el proceso padre llama a `install()` una sola vez, obtiene la ruta del binario y la fija en `os.environ["CHROMEDRIVER_PATH"]`. Esa variable se hereda en el entorno de cada subproceso vía `env["CHROMEDRIVER_PATH"]` en `ejecutar_script_paralelo()`.
    2. **`driver_setup.py` → `crear_driver()`:** Al iniciar, comprueba si `CHROMEDRIVER_PATH` está definida y apunta a un fichero existente. Si es así, construye `Service(ruta)` directamente, sin llamar jamás a `install()`. Si no (ejecución individual de un script), usa el `FileLock` + `install()` como fallback.

- **Mecanismo de Detección e Inicialización:**
  1. **Búsqueda Jerárquica de Binario:** Inspecciona variables de entorno (`CHROME_BINARY_PATH`), `%LOCALAPPDATA%\Chromium\Application\chrome.exe` y las rutas estándar de `Program Files`.
  2. **Inspección de Versión Mayor:** Ejecuta `(Get-Item "<binario>").VersionInfo.ProductVersion` vía PowerShell para extraer la versión mayor real instalada (ej: `151`).
  3. **Instalación Selectiva (bajo FileLock):** Invoca `ChromeDriverManager(driver_version=version_mayor).install()`, garantizando la descarga o reutilización del ChromeDriver idéntico a la versión del navegador.
  4. **Caché en Memoria:** Cachea la tupla `(version, binary_path)` tras la primera detección para no incurrir en sobrecosto en ejecuciones múltiples.
  5. **Configuración de Consola Windows (UTF-8):** Reconfigura `sys.stdout` y `sys.stderr` a UTF-8 con reemplazo de caracteres no mapeables, evitando fallos por `UnicodeEncodeError` al imprimir emojis informativos (`🚀`, `✅`, `❌`, `⚔️`) en consolas con codificación por defecto CP1252.
- **Variables de Entorno Opcionales:**
  - `CHROMEDRIVER_VERSION`: Fuerza una versión mayor específica (ej: `"151"`).
  - `CHROME_BINARY_PATH`: Fuerza la ruta al ejecutable `chrome.exe`.

### [Script 0] `scrapear_enlaces_evento.py`
- **Propósito:** Descargar todas las URLs de los enfrentamientos asociados a un torneo o fase VCT en VLR.gg.
- **Modos de Operación:**
  - `[1] Todos (all)`: Extrae partidos concluidos, en vivo y futuros (TBD).
  - `[2] Solo completados (completed)`: Filtra exclusivamente los tags que contienen la clase CSS `mod-completed` dentro de `div.match-item-eta`.
- **Salida:** `output_data/enlaces_<slug_evento>[_completed|_all].txt`.

### [Script 1] `scrapear_equipos_jugadores_franquicia.py`
- **Fuente:** Standings de franquicias en VLR.gg (`https://www.vlr.gg/vct/standings`).
- **Mecanismo:**
  1. Recibe la URL base del hub VCT (`ALETHEIA_VCT_URL`, default `https://www.vlr.gg/vct`) y navega a su pestaña `/standings`.
  2. Recorre los grupos `div.eg-standing-group` (uno por región) y extrae los equipos franquiciados: `team_id` nativo desde las URLs `/team/(\d+)/`, `team_name`, `country`, `region` y la URL canónica.
  3. Visita la página de cada equipo para extraer su `tag` (`h2.team-header-tag`) y su roster actual (`div.team-roster-item`): `player_id`, `nickname`, `real_name` y `country`.
  4. Vincula cada jugador a su `team_id`/`team_name`.
- **Alcance:** solo los **48 equipos franquiciados** (12 por región). **No** incluye equipos Challengers/tier-2.
- **Salidas:** `output_data/vct_equipos.xlsx` (Hoja: `Equipos`) y `output_data/vct_jugadores.xlsx` (Hoja: `Jugadores`).

### [Script 2] `scrapear_partidos.py`
- **Fuente:** Páginas de partido en VLR.gg (`/match_id/...`).
- **Mecanismo y Heurísticas:**
  - Extrae `match_id`, nombre del torneo, fase, fecha local/UTC y versión del parche de Valorant (`Patch XX.XX`).
  - **Decodificador de Veto y Selección de Mapas:** Parsea el contenido de `div.match-header-note` (donde se registran picks, bans y deciders).
  - **Resolución de Siglas desde el DOM (`construir_siglas_reales`):** Atribuye cada acción del veto al equipo correcto leyendo las siglas reales que VLR.gg asigna a cada escuadra directamente desde la primera columna del bloque `vlr-rounds` (elementos `div.team` en `vlr-rounds-row-col` col 0), cruzadas con los `div.team-name` del scoreboard. Produce un mapa `{sigla_lower → 'A'|'B'}` (ej: `{'t1': 'A', 'krx': 'B'}`). Mismo patrón que `scrapear_vlr_corregido.py` y `construir_mapa_tags()` en `scrapear_stats_pro.py`. El bloque `vlr-rounds` está presente en el HTML crudo de `requests`, por lo que no requiere Selenium.
  - **Sin atribución a ciegas:** Si una sigla del veto no está en el mapa del DOM, la acción se descarta con advertencia en consola. Anteriormente toda sigla no reconocida caía al equipo A por defecto, lo que corrompía picks/bans (bug detectado en Masters Bangkok 2025, match 449004: la sigla `KRX` de KIWOOM DRX no era derivable del nombre ni estaba en el antiguo `ALIAS_MAP`, y sus 2 picks + 2 bans se asignaron a T1).
- **Salida:** `output_data/<nombre_evento>/vct_partidos.xlsx`.

### [Script 3] `scrapear_vlr_corregido.py`
- **Fuente:** Páginas de partido en VLR.gg (DOM general).
- **Mecanismo y Heurísticas:**
  - Itera cada contenedor `.vm-stats-game` ignorando el contenedor resumen `data-game-id="all"`.
  - **Resolución de Siglas desde el DOM (`construir_siglas_reales`):** Antes de cruzar el veto, lee las siglas reales que VLR.gg asigna a cada equipo directamente desde la primera columna del bloque `vlr-rounds` (elementos `div.team` en `vlr-rounds-row-col` col 0). Esto produce un mapa `{sigla_lower → 'A'|'B'}` (ej: `{'tl': 'A', 'gx': 'B'}`). Mismo patrón que `construir_mapa_tags()` en `scrapear_stats_pro.py`. Resuelve correctamente equipos de una sola palabra en mayúsculas (GIANTX→gx, T1→t1, DRX→drx) que fallan con la heurística de texto.
  - **Detección de Picker y Decider:** Cruza el nombre del mapa con las notas de veto para identificar si fue pick de A, pick de B o mapa Decider (`"remains"`). La sigla del veto se resuelve primero por DOM; si el DOM no produce resultado, se aplica el fallback heurístico (`startswith` + `generar_abbrev`).
  - **Atribución de Selección de Bando:** En la ronda 1, evalúa qué escuadra ganó y el bando asignado (`mod-t` = Attack, `mod-ct` = Defense). Deduce el bando inicial del equipo que **no** pickeó el mapa (quien tiene la potestad de elegir lado).
  - **Compactación de Score por Bando:** Almacena las rondas ganadas en formato `atk/def` (ejemplo: `"7/6"` para el equipo superior y `"6/1"` para el inferior).
  - **Identificación de Resolución de Ronda:** Analiza la imagen de resolución para categorizar la victoria en: `"elim"` (bajas), `"detonation"` (explosión de spike), `"defuse"` (desactivación) o `"time"` (tiempo agotado).
- **Salidas:** `output_data/<nombre_evento>/vlr_mapas.xlsx` y `vlr_rondas.xlsx`.


### [Script 4] `scrapear_stats_pro.py` (Motor Estándar)
- **Fuente:** Páginas de partido en VLR.gg (Tab Overview).
- **Mecanismo:**
  - **Nombre de mapa (`map_id`):** el `div.map` de VLR.gg es `Fracture<span>PICK</span>` + duración, de modo que `get_text()` sin separador produce `FracturePICK58:08`. Se aísla el nombre con separador de espacio y se limpia el sufijo `PICK`, obteniendo `map_id = {match_id}_{map_lower}` (ej. `429379_fracture`), coherente con `vlr_mapas.round_id`.
  - **Alias de equipo:** `construir_mapa_tags()` compara el nombre del scoreboard contra `alias_nombres_equipo()` (ver §6.1) para resolver el `team_id`, soportando el formato `NombreLargo(Abrev)` del header.
  - Utiliza Selenium Headless para simular clics en los selectores de bando:
    - Attack: `div.js-side-filter div[data-side='t']`
    - Defense: `div.js-side-filter div[data-side='ct']`
  - Tras cada clic, actualiza el árbol DOM y extrae las métricas de rendimiento por jugador desde las tablas `.wf-table-inset`.
  - Genera **dos registros independientes por jugador por cada mapa** (`side = "Attack"` y `side = "Defense"`).
- **Salida:** `output_data/<nombre_evento>/vlr_stats_players_sides.xlsx`.

### [Script 5] `scrapear_enfrentamientos.py`
- **Fuente:** Tab de Performance en VLR.gg (`?tab=performance`).
- **Mecanismo:**
  - Carga la pestaña *performance* **una sola vez por partido** y reutiliza el DOM para extraer tanto las matrices como los multikills (antes se recargaba dos veces por partido).
  - Navega por cada mapa activo mediante el menú `.vm-stats-gamesnav-item`.
  - **Matrices Head-to-Head:** Alterna entre los tres filtros de matriz:
    - `"all"` (`data-matrix="normal"`): Duelos totales.
    - `"first"` (`data-matrix="fkfd"`): Primeros duelos (First Kill / First Death).
    - `"op"` (`data-matrix="op"`): Duelos con rifle francotirador Operator.
    - Limpia los tags de equipo (`.team-tag`) y descompone las celdas en formato `"kills_realizadas/kills_recibidas"`.
  - **Multikills y Clutches:** Lee la tabla de estadísticas avanzadas `.mod-adv-stats`, elimina los popups de detalles (`.wf-popable-contents`) y extrae `k2`, `k3`, `k4`, `k5`, clutches `v1` al `v5`, bajas económicas (`econ`), spikes plantadas (`pl`) y desactivadas (`de`).
- **Salidas:** `output_data/<nombre_evento>/vlr_enfrentamientos.xlsx` y `vlr_multikills_clutches.xlsx`.

### [Script 6] `scrapear_economia.py`
- **Fuente:** Tab de Economía en VLR.gg (`?tab=economy`).
- **Mecanismo y Corrección de Regla de Negocio:**
  - **Resolución de Siglas desde el DOM (`construir_tag_map` + `construir_siglas_reales`):** Las siglas que usa la pestaña de economía (ej. `KRX`, `VIT`) no siempre se derivan del nombre del equipo con heurísticas de texto. El script realiza una petición `requests` adicional a la pestaña **overview** del partido (cuyo HTML crudo sí contiene el bloque `vlr-rounds`, ausente en `?tab=economy`) y lee las siglas reales asignadas a cada equipo, produciendo `{sigla_lower → (team_id, team_name)}`. Anteriormente se resolvían desde el texto del veto con `startswith`/`generar_abbrev` + asignación por descarte, lo que dejaba `team_id` vacío cuando ambas siglas fallaban (bug detectado en Masters Bangkok 2025, match 449000: `KRX` para KIWOOM DRX y `VIT` para Team Vitality quedaron sin resolver en los 3 mapas).
  - Extrae las dos tablas económicas por cada mapa:
    1. **Tabla Resumen por Equipo:** Desglosa `pistol_won`, `eco`, `semi_eco`, `semi_buy` y `full_buy`.
       > [!IMPORTANT]
       > **Corrección Crítica de VLR.gg:** En la plataforma VLR.gg, las rondas de pistola son computadas incorrectamente dentro del contador de rondas `eco`. El script corrige esta distorsión deduciendo la ronda de pistola:  
       > `eco_real_j = eco_j - 1`  
       > `eco_real_g = eco_g - pistol_won`
    2. **Tabla de Economía Ronda a Ronda:** Registra el banco inicial (`bank`), el gasto efectuado (`spend`, obtenido del atributo `title` de `.rnd-sq`), la categoría de compra (`category`: `eco`, `semi_eco`, `semi_buy`, `full_buy`) y marca las rondas pistol fijas (`round == 1 or round == 13`).
- **Salidas:** `output_data/<nombre_evento>/vlr_economia_resumen.xlsx` y `vlr_economia_rondas.xlsx`.

---

## 5. Esquema de Datos y Diccionario de Tablas

### Diagrama Entidad-Relación Lógico

```
vct_equipos ◄─────────────── vct_jugadores
(team_id)                   (team_id)

vct_partidos ◄────────────── vlr_mapas (match_id)
(match_id)                   │
                             ├──────► vlr_rondas (round_id = match_id_map)
                             ├──────► vlr_stats_players_sides (map_id = match_id_map)
                             ├──────► vlr_enfrentamientos (map_id = match_id_map)
                             ├──────► vlr_multikills_clutches (map_id = match_id_map)
                             ├──────► vlr_economia_resumen (map_id = match_id_map)
                             └──────► vlr_economia_rondas (map_id = match_id_map)
```

---

### Tabla: `vct_equipos.xlsx` (Hoja: `Equipos`)
Catálogo maestro de **organizaciones franquiciadas** VCT con identificador nativo de VLR.gg (48 equipos, 12 por región).

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `team_id` | INTEGER PK | Identificador numérico real nativo de VLR.gg | `2` |
| `team_name` | TEXT NOT NULL | Nombre oficial de la organización | `Sentinels` |
| `tag` | TEXT | Sigla/abreviatura oficial mostrada por VLR.gg | `SEN` |
| `country` | TEXT | País de bandera del equipo | `United States` |
| `region` | TEXT NOT NULL | Región competitiva (Americas, EMEA, Pacific, China) | `Americas` |
| `url` | TEXT NOT NULL | Enlace canónico al perfil del equipo en VLR.gg | `https://www.vlr.gg/team/2/sentinels` |

---

### Tabla: `vct_jugadores.xlsx` (Hoja: `Jugadores`)
Catálogo del **roster actual** de cada equipo franquiciado, vinculado por su `team_id` nativo de VLR.gg.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `player_id` | INTEGER PK | Identificador numérico real nativo del jugador en VLR.gg | `9` |
| `nickname` | TEXT NOT NULL | Alias o gamertag profesional | `zekken` |
| `real_name` | TEXT | Nombre real del jugador | `Tyson Ngo` |
| `country` | TEXT | País del jugador (código de bandera) | `us` |
| `team_id` | INTEGER FK | Relación directa con `vct_equipos.team_id` | `2` |
| `team_name` | TEXT | Nombre del equipo al que pertenece | `Sentinels` |

---

### Tabla: `vct_partidos.xlsx` (Hoja: `Partidos`)
Metadatos globales del enfrentamiento y resultados de veto.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `match_id` | TEXT PK | Identificador numérico del partido en VLR.gg | `598923` |
| `torneo` | TEXT | Nombre completo de la competición | `Champions Tour 2026 Americas: Kickoff` |
| `fase` | TEXT | Fase o grupo del partido | `Group Stage - Opening (A)` |
| `fecha` | TEXT | Fecha y hora de programación / disputa | `Sat, January 17, 2026` |
| `equipo_a` | TEXT | Nombre de la primera escuadra | `Sentinels` |
| `equipo_b` | TEXT | Nombre de la segunda escuadra | `Cloud9` |
| `score` | TEXT | Marcador global en mapas de la serie | `2-1` |
| `pick_a` | TEXT | Mapas seleccionados por el equipo A | `Abyss` |
| `pick_b` | TEXT | Mapas seleccionados por el equipo B | `Sunset` |
| `ban_a` | TEXT | Mapas vetados/baneados por el equipo A | `Ascent, Bind` |
| `ban_b` | TEXT | Mapas vetados/baneados por el equipo B | `Haven, Lotus` |
| `decider` | TEXT | Mapa decisivo remanente | `Split` |
| `patch` | TEXT | Parche del cliente de Valorant | `Patch 10.01` |

---

### Tabla: `vlr_mapas.xlsx`
Detalle de mapas jugados en la serie, duración y quién seleccionó mapa vs lado.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `match_id` | TEXT FK | Relación con el partido | `598923` |
| `pick_a` | TEXT | Mapa pickeado por A o lado elegido por A | `Abyss` o `Defense` |
| `pick_b` | TEXT | Mapa pickeado por B o lado elegido por B | `Attack` o `Sunset` |
| `side_top_start` | TEXT | Bando inicial del equipo de la fila superior | `attack` o `defense` |
| `score_a` | TEXT | Rondas ganadas por equipo superior (`atk/def`) | `7/6` |
| `score_b` | TEXT | Rondas ganadas por equipo inferior (`atk/def`) | `6/1` |
| `time` | TEXT | Duración total de la partida en formato `MM:SS` | `48:15` |
| `round_id` | TEXT PK | Clave única del mapa (`{match_id}_{map_lower}`) | `598923_abyss` |

---

### Tabla: `vlr_rondas.xlsx`
Historial cronológico de cada ronda disputada.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `round_id` | TEXT FK | Relación con el mapa | `598923_abyss` |
| `num` | INTEGER | Número correlativo de la ronda (1..N) | `1` |
| `win` | INTEGER FK | Identificador numérico del equipo ganador (relación con `vct_equipos.team_id`) | `2` |
| `result` | TEXT | Método de resolución: `elim`, `detonation`, `defuse`, `time` | `elim` |
| `band` | TEXT | Bando que ostentaba el ganador (`attack` / `defense`) | `attack` |

---

### Tabla: `vlr_stats_players_sides.xlsx`
Métricas individuales de rendimiento divididas por bando atacante y defensor.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `match_id` | TEXT FK | ID del partido | `598923` |
| `map_id` | TEXT FK | ID del mapa (`{match_id}_{map_lower}`) | `598923_abyss` |
| `player_name` | TEXT | Nombre / Nick del jugador | `zekken` |
| `team_name` | TEXT | Nombre del equipo | `Sentinels` |
| `side` | TEXT | Bando computado: `Attack` o `Defense` | `Attack` |
| `agent` | TEXT | Agente utilizado en el mapa | `Jett` |
| `rating` | REAL | Calificación de rendimiento VLR | `1.34` |
| `acs` | REAL | Average Combat Score (Puntuación media de combate) | `265.0` |
| `kills` | INTEGER | Bajas totales logradas en este bando | `14` |
| `deaths` | INTEGER | Muertes sufridas en este bando | `9` |
| `assists` | INTEGER | Asistencias registradas | `4` |
| `kast` | REAL | Porcentaje de rondas con Kill, Assist, Survival o Trade | `78.0` |
| `adr` | REAL | Average Damage per Round (Daño promedio por ronda) | `168.5` |
| `hs_percent` | REAL | Porcentaje de disparos a la cabeza | `32.0` |
| `fk` | INTEGER | First Kills (Primeras bajas de la ronda logradas) | `4` |
| `fd` | INTEGER | First Deaths (Primeras muertes de la ronda recibidas) | `1` |

---

### Tabla: `vlr_enfrentamientos.xlsx`
Matriz de duelos 1v1 directos entre integrantes de equipos rivales.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `match_id` | TEXT FK | ID del partido | `598923` |
| `map_id` | TEXT FK | ID del mapa | `598923_abyss` |
| `tipo_kill` | TEXT | Tipo de enfrentamiento: `all` (general), `first` (FK/FD), `op` (Operator) | `all` |
| `player_a` | TEXT | Jugador de la fila evaluado (atacante/sujeto) | `zekken` |
| `player_b` | TEXT | Jugador rival de la columna (oponente) | `OXY` |
| `kills` | TEXT | Enfrentamiento en formato `logradas/recibidas` | `3/1` |

---

### Tabla: `vlr_multikills_clutches.xlsx`
Rondas especiales, multikills, situaciones de clutch y acciones de objetivo.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `match_id` | TEXT FK | ID del partido | `598923` |
| `map_id` | TEXT FK | ID del mapa | `598923_abyss` |
| `player_name` | TEXT | Nombre del jugador | `zekken` |
| `agent` | TEXT | Agente jugado | `Jett` |
| `k2` | INTEGER | Rondas con 2 bajas (Double Kill) | `4` |
| `k3` | INTEGER | Rondas con 3 bajas (Triple Kill) | `2` |
| `k4` | INTEGER | Rondas con 4 bajas (Quadra Kill) | `0` |
| `k5` | INTEGER | Rondas con 5 bajas (Ace) | `1` |
| `v1` | INTEGER | Clutches 1v1 ganados | `1` |
| `v2` | INTEGER | Clutches 1v2 ganados | `0` |
| `v3` | INTEGER | Clutches 1v3 ganados | `0` |
| `v4` | INTEGER | Clutches 1v4 ganados | `0` |
| `v5` | INTEGER | Clutches 1v5 ganados | `0` |
| `econ` | INTEGER | Bajas con desventaja de armamento (Eco Kills) | `2` |
| `pl` | INTEGER | Número de spikes plantadas | `3` |
| `de` | INTEGER | Número de spikes desactivadas | `1` |

---

### Tabla: `vlr_economia_resumen.xlsx`
Resumen de compra y efectividad por niveles de gasto de cada escuadra.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `match_id` | TEXT FK | ID del partido | `598923` |
| `map_id` | TEXT FK | ID del mapa | `598923_abyss` |
| `team` | TEXT | Nombre del equipo | `Sentinels` |
| `pistol_won` | INTEGER | Rondas de pistola ganadas (0, 1 o 2) | `2` |
| `eco` | TEXT | Rondas eco puras (sin pistols) en formato `jugadas(ganadas)` | `2(1)` |
| `semi_eco` | TEXT | Rondas semi-eco en formato `jugadas(ganadas)` | `1(0)` |
| `semi_buy` | TEXT | Rondas semi-buy en formato `jugadas(ganadas)` | `4(2)` |
| `full_buy` | TEXT | Rondas full-buy en formato `jugadas(ganadas)` | `15(10)` |

---

### Tabla: `vlr_economia_rondas.xlsx`
Economía transaccional ronda por ronda.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `match_id` | TEXT FK | ID del partido | `598923` |
| `map_id` | TEXT FK | ID del mapa | `598923_abyss` |
| `round` | INTEGER | Número de ronda | `3` |
| `is_pistol` | INTEGER | Bandera indicadora de ronda pistol (`1` si ronda es 1 o 13, `0` si no) | `0` |
| `team_top` | TEXT | Nombre del equipo superior | `Sentinels` |
| `bank_top` | INTEGER | Créditos acumulados en banco de team_top antes de comprar | `8700` |
| `spend_top` | INTEGER | Créditos gastados en la ronda por team_top | `19500` |
| `category_top`| TEXT | Categoría de inversión de team_top (`eco`, `semi_eco`, `semi_buy`, `full_buy`) | `full_buy` |
| `team_bot` | TEXT | Nombre del equipo inferior | `Cloud9` |
| `bank_bot` | INTEGER | Créditos en banco de team_bot antes de comprar | `1400` |
| `spend_bot` | INTEGER | Créditos gastados por team_bot | `2100` |
| `category_bot`| TEXT | Categoría de inversión de team_bot | `eco` |
| `winner` | TEXT | Escuadra ganadora de la ronda | `Sentinels` |

---

## 6. Particularidades, Heurísticas y Reglas de Negocio

1. **Desambiguación de Siglas y Nombres de Equipo:**  
   En los vetos (`match-header-note`) y en las tablas de economía, los equipos se expresan por siglas no estandarizadas (`C9`, `100T`, `SEN`, `KRX`, `VIT`) que no siempre son derivables del nombre completo (ej. VLR.gg usa `KRX` para KIWOOM DRX por motivos de sponsor). Los scripts 2, 3 y 6 resuelven las siglas **leyéndolas directamente del DOM** (primera columna del bloque `vlr-rounds`, cruzada con los `div.team-name` del scoreboard) mediante variantes de `construir_siglas_reales()`, en lugar de heurísticas de texto frágiles. Si una sigla no puede resolverse, la acción se descarta con advertencia en consola: el sistema nunca atribuye a ciegas (históricamente, toda sigla no reconocida caía al equipo A por defecto).
   - **Alias de nombre header/scoreboard (`equipos_utils.alias_nombres_equipo`):** cuando un equipo tiene patrocinador, VLR.gg muestra en el header `NombreLargo(Abrev)` (ej. `Movistar KOI(KOI)`, `JD Mall JDG Esports(JD Gaming)`), pero en el scoreboard usa solo una parte (ej. `KOI`, `JD Gaming`). Comparar por igualdad estricta hacía fallar el mapeo tag→`team_id` (dejaba `team_id` vacío en stats/economía y producía `pick_a="Unknown"`/`side_chosen` vacío en mapas). Ahora los scripts 3, 4 y 6 comparan el nombre del scoreboard contra el conjunto de alias derivado del header.
2. **Corrección de Pistolas en la Economía de VLR.gg:**  
   VLR.gg agrupa las rondas de pistolas (rondas 1 y 13) dentro del contador de compras `eco`. El script `scrapear_economia.py` resta de forma obligatoria 1 ronda jugada y la victoria correspondiente de la categoría Eco, evitando sesgar los análisis tácticos con rondas de compra forzada obligatoria.
3. **Manejo de Tiempos y Esperas Dinámicas en Selenium:**  
   Dado que las tablas de estadísticas avanzadas y matrices se inyectan en el DOM cliente mediante eventos JavaScript, los scripts emplean `WebDriverWait` en conjunción con ejecución de clicks nativos con script (`driver.execute_script("arguments[0].click();", elemento)`), garantizando que los elementos no queden tapados por headers flotantes o banners de VLR.gg.
4. **Optimización de Tiempos (esperas a condición en lugar de `time.sleep` fijos):**  
   Los scripts per-evento (`4`, `5`, `6`) ya no usan `time.sleep()` fijos tras cargar una página o hacer clic: esperan de forma **best-effort** con `WebDriverWait` a una condición concreta (p. ej. `.vm-stats-game`, `table.mod-econ`, `div.ovw-row`) y, si el timeout expira, continúan igualmente, de modo que un fallo puntual nunca provoca pérdida de datos. Esto **no incrementa el número de peticiones** a VLR.gg (no agrava el riesgo de bloqueo de Cloudflare) y elimina el tiempo muerto. Adicionalmente, `scrapear_enfrentamientos.py` carga la pestaña *performance* **una sola vez por partido** y la reutiliza en los dos pases (matrices y multikills), **reduciendo a la mitad sus peticiones**.
5. **Idempotencia y Resiliencia en Ejecuciones por Lotes:**  
   La ejecución `[A]` determina la pendencia **por evento**: `carpeta_evento_completa()` compara los archivos presentes en `output_data/<evento>/` contra `archivos_esperados_evento()` (8 para eventos no-China, 4 para China) y marca como pendiente cualquier carpeta incompleta. Además, `ejecutar_script_paralelo()` omite cada script cuya salida ya exista en la carpeta del evento. Resultado: se puede cancelar y reanudar el maestro en cualquier punto, sin omitir eventos a medio terminar y sin re-scrapear lo ya completado. (El catálogo maestro global —script 1— sigue usando `salidas_existen()`.)
6. **Gestión de Procesos Hijos y Prevención de Navegadores Huérfanos:**  
   Cada script analítico abre su propio Chrome headless. Al interrumpir con `Ctrl+C`, `subprocess.run()` mata solo al hijo Python, **no** a sus descendientes (`chromedriver` y `chrome.exe`), que quedarían huérfanos; acumulados entre corridas agotan la RAM del equipo (llegó a observarse 142 procesos `chrome.exe` y ~300 MB libres de 7,4 GB). `main.py` lo evita con dos capas: (1) registra cada subproceso con `Popen` y, ante `KeyboardInterrupt`, ejecuta `matar_procesos_activos()` (`taskkill /F /T /PID`) para terminar el **árbol completo** de procesos; (2) al arrancar, `limpiar_navegadores_huerfanos()` cierra cualquier Chrome headless de Selenium remanente de corridas anteriores (en el arranque no hay scraping activo, por lo que esos procesos son necesariamente huérfanos). El grado de concurrencia se controla con la constante `MAX_PARALELOS` (por defecto 5; conviene reducirlo en equipos con poca RAM, ya que cada script abre un Chrome).

---

## 7. Instalación y Guía de Uso

### A. Preparación del Entorno

```bash
# 1. Clonar el repositorio y acceder a la carpeta
git clone https://github.com/Leecsito/ALETHEIA_SCRAPPING.git
cd ALETHEIA

# 2. Crear entorno virtual en Windows
python -m venv venv
.\venv\Scripts\activate

# 3. Instalar librerías requeridas
pip install -r requirements.txt
```

> **Requisito del Sistema:** Google Chrome o Chromium instalado en el sistema operativo. ALETHEIA incluye detección automática en `scripts/driver_setup.py`, el cual localiza el ejecutable (en `Program Files` o `%LOCALAPPDATA%\Chromium`), consulta su versión real (`ProductVersion`) e instala la versión exacta compatible de ChromeDriver mediante `webdriver-manager`, permitiendo también anulación manual vía variables de entorno (`CHROMEDRIVER_VERSION`, `CHROME_BINARY_PATH`).

### B. Ejecución Interactiva

```bash
# Iniciar consola interactiva
python main.py
```

Menú disponible:
- `[0]`: Extractor de enlaces de evento (solicita URL de torneo en VLR.gg y genera el `.txt`).
- `[1]`: Equipos y jugadores VCT (descarga el catálogo de equipos franquiciados y su roster actual desde VLR.gg con `team_id`/`player_id` nativos).
- `[2] - [6]`: Ejecutar un script analítico específico de manera individual sobre un archivo `.txt`.
- `[A]`: **Ejecución total en paralelo.** Procesa todos los torneos pendientes con 5 hilos simultáneos.
- `[Q]`: Salir del programa.

---

## 8. Deuda Técnica y Buenas Prácticas

1. **Archivos Temporales Residuales de Excel:**  
   Se detectó la presencia ocasional de archivos de bloqueo de Microsoft Office (ej: `~$vlr_mapas.xlsx`). Ya se incluyó la regla `~$*.xlsx` en `.gitignore` para evitar su rastreo.
2. **Estandarización de Identificadores de Mapa:**  
   En `vlr_mapas.xlsx` y `vlr_rondas.xlsx` la columna clave se denomina `round_id`, mientras que en `vlr_stats_players_sides.xlsx`, `vlr_enfrentamientos.xlsx`, etc., se denomina `map_id`. Aunque su contenido es idéntico (`{match_id}_{map}`), unificar el nombre de columna facilitará futuras migraciones SQL.
3. **Respaldo / Migración a Base de Datos Relacional:**  
   Actualmente los datos residen en libros Excel aislados por evento. Se proyecta un script consolidador ETL para transferir todos los archivos `.xlsx` hacia una base de datos relacional (SQLite / PostgreSQL / Turso DB) para facilitar consultas SQL y analítica unificada.

---

## ⚠️ DIRECTIVA OBLIGATORIA DE MANTENIMIENTO DE DOCUMENTACIÓN

> [!IMPORTANT]
> **REGLA PERMANENTE DEL PROYECTO:**
> 
> **Actualización obligatoria por cambios:** Cada vez que se realice cualquier modificación, refactorización o ampliación en el proyecto (por ejemplo: cambios en la lógica de scraping o predicción, adición de nuevas funciones/consultas, nuevos scripts en `scripts/`, reorganización de archivos/carpetas o cambios en la estructura de datos/Excel), es **estrictamente obligatorio actualizar o incrementar este archivo `DOCUMENTACION.md`**. Ningún cambio de código o arquitectura se considerará finalizado sin haber reflejado sus nuevos conceptos, funciones, esquemas o parámetros dentro de esta documentación.
> 
> **Corrección oportunista de inconsistencias:** Si durante la implementación de un cambio te encuentras con explicaciones confusas, desactualizadas o incorrectas en la documentación directamente relacionada con lo que estás tocando, corrígelas en ese mismo momento. No realices revisiones ni auditorías completas de todo el archivo para evitar consumo innecesario de tokens; únicamente subsana los errores puntuales que encuentres al paso.
> 
> *"Con la idea de que la IA no tenga que revisar todo el proyecto, sino solo la documentación."*
