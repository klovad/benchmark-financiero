"""
Resuelve el par (canton, provincia) crudo del BCE (tsp/tsa) contra el catálogo
compartido `marts.dim_canton` -- mismo catálogo que ya usa CAPCOL (`fact_saldo_cartera`/
`fact_saldo_depositos`), NO una tabla de alias nueva (ver `docs/architecture.md`,
"Catálogos conformados").

Grano histórico (2026-09-01, `sql/28_bce_canton_grain.sql`): antes `parse_bce_tasas.py`
colapsaba cantón dentro de provincia con `_weighted_agg()` (`fact_captaciones_depositos`/
`fact_colocaciones_cartera` quedaban a grano provincia). Se cambia a grano cantón para
igualar el patrón Kimball ya usado por CAPCOL (`dim_canton` como dimensión directa,
`dim_provincia` como outrigger vía `dim_canton.provincia_id`).

SIEMPRE resolver por el PAR (canton, provincia) -- nunca cantón solo -- porque existen
cantones reales con el mismo nombre en dos provincias distintas (reclasificación
administrativa histórica real de Ecuador, no un error de dato): LA CONCORDIA
(Esmeraldas / Santo Domingo de los Tsáchilas), SANTO DOMINGO (Pichincha / Santo Domingo
de los Tsáchilas), BOLÍVAR (Carchi / Manabí), LORETO y AGUARICO (Napo / Orellana, previos
a la creación de la provincia de Orellana en 1998). Verificado contra `raw.bce_tasas_pasivas`/
`raw.bce_tasas_activas` completos (2026-09-01): 219 nombres de cantón distintos, 226 pares
(canton, provincia) distintos excluyendo el placeholder 'NACIONAL'.

Dos niveles de validación (mismo patrón two-tier que `dim_plazo`, ver
`sql/27_dim_plazo_estado_validacion.sql` y `docs/gobernanza_datos.md` regla de calidad #1
-- extendido acá a un 6to catálogo):

1. La `provincia` cruda no normaliza a ninguna de las 24 provincias reales del Ecuador
   ni a los 2 valores especiales sembrados en `marts.dim_provincia`
   (`ZONA NO DELIMITADA`, `S/N`) -> `CantonNoResueltoError`, fail-fast. Sin provincia
   conocida no hay geografía segura a la cual anclar el cantón -- esto sí sigue siendo
   una anomalía real (BCE cambió de ortografía de forma que `normalize_provincia()` ya
   no la cubre, o agregó una provincia que no existe hoy).
2. La `provincia` sí resuelve pero el par `(canton, provincia)` normalizado no está en
   el universo sembrado (`etl/seeds/canton_provincia.csv`, el mismo universo de 228 pares
   que `sql/28_bce_canton_grain.sql` sembró en `marts.dim_canton` con
   `estado_validacion='CONFIRMADO'`) -> **NO lanza**. Se devuelve el par normalizado tal
   cual -- `marts.dim_canton` lo auto-ingresa con `estado_validacion='AUTO_INGRESADO'`
   (DEFAULT de la columna) la próxima vez que `refresh_marts()` corra su
   `INSERT INTO marts.dim_canton ... ON CONFLICT (canton, provincia_id) DO NOTHING`,
   igual que un bucket de plazo nuevo hoy se auto-ingresa en `dim_plazo`.

Por qué `dim_canton` recibe two-tier (a diferencia de `dim_segmento_credito`/
`dim_subsegmento_credito`/`dim_categoria_deposito`/`dim_segmento_entidad`, que se quedan
con fail-fast absoluto): es un catálogo geográfico real y finito (INEC), no una
enumeración cerrada por definición NORMATIVA/regulatoria -- un cantón nuevo en el dato
(ej. BCE empieza a reportar un cantón que hoy no aparece porque ninguna entidad chica
tenía oficina ahí) es autoexplicativo una vez que la provincia ya es conocida, igual que
un rango de días nuevo lo es para `dim_plazo` -- no requiere interpretación humana previa
para saber qué significa.

INTERFAZ ESPERADA por el parser (`etl/transform/parse_bce_tasas.py`, carril de
data-engineer, fuera del alcance de este módulo): llamar
`resolver_canton_bce(canton_crudo, provincia_cruda)` fila por fila ANTES de escribir a
`staging.bce_tasas_pasivas`/`staging.bce_tasas_activas` (mismo punto donde hoy se llama
`resolver_plazo_bce()`/`resolver_entidad_bce()`). Si no lanza, escribir el par devuelto
tal cual a las columnas `staging.bce_tasas_pasivas`/`activas`.canton` / `.provincia`
(agregadas en `sql/28_bce_canton_grain.sql`) -- la resolución final a `canton_id` ocurre
en el `JOIN` de `refresh_marts()` (`etl/load/load_postgres.py`) contra
`marts.dim_canton (canton, provincia_id)`, exactamente igual que `banco_codigo`/
`segmento_id` se resuelven ahí y no acá.
"""

