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
| **Scraping Dinámico / SPA** | `selenium` + `webdriver-manager` | Automatización de Chrome headless para rankings, stats, perfiles y pestañas |
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
│   ├── scrapear_enlaces_evento.py   # [Script 0] Extrae URLs de partidos desde la página del evento en VLR.gg
│   ├── scrapear_equipos.py          # [Script 1] Extrae catálogo de equipos desde rankings VLR.gg (team_id nativo)
│   ├── scrapear_partidos.py         # [Script 2] Extrae metadatos del partido, fecha, score, veto y parches
│   ├── scrapear_vlr_corregido.py    # [Script 3] Extrae mapas, rondas, resoluciones y pick de mapa vs lado
│   ├── scrapear_stats_pro.py        # [Script 4] Extrae estadísticas por jugador discriminadas por lado (Attack/Defense)
│   ├── scrapear_stats_pro_china.py  # [Script 4 - China] Motor alternativo: split proporcional para eventos de China
│   ├── scrapear_enfrentamientos.py  # [Script 5] Extrae matrices de enfrentamientos (H2H) y tabla de multikills/clutches
│   ├── scrapear_economia.py         # [Script 6] Extrae resumen económico por equipo y economía ronda a ronda
│   └── scrapear_jugadores.py        # [Script 7] Extrae catálogo de jugadores activos y equipo actual desde VLR.gg
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
  [Paso 1: Script 0]            [Paso 2: Scripts 1 & 7]             [Paso 3: Scripts 2-6]
scrapear_enlaces_evento.py    scrapear_equipos / scrapear_jugadores Ejecución en Paralelo
           │                                │                                │
           ▼                                ▼                                ▼
   VLR.gg Event Page               VLR.gg Rankings & Stats          ThreadPoolExecutor (max=5)
           │                                │                                │
           ▼                                ▼                                ├── Script 2 (Partidos)
  output_data/                      output_data/                             ├── Script 3 (Mapas/Rondas)
  enlaces_<evento>.txt              ├── vct_equipos.xlsx                     ├── Script 4 (Stats Pro / China)
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
   - Comprueba si existen archivos `enlaces_*.txt` en `output_data/`.
   - Si existen, los reutiliza y salta al paso 2.
   - Si no existen, lanza interactivamente `scrapear_enlaces_evento.py`.
2. **Paso 2 — Catálogo Maestro (Prerrequisitos Secuenciales):**
   - Ejecuta `scrapear_equipos.py` y `scrapear_jugadores.py`.
   - Si `vct_equipos.xlsx` o `vct_jugadores.xlsx` ya existen, la función `salidas_existen()` **omite** el script correspondiente automáticamente para ahorrar tiempo de cómputo.
3. **Paso 3 — Scraping Concurrente por Lotes de Eventos:**
   - Detecta qué archivos `.txt` en `output_data/` aún **no tienen su subcarpeta correspondiente**.
   - Por cada evento pendiente, genera la subcarpeta `output_data/<nombre_evento>/`.
   - Lanza en paralelo los 5 scripts analíticos (`2`, `3`, `4`, `5`, `6`) usando `ThreadPoolExecutor(max_workers=5)`.
   - Inyecta la variable de entorno `ALETHEIA_TXT_FILE` al entorno de cada subproceso para indicarle la ruta exacta del `.txt` sin requerir inputs manuales por consola.

### C. Selección Dinámica del Motor de Estadísticas (Script 4)

VLR.gg presenta una inconsistencia estructural en las páginas de partidos de la región **China**: los botones y spans correspondientes a los bandos individuales `mod-t` (Attack) y `mod-ct` (Defense) están vacíos en el DOM original, lo que ocasiona que el motor normal (`scrapear_stats_pro.py`) extraiga todas las estadísticas en ceros.

`main.py` incorpora una regla heurística:
```python
if key == "4" and ruta_txt and "china" in os.path.basename(ruta_txt).lower():
    archivo = "scrapear_stats_pro_china.py"
```
Cuando detecta la palabra `china` en el nombre del `.txt`, conmuta la ejecución a `scrapear_stats_pro_china.py`, el cual lee las estadísticas globales del mapa (`mod-both`) y realiza un **split proporcional ponderado** a partir de las rondas reales jugadas extraídas previamente por el Script 3 en `vlr_mapas.xlsx`.

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

