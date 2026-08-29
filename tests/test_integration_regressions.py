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
    upsert_staging_bce_tasas_pasivas,
    upsert_staging_boletin_balance,
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
def test_staging_cartera_canton_null_safe_unique_regression(db_conn):
    """Regresión de sql/23_fix_staging_cartera_canton_null_safe.sql: dos filas con la
    misma llave natural (fecha, tipo_entidad, banco, tipo_credito, estado_cartera) salvo
    canton=NULL en ambas deben colapsar a una sola fila bajo el índice único NULL-safe
    staging_cartera_natural_key_unique (fecha, tipo_entidad, banco, COALESCE(canton, ''),
    tipo_credito, estado_cartera) -- antes del fix, el UNIQUE plano sobre `canton` (mismo
    bug class que sql/10_fix_null_unique_constraints.sql, NULL <> NULL incluso bajo
    UNIQUE) dejaba pasar ambas filas como filas distintas."""
    banco_codigo = "ZZTEST_CANTON_NULL"
    fecha = date(2099, 3, 31)
    with db_conn.cursor() as cur:
        for saldo in (100, 999):
            cur.execute(
                """
                INSERT INTO staging.cartera
                    (fecha, tipo_entidad, banco, banco_codigo, canton, tipo_credito,
                     estado_cartera, saldo, source_file)
                VALUES (%s, 'BANCO PRIVADO', 'ZZ TEST BANK', %s, NULL, 'comercial',
                        'por_vencer', %s, 'test_integration')
                ON CONFLICT (fecha, tipo_entidad, banco, COALESCE(canton, ''), tipo_credito, estado_cartera)
                DO UPDATE SET saldo = EXCLUDED.saldo, fecha_actualizacion = now()
                """,
                (fecha, banco_codigo, saldo),
            )

        cur.execute(
            "SELECT saldo FROM staging.cartera WHERE banco_codigo = %s",
            (banco_codigo,),
        )
        rows = cur.fetchall()

    assert len(rows) == 1  # las 2 filas con canton NULL colapsan a 1, no 2
    assert rows[0][0] == 999  # la segunda inserción actualizó la primera (mismo natural key)


@pytest.mark.integration
def test_staging_depositos_canton_null_safe_unique_regression(db_conn):
    """Regresión de sql/24_fix_staging_depositos_canton_null_safe.sql: dos filas con la
    misma llave natural (fecha, tipo_entidad, banco, tipo_deposito) salvo canton=NULL en
    ambas deben colapsar a una sola fila bajo el índice único NULL-safe
    staging_depositos_natural_key_unique (fecha, tipo_entidad, banco, COALESCE(canton, ''),
    tipo_deposito) -- mismo bug class que sql/23_fix_staging_cartera_canton_null_safe.sql
    y sql/10_fix_null_unique_constraints.sql (NULL <> NULL incluso bajo UNIQUE), y misma
    columna canton, aplicado esta vez a staging.depositos en vez de staging.cartera."""
    banco_codigo = "ZZTEST_CANTON_NULL_DEP"
    fecha = date(2099, 3, 31)
    with db_conn.cursor() as cur:
        for saldo in (100, 999):
            cur.execute(
                """
                INSERT INTO staging.depositos
                    (fecha, tipo_entidad, banco, banco_codigo, canton, tipo_deposito,
                     categoria_deposito, saldo, source_file)
                VALUES (%s, 'BANCO PRIVADO', 'ZZ TEST BANK', %s, NULL, 'ahorro',
                        'DEPÓSITOS DE AHORRO', %s, 'test_integration')
                ON CONFLICT (fecha, tipo_entidad, banco, COALESCE(canton, ''), tipo_deposito)
                DO UPDATE SET saldo = EXCLUDED.saldo, fecha_actualizacion = now()
                """,
                (fecha, banco_codigo, saldo),
            )

        cur.execute(
            "SELECT saldo FROM staging.depositos WHERE banco_codigo = %s",
            (banco_codigo,),
        )
        rows = cur.fetchall()

    assert len(rows) == 1  # las 2 filas con canton NULL colapsan a 1, no 2
    assert rows[0][0] == 999  # la segunda inserción actualizó la primera (mismo natural key)


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


