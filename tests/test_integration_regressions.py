"""Tests de integración (@pytest.mark.integration): requieren Postgres real ya
migrado hasta sql/22 (ver docker-compose.yml / tests/conftest.py::db_conn). Cubren
los items routeados en docs/propuesta_escalabilidad_etl.md sección 2.2 (regresiones
de sql/10 y sql/21) y una porción de la sección 2.3 (cobertura de orquestación de
etl/load/load_postgres.py).

Ninguno hace commit -- db_conn siempre hace rollback al terminar, así que no dejan
residuos ni en la base de desarrollo local ni en el contenedor postgres:17 efímero de
CI."""

from datetime import date

import pandas as pd
import pytest

from etl.load.load_postgres import (
    _REFRESH_MARTS_SQL,
    is_source_loaded,
    register_source_file,
    upsert_staging_cartera,
)


def _fact_saldo_cartera_pivot_statement() -> str:
    """Extrae, desde la misma constante _REFRESH_MARTS_SQL que usa refresh_marts() en
    producción, el statement que puebla marts.fact_saldo_cartera -- evita duplicar a
    mano la lógica del pivote (sql/21) en el test, y evita pagar el costo de correr
    refresh_marts() completo (medido ~107s contra la base de desarrollo local, que ya
    tiene ~10M filas acumuladas entre todas las fuentes) solo para probar esta
    invariante puntual, que por sí sola corre en <2s."""
    statements = [s.strip() for s in _REFRESH_MARTS_SQL.split(";")]
    matches = [
        s
        for s in statements
        if "INTO marts.fact_saldo_cartera" in s and "saldo_por_vencer" in s
    ]
    assert len(matches) == 1, (
        "No se pudo aislar (de forma única) el statement de fact_saldo_cartera dentro "
        "de _REFRESH_MARTS_SQL -- revisar si el SQL de refresh_marts() cambió de forma "
        "y ajustar este extractor."
    )
    return matches[0]


@pytest.mark.integration
def test_dim_plazo_null_safe_unique_regression(db_conn):
    """Regresión de sql/10_fix_null_unique_constraints.sql: dos filas con la misma
    llave natural (dias_desde) salvo dias_hasta=NULL en ambas deben colapsar a una
    sola fila bajo el índice único NULL-safe dim_plazo_rango_unique
    (dias_desde, COALESCE(dias_hasta, -1)) -- antes del fix, NULL <> NULL incluso bajo
    UNIQUE dejaba pasar ambas filas como filas distintas."""
    dias_desde = 999_999  # sentinela fuera de cualquier rango real de plazo
    with db_conn.cursor() as cur:
        for plazo_codigo in ("TEST_A", "TEST_B"):
            cur.execute(
                """
                INSERT INTO marts.dim_plazo (dias_desde, dias_hasta, plazo_codigo)
                VALUES (%s, NULL, %s)
                ON CONFLICT (dias_desde, COALESCE(dias_hasta, -1)) DO NOTHING
                """,
                (dias_desde, plazo_codigo),
            )

        cur.execute(
            "SELECT plazo_codigo FROM marts.dim_plazo WHERE dias_desde = %s",
            (dias_desde,),
        )
        rows = cur.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "TEST_A"  # la primera inserción gana, la segunda es no-op


@pytest.mark.integration
def test_fact_saldo_cartera_pivot_invariant(db_conn):
    """Regresión de sql/21_fact_saldo_cartera_pivot.sql: 3 filas EAV-shape
    (por_vencer / no_devenga_intereses / vencida) en staging.cartera para la misma
    llave (fecha, banco, cantón, segmento) deben colapsar a EXACTAMENTE 1 fila en
    marts.fact_saldo_cartera (nunca 3, el antipatrón que sql/21 corrigió), y
    saldo_total debe ser exactamente la suma de las 3 medidas columnares."""
    banco_codigo = "ZZTEST_PIVOT"
    fecha = date(2099, 1, 31)

    with db_conn.cursor() as cur:
        # El statement extraído solo hace fact_saldo_cartera -- salta el resto de
        # refresh_marts() (dim_fecha, dim_banco, ...), así que se sembran a mano las
        # dimensiones de las que depende su FK/JOIN (misma forma que el INSERT real
        # de dim_fecha en _REFRESH_MARTS_SQL, para no hardcodear nombre_mes/trimestre).
        cur.execute(
            """
            INSERT INTO marts.dim_fecha (fecha_id, fecha, anio, mes, dia, trimestre, nombre_mes, anio_mes)
            VALUES (
                TO_CHAR(%(fecha)s::date, 'YYYYMMDD')::INT,
                %(fecha)s,
                EXTRACT(YEAR FROM %(fecha)s::date)::INT,
                EXTRACT(MONTH FROM %(fecha)s::date)::INT,
                EXTRACT(DAY FROM %(fecha)s::date)::INT,
                EXTRACT(QUARTER FROM %(fecha)s::date)::INT,
                TO_CHAR(%(fecha)s::date, 'TMMonth'),
                (EXTRACT(YEAR FROM %(fecha)s::date) * 100 + EXTRACT(MONTH FROM %(fecha)s::date))::INT
            )
            ON CONFLICT (fecha_id) DO NOTHING
            """,
            {"fecha": fecha},
        )
        cur.execute(
            """
            INSERT INTO marts.dim_banco (banco, banco_codigo, tipo_entidad)
            VALUES (%s, %s, 'BANCO PRIVADO')
            RETURNING banco_id
            """,
            ("BANCO DE PRUEBA PIVOTE", banco_codigo),
        )
        banco_id = cur.fetchone()[0]

        for estado, saldo in (
            ("por_vencer", 100),
            ("no_devenga_intereses", 20),
            ("vencida", 5),
        ):
            cur.execute(
                """
                INSERT INTO staging.cartera
                    (fecha, tipo_entidad, banco, banco_codigo, tipo_credito, estado_cartera, saldo, source_file)
                VALUES (%s, 'BANCO PRIVADO', %s, %s, 'comercial', %s, %s, 'test_integration')
                """,
                (fecha, "BANCO DE PRUEBA PIVOTE", banco_codigo, estado, saldo),
            )

        cur.execute(_fact_saldo_cartera_pivot_statement())

        cur.execute(
            """
            SELECT saldo_por_vencer, saldo_no_devenga_intereses, saldo_vencida, saldo_total
            FROM marts.fact_saldo_cartera
            WHERE banco_id = %s
            """,
            (banco_id,),
        )
        rows = cur.fetchall()

    assert len(rows) == 1  # nunca 3 filas EAV para la misma llave

    por_vencer, no_devenga, vencida, total = rows[0]
    assert por_vencer == 100
    assert no_devenga == 20
    assert vencida == 5
    assert total == por_vencer + no_devenga + vencida


