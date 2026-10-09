"""
Carga idempotente a Postgres: archivo parseado -> staging (tipado) -> marts (estrella).

Idempotencia, en tres niveles (ver docs/architecture.md, "Carga incremental"):
- Archivo: meta.source_files evita reprocesar un archivo cuyo sha256 ya fue cargado.
- Fila: staging.* tiene UNIQUE en la llave natural -> COPY a tabla temporal + INSERT ...
  ON CONFLICT DO UPDATE con guard `(t.a, t.b) IS DISTINCT FROM (EXCLUDED.a, EXCLUDED.b)`
  sobre las columnas mutables (CDC_COLUMNS), para que una fila sin cambios reales no
  dispare un UPDATE ni mueva fecha_actualizacion.
- Refresh: refresh_marts() recalcula solo el alcance (fecha, banco_codigo) de las filas
  de staging cambiadas desde la última marca de agua (meta.refresh_watermark), con el
  mismo guard de CDC hacia marts. Correr el pipeline varias veces converge al mismo
  resultado.
- La identidad de banco (banco_codigo) se resuelve en src/benchmark_bancos/transform/banco_matching.py
  ANTES de llegar a staging -- marts.dim_entidad no es más que un catálogo poblado desde
  staging.banco_maestro (sembrado desde src/benchmark_bancos/seeds/banco_maestro.csv), sin tabla de alias.
"""

import csv
import logging
import re

import pandas as pd
import psycopg

from benchmark_bancos.config import DB_CONFIG, SEEDS_DIR
from benchmark_bancos.transform.canton_matching import seed_cantones

log = logging.getLogger(__name__)

_SEEDS_DIR = SEEDS_DIR


def get_connection() -> psycopg.Connection:
    return psycopg.connect(**DB_CONFIG, autocommit=False)


def is_source_loaded(conn, source_file: str, source_hash: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM meta.source_files WHERE source_file = %s AND source_hash = %s",
            (source_file, source_hash),
        )
        return cur.fetchone() is not None


