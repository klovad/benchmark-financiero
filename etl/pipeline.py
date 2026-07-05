"""
Orquestador end-to-end: extract (Playwright) -> transform (parsers) -> load (Postgres).

Uso:
    python -m etl.pipeline extract --years 2021 2022 2023 2024 2025
    python -m etl.pipeline load --years 2021 2022 2023 2024 2025
    python -m etl.pipeline all --years 2021 2022 2023 2024 2025
"""

import argparse
import logging
from pathlib import Path

from etl.config import DEFAULT_YEARS, RAW_DIR
from etl.extract.scrape_superbancos import scrape
from etl.load.load_postgres import (
    get_connection,
    is_source_loaded,
    load_raw,
    refresh_marts,
    register_source_file,
    upsert_staging_cartera,
    upsert_staging_depositos,
)
from etl.transform.common import sha256_file
from etl.transform.parse_cartera import parse_cartera_file
from etl.transform.parse_depositos import parse_depositos_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

EXTRACT_DIR = RAW_DIR.parent / "_tmp_extract"


def load_years(years: list[int], base_dir: Path = RAW_DIR) -> None:
    conn = get_connection()
    try:
        for year in years:
            for report_type, table, parse_fn, upsert_fn in (
                ("cartera", "cartera", parse_cartera_file, upsert_staging_cartera),
                ("depositos", "depositos", parse_depositos_file, upsert_staging_depositos),
            ):
                report_dir = base_dir / str(year) / report_type
                if not report_dir.exists():
                    log.warning("No existe %s, se omite", report_dir)
                    continue
                for zip_path in sorted(report_dir.glob("*.zip")):
                    source_hash = sha256_file(zip_path)
                    if is_source_loaded(conn, zip_path.name, source_hash):
                        log.info("Ya cargado, se omite: %s", zip_path.name)
                        continue
                    log.info("Procesando %s", zip_path.name)
                    df = parse_fn(zip_path, EXTRACT_DIR)
                    load_raw(conn, table, df, year)
                    upsert_fn(conn, df)
                    register_source_file(conn, zip_path.name, source_hash, report_type)
                    conn.commit()
        refresh_marts(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Pipeline ETL benchmark cartera/depositos")
    parser.add_argument("stage", choices=["extract", "load", "all"])
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--out", type=Path, default=RAW_DIR)
    args = parser.parse_args()

    if args.stage in ("extract", "all"):
        scrape(args.years, args.out)
    if args.stage in ("load", "all"):
        load_years(args.years, args.out)


if __name__ == "__main__":
    main()
