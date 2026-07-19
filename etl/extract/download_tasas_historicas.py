"""
Descarga de las páginas mensuales TasasVigentes{MM}{YYYY}.htm del BCE (techos
regulatorios y tasas referenciales del sistema). HTML estático, sin Playwright.

El patrón de URL es 100% predecible (mes/año en el nombre de archivo), pero no todos los
meses tienen página publicada (huecos, sobre todo en 2007-2008 y meses recientes que
aún no se publican) -- se tolera 404 y se sigue con el resto.
"""

import datetime
import logging
import urllib.error
import urllib.request
from pathlib import Path

from etl.config import BCE_BASE_URL, BCE_DIR

log = logging.getLogger(__name__)

HISTORICO_DIR = BCE_DIR / "historico"
_INICIO = (2008, 1)


def _meses_hasta_hoy():
    anio, mes = _INICIO
    hoy = datetime.date.today()
    while (anio, mes) <= (hoy.year, hoy.month):
        yield anio, mes
        mes += 1
        if mes > 12:
            mes = 1
            anio += 1


def download_tasas_historicas(out_dir: Path = HISTORICO_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    descargados = []
    for anio, mes in _meses_hasta_hoy():
        nombre = f"TasasVigentes{mes:02d}{anio}.htm"
        dest = out_dir / nombre
        if dest.exists():
            descargados.append(dest)
            continue
        url = f"{BCE_BASE_URL}/{nombre}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                log.info("No existe %s (404), se omite", nombre)
                continue
            raise
        dest.write_bytes(data)
        descargados.append(dest)
        log.info("Descargado %s", nombre)
    return descargados


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    files = download_tasas_historicas()
    print(f"{len(files)} páginas disponibles")
