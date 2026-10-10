"""Control de conciliación saldos vs. contabilidad (sql/39, conciliacion.py)."""

import psycopg
import pytest

from benchmark_bancos import cli, conciliacion
from benchmark_bancos.conciliacion import Resultado, evaluar
from benchmark_bancos.config import DB_CONFIG


def test_mes_que_cuadra_no_falla():
    assert (
        evaluar([Resultado(20260831, "COOPERATIVA", "cartera", 204, 0.0, 0.96)]) == []
    )


def test_mediana_fuera_de_umbral_falla():
    fallas = evaluar(
        [Resultado(20260831, "COOPERATIVA", "depositos", 203, -0.03, 0.95)]
    )
    assert len(fallas) == 1 and "mediana -3.00%" in fallas[0]


def test_pocas_entidades_dentro_de_2pct_falla():
    fallas = evaluar([Resultado(20260831, "COOPERATIVA", "cartera", 204, 0.0, 0.60)])
    assert len(fallas) == 1 and "60%" in fallas[0]


def test_desvio_conocido_de_bancos_privados_en_depositos_no_falla():
    # CAPCOL no cubre 5 subcuentas de la 21: mediana histórica -0,5% a -1,1%.
    assert (
        evaluar([Resultado(20260831, "BANCO PRIVADO", "depositos", 23, -0.0106, 0.80)])
        == []
    )


def test_mutualistas_cartera_no_se_evalua():
    # Cartera en fideicomiso (explicado): +1% a +47%.
    assert evaluar([Resultado(20260831, "MUTUALISTA", "cartera", 4, 0.47, 0.25)]) == []


def test_conciliar_falla_con_codigo_2(monkeypatch):
    def con_falla(conn, meses=3):
        conciliacion.log.error("conciliación fuera de umbral: prueba")
        return ["prueba"]

    monkeypatch.setattr(conciliacion, "verificar", con_falla)
    monkeypatch.setattr(cli.psycopg, "connect", lambda **kw: _ConnFalsa())
    assert cli.main(["conciliar"]) == 2


class _ConnFalsa:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.mark.integration
def test_verificar_sobre_la_base_no_falla():
    # Base local: todos los meses dentro de umbral; CI: base vacía, nada que evaluar.
    with psycopg.connect(**DB_CONFIG) as conn:
        assert conciliacion.verificar(conn) == []
