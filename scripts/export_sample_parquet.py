"""
Exporta marts.* a Parquet, para poder probar el modelo de datos (Power BI, notebooks,
lo que sea) sin tener Postgres cargado -- ej. en otra sesión/máquina donde el ETL
todavía no corrió.

Dos modos:
- Muestra de un mes (default): los 9 catálogos pequeños (dim_banco, dim_canton,
  dim_provincia, dim_segmento_credito, dim_subsegmento_credito, dim_segmento_entidad,
  dim_categoria_deposito, dim_plazo, dim_cuenta_contable) se exportan completos -- no
  tiene sentido recortarlos por mes, y
  los hechos filtrados necesitan el catálogo completo para resolver sus FK. dim_fecha se
  exporta acotada a las fechas que realmente aparecen en los hechos filtrados (mantiene
  el sample chico y autocontenido). Las 10 tablas de hechos se filtran por (anio, mes)
  vía dim_fecha -- CAPCOL es mensual (una fecha por mes), BCE tsp/tsa es semanal (~4-5
  fechas por mes), TasasHistorico/Boletín son mensuales.
- Histórico completo (--full): los catálogos + dim_fecha se exportan en un solo archivo
  (chicos); los hechos se particionan por año (`{tabla}_{anio}.parquet`) vía dim_fecha --
  necesario porque de un solo archivo, fact_colocaciones_cartera solo (histórico BCE
  semanal desde 2008) pesa 230MB, por encima del límite de 100MB/archivo de GitHub sin
  Git LFS. Particionado por año ningún archivo pasa ese límite. `--anios-recientes N`
  limita los hechos particionados a los últimos N años calendario con datos (los
  catálogos/dim_fecha se quedan completos igual, son chicos) -- útil para no versionar
  los ~394MB del histórico completo (2008-2026) cuando alcanza con una ventana reciente
  para pruebas; el directorio de salida se nombra `marts_ultimos_{N}_anios` en ese caso.

Uso: uv run scripts/export_sample_parquet.py [--anio 2025] [--mes 3]
     uv run scripts/export_sample_parquet.py --full
     uv run scripts/export_sample_parquet.py --full --anios-recientes 5
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
    "dim_banco",
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


def export_full(out_dir: Path, anios_recientes: int | None = None) -> None:
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
            if anios_recientes is not None:
                anios = anios[-anios_recientes:]
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
    parser.add_argument("--anio", type=int, default=2025)
    parser.add_argument("--mes", type=int, default=3)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Exporta todo el histórico, sin filtrar por mes",
    )
    parser.add_argument(
        "--anios-recientes",
        type=int,
        default=None,
        help="Con --full, limita los hechos a los últimos N años calendario con datos",
    )
    args = parser.parse_args()

    if args.full:
        if args.anios_recientes:
            destino = (
                PROJECT_ROOT
                / "data"
                / "samples"
                / f"marts_ultimos_{args.anios_recientes}_anios"
            )
        else:
            destino = PROJECT_ROOT / "data" / "samples" / "marts_full"
        export_full(destino, anios_recientes=args.anios_recientes)
    else:
        destino = (
            PROJECT_ROOT / "data" / "samples" / f"marts_{args.anio:04d}-{args.mes:02d}"
        )
        export_sample(args.anio, args.mes, destino)
    log.info("Listo: %s", destino)
