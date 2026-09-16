# ⚔️ ALETHEIA

Herramienta de scraping y pipeline ETL para datos competitivos de **Valorant Champions Tour (VCT)**.

Extrae automáticamente equipos, jugadores, partidos, estadísticas por mapa/lado, enfrentamientos directos, multikills, clutches y economía desde **Liquipedia** y **VLR.gg**.

> 📖 **Documentación Técnica Completa:** Consulta [DOCUMENTACION.md](DOCUMENTACION.md) para conocer la arquitectura profunda, diccionarios de datos, esquemas de tablas Excel, motores de scraping y la directiva obligatoria de mantenimiento.

## 📂 Estructura

```
ALETHEIA/
├── main.py                          # Menú principal y orquestador CLI
├── DOCUMENTACION.md                 # Documentación técnica exhaustiva del sistema
├── scripts/
│   ├── scrapear_enlaces_evento.py   # Extractor de URLs de partidos
│   ├── scrapear_equipos.py          # Catálogo de equipos (VLR.gg)
│   ├── scrapear_jugadores.py        # Catálogo de jugadores (VLR.gg)
│   ├── scrapear_partidos.py         # Partidos VCT (VLR.gg)
│   ├── scrapear_vlr_corregido.py    # Mapas y rondas
│   ├── scrapear_stats_pro.py        # Stats por lado ATK/DEF
│   ├── scrapear_enfrentamientos.py  # Enfrentamientos y multikills
│   └── scrapear_economia.py         # Economía por ronda y resumen
├── output_data/                     # Archivos Excel generados
├── requirements.txt
└── README.md
```

## 🚀 Instalación

```bash
# Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate        # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## ▶️ Uso

```bash
# Menú interactivo
python main.py

# Ejecutar un script individual
python scripts/scrapear_equipos.py
```

## 📊 Archivos de salida

Todos los archivos se guardan en `output_data/` (los torneos en sus subcarpetas respectivas):

| Script | Archivos generados |
|---|---|
| Equipos VCT | `vct_equipos.xlsx` |
| Jugadores VCT | `vct_jugadores.xlsx` |
| Partidos | `vct_partidos.xlsx` |
| Mapas y Rondas | `vlr_mapas.xlsx`, `vlr_rondas.xlsx` |
| Stats por lado | `vlr_stats_players_sides.xlsx` |
| Enfrentamientos | `vlr_enfrentamientos.xlsx`, `vlr_multikills_clutches.xlsx` |
| Economía | `vlr_economia_resumen.xlsx`, `vlr_economia_rondas.xlsx` |

## ⚙️ Requisitos

- Python 3.8+
- Google Chrome (para scripts que usan Selenium Headless)

