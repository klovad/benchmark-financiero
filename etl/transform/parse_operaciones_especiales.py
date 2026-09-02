"""
Parser de operaciones_especiales.xlsx -- Banco de Guayaquil, es_operacion_especial='SI'.

El archivo (descarga manual a data/raw, fuente: SharePoint DataEngineeringBG-FINANCIERO/
BENCHMARK_TASAS) tiene EXACTAMENTE la estructura de BCE tsa (semana, ruc, razon_social,
sector_financiero, tipo_entidad, tipo_segmento, provincia, canton, segmento_credito,
plazo, monto_total, numero_operaciones, tasa_activa_efectiva, tasa_nominal), pero son
filas que en el tablero anterior se anexaban marcadas como operaciones especiales ('SI').

Se integran al MISMO grano de staging.bce_tasas_activas / marts.fact_colocaciones_cartera
(clienta por fecha x banco x segmento x plazo x provincia, con tasas ponderadas por
monto), distinguiéndose del resto por la columna es_operacion_especial. Reusa la
maquinaria de identidad/plazos/agregación de parse_bce_tasas.py para garantizar el
mismo criterio del resto de la cartera.

Diferencias con vs. tsa normal (parse_tsa_file):
- Origen es xlsx (pandas.read_excel), no zip/csv.
- `ruc` viene como entero (pierde el cero inicial real, ej. 990049459001 vs
  0990049459001) -> se lee como str y se rellena a 13 dígitos con zfill(13).
- `canton` trae espacios al final en algunos valores ('LAGO AGRIO ', 'GUAYAQUIL ') ->
  strip.
- Se forza es_operacion_especial = 'SI' en TODO el dataset.
- source_file = 'operaciones_especiales.xlsx'.
"""

from pathlib import Path

import pandas as pd

from etl.transform.banco_matching import resolver_entidad_bce
from etl.transform.bce_plazo_matching import (
    PLAZOS_TSA_VALIDOS,
    resolver_plazo_bce,
    validar_universo_plazos_bce,
)
from etl.transform.common import normalize_provincia
from etl.transform.parse_bce_tasas import (
    TIPOS_SEGMENTO_VALIDOS,
    SEGMENTOS_VALIDOS,
    _add_common_columns,
    _resolve_segmento_entidad,
    _weighted_agg,
    TipoSegmentoNoResueltoError,
    SegmentoNoResueltoError,
)

COLUMNAS_EXPECTADAS = {
    "semana",
    "ruc",
    "razon_social",
    "sector_financiero",
    "tipo_entidad",
    "tipo_segmento",
    "provincia",
    "canton",
    "segmento_credito",
    "plazo",
    "monto_total",
    "numero_operaciones",
    "tasa_activa_efectiva",
    "tasa_nominal",
}

FUENTE = "operaciones_especiales.xlsx"


def parse_operaciones_especiales_file(xlsx_path: Path) -> pd.DataFrame:
    """Lee operaciones_especiales.xlsx y devuelve el df de staging compatible con
    _BCE_TASAS_ACTIVAS_COLS + es_operacion_especial + source_file."""
    df = pd.read_excel(xlsx_path)
    faltantes = COLUMNAS_EXPECTADAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"{xlsx_path.name}: faltan columnas {sorted(faltantes)} "
            f"(esperadas: {sorted(COLUMNAS_EXPECTADAS)})"
        )

    df = df.copy()
    df["fecha"] = pd.to_datetime(df["semana"]).dt.date
    df["ruc"] = df["ruc"].astype(str).str.strip().str.zfill(13)
    df["canton"] = df["canton"].astype(str).str.strip()
    df["razon_social"] = df["razon_social"].astype(str).str.strip()
    df["tipo_segmento"] = df["tipo_segmento"].astype(str).str.strip().str.upper()

    df, entidades = _add_common_columns(df, PLAZOS_TSA_VALIDOS, "tsa")

    # Igual gate que parse_tsa_file sobre el universo sembrado.
    segmentos = df["segmento_credito"].str.strip().str.upper()
    desconocidos_seg = set(segmentos.unique()) - SEGMENTOS_VALIDOS
    if desconocidos_seg:
        raise SegmentoNoResueltoError(
            f"segmento_credito desconocido en operaciones especiales: {desconocidos_seg}"
        )
    df["segmento_credito"] = segmentos
    desconocidos_tipo = set(df["tipo_segmento"].unique()) - TIPOS_SEGMENTO_VALIDOS
    if desconocidos_tipo:
        raise TipoSegmentoNoResueltoError(
            f"tipo_segmento desconocido en operaciones especiales: {desconocidos_tipo}"
        )

    segmento_entidad = _resolve_segmento_entidad(df)

    group_cols = [
        "fecha",
        "banco_codigo",
        "segmento_credito",
        "plazo_dias_desde",
        "plazo_dias_hasta",
        "plazo_codigo",
        "provincia",
    ]
    result = _weighted_agg(df, group_cols, ["tasa_activa_efectiva", "tasa_nominal"])
    result = result.merge(segmento_entidad, on=["fecha", "banco_codigo"], how="left")

    result["es_operacion_especial"] = "SI"
    result["source_file"] = FUENTE
    return result