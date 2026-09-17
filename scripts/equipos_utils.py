"""ALETHEIA - Utilidades de equipos compartidas por los scripts de scraping."""

import re


def alias_nombres_equipo(nombre_header):
    """Devuelve el conjunto de nombres (en minúsculas) con los que puede
    aparecer un equipo en el scoreboard, a partir del nombre del header.

    VLR.gg muestra el header como 'NombreLargo(Abrev)' cuando el equipo tiene
    patrocinador (ej. 'Movistar KOI(KOI)'), mientras que en el scoreboard usa
    solo una de esas partes (ej. 'KOI'). Esta función devuelve todos los alias:

      'Movistar KOI(KOI)'              -> {'movistar koi(koi)', 'movistar koi', 'koi'}
      'JD Mall JDG Esports(JD Gaming)' -> {..., 'jd mall jdg esports', 'jd gaming'}
      'Team Liquid'                    -> {'team liquid'}
    """
    base = (nombre_header or "").strip()
    alias = {base.lower()}
    m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", base)
    if m:
        alias.add(m.group(1).strip().lower())
        alias.add(m.group(2).strip().lower())
    return alias
