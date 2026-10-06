"""
Parser de las páginas mensuales TasasVigentes{MM}{YYYY}.htm del BCE.

Cada página trae 2 <table> HTML que en realidad mezclan 5 secciones lógicas vía celdas
combinadas (colspan) -- ver docs/fuentes_datos.md sección 2.3 y sql/12_schema_tasas_historicas.sql.
Confirmado leyendo la página real (TasasVigentes062026.htm) que la investigación inicial
subestimó el contenido real: 13 segmentos (no 16), 5 categorías en la sección de
instrumento (no 3), 6 buckets de plazo (no 3), 4 métricas de sistema (no 2).

pandas.read_html reconstruye cada tabla con columnas duplicadas por el colspan. IMPORTANTE:
en qué <table> física cae cada sección NO es estable a través de los años -- se confirmó
comparando meses reales que para un subconjunto de meses la sección "activas máximas"
(layout de 1 valor, 3 columnas de label fusionadas) y las otras 3 secciones (layout de 2
columnas independientes lado a lado) pueden terminar ambas dentro de la misma tabla física.
Por eso NO se asume "tabla 0 = activa_maxima, tabla 1 = resto": se concatenan las filas de
TODAS las tablas devueltas y se rastrea la sección vigente fila por fila, detectando el
layout de cada fila por su contenido (no por su posición de tabla).
"""

import re
from pathlib import Path

import pandas as pd

from benchmark_bancos.transform.bce_plazo_matching import (
    PlazoNoResueltoError,
    validar_rango_plazo,
)

_NUM = re.compile(r"^-?\d+[.,]\d+$")


def _to_float(s) -> float | None:
    if not isinstance(s, str) or not _NUM.match(s.strip()):
        return None
    return float(s.strip().replace(",", "."))


def _clean_label(s) -> str | None:
    if not isinstance(s, str):
        return None
    return s.strip() or None


# La única discrepancia real de nombre entre esta fuente y el universo de
# dim_subsegmento_credito (sembrado desde tsa): esta página omite el guion.
_SEGMENTO_ALIAS = {"PRODUCTIVO CORPORATIVO": "PRODUCTIVO - CORPORATIVO"}

# "Depósitos de Tarjetahabientes" (esta fuente) y "FONDOS DE TARJETAHABIENTES"
# (CAPCOL/BCE tsp) son el mismo concepto con wording distinto -- se armoniza al nombre ya
# sembrado en dim_categoria_deposito, no se crea un duplicado.
_CATEGORIA_ALIAS = {"DEPÓSITOS DE TARJETAHABIENTES": "FONDOS DE TARJETAHABIENTES"}

_PLAZO_RANGO = re.compile(r"^PLAZO\s+(\d+)\s*-\s*(\d+)$")
_PLAZO_SIN_TOPE = re.compile(r"^PLAZO\s+(\d+)\s+Y\s+M[AÁ]S$")

# Universo verificado contra staging.tasas_referenciales seccion='pasiva_plazo'
# (2026-08-22): esta fuente trae exactamente estos 6 buckets. Mismo criterio que
# PLAZOS_TSP_VALIDOS/PLAZOS_TSA_VALIDOS (src/benchmark_bancos/transform/bce_plazo_matching.py) y
# PLAZOS_VALIDOS (src/benchmark_bancos/transform/categoria_deposito_matching.py): ya NO es un gate duro
# (ver sql/27_dim_plazo_estado_validacion.sql), sigue siendo el universo CONFIRMADO -- un
# texto nuevo que matchee el *shape* de _PLAZO_RANGO/_PLAZO_SIN_TOPE y tenga un rango
# sano (validar_rango_plazo()) se acepta igual, aunque no esté acá, y se auto-ingresa en
# marts.dim_plazo con estado_validacion='AUTO_INGRESADO' para revisión posterior. Solo un
# shape no reconocido sigue abortando la carga.
PLAZOS_VALIDOS = {
    "PLAZO 30-60",
    "PLAZO 61-90",
    "PLAZO 91-120",
    "PLAZO 121-180",
    "PLAZO 181-360",
    # el regex _PLAZO_SIN_TOPE acepta "MAS"/"MÁS" (M[AÁ]S) porque esta fuente no es
    # 100% consistente con el acento -- se incluyen ambas variantes en el universo
    # válido para no romper filas reales por una diferencia de tilde.
    "PLAZO 361 Y MAS",
    "PLAZO 361 Y MÁS",
}


def _resolver_plazo(texto: str) -> tuple[int, int | None]:
    """Shape check primero (_PLAZO_RANGO/_PLAZO_SIN_TOPE), luego sanity de rango
    (validar_rango_plazo()) -- ambos siguen siendo fallo duro (PlazoNoResueltoError) si
    no matchean o el rango es inválido. Si shape+rango son válidos pero el texto no está
    en PLAZOS_VALIDOS, se acepta igual: no es un gate, ver comentario de PLAZOS_VALIDOS
    más arriba."""
    t = texto.strip().upper()

    m = _PLAZO_RANGO.match(t)
    if m:
        desde, hasta = int(m.group(1)), int(m.group(2))
        validar_rango_plazo(desde, hasta, texto)
        return desde, hasta

    m = _PLAZO_SIN_TOPE.match(t)
    if m:
        desde = int(m.group(1))
        validar_rango_plazo(desde, None, texto)
        return desde, None

    raise PlazoNoResueltoError(
        f"No se pudo resolver el plazo de TasasHistorico: '{texto}'. Formato no "
        f"reconocido (ni 'PLAZO X-Y' ni 'PLAZO X Y MAS')."
    )


