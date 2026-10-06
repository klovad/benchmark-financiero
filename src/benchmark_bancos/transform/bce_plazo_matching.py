"""
Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de días,
para poblar el mismo `marts.dim_plazo` compartido con CAPCOL (ver
src/benchmark_bancos/transform/categoria_deposito_matching.py para el caso análogo de CAPCOL).

El BCE usa un prefijo de letra ordinal ("a. ", "b. ", ...) seguido del rango en DIAS
(tsp: 7 buckets) o una mezcla de DIAS/AÑOS (tsa: 14 buckets, plazos más largos
expresados en años) -- ver docs/fuentes_datos.md sección 2. No se fuerza una
equivalencia con los buckets de CAPCOL: se guarda el rango de días real de cada bucket,
tal cual lo reporta el BCE, y dim_plazo lo descubre por auto-inserción.
"""

import re

# Convención bancaria ecuatoriana de "año comercial" (12 meses de 30 días), consistente
# con cómo el BCE ya expresa los plazos largos de tsa en años en vez de días.
DIAS_POR_ANIO = 360

_PREFIJO = re.compile(r"^[A-ZÑ]\.\s*")
_RANGO_DIAS = re.compile(r"^(\d+)\s*-\s*(\d+)\s*D[IÍ]AS$")
_MENOS_DIAS = re.compile(r"^MENOS\s+DE\s+(\d+)\s*D[IÍ]AS$")
_MAS_DIAS = re.compile(r"^M[AÁ]S\s+DE\s+(\d+)\s*D[IÍ]AS$")
_RANGO_ANIOS = re.compile(r"^(\d+)\s*-\s*(\d+)\s*A[ÑN]OS$")
_MAS_ANIOS = re.compile(r"^M[AÁ]S\s+DE\s+(\d+)\s*A[ÑN]OS$")


class PlazoNoResueltoError(ValueError):
    """El texto crudo de plazo no matchea ningún patrón conocido (shape inválido), o
    matchea el patrón pero el rango resultante es inválido (ej. dias_desde > dias_hasta)
    -- error único para dim_plazo sin importar la fuente (tsp, tsa, CAPCOL vía
    categoria_deposito_matching.py, o TasasHistorico vía parse_tasas_historicas.py),
    igual que BancoNoResueltoError centraliza la identidad de banco en banco_matching.py.

    Desde sql/27_dim_plazo_estado_validacion.sql, un texto que SÍ matchea un shape
    conocido y tiene un rango sano pero NO está en el universo curado
    (PLAZOS_*_VALIDOS más abajo) YA NO lanza este error: se deja pasar y se auto-ingresa
    en marts.dim_plazo con estado_validacion='AUTO_INGRESADO' para revisión posterior
    (ver validar_universo_plazos_bce). Solo shape inválido o rango inválido siguen
    abortando la carga -- eso sigue siendo una anomalía real de parsing, no un bucket
    nuevo legítimo.
    """


def validar_rango_plazo(
    dias_desde: int, dias_hasta: int | None, texto_original: str
) -> None:
    """Sanity check de rango, aplicado DESPUÉS de que el shape ya matcheó un patrón
    conocido (ver resolver_plazo_bce, categoria_deposito_matching.resolver_categoria_deposito,
    parse_tasas_historicas._resolver_plazo -- los 3 puntos de validación que además de
    bce_plazo_matching.py resuelven texto crudo de plazo a un rango de días). dias_desde
    no puede ser negativo; si dias_hasta está presente (bucket cerrado) debe ser >=
    dias_desde. Un bucket abierto ('MAS DE N ...', dias_hasta=None) no cae en el segundo
    caso. Un rango invertido o negativo es una anomalía real de parsing (ej. un regex que
    matcheó un texto degenerado), no un bucket nuevo legítimo -- sigue fallando fuerte
    igual que un shape no reconocido, nunca se relaja a AUTO_INGRESADO."""
    if dias_desde < 0 or (dias_hasta is not None and dias_desde > dias_hasta):
        raise PlazoNoResueltoError(
            f"Rango de plazo inválido para '{texto_original}': dias_desde={dias_desde}, "
            f"dias_hasta={dias_hasta}. Esto es una anomalía de parsing (ej. un rango "
            f"invertido), no un bucket nuevo -- revisar el patrón regex o el dato fuente."
        )


