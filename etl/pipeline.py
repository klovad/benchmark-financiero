"""
Orquestador end-to-end: extract (Playwright) -> transform (parsers) -> load (Postgres).

Uso:
    python -m etl.pipeline extract --years 2021 2022 2023 2024 2025
    python -m etl.pipeline load --years 2021 2022 2023 2024 2025
    python -m etl.pipeline all --years 2021 2022 2023 2024 2025
    python -m etl.pipeline bce
    python -m etl.pipeline bce-reprocess-canton-grain  # backfill de un solo uso, ver
                                                        # reprocess_bce_staging() más abajo
"""

import argparse
import calendar
import datetime
import logging
import re
from pathlib import Path

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
    truncate_staging_bce,
    upsert_banco_maestro_ruc,
    upsert_dim_cuenta_contable,
    upsert_staging_bce_tasas_activas,
    upsert_staging_bce_tasas_pasivas,
    upsert_staging_boletin_balance,
    upsert_staging_boletin_pyg,
    upsert_staging_cartera,
    upsert_staging_depositos,
    upsert_staging_tasas_referenciales,
)
from etl.logging_utils import setup_logging
from etl.transform.common import sha256_file
from etl.transform.parse_bce_tasas import (
    RAW_TSA_COLS,
    RAW_TSP_COLS,
    parse_tsa_file,
    parse_tsp_file,
)
from etl.transform.parse_bce_tasas import read_raw as read_raw_bce
from etl.transform.parse_boletin import parse_boletin_file
from etl.transform.parse_cartera import parse_cartera_file
from etl.transform.parse_depositos import parse_depositos_file
from etl.transform.parse_tasas_historicas import parse_tasas_historicas_file

setup_logging()
log = logging.getLogger(__name__)

EXTRACT_DIR = RAW_DIR.parent / "_tmp_extract"


