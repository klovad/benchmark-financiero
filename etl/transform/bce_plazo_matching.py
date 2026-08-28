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
    """El texto crudo de plazo no matchea ningún patrón conocido, o matchea el patrón
    pero no es un bucket conocido/verificado para esa fuente (ver PLAZOS_*_VALIDOS más
    abajo) -- error único para dim_plazo sin importar la fuente (tsp, tsa, CAPCOL vía
    categoria_deposito_matching.py, o TasasHistorico vía parse_tasas_historicas.py),
    igual que BancoNoResueltoError centraliza la identidad de banco en banco_matching.py.
    """


# Universos verificados contra staging.bce_tasas_pasivas/activas (2026-08-22): tsp trae
# exactamente estos 7 buckets, tsa exactamente estos 14 (a-n, con los últimos 6 en años).
# dim_plazo es un catálogo COMPARTIDO entre fuentes (ver comentario en
# sql/... / etl/load/load_postgres.py) -- que un texto nuevo matchee el *shape* de
# resolver_plazo_bce() no basta para aceptarlo en dim_plazo sin revisión: si el BCE algún
# día cambia la cantidad o el corte de buckets, eso debe fallar fuerte y forzar un cambio
# deliberado acá (agregar el bucket nuevo a este set), no crecer silenciosamente vía
# INSERT ... ON CONFLICT DO NOTHING en marts.dim_plazo.
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
    """Valida que TODOS los valores crudos de `plazo` observados en un archivo tsp/tsa
    estén en el universo conocido y verificado para esa fuente -- mismo patrón que
    `segmento_credito`/`tipo_segmento` en parse_bce_tasas.py (`set(...) - VALIDOS`).
    Lanza PlazoNoResueltoError si aparece un bucket no reconocido, en vez de dejarlo
    pasar silenciosamente hacia marts.dim_plazo."""
    desconocidos = {str(p).strip().upper() for p in plazos_crudos} - universo_valido
    if desconocidos:
        raise PlazoNoResueltoError(
            f"plazo desconocido en {fuente}: {sorted(desconocidos)}. Si es un bucket "
            f"nuevo y legítimo del BCE, agregarlo deliberadamente a PLAZOS_{fuente.upper()}_VALIDOS "
            f"en etl/transform/bce_plazo_matching.py (no relajar esta validación)."
        )


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
