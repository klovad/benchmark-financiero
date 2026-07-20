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

import calendar
import datetime
import re

from etl.config import BCE_DIR, DEFAULT_YEARS, RAW_DIR
from etl.extract.download_bce import download_all as download_bce_all
from etl.extract.download_tasas_historicas import download_tasas_historicas
from etl.extract.scrape_boletin import scrape as scrape_boletin
from etl.extract.scrape_superbancos import scrape
from etl.load.load_postgres import (
    get_connection,
    is_source_loaded,
    load_raw,
    load_raw_bce,
    load_raw_boletin,
    load_raw_tasas_referenciales,
    refresh_marts,
    register_source_file,
    upsert_banco_maestro_auto,
    upsert_dim_cuenta_contable,
    upsert_staging_bce_tasas_activas,
    upsert_staging_bce_tasas_pasivas,
    upsert_staging_boletin_balance,
    upsert_staging_boletin_pyg,
    upsert_staging_cartera,
    upsert_staging_depositos,
    upsert_staging_tasas_referenciales,
)
from etl.transform.common import sha256_file
from etl.transform.parse_bce_tasas import RAW_TSA_COLS, RAW_TSP_COLS, parse_tsa_file, parse_tsp_file, read_raw as read_raw_bce
from etl.transform.parse_boletin import parse_boletin_file
from etl.transform.parse_cartera import parse_cartera_file
from etl.transform.parse_depositos import parse_depositos_file
from etl.transform.parse_tasas_historicas import parse_tasas_historicas_file

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


