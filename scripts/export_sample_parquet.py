"""
Exporta marts.* a Parquet, para poder probar el modelo de datos (notebooks, BI, lo que
sea) sin tener Postgres cargado. No es data productiva: la fuente de verdad es Postgres.

Tres modos:
- Últimos meses (default, `--meses-recientes 13`): lo que se versiona en
  `data/samples/marts_ultimos_13_meses/` (2026-10-09; antes 5 años, ~178 MB). Catálogos y
  dim_fecha completos (chicos, y los hechos necesitan el catálogo completo para resolver
  sus FK); cada hecho filtrado a sus últimos N meses con datos (cada fuente llega a un mes
  distinto: Boletín y BCE van uno adelante de CAPCOL/SEPS), un archivo por tabla.
- Histórico completo (`--full`): hechos particionados por año (`{tabla}_{anio}.parquet`)
  para no pasar el límite de 100 MB por archivo de GitHub. No se versiona.
- Un mes puntual (`--anio 2025 --mes 3`): dim_fecha acotada a las fechas usadas.

Uso: uv run scripts/export_sample_parquet.py                     # últimos 13 meses
     uv run scripts/export_sample_parquet.py --meses-recientes 24
     uv run scripts/export_sample_parquet.py --full
     uv run scripts/export_sample_parquet.py --anio 2025 --mes 3
"""

import argparse
import logging
import warnings
from pathlib import Path

import pandas as pd
import psycopg

from benchmark_bancos.config import DB_CONFIG, PROJECT_ROOT

log = logging.getLogger(__name__)

# pd.read_sql con una conexión psycopg 3 funciona bien; pandas solo avisa que no la testea.
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

CATALOGOS_COMPLETOS = [
    "dim_entidad",
    "dim_canton",
    "dim_provincia",
    "dim_segmento_credito",
    "dim_subsegmento_credito",
    "dim_segmento_entidad",
    "dim_categoria_deposito",
    "dim_plazo",
    "dim_cuenta_contable",
]

FACTS = [
    "fact_saldo_cartera",
    "fact_saldo_depositos",
    "fact_captaciones_depositos",
    "fact_colocaciones_cartera",
    "fact_tasas_referenciales_cartera",
    "fact_tasas_referenciales_depositos_instrumento",
    "fact_tasas_referenciales_depositos_plazo",
    "fact_tasas_referenciales_sistema",
    "fact_balance",
    "fact_pyg",
]


def export_recientes(out_dir: Path, meses: int) -> None:
    """Catálogos completos + cada hecho con sus últimos `meses` meses con datos."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(**DB_CONFIG, autocommit=True) as conn:
        for tabla in CATALOGOS_COMPLETOS + ["dim_fecha"]:
            df = pd.read_sql(f"SELECT * FROM marts.{tabla}", conn)
            df.to_parquet(out_dir / f"{tabla}.parquet", index=False)
            log.info("%s: %d filas (catálogo completo)", tabla, len(df))

        for tabla in FACTS:
            df = pd.read_sql(
                f"""
                WITH meses AS (
                    SELECT DISTINCT d.anio_mes FROM marts.{tabla} f
                    JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
                    ORDER BY d.anio_mes DESC LIMIT %(meses)s
                )
                SELECT f.* FROM marts.{tabla} f
                JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
                WHERE d.anio_mes IN (SELECT anio_mes FROM meses)
                """,
                conn,
                params={"meses": meses},
            )
            df.to_parquet(out_dir / f"{tabla}.parquet", index=False)
            log.info("%s: %d filas (últimos %d meses)", tabla, len(df), meses)


def export_full(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(**DB_CONFIG, autocommit=True) as conn:
        for tabla in CATALOGOS_COMPLETOS + ["dim_fecha"]:
            df = pd.read_sql(f"SELECT * FROM marts.{tabla}", conn)
            df.to_parquet(out_dir / f"{tabla}.parquet", index=False)
            log.info("%s: %d filas (catálogo completo)", tabla, len(df))

        for tabla in FACTS:
            anios = pd.read_sql(
                f"""
                SELECT DISTINCT d.anio FROM marts.{tabla} f
                JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
                ORDER BY d.anio
                """,
                conn,
            )["anio"].tolist()
            for anio in anios:
                df = pd.read_sql(
                    f"""
                    SELECT f.* FROM marts.{tabla} f
                    JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
                    WHERE d.anio = %(anio)s
                    """,
                    conn,
                    params={"anio": anio},
                )
                df.to_parquet(out_dir / f"{tabla}_{anio}.parquet", index=False)
                log.info("%s_%d: %d filas", tabla, anio, len(df))


def export_sample(anio: int, mes: int, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(**DB_CONFIG, autocommit=True) as conn:
        for tabla in CATALOGOS_COMPLETOS:
            df = pd.read_sql(f"SELECT * FROM marts.{tabla}", conn)
            df.to_parquet(out_dir / f"{tabla}.parquet", index=False)
            log.info("%s: %d filas (catálogo completo)", tabla, len(df))

        fecha_ids: set[int] = set()
        for tabla in FACTS:
            df = pd.read_sql(
                f"""
                SELECT f.* FROM marts.{tabla} f
                JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
                WHERE d.anio = %(anio)s AND d.mes = %(mes)s
                """,
                conn,
                params={"anio": anio, "mes": mes},
            )
            df.to_parquet(out_dir / f"{tabla}.parquet", index=False)
            fecha_ids.update(df["fecha_id"].unique().tolist())
            log.info("%s: %d filas (%04d-%02d)", tabla, len(df), anio, mes)

        dim_fecha = pd.read_sql(
            "SELECT * FROM marts.dim_fecha WHERE fecha_id = ANY(%(ids)s)",
            conn,
            params={"ids": sorted(fecha_ids)},
        )
        dim_fecha.to_parquet(out_dir / "dim_fecha.parquet", index=False)
        log.info(
            "dim_fecha: %d filas (fechas usadas por los hechos exportados)",
            len(dim_fecha),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anio", type=int, default=None)
    parser.add_argument("--mes", type=int, default=None)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Exporta todo el histórico, sin filtrar por mes",
    )
    parser.add_argument(
        "--meses-recientes",
        type=int,
        default=13,
        help="Modo por defecto: últimos N meses con datos de cada hecho",
    )
    args = parser.parse_args()

    if args.full:
        destino = PROJECT_ROOT / "data" / "samples" / "marts_full"
        export_full(destino)
    elif args.anio and args.mes:
        destino = (
            PROJECT_ROOT / "data" / "samples" / f"marts_{args.anio:04d}-{args.mes:02d}"
        )
        export_sample(args.anio, args.mes, destino)
    else:
        destino = (
            PROJECT_ROOT
            / "data"
            / "samples"
            / f"marts_ultimos_{args.meses_recientes}_meses"
        )
        export_recientes(destino, args.meses_recientes)
    log.info("Listo: %s", destino)
