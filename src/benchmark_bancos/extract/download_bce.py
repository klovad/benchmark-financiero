"""
Descarga directa de los archivos semanales de tasas de interés del BCE (tsp/tsa).

A diferencia de CAPCOL (portal WordPress con plugin OneDrive, requiere Playwright),
estos son links estáticos -- descarga simple por streaming, sin navegador.

El BCE republica cada semana el MISMO archivo (mismo nombre, todo el histórico desde
2008), así que "ya existe en disco" no significa "está al día". La descarga es
condicional (2026-10-09): se guarda el ETag/Last-Modified de la última versión en un
archivo `<zip>.meta.json` al lado del ZIP y se pide al servidor con `If-None-Match`/
`If-Modified-Since`. Si responde 304 se conserva el archivo local; si responde 200 se
reemplaza. Sin el `.meta.json` (archivos bajados antes de este cambio) se usa la fecha
de modificación del archivo local. Después, `pipeline.load_bce()` compara el sha256
contra `meta.source_files`: un archivo nuevo con el mismo contenido no se reprocesa.
"""

import email.utils
import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

from benchmark_bancos.config import BCE_DIR, BCE_URLS
from benchmark_bancos.extract.red import con_reintentos
from benchmark_bancos.logging_utils import setup_logging

log = logging.getLogger(__name__)

_CHUNK_SIZE = 1 << 20  # 1 MiB


def _meta_path(dest: Path) -> Path:
    return dest.with_name(dest.name + ".meta.json")


def _leer_meta(dest: Path) -> dict:
    try:
        return json.loads(_meta_path(dest).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _cabeceras_condicionales(dest: Path) -> dict[str, str]:
    if not dest.exists():
        return {}
    meta = _leer_meta(dest)
    headers = {}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    headers["If-Modified-Since"] = meta.get("last_modified") or email.utils.formatdate(
        dest.stat().st_mtime, usegmt=True
    )
    return headers


def download_bce_file(clave: str, out_dir: Path = BCE_DIR) -> Path:
    """clave: 'tsp' o 'tsa'. Descarga solo si el servidor tiene una versión distinta a
    la local (o si no hay copia local). Devuelve la ruta del ZIP vigente."""
    url = BCE_URLS[clave]
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / Path(url).name

    headers = {"User-Agent": "Mozilla/5.0", **_cabeceras_condicionales(dest)}
    req = urllib.request.Request(url, headers=headers)
    tmp = dest.with_suffix(dest.suffix + ".part")

    def bajar() -> tuple[str | None, str | None]:
        with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as f:
            while chunk := resp.read(_CHUNK_SIZE):
                f.write(chunk)
            return resp.headers.get("ETag"), resp.headers.get("Last-Modified")

    try:
        etag, last_modified = con_reintentos(bajar, f"BCE {dest.name}")
    except urllib.error.HTTPError as e:
        tmp.unlink(missing_ok=True)
        if e.code == 304:
            log.info("Sin cambios en el servidor, se conserva: %s", dest.name)
            return dest
        raise

    os.replace(tmp, dest)
    if last_modified:
        ts = email.utils.parsedate_to_datetime(last_modified).timestamp()
        os.utime(dest, (ts, ts))
    _meta_path(dest).write_text(
        json.dumps(
            {"url": url, "etag": etag, "last_modified": last_modified}, indent=2
        ),
        encoding="utf-8",
    )
    log.info(
        "Descargado %s (%.1f MB, publicado %s)",
        dest.name,
        dest.stat().st_size / 1e6,
        last_modified or "sin fecha",
    )
    return dest


def download_all(out_dir: Path = BCE_DIR) -> dict[str, Path]:
    return {clave: download_bce_file(clave, out_dir) for clave in BCE_URLS}


if __name__ == "__main__":
    setup_logging()
    download_all()
