import psycopg
import pytest

from benchmark_bancos.config import DB_CONFIG


@pytest.fixture
def db_conn():
    """Conexión a Postgres real para tests marcados @pytest.mark.integration.

    Nunca hace commit: siempre se hace rollback al terminar el test (pase o falle),
    para que ninguno de estos tests deje residuos permanentes en la base -- ni en la
    base de desarrollo local ni en el contenedor postgres:17 efímero de CI. Ver
    docs/propuesta_escalabilidad_etl.md sección 2.2/2.3.
    """
    conn = psycopg.connect(**DB_CONFIG, autocommit=False)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