def load_years(years: list[int], base_dir: Path = RAW_DIR) -> None:
    conn = get_connection()
    try:
        for year in years:
            for report_type, table, parse_fn, upsert_fn in (
                ("cartera", "cartera", parse_cartera_file, upsert_staging_cartera),
                (
                    "depositos",
                    "depositos",
                    parse_depositos_file,
                    upsert_staging_depositos,
                ),
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
    auto-registrado por RUC en staging.banco_maestro; el RUC se guarda para todas,
    privados incluidos (upsert_banco_maestro_ruc, ver sql/17)."""
    files = download_bce_all(base_dir)
    conn = get_connection()
    try:
        for clave, report_type, parse_fn, upsert_fn, raw_cols in (
            (
                "tsp",
                "bce_tasas_pasivas",
                parse_tsp_file,
                upsert_staging_bce_tasas_pasivas,
                RAW_TSP_COLS,
            ),
            (
                "tsa",
                "bce_tasas_activas",
                parse_tsa_file,
                upsert_staging_bce_tasas_activas,
                RAW_TSA_COLS,
            ),
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

            df_staging, entidades = parse_fn(zip_path, df_raw=df_raw)
            upsert_banco_maestro_ruc(conn, entidades)
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


def reprocess_bce_staging(base_dir: Path = BCE_DIR) -> None:
    """Backfill de sql/28_bce_canton_grain.sql (cambio de grano provincia -> cantón,
    2026-09-01, ver etl/transform/parse_bce_tasas.py y canton_matching.py): re-deriva
    staging.bce_tasas_pasivas/activas -- y, vía refresh_marts(), fact_captaciones_depositos/
    fact_colocaciones_cartera -- SIN re-descargar ni re-insertar en raw.*. Seguro porque:
    (a) tsp/tsa son un solo zip acumulativo con el histórico completo ya en disco (no hay
    'año' que iterar como en CAPCOL); (b) raw.bce_tasas_pasivas/activas.data (JSONB) ya
    tenía `canton` en el payload desde siempre -- RAW_TSP_COLS/RAW_TSA_COLS no cambiaron
    con esta migración, solo el parser dejó de descartar esa columna en _weighted_agg().

    A diferencia de load_bce(), este NO respeta is_source_loaded(): el hash del archivo
    tsp/tsa no cambió (es el mismo de siempre, ya registrado en raw.source_files), así
    que ese gate diría "ya cargado" para siempre y load_bce() normal nunca dispararía el
    reproceso -- correcto para una carga semanal normal, pero exactamente lo que hay que
    saltarse para un backfill de un cambio de esquema. Por eso es una función aparte, no
    un flag de load_bce(): el flujo normal de cargas semanales queda intacto y sigue
    siendo 100% idempotente sin este comportamiento.

    truncate_staging_bce() vacía staging.bce_tasas_pasivas/activas primero -- necesario
    porque la llave natural de ambas tablas se extendió con `canton` (sql/28): sin este
    TRUNCATE, un upsert normal dejaría las filas viejas (canton NULL, grano provincia)
    como duplicados huérfanos junto a las nuevas (canton siempre poblado, grano cantón)
    en vez de reemplazarlas -- ver el docstring de esa función para el detalle completo.

    Comando de un solo uso para esta migración -- no forma parte del flujo semanal
    normal (load_bce() no lo invoca)."""
    files = download_bce_all(base_dir)
    conn = get_connection()
    try:
        truncate_staging_bce(conn)
        conn.commit()
        for clave, parse_fn, upsert_fn in (
            ("tsp", parse_tsp_file, upsert_staging_bce_tasas_pasivas),
            ("tsa", parse_tsa_file, upsert_staging_bce_tasas_activas),
        ):
            zip_path = files[clave]
            log.info(
                "Reprocesando %s (backfill grano cantón, raw.* intacto)", zip_path.name
            )
            df_staging, entidades = parse_fn(zip_path)
            upsert_banco_maestro_ruc(conn, entidades)
            upsert_fn(conn, df_staging)
            conn.commit()
        refresh_marts(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_NOMBRE_ARCHIVO = re.compile(r"TasasVigentes(\d{2})(\d{4})\.htm$")


def parse_fecha_from_tasas_historicas_filename(name: str) -> datetime.date:
    """Extrae la fecha (fin de mes) de un nombre de archivo TasasVigenteMMAAAA.htm.
    Pura, sin DB ni red -- factorizada desde el loop de load_tasas_historicas() para
    poder testearla en aislamiento (ver docs/propuesta_escalabilidad_etl.md sección 2.3).
    """
    m = _NOMBRE_ARCHIVO.search(name)
    if not m:
        raise ValueError(
            f"Nombre de archivo no reconocido para TasasHistorico: '{name}'"
        )
    mes, anio = int(m.group(1)), int(m.group(2))
    return datetime.date(anio, mes, calendar.monthrange(anio, mes)[1])


def load_tasas_historicas() -> None:
    """TasasHistorico.htm: a diferencia de tsp/tsa (un solo archivo acumulativo), acá
    cada mes es un archivo HTML separado -- se procesa uno por uno, cada uno con su
    propio source_hash/idempotencia (mismo patrón que CAPCOL)."""
    files = download_tasas_historicas()
    conn = get_connection()
    try:
        for path in files:
            try:
                fecha = parse_fecha_from_tasas_historicas_filename(path.name)
            except ValueError as e:
                # Antes de este refactor, un nombre de archivo que no calzara con
                # _NOMBRE_ARCHIVO crasheaba todo load_tasas_historicas() con un
                # AttributeError no capturado (m.group() sobre un match None) --
                # fuera del try/except que solo envolvía parse_tasas_historicas_file.
                # Factorizar el parseo permite atraparlo aquí igual que el resto de
                # fallas por archivo, en vez de abortar la corrida completa.
                log.warning("%s, se omite", e)
                continue

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
                log.warning(
                    "No se pudo parsear %s (layout distinto), se omite: %s",
                    path.name,
                    e,
                )
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
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}
_NOMBRE_BOLETIN = re.compile(
    r"BOLET[IÍ]N\s+BANCOS\s+([A-ZÑ]+)\s+(\d{4})", re.IGNORECASE
)


def parse_fecha_from_boletin_filename(name: str) -> datetime.date:
    """Extrae la fecha (fin de mes) de un nombre de archivo 'Boletín Bancos <MES_ES>
    <AAAA>...'. Pura, sin DB ni red -- factorizada desde el loop de load_boletin() para
    poder testearla en aislamiento (ver docs/propuesta_escalabilidad_etl.md sección 2.3).
    """
    m = _NOMBRE_BOLETIN.search(name.upper())
    if not m:
        raise ValueError(f"No se pudo extraer mes/año de '{name}'")
    mes = _MESES_ES.get(m.group(1))
    if mes is None:
        raise ValueError(f"Mes no reconocido en '{name}'")
    anio = int(m.group(2))
    return datetime.date(anio, mes, calendar.monthrange(anio, mes)[1])


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
                try:
                    fecha = parse_fecha_from_boletin_filename(zip_path.name)
                except ValueError as e:
                    log.warning("%s, se omite", e)
                    continue

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
                    log.warning(
                        "No se pudo parsear %s (layout/banco distinto), se omite: %s",
                        zip_path.name,
                        e,
                    )
                    continue
                upsert_dim_cuenta_contable(conn, result["cuentas"])
                load_raw_boletin(
                    conn, "boletin_balance", result["balance"], source_hash
                )
                load_raw_boletin(conn, "boletin_pyg", result["pyg"], source_hash)
                upsert_staging_boletin_balance(conn, result["balance"])
                upsert_staging_boletin_pyg(conn, result["pyg"])
                register_source_file(
                    conn, zip_path.name, source_hash, "boletin_balance"
                )
                conn.commit()
        refresh_marts(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline ETL benchmark cartera/depositos"
    )
    parser.add_argument(
        "stage",
        choices=[
            "extract",
            "load",
            "all",
            "bce",
            "bce-reprocess-canton-grain",
            "tasas-historicas",
            "boletin",
        ],
    )
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--out", type=Path, default=RAW_DIR)
    args = parser.parse_args()

    if args.stage in ("extract", "all"):
        scrape(args.years, args.out)
    if args.stage in ("load", "all"):
        load_years(args.years, args.out)
    if args.stage == "bce":
        load_bce()
    if args.stage == "bce-reprocess-canton-grain":
        reprocess_bce_staging()
    if args.stage == "tasas-historicas":
        load_tasas_historicas()
    if args.stage == "boletin":
        load_boletin(args.years, args.out)


if __name__ == "__main__":
    main()