def register_source_file(
    conn, source_file: str, source_hash: str, report_type: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO meta.source_files (source_file, source_hash, report_type)
            VALUES (%s, %s, %s)
            ON CONFLICT (source_file) DO UPDATE SET source_hash = EXCLUDED.source_hash, loaded_at = now()
            """,
            (source_file, source_hash, report_type),
        )


def _clean(value):
    """pandas usa NaN para valores faltantes incluso en columnas de texto; json.dumps
    serializa NaN como el token literal `NaN`, que no es JSON válido para Postgres."""
    return None if pd.isna(value) else value


def upsert_banco_maestro_ruc(conn, entidades: list[tuple[str, str, str, str]]) -> None:
    """Registra el RUC de TODAS las entidades resueltas por BCE (bancos privados
    incluidos) y auto-registra las no-privadas (cooperativas, mutualistas, banca pública,
    sociedad financiera, tarjetas de crédito) -- ver
    src/benchmark_bancos/transform/banco_matching.py::resolver_entidad_bce. `ON CONFLICT DO UPDATE SET
    ruc` únicamente: para bancos privados la fila ya existe (sembrada desde
    banco_maestro.csv) y no se toca `banco`/`tipo_entidad`, que siguen siendo dueños de
    ese valor -- load_banco_maestro_seed() los reafirma en cada refresh_marts(); para
    entidades nuevas, el INSERT las crea con banco/tipo_entidad/ruc de una vez.

    estado_validacion no se toca en el ON CONFLICT (se preserva el valor existente) y no
    se lista en el INSERT -- una fila nueva hereda el DEFAULT 'AUTO_INGRESADO' de
    staging.banco_maestro (sql/26_dim_banco_estado_validacion.sql) sin necesitar cambio
    de código acá; si esa fila resulta ser uno de los curados (33 privados + 3 públicos de CAPCOL) y esta función la creó
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
    """Siembra staging.banco_maestro desde src/benchmark_bancos/seeds/banco_maestro.csv -- el nombre a
    mostrar y tipo_entidad de cada banco_codigo, determinista sin importar qué variante
    de texto llegó primero durante la carga.

    estado_validacion = 'CONFIRMADO' siempre, en el INSERT y en el UPDATE del conflicto
    (sql/26_dim_banco_estado_validacion.sql): estos banco_codigo (33 privados + 3 públicos de CAPCOL, 2026-10-05) son exactamente los
    curados a mano en el CSV, así que cada corrida reafirma CONFIRMADO sin importar si la
    fila ya existía (curada de siempre) o si upsert_banco_maestro_ruc() la creó primero
    con el DEFAULT AUTO_INGRESADO (posible en una base nueva si load_bce() corre antes
    que este seed) -- refresh_marts() llama a esta función antes de correr
    _REFRESH_MARTS_SQL, así que el estado queda correcto antes de poblar marts.dim_entidad.
    """
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


def sincronizar_cantones_seed(conn) -> None:
    """Vuelca `seeds/canton_provincia.csv` sobre marts.dim_canton: código INEC y
    estado CONFIRMADO para cada par curado (sql/36). Curar un cantón AUTO_INGRESADO es
    agregar su fila (con código) al CSV; la próxima corrida lo confirma. Solo toca filas
    que cambian. Avisa con WARNING si queda algún cantón real sin código."""
    rows = [(c, p, cod) for (c, p), cod in seed_cantones().items()]
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _seed_canton "
            "(canton text, provincia text, codigo_inec text)"
        )
        cur.execute("TRUNCATE _seed_canton")
        cur.executemany("INSERT INTO _seed_canton VALUES (%s, %s, %s)", rows)
        cur.execute(
            """
            UPDATE marts.dim_canton d
            SET codigo_inec = s.codigo_inec, estado_validacion = 'CONFIRMADO'
            FROM _seed_canton s
            JOIN marts.dim_provincia p ON p.provincia = s.provincia
            WHERE d.canton = s.canton AND d.provincia_id = p.provincia_id
              AND (d.codigo_inec IS DISTINCT FROM s.codigo_inec
                   OR d.estado_validacion IS DISTINCT FROM 'CONFIRMADO')
            """
        )
        actualizados = cur.rowcount
        cur.execute(
            """
            SELECT d.canton || ' (' || p.provincia || ')'
            FROM marts.dim_canton d JOIN marts.dim_provincia p USING (provincia_id)
            WHERE d.codigo_inec IS NULL AND p.provincia <> 'S/N'
            ORDER BY 1
            """
        )
        sin_codigo = [r[0] for r in cur.fetchall()]
    if actualizados:
        log.info(
            "marts.dim_canton: %d cantones sincronizados desde el seed", actualizados
        )
    if sin_codigo:
        log.warning(
            "marts.dim_canton: %d cantón(es) AUTO_INGRESADO sin código INEC, revisar y "
            "agregar a seeds/canton_provincia.csv (o a _ALIASES_CANTON si es una "
            "variante): %s",
            len(sin_codigo),
            ", ".join(sin_codigo),
        )


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
        cur.execute(
            "CREATE TEMP TABLE _tmp_cartera (LIKE staging.cartera INCLUDING DEFAULTS) ON COMMIT DROP"
        )
    _copy_rows(
        conn,
        "COPY _tmp_cartera (fecha, tipo_entidad, banco, banco_codigo, region, provincia, "
        "canton, tipo_credito, estado_cartera, saldo, source_file) FROM STDIN",
        rows,
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO staging.cartera
                (fecha, tipo_entidad, banco, banco_codigo, region, provincia, canton, tipo_credito, estado_cartera, saldo, source_file)
            SELECT fecha, tipo_entidad, banco, banco_codigo, region, provincia, canton, tipo_credito, estado_cartera, saldo, source_file
            FROM _tmp_cartera
            ON CONFLICT (fecha, tipo_entidad, banco, COALESCE(provincia, ''), COALESCE(canton, ''), tipo_credito, estado_cartera)
            DO UPDATE SET saldo = EXCLUDED.saldo, region = EXCLUDED.region,
                          provincia = EXCLUDED.provincia, source_file = EXCLUDED.source_file,
                          banco_codigo = EXCLUDED.banco_codigo, fecha_actualizacion = now()
            WHERE (staging.cartera.saldo, staging.cartera.region, staging.cartera.provincia, staging.cartera.source_file) IS DISTINCT FROM (EXCLUDED.saldo, EXCLUDED.region, EXCLUDED.provincia, EXCLUDED.source_file)
            """
        )
        cur.execute("DROP TABLE _tmp_cartera")
    log.info("staging.cartera: %d filas upsert", len(rows))


def upsert_staging_depositos(conn, df: pd.DataFrame) -> None:
    df = df.copy()
    for c in (
        "plazo_dias_desde",
        "plazo_dias_hasta",
        "numero_clientes",
        "numero_cuentas",
    ):
        # nullable Int64: COPY rechaza '30.0' en una columna INT
        df[c] = pd.to_numeric(df[c]).astype("Int64")
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
    cols = (
        "fecha, tipo_entidad, banco, banco_codigo, region, provincia, canton, tipo_deposito, "
        "categoria_deposito, plazo_dias_desde, plazo_dias_hasta, saldo, numero_clientes, "
        "numero_cuentas, source_file"
    )
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE _tmp_depositos (LIKE staging.depositos INCLUDING DEFAULTS) ON COMMIT DROP"
        )
    _copy_rows(conn, f"COPY _tmp_depositos ({cols}) FROM STDIN", rows)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO staging.depositos ({cols})
            SELECT {cols} FROM _tmp_depositos
            ON CONFLICT (fecha, tipo_entidad, banco, COALESCE(provincia, ''), COALESCE(canton, ''), tipo_deposito)
            DO UPDATE SET saldo = EXCLUDED.saldo, numero_clientes = EXCLUDED.numero_clientes,
                          numero_cuentas = EXCLUDED.numero_cuentas, region = EXCLUDED.region,
                          provincia = EXCLUDED.provincia, source_file = EXCLUDED.source_file,
                          banco_codigo = EXCLUDED.banco_codigo,
                          categoria_deposito = EXCLUDED.categoria_deposito,
                          plazo_dias_desde = EXCLUDED.plazo_dias_desde,
                          plazo_dias_hasta = EXCLUDED.plazo_dias_hasta,
                          fecha_actualizacion = now()
            WHERE (staging.depositos.saldo, staging.depositos.region, staging.depositos.provincia, staging.depositos.numero_clientes, staging.depositos.numero_cuentas, staging.depositos.source_file) IS DISTINCT FROM (EXCLUDED.saldo, EXCLUDED.region, EXCLUDED.provincia, EXCLUDED.numero_clientes, EXCLUDED.numero_cuentas, EXCLUDED.source_file)
            """
        )
        cur.execute("DROP TABLE _tmp_depositos")
    log.info("staging.depositos: %d filas upsert", len(rows))


# CDC por columnas (sql/34 eliminó las columnas GENERATED row_hash): un upsert solo
# reescribe la fila si cambió alguna de estas columnas. Son exactamente las que cubría el
# md5 de cada row_hash, así que el comportamiento es idéntico, sin guardar el hash.
CDC_COLUMNS = {
    "bce_tasas_activas": [
        "monto_total",
        "numero_operaciones",
        "tasa_activa_efectiva",
        "tasa_nominal",
        "tipo_segmento",
    ],
    "bce_tasas_pasivas": [
        "monto_total",
        "numero_operaciones",
        "tasa_pasiva_efectiva",
        "tasa_nominal",
        "tipo_segmento",
    ],
    "boletin_balance": ["saldo_usd"],
    "boletin_pyg": ["valor_usd"],
    "cartera": ["saldo", "region", "provincia", "source_file"],
    "depositos": [
        "saldo",
        "region",
        "provincia",
        "numero_clientes",
        "numero_cuentas",
        "source_file",
    ],
    "tasas_referenciales": ["valor"],
}


