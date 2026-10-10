"""Reintentos para las descargas (2026-10-09).

Antes un corte de red momentáneo o un timeout del portal hacía fallar la fuente entera
hasta la siguiente corrida programada (una semana después). `con_reintentos()` repite la
operación ante errores transitorios, con espera creciente (5 s, 15 s, 45 s por defecto),
y deja pasar de inmediato los que no se arreglan reintentando: HTTP 4xx (un 404 de un
mes aún no publicado, un 304 de "sin cambios") y cualquier otro error de lógica.
"""

import logging
import socket
import time
import urllib.error
from collections.abc import Callable
from typing import TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")

INTENTOS = 3
ESPERA_INICIAL = 5.0
FACTOR = 3.0


def es_transitorio(error: BaseException) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code >= 500 or error.code == 429
    if isinstance(error, (urllib.error.URLError, TimeoutError, socket.timeout)):
        return True
    if isinstance(error, (ConnectionError, OSError)) and not isinstance(
        error, FileNotFoundError
    ):
        return True
    # Playwright: TimeoutError propio (navegación o descarga que no llegó a tiempo).
    return type(error).__name__ == "TimeoutError"


def con_reintentos(
    operacion: Callable[[], T],
    descripcion: str,
    intentos: int = INTENTOS,
    espera_inicial: float = ESPERA_INICIAL,
    factor: float = FACTOR,
) -> T:
    espera = espera_inicial
    for intento in range(1, intentos + 1):
        try:
            return operacion()
        except Exception as e:
            if not es_transitorio(e) or intento == intentos:
                raise
            log.warning(
                "%s: error transitorio (%s: %s), reintento %d/%d en %.0f s",
                descripcion,
                type(e).__name__,
                e,
                intento,
                intentos - 1,
                espera,
            )
            time.sleep(espera)
            espera *= factor
    raise AssertionError("inalcanzable")
