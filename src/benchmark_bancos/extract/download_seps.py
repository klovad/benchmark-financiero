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
import json
import logging
import os
import urllib.parse
import urllib.request
from pathlib import Path

from benchmark_bancos.config import (
    DEFAULT_YEARS,
    SEPS_DIR,
    SEPS_DOWNLOAD_IDS,
    SEPS_DOWNLOAD_URL,
)
from benchmark_bancos.logging_utils import setup_logging

log = logging.getLogger(__name__)

_CHUNK_SIZE = 1 << 20  # 1 MiB
REPORTES_SEPS = ("eeff", "captaciones", "colocaciones")


_META = "_descarga.json"


def _version_publicada(url: str) -> dict:
    """HEAD al link del portal (sigue la redirección al .zip real, sin bajarlo): URL
    final, Last-Modified y tamaño de la versión publicada hoy."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return {
            "url_final": resp.url,
            "last_modified": resp.headers.get("Last-Modified"),
            "tamano": int(resp.headers.get("Content-Length") or 0),
        }


def _nombre_zip(url_final: str, year: int, reporte: str, url: str) -> str:
    nombre = Path(urllib.parse.unquote(urllib.parse.urlparse(url_final).path)).name
    if not nombre.lower().endswith(".zip"):
        raise ValueError(
            f"SEPS {year}/{reporte}: la descarga {url} no redirigió a un .zip "
            f"(final: {url_final}). ¿Cambió el download_id en el portal?"
        )
    return nombre


def download_seps_file(year: int, reporte: str, out_dir: Path = SEPS_DIR) -> Path:
    """Descarga solo si la SEPS publicó una versión distinta a la local.

    El año en curso se republica cada mes con el MISMO download_id (y a veces el mismo
    nombre de archivo), así que "la carpeta ya tiene un .zip" no basta (2026-10-09). Se
    compara la versión publicada (URL final, Last-Modified, tamaño, vía HEAD) contra la
    guardada en `<carpeta>/_descarga.json`. Sin ese archivo (descargas anteriores a este
    cambio) se acepta el .zip local si coincide en nombre y tamaño. Al bajar una versión
    nueva se borra la anterior: la carpeta queda con un solo .zip. Después, el sha256 de
    `meta.source_files` decide si hay que recargar.
    """
    url = SEPS_DOWNLOAD_URL.format(id=SEPS_DOWNLOAD_IDS[year][reporte])
    dest_dir = out_dir / str(year) / reporte
    dest_dir.mkdir(parents=True, exist_ok=True)
    meta_path = dest_dir / _META
    existentes = sorted(dest_dir.glob("*.zip"))

    publicada = _version_publicada(url)
    nombre = _nombre_zip(publicada["url_final"], year, reporte, url)
    try:
        local = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        local = None
    if existentes:
        mismo = (
            local == publicada
            if local is not None
            else (
                existentes[0].name == nombre
                and existentes[0].stat().st_size == publicada["tamano"]
            )
        )
        if mismo:
            if local is None:
                meta_path.write_text(json.dumps(publicada, indent=2), encoding="utf-8")
            log.info("Sin cambios en la SEPS, se conserva: %s", existentes[0])
            return existentes[0]
        log.info(
            "SEPS %s/%s: versión nueva publicada (%s)",
            year,
            reporte,
            publicada["last_modified"],
        )

    dest = dest_dir / nombre
    tmp = dest_dir / (nombre + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(_CHUNK_SIZE):
            f.write(chunk)
    for viejo in existentes:
        viejo.unlink()
    os.replace(tmp, dest)
    meta_path.write_text(json.dumps(publicada, indent=2), encoding="utf-8")
    log.info("Descargado %s (%.1f MB)", dest, dest.stat().st_size / 1e6)
    return dest


def download_seps(
    years: list[int], out_dir: Path = SEPS_DIR
) -> dict[int, dict[str, Path]]:
    resultado = {}
    for year in years:
        if year not in SEPS_DOWNLOAD_IDS:
            log.warning(
                "SEPS %s: sin download_id en benchmark_bancos.config.SEPS_DOWNLOAD_IDS, se omite",
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
