"""Códigos de salida del CLI, `actualizar` y `migrate` (2026-10-09)."""

import contextlib
import datetime
import logging

import psycopg
import pytest

from benchmark_bancos import cli, migrate, orquestacion
from benchmark_bancos.config import DB_CONFIG


@pytest.fixture
def sin_esperas_ni_conciliacion(monkeypatch):
    # actualizar() espera antes de reintentar y concilia contra la base al final.
    monkeypatch.setattr(orquestacion.time, "sleep", lambda s: None)
    monkeypatch.setattr(orquestacion.conciliacion, "verificar", lambda conn: [])
    monkeypatch.setattr(orquestacion.psycopg, "connect", lambda **kw: _Conn())


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def sin_bloqueo(monkeypatch):
    monkeypatch.setattr(orquestacion, "bloqueo_corrida", contextlib.nullcontext)


def test_exit_0_si_todo_ok(monkeypatch, sin_bloqueo):
    monkeypatch.setattr(cli, "_ejecutar", lambda args: None)
    assert cli.main(["refresh"]) == 0


def test_exit_2_si_se_registraron_errores(monkeypatch, sin_bloqueo):
    monkeypatch.setattr(
        cli, "_ejecutar", lambda args: logging.getLogger("x").error("timeout")
    )
    assert cli.main(["refresh"]) == 2


def test_exit_1_si_la_etapa_se_interrumpe(monkeypatch, sin_bloqueo):
    def falla(args):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "_ejecutar", falla)
    assert cli.main(["refresh"]) == 1


def test_exit_75_si_hay_otra_corrida(monkeypatch):
    @contextlib.contextmanager
    def ocupado():
        raise orquestacion.CorridaEnCurso("ocupado")
        yield

    monkeypatch.setattr(orquestacion, "bloqueo_corrida", ocupado)
    monkeypatch.setattr(cli, "_ejecutar", lambda args: None)
    assert cli.main(["refresh"]) == 75


def test_contador_no_se_acumula_entre_corridas(monkeypatch, sin_bloqueo):
    monkeypatch.setattr(cli, "_ejecutar", lambda args: logging.getLogger().error("x"))
    cli.main(["refresh"])
    monkeypatch.setattr(cli, "_ejecutar", lambda args: None)
    assert cli.main(["refresh"]) == 0


def test_actualizar_sigue_si_una_fuente_falla(monkeypatch, sin_esperas_ni_conciliacion):
    corridas = []

    def falla():
        raise RuntimeError("portal caído")

    pasos = {f: (lambda f=f: corridas.append(f)) for f in orquestacion.FUENTES}
    pasos["capcol"] = falla
    monkeypatch.setattr(orquestacion, "_pasos", lambda anios: pasos)
    fallidas = orquestacion.actualizar(anios=[2026])
    assert fallidas == ["capcol"]
    assert corridas == ["bce", "boletin", "tasas-historicas", "seps"]


def test_actualizar_reintenta_una_fuente_que_falla_una_vez(
    monkeypatch, sin_esperas_ni_conciliacion
):
    intentos = []

    def falla_la_primera():
        intentos.append(1)
        if len(intentos) == 1:
            raise RuntimeError("portal respondió a medias")

    pasos = {f: (lambda: None) for f in orquestacion.FUENTES}
    pasos["seps"] = falla_la_primera
    monkeypatch.setattr(orquestacion, "_pasos", lambda anios: pasos)
    assert orquestacion.actualizar(anios=[2026]) == []
    assert len(intentos) == 2


@pytest.mark.parametrize(
    "hoy,esperado",
    [
        (datetime.date(2026, 10, 9), [2026]),
        (datetime.date(2027, 1, 15), [2026, 2027]),
        (datetime.date(2027, 3, 1), [2027]),
    ],
)
def test_anios_en_curso(hoy, esperado):
    assert orquestacion.anios_en_curso(hoy) == esperado


def test_migrate_rechaza_base_con_esquema_y_sin_registro(monkeypatch, tmp_path):
    (tmp_path / "01_x.sql").write_text("SELECT 1;")
    monkeypatch.setattr(
        migrate,
        "estado",
        lambda conn, sql_dir, crear_registro=True: migrate.Estado(
            {}, [tmp_path / "01_x.sql"], [], True
        ),
    )

    class Conn:
        autocommit = True

    with pytest.raises(migrate.MigracionError, match="--baseline"):
        migrate.migrar(Conn(), tmp_path)


@pytest.mark.integration
def test_migrate_aplica_pendientes_una_vez_y_detecta_cambios(tmp_path, caplog):
    a = tmp_path / "990_zz_test_a.sql"
    b = tmp_path / "991_zz_test_b.sql"
    a.write_text("CREATE TABLE meta._zz_test_migrate (x int);")
    b.write_text("INSERT INTO meta._zz_test_migrate VALUES (1);")
    conn = psycopg.connect(**DB_CONFIG, autocommit=True)
    try:
        migrate.estado(conn, tmp_path)  # crea el registro si no existe
        # registro no vacío para que no pida --baseline (en CI viene vacío)
        conn.execute(
            "INSERT INTO meta.schema_migrations (archivo, sha256) "
            "VALUES ('zz_sentinela.sql', 'x') ON CONFLICT DO NOTHING"
        )
        assert migrate.migrar(conn, tmp_path) == [a.name, b.name]
        assert (
            conn.execute("SELECT count(*) FROM meta._zz_test_migrate").fetchone()[0]
            == 1
        )
        assert migrate.migrar(conn, tmp_path) == []  # no re-ejecuta

        b.write_text("INSERT INTO meta._zz_test_migrate VALUES (2);")
        with caplog.at_level(logging.WARNING):
            migrate.migrar(conn, tmp_path)
        assert "991_zz_test_b.sql" in caplog.text
        assert (
            conn.execute("SELECT count(*) FROM meta._zz_test_migrate").fetchone()[0]
            == 1
        )
    finally:
        conn.execute("DROP TABLE IF EXISTS meta._zz_test_migrate")
        conn.execute("DELETE FROM meta.schema_migrations WHERE archivo LIKE '%zz_%'")
        conn.close()