def _cdc_guard(tabla: str, clave: str) -> str:
    """`(t.a, t.b) IS DISTINCT FROM (EXCLUDED.a, EXCLUDED.b)` para el ON CONFLICT."""
    cols = CDC_COLUMNS[clave]
    actual = ", ".join(f"{tabla}.{c}" for c in cols)
    nuevo = ", ".join(f"EXCLUDED.{c}" for c in cols)
    return f"({actual}) IS DISTINCT FROM ({nuevo})"


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


_BCE_INT_COLS = {"plazo_dias_desde", "plazo_dias_hasta", "numero_operaciones"}


def _upsert_bce_via_temp(
    conn, df: pd.DataFrame, table: str, cols: list[str], key_cols: list[str]
) -> None:
    """COPY a una tabla temporal (misma sesión, se descarta sola) y de ahí INSERT ...
    ON CONFLICT DO UPDATE con guard de CDC por columnas -- COPY no soporta ON CONFLICT
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
            else (f"COALESCE({c}, '')" if c in ("provincia", "canton") else c)
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
            WHERE {_cdc_guard(f'staging.{table}', table)}
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
    "canton",
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
    "canton",
    "monto_total",
    "numero_operaciones",
    "tasa_activa_efectiva",
    "tasa_nominal",
    "tipo_segmento",
    "source_file",
]


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
            WHERE staging.tasas_referenciales.valor IS DISTINCT FROM EXCLUDED.valor
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
        "canton",
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
        "canton",
    ]
    _upsert_bce_via_temp(
        conn, df, "bce_tasas_activas", _BCE_TASAS_ACTIVAS_COLS, key_cols
    )


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


def insert_dim_cuenta_contable_seps(conn, cuentas_df: pd.DataFrame) -> None:
    """Plan de cuentas de la SEPS (mismo Catálogo Único que Superbancos: 1.063 de 1.214
    códigos SEPS 2025 ya existen). A diferencia de upsert_dim_cuenta_contable(), NO pisa
    en conflicto: la descripción de un código compartido sigue siendo la de Superbancos
    (la SEPS redacta distinto, p.ej. "interfinancieras" vs. "interbancarias"). Los
    códigos solo-SEPS entran con el DEFAULT estado_validacion='AUTO_INGRESADO' (sql/25).
    """
    rows = [
        tuple(
            _clean(v)
            for v in (r.reporte, r.codigo, r.cuenta, r.nivel, r.codigo_padre, r.seccion)
        )
        for r in cuentas_df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO marts.dim_cuenta_contable (reporte, codigo, cuenta, nivel, codigo_padre, seccion)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (reporte, codigo) DO NOTHING
            """,
            rows,
        )
    log.info(
        "marts.dim_cuenta_contable: %d códigos SEPS vistos (solo se insertan los nuevos)",
        len(rows),
    )


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
            WHERE {_cdc_guard(f'staging.{table}', table)}
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

-- dim_entidad (antes dim_banco, sql/37): identidad ya resuelta en staging.banco_codigo (src/benchmark_bancos/transform/banco_matching.py);
-- el nombre a mostrar y tipo_entidad vienen de staging.banco_maestro (sembrado desde
-- src/benchmark_bancos/seeds/banco_maestro.csv), no de cualquier texto crudo que haya llegado primero.
-- estado_validacion (sql/26_dim_banco_estado_validacion.sql) se copia de
-- staging.banco_maestro tal cual -- CONFIRMADO para los 36 curados -- 33 privados + 3 públicos (reafirmado en cada
-- corrida por load_banco_maestro_seed(), llamado justo antes que esta sentencia dentro
-- de refresh_marts()), AUTO_INGRESADO para las ~409 entidades auto-registradas por RUC.
--
-- segmento_entidad_id SÍ va en el SELECT/columna del INSERT (leído de la propia
-- marts.dim_entidad vía el LEFT JOIN de abajo) aunque esta sentencia nunca lo escribe en
-- el SET del ON CONFLICT -- esa columna es propiedad del UPDATE separado más abajo
-- (SCD1 desde los hechos BCE). Bug real encontrado y corregido 2026-08-30 al verificar
-- CDC no-op para esta migración: como segmento_entidad_id NO estaba en la lista de
-- columnas del INSERT, Postgres computaba `EXCLUDED.segmento_entidad_id` como NULL (el
-- DEFAULT de una columna omitida en el INSERT, no el valor real de la fila en conflicto)
-- -- eso hacía que el guard de CDC (entonces sobre row_hash, desde sql/34 sobre las
-- columnas mismas) casi nunca coincidiera con la fila real para cualquier
-- banco con segmento_entidad_id ya poblado (prácticamente los 442), disparando un
-- UPDATE real (`fecha_actualizacion = now()`) en CADA corrida de refresh_marts(), no
-- solo cuando algo cambiaba de verdad. Preexistía desde sql/19_dim_segmento_entidad.sql
-- (2026-07-25) -- no lo introdujo esta migración, solo quedó expuesto al verificar CDC
-- no-op de punta a punta en vez de asumirlo. Con el LEFT JOIN, una fila nueva sigue
-- resolviendo segmento_entidad_id = NULL correctamente (no hay fila existente que unir).
INSERT INTO marts.dim_entidad (entidad_codigo, entidad, tipo_entidad, ruc, estado_validacion, segmento_entidad_id)
SELECT bm.banco_codigo, bm.banco, bm.tipo_entidad, bm.ruc, bm.estado_validacion, existente.segmento_entidad_id
FROM staging.banco_maestro bm
LEFT JOIN marts.dim_entidad existente ON existente.entidad_codigo = bm.banco_codigo
WHERE bm.banco_codigo IN (SELECT entidad_codigo FROM marts.dim_entidad)
   OR bm.banco_codigo IN (
    SELECT DISTINCT banco_codigo FROM staging.cartera WHERE tipo_entidad IN ('BANCO PRIVADO', 'BANCO PUBLICO', 'COOPERATIVA', 'MUTUALISTA', 'ENTIDAD DE SEGUNDO PISO')
    UNION
    SELECT DISTINCT banco_codigo FROM staging.depositos WHERE tipo_entidad IN ('BANCO PRIVADO', 'BANCO PUBLICO', 'COOPERATIVA', 'MUTUALISTA', 'ENTIDAD DE SEGUNDO PISO')
    UNION
    SELECT DISTINCT banco_codigo FROM staging.bce_tasas_pasivas
    UNION
    SELECT DISTINCT banco_codigo FROM staging.bce_tasas_activas
    UNION
    SELECT DISTINCT banco_codigo FROM staging.boletin_balance
    UNION
    SELECT DISTINCT banco_codigo FROM staging.boletin_pyg
)
ON CONFLICT (entidad_codigo) DO UPDATE SET
    entidad = EXCLUDED.entidad, tipo_entidad = EXCLUDED.tipo_entidad, ruc = EXCLUDED.ruc,
    estado_validacion = EXCLUDED.estado_validacion, fecha_actualizacion = now()