def _segmento_label(raw: str) -> str:
    label = (
        re.sub(r"\d+$", "", raw.strip()).strip().upper()
    )  # quita superíndices de nota al pie (ej. "Inmobiliario3")
    return _SEGMENTO_ALIAS.get(label, label)


def _categoria_label(raw: str) -> str:
    label = (
        re.sub(r"[\d*]+$", "", raw.strip()).strip().upper()
    )  # quita marcadores de nota al pie (ej. "Depósitos a Plazo*")
    return _CATEGORIA_ALIAS.get(label, label)


# Orden de prioridad: "activa máximas" primero, porque su encabezado también contiene el
# texto "activas" y podría confundirse con el de "activas referenciales" si se buscara al revés.
_SECCION_MARCADORES = [
    ("TASAS DE INTERÉS ACTIVAS MÁXIMAS", "activa_maxima"),
    ("TASAS DE INTERÉS ACTIVAS EFECTIVAS REFERENCIALES", "activa_referencial"),
    (
        "TASAS DE INTERÉS PASIVAS EFECTIVAS PROMEDIO POR INSTRUMENTO",
        "pasiva_instrumento",
    ),
    ("TASAS DE INTERÉS PASIVAS EFECTIVAS REFERENCIALES POR PLAZO", "pasiva_plazo"),
    ("OTRAS TASAS REFERENCIALES", "sistema"),
]

_METRICAS_SISTEMA = {
    "TASA PASIVA REFERENCIAL": "tasa_pasiva_referencial_sistema",
    "TASA ACTIVA REFERENCIAL": "tasa_activa_referencial_sistema",
    "TASA LEGAL": "tasa_legal",
    "TASA MÁXIMA CONVENCIONAL": "tasa_maxima_convencional",
}


def _emitir(seccion: str, label: str, valor: float) -> dict | None:
    if seccion == "activa_maxima":
        return {
            "seccion": seccion,
            "dimension_valor": _segmento_label(label),
            "metrica": "tasa_activa_maxima",
            "valor": valor,
        }
    if seccion == "activa_referencial":
        return {
            "seccion": seccion,
            "dimension_valor": _segmento_label(label),
            "metrica": "tasa_activa_referencial",
            "valor": valor,
        }
    if seccion == "pasiva_instrumento":
        return {
            "seccion": seccion,
            "dimension_valor": _categoria_label(label),
            "metrica": "tasa_pasiva_promedio",
            "valor": valor,
        }
    if seccion == "pasiva_plazo":
        desde, hasta = _resolver_plazo(label)
        return {
            "seccion": seccion,
            "plazo_dias_desde": desde,
            "plazo_dias_hasta": hasta,
            "metrica": "tasa_pasiva_referencial",
            "valor": valor,
        }
    if seccion == "sistema":
        metrica = _METRICAS_SISTEMA.get(label.strip().upper())
        return (
            {"seccion": seccion, "metrica": metrica, "valor": valor}
            if metrica
            else None
        )
    return None


def _parse_filas(tablas: list[pd.DataFrame]) -> list[dict]:
    filas = []
    seccion = None
    for tabla in tablas:
        if tabla.shape[1] != 4:
            continue  # layout de página antigua no reconocido, se ignora esta tabla puntual
        for _, row in tabla.iterrows():
            col0, col1, col2, col3 = row[0], row[1], row[2], row[3]
            valores_distintos = len({str(col0), str(col1), str(col2), str(col3)})

            if valores_distintos == 1:
                # fila fusionada en las 4 columnas: encabezado/pie de sección o texto
                # informativo -- se usa solo para actualizar qué sección está vigente.
                texto = re.sub(r"\s+", " ", str(col0).upper())
                for marcador, nombre in _SECCION_MARCADORES:
                    if marcador in texto:
                        seccion = nombre
                        break
                continue

            if seccion is None:
                continue

            # Layout "1 valor" (activa_maxima: 3 columnas de label fusionadas + 1 valor)
            valor_ancho = _to_float(col3)
            if col0 == col1 == col2 and valor_ancho is not None:
                label = _clean_label(col0)
                if label is not None:
                    fila = _emitir(seccion, label, valor_ancho)
                    if fila:
                        filas.append(fila)
                continue

            # Layout "2 pares independientes" (resto de secciones)
            for label_col, valor_col in ((0, 1), (2, 3)):
                label, valor = _clean_label(row[label_col]), _to_float(row[valor_col])
                if label is None or valor is None:
                    continue
                fila = _emitir(seccion, label, valor)
                if fila:
                    filas.append(fila)
    return filas


def parse_tasas_historicas_file(path: Path, fecha) -> pd.DataFrame:
    """fecha: fin de mes correspondiente al archivo (ej. 2026-06-30 para
    TasasVigentes062026.htm) -- el nombre de archivo ya trae mes/año, no hace falta
    parsear el texto "Junio 2026" del HTML."""
    # pandas.read_html usa thousands=',' por defecto SIEMPRE (incluso especificando
    # decimal=","), lo que corrompe silenciosamente "7,99" -> "799" -- hay que fijar
    # thousands explícito a algo que no aparezca en los datos para desactivar ese default.
    tablas = pd.read_html(path, decimal=",", thousands=".")

    filas = _parse_filas(tablas)
    if not filas:
        raise ValueError(
            f"{path.name}: no se pudo extraer ninguna fila reconocible (layout no soportado)"
        )

    df = pd.DataFrame.from_records(filas)
    df["fecha"] = fecha
    for col in ("dimension_valor", "plazo_dias_desde", "plazo_dias_hasta"):
        if col not in df.columns:
            df[col] = None
    df["source_file"] = path.name
    return df[
        [
            "fecha",
            "seccion",
            "dimension_valor",
            "plazo_dias_desde",
            "plazo_dias_hasta",
            "metrica",
            "valor",
            "source_file",
        ]
    ]
