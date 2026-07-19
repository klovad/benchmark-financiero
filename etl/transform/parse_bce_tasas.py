"""
Parser de los archivos semanales de tasas de interés del BCE (tsp=pasivas, tsa=activas).

Ambos archivos comparten estructura (semana;ruc;razon_social;sector_financiero;
tipo_entidad;tipo_segmento;<instrumento_captacion|segmento_credito>;provincia;canton;
plazo;monto_total;numero_operaciones;<tasa_pasiva|tasa_activa>_efectiva;tasa_nominal),
71-123MB comprimidos / 711MB-1.75GB descomprimidos, ~3M/7.7M filas totales -- se lee por
chunks directo desde el zip (sin extraer a disco) y se filtra a BANCOS PRIVADOS antes de
acumular en memoria (ver docs/fuentes_datos.md sección 2).

El grano de fact_tasas_pasivas/activas es (fecha, banco, categoria/segmento, plazo,
provincia) -- SIN canton. El archivo trae canton como grano más fino dentro de cada
provincia (confirmado: ej. GUAYAS tiene más filas que solo GUAYAQUIL), así que hay que
reagregar: montos y operaciones se SUMAN, las tasas se promedian PONDERADAS por
monto_total de cada fila (no un promedio simple entre cantones), mismo criterio que
tasa_ponderada en fact_cartera/fact_depositos.
"""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from etl.transform.banco_matching import resolver_banco_codigo
from etl.transform.bce_plazo_matching import resolver_plazo_bce
from etl.transform.categoria_deposito_matching import CATEGORIAS_VALIDAS
from etl.transform.common import normalize_text, sha256_file

CHUNK_SIZE = 300_000

# Universo completo de segmento_credito de BCE, igual al sembrado en
# sql/08_dim_segmento_categoria_plazo.sql -- se valida acá antes de llegar a staging.
SEGMENTOS_VALIDOS = {
    "COMERCIAL ORDINARIO", "COMERCIAL PRIORITARIO CORPORATIVO", "COMERCIAL PRIORITARIO EMPRESARIAL",
    "COMERCIAL PRIORITARIO PYMES", "CONSUMO", "CONSUMO MINORISTA", "CONSUMO ORDINARIO",
    "CONSUMO PRIORITARIO", "EDUCATIVO", "EDUCATIVO SOCIAL", "INMOBILIARIO", "INVERSIÓN PÚBLICA",
    "MICROCRÉDITO ACUMULACIÓN AMPLIADA (SE)", "MICROCRÉDITO ACUMULACIÓN SIMPLE (SE)",
    "MICROCRÉDITO AGRÍCOLA Y GANADERO", "MICROCRÉDITO DE ACUMULACIÓN AMPLIADA",
    "MICROCRÉDITO DE ACUMULACIÓN SIMPLE", "MICROCRÉDITO MINORISTA", "MICROCRÉDITO MINORISTA (SE)",
    "PRODUCTIVO - CORPORATIVO", "PRODUCTIVO AGRÍCOLA Y GANADERO", "PRODUCTIVO EMPRESARIAL",
    "PRODUCTIVO PYMES", "VIVIENDA", "VIVIENDA DE INTERÉS PÚBLICO", "VIVIENDA DE INTERÉS SOCIAL",
}


class SegmentoNoResueltoError(ValueError):
    """segmento_credito de tsa no está en el universo sembrado de dim_segmento_credito."""


def _single_csv_in_zip(zip_path: Path) -> str:
    names = [n for n in zipfile.ZipFile(zip_path).namelist() if n.lower().endswith(".csv")]
    if len(names) != 1:
        raise ValueError(f"{zip_path.name}: se esperaba 1 csv dentro del zip, se encontraron {len(names)}")
    return names[0]


def _read_filtered(zip_path: Path) -> pd.DataFrame:
    """Lee por chunks directo desde el zip (sin extraer 700MB-1.75GB a disco) y filtra a
    BANCOS PRIVADOS chunk por chunk, para no cargar el sistema financiero completo en
    memoria."""
    csv_name = _single_csv_in_zip(zip_path)
    filtered = []
    with zipfile.ZipFile(zip_path) as zf, zf.open(csv_name) as f:
        for chunk in pd.read_csv(f, sep=";", decimal=",", encoding="utf-8", chunksize=CHUNK_SIZE):
            filtered.append(chunk[chunk["tipo_entidad"] == "BANCOS PRIVADOS"])
    return pd.concat(filtered, ignore_index=True)


