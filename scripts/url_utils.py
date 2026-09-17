"""ALETHEIA - Utilidades de URLs compartidas por los scripts de scraping."""


def normalizar_url(url):
    """Devuelve una URL absoluta de VLR.gg a partir de distintos formatos.

    Acepta, por ejemplo:
      - 'https://www.vlr.gg/123'  -> sin cambios
      - 'www.vlr.gg/123'          -> 'https://www.vlr.gg/123'
      - 'vlr.gg/123'              -> 'https://www.vlr.gg/123'
      - '/vlr.gg/123'             -> 'https://www.vlr.gg/123'

    Así los archivos .txt de enlaces funcionan aunque las URLs vengan sin
    esquema (evita el error MissingSchema de requests).
    """
    url = (url or "").strip()
    if not url:
        return url
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("www."):
        return "https://" + url
    return "https://www." + url.lstrip("/")
