"""
Parser de los archivos semanales de tasas de interés del BCE (tsp=pasivas, tsa=activas).

Ambos archivos comparten estructura (semana;ruc;razon_social;sector_financiero;
tipo_entidad;tipo_segmento;<instrumento_captacion|segmento_credito>;provincia;canton;
plazo;monto_total;numero_operaciones;<tasa_pasiva|tasa_activa>_efectiva;tasa_nominal),
71-123MB comprimidos / 711MB-1.75GB descomprimidos -- se lee por chunks directo desde el
zip, sin extraer a disco.

**Sin filtro de tipo_entidad** (corregido 2026-07-19: una versión anterior filtraba a
BANCOS PRIVADOS antes de que el dato llegara siquiera a raw.*, perdiendo ~85% de las
filas para siempre -- el archivo trae las 6 categorías del sistema financiero completo:
BANCOS PRIVADOS, BANCOS PUBLICOS, COOPERATIVAS DE AHORRO Y CREDITO (~400 entidades, la
inmensa mayoría del universo), MUTUALISTAS, SOCIEDAD FINANCIERA, ADMINISTRADORA DE
TARJETAS DE CREDITO -- confirmado contra el archivo real: 456/466 entidades distintas en
tsp/tsa). `read_raw()` captura TODO tal cual, sin agregar ni resolver identidad -- eso
alimenta `raw.*`. `parse_tsp_file`/`parse_tsa_file` agregan y resuelven identidad para
TODAS las entidades (no solo bancos privados): los bancos privados usan el crosswalk
curado de siempre (necesitan alinearse con CAPCOL/Boletín); el resto (~420 entidades) se
auto-registra por RUC -- ver `src/benchmark_bancos/transform/banco_matching.py::resolver_entidad_bce()`.

El grano de fact_captaciones_depositos/fact_colocaciones_cartera (nombres desde
2026-07-19, antes fact_tasas_pasivas/fact_tasas_activas) es, desde 2026-09-01
(sql/28_bce_canton_grain.sql), (fecha, banco, categoria/segmento, plazo, cantón) --
igualando el grano ya usado por CAPCOL (dim_canton como dimensión directa, dim_provincia
como outrigger vía dim_canton.provincia_id). Antes de esa migración el grano era
provincia (SIN cantón): el archivo trae cantón, pero se colapsaba dentro de provincia en
este mismo `_weighted_agg()` porque `fact_captaciones_depositos`/`fact_colocaciones_cartera`
solo tenían `provincia_id`. `canton`/`provincia` se resuelven contra
`src/benchmark_bancos/transform/canton_matching.py::resolver_canton_bce()` (mismo catálogo compartido con
CAPCOL, `marts.dim_canton`) ANTES de `_weighted_agg`, y ambos entran al `group_cols` --
`_weighted_agg` se mantiene como red de seguridad real, no solo defensiva: el archivo
fuente SÍ trae duplicados genuinos incluso al grano completo con cantón (verificado
2026-09-01 contra tsp_desde_200801.zip: 1030 filas en grupos duplicados de 2, mismo
RUC/fecha/instrumento/provincia/canton/plazo con montos distintos -- reportes corregidos
o reenviados por la misma entidad para la misma semana). Montos y operaciones se SUMAN,
las tasas se promedian PONDERADAS por monto_total de cada fila (no un promedio simple).

`tipo_segmento` (columna original, ver docs/fuentes_datos.md) es la clasificación
normativa de tamaño/estructura de CADA entidad -- BANCO GRANDE/MEDIANO/PEQUEÑO para
bancos privados, SEGMENTO 1-5/SIN SEGMENTO para cooperativas (JPRF, umbrales por
activos), SEGMENTO 1 MUTUALISTA para mutualistas, una sola categoría para el resto.
Detectada 2026-07-25 (el usuario preguntó dónde se había considerado -- no se había
considerado: se preservaba en raw.* pero se descartaba antes de staging sin examinar su
contenido). Es un atributo de la ENTIDAD en esa fecha, no del instrumento/segmento de
crédito -- se resuelve una sola vez por (fecha, banco_codigo) ANTES de la agregación por
cantón (`_resolve_segmento_entidad`), no se incluye en el group_cols de
`_weighted_agg` para no multiplicar filas. Es estable dentro de (fecha, banco_codigo) en
la inmensa mayoría de los casos; en los pocos donde no lo es (~1 en un millón de filas,
verificado), se resuelve por la fila de mayor monto_total, mismo criterio de
ponderación que ya se usa para las tasas.
"""

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark_bancos.transform.banco_matching import resolver_entidad_bce
from benchmark_bancos.transform.bce_plazo_matching import (
    PLAZOS_TSA_VALIDOS,
    PLAZOS_TSP_VALIDOS,
    resolver_plazo_bce,
    validar_universo_plazos_bce,
)
from benchmark_bancos.transform.canton_matching import resolver_canton_bce
from benchmark_bancos.transform.categoria_deposito_matching import CATEGORIAS_VALIDAS
from benchmark_bancos.transform.common import sha256_file

