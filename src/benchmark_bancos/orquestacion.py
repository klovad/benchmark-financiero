"""Orquestación de corridas desatendidas (2026-10-09).

- `bloqueo_corrida()`: advisory lock de Postgres para que dos corridas no escriban a la
  vez (el refresh incremental supone un solo escritor). Si otra corrida lo tiene, la
  segunda termina con código 75 sin tocar nada.
- `actualizar()`: la actualización incremental completa, fuente por fuente. Cada fuente
  es independiente: si una falla se registra como ERROR y se sigue con las demás; el
  CLI termina con código distinto de 0. Es seguro correrla seguido: el BCE y la SEPS
  solo descargan si hay versión nueva, CAPCOL y el Boletín vuelven a bajar los archivos
  del año (pocos MB) pero no recargan lo que ya tiene el mismo sha256, y TasasHistorico
  solo baja los meses que faltan.
"""

import contextlib
import datetime
import logging
import time
from collections.abc import Callable, Iterator

import psycopg

from benchmark_bancos import conciliacion, pipeline
from benchmark_bancos.config import CAPCOL_PORTALES, DB_CONFIG, RAW_DIR
from benchmark_bancos.extract.scrape_superbancos import scrape

log = logging.getLogger(__name__)

_CLAVE_BLOQUEO = 7_301_550_018  # constante arbitraria, propia de este proyecto

EXIT_OK = 0
EXIT_ERRORES = 2  # la corrida terminó, pero hubo errores (ver log)
EXIT_BLOQUEADO = 75  # otra corrida en curso (EX_TEMPFAIL)

FUENTES = ("bce", "capcol", "boletin", "tasas-historicas", "seps")
ESPERA_REINTENTO_FUENTE = 120.0  # segundos antes de reintentar una fuente fallida


class CorridaEnCurso(RuntimeError):
    pass


@contextlib.contextmanager
def bloqueo_corrida() -> Iterator[None]:
    conn = psycopg.connect(**DB_CONFIG, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (_CLAVE_BLOQUEO,))
            if not cur.fetchone()[0]:
                raise CorridaEnCurso(
                    "Hay otra corrida de benchmark-bancos en curso sobre esta base"
                )
        yield
    finally:
        conn.close()  # cerrar la sesión libera el lock


class ContadorErrores(logging.Handler):
    """Cuenta los registros ERROR/CRITICAL de la corrida (scrapers con timeout, archivos
    que no se pudieron parsear, fuentes de `actualizar` que fallaron) para decidir el
    código de salida sin cambiar cada módulo."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.errores = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.errores += 1


def anios_en_curso(hoy: datetime.date | None = None) -> list[int]:
    """Año actual; en enero y febrero también el anterior, porque sus últimos meses
    (y el cierre anual) se publican con rezago."""
    hoy = hoy or datetime.date.today()
    return [hoy.year - 1, hoy.year] if hoy.month <= 2 else [hoy.year]


def _pasos(anios: list[int]) -> dict[str, Callable[[], None]]:
    def capcol() -> None:
        for portal in CAPCOL_PORTALES:
            scrape(anios, RAW_DIR, portal=portal)
        pipeline.load_years(anios, RAW_DIR, tuple(CAPCOL_PORTALES))

    return {
        "bce": pipeline.load_bce,
        "capcol": capcol,
        "boletin": lambda: pipeline.load_boletin(anios, RAW_DIR),
        "tasas-historicas": pipeline.load_tasas_historicas,
        "seps": lambda: pipeline.load_seps(anios),
    }


def actualizar(
    fuentes: list[str] | None = None,
    anios: list[int] | None = None,
    espera_reintento: float = ESPERA_REINTENTO_FUENTE,
) -> list[str]:
    """Corre la actualización incremental de las fuentes pedidas (todas por defecto) y
    devuelve las que fallaron. Una fuente que falla se reintenta una vez al final, tras
    `espera_reintento` segundos (las descargas ya reintentan cortes de red por su cuenta;
    esto cubre el resto, p. ej. un portal que respondió a medias)."""
    anios = anios or anios_en_curso()
    pasos = _pasos(anios)
    pendientes = []
    for fuente in fuentes or FUENTES:
        log.info("=== actualizar: %s (años %s) ===", fuente, anios)
        try:
            pasos[fuente]()
        except Exception as e:
            log.warning(
                "actualizar: falló la fuente %s (%s: %s), se reintenta al final",
                fuente,
                type(e).__name__,
                e,
            )
            pendientes.append(fuente)

    fallidas = []
    if pendientes:
        time.sleep(espera_reintento)
    for fuente in pendientes:
        log.info("=== actualizar: reintento de %s ===", fuente)
        try:
            pasos[fuente]()
        except Exception:
            log.exception(
                "actualizar: la fuente %s falló también al reintentar", fuente
            )
            fallidas.append(fuente)
    if fallidas:
        log.error("actualizar: terminó con fuentes fallidas: %s", ", ".join(fallidas))
    else:
        log.info("actualizar: todas las fuentes OK")
    # Control de calidad final (sql/39): una falla de conciliación se registra como
    # ERROR (código 2) pero no se cuenta como fuente fallida.
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            conciliacion.verificar(conn)
    except Exception:
        log.exception("actualizar: no se pudo correr el control de conciliación")
    return fallidas