import csv
from pathlib import Path

from etl.config import PROVINCIA_REGION
from etl.transform.common import normalize_provincia

_SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"
_CANTON_PROVINCIA_PATH = _SEEDS_DIR / "canton_provincia.csv"

# Sembrados directo en marts.dim_provincia (sql/20_dim_provincia.sql) pero SIN región
# real -- no forman parte de PROVINCIA_REGION (que solo mapea las 24 provincias reales a
# su región). 'S/N' es el placeholder de BCE para filas a nivel nacional sin desagregar
# (siempre acompañado de canton='NACIONAL', relación 1:1 verificada contra
# raw.bce_tasas_pasivas completo); 'ZONA NO DELIMITADA' es el de CAPCOL.
_PROVINCIAS_ESPECIALES = {"ZONA NO DELIMITADA", "S/N"}
_PROVINCIAS_VALIDAS = set(PROVINCIA_REGION.keys()) | _PROVINCIAS_ESPECIALES

# Placeholder de "sin cantón desagregado" -- ver docstring del módulo y
# sql/28_bce_canton_grain.sql. Estructural para varios instrumentos de BCE (depósitos de
# ahorro, monetarios, fondos de tarjetahabientes, reportos: 100% NACIONAL siempre) y para
# todo el histórico 2008-~2015 (ningún instrumento traía cantón todavía) -- no es un dato
# faltante ni un error de parsing.
CANTON_NACIONAL = "NACIONAL"
PROVINCIA_SN = "S/N"


class CantonNoResueltoError(ValueError):
    """La `provincia` cruda no normaliza contra ninguna de las 24 provincias reales del
    Ecuador ni contra los 2 valores especiales de `marts.dim_provincia`
    (`ZONA NO DELIMITADA`, `S/N`). A diferencia de un cantón fuera del universo sembrado
    (que se auto-ingresa, ver `resolver_canton_bce`), esto sí sigue siendo un fallo duro:
    sin provincia conocida no hay geografía segura donde anclar el cantón."""


def normalize_canton(value: str | None) -> str | None:
    """Mismo criterio de acentos que `normalize_provincia()` (quita solo el acento agudo
    tras descomponer NFKD, conserva la Ñ) -- necesario para igualar la ortografía ya
    usada en `marts.dim_canton.canton` (heredada de CAPCOL: sin tilde salvo la Ñ, ej.
    `BIBLIAN`, `GIRON`, `LOGROÑO`, `OÑA`). Se delega en `normalize_provincia()` en vez de
    duplicar el algoritmo -- es textualmente el mismo procedimiento, solo aplicado a un
    texto de cantón en vez de provincia."""
    return normalize_provincia(value)


_seed_cache: set[tuple[str, str]] | None = None


def _seed_pairs() -> set[tuple[str, str]]:
    """Universo de 228 pares (canton, provincia) ya sembrados en `marts.dim_canton` con
    `estado_validacion='CONFIRMADO'` (`sql/28_bce_canton_grain.sql`) -- 132 de CAPCOL +
    95 nuevos de BCE + el placeholder `('NACIONAL', 'S/N')`. Ya NO es un gate duro (ver
    nivel 2 de `resolver_canton_bce`): un par que no está acá se acepta igual, solo queda
    marcado para revisión posterior en `marts.dim_canton` en vez de bloquear la carga.
    """
    global _seed_cache
    if _seed_cache is None:
        with open(_CANTON_PROVINCIA_PATH, encoding="utf-8") as f:
            _seed_cache = {
                (row["canton"], row["provincia"]) for row in csv.DictReader(f)
            }
    return _seed_cache


