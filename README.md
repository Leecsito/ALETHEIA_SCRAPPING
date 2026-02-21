<<<<<<< HEAD
# ⚔️ ALETHEIA

Herramienta de scraping para datos competitivos de **Valorant VCT 2026**.

Extrae automáticamente equipos, jugadores, partidos, estadísticas por mapa/lado, enfrentamientos, multikills y economía desde **Liquipedia** y **VLR.gg**.

## 📂 Estructura

```
ALETHEIA/
├── main.py                  # Menú principal para ejecutar scripts
├── scripts/
│   ├── scrapear_equipos_jugadores.py   # Equipos y jugadores (Liquipedia)
│   ├── scrapear_partidos.py            # Partidos VCT (VLR.gg)
│   ├── scrapear_vlr_corregido.py       # Mapas y rondas
│   ├── scrapear_stats_pro.py           # Stats por lado ATK/DEF
│   ├── scrapear_enfrentamientos.py     # Enfrentamientos y multikills
│   └── scrapear_economia.py            # Economía por ronda
├── output_data/             # Archivos Excel generados
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
python scripts/scrapear_equipos_jugadores.py
```

## 📊 Archivos de salida

Todos los archivos se guardan en `output_data/`:

| Script | Archivos generados |
|---|---|
| Equipos y Jugadores | `vct_equipos.xlsx`, `vct_jugadores.xlsx` |
| Partidos | `vct_partidos.xlsx` |
| Mapas y Rondas | `vlr_mapas.xlsx`, `vlr_rondas.xlsx` |
| Stats por lado | `vlr_stats_players_sides.xlsx` |
| Enfrentamientos | `vlr_enfrentamientos.xlsx`, `vlr_multikills_clutches.xlsx` |
| Economía | `vlr_economia_resumen.xlsx`, `vlr_economia_rondas.xlsx` |

## ⚙️ Requisitos

- Python 3.8+
- Google Chrome (para scripts que usan Selenium)
=======
# ALETHEIA_SCRAPPING
Scrapeador hecho en Python para extraer datos de partidos profesionales de Valorant.
>>>>>>> d666f0e075fcaa4b4190ae19ff065e13f7895def
