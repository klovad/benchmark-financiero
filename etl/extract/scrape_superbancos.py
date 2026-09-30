"""
Descarga los archivos ZIP de cartera y depósitos del portal CAPCOL de Superbancos.

El listado de archivos por año no es HTML estático: el portal usa el plugin
"Share-one-Drive" (WordPress + OneDrive/SharePoint) para renderizar un explorador
de carpetas vía AJAX. Por eso se automatiza con Playwright en vez de requests/httpx.

Estructura del portal: Año {YYYY} > {CARTERA|COLOCACIONES} / {DEPOSITOS|CAPTACIONES} > archivos .zip
(los nombres de carpeta cambiaron en 2024; ver etl.config.FOLDER_NAMES).

Mismo código para los sub-portales de bancos privados y Banca Pública
(etl.config.CAPCOL_PORTALES): solo cambian la URL y el subdirectorio de destino.
"""

import argparse
import logging
from pathlib import Path

from playwright.sync_api import TimeoutError as PwTimeoutError
from playwright.sync_api import sync_playwright

from etl.config import CAPCOL_PORTALES, DEFAULT_YEARS, FOLDER_NAMES, RAW_DIR
from etl.logging_utils import setup_logging

setup_logging()
log = logging.getLogger(__name__)


def _reset_to_root(page) -> None:
    """Vuelve al listado raíz de años vía el breadcrumb 'Inicio'.

    OJO: recargar la página con page.goto() NO sirve para esto: el plugin
    Share-one-Drive persiste la última carpeta vista y la restaura al recargar,
    en vez de mostrar el listado raíz de años.
    """
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
        log.info(
            "Intento %d/%d: carpeta 'Año %s' no visible aún, esperando...",
            attempt,
            retries,
            year,
        )
        page.wait_for_timeout(2000)
    log.warning("No se encontró la carpeta 'Año %s' en el portal", year)
    return False


def _open_report_folder(page, report_type: str) -> bool:
    for name in FOLDER_NAMES[report_type]:
        folder = page.locator(f'.entry.folder[data-name="{name}"]')
        if folder.count() > 0:
            folder.first.click()
            page.wait_for_timeout(2000)
            return True
    return False


def _download_all_files(page, dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    count = page.locator(".entry.file").count()
    for i in range(count):
        entry = page.locator(".entry.file").nth(i)
        name = entry.get_attribute("data-name") or f"archivo_{i}"
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


def scrape_year(page, year: int, out_dir: Path) -> dict[str, list[Path]]:
    results: dict[str, list[Path]] = {"cartera": [], "depositos": []}
    for report_type in ("cartera", "depositos"):
        _reset_to_root(page)
        if not _open_year_folder(page, year):
            continue
        if not _open_report_folder(page, report_type):
            log.warning("Año %s: no se encontró carpeta de %s", year, report_type)
            continue
        dest = out_dir / str(year) / report_type
        results[report_type] = _download_all_files(page, dest)
    return results


def scrape(
    years: list[int],
    out_dir: Path = RAW_DIR,
    headless: bool = True,
    portal: str = "privada",
) -> dict[int, dict]:
    cfg = CAPCOL_PORTALES[portal]
    if cfg["subdir"]:
        out_dir = out_dir / cfg["subdir"]
    all_results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(accept_downloads=True)
        page.goto(cfg["url"], wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(2000)
        for year in years:
            log.info("=== %s: Año %s ===", portal, year)
            all_results[year] = scrape_year(page, year, out_dir)
        browser.close()
    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="Descarga archivos CAPCOL de Superbancos"
    )
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--out", type=Path, default=RAW_DIR)
    parser.add_argument("--portal", choices=list(CAPCOL_PORTALES), default="privada")
    args = parser.parse_args()
    results = scrape(args.years, args.out, portal=args.portal)
    total = sum(len(v) for r in results.values() for v in r.values())
    log.info("Descarga completa: %d archivos", total)


if __name__ == "__main__":
    main()
