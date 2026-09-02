"""
Carga idempotente a Postgres: raw (JSONB tal cual) -> staging (tipado) -> marts (estrella).

Idempotencia:
- raw.source_files evita reprocesar un archivo cuyo hash ya fue cargado.
- staging.* tiene UNIQUE en la llave natural -> INSERT ... ON CONFLICT DO UPDATE, con un
  guard `WHERE row_hash IS DISTINCT FROM EXCLUDED.row_hash` para que una fila sin cambios
  reales no dispare un UPDATE (row_hash es una columna GENERATED que cubre solo las
  columnas mutables, no la llave natural -- ver sql/05_dim_banco_rework.sql).
- marts.* se reconstruye desde staging con la misma técnica, así que correr el
  pipeline varias veces (o solo para un año) siempre converge al mismo resultado.
- La identidad de banco (banco_codigo) se resuelve en etl/transform/banco_matching.py
  ANTES de llegar a staging -- marts.dim_banco no es más que un catálogo poblado desde
  staging.banco_maestro (sembrado desde etl/seeds/banco_maestro.csv), sin tabla de alias.
"""

import csv
import json
import logging
from pathlib import Path

import pandas as pd
import psycopg

from etl.config import DB_CONFIG

log = logging.getLogger(__name__)

_SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"


def get_connection() -> psycopg.Connection:
    return psycopg.connect(**DB_CONFIG, autocommit=False)


def is_source_loaded(conn, source_file: str, source_hash: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM raw.source_files WHERE source_file = %s AND source_hash = %s",
            (source_file, source_hash),
        )
        return cur.fetchone() is not None


