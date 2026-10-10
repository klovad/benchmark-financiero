"""Interfaz de línea de comandos del pipeline.

Uso (con uv):
    uv run benchmark-bancos migrate                                # aplica sql/ pendientes
    uv run benchmark-bancos migrate --status                       # solo informa
    uv run benchmark-bancos migrate --baseline                     # base ya al día sin registro
    uv run benchmark-bancos actualizar                             # todas las fuentes, año en curso
    uv run benchmark-bancos actualizar --fuentes bce seps          # solo algunas
    uv run benchmark-bancos conciliar [--meses 12]                 # saldos vs. contabilidad
    uv run benchmark-bancos all --years 2021 2022 2023 2024 2025   # CAPCOL: extract + load
    uv run benchmark-bancos load --portales publica                # solo carga, Banca Pública
    uv run benchmark-bancos bce                                    # BCE tsp/tsa
    uv run benchmark-bancos tasas-historicas                       # BCE TasasHistorico.htm
    uv run benchmark-bancos boletin --years 2025 2026              # Boletín Superbancos
    uv run benchmark-bancos seps --years 2021 2022 2023 2024 2025  # SEPS
    uv run benchmark-bancos refresh                                # solo marts (incremental)
    uv run benchmark-bancos refresh --full                         # solo marts (completo)

Equivalente sin el script instalado: `python -m benchmark_bancos <stage> ...`.

Códigos de salida (2026-10-09): 0 = OK; 1 = error que cortó la corrida; 2 = terminó,
pero se registraron errores (una fuente de `actualizar` que falló, un archivo que no se
pudo descargar, ...: ver el log); 75 = otra corrida en curso sobre la misma base, no se
hizo nada. Todas las etapas que escriben toman un bloqueo en Postgres.
"""

import argparse
import logging
import sys
from pathlib import Path

import psycopg

from benchmark_bancos import conciliacion, migrate, orquestacion, pipeline
from benchmark_bancos.config import CAPCOL_PORTALES, DB_CONFIG, DEFAULT_YEARS, RAW_DIR
from benchmark_bancos.extract.scrape_superbancos import scrape
from benchmark_bancos.logging_utils import setup_logging

log = logging.getLogger(__name__)

STAGES = [
    "migrate",
    "actualizar",
    "conciliar",
    "extract",
    "load",
    "all",
    "bce",
    "tasas-historicas",
    "boletin",
    "seps",
    "refresh",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark-bancos",
        description="Pipeline ETL benchmark de cartera, depósitos y tasas (Ecuador)",
    )
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        help="Años a procesar (default: SCRAPER_YEARS; en `actualizar`, el año en curso)",
    )
    parser.add_argument("--out", type=Path, default=RAW_DIR)
    parser.add_argument(
        "--portales",
        nargs="+",
        choices=list(CAPCOL_PORTALES),
        default=list(CAPCOL_PORTALES),
        help="Sub-portales CAPCOL a extraer/cargar (default: todos)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="refresh: recalcular marts desde todo staging en vez de solo lo cambiado",
    )
    parser.add_argument(
        "--fuentes",
        nargs="+",
        choices=list(orquestacion.FUENTES),
        default=None,
        help="actualizar: fuentes a correr (default: todas)",
    )
    parser.add_argument(
        "--status", action="store_true", help="migrate: solo informar pendientes"
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="migrate: marcar los archivos actuales como aplicados sin ejecutarlos",
    )
    parser.add_argument(
        "--meses",
        type=int,
        default=3,
        help="conciliar: cuántos cortes recientes evaluar (default 3)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Además de la consola, escribir el log a este archivo (UTF-8)",
    )
    return parser


def _ejecutar(args: argparse.Namespace) -> None:
    years = args.years or DEFAULT_YEARS
    if args.stage == "migrate":
        with psycopg.connect(**DB_CONFIG, autocommit=True) as conn:
            migrate.migrar(conn, baseline=args.baseline, solo_estado=args.status)
        return
    if args.stage == "conciliar":
        with psycopg.connect(**DB_CONFIG) as conn:
            conciliacion.verificar(conn, meses=args.meses)
        return
    if args.stage == "actualizar":
        orquestacion.actualizar(args.fuentes, args.years)
        return
    if args.stage in ("extract", "all"):
        for portal in args.portales:
            scrape(years, args.out, portal=portal)
    if args.stage in ("load", "all"):
        pipeline.load_years(years, args.out, tuple(args.portales))
    if args.stage == "bce":
        pipeline.load_bce()
    if args.stage == "tasas-historicas":
        pipeline.load_tasas_historicas()
    if args.stage == "boletin":
        pipeline.load_boletin(years, args.out)
    if args.stage == "seps":
        pipeline.load_seps(years)
    if args.stage == "refresh":
        pipeline.refresh(full=args.full)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(log_file=args.log_file)
    contador = orquestacion.ContadorErrores()
    logging.getLogger().addHandler(contador)
    try:
        return _codigo_salida(args, contador)
    finally:
        logging.getLogger().removeHandler(contador)


def _codigo_salida(args: argparse.Namespace, contador) -> int:
    try:
        if args.stage in ("extract", "conciliar") or (
            args.stage == "migrate" and args.status
        ):
            _ejecutar(args)  # no escriben en la base: sin bloqueo
        else:
            with orquestacion.bloqueo_corrida():
                _ejecutar(args)
    except orquestacion.CorridaEnCurso as e:
        log.warning("%s; no se hizo nada", e)
        return orquestacion.EXIT_BLOQUEADO
    except migrate.MigracionError as e:
        log.error("%s", e)
        return 1
    except Exception:
        log.exception("La etapa %s se interrumpió", args.stage)
        return 1

    if contador.errores:
        log.warning(
            "La etapa %s terminó con %d error(es) registrados: revisar el log",
            args.stage,
            contador.errores,
        )
        return orquestacion.EXIT_ERRORES
    return orquestacion.EXIT_OK


def run() -> None:
    """Entry point del script `benchmark-bancos` (pyproject) y de `python -m`."""
    sys.exit(main())


if __name__ == "__main__":
    run()