CHUNK_SIZE = 300_000

# Universo completo de segmento_credito de BCE (= subsegmento, nivel fino), igual al
# sembrado en sql/08_dim_segmento_categoria_plazo.sql / dim_subsegmento_credito (renombrada
# en sql/16_dim_segmento_normativo.sql) -- se valida acá antes de llegar a staging.
# Verificado (2026-07-19) contra el archivo tsa completo SIN filtrar por tipo_entidad:
# los 26 valores aparecen tal cual, ninguno nuevo aportado por entidades no-privadas.
SEGMENTOS_VALIDOS = {
    "COMERCIAL ORDINARIO",
    "COMERCIAL PRIORITARIO CORPORATIVO",
    "COMERCIAL PRIORITARIO EMPRESARIAL",
    "COMERCIAL PRIORITARIO PYMES",
    "CONSUMO",
    "CONSUMO MINORISTA",
    "CONSUMO ORDINARIO",
    "CONSUMO PRIORITARIO",
    "EDUCATIVO",
    "EDUCATIVO SOCIAL",
    "INMOBILIARIO",
    "INVERSIÓN PÚBLICA",
    "MICROCRÉDITO ACUMULACIÓN AMPLIADA (SE)",
    "MICROCRÉDITO ACUMULACIÓN SIMPLE (SE)",
    "MICROCRÉDITO AGRÍCOLA Y GANADERO",
    "MICROCRÉDITO DE ACUMULACIÓN AMPLIADA",
    "MICROCRÉDITO DE ACUMULACIÓN SIMPLE",
    "MICROCRÉDITO MINORISTA",
    "MICROCRÉDITO MINORISTA (SE)",
    "PRODUCTIVO - CORPORATIVO",
    "PRODUCTIVO AGRÍCOLA Y GANADERO",
    "PRODUCTIVO EMPRESARIAL",
    "PRODUCTIVO PYMES",
    "VIVIENDA",
    "VIVIENDA DE INTERÉS PÚBLICO",
    "VIVIENDA DE INTERÉS SOCIAL",
}

# Universo completo de tipo_segmento (= clasificación normativa de tamaño/estructura de
# la ENTIDAD, distinta de segmento_credito que clasifica el PRODUCTO). Verificado
# 2026-07-25 leyendo tsp y tsa completos, sin filtrar por tipo_entidad -- idéntico
# universo en ambos archivos, 14 valores. Cooperativas: JPRF-F-2023-074 (segmentación
# por activos, seps.gob.ec). Bancos privados: Superbancos ya usa este tier en las
# columnas de agregado del Boletín (BANCOS PRIVADOS GRANDES/MEDIANOS/PEQUEÑOS), pero acá
# es la primera vez que se ve etiquetado por banco individual -- ver dim_segmento_entidad.
TIPOS_SEGMENTO_VALIDOS = {
    "BANCO GRANDE",
    "BANCO MEDIANO",
    "BANCO PEQUEÑO",
    "BANCOS PUBLICOS",
    "SEGMENTO 1",
    "SEGMENTO 2",
    "SEGMENTO 3",
    "SEGMENTO 4",
    "SEGMENTO 5",
    "SIN SEGMENTO",
    "SEGMENTO 1 MUTUALISTA",
    "MUTUALISTAS",
    "SOCIEDAD FINANCIERA",
    "ADMINISTRADORA DE TARJETAS DE CREDITO",
}


class SegmentoNoResueltoError(ValueError):
    """segmento_credito de tsa no está en el universo sembrado de dim_subsegmento_credito."""


class TipoSegmentoNoResueltoError(ValueError):
    """tipo_segmento no está en el universo sembrado de dim_segmento_entidad."""


def _resolve_segmento_entidad(df: pd.DataFrame) -> pd.DataFrame:
    """Un tipo_segmento por (fecha, banco_codigo) -- atributo de la entidad, no del
    instrumento/plazo/provincia de cada fila. Estable en casi todos los casos; cuando no
    (raro, ver docstring del módulo), gana la fila de mayor monto_total."""
    idx = df.groupby(["fecha", "banco_codigo"])["monto_total"].idxmax()
    return df.loc[idx, ["fecha", "banco_codigo", "tipo_segmento"]].reset_index(
        drop=True
    )


