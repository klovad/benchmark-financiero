"""
Descarga los ZIP del Boletín Financiero Mensual (Balance y PyG) de bancos privados,
portal Superbancos.

Mismo plugin OneDrive/SharePoint ("Share-one-Drive") que CAPCOL (ver
etl/extract/scrape_superbancos.py) -- requiere Playwright, no es HTML estático. A
diferencia de CAPCOL, la estructura es más plana: Año {YYYY} > archivos .zip
directamente (sin subcarpeta de tipo de reporte), nombrados
"{N}. BOLETIN BANCOS {MES} {YYYY}.zip".
"""

import argparse
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeoutError

from etl.config import BOLETIN_URL, DEFAULT_YEARS, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def _reset_to_root(page) -> None:
    root_link = page.locator("a.first-breadcrumb")
    if root_link.count() > 0:
        root_link.first.click()
        page.wait_for_timeout(2000)


def _open_year_folder(page, year: int, retries: int = 3) -> bool:
    for attempt in range(1, retries + 1):
        folder = page.locator(f'.entry.folder[data-name="Año {year}"]')
        if folder.count() > 0:
            folder.first.click()
            page.wait_for_timeout(2500)
            return True
        log.info("Intento %d/%d: carpeta 'Año %s' no visible aún, esperando...", attempt, retries, year)
        page.wait_for_timeout(2000)
    log.warning("No se encontró la carpeta 'Año %s' en el portal", year)
    return False


def _download_all_files(page, dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    count = page.locator(".entry.file").count()
    for i in range(count):
        entry = page.locator(".entry.file").nth(i)
        name = entry.get_attribute("data-name") or f"archivo_{i}"
        if "boletin" not in name.lower() and "boletín" not in name.lower():
            continue  # la carpeta de año trae otros archivos además del boletín mensual
        try:
            with page.expect_download(timeout=30_000) as dl_info:
                entry.dblclick()
            download = dl_info.value
            target = dest_dir / download.suggested_filename
            download.save_as(target)
            saved.append(target)
            log.info("Descargado: %s", target)
        except PwTimeoutError:
            log.error("Timeout descargando '%s'", name)
    return saved


def scrape_year(page, year: int, out_dir: Path) -> list[Path]:
    _reset_to_root(page)
    if not _open_year_folder(page, year):
        return []
    dest = out_dir / str(year) / "boletin"
    return _download_all_files(page, dest)


def scrape(years: list[int], out_dir: Path = RAW_DIR, headless: bool = True) -> dict[int, list[Path]]:
    all_results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(accept_downloads=True)
        page.goto(BOLETIN_URL, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(2000)
        for year in years:
            log.info("=== Año %s ===", year)
            all_results[year] = scrape_year(page, year, out_dir)
        browser.close()
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Descarga Boletín Financiero Mensual de Superbancos")
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--out", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    results = scrape(args.years, args.out)
    total = sum(len(v) for v in results.values())
    log.info("Descarga completa: %d archivos", total)


if __name__ == "__main__":
    main()