# Cantones donde BCE usa un nombre/forma distinta al ya sembrado en marts.dim_canton
# (heredado de CAPCOL) para EL MISMO cantón físico -- no son cantones nuevos, son alias
# de escritura. Identificados 2026-09-01 comparando (canton, provincia) de BCE contra
# dim_canton con difflib + verificación manual contra la división político-administrativa
# real de Ecuador (INEC) antes de tratarlos como el mismo cantón en vez de asumir que
# cualquier texto no encontrado es necesariamente nuevo:
#   - 'DISTRITO METROPOLITANO DE QUITO' es el nombre administrativo completo de 'QUITO'.
#   - 'EL EMPALME' / 'EMPALME': mismo cantón de Guayas, dim_canton ya lo tenía sin "EL".
#   - 'GENERAL ANTONIO ELIZALDE' / 'GENERAL ANTONIO ELIZALDE (BUCAY)': dim_canton ya
#     incluía el apodo "(BUCAY)" entre paréntesis.
#   - 'PUEBLOVIEJO' (una palabra, forma de BCE) / 'PUEBLO VIEJO' (dos palabras, ya en
#     dim_canton) -- mismo cantón de Los Ríos.
#   - 'SAN FRANCISCO DE ORELLANA' (nombre oficial completo) / 'ORELLANA' (forma corta ya
#     sembrada desde CAPCOL) -- único cantón de ese nombre en la provincia de Orellana.
# NO confundir con 'PUERTO QUITO' (cantón real y distinto de Pichincha, sí es net-new) ni
# con los pares de cantón-homónimo-en-otra-provincia de arriba (esos SÍ son 2 filas
# reales distintas, no alias).
_ALIASES_BCE: dict[tuple[str, str], tuple[str, str]] = {
    ("DISTRITO METROPOLITANO DE QUITO", "PICHINCHA"): ("QUITO", "PICHINCHA"),
    ("EL EMPALME", "GUAYAS"): ("EMPALME", "GUAYAS"),
    ("GENERAL ANTONIO ELIZALDE", "GUAYAS"): (
        "GENERAL ANTONIO ELIZALDE (BUCAY)",
        "GUAYAS",
    ),
    ("PUEBLOVIEJO", "LOS RIOS"): ("PUEBLO VIEJO", "LOS RIOS"),
    ("SAN FRANCISCO DE ORELLANA", "ORELLANA"): ("ORELLANA", "ORELLANA"),
}


def resolver_canton_bce(canton_crudo: str, provincia_cruda: str) -> tuple[str, str]:
    """Resuelve un par crudo (canton, provincia) de BCE tsp/tsa al par normalizado listo
    para escribir a `staging.bce_tasas_pasivas`/`staging.bce_tasas_activas` (columnas
    `canton`/`provincia`, `sql/28_bce_canton_grain.sql`) -- NO devuelve `canton_id`, esa
    resolución final ocurre en el `JOIN` de `refresh_marts()` contra `marts.dim_canton`.

    Lanza `CantonNoResueltoError` únicamente si la `provincia` no resuelve (nivel 1, ver
    docstring del módulo). Un cantón fuera del universo sembrado pero con provincia
    válida NUNCA lanza (nivel 2) -- se acepta y se auto-ingresa en `marts.dim_canton`.
    """
    if not provincia_cruda or not str(provincia_cruda).strip():
        raise CantonNoResueltoError(
            f"provincia vacía para canton='{canton_crudo}'. Sin provincia no hay "
            f"geografía segura donde anclar el cantón."
        )
    if not canton_crudo or not str(canton_crudo).strip():
        raise CantonNoResueltoError(f"canton vacío (provincia='{provincia_cruda}')")

    provincia_norm = normalize_provincia(provincia_cruda)
    if provincia_norm not in _PROVINCIAS_VALIDAS:
        raise CantonNoResueltoError(
            f"provincia '{provincia_cruda}' (normalizada '{provincia_norm}') no "
            f"resuelve contra marts.dim_provincia para canton='{canton_crudo}'. "
            f"Revisar si BCE cambió la ortografía o agregó una provincia nueva -- "
            f"agregar a etl/config.py::PROVINCIA_REGION si es una provincia real nueva."
        )

    canton_norm = normalize_canton(canton_crudo)
    canton_norm, provincia_norm = _ALIASES_BCE.get(
        (canton_norm, provincia_norm), (canton_norm, provincia_norm)
    )

    # Nivel 2: no es un gate. Un par fuera de _seed_pairs() se acepta igual -- solo se
    # deja constancia (vía marts.dim_canton.estado_validacion='AUTO_INGRESADO') de que no
    # estaba en el universo curado al momento de escribir sql/28. Ver es_canton_conocido()
    # más abajo para el hook de observabilidad opcional sobre este mismo universo.
    return canton_norm, provincia_norm


def es_canton_conocido(canton_normalizado: str, provincia_normalizada: str) -> bool:
    """True si el par (ya normalizado, tal como lo devuelve `resolver_canton_bce()`) está
    en el universo sembrado `CONFIRMADO` (`etl/seeds/canton_provincia.csv`, 228 pares).
    No cambia el comportamiento de `resolver_canton_bce()` -- esa función nunca lanza por
    esto -- es un hook de observabilidad opcional para que el parser
    (`parse_bce_tasas.py`) loguee un WARNING con el detalle de pares nuevos antes de que
    lleguen a `AUTO_INGRESADO`, mismo rol que
    `bce_plazo_matching.validar_universo_plazos_bce()` cumple para `dim_plazo`."""
    return (canton_normalizado, provincia_normalizada) in _seed_pairs()