# --- Cobertura de la mecánica COPY/temp-table (sección 2.3, item pendiente) ---------
#
# _upsert_bce_via_temp() / _upsert_boletin_via_temp() (etl/load/load_postgres.py) hacen
# CREATE TEMP TABLE ... ON COMMIT DROP dentro de la MISMA conexión/transacción que el
# INSERT ... ON CONFLICT final. ON COMMIT DROP solo dispara en un COMMIT real -- nunca en
# un ROLLBACK (el ROLLBACK deshace la propia creación de la tabla igual, por las
# propiedades transaccionales normales de CREATE TABLE, así que no ejercita la cláusula
# ON COMMIT DROP en absoluto). Confirmado empíricamente antes de escribir estos tests:
# llamar la función de upsert dos veces sobre la MISMA conexión sin un commit() en medio
# revienta con `DuplicateTable: la relación "_tmp_bce_tasas_pasivas" ya existe`, porque la
# tabla temporal de la primera llamada seguía viva. Por eso estos tests, a diferencia del
# resto del archivo, sí necesitan un commit() real entre llamadas -- es la única forma de
# ejercitar la ruta de temp-table más de una vez por sesión, y es exactamente lo que pasa
# en producción (pipeline.py hace commit por archivo). Para no romper la garantía de
# db_conn (nunca deja residuos), cada test borra sus propias filas y hace commit() de ese
# borrado en un `finally`, incluso si una aserción falla a mitad de camino.


def _bce_tasas_pasivas_row(banco_codigo: str, **overrides) -> dict:
    row = {
        "fecha": date(2099, 6, 30),
        "banco_codigo": banco_codigo,
        "categoria_deposito": "DEPÓSITOS DE AHORRO",
        "plazo_dias_desde": 0,
        "plazo_dias_hasta": 30,
        "plazo_codigo": "A",
        "provincia": "PICHINCHA",
        "monto_total": 10000.0,
        "numero_operaciones": 12,
        "tasa_pasiva_efectiva": 3.25,
        "tasa_nominal": 3.20,
        "tipo_segmento": "BANCO MEDIANO",
        "source_file": "test_integration_bce.csv",
    }
    row.update(overrides)
    return row


def _cleanup_bce_tasas_pasivas(conn, banco_codigo: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM staging.bce_tasas_pasivas WHERE banco_codigo = %s",
            (banco_codigo,),
        )
    conn.commit()


@pytest.mark.integration
def test_upsert_staging_bce_tasas_pasivas_temp_table_row_count_and_cdc_no_op(db_conn):
    """Cobertura de orquestación (sección 2.3): _upsert_bce_via_temp() vía
    upsert_staging_bce_tasas_pasivas(). (a) una carga a través de COPY -> tabla temporal
    -> INSERT ... ON CONFLICT inserta el conteo exacto de filas esperado; (b) correr la
    misma carga otra vez, con datos idénticos, no dispara ningún UPDATE real -- verificado
    porque fecha_actualizacion no cambia. A diferencia de
    test_upsert_staging_cartera_round_trip_cdc_no_op, esta ruta pasa por una tabla
    temporal (ON COMMIT DROP), así que necesita su propia cobertura -- no se puede asumir
    que el guard `row_hash IS DISTINCT FROM` se comporta igual solo porque ya está
    probado en la ruta de executemany directo."""
    banco_codigo = "ZZTEST_BCE_TEMP_CDC"
    df = pd.DataFrame(
        [
            _bce_tasas_pasivas_row(banco_codigo, plazo_dias_desde=0, plazo_dias_hasta=30),
            _bce_tasas_pasivas_row(banco_codigo, plazo_dias_desde=31, plazo_dias_hasta=60),
        ]
    )

    try:
        upsert_staging_bce_tasas_pasivas(db_conn, df)

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, fecha_actualizacion FROM staging.bce_tasas_pasivas "
                "WHERE banco_codigo = %s ORDER BY plazo_dias_desde",
                (banco_codigo,),
            )
            first_load = cur.fetchall()

        assert len(first_load) == 2  # (a) conteo exacto tras la primera carga

        # commit real -- necesario para que ON COMMIT DROP suelte _tmp_bce_tasas_pasivas
        # antes de la segunda llamada (ver nota de cabecera de esta sección).
        db_conn.commit()

        upsert_staging_bce_tasas_pasivas(db_conn, df)  # misma carga, datos idénticos

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, fecha_actualizacion FROM staging.bce_tasas_pasivas "
                "WHERE banco_codigo = %s ORDER BY plazo_dias_desde",
                (banco_codigo,),
            )
            second_load = cur.fetchall()

        # (b) CDC no-op: mismas filas (mismo id), mismo fecha_actualizacion -- ningún
        # UPDATE real fue disparado por la segunda carga idéntica a través de la ruta de
        # tabla temporal.
        assert second_load == first_load
    finally:
        _cleanup_bce_tasas_pasivas(db_conn, banco_codigo)


