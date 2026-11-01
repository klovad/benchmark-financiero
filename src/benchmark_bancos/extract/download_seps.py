"""
Descarga directa de los reportes anuales de la SEPS (captaciones, colocaciones, EEFF).

A diferencia de CAPCOL, el portal SEPS publica links estáticos del plugin "Simple
Download Monitor" (`?sdm_process_download=1&download_id=N`) que redirigen al .zip real
en wp-content/uploads -- descarga simple por streaming, sin navegador (mismo patrón que
download_bce.py). Destino: data/raw/seps/{año}/{reporte}/{nombre real del zip}.

Los links de años viejos en el portal usan el parámetro con typo `smd_process_download`;
el plugin acepta ambos, verificado 2026-09-30 para 2021-2025.

Los download_id de un año que no está en `SEPS_DOWNLOAD_IDS` se descubren leyendo la
página del portal (`descubrir_download_ids`), así que el año nuevo se descarga solo en
cuanto la SEPS publica su link.
"""

import argparse
import html
import json
import logging
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from benchmark_bancos.config import (
    DEFAULT_YEARS,
    SEPS_DIR,
    SEPS_DOWNLOAD_IDS,
    SEPS_DOWNLOAD_URL,
    SEPS_PORTAL_URL,
)
from benchmark_bancos.extract.red import con_reintentos
from benchmark_bancos.logging_utils import setup_logging

log = logging.getLogger(__name__)

_CHUNK_SIZE = 1 << 20  # 1 MiB
REPORTES_SEPS = ("eeff", "captaciones", "colocaciones")


_META = "_descarga.json"

# Dónde está cada reporte en la página del portal: (sección, bloque, título), sin tildes
# ni mayúsculas. La sección "situacion financiera" es la primera de la página y no tiene
# encabezado propio en el HTML (es una pestaña), por eso es el estado inicial.
_UBICACION_PORTAL = {
    ("situacion financiera", "bases de datos", "estados financieros mensuales"): "eeff",
    ("depositos", "reportes", "captaciones mensuales"): "captaciones",
    ("cartera de credito", "reportes", "colocaciones mensuales"): "colocaciones",
}
_SECCIONES = {
    "depositos",
    "cartera de credito",
    "tasas de interes",
    "inclusion financiera",
}
_BLOQUES = {
    "reporte": "reportes",
    "reportes": "reportes",
    "bases de datos": "bases de datos",
    "metodologia": "otro",
    "documentacion adicional": "otro",
}
_TOKEN = re.compile(
    r"<a\s[^>]*download_id=(\d+)[^>]*>(.*?)</a>|<(h[1-6]|p)\b[^>]*>(.*?)</\3>",
    re.S | re.I,
)


def _normalizar(texto: str) -> str:
    texto = html.unescape(re.sub(r"<[^>]+>", "", texto))
    texto = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", texto).strip(" :").lower()


def descubrir_download_ids(pagina: str) -> dict[int, dict[str, int]]:
    """download_id por año y reporte leídos de la página del portal. Recorre en orden
    los encabezados y los links de año: cada link pertenece al último título visto,
    dentro del último bloque (Reportes / Bases de Datos) y sección. Si un año aparece dos
    veces bajo el mismo título (EEFF trae una segunda fila de 2026), vale el primero, que
    es la base de 6 dígitos."""
    seccion, bloque, titulo = "situacion financiera", None, None
    ids: dict[int, dict[str, int]] = {}
    for m in _TOKEN.finditer(pagina):
        if m.group(1):
            anio = _normalizar(m.group(2))
            reporte = _UBICACION_PORTAL.get((seccion, bloque, titulo))
            if reporte and re.fullmatch(r"\d{4}", anio):
                ids.setdefault(int(anio), {}).setdefault(reporte, int(m.group(1)))
            continue
        texto = _normalizar(m.group(4))
        if not texto or len(texto) > 80:
            continue
        if texto in _SECCIONES:
            seccion, bloque, titulo = texto, None, None
        elif texto in _BLOQUES:
            bloque, titulo = _BLOQUES[texto], None
        else:
            titulo = texto
    return ids


def _ids_del_portal() -> dict[int, dict[str, int]]:
    def leer() -> str:
        req = urllib.request.Request(
            SEPS_PORTAL_URL, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode(resp.headers.get_content_charset() or "utf-8")

    return descubrir_download_ids(con_reintentos(leer, "SEPS (página del portal)"))


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


def download_seps_file(
    year: int,
    reporte: str,
    out_dir: Path = SEPS_DIR,
    ids: dict[str, int] | None = None,
) -> Path:
    """Descarga solo si la SEPS publicó una versión distinta a la local.

    El año en curso se republica cada mes con el MISMO download_id (y a veces el mismo
    nombre de archivo), así que "la carpeta ya tiene un .zip" no basta (2026-10-09). Se
    compara la versión publicada (URL final, Last-Modified, tamaño, vía HEAD) contra la
    guardada en `<carpeta>/_descarga.json`. Sin ese archivo (descargas anteriores a este
    cambio) se acepta el .zip local si coincide en nombre y tamaño. Al bajar una versión
    nueva se borra la anterior: la carpeta queda con un solo .zip. Después, el sha256 de
    `meta.source_files` decide si hay que recargar.

    `ids`: download_id de ese año por reporte; por defecto, los de SEPS_DOWNLOAD_IDS.
    """
    ids = ids or SEPS_DOWNLOAD_IDS[year]
    url = SEPS_DOWNLOAD_URL.format(id=ids[reporte])
    dest_dir = out_dir / str(year) / reporte
    dest_dir.mkdir(parents=True, exist_ok=True)
    meta_path = dest_dir / _META
    existentes = sorted(dest_dir.glob("*.zip"))

    publicada = con_reintentos(
        lambda: _version_publicada(url), f"SEPS {year}/{reporte} (HEAD)"
    )
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

    def bajar() -> None:
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as f:
            while chunk := resp.read(_CHUNK_SIZE):
                f.write(chunk)

    con_reintentos(bajar, f"SEPS {year}/{reporte}")
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
    portal = None
    for year in years:
        ids = SEPS_DOWNLOAD_IDS.get(year)
        if ids is None:
            if portal is None:
                portal = _ids_del_portal()
            ids = portal.get(year, {})
            faltan = [r for r in REPORTES_SEPS if r not in ids]
            if faltan:
                # Normal en enero-febrero: la SEPS publica el año nuevo con rezago.
                log.info(
                    "SEPS %s: el portal todavía no publica %s, se omite el año",
                    year,
                    ", ".join(faltan),
                )
                continue
            log.info(
                "SEPS %s: download_id leídos del portal %s (se pueden fijar en "
                "config.SEPS_DOWNLOAD_IDS)",
                year,
                ids,
            )
        resultado[year] = {
            r: download_seps_file(year, r, out_dir, ids) for r in REPORTES_SEPS
        }
    return resultado


if __name__ == "__main__":
    setup_logging()
    parser = argparse.ArgumentParser(description="Descarga reportes SEPS")
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    args = parser.parse_args()
    download_seps(args.years)
