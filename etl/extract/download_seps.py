"""
Descarga directa de los reportes anuales de la SEPS (captaciones, colocaciones, EEFF).

A diferencia de CAPCOL, el portal SEPS publica links estáticos del plugin "Simple
Download Monitor" (`?sdm_process_download=1&download_id=N`) que redirigen al .zip real
en wp-content/uploads -- descarga simple por streaming, sin navegador (mismo patrón que
download_bce.py). Destino: data/raw/seps/{año}/{reporte}/{nombre real del zip}.

Los links de años viejos en el portal usan el parámetro con typo `smd_process_download`;
el plugin acepta ambos, verificado 2026-09-30 para 2021-2025.
"""

import argparse
import logging
import urllib.parse
import urllib.request
from pathlib import Path

from etl.config import DEFAULT_YEARS, SEPS_DIR, SEPS_DOWNLOAD_IDS, SEPS_DOWNLOAD_URL
from etl.logging_utils import setup_logging

log = logging.getLogger(__name__)

_CHUNK_SIZE = 1 << 20  # 1 MiB
REPORTES_SEPS = ("eeff", "captaciones", "colocaciones")


def download_seps_file(year: int, reporte: str, out_dir: Path = SEPS_DIR) -> Path:
    """Descarga si la carpeta destino no tiene ya un .zip (el nombre real solo se conoce
    tras seguir la redirección, así que el chequeo de "ya descargado" es por carpeta).
    """
    dest_dir = out_dir / str(year) / reporte
    existentes = sorted(dest_dir.glob("*.zip"))
    if existentes:
        log.info("Ya descargado, se omite: %s", existentes[0])
        return existentes[0]

    url = SEPS_DOWNLOAD_URL.format(id=SEPS_DOWNLOAD_IDS[year][reporte])
    dest_dir.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        nombre = Path(urllib.parse.unquote(urllib.parse.urlparse(resp.url).path)).name
        if not nombre.lower().endswith(".zip"):
            raise ValueError(
                f"SEPS {year}/{reporte}: la descarga {url} no redirigió a un .zip "
                f"(final: {resp.url}). ¿Cambió el download_id en el portal?"
            )
        dest = dest_dir / nombre
        tmp = dest.with_suffix(".zip.part")
        with open(tmp, "wb") as f:
            while chunk := resp.read(_CHUNK_SIZE):
                f.write(chunk)
    tmp.rename(dest)
    log.info("Descargado %s (%.1f MB)", dest, dest.stat().st_size / 1e6)
    return dest


def download_seps(
    years: list[int], out_dir: Path = SEPS_DIR
) -> dict[int, dict[str, Path]]:
    resultado = {}
    for year in years:
        if year not in SEPS_DOWNLOAD_IDS:
            log.warning(
                "SEPS %s: sin download_id en etl.config.SEPS_DOWNLOAD_IDS, se omite",
                year,
            )
            continue
        resultado[year] = {
            r: download_seps_file(year, r, out_dir) for r in REPORTES_SEPS
        }
    return resultado


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Descarga reportes SEPS")
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    args = parser.parse_args()
    download_seps(args.years)