@pytest.mark.integration
def test_upsert_staging_bce_tasas_pasivas_temp_table_real_update(db_conn):
    """Cobertura de orquestación (sección 2.3): un cambio real de valor (tasa_pasiva_efectiva)
    a través de la ruta COPY/tabla-temporal SÍ dispara un UPDATE real -- fecha_actualizacion
    avanza y el nuevo valor queda persistido. Confirma que el guard de row_hash en esta
    ruta no se pasa de conservador (nunca actualiza) tanto como no se pasa de agresivo
    (actualiza sin necesidad, cubierto por el test de CDC no-op de al lado)."""
    banco_codigo = "ZZTEST_BCE_TEMP_UPD"
    df = pd.DataFrame([_bce_tasas_pasivas_row(banco_codigo, tasa_pasiva_efectiva=3.25)])

    try:
        upsert_staging_bce_tasas_pasivas(db_conn, df)
        db_conn.commit()

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, fecha_actualizacion, tasa_pasiva_efectiva FROM staging.bce_tasas_pasivas "
                "WHERE banco_codigo = %s",
                (banco_codigo,),
            )
            before_id, before_ts, before_tasa = cur.fetchone()

        assert before_tasa == pytest.approx(3.25)

        df_updated = pd.DataFrame(
            [_bce_tasas_pasivas_row(banco_codigo, tasa_pasiva_efectiva=4.75)]
        )
        upsert_staging_bce_tasas_pasivas(db_conn, df_updated)

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, fecha_actualizacion, tasa_pasiva_efectiva FROM staging.bce_tasas_pasivas "
                "WHERE banco_codigo = %s",
                (banco_codigo,),
            )
            after_id, after_ts, after_tasa = cur.fetchone()

        assert after_id == before_id  # mismo natural key -- UPDATE, no un INSERT nuevo
        assert after_ts > before_ts  # UPDATE real: fecha_actualizacion avanzó
        assert after_tasa == pytest.approx(4.75)  # el nuevo valor quedó persistido
    finally:
        _cleanup_bce_tasas_pasivas(db_conn, banco_codigo)


@pytest.mark.integration
def test_upsert_staging_bce_tasas_pasivas_temp_table_on_commit_drop(db_conn):
    """Verifica la promesa de `ON COMMIT DROP` en _upsert_bce_via_temp() (etl/load/
    load_postgres.py) contra el catálogo real, no solo por lectura del SQL:
    (a) inmediatamente después de que la función retorna -- todavía sin commit --
    _tmp_bce_tasas_pasivas SÍ existe, como tabla temporal de sesión (schema pg_temp_N);
    (b) después de un commit() real, ya no existe.

    Nota sobre qué SÍ y qué NO se puede verificar con el fixture db_conn (que nunca hace
    commit, siempre rollback): un ROLLBACK deshace la propia sentencia CREATE TEMP TABLE
    por las propiedades transaccionales normales de Postgres, sin que la cláusula
    ON COMMIT DROP entre en juego en absoluto -- así que un test que solo confiara en el
    rollback final del fixture NO probaría nada específico de ON COMMIT DROP (probaría lo
    mismo que probaría cualquier tabla permanente creada y nunca commiteada). Por eso este
    test hace su propio commit() real -- explícito, con limpieza en `finally` -- para
    observar el efecto real de ON COMMIT DROP entre los dos estados (existe / no existe),
    en vez de asumirlo."""
    banco_codigo = "ZZTEST_BCE_TEMP_DROP"
    df = pd.DataFrame([_bce_tasas_pasivas_row(banco_codigo)])

    try:
        upsert_staging_bce_tasas_pasivas(db_conn, df)

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT schemaname FROM pg_tables WHERE tablename = %s",
                ("_tmp_bce_tasas_pasivas",),
            )
            before_commit = cur.fetchall()

        # (a) sigue viva justo después de que la función retorna -- todavía no hubo commit.
        assert len(before_commit) == 1
        assert before_commit[0][0].startswith("pg_temp")

        db_conn.commit()

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT schemaname FROM pg_tables WHERE tablename = %s",
                ("_tmp_bce_tasas_pasivas",),
            )
            after_commit = cur.fetchall()

        # (b) ON COMMIT DROP la soltó: ya no aparece en pg_tables tras el commit real.
        assert after_commit == []
    finally:
        _cleanup_bce_tasas_pasivas(db_conn, banco_codigo)