def _map_unique(series: pd.Series, fn) -> pd.Series:
    """Aplica fn solo sobre los valores únicos (docenas, no millones de filas) y hace
    .map() de vuelta -- resolver_banco_codigo/resolver_plazo_bce hacen trabajo de texto
    no trivial, no conviene llamarlas fila por fila sobre ~3M filas."""
    lookup = {v: fn(v) for v in series.unique()}
    return series.map(lookup)


def _weighted_agg(df: pd.DataFrame, group_cols: list[str], tasa_cols: list[str]) -> pd.DataFrame:
    """Colapsa cantón dentro de cada provincia: SUM(monto_total)/SUM(numero_operaciones);
    cada tasa se promedia ponderada por el monto_total de las filas donde esa tasa
    específica no es nula (denominador propio por columna, no el monto_total agregado
    total, para no sesgar si una fila tiene monto pero tasa en blanco)."""
    df = df.copy()
    for col in tasa_cols:
        df[f"_{col}_num"] = df[col] * df["monto_total"]
        df[f"_{col}_den"] = df["monto_total"].where(df[col].notna())

    agg = {
        "monto_total": "sum",
        "numero_operaciones": "sum",
        **{f"_{col}_num": "sum" for col in tasa_cols},
        **{f"_{col}_den": "sum" for col in tasa_cols},
    }
    g = df.groupby(group_cols, dropna=False, as_index=False).agg(agg)
    for col in tasa_cols:
        g[col] = g[f"_{col}_num"] / g[f"_{col}_den"].replace(0, np.nan)
        g = g.drop(columns=[f"_{col}_num", f"_{col}_den"])
    return g


def _add_common_columns(df: pd.DataFrame) -> pd.DataFrame:
    df["fecha"] = pd.to_datetime(df["semana"], format="%d/%m/%Y").dt.date
    df["banco_codigo"] = _map_unique(df["razon_social"], lambda x: resolver_banco_codigo(x, "BCE"))
    df["provincia"] = df["provincia"].apply(normalize_text)
    df["plazo_codigo"] = df["plazo"]
    plazo_lookup = {v: resolver_plazo_bce(v) for v in df["plazo"].unique()}
    df["plazo_dias_desde"] = df["plazo"].map(lambda v: plazo_lookup[v][0])
    df["plazo_dias_hasta"] = df["plazo"].map(lambda v: plazo_lookup[v][1])
    return df


def parse_tsp_file(zip_path: Path) -> pd.DataFrame:
    source_hash = sha256_file(zip_path)
    df = _add_common_columns(_read_filtered(zip_path))

    categorias = df["instrumento_captacion"].str.strip().str.upper()
    desconocidas = set(categorias.unique()) - CATEGORIAS_VALIDAS
    if desconocidas:
        raise ValueError(f"instrumento_captacion desconocido en tsp: {desconocidas}")
    df["categoria_deposito"] = categorias

    group_cols = [
        "fecha", "banco_codigo", "categoria_deposito",
        "plazo_dias_desde", "plazo_dias_hasta", "plazo_codigo", "provincia",
    ]
    result = _weighted_agg(df, group_cols, ["tasa_pasiva_efectiva", "tasa_nominal"])
    result["source_file"] = zip_path.name
    result["source_hash"] = source_hash
    return result


def parse_tsa_file(zip_path: Path) -> pd.DataFrame:
    source_hash = sha256_file(zip_path)
    df = _add_common_columns(_read_filtered(zip_path))

    segmentos = df["segmento_credito"].str.strip().str.upper()
    desconocidos = set(segmentos.unique()) - SEGMENTOS_VALIDOS
    if desconocidos:
        raise SegmentoNoResueltoError(f"segmento_credito desconocido en tsa: {desconocidos}")
    df["segmento_credito"] = segmentos

    group_cols = [
        "fecha", "banco_codigo", "segmento_credito",
        "plazo_dias_desde", "plazo_dias_hasta", "plazo_codigo", "provincia",
    ]
    result = _weighted_agg(df, group_cols, ["tasa_activa_efectiva", "tasa_nominal"])
    result["source_file"] = zip_path.name
    result["source_hash"] = source_hash
    return result