def _single_csv_in_zip(zip_path: Path) -> str:
    names = [
        n for n in zipfile.ZipFile(zip_path).namelist() if n.lower().endswith(".csv")
    ]
    if len(names) != 1:
        raise ValueError(
            f"{zip_path.name}: se esperaba 1 csv dentro del zip, se encontraron {len(names)}"
        )
    return names[0]


def read_raw(zip_path: Path) -> pd.DataFrame:
    """Lee TODO el archivo por chunks directo desde el zip (sin extraer 700MB-1.75GB a
    disco), sin filtrar tipo_entidad -- captura completa para raw.*. `ruc` se lee como
    texto (no numérico) para no perder ceros a la izquierda."""
    csv_name = _single_csv_in_zip(zip_path)
    chunks = []
    with zipfile.ZipFile(zip_path) as zf, zf.open(csv_name) as f:
        for chunk in pd.read_csv(
            f,
            sep=";",
            decimal=",",
            encoding="utf-8",
            dtype={"ruc": str},
            chunksize=CHUNK_SIZE,
        ):
            chunks.append(chunk)
    df = pd.concat(chunks, ignore_index=True)
    df["fecha"] = pd.to_datetime(df["semana"], format="%d/%m/%Y").dt.date
    return df


def _weighted_agg(
    df: pd.DataFrame, group_cols: list[str], tasa_cols: list[str]
) -> pd.DataFrame:
    """Colapsa `group_cols` (desde 2026-09-01 incluye `canton`, ver docstring del módulo):
    SUM(monto_total)/SUM(numero_operaciones); cada tasa se promedia ponderada por el
    monto_total de las filas donde esa tasa específica no es nula (denominador propio por
    columna, no el monto_total agregado total, para no sesgar si una fila tiene monto pero
    tasa en blanco). Con `canton` en `group_cols` esto ya no colapsa geografía (cada fila
    resultante es prácticamente 1:1 con una fila fuente) pero sigue siendo necesaria como
    red de seguridad real, no cosmética: el archivo fuente trae duplicados genuinos incluso
    al grano completo con cantón (ver docstring del módulo)."""
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