### [Script 1] `scrapear_equipos.py`
- **Fuente:** Rankings regionales oficiales en VLR.gg (`https://www.vlr.gg/rankings/{slug}`).
- **Mecanismo:**
  1. Recorre las 13 divisiones y regiones (`north-america`, `europe`, `brazil`, `asia-pacific`, `korea`, `china`, `japan`, `la-s`, `la-n`, `oceania`, `mena`, `gc`, `collegiate`).
  2. Extrae el `team_id` numérico nativo de VLR.gg desde las URLs `/team/(\d+)/`, garantizando compatibilidad directa con las demás tablas de partidos y estadísticas.
  3. Extrae `team_name`, `region`, `country` y la URL canónica del equipo en VLR.gg.
  4. Deduplica por `team_id` conservando el primer registro encontrado.
- **Salida:** `output_data/vct_equipos.xlsx` (Hoja: `Equipos`).

### [Script 2] `scrapear_partidos.py`
- **Fuente:** Páginas de partido en VLR.gg (`/match_id/...`).
- **Mecanismo y Heurísticas:**
  - Extrae `match_id`, nombre del torneo, fase, fecha local/UTC y versión del parche de Valorant (`Patch XX.XX`).
  - **Decodificador de Veto y Selección de Mapas:** Parsea el contenido de `div.match-header-note` (donde se registran picks, bans y deciders).
  - **Mapeo de Siglas (`ALIAS_MAP`):** Resuelve abreviaturas competitivas de equipos en las 4 regiones (ej: `SEN` → Sentinels, `100T` → 100 Thieves, `EDG` → EDward Gaming, `PRX` → Paper Rex) para atribuir inequívocamente qué equipo ejecutó cada ban o pick.
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
  - Utiliza Selenium Headless para simular clics en los selectores de bando:
    - Attack: `div.js-side-filter div[data-side='t']`
    - Defense: `div.js-side-filter div[data-side='ct']`
  - Tras cada clic, actualiza el árbol DOM y extrae las métricas de rendimiento por jugador desde las tablas `.wf-table-inset`.
  - Genera **dos registros independientes por jugador por cada mapa** (`side = "Attack"` y `side = "Defense"`).
- **Salida:** `output_data/<nombre_evento>/vlr_stats_players_sides.xlsx`.

### [Script 4 - Alternativo] `scrapear_stats_pro_china.py` (Motor Región China)
- **Fuente:** Páginas de partido en VLR.gg + `output_data/<nombre_evento>/vlr_mapas.xlsx`.
- **Mecanismo:**
  - Extrae las métricas globales del mapa desde el selector `mod-both` (pestaña ALL), disponible sin fallas en los partidos chinos.
  - Carga el archivo generado previamente `vlr_mapas.xlsx` para conocer `score_a` y `score_b`.
  - **Fórmula de Rondas Reales Jugadas:**
    $$\text{atk\_played}_{\text{top}} = \text{sa\_atk} + \text{sb\_def}$$
    $$\text{def\_played}_{\text{top}} = \text{sa\_def} + \text{sb\_atk}$$
  - **División Proporcional de Métricas:**
    - Métricas acumulativas enteras (`kills`, `deaths`, `assists`, `fk`, `fd`) se ponderan por la fracción de rondas disputadas en cada bando:
      $$\text{val\_atk} = \text{round}\left(\text{total} \times \frac{\text{atk\_r}}{\text{atk\_r} + \text{def\_r}}\right),\quad \text{val\_def} = \text{total} - \text{val\_atk}$$
    - Métricas de ratio o promedio (`rating`, `acs`, `adr`, `kast`, `hs_percent`) se mantienen iguales en ambos lados por tratarse de valores medios del mapa completo.
- **Salida:** `output_data/<nombre_evento>/vlr_stats_players_sides.xlsx`.

### [Script 5] `scrapear_enfrentamientos.py`
- **Fuente:** Tab de Performance en VLR.gg (`?tab=performance`).
- **Mecanismo:**
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
  - Extrae las dos tablas económicas por cada mapa:
    1. **Tabla Resumen por Equipo:** Desglosa `pistol_won`, `eco`, `semi_eco`, `semi_buy` y `full_buy`.
       > [!IMPORTANT]
       > **Corrección Crítica de VLR.gg:** En la plataforma VLR.gg, las rondas de pistola son computadas incorrectamente dentro del contador de rondas `eco`. El script corrige esta distorsión deduciendo la ronda de pistola:  
       > `eco_real_j = eco_j - 1`  
       > `eco_real_g = eco_g - pistol_won`
    2. **Tabla de Economía Ronda a Ronda:** Registra el banco inicial (`bank`), el gasto efectuado (`spend`, obtenido del atributo `title` de `.rnd-sq`), la categoría de compra (`category`: `eco`, `semi_eco`, `semi_buy`, `full_buy`) y marca las rondas pistol fijas (`round == 1 or round == 13`).