WHERE (marts.dim_entidad.entidad, marts.dim_entidad.tipo_entidad, marts.dim_entidad.ruc, marts.dim_entidad.segmento_entidad_id, marts.dim_entidad.estado_validacion) IS DISTINCT FROM (EXCLUDED.entidad, EXCLUDED.tipo_entidad, EXCLUDED.ruc, EXCLUDED.segmento_entidad_id, EXCLUDED.estado_validacion);

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
--
-- staging.bce_tasas_pasivas/activas se suman a este mismo auto-ingreso desde
-- sql/28_bce_canton_grain.sql (2026-09-01): un par (canton, provincia) de BCE fuera del
-- universo curado en src/benchmark_bancos/seeds/canton_provincia.csv nunca fue rechazado por
-- resolver_canton_bce() (two-tier, ver src/benchmark_bancos/transform/canton_matching.py) -- este INSERT es
-- el punto donde efectivamente se auto-ingresa a marts.dim_canton con
-- estado_validacion='AUTO_INGRESADO' (DEFAULT de la columna, sql/28), igual que un bucket
-- nuevo de dim_plazo. A diferencia de CAPCOL, BCE ya normaliza canton/provincia en Python
-- antes de staging, así que en la práctica coincide por igualdad exacta -- translate()
-- sigue aplicando por si acaso, sin costo real.
INSERT INTO marts.dim_canton (canton, provincia_id)
SELECT DISTINCT c.canton, dp.provincia_id FROM (
    SELECT canton, provincia FROM staging.cartera
    UNION
    SELECT canton, provincia FROM staging.depositos
    UNION
    SELECT canton, provincia FROM staging.bce_tasas_pasivas
    UNION
    SELECT canton, provincia FROM staging.bce_tasas_activas
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
    (fecha_id, entidad_id, canton_id, segmento_id, saldo_por_vencer, saldo_no_devenga_intereses, saldo_vencida)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.entidad_id,
    c.canton_id,
    sg.segmento_id,
    COALESCE(SUM(s.saldo) FILTER (WHERE s.estado_cartera = 'por_vencer'), 0),
    COALESCE(SUM(s.saldo) FILTER (WHERE s.estado_cartera = 'no_devenga_intereses'), 0),
    COALESCE(SUM(s.saldo) FILTER (WHERE s.estado_cartera = 'vencida'), 0)
FROM staging.cartera s
JOIN marts.dim_entidad b ON b.entidad_codigo = s.banco_codigo
LEFT JOIN marts.dim_provincia dp ON dp.provincia = translate(s.provincia, 'ÁÉÍÓÚ', 'AEIOU')
LEFT JOIN marts.dim_canton c ON c.canton = s.canton AND c.provincia_id = dp.provincia_id
JOIN marts.dim_segmento_credito sg ON sg.segmento = CASE s.tipo_credito
    WHEN 'comercial' THEN 'PRODUCTIVO'
    WHEN 'consumo' THEN 'CONSUMO'
    WHEN 'inmobiliario' THEN 'INMOBILIARIO'
    WHEN 'microcredito' THEN 'MICROCRÉDITO'
    WHEN 'vivienda_interes_publico' THEN 'VIVIENDA DE INTERÉS PÚBLICO'
    WHEN 'educativo' THEN 'EDUCATIVO'
    WHEN 'inversion_publica' THEN 'INVERSIÓN PÚBLICA'  -- solo Banca Pública
END
WHERE s.tipo_entidad IN ('BANCO PRIVADO', 'BANCO PUBLICO', 'COOPERATIVA', 'MUTUALISTA', 'ENTIDAD DE SEGUNDO PISO')
GROUP BY TO_CHAR(s.fecha, 'YYYYMMDD')::INT, b.entidad_id, c.canton_id, sg.segmento_id
ON CONFLICT (fecha_id, entidad_id, COALESCE(canton_id, -1), segmento_id)
DO UPDATE SET saldo_por_vencer = EXCLUDED.saldo_por_vencer,
              saldo_no_devenga_intereses = EXCLUDED.saldo_no_devenga_intereses,
              saldo_vencida = EXCLUDED.saldo_vencida,
              fecha_actualizacion = now()
WHERE (marts.fact_saldo_cartera.saldo_por_vencer, marts.fact_saldo_cartera.saldo_no_devenga_intereses, marts.fact_saldo_cartera.saldo_vencida) IS DISTINCT FROM (EXCLUDED.saldo_por_vencer, EXCLUDED.saldo_no_devenga_intereses, EXCLUDED.saldo_vencida);

INSERT INTO marts.fact_saldo_depositos (fecha_id, entidad_id, canton_id, categoria_deposito_id, plazo_id, saldo, numero_clientes, numero_cuentas)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.entidad_id,
    c.canton_id,
    cd.categoria_deposito_id,
    pl.plazo_id,
    s.saldo,
    s.numero_clientes,
    s.numero_cuentas
FROM staging.depositos s
JOIN marts.dim_entidad b ON b.entidad_codigo = s.banco_codigo
LEFT JOIN marts.dim_provincia dp ON dp.provincia = translate(s.provincia, 'ÁÉÍÓÚ', 'AEIOU')
LEFT JOIN marts.dim_canton c ON c.canton = s.canton AND c.provincia_id = dp.provincia_id
JOIN marts.dim_categoria_deposito cd ON cd.categoria = s.categoria_deposito
LEFT JOIN marts.dim_plazo pl ON pl.dias_desde = s.plazo_dias_desde
    AND pl.dias_hasta IS NOT DISTINCT FROM s.plazo_dias_hasta
WHERE s.tipo_entidad IN ('BANCO PRIVADO', 'BANCO PUBLICO', 'COOPERATIVA', 'MUTUALISTA', 'ENTIDAD DE SEGUNDO PISO')
ON CONFLICT (fecha_id, entidad_id, canton_id, categoria_deposito_id, COALESCE(plazo_id, -1))
DO UPDATE SET saldo = EXCLUDED.saldo,
              numero_clientes = EXCLUDED.numero_clientes,
              numero_cuentas = EXCLUDED.numero_cuentas,
              fecha_actualizacion = now()
WHERE (marts.fact_saldo_depositos.saldo, marts.fact_saldo_depositos.numero_clientes, marts.fact_saldo_depositos.numero_cuentas) IS DISTINCT FROM (EXCLUDED.saldo, EXCLUDED.numero_clientes, EXCLUDED.numero_cuentas);

-- canton_id (antes provincia_id, sql/28_bce_canton_grain.sql): mismo patrón de
-- resolución de 2 pasos que ya usan fact_saldo_cartera/fact_saldo_depositos (CAPCOL) --
-- dim_provincia primero (para tener provincia_id), luego dim_canton por el PAR
-- (canton, provincia_id), NUNCA canton solo (hay cantones homónimos en provincias
-- distintas, ver canton_matching.py). El INSERT de marts.dim_canton más arriba en este
-- mismo _REFRESH_MARTS_SQL ya corrió antes de esta sentencia, así que un par
-- AUTO_INGRESADO nuevo de BCE ya existe en dim_canton para cuando este JOIN se ejecuta.
INSERT INTO marts.fact_captaciones_depositos
    (fecha_id, entidad_id, categoria_deposito_id, plazo_id, canton_id, monto_total, numero_operaciones, tasa_pasiva_efectiva, tasa_nominal, segmento_entidad_id)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.entidad_id,
    cd.categoria_deposito_id,
    pl.plazo_id,
    c.canton_id,
    s.monto_total,
    s.numero_operaciones,
    s.tasa_pasiva_efectiva,
    s.tasa_nominal,
    se.segmento_entidad_id
FROM staging.bce_tasas_pasivas s
JOIN marts.dim_entidad b ON b.entidad_codigo = s.banco_codigo
JOIN marts.dim_categoria_deposito cd ON cd.categoria = s.categoria_deposito
JOIN marts.dim_plazo pl ON pl.dias_desde = s.plazo_dias_desde
    AND pl.dias_hasta IS NOT DISTINCT FROM s.plazo_dias_hasta
LEFT JOIN marts.dim_provincia dp ON dp.provincia = translate(s.provincia, 'ÁÉÍÓÚ', 'AEIOU')
LEFT JOIN marts.dim_canton c ON c.canton = s.canton AND c.provincia_id = dp.provincia_id
LEFT JOIN marts.dim_segmento_entidad se ON se.tipo_segmento = s.tipo_segmento
ON CONFLICT (fecha_id, entidad_id, categoria_deposito_id, plazo_id, COALESCE(canton_id, -1))
DO UPDATE SET monto_total = EXCLUDED.monto_total,
              numero_operaciones = EXCLUDED.numero_operaciones,
              tasa_pasiva_efectiva = EXCLUDED.tasa_pasiva_efectiva,
              tasa_nominal = EXCLUDED.tasa_nominal,
              segmento_entidad_id = EXCLUDED.segmento_entidad_id,
              fecha_actualizacion = now()
WHERE (marts.fact_captaciones_depositos.monto_total, marts.fact_captaciones_depositos.numero_operaciones, marts.fact_captaciones_depositos.tasa_pasiva_efectiva, marts.fact_captaciones_depositos.tasa_nominal, marts.fact_captaciones_depositos.segmento_entidad_id) IS DISTINCT FROM (EXCLUDED.monto_total, EXCLUDED.numero_operaciones, EXCLUDED.tasa_pasiva_efectiva, EXCLUDED.tasa_nominal, EXCLUDED.segmento_entidad_id);

-- canton_id: mismo patrón de resolución de 2 pasos que fact_captaciones_depositos arriba
-- -- ver ese comentario para el detalle completo.
INSERT INTO marts.fact_colocaciones_cartera
    (fecha_id, entidad_id, subsegmento_id, plazo_id, canton_id, monto_total, numero_operaciones, tasa_activa_efectiva, tasa_nominal, segmento_entidad_id)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.entidad_id,
    sg.subsegmento_id,
    pl.plazo_id,
    c.canton_id,
    s.monto_total,
    s.numero_operaciones,
    s.tasa_activa_efectiva,
    s.tasa_nominal,
    se.segmento_entidad_id
FROM staging.bce_tasas_activas s
JOIN marts.dim_entidad b ON b.entidad_codigo = s.banco_codigo
JOIN marts.dim_subsegmento_credito sg ON sg.subsegmento = s.segmento_credito
JOIN marts.dim_plazo pl ON pl.dias_desde = s.plazo_dias_desde
    AND pl.dias_hasta IS NOT DISTINCT FROM s.plazo_dias_hasta
LEFT JOIN marts.dim_provincia dp ON dp.provincia = translate(s.provincia, 'ÁÉÍÓÚ', 'AEIOU')
LEFT JOIN marts.dim_canton c ON c.canton = s.canton AND c.provincia_id = dp.provincia_id
LEFT JOIN marts.dim_segmento_entidad se ON se.tipo_segmento = s.tipo_segmento
ON CONFLICT (fecha_id, entidad_id, subsegmento_id, plazo_id, COALESCE(canton_id, -1))
DO UPDATE SET monto_total = EXCLUDED.monto_total,
              numero_operaciones = EXCLUDED.numero_operaciones,
              tasa_activa_efectiva = EXCLUDED.tasa_activa_efectiva,
              tasa_nominal = EXCLUDED.tasa_nominal,
              segmento_entidad_id = EXCLUDED.segmento_entidad_id,
              fecha_actualizacion = now()
WHERE (marts.fact_colocaciones_cartera.monto_total, marts.fact_colocaciones_cartera.numero_operaciones, marts.fact_colocaciones_cartera.tasa_activa_efectiva, marts.fact_colocaciones_cartera.tasa_nominal, marts.fact_colocaciones_cartera.segmento_entidad_id) IS DISTINCT FROM (EXCLUDED.monto_total, EXCLUDED.numero_operaciones, EXCLUDED.tasa_activa_efectiva, EXCLUDED.tasa_nominal, EXCLUDED.segmento_entidad_id);

-- dim_entidad.segmento_entidad_id: conveniencia con la ÚLTIMA clasificación conocida (SCD
-- tipo 1) para análisis puntuales contra la situación actual, sin tener que ir a buscar
-- la fila más reciente en los hechos semanales. Se resuelve tomando la fecha más
-- reciente entre AMBOS hechos BCE (un banco puede aparecer solo en tsp o solo en tsa).
--
-- Guard de CDC: solo escribe si segmento_entidad_id cambió de verdad. Hasta sql/34 este
-- WHERE recalculaba a mano el md5 de marts.dim_entidad.row_hash y se desincronizó una vez
-- (2026-08-30, al agregar estado_validacion): CDC roto en silencio. Comparar la única
-- columna que este UPDATE escribe elimina esa clase de error.
-- Alcance: solo bancos con datos BCE en staging (src_* en el refresh incremental).
UPDATE marts.dim_entidad b
SET segmento_entidad_id = latest.segmento_entidad_id, fecha_actualizacion = now()
FROM (
    SELECT DISTINCT ON (entidad_id) entidad_id, segmento_entidad_id
    FROM (
        SELECT entidad_id, fecha_id, segmento_entidad_id FROM marts.fact_captaciones_depositos WHERE segmento_entidad_id IS NOT NULL
        UNION ALL
        SELECT entidad_id, fecha_id, segmento_entidad_id FROM marts.fact_colocaciones_cartera WHERE segmento_entidad_id IS NOT NULL
    ) x
    WHERE x.entidad_id IN (
        SELECT b2.entidad_id FROM marts.dim_entidad b2
        WHERE b2.entidad_codigo IN (SELECT banco_codigo FROM staging.bce_tasas_pasivas
                                    UNION SELECT banco_codigo FROM staging.bce_tasas_activas)
    )
    ORDER BY entidad_id, fecha_id DESC
) latest
WHERE b.entidad_id = latest.entidad_id
  AND b.segmento_entidad_id IS DISTINCT FROM latest.segmento_entidad_id;

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
WHERE (marts.fact_tasas_referenciales_cartera.tasa_activa_maxima, marts.fact_tasas_referenciales_cartera.tasa_activa_referencial) IS DISTINCT FROM (EXCLUDED.tasa_activa_maxima, EXCLUDED.tasa_activa_referencial);

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
WHERE marts.fact_tasas_referenciales_depositos_instrumento.tasa_pasiva_promedio IS DISTINCT FROM EXCLUDED.tasa_pasiva_promedio;

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
WHERE marts.fact_tasas_referenciales_depositos_plazo.tasa_pasiva_referencial IS DISTINCT FROM EXCLUDED.tasa_pasiva_referencial;

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
WHERE (marts.fact_tasas_referenciales_sistema.tasa_pasiva_referencial_sistema, marts.fact_tasas_referenciales_sistema.tasa_activa_referencial_sistema, marts.fact_tasas_referenciales_sistema.tasa_legal, marts.fact_tasas_referenciales_sistema.tasa_maxima_convencional) IS DISTINCT FROM (EXCLUDED.tasa_pasiva_referencial_sistema, EXCLUDED.tasa_activa_referencial_sistema, EXCLUDED.tasa_legal, EXCLUDED.tasa_maxima_convencional);

-- Boletín BALANCE/PYG -- dim_cuenta_contable se puebla directo desde Python
-- (upsert_dim_cuenta_contable, antes de refresh_marts) porque su llave (reporte, codigo)
-- no es un valor que se pueda derivar por SELECT DISTINCT de una sola columna staging
-- como el resto de catálogos auto-descubiertos.
INSERT INTO marts.fact_balance (fecha_id, entidad_id, cuenta_id, saldo_usd)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.entidad_id,
    cc.cuenta_id,
    s.saldo_usd
FROM staging.boletin_balance s
JOIN marts.dim_entidad b ON b.entidad_codigo = s.banco_codigo
JOIN marts.dim_cuenta_contable cc ON cc.reporte = 'BALANCE' AND cc.codigo = s.codigo
ON CONFLICT (fecha_id, entidad_id, cuenta_id)
DO UPDATE SET saldo_usd = EXCLUDED.saldo_usd, fecha_actualizacion = now()
WHERE marts.fact_balance.saldo_usd IS DISTINCT FROM EXCLUDED.saldo_usd;

INSERT INTO marts.fact_pyg (fecha_id, entidad_id, cuenta_id, valor_usd)
SELECT
    TO_CHAR(s.fecha, 'YYYYMMDD')::INT,
    b.entidad_id,
    cc.cuenta_id,
    s.valor_usd
FROM staging.boletin_pyg s
JOIN marts.dim_entidad b ON b.entidad_codigo = s.banco_codigo
JOIN marts.dim_cuenta_contable cc ON cc.reporte = 'PYG' AND cc.codigo = s.codigo
ON CONFLICT (fecha_id, entidad_id, cuenta_id)
DO UPDATE SET valor_usd = EXCLUDED.valor_usd, fecha_actualizacion = now()
WHERE marts.fact_pyg.valor_usd IS DISTINCT FROM EXCLUDED.valor_usd;
"""


def _log_cantones_no_resueltos(conn, fuentes=lambda sql: sql) -> None:
    """El INSERT de marts.dim_canton en _REFRESH_MARTS_SQL usa un INNER JOIN contra
    dim_provincia (provincia_id es NOT NULL en dim_canton, así que no puede ser un LEFT
    JOIN con NULL) -- toda fila de staging.cartera/staging.depositos/staging.bce_tasas_*
    cuya `provincia` no resuelve contra dim_provincia (ni exacto ni via translate(), ver el
    comentario sobre ese INSERT) queda descartada ahí sin error, sin fila huérfana, sin
    rastro. Bug real encontrado 2026-08-30 al revisar load_postgres.py, no una feature
    nueva.

    staging.bce_tasas_pasivas/activas se agregan a esta misma consulta desde
    sql/28_bce_canton_grain.sql (2026-09-01): en la práctica no deberían aportar NUNCA una
    fila acá -- resolver_canton_bce() (src/benchmark_bancos/transform/canton_matching.py) ya hace fail-fast
    en Python (CantonNoResueltoError) si la provincia cruda no resuelve, ANTES de que la
    fila llegue a staging -- pero esta función es la red de seguridad de nivel SQL, no
    Python: cubre el caso de que alguna vez se escriba a staging.bce_tasas_* por una ruta
    que no pase por resolver_canton_bce() (ej. una migración de datos manual, un backfill
    ad-hoc), mismo motivo por el que ya cubre staging.cartera/depositos aunque esas dos
    tampoco deberían llegar acá bajo el flujo normal actual.

    Se resuelve con logging (WARNING si hay filas afectadas, INFO si no), NO con una
    tabla staging.catalogo_rechazos: a diferencia de dim_plazo/banco_codigo (catálogos
    regulatorios cerrados donde un valor no resuelto significa un dato mal identificado
    que un analista podría contar como otra cosa), dim_canton es geografía de bajo riesgo
    -- el motivo de scope-out real ("agregar geografía sin curar caso por caso") no
    aplica acá; y a fecha de esta función, 0 filas de ninguna de las 4 tablas caen en este
    caso (verificado contra la base viva, ver docs/gobernanza_datos.md). Construir
    infraestructura de rechazos persistente para un caso con 0 filas afectadas hoy sería
    sobre-ingeniería; si esta función alguna vez loguea un WARNING real, ESE es el momento
    de evaluar si hace falta algo más que un log."""
    with conn.cursor() as cur:
        cur.execute(
            fuentes(
                """
            SELECT c.provincia, count(*) AS filas, count(DISTINCT c.canton) AS cantones
            FROM (
                SELECT canton, provincia FROM staging.cartera
                UNION ALL
                SELECT canton, provincia FROM staging.depositos
                UNION ALL
                SELECT canton, provincia FROM staging.bce_tasas_pasivas
                UNION ALL
                SELECT canton, provincia FROM staging.bce_tasas_activas
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
        )
        rows = cur.fetchall()
    if rows:
        total_filas = sum(r[1] for r in rows)
        detalle = ", ".join(
            f"{provincia!r} ({filas} filas, {cantones} cantón(es) distintos)"
            for provincia, filas, cantones in rows
        )
        log.warning(
            "marts.dim_canton: %d fila(s) de staging.cartera/depositos/bce_tasas_pasivas/"
            "bce_tasas_activas con provincia NO resoluble contra marts.dim_provincia -- "
            "el INNER JOIN de refresh_marts() las va a DESCARTAR silenciosamente si esto "
            "no se corrige (%d provincia(s) distintas afectadas: %s)",
            total_filas,
            len(rows),
            detalle,
        )
    else:
        log.info(
            "marts.dim_canton: 0 filas con provincia no resoluble (verificado en esta corrida)"
        )


def _log_bancos_no_resueltos(conn, fuentes=lambda sql: sql) -> None:
    """Los INSERT de fact_saldo_cartera/fact_saldo_depositos hacen INNER JOIN contra
    marts.dim_entidad, que solo contiene banco_codigo presentes en staging.banco_maestro.
    Banca Pública resuelve por crosswalk a filas BCE_<ruc> que solo existen si BCE ya
    corrió al menos una vez (docs/fuentes_datos.md sección 1.1): en una base
    reconstruida desde cero con CAPCOL cargado antes que BCE, esas filas se descartarían
    sin error. Mismo criterio log-only que _log_cantones_no_resueltos()."""
    with conn.cursor() as cur:
        cur.execute(
            fuentes(
                """
            SELECT s.tipo_entidad, s.banco_codigo, count(*) AS filas
            FROM (
                SELECT tipo_entidad, banco_codigo FROM staging.cartera
                UNION ALL
                SELECT tipo_entidad, banco_codigo FROM staging.depositos
            ) s
            WHERE NOT EXISTS (
                SELECT 1 FROM staging.banco_maestro bm
                WHERE bm.banco_codigo = s.banco_codigo
            )
            GROUP BY s.tipo_entidad, s.banco_codigo
            ORDER BY filas DESC
            """
            )
        )
        rows = cur.fetchall()
    if rows:
        detalle = ", ".join(f"{c!r} [{t}] ({n} filas)" for t, c, n in rows)
        log.warning(
            "marts.dim_entidad: %d banco_codigo de staging.cartera/depositos sin fila en "
            "staging.banco_maestro -- el INNER JOIN de refresh_marts() DESCARTARÁ sus "
            "filas (¿falta correr `uv run benchmark-bancos bce` primero?): %s",
            len(rows),
            detalle,
        )
    else:
        log.info(
            "marts.dim_entidad: 0 banco_codigo CAPCOL sin resolver (verificado en esta corrida)"
        )


# Tablas de staging que alimentan marts. Las que tienen banco_codigo se recalculan por
# (fecha, banco_codigo) completos: fact_saldo_cartera agrega 3 filas de staging (los 3
# estados de cartera) en una, así que si cambió una hay que recalcular con las otras dos.
# Recalcular filas que no cambiaron es inocuo (el guard de CDC no las reescribe).
# tasas_referenciales no tiene banco_codigo: su alcance es la fecha.
_FUENTES_REFRESH = {
    "cartera": "fecha, banco_codigo",
    "depositos": "fecha, banco_codigo",
    "bce_tasas_pasivas": "fecha, banco_codigo",
    "bce_tasas_activas": "fecha, banco_codigo",
    "boletin_balance": "fecha, banco_codigo",
    "boletin_pyg": "fecha, banco_codigo",
    "tasas_referenciales": "fecha",
}
_RE_FUENTES = re.compile(r"\bstaging\.(" + "|".join(_FUENTES_REFRESH) + r")\b")


def _leer_watermark(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT hasta FROM meta.refresh_watermark WHERE proceso = 'marts'")
        row = cur.fetchone()
    return row[0] if row else None


def _crear_fuentes_incrementales(conn, desde) -> dict[str, int]:
    """Copia a tablas temporales src_<tabla> el alcance a recalcular: todas las filas de
    staging de cada (fecha, banco_codigo) con al menos una fila cambiada después de
    `desde`. Usa el índice sobre fecha_actualizacion (sql/34)."""
    filas = {}
    with conn.cursor() as cur:
        for tabla, alcance in _FUENTES_REFRESH.items():
            cur.execute(f"DROP TABLE IF EXISTS src_{tabla}")
            cur.execute(
                f"""
                CREATE TEMP TABLE src_{tabla} ON COMMIT DROP AS
                SELECT s.* FROM staging.{tabla} s
                WHERE ({alcance}) IN (
                    SELECT DISTINCT {alcance} FROM staging.{tabla}
                    WHERE fecha_actualizacion > %s
                )
                """,
                (desde,),
            )
            filas[tabla] = cur.rowcount
            cur.execute(f"ANALYZE src_{tabla}")
    return filas


def refresh_marts(conn, full: bool = False) -> None:
    """Actualiza marts.* desde staging.

    Incremental por defecto: solo recalcula el alcance (fecha, banco_codigo) de las filas
    de staging cambiadas desde la última corrida (marca de agua en
    meta.refresh_watermark, sql/34). Antes cada corrida releía staging completo: ~196 s
    aunque no hubiera nada nuevo (medido 2026-10-05). El SQL es el mismo en ambos modos;
    el incremental solo cambia `staging.X` por la tabla temporal `src_X`.

    Hace refresh completo si `full=True` o si todavía no hay marca de agua (base nueva).
    Supone un solo escritor a la vez: una carga concurrente que empezó antes de esta
    corrida y commitea después tendría fecha_actualizacion anterior a la nueva marca y no
    se vería; para ese caso, `benchmark-bancos refresh --full`.
    """
    load_banco_maestro_seed(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT now()")
        inicio = cur.fetchone()[0]
    desde = None if full else _leer_watermark(conn)

    if desde is None:
        fuentes = lambda sql: sql  # noqa: E731
        log.info("refresh de marts: COMPLETO (full=%s, marca previa=%s)", full, desde)
    else:
        filas = _crear_fuentes_incrementales(conn, desde)
        fuentes = lambda sql: _RE_FUENTES.sub(r"src_\1", sql)  # noqa: E731
        log.info(
            "refresh de marts: INCREMENTAL desde %s, filas en alcance: %s",
            desde,
            {k: v for k, v in filas.items() if v} or "ninguna",
        )

    _log_cantones_no_resueltos(conn, fuentes)
    _log_bancos_no_resueltos(conn, fuentes)
    with conn.cursor() as cur:
        cur.execute(fuentes(_REFRESH_MARTS_SQL))
        sincronizar_cantones_seed(conn)
        cur.execute(
            """
            INSERT INTO meta.refresh_watermark (proceso, hasta) VALUES ('marts', %s)
            ON CONFLICT (proceso) DO UPDATE SET hasta = EXCLUDED.hasta
            """,
            (inicio,),
        )
    log.info("marts.* actualizado desde staging")