def _resolve_identidad(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[tuple[str, str, str, str]]]:
    """Resuelve banco_codigo/banco/tipo_entidad/ruc para TODAS las filas -- solo sobre las
    combinaciones distintas de (razon_social, ruc, tipo_entidad) (cientos, no millones de
    filas), luego se pega de vuelta con merge(). Devuelve también la lista de TODAS las
    entidades resueltas (bancos privados incluidos, no solo las auto-registradas) para
    poblar staging.banco_maestro.ruc -- BCE es la única fuente que trae RUC, ver
    resolver_entidad_bce()."""
    claves = (
        df[["razon_social", "ruc", "tipo_entidad"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    resueltas = claves.apply(
        lambda r: resolver_entidad_bce(r["razon_social"], r["ruc"], r["tipo_entidad"]),
        axis=1,
    )
    claves["banco_codigo"] = [t[0] for t in resueltas]
    claves["banco_nombre"] = [t[1] for t in resueltas]
    claves["banco_tipo_entidad"] = [t[2] for t in resueltas]
    claves["banco_ruc"] = [t[3] for t in resueltas]

    df = df.merge(claves, on=["razon_social", "ruc", "tipo_entidad"], how="left")

    entidades = list(
        claves[["banco_codigo", "banco_nombre", "banco_tipo_entidad", "banco_ruc"]]
        .drop_duplicates(subset="banco_codigo")
        .itertuples(index=False, name=None)
    )
    return df, entidades


def _resolve_canton(df: pd.DataFrame) -> pd.DataFrame:
    """Resuelve canton/provincia (canton_matching.py::resolver_canton_bce) solo sobre las
    combinaciones DISTINTAS de (canton, provincia) crudas -- ~226 pares, no millones de
    filas -- luego se pega de vuelta con merge() (mismo patrón que _resolve_identidad
    para banco_codigo/RUC, cardinalidad baja frente al total de filas). Deja que
    CantonNoResueltoError propague sin capturar -- mismo criterio que
    SegmentoNoResueltoError/TipoSegmentoNoResueltoError en este módulo."""
    claves = df[["canton", "provincia"]].drop_duplicates().reset_index(drop=True)
    resueltas = claves.apply(
        lambda r: resolver_canton_bce(r["canton"], r["provincia"]), axis=1
    )
    claves["canton_resuelto"] = [t[0] for t in resueltas]
    claves["provincia_resuelta"] = [t[1] for t in resueltas]

    df = df.merge(claves, on=["canton", "provincia"], how="left")
    df["canton"] = df["canton_resuelto"]
    df["provincia"] = df["provincia_resuelta"]
    return df.drop(columns=["canton_resuelto", "provincia_resuelta"])


def _add_common_columns(
    df: pd.DataFrame, plazos_validos: set[str], fuente: str
) -> tuple[pd.DataFrame, list[tuple[str, str, str, str]]]:
    df = df.copy()
    df, entidades = _resolve_identidad(df)
    df = _resolve_canton(df)
    df["plazo_codigo"] = df["plazo"]
    validar_universo_plazos_bce(df["plazo"].unique(), plazos_validos, fuente)
    plazo_lookup = {v: resolver_plazo_bce(v) for v in df["plazo"].unique()}
    df["plazo_dias_desde"] = df["plazo"].map(lambda v: plazo_lookup[v][0])
    df["plazo_dias_hasta"] = df["plazo"].map(lambda v: plazo_lookup[v][1])
    return df, entidades


def parse_tsp_file(
    zip_path: Path, df_raw: pd.DataFrame | None = None
) -> tuple[pd.DataFrame, list[tuple[str, str, str, str]]]:
    """Devuelve (df_staging, entidades). `df_raw` permite reusar una lectura ya
    hecha (evita leer el zip de ~700MB dos veces si el llamador ya lo cargó para raw.*
    vía read_raw())."""
    source_hash = sha256_file(zip_path)
    df = df_raw if df_raw is not None else read_raw(zip_path)
    df, entidades = _add_common_columns(df, PLAZOS_TSP_VALIDOS, "tsp")

    categorias = df["instrumento_captacion"].str.strip().str.upper()
    desconocidas = set(categorias.unique()) - CATEGORIAS_VALIDAS
    if desconocidas:
        raise ValueError(f"instrumento_captacion desconocido en tsp: {desconocidas}")
    df["categoria_deposito"] = categorias

    df["tipo_segmento"] = df["tipo_segmento"].str.strip().str.upper()
    desconocidos_seg = set(df["tipo_segmento"].unique()) - TIPOS_SEGMENTO_VALIDOS
    if desconocidos_seg:
        raise TipoSegmentoNoResueltoError(
            f"tipo_segmento desconocido en tsp: {desconocidos_seg}"
        )
    segmento_entidad = _resolve_segmento_entidad(df)

    group_cols = [
        "fecha",
        "banco_codigo",
        "categoria_deposito",
        "plazo_dias_desde",
        "plazo_dias_hasta",
        "plazo_codigo",
        "provincia",
        "canton",
    ]
    result = _weighted_agg(df, group_cols, ["tasa_pasiva_efectiva", "tasa_nominal"])
    result = result.merge(segmento_entidad, on=["fecha", "banco_codigo"], how="left")
    result["source_file"] = zip_path.name
    result["source_hash"] = source_hash
    return result, entidades


def parse_tsa_file(
    zip_path: Path, df_raw: pd.DataFrame | None = None
) -> tuple[pd.DataFrame, list[tuple[str, str, str, str]]]:
    """Devuelve (df_staging, entidades) -- ver parse_tsp_file."""
    source_hash = sha256_file(zip_path)
    df = df_raw if df_raw is not None else read_raw(zip_path)
    df, entidades = _add_common_columns(df, PLAZOS_TSA_VALIDOS, "tsa")

    segmentos = df["segmento_credito"].str.strip().str.upper()
    desconocidos = set(segmentos.unique()) - SEGMENTOS_VALIDOS
    if desconocidos:
        raise SegmentoNoResueltoError(
            f"segmento_credito desconocido en tsa: {desconocidos}"
        )
    df["segmento_credito"] = segmentos

    df["tipo_segmento"] = df["tipo_segmento"].str.strip().str.upper()
    desconocidos_seg = set(df["tipo_segmento"].unique()) - TIPOS_SEGMENTO_VALIDOS
    if desconocidos_seg:
        raise TipoSegmentoNoResueltoError(
            f"tipo_segmento desconocido en tsa: {desconocidos_seg}"
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
        "canton",
    ]
    result = _weighted_agg(df, group_cols, ["tasa_activa_efectiva", "tasa_nominal"])
    result = result.merge(segmento_entidad, on=["fecha", "banco_codigo"], how="left")
    result["source_file"] = zip_path.name
    result["source_hash"] = source_hash
    return result, entidades
