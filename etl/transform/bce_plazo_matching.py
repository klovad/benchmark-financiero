"""
Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de días,
para poblar el mismo `marts.dim_plazo` compartido con CAPCOL (ver
etl/transform/categoria_deposito_matching.py para el caso análogo de CAPCOL).

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
    """El texto crudo de plazo del BCE no matchea ningún patrón conocido."""


def resolver_plazo_bce(plazo_crudo: str) -> tuple[int, int | None]:
    """Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto
    ('MAS DE ...')."""
    if not plazo_crudo or not plazo_crudo.strip():
        raise PlazoNoResueltoError("plazo vacío")

    texto = _PREFIJO.sub("", plazo_crudo.strip().upper()).strip()

    m = _RANGO_DIAS.match(texto)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = _MENOS_DIAS.match(texto)
    if m:
        return 1, int(m.group(1)) - 1

    m = _MAS_DIAS.match(texto)
    if m:
        return int(m.group(1)), None

    m = _RANGO_ANIOS.match(texto)
    if m:
        return int(m.group(1)) * DIAS_POR_ANIO, int(m.group(2)) * DIAS_POR_ANIO

    m = _MAS_ANIOS.match(texto)
    if m:
        return int(m.group(1)) * DIAS_POR_ANIO, None

    raise PlazoNoResueltoError(
        f"No se pudo resolver el plazo BCE para '{plazo_crudo}'. "
        f"Agregar un patrón nuevo a bce_plazo_matching.py."
    )
