"""Reintentos de descarga (extract/red.py, 2026-10-09). Sin red ni esperas reales."""

import socket
import urllib.error

import pytest

from benchmark_bancos.extract import red


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    esperas = []
    monkeypatch.setattr(red.time, "sleep", esperas.append)
    return esperas


def _falla_n_veces(n, error):
    llamadas = []

    def operacion():
        llamadas.append(1)
        if len(llamadas) <= n:
            raise error
        return "ok"

    return operacion, llamadas


def test_error_transitorio_se_reintenta_con_espera_creciente(sin_esperas):
    op, llamadas = _falla_n_veces(2, urllib.error.URLError("conexión rechazada"))
    assert red.con_reintentos(op, "prueba") == "ok"
    assert len(llamadas) == 3
    assert sin_esperas == [5.0, 15.0]


def test_se_rinde_tras_los_intentos():
    op, llamadas = _falla_n_veces(5, socket.timeout("timed out"))
    with pytest.raises(socket.timeout):
        red.con_reintentos(op, "prueba")
    assert len(llamadas) == 3


@pytest.mark.parametrize("codigo", [304, 404])
def test_http_4xx_y_304_no_se_reintentan(codigo):
    op, llamadas = _falla_n_veces(1, urllib.error.HTTPError("u", codigo, "x", {}, None))
    with pytest.raises(urllib.error.HTTPError):
        red.con_reintentos(op, "prueba")
    assert len(llamadas) == 1


def test_http_5xx_se_reintenta():
    op, llamadas = _falla_n_veces(1, urllib.error.HTTPError("u", 503, "x", {}, None))
    assert red.con_reintentos(op, "prueba") == "ok"
    assert len(llamadas) == 2


def test_error_de_logica_no_se_reintenta():
    op, llamadas = _falla_n_veces(1, ValueError("no es un zip"))
    with pytest.raises(ValueError):
        red.con_reintentos(op, "prueba")
    assert len(llamadas) == 1


def test_timeout_de_playwright_se_reintenta():
    class TimeoutError(Exception):  # mismo nombre que playwright.sync_api.TimeoutError
        pass

    op, llamadas = _falla_n_veces(1, TimeoutError("navegación"))
    assert red.con_reintentos(op, "prueba") == "ok"
    assert len(llamadas) == 2
