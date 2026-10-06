"""
Resuelve el texto crudo de `tipo_deposito` (CAPCOL) o `instrumento_captacion` (BCE) a
una categoría canónica de marts.dim_categoria_deposito, separando el plazo cuando
corresponde.

CAPCOL mezcla dos conceptos en `tipo_deposito`: 5 de sus 13 valores no son una
categoría de producto sino buckets de plazo de lo que BCE reporta como una sola
categoría "DEPÓSITOS A PLAZO" (ej. "DE 1 A 30 DÍAS") -- ver docs/fuentes_datos.md
sección 5. Este módulo separa ambos conceptos antes de que el dato llegue a staging,
igual que banco_matching.py hace con la identidad de banco.
"""

import re
import unicodedata

from benchmark_bancos.transform.bce_plazo_matching import validar_rango_plazo

CATEGORIAS_VALIDAS = {
    "DEPÓSITOS DE AHORRO",
    "DEPÓSITOS DE CUENTA BÁSICA",
    "DEPÓSITOS DE GARANTÍA",
    "DEPÓSITOS MONETARIOS QUE GENERAN INTERESES",
    "DEPÓSITOS MONETARIOS QUE NO GENERAN INTERESES",
    "DEPÓSITOS MONETARIOS DE INSTITUCIONES FINANCIERAS",
    "DEPÓSITOS POR CONFIRMAR",
    "DEPÓSITOS RESTRINGIDOS",
    "DEPÓSITOS A PLAZO",
    "FONDOS DE TARJETAHABIENTES",
    "OPERACIONES DE REPORTO",
    # SEPS (cooperativas/mutualistas): taxonomía simplificada vista/plazo/garantía/
    # restringidos. No se fusiona con AHORRO/MONETARIOS por similitud de nombre -- ver
    # docs/fuentes_datos.md sección 4.0 y sql/30_seps.sql.
    "DEPÓSITOS A LA VISTA",
}

# CAPCOL: "DE 1 A 30 DÍAS", "DE 31 A 90 DÍAS", ..., "DE MÁS DE 361 DÍAS" -- buckets de
# plazo de DEPÓSITOS A PLAZO, no una categoría de producto distinta.
_RANGO = re.compile(r"^DE\s+(\d+)\s+A\s+(\d+)\s+D[IÍ]AS$")
_SIN_TOPE = re.compile(r"^DE\s+M[AÁ]S\s+DE\s+(\d+)\s+D[IÍ]AS$")

# Universo verificado contra staging.depositos (2026-08-22): CAPCOL trae exactamente
# estos 5 buckets de plazo, sin cambios desde que se integró la fuente. Igual que
# PLAZOS_TSP_VALIDOS/PLAZOS_TSA_VALIDOS en bce_plazo_matching.py, este set ya NO es un
# gate duro (ver sql/27_dim_plazo_estado_validacion.sql): sigue siendo el universo
# CONFIRMADO -- un texto nuevo que matchee el *shape* de _RANGO/_SIN_TOPE y tenga un
# rango sano (validar_rango_plazo()) se acepta igual, aunque no esté acá, y se
# auto-ingresa en marts.dim_plazo con estado_validacion='AUTO_INGRESADO' para revisión
# posterior. Solo un shape no reconocido o un rango inválido siguen abortando la carga.
PLAZOS_VALIDOS = {
    "DE 1 A 30 DÍAS",
    "DE 31 A 90 DÍAS",
    "DE 91 A 180 DÍAS",
    "DE 181 A 360 DÍAS",
    "DE MÁS DE 361 DÍAS",
}


class CategoriaNoResueltaError(ValueError):
    """El texto crudo no es ni una categoría conocida ni un bucket de plazo reconocible."""


def resolver_categoria_deposito(
    tipo_deposito_crudo: str,
) -> tuple[str, int | None, int | None]:
    """Devuelve (categoria, dias_desde, dias_hasta). dias_* son None salvo que la
    categoría resultante sea 'DEPÓSITOS A PLAZO' con un bucket de plazo reconocible.

    Bucket de plazo: shape check primero (_RANGO/_SIN_TOPE), luego sanity de rango
    (validar_rango_plazo()) -- ambos siguen siendo fallo duro (PlazoNoResueltoError) si
    no matchean o el rango es inválido. Si shape+rango son válidos pero el texto no está
    en PLAZOS_VALIDOS, se acepta igual: no es un gate, ver comentario de PLAZOS_VALIDOS
    más arriba."""
    if not tipo_deposito_crudo or not tipo_deposito_crudo.strip():
        raise CategoriaNoResueltaError("tipo_deposito vacío")

    texto = tipo_deposito_crudo.strip().upper()

    m = _RANGO.match(texto)
    if m:
        desde, hasta = int(m.group(1)), int(m.group(2))
        validar_rango_plazo(desde, hasta, tipo_deposito_crudo)
        return "DEPÓSITOS A PLAZO", desde, hasta

    m = _SIN_TOPE.match(texto)
    if m:
        desde = int(m.group(1))
        validar_rango_plazo(desde, None, tipo_deposito_crudo)
        return "DEPÓSITOS A PLAZO", desde, None

    if texto in CATEGORIAS_VALIDAS:
        return texto, None, None

    raise CategoriaNoResueltaError(
        f"No se pudo resolver categoria_deposito para '{tipo_deposito_crudo}'. "
        f"Agregar el valor a CATEGORIAS_VALIDAS o un patrón de plazo nuevo."
    )


def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


_CATEGORIAS_SIN_TILDE = {_sin_tildes(c): c for c in CATEGORIAS_VALIDAS}


def resolver_categoria_deposito_seps(tipo_deposito_crudo: str) -> str:
    """SEPS escribe las categorías sin tilde ('DEPOSITOS A LA VISTA', 'DEPOSITOS DE
    GARANTIA'); se comparan sin tildes contra CATEGORIAS_VALIDAS y se devuelve la forma
    canónica con tildes (la que vive en marts.dim_categoria_deposito). SEPS no trae banda
    de plazo en el reporte con entidad, así que no hay (dias_desde, dias_hasta).
    Fail-fast igual que resolver_categoria_deposito()."""
    if not tipo_deposito_crudo or not str(tipo_deposito_crudo).strip():
        raise CategoriaNoResueltaError("tipo_deposito SEPS vacío")
    clave = _sin_tildes(" ".join(str(tipo_deposito_crudo).upper().split()))
    if clave in _CATEGORIAS_SIN_TILDE:
        return _CATEGORIAS_SIN_TILDE[clave]
    raise CategoriaNoResueltaError(
        f"No se pudo resolver categoria_deposito SEPS para '{tipo_deposito_crudo}'. "
        f"Agregar el valor a CATEGORIAS_VALIDAS (y a marts.dim_categoria_deposito)."
    )
