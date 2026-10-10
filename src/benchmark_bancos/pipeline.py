"""
Orquestación end-to-end por fuente: extract -> transform (parsers) -> load (Postgres).

Cada `load_*` es una unidad independiente e idempotente (salta archivos ya registrados por
hash). La interfaz de línea de comandos vive en `benchmark_bancos.cli`.
"""

import calendar
import datetime
import logging
import re
from pathlib import Path

from benchmark_bancos.config import (
    BCE_DIR,
    CAPCOL_PORTALES,
    EXTRACT_DIR,
    RAW_DIR,
    SEPS_DIR,
)
from benchmark_bancos.extract.download_bce import download_all as download_bce_all
from benchmark_bancos.extract.download_seps import download_seps
from benchmark_bancos.extract.download_tasas_historicas import download_tasas_historicas
from benchmark_bancos.extract.scrape_boletin import scrape as scrape_boletin
from benchmark_bancos.load.load_postgres import (
    get_connection,
    insert_dim_cuenta_contable_seps,
    is_source_loaded,
    refresh_marts,
    register_source_file,
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
from benchmark_bancos.transform.common import sha256_file
from benchmark_bancos.transform.parse_bce_tasas import (
    parse_tsa_file,
    parse_tsp_file,
)
from benchmark_bancos.transform.parse_bce_tasas import read_raw as read_raw_bce
from benchmark_bancos.transform.parse_boletin import parse_boletin_file
from benchmark_bancos.transform.parse_cartera import parse_cartera_file
from benchmark_bancos.transform.parse_depositos import parse_depositos_file
from benchmark_bancos.transform.parse_seps import (
    parse_seps_captaciones_file,
    parse_seps_colocaciones_file,
    parse_seps_eeff_file,
)
from benchmark_bancos.transform.parse_tasas_historicas import (
    parse_tasas_historicas_file,
)

log = logging.getLogger(__name__)


def load_years(
    years: list[int],
    base_dir: Path = RAW_DIR,
    portales: tuple[str, ...] = tuple(CAPCOL_PORTALES),
) -> None:
    """tipo_entidad de cada fila lo fija el sub-portal CAPCOL de donde vino el archivo
    (benchmark_bancos.config.CAPCOL_PORTALES), no el parser. source_file se prefija con el subdir del
    portal (ej. 'banca_publica/Cartera Consumo DICIEMBRE 2025.zip') porque
    meta.source_files es UNIQUE por nombre y ambos portales usan nombres parecidos."""
    conn = get_connection()
    try:
        for portal in portales:
            cfg = CAPCOL_PORTALES[portal]
            portal_dir = base_dir / cfg["subdir"] if cfg["subdir"] else base_dir
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
                    report_dir = portal_dir / str(year) / report_type
                    if not report_dir.exists():
                        log.warning("No existe %s, se omite", report_dir)
                        continue
                    for zip_path in sorted(report_dir.glob("*.zip")):
                        source_key = (
                            f"{cfg['subdir']}/{zip_path.name}"
                            if cfg["subdir"]
                            else zip_path.name
                        )
                        source_hash = sha256_file(zip_path)
                        if is_source_loaded(conn, source_key, source_hash):
                            log.info("Ya cargado, se omite: %s", source_key)
                            continue
                        log.info("Procesando %s (%s)", source_key, cfg["tipo_entidad"])
                        df = parse_fn(zip_path, EXTRACT_DIR, cfg["tipo_entidad"])
                        df["source_file"] = source_key
                        upsert_fn(conn, df)
                        register_source_file(conn, source_key, source_hash, report_type)
                        conn.commit()
        refresh_marts(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_seps(
    years: list[int], base_dir: Path = SEPS_DIR, descargar: bool = True
) -> None:
    """SEPS (cooperativas S1-S3 + mutualistas): descarga directa + 3 reportes por año que
    conforman contra tablas ya existentes (docs/fuentes_datos.md sección 4.0).

    Orden por año: EEFF primero, porque trae la razón social completa. Así, una entidad
    nueva (no vista antes por BCE) se registra en staging.banco_maestro con ese nombre y
    no con la abreviatura de los reportes. Después van captaciones y colocaciones. Cada
    archivo se commitea por separado y se registra en meta.source_files con clave
    'seps/{año}/{archivo}', así que una re-corrida salta lo ya cargado."""
    if descargar:
        download_seps(years, base_dir)
    conn = get_connection()
    try:
        for year in years:
            for reporte in ("eeff", "captaciones", "colocaciones"):
                report_dir = base_dir / str(year) / reporte
                zips = sorted(report_dir.glob("*.zip")) if report_dir.exists() else []
                if not zips:
                    log.warning("No existe %s, se omite", report_dir)
                    continue
                for zip_path in zips:
                    source_key = f"seps/{year}/{zip_path.name}"
                    source_hash = sha256_file(zip_path)
                    if is_source_loaded(conn, source_key, source_hash):
                        log.info("Ya cargado, se omite: %s", source_key)
                        continue
                    log.info("Procesando %s", source_key)
                    if reporte == "eeff":
                        r = parse_seps_eeff_file(zip_path)
                        upsert_banco_maestro_ruc(conn, r["entidades"])
                        insert_dim_cuenta_contable_seps(conn, r["cuentas"])
                        for df in (r["balance"], r["pyg"]):
                            df["source_file"] = source_key
                        upsert_staging_boletin_balance(conn, r["balance"])
                        upsert_staging_boletin_pyg(conn, r["pyg"])
                        register_source_file(
                            conn, source_key, source_hash, "boletin_balance"
                        )
                    else:
                        parse_fn, table, upsert_fn = {
                            "captaciones": (
                                parse_seps_captaciones_file,
                                "depositos",
                                upsert_staging_depositos,
                            ),
                            "colocaciones": (
                                parse_seps_colocaciones_file,
                                "cartera",
                                upsert_staging_cartera,
                            ),
                        }[reporte]
                        df, entidades = parse_fn(zip_path, EXTRACT_DIR)
                        df["source_file"] = source_key
                        upsert_banco_maestro_ruc(conn, entidades)
                        upsert_fn(conn, df)
                        register_source_file(conn, source_key, source_hash, table)
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
    src/benchmark_bancos/transform/parse_bce_tasas.py): raw.* captura las 6 categorías del sistema
    financiero tal cual (read_raw), staging.* resuelve identidad y agrega para TODAS
    (parse_tsp_file/parse_tsa_file) -- bancos privados vía crosswalk curado, el resto
    auto-registrado por RUC en staging.banco_maestro; el RUC se guarda para todas,
    privados incluidos (upsert_banco_maestro_ruc, ver sql/17)."""
    files = download_bce_all(base_dir)
    conn = get_connection()
    try:
        for clave, report_type, parse_fn, upsert_fn in (
            (
                "tsp",
                "bce_tasas_pasivas",
                parse_tsp_file,
                upsert_staging_bce_tasas_pasivas,
            ),
            (
                "tsa",
                "bce_tasas_activas",
                parse_tsa_file,
                upsert_staging_bce_tasas_activas,
            ),
        ):
            zip_path = files[clave]
            source_hash = sha256_file(zip_path)
            if is_source_loaded(conn, zip_path.name, source_hash):
                log.info("Ya cargado, se omite: %s", zip_path.name)
                continue
            log.info("Procesando %s (sin filtrar tipo_entidad)", zip_path.name)
            df_raw = read_raw_bce(zip_path)
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


_NOMBRE_ARCHIVO = re.compile(r"TasasVigentes(\d{2})(\d{4})\.htm$")
# Primer mes que entiende parse_tasas_historicas (2026-10-09; antes 2022-04). Antes de
# 2009-07 la página trae segmentos que ya no existen en el catálogo (Comercial
# Corporativo, Microcrédito de Subsistencia, ...) y tablas de 6-7 columnas.
_TASAS_HISTORICAS_DESDE = datetime.date(2009, 7, 1)
# Meses sueltos con un formato que no vale la pena soportar (se omiten sin ERROR para que
# la corrida semanal no termine siempre con código 2). 2009-09: tabla de 5 columnas donde
# la quinta repite la cuarta solo en parte de las filas.
_TASAS_HISTORICAS_EXCLUIDAS = {"TasasVigentes092009.htm"}


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


def _log_segmentos_tasas_sin_catalogo(conn) -> None:
    """fact_tasas_referenciales_cartera/_depositos_instrumento unen por nombre contra
    dim_subsegmento_credito/dim_categoria_deposito (INNER JOIN): un nombre con otra
    escritura se descartaba sin aviso (pasó con los dobles espacios de 2009-2020). ERROR para que
    la corrida termine con código 2 y se agregue el alias en parse_tasas_historicas."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.dimension_valor, count(*), min(s.fecha), max(s.fecha)
            FROM staging.tasas_referenciales s
            WHERE (s.seccion IN ('activa_maxima', 'activa_referencial')
                   AND NOT EXISTS (SELECT 1 FROM marts.dim_subsegmento_credito d
                                   WHERE d.subsegmento = s.dimension_valor))
               OR (s.seccion = 'pasiva_instrumento'
                   AND NOT EXISTS (SELECT 1 FROM marts.dim_categoria_deposito d
                                   WHERE d.categoria = s.dimension_valor))
            GROUP BY 1 ORDER BY 1
            """
        )
        for segmento, filas, desde, hasta in cur.fetchall():
            log.error(
                "TasasHistorico: '%s' (%d filas, %s a %s) no está en "
                "dim_subsegmento_credito / dim_categoria_deposito: agregar el alias en "
                "parse_tasas_historicas (_SEGMENTO_ALIAS / _CATEGORIA_ALIAS)",
                segmento,
                filas,
                desde,
                hasta,
            )


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
                log.error("%s, se omite", e)
                continue
            if (
                fecha < _TASAS_HISTORICAS_DESDE
                or path.name in _TASAS_HISTORICAS_EXCLUIDAS
            ):
                # Layout HTML anterior, no soportado por el parser (ver "Alcance de los
                # datos" en el README). Sin este corte se reintentaban ~170 páginas en
                # cada corrida y llenaban el log de WARNING (2026-10-09).
                log.debug("Anterior al layout soportado, se omite: %s", path.name)
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
                # ERROR (2026-10-09): desde _TASAS_HISTORICAS_DESDE el layout es el
                # soportado, así que una falla acá es un mes publicado que no se cargó
                # y la corrida debe terminar con código 2.
                log.error(
                    "No se pudo parsear %s (layout distinto), se omite: %s",
                    path.name,
                    e,
                )
                continue
            upsert_staging_tasas_referenciales(conn, df)
            register_source_file(conn, path.name, source_hash, "tasas_referenciales")
            conn.commit()
        refresh_marts(conn)
        conn.commit()
        _log_segmentos_tasas_sin_catalogo(conn)
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
                    log.error("%s, se omite", e)
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
                    # ERROR (2026-10-09): un boletín publicado que no se pudo cargar;
                    # la corrida termina con código 2 en vez de 0.
                    log.error(
                        "No se pudo parsear %s (layout/banco distinto), se omite: %s",
                        zip_path.name,
                        e,
                    )
                    continue
                upsert_dim_cuenta_contable(conn, result["cuentas"])
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


def refresh(full: bool = False) -> None:
    """Recalcula solo marts.* desde staging, sin leer archivos (p.ej. tras curar un seed
    o aplicar una migración que cambia la lógica de refresh). Incremental por defecto;
    `full=True` recalcula todo staging."""
    conn = get_connection()
    try:
        refresh_marts(conn, full=full)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