def load_bce(base_dir: Path = BCE_DIR) -> None:
    """BCE tsp/tsa: descarga directa (sin Playwright), un solo archivo cada uno con todo
    el histórico semanal (2008-actualidad) -- no hay noción de 'año' para iterar como en
    CAPCOL, se procesa el archivo completo de una vez.

    Sin filtro de tipo_entidad (corregido 2026-07-19, ver docstring de
    etl/transform/parse_bce_tasas.py): raw.* captura las 6 categorías del sistema
    financiero tal cual (read_raw), staging.* resuelve identidad y agrega para TODAS
    (parse_tsp_file/parse_tsa_file) -- bancos privados vía crosswalk curado, el resto
    auto-registrado por RUC en staging.banco_maestro (upsert_banco_maestro_auto)."""
    files = download_bce_all(base_dir)
    conn = get_connection()
    try:
        for clave, report_type, parse_fn, upsert_fn, raw_cols in (
            ("tsp", "bce_tasas_pasivas", parse_tsp_file, upsert_staging_bce_tasas_pasivas, RAW_TSP_COLS),
            ("tsa", "bce_tasas_activas", parse_tsa_file, upsert_staging_bce_tasas_activas, RAW_TSA_COLS),
        ):
            table = report_type
            zip_path = files[clave]
            source_hash = sha256_file(zip_path)
            if is_source_loaded(conn, zip_path.name, source_hash):
                log.info("Ya cargado, se omite: %s", zip_path.name)
                continue
            log.info("Procesando %s (sin filtrar tipo_entidad)", zip_path.name)
            df_raw = read_raw_bce(zip_path)
            df_raw["source_file"] = zip_path.name
            df_raw["source_hash"] = source_hash
            load_raw_bce(conn, table, df_raw, raw_cols)

            df_staging, entidades_auto = parse_fn(zip_path, df_raw=df_raw)
            upsert_banco_maestro_auto(conn, entidades_auto)
            upsert_fn(conn, df_staging)
            register_source_file(conn, zip_path.name, source_hash, report_type)
            conn.commit()
        refresh_marts(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_NOMBRE_ARCHIVO = re.compile(r"TasasVigentes(\d{2})(\d{4})\.htm$")


def load_tasas_historicas() -> None:
    """TasasHistorico.htm: a diferencia de tsp/tsa (un solo archivo acumulativo), acá
    cada mes es un archivo HTML separado -- se procesa uno por uno, cada uno con su
    propio source_hash/idempotencia (mismo patrón que CAPCOL)."""
    files = download_tasas_historicas()
    conn = get_connection()
    try:
        for path in files:
            m = _NOMBRE_ARCHIVO.search(path.name)
            mes, anio = int(m.group(1)), int(m.group(2))
            fecha = datetime.date(anio, mes, calendar.monthrange(anio, mes)[1])

            source_hash = sha256_file(path)
            if is_source_loaded(conn, path.name, source_hash):
                log.info("Ya cargado, se omite: %s", path.name)
                continue
            log.info("Procesando %s", path.name)
            try:
                df = parse_tasas_historicas_file(path, fecha)
            except (ValueError, KeyError, IndexError) as e:
                # El layout HTML de la página cambió varias veces en 18 años (metodología
                # de segmentos, secciones); páginas muy antiguas (~2008-2010) no siempre
                # calzan con el layout actual -- se documenta y se sigue con el resto en
                # vez de abortar todo el histórico por un formato antiguo puntual.
                log.warning("No se pudo parsear %s (layout distinto), se omite: %s", path.name, e)
                continue
            load_raw_tasas_referenciales(conn, df, source_hash)
            upsert_staging_tasas_referenciales(conn, df)
            register_source_file(conn, path.name, source_hash, "tasas_referenciales")
            conn.commit()
        refresh_marts(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_MESES_ES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
}
_NOMBRE_BOLETIN = re.compile(r"BOLET[IÍ]N\s+BANCOS\s+([A-ZÑ]+)\s+(\d{4})", re.IGNORECASE)


def load_boletin(years: list[int], base_dir: Path = RAW_DIR) -> None:
    """Boletín Financiero Mensual: un archivo .zip por mes (nombre con mes en español),
    Playwright para descargar (mismo plugin OneDrive que CAPCOL)."""
    scrape_boletin(years, base_dir)
    conn = get_connection()
    try:
        for year in years:
            report_dir = base_dir / str(year) / "boletin"
            if not report_dir.exists():
                log.warning("No existe %s, se omite", report_dir)
                continue
            for zip_path in sorted(report_dir.glob("*.zip")):
                m = _NOMBRE_BOLETIN.search(zip_path.name.upper())
                if not m:
                    log.warning("No se pudo extraer mes/año de '%s', se omite", zip_path.name)
                    continue
                mes = _MESES_ES.get(m.group(1))
                anio = int(m.group(2))
                if mes is None:
                    log.warning("Mes no reconocido en '%s', se omite", zip_path.name)
                    continue
                fecha = datetime.date(anio, mes, calendar.monthrange(anio, mes)[1])

                source_hash = sha256_file(zip_path)
                if is_source_loaded(conn, zip_path.name, source_hash):
                    log.info("Ya cargado, se omite: %s", zip_path.name)
                    continue
                log.info("Procesando %s", zip_path.name)
                try:
                    result = parse_boletin_file(zip_path, EXTRACT_DIR, fecha)
                except (ValueError, KeyError, IndexError) as e:
                    # Igual que TasasHistorico: la plantilla del boletín cambió de
                    # formato entre años (encabezado, columnas de agregado, nombres de
                    # banco) -- se documenta y se sigue con el resto en vez de abortar.
                    log.warning("No se pudo parsear %s (layout/banco distinto), se omite: %s", zip_path.name, e)
                    continue
                upsert_dim_cuenta_contable(conn, result["cuentas"])
                load_raw_boletin(conn, "boletin_balance", result["balance"], source_hash)
                load_raw_boletin(conn, "boletin_pyg", result["pyg"], source_hash)
                upsert_staging_boletin_balance(conn, result["balance"])
                upsert_staging_boletin_pyg(conn, result["pyg"])
                register_source_file(conn, zip_path.name, source_hash, "boletin_balance")
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
    parser.add_argument("stage", choices=["extract", "load", "all", "bce", "tasas-historicas", "boletin"])
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--out", type=Path, default=RAW_DIR)
    args = parser.parse_args()

    if args.stage in ("extract", "all"):
        scrape(args.years, args.out)
    if args.stage in ("load", "all"):
        load_years(args.years, args.out)
    if args.stage == "bce":
        load_bce()
    if args.stage == "tasas-historicas":
        load_tasas_historicas()
    if args.stage == "boletin":
        load_boletin(args.years, args.out)


if __name__ == "__main__":
    main()
