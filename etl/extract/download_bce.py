"""
Descarga directa de los archivos semanales de tasas de interés del BCE (tsp/tsa).

A diferencia de CAPCOL (portal WordPress con plugin OneDrive, requiere Playwright),
estos son links estáticos -- descarga simple por streaming, sin navegador.
"""

import logging
import urllib.request
from pathlib import Path

from etl.config import BCE_DIR, BCE_URLS
from etl.logging_utils import setup_logging

log = logging.getLogger(__name__)

_CHUNK_SIZE = 1 << 20  # 1 MiB


def download_bce_file(clave: str, out_dir: Path = BCE_DIR) -> Path:
    """clave: 'tsp' o 'tsa'. Descarga si no existe ya un archivo con ese nombre."""
    url = BCE_URLS[clave]
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / Path(url).name
    if dest.exists():
        log.info("Ya descargado, se omite: %s", dest)
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(_CHUNK_SIZE):
            f.write(chunk)
    tmp.rename(dest)
    log.info("Descargado %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


def download_all(out_dir: Path = BCE_DIR) -> dict[str, Path]:
    return {clave: download_bce_file(clave, out_dir) for clave in BCE_URLS}


if __name__ == "__main__":
    setup_logging()
    download_all()