@pytest.mark.integration
def test_upsert_staging_cartera_round_trip_cdc_no_op(db_conn):
    """Cobertura de orquestación (sección 2.3): round-trip real de
    upsert_staging_cartera() contra Postgres. (a) una carga inserta el conteo
    esperado de filas; (b) correr la misma carga otra vez, con datos idénticos, no
    dispara ningún UPDATE real -- verificado porque fecha_actualizacion no cambia
    (el guard `WHERE row_hash IS DISTINCT FROM EXCLUDED.row_hash` hace su trabajo)."""
    banco_codigo = "ZZTEST_ORC"
    fecha = date(2099, 2, 28)
    df = pd.DataFrame(
        [
            {
                "fecha": fecha,
                "tipo_entidad": "BANCO PRIVADO",
                "banco": "BANCO DE PRUEBA ORQUESTACION",
                "banco_codigo": banco_codigo,
                "region": "COSTA",
                "provincia": "GUAYAS",
                "canton": "GUAYAQUIL",
                "tipo_credito": "comercial",
                "estado_cartera": "por_vencer",
                "saldo": 1000,
                "source_file": "test_integration",
            },
            {
                "fecha": fecha,
                "tipo_entidad": "BANCO PRIVADO",
                "banco": "BANCO DE PRUEBA ORQUESTACION",
                "banco_codigo": banco_codigo,
                "region": "COSTA",
                "provincia": "GUAYAS",
                "canton": "GUAYAQUIL",
                "tipo_credito": "comercial",
                "estado_cartera": "vencida",
                "saldo": 50,
                "source_file": "test_integration",
            },
        ]
    )

    upsert_staging_cartera(db_conn, df)

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id, fecha_actualizacion FROM staging.cartera "
            "WHERE banco_codigo = %s ORDER BY estado_cartera",
            (banco_codigo,),
        )
        first_load = cur.fetchall()

    assert len(first_load) == 2  # (a) conteo esperado tras la primera carga

    upsert_staging_cartera(db_conn, df)  # misma carga, datos idénticos

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id, fecha_actualizacion FROM staging.cartera "
            "WHERE banco_codigo = %s ORDER BY estado_cartera",
            (banco_codigo,),
        )
        second_load = cur.fetchall()

    # (b) CDC no-op: mismas filas (mismo id), mismo fecha_actualizacion -- ningún
    # UPDATE real fue disparado por la segunda carga idéntica.
    assert second_load == first_load


@pytest.mark.integration
def test_source_file_hash_gate(db_conn):
    """CDC invariante #1 (gate por hash de archivo, raw.source_files -- ver
    is_source_loaded()/register_source_file() en etl/load/load_postgres.py): un
    archivo con el mismo (source_file, source_hash) ya registrado se considera
    cargado; el mismo nombre de archivo con un hash distinto (contenido cambió) se
    considera pendiente de (re)carga."""
    source_file = "zztest_hash_gate.zip"
    hash_v1 = "a" * 64
    hash_v2 = "b" * 64

    assert not is_source_loaded(db_conn, source_file, hash_v1)

    register_source_file(db_conn, source_file, hash_v1, "cartera")

    assert is_source_loaded(db_conn, source_file, hash_v1)
    assert not is_source_loaded(db_conn, source_file, hash_v2)