- **Salidas:** `output_data/<nombre_evento>/vlr_economia_resumen.xlsx` y `vlr_economia_rondas.xlsx`.

### [Script 7] `scrapear_jugadores.py`
- **Fuente:** VLR.gg (`/stats/` de ligas VCT y perfiles de jugador `/player/{id}/`).
- **Mecanismo:**
  1. Recorre de forma paginada las estadísticas globales de las 4 regiones principales (`americas`, `emea`, `pacific`, `china`).
  2. Extrae el `player_id` numérico nativo de VLR.gg y el `nickname` de cada jugador.
  3. Visita de manera individual el perfil de cada jugador único para inspeccionar la sección *"Current Teams"* (`wf-card`).
  4. Obtiene el `team_id` real y el `team_name` de su equipo activo actual (o `None` si es agente libre / inactivo).
- **Salida:** `output_data/vct_jugadores.xlsx` (Hoja: `Jugadores`).

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
Catálogo maestro de organizaciones con identificador nativo de VLR.gg.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `team_id` | INTEGER PK | Identificador numérico real nativo de VLR.gg | `2` |
| `team_name` | TEXT NOT NULL | Nombre oficial de la organización | `Sentinels` |
| `region` | TEXT NOT NULL | Región competitiva VLR (`North America`, `Europe`, etc.) | `North America` |
| `country` | TEXT | País de bandera del equipo | `United States` |
| `url` | TEXT NOT NULL | Enlace canónico al perfil del equipo en VLR.gg | `https://www.vlr.gg/team/2/sentinels` |

---

### Tabla: `vct_jugadores.xlsx` (Hoja: `Jugadores`)
Catálogo de jugadores competitivos activos vinculados por su `team_id` nativo de VLR.gg.

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `player_id` | INTEGER PK | Identificador numérico real nativo del jugador en VLR.gg | `9` |
| `nickname` | TEXT NOT NULL | Alias o gamertag profesional | `zekken` |
| `team_id` | INTEGER FK | Relación directa con `vct_equipos.team_id` | `2` |
| `team_name` | TEXT | Nombre del equipo activo en su perfil de VLR.gg | `Sentinels` |

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
   En los vetos (`match-header-note`), los equipos suelen expresarse por siglas no estandarizadas (`C9`, `100T`, `SEN`, `FPX`, `EDG`). El sistema utiliza una doble estrategia:
   - Coincidencia con diccionario explícito `ALIAS_MAP`.
   - Generación algorítmica de acrónimos (`generar_abbrev`) combinando letras mayúsculas y dígitos para nombres complejos (ej. `100 Thieves` $\rightarrow$ `100t`).
2. **Corrección de Pistolas en la Economía de VLR.gg:**  
   VLR.gg agrupa las rondas de pistolas (rondas 1 y 13) dentro del contador de compras `eco`. El script `scrapear_economia.py` resta de forma obligatoria 1 ronda jugada y la victoria correspondiente de la categoría Eco, evitando sesgar los análisis tácticos con rondas de compra forzada obligatoria.
3. **Manejo de Tiempos y Esperas Dinámicas en Selenium:**  
   Dado que las tablas de estadísticas avanzadas y matrices se inyectan en el DOM cliente mediante eventos JavaScript, los scripts emplean `WebDriverWait` en conjunción con ejecución de clicks nativos con script (`driver.execute_script("arguments[0].click();", elemento)`), garantizando que los elementos no queden tapados por headers flotantes o banners de VLR.gg.
4. **Idempotencia y Resiliencia en Ejecuciones por Lotes:**  
   El verificador `salidas_existen()` examina tanto la raíz de `output_data/` como sus subdirectorios con patrones glob (`output_data/*/archivo.xlsx`). Esto permite cancelar o reanudar el script maestro en cualquier momento sin riesgo de sobrescribir eventos concluidos ni duplicar solicitudes HTTP.

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
- `[1]`: Equipos VCT (descarga catálogo maestro de equipos desde VLR.gg con `team_id` nativo).
- `[2] - [6]`: Ejecutar un script analítico específico de manera individual sobre un archivo `.txt`.
- `[7]`: Jugadores VCT (descarga catálogo maestro de jugadores y equipo actual desde VLR.gg con `player_id` y `team_id` nativos).
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
