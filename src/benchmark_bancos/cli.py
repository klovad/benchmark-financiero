"""Interfaz de línea de comandos del pipeline.

Uso (con uv):
    uv run benchmark-bancos all --years 2021 2022 2023 2024 2025   # CAPCOL: extract + load
    uv run benchmark-bancos load --portales publica                # solo carga, Banca Pública
    uv run benchmark-bancos bce                                    # BCE tsp/tsa
    uv run benchmark-bancos tasas-historicas                       # BCE TasasHistorico.htm
    uv run benchmark-bancos boletin --years 2025 2026              # Boletín Superbancos
    uv run benchmark-bancos seps --years 2021 2022 2023 2024 2025  # SEPS
    uv run benchmark-bancos refresh                                # solo marts (incremental)
    uv run benchmark-bancos refresh --full                         # solo marts (completo)

Equivalente sin el script instalado: `python -m benchmark_bancos <stage> ...`.
"""

import argparse
from pathlib import Path

from benchmark_bancos import pipeline
from benchmark_bancos.config import CAPCOL_PORTALES, DEFAULT_YEARS, RAW_DIR
from benchmark_bancos.extract.scrape_superbancos import scrape
from benchmark_bancos.logging_utils import setup_logging

STAGES = [
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
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
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
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    setup_logging()

    if args.stage in ("extract", "all"):
        for portal in args.portales:
            scrape(args.years, args.out, portal=portal)
    if args.stage in ("load", "all"):
        pipeline.load_years(args.years, args.out, tuple(args.portales))
    if args.stage == "bce":
        pipeline.load_bce()
    if args.stage == "tasas-historicas":
        pipeline.load_tasas_historicas()
    if args.stage == "boletin":
        pipeline.load_boletin(args.years, args.out)
    if args.stage == "seps":
        pipeline.load_seps(args.years)
    if args.stage == "refresh":
        pipeline.refresh(full=args.full)


if __name__ == "__main__":
    main()