def _boletin_balance_row(banco_codigo: str, **overrides) -> dict:
    row = {
        "fecha": date(2099, 6, 30),
        "banco": "BANCO DE PRUEBA BOLETIN",
        "banco_codigo": banco_codigo,
        "codigo": "1",
        "saldo_usd": 100000.0,
        "source_file": "test_integration_boletin.xlsx",
    }
    row.update(overrides)
    return row


def _cleanup_boletin_balance(conn, banco_codigo: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM staging.boletin_balance WHERE banco_codigo = %s",
            (banco_codigo,),
        )
    conn.commit()


@pytest.mark.integration
def test_upsert_staging_boletin_balance_temp_table_row_count_and_cdc_no_op(db_conn):
    """Mismo criterio que test_upsert_staging_bce_tasas_pasivas_temp_table_row_count_and_cdc_no_op,
    pero para _upsert_boletin_via_temp() (helper distinto, ON CONFLICT de 3 columnas fijas
    en vez de key_cols variable con COALESCE) -- confirma que la otra mitad de la mecánica
    COPY/temp-table también preserva conteo exacto y CDC no-op."""
    banco_codigo = "ZZTEST_BOLETIN_TEMP_CDC"
    df = pd.DataFrame(
        [
            _boletin_balance_row(banco_codigo, codigo="1"),
            _boletin_balance_row(banco_codigo, codigo="2"),
        ]
    )

    try:
        upsert_staging_boletin_balance(db_conn, df)

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, fecha_actualizacion FROM staging.boletin_balance "
                "WHERE banco_codigo = %s ORDER BY codigo",
                (banco_codigo,),
            )
            first_load = cur.fetchall()

        assert len(first_load) == 2  # (a) conteo exacto tras la primera carga

        db_conn.commit()  # necesario para soltar _tmp_boletin_balance (ON COMMIT DROP)

        upsert_staging_boletin_balance(db_conn, df)  # misma carga, datos idénticos

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, fecha_actualizacion FROM staging.boletin_balance "
                "WHERE banco_codigo = %s ORDER BY codigo",
                (banco_codigo,),
            )
            second_load = cur.fetchall()

        # (b) CDC no-op a través de la ruta de tabla temporal de Boletín.
        assert second_load == first_load
    finally:
        _cleanup_boletin_balance(db_conn, banco_codigo)


@pytest.mark.integration
def test_upsert_staging_boletin_balance_temp_table_real_update(db_conn):
    """Un cambio real de saldo_usd a través de _upsert_boletin_via_temp() SÍ dispara un
    UPDATE real (fecha_actualizacion avanza, el nuevo saldo queda persistido) -- misma
    cobertura que el equivalente de BCE, para el otro helper de tabla temporal."""
    banco_codigo = "ZZTEST_BOLETIN_TEMP_UPD"
    df = pd.DataFrame([_boletin_balance_row(banco_codigo, saldo_usd=100000.0)])

    try:
        upsert_staging_boletin_balance(db_conn, df)
        db_conn.commit()

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, fecha_actualizacion, saldo_usd FROM staging.boletin_balance "
                "WHERE banco_codigo = %s",
                (banco_codigo,),
            )
            before_id, before_ts, before_saldo = cur.fetchone()

        assert before_saldo == pytest.approx(100000.0)

        df_updated = pd.DataFrame(
            [_boletin_balance_row(banco_codigo, saldo_usd=250000.0)]
        )
        upsert_staging_boletin_balance(db_conn, df_updated)

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, fecha_actualizacion, saldo_usd FROM staging.boletin_balance "
                "WHERE banco_codigo = %s",
                (banco_codigo,),
            )
            after_id, after_ts, after_saldo = cur.fetchone()

        assert after_id == before_id  # mismo natural key -- UPDATE, no un INSERT nuevo
        assert after_ts > before_ts  # UPDATE real: fecha_actualizacion avanzó
        assert after_saldo == pytest.approx(250000.0)
    finally:
        _cleanup_boletin_balance(db_conn, banco_codigo)
