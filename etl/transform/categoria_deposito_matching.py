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
}

# CAPCOL: "DE 1 A 30 DÍAS", "DE 31 A 90 DÍAS", ..., "DE MÁS DE 361 DÍAS" -- buckets de
# plazo de DEPÓSITOS A PLAZO, no una categoría de producto distinta.
_RANGO = re.compile(r"^DE\s+(\d+)\s+A\s+(\d+)\s+D[IÍ]AS$")
_SIN_TOPE = re.compile(r"^DE\s+M[AÁ]S\s+DE\s+(\d+)\s+D[IÍ]AS$")


class CategoriaNoResueltaError(ValueError):
    """El texto crudo no es ni una categoría conocida ni un bucket de plazo reconocible."""


def resolver_categoria_deposito(tipo_deposito_crudo: str) -> tuple[str, int | None, int | None]:
    """Devuelve (categoria, dias_desde, dias_hasta). dias_* son None salvo que la
    categoría resultante sea 'DEPÓSITOS A PLAZO' con un bucket de plazo reconocible."""
    if not tipo_deposito_crudo or not tipo_deposito_crudo.strip():
        raise CategoriaNoResueltaError("tipo_deposito vacío")

    texto = tipo_deposito_crudo.strip().upper()

    m = _RANGO.match(texto)
    if m:
        return "DEPÓSITOS A PLAZO", int(m.group(1)), int(m.group(2))

    m = _SIN_TOPE.match(texto)
    if m:
        return "DEPÓSITOS A PLAZO", int(m.group(1)), None

    if texto in CATEGORIAS_VALIDAS:
        return texto, None, None

    raise CategoriaNoResueltaError(
        f"No se pudo resolver categoria_deposito para '{tipo_deposito_crudo}'. "
        f"Agregar el valor a CATEGORIAS_VALIDAS o un patrón de plazo nuevo."
    )
