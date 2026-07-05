"""
Carga idempotente a Postgres: raw (JSONB tal cual) -> staging (tipado) -> marts (estrella).

Idempotencia:
- raw.source_files evita reprocesar un archivo cuyo hash ya fue cargado.
- staging.* tiene UNIQUE en la llave natural -> INSERT ... ON CONFLICT DO UPDATE.
- marts.* se reconstruye desde staging con la misma técnica, así que correr el
  pipeline varias veces (o solo para un año) siempre converge al mismo resultado.
"""

import json
import logging

import pandas as pd
import psycopg

from etl.config import DB_CONFIG

log = logging.getLogger(__name__)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(**DB_CONFIG, autocommit=False)


def is_source_loaded(conn, source_file: str, source_hash: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM raw.source_files WHERE source_file = %s AND source_hash = %s",
            (source_file, source_hash),
        )
        return cur.fetchone() is not None


def register_source_file(conn, source_file: str, source_hash: str, report_type: str) -> None:
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


def upsert_staging_cartera(conn, df: pd.DataFrame) -> None:
    rows = [
        tuple(_clean(v) for v in (
            r.fecha, r.tipo_entidad, r.banco, r.region, r.provincia, r.canton,
            r.tipo_credito, r.estado_cartera, r.saldo, r.source_file,
        ))
        for r in df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO staging.cartera
                (fecha, tipo_entidad, banco, region, provincia, canton, tipo_credito, estado_cartera, saldo, source_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fecha, tipo_entidad, banco, canton, tipo_credito, estado_cartera)
            DO UPDATE SET saldo = EXCLUDED.saldo, region = EXCLUDED.region,
                          provincia = EXCLUDED.provincia, source_file = EXCLUDED.source_file,
                          loaded_at = now()
            """,
            rows,
        )
    log.info("staging.cartera: %d filas upsert", len(rows))


def upsert_staging_depositos(conn, df: pd.DataFrame) -> None:
    rows = [
        tuple(_clean(v) for v in (
            r.fecha, r.tipo_entidad, r.banco, r.region, r.provincia, r.canton,
            r.tipo_deposito, r.saldo, r.numero_clientes, r.numero_cuentas, r.source_file,
        ))
        for r in df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO staging.depositos
                (fecha, tipo_entidad, banco, region, provincia, canton, tipo_deposito, saldo, numero_clientes, numero_cuentas, source_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (fecha, tipo_entidad, banco, canton, tipo_deposito)
            DO UPDATE SET saldo = EXCLUDED.saldo, numero_clientes = EXCLUDED.numero_clientes,
                          numero_cuentas = EXCLUDED.numero_cuentas, region = EXCLUDED.region,
                          provincia = EXCLUDED.provincia, source_file = EXCLUDED.source_file,
                          loaded_at = now()
            """,
            rows,
        )
    log.info("staging.depositos: %d filas upsert", len(rows))


_REFRESH_MARTS_SQL = """
INSERT INTO marts.dim_fecha (fecha_id, fecha, anio, mes, trimestre, nombre_mes)
SELECT DISTINCT
    (EXTRACT(YEAR FROM fecha) * 100 + EXTRACT(MONTH FROM fecha))::INT,
    fecha,
    EXTRACT(YEAR FROM fecha)::INT,
    EXTRACT(MONTH FROM fecha)::INT,
    EXTRACT(QUARTER FROM fecha)::INT,
    TO_CHAR(fecha, 'TMMonth')
FROM (SELECT fecha FROM staging.cartera UNION SELECT fecha FROM staging.depositos) f
ON CONFLICT (fecha_id) DO NOTHING;

INSERT INTO marts.dim_banco (banco)
SELECT DISTINCT banco FROM (
    SELECT banco FROM staging.cartera WHERE tipo_entidad = 'BANCO PRIVADO'
    UNION
    SELECT banco FROM staging.depositos WHERE tipo_entidad = 'BANCO PRIVADO'
) b
ON CONFLICT (banco) DO NOTHING;

INSERT INTO marts.dim_canton (canton, provincia, region)
SELECT DISTINCT canton, provincia, region FROM (
    SELECT canton, provincia, region FROM staging.cartera
    UNION
    SELECT canton, provincia, region FROM staging.depositos
) c
WHERE canton IS NOT NULL
ON CONFLICT (canton, provincia) DO NOTHING;

INSERT INTO marts.dim_producto_cartera (tipo_credito, estado_cartera)
SELECT DISTINCT tipo_credito, estado_cartera FROM staging.cartera
ON CONFLICT (tipo_credito, estado_cartera) DO NOTHING;

INSERT INTO marts.dim_producto_deposito (tipo_deposito)
SELECT DISTINCT tipo_deposito FROM staging.depositos
ON CONFLICT (tipo_deposito) DO NOTHING;

INSERT INTO marts.fact_cartera (fecha_id, banco_id, canton_id, producto_cartera_id, saldo)
SELECT
    (EXTRACT(YEAR FROM s.fecha) * 100 + EXTRACT(MONTH FROM s.fecha))::INT,
    b.banco_id,
    c.canton_id,
    p.producto_cartera_id,
    s.saldo
FROM staging.cartera s
JOIN marts.dim_banco b ON b.banco = s.banco
LEFT JOIN marts.dim_canton c ON c.canton = s.canton AND c.provincia = s.provincia
JOIN marts.dim_producto_cartera p ON p.tipo_credito = s.tipo_credito AND p.estado_cartera = s.estado_cartera
WHERE s.tipo_entidad = 'BANCO PRIVADO'
ON CONFLICT (fecha_id, banco_id, canton_id, producto_cartera_id)
DO UPDATE SET saldo = EXCLUDED.saldo;

INSERT INTO marts.fact_depositos (fecha_id, banco_id, canton_id, producto_deposito_id, saldo, numero_clientes, numero_cuentas)
SELECT
    (EXTRACT(YEAR FROM s.fecha) * 100 + EXTRACT(MONTH FROM s.fecha))::INT,
    b.banco_id,
    c.canton_id,
    p.producto_deposito_id,
    s.saldo,
    s.numero_clientes,
    s.numero_cuentas
FROM staging.depositos s
JOIN marts.dim_banco b ON b.banco = s.banco
LEFT JOIN marts.dim_canton c ON c.canton = s.canton AND c.provincia = s.provincia
JOIN marts.dim_producto_deposito p ON p.tipo_deposito = s.tipo_deposito
WHERE s.tipo_entidad = 'BANCO PRIVADO'
ON CONFLICT (fecha_id, banco_id, canton_id, producto_deposito_id)
DO UPDATE SET saldo = EXCLUDED.saldo,
              numero_clientes = EXCLUDED.numero_clientes,
              numero_cuentas = EXCLUDED.numero_cuentas;
"""


def refresh_marts(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_REFRESH_MARTS_SQL)
    log.info("marts.* actualizado desde staging")
