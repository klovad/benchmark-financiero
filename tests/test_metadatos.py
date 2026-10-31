"""Toda tabla, vista y columna de marts tiene descripción en el catálogo de Postgres
(COMMENT ON, sql/44). Regla 10 de docs/gobernanza_datos.md: una migración que agrega un
objeto o una columna a marts trae su COMMENT; si no, este test falla y dice cuál falta."""

import pytest


@pytest.mark.integration
def test_objetos_de_marts_tienen_descripcion(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'marts' AND c.relkind IN ('r', 'v', 'm', 'p')
              AND obj_description(c.oid, 'pg_class') IS NULL
            ORDER BY 1
            """
        )
        sin_descripcion = [r[0] for r in cur.fetchall()]
    assert not sin_descripcion, f"Tablas/vistas de marts sin COMMENT: {sin_descripcion}"


@pytest.mark.integration
def test_columnas_de_marts_tienen_descripcion(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname || '.' || a.attname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            WHERE n.nspname = 'marts' AND c.relkind IN ('r', 'v', 'm', 'p')
              AND col_description(c.oid, a.attnum) IS NULL
            ORDER BY 1
            """
        )
        sin_descripcion = [r[0] for r in cur.fetchall()]
    assert not sin_descripcion, f"Columnas de marts sin COMMENT: {sin_descripcion}"