def register_source_file(
    conn, source_file: str, source_hash: str, report_type: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.source_files (source_file, source_hash, report_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (source_file) DO UPDATE SET source_hash = EXCLUDED.source_hash, loaded_at = now()
            """,
            (source_file, source_hash, report_type),
        )


def _clean(value):
    """pandas usa NaN para valores faltantes incluso en columnas de texto; json.dumps
    serializa NaN como el token literal `NaN`, que no es JSON válido para Postgres."""
    return None if pd.isna(value) else value


def load_raw(conn, table: str, df: pd.DataFrame, anio: int) -> None:
    payload_cols = [c for c in df.columns if c not in ("source_file", "source_hash")]
    rows = [
        (
            row["source_file"],
            row["source_hash"],
            anio,
            row["fecha"].month if pd.notna(row["fecha"]) else None,
            json.dumps({c: _clean(row[c]) for c in payload_cols}, default=str),
        )
        for _, row in df.iterrows()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO raw.{table} (source_file, source_hash, anio, mes, data) "
            f"VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    log.info("raw.%s: %d filas insertadas", table, len(rows))


def upsert_banco_maestro_ruc(conn, entidades: list[tuple[str, str, str, str]]) -> None:
    """Registra el RUC de TODAS las entidades resueltas por BCE (bancos privados
    incluidos) y auto-registra las no-privadas (cooperativas, mutualistas, banca pública,
    sociedad financiera, tarjetas de crédito) -- ver
    etl/transform/banco_matching.py::resolver_entidad_bce. `ON CONFLICT DO UPDATE SET
    ruc` únicamente: para bancos privados la fila ya existe (sembrada desde
    banco_maestro.csv) y no se toca `banco`/`tipo_entidad`, que siguen siendo dueños de
    ese valor -- load_banco_maestro_seed() los reafirma en cada refresh_marts(); para
    entidades nuevas, el INSERT las crea con banco/tipo_entidad/ruc de una vez.

    estado_validacion no se toca en el ON CONFLICT (se preserva el valor existente) y no
    se lista en el INSERT -- una fila nueva hereda el DEFAULT 'AUTO_INGRESADO' de
    staging.banco_maestro (sql/26_dim_banco_estado_validacion.sql) sin necesitar cambio
    de código acá; si esa fila resulta ser uno de los 33 curados y esta función la creó
    antes que load_banco_maestro_seed() corriera (orden posible en una base nueva),
    load_banco_maestro_seed() la corrige a CONFIRMADO más adelante en el mismo
    refresh_marts()."""
    if not entidades:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO staging.banco_maestro (banco_codigo, banco, tipo_entidad, ruc)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (banco_codigo) DO UPDATE SET ruc = EXCLUDED.ruc
            """,
            entidades,
        )
    log.info(
        "staging.banco_maestro: ruc actualizado/creado para %d entidades",
        len(entidades),
    )


def load_banco_maestro_seed(conn) -> None:
    """Siembra staging.banco_maestro desde etl/seeds/banco_maestro.csv -- el nombre a
    mostrar y tipo_entidad de cada banco_codigo, determinista sin importar qué variante
    de texto llegó primero durante la carga.

    estado_validacion = 'CONFIRMADO' siempre, en el INSERT y en el UPDATE del conflicto
    (sql/26_dim_banco_estado_validacion.sql): estos ~33 banco_codigo son exactamente los
    curados a mano en el CSV, así que cada corrida reafirma CONFIRMADO sin importar si la
    fila ya existía (curada de siempre) o si upsert_banco_maestro_ruc() la creó primero
    con el DEFAULT AUTO_INGRESADO (posible en una base nueva si load_bce() corre antes
    que este seed) -- refresh_marts() llama a esta función antes de correr
    _REFRESH_MARTS_SQL, así que el estado queda correcto antes de poblar marts.dim_banco."""
    with open(_SEEDS_DIR / "banco_maestro.csv", encoding="utf-8") as f:
        rows = [
            (r["banco_codigo"], r["banco"], r["tipo_entidad"])
            for r in csv.DictReader(f)
        ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO staging.banco_maestro (banco_codigo, banco, tipo_entidad, estado_validacion)
            VALUES (%s, %s, %s, 'CONFIRMADO')
            ON CONFLICT (banco_codigo) DO UPDATE SET
                banco = EXCLUDED.banco, tipo_entidad = EXCLUDED.tipo_entidad,
                estado_validacion = 'CONFIRMADO'
            """,
            rows,
        )
    log.info("staging.banco_maestro: %d filas sembradas", len(rows))


def upsert_staging_cartera(conn, df: pd.DataFrame) -> None:
    rows = [
        tuple(
            _clean(v)
            for v in (
                r.fecha,
                r.tipo_entidad,
                r.banco,
                r.banco_codigo,
                r.region,
                r.provincia,
                r.canton,
                r.tipo_credito,
                r.estado_cartera,
                r.saldo,
                r.source_file,
            )
        )
        for r in df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO staging.cartera
                (fecha, tipo_entidad, banco, banco_codigo, region, provincia, canton, tipo_credito, estado_cartera, saldo, source_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fecha, tipo_entidad, banco, COALESCE(canton, ''), tipo_credito, estado_cartera)
            DO UPDATE SET saldo = EXCLUDED.saldo, region = EXCLUDED.region,
                          provincia = EXCLUDED.provincia, source_file = EXCLUDED.source_file,
                          banco_codigo = EXCLUDED.banco_codigo, fecha_actualizacion = now()
            WHERE staging.cartera.row_hash IS DISTINCT FROM EXCLUDED.row_hash
            """,
            rows,
        )
    log.info("staging.cartera: %d filas upsert", len(rows))


def upsert_staging_depositos(conn, df: pd.DataFrame) -> None:
    rows = [
        tuple(
            _clean(v)
            for v in (
                r.fecha,
                r.tipo_entidad,
                r.banco,
                r.banco_codigo,
                r.region,
                r.provincia,
                r.canton,
                r.tipo_deposito,
                r.categoria_deposito,
                r.plazo_dias_desde,
                r.plazo_dias_hasta,
                r.saldo,
                r.numero_clientes,
                r.numero_cuentas,
                r.source_file,
            )
        )
        for r in df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO staging.depositos
                (fecha, tipo_entidad, banco, banco_codigo, region, provincia, canton, tipo_deposito,
                 categoria_deposito, plazo_dias_desde, plazo_dias_hasta, saldo, numero_clientes, numero_cuentas, source_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fecha, tipo_entidad, banco, COALESCE(canton, ''), tipo_deposito)
            DO UPDATE SET saldo = EXCLUDED.saldo, numero_clientes = EXCLUDED.numero_clientes,
                          numero_cuentas = EXCLUDED.numero_cuentas, region = EXCLUDED.region,
                          provincia = EXCLUDED.provincia, source_file = EXCLUDED.source_file,
                          banco_codigo = EXCLUDED.banco_codigo,
                          categoria_deposito = EXCLUDED.categoria_deposito,
                          plazo_dias_desde = EXCLUDED.plazo_dias_desde,
                          plazo_dias_hasta = EXCLUDED.plazo_dias_hasta,
                          fecha_actualizacion = now()
            WHERE staging.depositos.row_hash IS DISTINCT FROM EXCLUDED.row_hash
            """,
            rows,
        )
    log.info("staging.depositos: %d filas upsert", len(rows))


def _copy_rows(conn, copy_sql: str, rows) -> int:
    """COPY es ~10-100x más rápido que executemany para los volúmenes de BCE (cientos de
    miles de filas por archivo, todo el histórico semanal 2008-2026 en un solo CSV)."""
    n = 0
    with conn.cursor() as cur:
        with cur.copy(copy_sql) as copy:
            for row in rows:
                copy.write_row(row)
                n += 1
    return n


def load_raw_bce(conn, table: str, df: pd.DataFrame, payload_cols: list[str]) -> None:
    rows = (
        (
            r.source_file,
            r.source_hash,
            r.fecha.year,
            r.fecha.month,
            json.dumps({c: _clean(getattr(r, c)) for c in payload_cols}, default=str),
        )
        for r in df.itertuples(index=False)
    )
    n = _copy_rows(
        conn,
        f"COPY raw.{table} (source_file, source_hash, anio, mes, data) FROM STDIN",
        rows,
    )
    log.info("raw.%s: %d filas insertadas", table, n)


_BCE_INT_COLS = {"plazo_dias_desde", "plazo_dias_hasta", "numero_operaciones"}


def _upsert_bce_via_temp(
    conn, df: pd.DataFrame, table: str, cols: list[str], key_cols: list[str]
) -> None:
    """COPY a una tabla temporal (misma sesión, se descarta sola) y de ahí INSERT ...
    ON CONFLICT DO UPDATE con guard de row_hash -- COPY no soporta ON CONFLICT
    directamente, así que no se puede COPY directo a staging.*."""
    df = df.copy()
    for c in _BCE_INT_COLS & set(cols):
        df[c] = df[c].astype(
            "Int64"
        )  # nullable -- evita que NaN vuelva float la columna (COPY rechaza '60.0' en INT)

    with conn.cursor() as cur:
        cur.execute(
            f"CREATE TEMP TABLE _tmp_{table} (LIKE staging.{table} INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        cur.execute(f"ALTER TABLE _tmp_{table} DROP COLUMN IF EXISTS id")

    rows = (
        tuple(_clean(getattr(r, c)) for c in cols) for r in df.itertuples(index=False)
    )
    cols_sql = ", ".join(cols)
    _copy_rows(conn, f"COPY _tmp_{table} ({cols_sql}) FROM STDIN", rows)

    set_cols = [c for c in cols if c not in key_cols]
    set_clause = (
        ", ".join(f"{c} = EXCLUDED.{c}" for c in set_cols)
        + ", fecha_actualizacion = now()"
    )
    key_expr = ", ".join(
        (
            f"COALESCE({c}, -1)"
            if c in ("plazo_dias_hasta",)
            else (f"COALESCE({c}, '')" if c == "provincia" else c)
        )
        for c in key_cols
    )
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO staging.{table} ({cols_sql})
            SELECT {cols_sql} FROM _tmp_{table}
            ON CONFLICT ({key_expr})
            DO UPDATE SET {set_clause}
            WHERE staging.{table}.row_hash IS DISTINCT FROM EXCLUDED.row_hash
            """
        )
    log.info("staging.%s: %d filas upsert", table, len(df))


_BCE_TASAS_PASIVAS_COLS = [
    "fecha",
    "banco_codigo",
    "categoria_deposito",
    "plazo_dias_desde",
    "plazo_dias_hasta",
    "plazo_codigo",
    "provincia",
    "monto_total",
    "numero_operaciones",
    "tasa_pasiva_efectiva",
    "tasa_nominal",
    "tipo_segmento",
    "source_file",
]
_BCE_TASAS_ACTIVAS_COLS = [
    "fecha",
    "banco_codigo",
    "segmento_credito",
    "plazo_dias_desde",
    "plazo_dias_hasta",
    "plazo_codigo",
    "provincia",
    "monto_total",
    "numero_operaciones",
    "tasa_activa_efectiva",
    "tasa_nominal",
    "tipo_segmento",
    "source_file",
]


def load_raw_tasas_referenciales(conn, df: pd.DataFrame, source_hash: str) -> None:
    """Volumen pequeño (~40 filas/mes x ~222 meses -- miles, no millones), executemany
    alcanza sin necesidad de COPY como en BCE tsp/tsa. A diferencia de tsp/tsa (un solo
    archivo acumulativo), acá cada mes es un archivo separado -- source_hash se calcula
    por archivo en el llamador (igual que CAPCOL)."""
    payload_cols = [c for c in df.columns if c != "source_file"]
    rows = [
        (
            r.source_file,
            source_hash,
            r.fecha.year,
            r.fecha.month,
            json.dumps({c: _clean(getattr(r, c)) for c in payload_cols}, default=str),
        )
        for r in df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO raw.tasas_referenciales (source_file, source_hash, anio, mes, data) VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    log.info("raw.tasas_referenciales: %d filas insertadas", len(rows))


def upsert_staging_tasas_referenciales(conn, df: pd.DataFrame) -> None:
    rows = [
        tuple(
            _clean(v)
            for v in (
                r.fecha,
                r.seccion,
                r.dimension_valor,
                r.plazo_dias_desde,
                r.plazo_dias_hasta,
                r.metrica,
                r.valor,
                r.source_file,
            )
        )
        for r in df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO staging.tasas_referenciales
                (fecha, seccion, dimension_valor, plazo_dias_desde, plazo_dias_hasta, metrica, valor, source_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fecha, seccion, COALESCE(dimension_valor, ''), COALESCE(plazo_dias_desde, -1), COALESCE(plazo_dias_hasta, -1), metrica)
            DO UPDATE SET valor = EXCLUDED.valor, source_file = EXCLUDED.source_file, fecha_actualizacion = now()
            WHERE staging.tasas_referenciales.row_hash IS DISTINCT FROM EXCLUDED.row_hash
            """,
            rows,
        )
    log.info("staging.tasas_referenciales: %d filas upsert", len(rows))


def upsert_staging_bce_tasas_pasivas(conn, df: pd.DataFrame) -> None:
    key_cols = [
        "fecha",
        "banco_codigo",
        "categoria_deposito",
        "plazo_dias_desde",
        "plazo_dias_hasta",
        "provincia",
    ]
    _upsert_bce_via_temp(
        conn, df, "bce_tasas_pasivas", _BCE_TASAS_PASIVAS_COLS, key_cols
    )


def upsert_staging_bce_tasas_activas(conn, df: pd.DataFrame) -> None:
    key_cols = [
        "fecha",
        "banco_codigo",
        "segmento_credito",
        "plazo_dias_desde",
        "plazo_dias_hasta",
        "provincia",
    ]
    _upsert_bce_via_temp(
        conn, df, "bce_tasas_activas", _BCE_TASAS_ACTIVAS_COLS, key_cols
    )


def upsert_staging_operaciones_especiales(conn, df: pd.DataFrame) -> None:
    """Inserta las filas de operaciones_especiales.xlsx en staging.bce_tasas_activas con
    es_operacion_especial='SI' (la columna y la llave única ya la contemplan, sql/28).
    `df` viene del parser parse_operaciones_especiales.py con la misma forma que
    _BCE_TASAS_ACTIVAS_COLS + es_operacion_especial; el flag entra a la llave para que
    conviva con filas 'NO' del mismo grano."""
    cols = _BCE_TASAS_ACTIVAS_COLS + ["es_operacion_especial"]
    key_cols = [
        "fecha",
        "banco_codigo",
        "segmento_credito",
        "plazo_dias_desde",
        "plazo_dias_hasta",
        "provincia",
        "es_operacion_especial",
    ]
    _upsert_bce_via_temp(conn, df, "bce_tasas_activas", cols, key_cols)


def upsert_dim_cuenta_contable(conn, cuentas_df: pd.DataFrame) -> None:
    """Plan de cuentas descubierto en cada archivo del Boletín -- volumen pequeño
    (~1500 cuentas), executemany alcanza. grupo_met se actualiza si el archivo nuevo trae
    un valor donde antes no había (no se pisa un grupo ya conocido con NULL)."""
    rows = [
        tuple(
            _clean(v)
            for v in (
                r.reporte,
                r.codigo,
                r.cuenta,
                r.nivel,
                r.codigo_padre,
                r.seccion,
                r.grupo_met,
            )
        )
        for r in cuentas_df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO marts.dim_cuenta_contable (reporte, codigo, cuenta, nivel, codigo_padre, seccion, grupo_met)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (reporte, codigo) DO UPDATE SET
                cuenta = EXCLUDED.cuenta, nivel = EXCLUDED.nivel, codigo_padre = EXCLUDED.codigo_padre,
                seccion = EXCLUDED.seccion,
                grupo_met = COALESCE(marts.dim_cuenta_contable.grupo_met, EXCLUDED.grupo_met)
            """,
            rows,
        )
    log.info("marts.dim_cuenta_contable: %d filas upsert", len(rows))


def load_raw_boletin(conn, table: str, df: pd.DataFrame, source_hash: str) -> None:
    payload_cols = [c for c in df.columns if c not in ("source_file",)]
    rows = (
        (
            r.source_file,
            source_hash,
            r.fecha.year,
            r.fecha.month,
            json.dumps({c: _clean(getattr(r, c)) for c in payload_cols}, default=str),
        )
        for r in df.itertuples(index=False)
    )
    n = _copy_rows(
        conn,
        f"COPY raw.{table} (source_file, source_hash, anio, mes, data) FROM STDIN",
        rows,
    )
    log.info("raw.%s: %d filas insertadas", table, n)


def _upsert_boletin_via_temp(
    conn, df: pd.DataFrame, table: str, cols: list[str], valor_col: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE TEMP TABLE _tmp_{table} (LIKE staging.{table} INCLUDING DEFAULTS) ON COMMIT DROP"
        )
        cur.execute(f"ALTER TABLE _tmp_{table} DROP COLUMN IF EXISTS id")

    rows = (
        tuple(_clean(getattr(r, c)) for c in cols) for r in df.itertuples(index=False)
    )
    cols_sql = ", ".join(cols)
    _copy_rows(conn, f"COPY _tmp_{table} ({cols_sql}) FROM STDIN", rows)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO staging.{table} ({cols_sql})
            SELECT {cols_sql} FROM _tmp_{table}
            ON CONFLICT (fecha, banco_codigo, codigo)
            DO UPDATE SET {valor_col} = EXCLUDED.{valor_col}, source_file = EXCLUDED.source_file, fecha_actualizacion = now()
            WHERE staging.{table}.row_hash IS DISTINCT FROM EXCLUDED.row_hash
            """
        )
    log.info("staging.%s: %d filas upsert", table, len(df))


_BOLETIN_BALANCE_COLS = [
    "fecha",
    "banco",
    "banco_codigo",
    "codigo",
    "saldo_usd",
    "source_file",
]
_BOLETIN_PYG_COLS = [
    "fecha",
    "banco",
    "banco_codigo",
    "codigo",
    "valor_usd",
    "source_file",
]


def upsert_staging_boletin_balance(conn, df: pd.DataFrame) -> None:
    _upsert_boletin_via_temp(
        conn, df, "boletin_balance", _BOLETIN_BALANCE_COLS, "saldo_usd"
    )


def upsert_staging_boletin_pyg(conn, df: pd.DataFrame) -> None:
    _upsert_boletin_via_temp(conn, df, "boletin_pyg", _BOLETIN_PYG_COLS, "valor_usd")


_REFRESH_MARTS_SQL = """
-- dim_fecha: grano día (fecha_id = YYYYMMDD), conformed dimension única para grano
-- mensual (CAPCOL/Boletín) y semanal (BCE, cuando se sumen sus fact tables). anio_mes
-- es la llave de roll-up para comparar ambos grano sin joins adicionales.
INSERT INTO marts.dim_fecha (fecha_id, fecha, anio, mes, dia, trimestre, nombre_mes, anio_mes)
SELECT DISTINCT
    TO_CHAR(fecha, 'YYYYMMDD')::INT,
    fecha,
    EXTRACT(YEAR FROM fecha)::INT,
    EXTRACT(MONTH FROM fecha)::INT,
    EXTRACT(DAY FROM fecha)::INT,
    EXTRACT(QUARTER FROM fecha)::INT,
    TO_CHAR(fecha, 'TMMonth'),
    (EXTRACT(YEAR FROM fecha) * 100 + EXTRACT(MONTH FROM fecha))::INT
FROM (
    SELECT fecha FROM staging.cartera
    UNION SELECT fecha FROM staging.depositos
    UNION SELECT fecha FROM staging.bce_tasas_pasivas
    UNION SELECT fecha FROM staging.bce_tasas_activas
    UNION SELECT fecha FROM staging.tasas_referenciales
    UNION SELECT fecha FROM staging.boletin_balance
    UNION SELECT fecha FROM staging.boletin_pyg
) f
ON CONFLICT (fecha_id) DO NOTHING;

-- dim_banco: identidad ya resuelta en staging.banco_codigo (etl/transform/banco_matching.py);
-- el nombre a mostrar y tipo_entidad vienen de staging.banco_maestro (sembrado desde
-- etl/seeds/banco_maestro.csv), no de cualquier texto crudo que haya llegado primero.
-- estado_validacion (sql/26_dim_banco_estado_validacion.sql) se copia de
-- staging.banco_maestro tal cual -- CONFIRMADO para los 33 curados (reafirmado en cada
-- corrida por load_banco_maestro_seed(), llamado justo antes que esta sentencia dentro
-- de refresh_marts()), AUTO_INGRESADO para las ~409 entidades auto-registradas por RUC.
--
-- segmento_entidad_id SÍ va en el SELECT/columna del INSERT (leído de la propia
-- marts.dim_banco vía el LEFT JOIN de abajo) aunque esta sentencia nunca lo escribe en
-- el SET del ON CONFLICT -- esa columna es propiedad del UPDATE separado más abajo
-- (SCD1 desde los hechos BCE). Bug real encontrado y corregido 2026-08-30 al verificar
-- CDC no-op para esta migración: como segmento_entidad_id NO estaba en la lista de
-- columnas del INSERT, Postgres computaba `EXCLUDED.segmento_entidad_id` como NULL (el
-- DEFAULT de una columna omitida en el INSERT, no el valor real de la fila en conflicto)
-- -- eso hacía que `EXCLUDED.row_hash` (columna GENERATED, se recalcula para EXCLUDED
-- también) casi nunca coincidiera con `marts.dim_banco.row_hash` real para cualquier
-- banco con segmento_entidad_id ya poblado (prácticamente los 442), disparando un
-- UPDATE real (`fecha_actualizacion = now()`) en CADA corrida de refresh_marts(), no
-- solo cuando algo cambiaba de verdad. Preexistía desde sql/19_dim_segmento_entidad.sql
-- (2026-07-25) -- no lo introdujo esta migración, solo quedó expuesto al verificar CDC
-- no-op de punta a punta en vez de asumirlo. Con el LEFT JOIN, una fila nueva sigue
-- resolviendo segmento_entidad_id = NULL correctamente (no hay fila existente que unir).
INSERT INTO marts.dim_banco (banco_codigo, banco, tipo_entidad, ruc, estado_validacion, segmento_entidad_id)
SELECT bm.banco_codigo, bm.banco, bm.tipo_entidad, bm.ruc, bm.estado_validacion, existente.segmento_entidad_id
FROM staging.banco_maestro bm
LEFT JOIN marts.dim_banco existente ON existente.banco_codigo = bm.banco_codigo
WHERE bm.banco_codigo IN (
    SELECT DISTINCT banco_codigo FROM staging.cartera WHERE tipo_entidad = 'BANCO PRIVADO'
    UNION
    SELECT DISTINCT banco_codigo FROM staging.depositos WHERE tipo_entidad = 'BANCO PRIVADO'
    UNION
    SELECT DISTINCT banco_codigo FROM staging.bce_tasas_pasivas
    UNION
    SELECT DISTINCT banco_codigo FROM staging.bce_tasas_activas
    UNION
    SELECT DISTINCT banco_codigo FROM staging.boletin_balance
    UNION
    SELECT DISTINCT banco_codigo FROM staging.boletin_pyg
)
ON CONFLICT (banco_codigo) DO UPDATE SET
    banco = EXCLUDED.banco, tipo_entidad = EXCLUDED.tipo_entidad, ruc = EXCLUDED.ruc,
    estado_validacion = EXCLUDED.estado_validacion, fecha_actualizacion = now()
WHERE marts.dim_banco.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

-- translate() en vez de igualdad exacta: CAPCOL no es 100% consistente en su propia
-- ortografía sin tilde (ver sql/20_dim_provincia.sql) -- normalize_provincia() en Python
-- ya homologa las filas nuevas, esto es una red de seguridad adicional en SQL.
--
-- BUG conocido de este INNER JOIN (encontrado 2026-08-30, ver _log_cantones_no_resueltos
-- más abajo): una fila de staging.cartera/depositos cuya `provincia` no matchea contra
-- dim_provincia (ni exacto ni via translate()) se descarta acá SIN error ni fila
-- huérfana visible -- el INNER JOIN simplemente no la selecciona. refresh_marts()
-- corre _log_cantones_no_resueltos(conn) inmediatamente antes de este SQL para que ese
-- descarte, si ocurre, quede en el log de cualquier corrida normal en vez de ser
-- silencioso -- ver el docstring de esa función para la justificación de por qué es
-- log-only y no un staging.catalogo_rechazos dedicado.
INSERT INTO marts.dim_canton (canton, provincia_id)
SELECT DISTINCT c.canton, dp.provincia_id FROM (
    SELECT canton, provincia FROM staging.cartera
    UNION
    SELECT canton, provincia FROM staging.depositos
) c
JOIN marts.dim_provincia dp ON dp.provincia = translate(c.provincia, 'ÁÉÍÓÚ', 'AEIOU')
WHERE c.canton IS NOT NULL
ON CONFLICT (canton, provincia_id) DO NOTHING;

-- dim_plazo: catálogo abierto por rango numérico, auto-descubierto desde cada fuente.
-- No se fuerza una equivalencia falsa entre esquemas de plazo que no calzan entre
-- fuentes (ej. CAPCOL "DE MÁS DE 361 DÍAS" vs. tsp "g. MAS DE 360 DIAS" quedan como
-- filas distintas, cada una con su propio límite real).
INSERT INTO marts.dim_plazo (dias_desde, dias_hasta, plazo_codigo)
SELECT DISTINCT plazo_dias_desde, plazo_dias_hasta, tipo_deposito
FROM staging.depositos
WHERE plazo_dias_desde IS NOT NULL
ON CONFLICT (dias_desde, COALESCE(dias_hasta, -1)) DO NOTHING;

INSERT INTO marts.dim_plazo (dias_desde, dias_hasta, plazo_codigo)
SELECT DISTINCT plazo_dias_desde, plazo_dias_hasta, plazo_codigo FROM staging.bce_tasas_pasivas
ON CONFLICT (dias_desde, COALESCE(dias_hasta, -1)) DO NOTHING;

INSERT INTO marts.dim_plazo (dias_desde, dias_hasta, plazo_codigo)
SELECT DISTINCT plazo_dias_desde, plazo_dias_hasta, plazo_codigo FROM staging.bce_tasas_activas
ON CONFLICT (dias_desde, COALESCE(dias_hasta, -1)) DO NOTHING;

INSERT INTO marts.dim_plazo (dias_desde, dias_hasta, plazo_codigo)
SELECT DISTINCT plazo_dias_desde, plazo_dias_hasta, NULL FROM staging.tasas_referenciales
WHERE seccion = 'pasiva_plazo'
ON CONFLICT (dias_desde, COALESCE(dias_hasta, -1)) DO NOTHING;

-- tipo_credito de CAPCOL (6 valores, snake_case) es el nombre coloquial del mismo
-- segmento normativo grueso que usa marts.dim_segmento_credito (7 valores, MAYÚSCULAS
-- regulatorias) -- se resuelve aquí en vez de duplicar la columna como texto suelto.
-- estado_cartera ya no es dimensión degenerada -- son 3 medidas columnares del mismo
-- grano (fecha, banco, cantón, segmento), ver sql/21_fact_saldo_cartera_pivot.sql.
INSERT INTO marts.fact_saldo_cartera
    (fecha_id, banco_id, canton_id, segmento_id, saldo_por_vencer, saldo_no_devenga_intereses, saldo_vencida)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.banco_id,
    c.canton_id,
    sg.segmento_id,
    COALESCE(SUM(s.saldo) FILTER (WHERE s.estado_cartera = 'por_vencer'), 0),
    COALESCE(SUM(s.saldo) FILTER (WHERE s.estado_cartera = 'no_devenga_intereses'), 0),
    COALESCE(SUM(s.saldo) FILTER (WHERE s.estado_cartera = 'vencida'), 0)
FROM staging.cartera s
JOIN marts.dim_banco b ON b.banco_codigo = s.banco_codigo
LEFT JOIN marts.dim_provincia dp ON dp.provincia = translate(s.provincia, 'ÁÉÍÓÚ', 'AEIOU')
LEFT JOIN marts.dim_canton c ON c.canton = s.canton AND c.provincia_id = dp.provincia_id
JOIN marts.dim_segmento_credito sg ON sg.segmento = CASE s.tipo_credito
    WHEN 'comercial' THEN 'PRODUCTIVO'
    WHEN 'consumo' THEN 'CONSUMO'
    WHEN 'inmobiliario' THEN 'INMOBILIARIO'
    WHEN 'microcredito' THEN 'MICROCRÉDITO'
    WHEN 'vivienda_interes_publico' THEN 'VIVIENDA DE INTERÉS PÚBLICO'
    WHEN 'educativo' THEN 'EDUCATIVO'
END
WHERE s.tipo_entidad = 'BANCO PRIVADO'
GROUP BY TO_CHAR(s.fecha, 'YYYYMMDD')::INT, b.banco_id, c.canton_id, sg.segmento_id
ON CONFLICT (fecha_id, banco_id, COALESCE(canton_id, -1), segmento_id)
DO UPDATE SET saldo_por_vencer = EXCLUDED.saldo_por_vencer,
              saldo_no_devenga_intereses = EXCLUDED.saldo_no_devenga_intereses,
              saldo_vencida = EXCLUDED.saldo_vencida,
              fecha_actualizacion = now()
WHERE marts.fact_saldo_cartera.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

INSERT INTO marts.fact_saldo_depositos (fecha_id, banco_id, canton_id, categoria_deposito_id, plazo_id, saldo, numero_clientes, numero_cuentas)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.banco_id,
    c.canton_id,
    cd.categoria_deposito_id,
    pl.plazo_id,
    s.saldo,
    s.numero_clientes,
    s.numero_cuentas
FROM staging.depositos s
JOIN marts.dim_banco b ON b.banco_codigo = s.banco_codigo
LEFT JOIN marts.dim_provincia dp ON dp.provincia = translate(s.provincia, 'ÁÉÍÓÚ', 'AEIOU')
LEFT JOIN marts.dim_canton c ON c.canton = s.canton AND c.provincia_id = dp.provincia_id
JOIN marts.dim_categoria_deposito cd ON cd.categoria = s.categoria_deposito
LEFT JOIN marts.dim_plazo pl ON pl.dias_desde = s.plazo_dias_desde
    AND pl.dias_hasta IS NOT DISTINCT FROM s.plazo_dias_hasta
WHERE s.tipo_entidad = 'BANCO PRIVADO'
ON CONFLICT (fecha_id, banco_id, canton_id, categoria_deposito_id, COALESCE(plazo_id, -1))
DO UPDATE SET saldo = EXCLUDED.saldo,
              numero_clientes = EXCLUDED.numero_clientes,
              numero_cuentas = EXCLUDED.numero_cuentas,
              fecha_actualizacion = now()
WHERE marts.fact_saldo_depositos.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

INSERT INTO marts.fact_captaciones_depositos
    (fecha_id, banco_id, categoria_deposito_id, plazo_id, provincia_id, monto_total, numero_operaciones, tasa_pasiva_efectiva, tasa_nominal, segmento_entidad_id)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.banco_id,
    cd.categoria_deposito_id,
    pl.plazo_id,
    dp.provincia_id,
    s.monto_total,
    s.numero_operaciones,
    s.tasa_pasiva_efectiva,
    s.tasa_nominal,
    se.segmento_entidad_id
FROM staging.bce_tasas_pasivas s
JOIN marts.dim_banco b ON b.banco_codigo = s.banco_codigo
JOIN marts.dim_categoria_deposito cd ON cd.categoria = s.categoria_deposito
JOIN marts.dim_plazo pl ON pl.dias_desde = s.plazo_dias_desde
    AND pl.dias_hasta IS NOT DISTINCT FROM s.plazo_dias_hasta
LEFT JOIN marts.dim_provincia dp ON dp.provincia = s.provincia
LEFT JOIN marts.dim_segmento_entidad se ON se.tipo_segmento = s.tipo_segmento
ON CONFLICT (fecha_id, banco_id, categoria_deposito_id, plazo_id, COALESCE(provincia_id, -1))
DO UPDATE SET monto_total = EXCLUDED.monto_total,
              numero_operaciones = EXCLUDED.numero_operaciones,
              tasa_pasiva_efectiva = EXCLUDED.tasa_pasiva_efectiva,
              tasa_nominal = EXCLUDED.tasa_nominal,
              segmento_entidad_id = EXCLUDED.segmento_entidad_id,
              fecha_actualizacion = now()
WHERE marts.fact_captaciones_depositos.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

INSERT INTO marts.fact_colocaciones_cartera
    (fecha_id, banco_id, subsegmento_id, plazo_id, provincia_id, monto_total, numero_operaciones, tasa_activa_efectiva, tasa_nominal, segmento_entidad_id, es_operacion_especial)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.banco_id,
    sg.subsegmento_id,
    pl.plazo_id,
    dp.provincia_id,
    s.monto_total,
    s.numero_operaciones,
    s.tasa_activa_efectiva,
    s.tasa_nominal,
    se.segmento_entidad_id,
    s.es_operacion_especial
FROM staging.bce_tasas_activas s
JOIN marts.dim_banco b ON b.banco_codigo = s.banco_codigo
JOIN marts.dim_subsegmento_credito sg ON sg.subsegmento = s.segmento_credito
JOIN marts.dim_plazo pl ON pl.dias_desde = s.plazo_dias_desde
    AND pl.dias_hasta IS NOT DISTINCT FROM s.plazo_dias_hasta
LEFT JOIN marts.dim_provincia dp ON dp.provincia = s.provincia
LEFT JOIN marts.dim_segmento_entidad se ON se.tipo_segmento = s.tipo_segmento
ON CONFLICT (fecha_id, banco_id, subsegmento_id, plazo_id, COALESCE(provincia_id, -1), es_operacion_especial)
DO UPDATE SET monto_total = EXCLUDED.monto_total,
              numero_operaciones = EXCLUDED.numero_operaciones,
              tasa_activa_efectiva = EXCLUDED.tasa_activa_efectiva,
              tasa_nominal = EXCLUDED.tasa_nominal,
              segmento_entidad_id = EXCLUDED.segmento_entidad_id,
              es_operacion_especial = EXCLUDED.es_operacion_especial,
              fecha_actualizacion = now()
WHERE marts.fact_colocaciones_cartera.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

-- dim_banco.segmento_entidad_id: conveniencia con la ÚLTIMA clasificación conocida (SCD
-- tipo 1) para análisis puntuales contra la situación actual, sin tener que ir a buscar
-- la fila más reciente en los hechos semanales. Se resuelve tomando la fecha más
-- reciente entre AMBOS hechos BCE (un banco puede aparecer solo en tsp o solo en tsa).
--
-- ADVERTENCIA de mantenimiento (bug real encontrado y corregido 2026-08-30 al agregar
-- estado_validacion, sql/26_dim_banco_estado_validacion.sql): el WHERE de abajo
-- RECALCULA a mano la misma expresión del row_hash GENERATED de marts.dim_banco (última
-- definición en sql/26) porque este UPDATE no pasa por INSERT...ON CONFLICT/EXCLUDED --
-- necesita decidir si vale la pena escribir ANTES de tocar la fila. Si esta fórmula
-- queda desincronizada de la definición real de row_hash (como pasó acá: se agregó
-- estado_validacion al GENERATED pero no aquí), la condición IS DISTINCT FROM queda
-- permanentemente en true para toda fila con segmento_entidad_id -- CDC roto en
-- silencio, cada refresh_marts() pisa fecha_actualizacion sin cambio real. Cualquier
-- migración futura que extienda marts.dim_banco.row_hash DEBE actualizar esta línea en
-- el mismo cambio, o este UPDATE deja de ser un no-op.
UPDATE marts.dim_banco b
SET segmento_entidad_id = latest.segmento_entidad_id, fecha_actualizacion = now()
FROM (
    SELECT DISTINCT ON (banco_id) banco_id, segmento_entidad_id
    FROM (
        SELECT banco_id, fecha_id, segmento_entidad_id FROM marts.fact_captaciones_depositos WHERE segmento_entidad_id IS NOT NULL
        UNION ALL
        SELECT banco_id, fecha_id, segmento_entidad_id FROM marts.fact_colocaciones_cartera WHERE segmento_entidad_id IS NOT NULL
    ) x
    ORDER BY banco_id, fecha_id DESC
) latest
WHERE b.banco_id = latest.banco_id
  AND b.row_hash IS DISTINCT FROM md5(b.banco || '|' || b.tipo_entidad || '|' || COALESCE(b.ruc, '') || '|' || COALESCE(latest.segmento_entidad_id::text, '') || '|' || b.estado_validacion);

-- TasasHistorico.htm: 4 tablas anchas, una por sección real (activa_maxima +
-- activa_referencial comparten grano segmento -> misma tabla). staging.tasas_referenciales
-- es la única tabla "larga" del proyecto (por sección/métrica) -- ver sql/12_schema_tasas_historicas.sql.
INSERT INTO marts.fact_tasas_referenciales_cartera (fecha_id, subsegmento_id, tasa_activa_maxima, tasa_activa_referencial)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    sg.subsegmento_id,
    MAX(s.valor) FILTER (WHERE s.seccion = 'activa_maxima'),
    MAX(s.valor) FILTER (WHERE s.seccion = 'activa_referencial')
FROM staging.tasas_referenciales s
JOIN marts.dim_subsegmento_credito sg ON sg.subsegmento = s.dimension_valor
WHERE s.seccion IN ('activa_maxima', 'activa_referencial')
GROUP BY TO_CHAR(s.fecha, 'YYYYMMDD')::INT, sg.subsegmento_id
ON CONFLICT (fecha_id, subsegmento_id)
DO UPDATE SET tasa_activa_maxima = EXCLUDED.tasa_activa_maxima,
              tasa_activa_referencial = EXCLUDED.tasa_activa_referencial,
              fecha_actualizacion = now()
WHERE marts.fact_tasas_referenciales_cartera.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

INSERT INTO marts.fact_tasas_referenciales_depositos_instrumento (fecha_id, categoria_deposito_id, tasa_pasiva_promedio)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    cd.categoria_deposito_id,
    s.valor
FROM staging.tasas_referenciales s
JOIN marts.dim_categoria_deposito cd ON cd.categoria = s.dimension_valor
WHERE s.seccion = 'pasiva_instrumento'
ON CONFLICT (fecha_id, categoria_deposito_id)
DO UPDATE SET tasa_pasiva_promedio = EXCLUDED.tasa_pasiva_promedio, fecha_actualizacion = now()
WHERE marts.fact_tasas_referenciales_depositos_instrumento.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

INSERT INTO marts.fact_tasas_referenciales_depositos_plazo (fecha_id, plazo_id, tasa_pasiva_referencial)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    pl.plazo_id,
    s.valor
FROM staging.tasas_referenciales s
JOIN marts.dim_plazo pl ON pl.dias_desde = s.plazo_dias_desde
    AND pl.dias_hasta IS NOT DISTINCT FROM s.plazo_dias_hasta
WHERE s.seccion = 'pasiva_plazo'
ON CONFLICT (fecha_id, plazo_id)
DO UPDATE SET tasa_pasiva_referencial = EXCLUDED.tasa_pasiva_referencial, fecha_actualizacion = now()
WHERE marts.fact_tasas_referenciales_depositos_plazo.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

INSERT INTO marts.fact_tasas_referenciales_sistema
    (fecha_id, tasa_pasiva_referencial_sistema, tasa_activa_referencial_sistema, tasa_legal, tasa_maxima_convencional)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    MAX(s.valor) FILTER (WHERE s.metrica = 'tasa_pasiva_referencial_sistema'),
    MAX(s.valor) FILTER (WHERE s.metrica = 'tasa_activa_referencial_sistema'),
    MAX(s.valor) FILTER (WHERE s.metrica = 'tasa_legal'),
    MAX(s.valor) FILTER (WHERE s.metrica = 'tasa_maxima_convencional')
FROM staging.tasas_referenciales s
WHERE s.seccion = 'sistema'
GROUP BY TO_CHAR(s.fecha, 'YYYYMMDD')::INT
ON CONFLICT (fecha_id)
DO UPDATE SET tasa_pasiva_referencial_sistema = EXCLUDED.tasa_pasiva_referencial_sistema,
              tasa_activa_referencial_sistema = EXCLUDED.tasa_activa_referencial_sistema,
              tasa_legal = EXCLUDED.tasa_legal,
              tasa_maxima_convencional = EXCLUDED.tasa_maxima_convencional,
              fecha_actualizacion = now()
WHERE marts.fact_tasas_referenciales_sistema.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

-- Boletín BALANCE/PYG -- dim_cuenta_contable se puebla directo desde Python
-- (upsert_dim_cuenta_contable, antes de refresh_marts) porque su llave (reporte, codigo)
-- no es un valor que se pueda derivar por SELECT DISTINCT de una sola columna staging
-- como el resto de catálogos auto-descubiertos.
INSERT INTO marts.fact_balance (fecha_id, banco_id, cuenta_id, saldo_usd)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.banco_id,
    cc.cuenta_id,
    s.saldo_usd
FROM staging.boletin_balance s
JOIN marts.dim_banco b ON b.banco_codigo = s.banco_codigo
JOIN marts.dim_cuenta_contable cc ON cc.reporte = 'BALANCE' AND cc.codigo = s.codigo
ON CONFLICT (fecha_id, banco_id, cuenta_id)
DO UPDATE SET saldo_usd = EXCLUDED.saldo_usd, fecha_actualizacion = now()
WHERE marts.fact_balance.row_hash IS DISTINCT FROM EXCLUDED.row_hash;

INSERT INTO marts.fact_pyg (fecha_id, banco_id, cuenta_id, valor_usd)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.banco_id,
    cc.cuenta_id,
    s.valor_usd
FROM staging.boletin_pyg s
JOIN marts.dim_banco b ON b.banco_codigo = s.banco_codigo
JOIN marts.dim_cuenta_contable cc ON cc.reporte = 'PYG' AND cc.codigo = s.codigo
ON CONFLICT (fecha_id, banco_id, cuenta_id)
DO UPDATE SET valor_usd = EXCLUDED.valor_usd, fecha_actualizacion = now()
WHERE marts.fact_pyg.row_hash IS DISTINCT FROM EXCLUDED.row_hash;
"""


def _log_cantones_no_resueltos(conn) -> None:
    """El INSERT de marts.dim_canton en _REFRESH_MARTS_SQL usa un INNER JOIN contra
    dim_provincia (provincia_id es NOT NULL en dim_canton, así que no puede ser un LEFT
    JOIN con NULL) -- toda fila de staging.cartera/staging.depositos cuya `provincia` no
    resuelve contra dim_provincia (ni exacto ni via translate(), ver el comentario sobre
    ese INSERT) queda descartada ahí sin error, sin fila huérfana, sin rastro. Bug real
    encontrado 2026-08-30 al revisar load_postgres.py, no una feature nueva.

    Se resuelve con logging (WARNING si hay filas afectadas, INFO si no), NO con una
    tabla staging.catalogo_rechazos: a diferencia de dim_plazo/banco_codigo (catálogos
    regulatorios cerrados donde un valor no resuelto significa un dato mal identificado
    que un analista podría contar como otra cosa), dim_canton es geografía de bajo riesgo
    -- el motivo de scope-out real ("agregar geografía sin curar caso por caso") no
    aplica acá; y a fecha de esta función, 0 filas de staging.cartera/staging.depositos
    caen en este caso (verificado contra la base viva, ver docs/gobernanza_datos.md).
    Construir infraestructura de rechazos persistente para un caso con 0 filas afectadas
    hoy sería sobre-ingeniería; si esta función alguna vez loguea un WARNING real, ESE es
    el momento de evaluar si hace falta algo más que un log."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.provincia, count(*) AS filas, count(DISTINCT c.canton) AS cantones
            FROM (
                SELECT canton, provincia FROM staging.cartera
                UNION ALL
                SELECT canton, provincia FROM staging.depositos
            ) c
            WHERE c.canton IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM marts.dim_provincia dp
                  WHERE dp.provincia = translate(c.provincia, 'ÁÉÍÓÚ', 'AEIOU')
              )
            GROUP BY c.provincia
            ORDER BY filas DESC
            """
        )
        rows = cur.fetchall()
    if rows:
        total_filas = sum(r[1] for r in rows)
        detalle = ", ".join(
            f"{provincia!r} ({filas} filas, {cantones} cantón(es) distintos)"
            for provincia, filas, cantones in rows
        )
        log.warning(
            "marts.dim_canton: %d fila(s) de staging.cartera/depositos con provincia "
            "NO resoluble contra marts.dim_provincia -- el INNER JOIN de refresh_marts() "
            "las va a DESCARTAR silenciosamente si esto no se corrige (%d provincia(s) "
            "distintas afectadas: %s)",
            total_filas,
            len(rows),
            detalle,
        )
    else:
        log.info(
            "marts.dim_canton: 0 filas con provincia no resoluble (verificado en esta corrida)"
        )


def refresh_marts(conn) -> None:
    load_banco_maestro_seed(conn)
    _log_cantones_no_resueltos(conn)
    with conn.cursor() as cur:
        cur.execute(_REFRESH_MARTS_SQL)
    log.info("marts.* actualizado desde staging")