# Universos verificados contra staging.bce_tasas_pasivas/activas (2026-08-22): tsp trae
# exactamente estos 7 buckets, tsa exactamente estos 14 (a-n, con los últimos 6 en años).
# dim_plazo es un catálogo COMPARTIDO entre fuentes (ver comentario en
# sql/... / src/benchmark_bancos/load/load_postgres.py). Estos sets ya NO son un gate duro (ver
# sql/27_dim_plazo_estado_validacion.sql): siguen siendo el universo CONFIRMADO -- todo
# texto nuevo cuyo *shape* matchea resolver_plazo_bce() y cuyo rango es sano se acepta y
# se auto-ingresa en marts.dim_plazo con estado_validacion='AUTO_INGRESADO' aunque no
# esté acá, para revisión posterior en vez de abortar la carga completa. Si el BCE cambia
# la cantidad/corte de buckets de forma que el texto YA NO matchea ningún shape conocido
# (o produce un rango inválido), eso sí sigue fallando fuerte -- ver PlazoNoResueltoError.
PLAZOS_TSP_VALIDOS = {
    "A. MENOS DE 30 DIAS",
    "B. 30 - 60 DIAS",
    "C. 61 - 90 DIAS",
    "D. 91 - 120 DIAS",
    "E. 121 - 180 DIAS",
    "F. 181 - 360 DIAS",
    "G. MAS DE 360 DIAS",
}

PLAZOS_TSA_VALIDOS = {
    "A. 1 - 29 DIAS",
    "B. 30 - 60 DIAS",
    "C. 61 - 120 DIAS",
    "D. 121 - 180 DIAS",
    "E. 181 - 360 DIAS",
    "F. 361 - 450 DIAS",
    "G. 451 - 540 DIAS",
    "H. 541 - 720 DIAS",
    "I. 2 - 4 AÑOS",
    "J. 4 - 6 AÑOS",
    "K. 6 - 8 AÑOS",
    "L. 8 - 10 AÑOS",
    "M. 10 - 12 AÑOS",
    "N. MAS DE 12 AÑOS",
}


def validar_universo_plazos_bce(
    plazos_crudos, universo_valido: set[str], fuente: str
) -> None:
    """Chequeo de dos niveles para TODOS los valores crudos de `plazo` observados en un
    archivo tsp/tsa que no están en `universo_valido` (mismo patrón de comparación por
    set que `segmento_credito`/`tipo_segmento` en parse_bce_tasas.py):

    1. Shape + rango: se resuelve cada desconocido vía resolver_plazo_bce(), que
       propaga PlazoNoResueltoError tal cual si el texto no matchea ningún patrón
       conocido o el rango resultante es inválido -- eso sigue siendo un fallo duro,
       aborta la carga.
    2. Si el shape matchea y el rango es sano pero el texto no está en
       `universo_valido`: NO se lanza. Se deja pasar -- marts.dim_plazo lo auto-ingresa
       con estado_validacion='AUTO_INGRESADO' (sql/27_dim_plazo_estado_validacion.sql)
       para revisión posterior, en vez de abortar toda la carga por un bucket nuevo y
       legítimo del BCE."""
    desconocidos = {str(p).strip().upper() for p in plazos_crudos} - universo_valido
    for texto in desconocidos:
        resolver_plazo_bce(texto)


def resolver_plazo_bce(plazo_crudo: str) -> tuple[int, int | None]:
    """Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto
    ('MAS DE ...'). Shape check vía los patrones _RANGO_DIAS/_MENOS_DIAS/_MAS_DIAS/
    _RANGO_ANIOS/_MAS_ANIOS (PlazoNoResueltoError si ninguno matchea), seguido de un
    sanity check de rango vía validar_rango_plazo() (PlazoNoResueltoError si el rango
    resultante es inválido, ej. un 'MENOS DE 1 DIAS' degenerado) -- ambos casos siguen
    siendo fallo duro. Un shape válido con rango sano SIEMPRE se acepta acá, sin importar
    si el texto está en PLAZOS_TSP_VALIDOS/PLAZOS_TSA_VALIDOS: ese universo curado ya no
    es un gate de esta función, ver validar_universo_plazos_bce()."""
    if not plazo_crudo or not plazo_crudo.strip():
        raise PlazoNoResueltoError("plazo vacío")

    texto = _PREFIJO.sub("", plazo_crudo.strip().upper()).strip()

    m = _RANGO_DIAS.match(texto)
    if m:
        desde, hasta = int(m.group(1)), int(m.group(2))
        validar_rango_plazo(desde, hasta, plazo_crudo)
        return desde, hasta

    m = _MENOS_DIAS.match(texto)
    if m:
        desde, hasta = 1, int(m.group(1)) - 1
        validar_rango_plazo(desde, hasta, plazo_crudo)
        return desde, hasta

    m = _MAS_DIAS.match(texto)
    if m:
        desde = int(m.group(1))
        validar_rango_plazo(desde, None, plazo_crudo)
        return desde, None

    m = _RANGO_ANIOS.match(texto)
    if m:
        desde = int(m.group(1)) * DIAS_POR_ANIO
        hasta = int(m.group(2)) * DIAS_POR_ANIO
        validar_rango_plazo(desde, hasta, plazo_crudo)
        return desde, hasta

    m = _MAS_ANIOS.match(texto)
    if m:
        desde = int(m.group(1)) * DIAS_POR_ANIO
        validar_rango_plazo(desde, None, plazo_crudo)
        return desde, None

    raise PlazoNoResueltoError(
        f"No se pudo resolver el plazo BCE para '{plazo_crudo}'. "
        f"Agregar un patrón nuevo a bce_plazo_matching.py."
    )
