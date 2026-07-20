"""
Resuelve el nombre de un banco (de cualquier fuente: CAPCOL, BCE, Boletín) a un
banco_codigo canónico, ANTES de que el dato llegue a staging/marts.

La limpieza de identidad de banco vive aquí, no como una tabla de alias en el esquema
estrella: cada parser llama a resolver_banco_codigo() y escribe banco_codigo ya resuelto
en staging.*; marts.dim_banco se puebla directo desde ese valor (un solo join, sin
indirección).

Reglas determinísticas (tildes, mayúsculas, espacios, sufijos legales, prefijo BP/BANCO)
resuelven variaciones triviales. Lo que la regla no resuelve se busca en
etl/seeds/banco_crosswalk.csv (fuente, nombre_fuente, banco_codigo), sembrado a mano —
ahí es donde se fusionan los renames reales de CAPCOL (ej. 'BP COMERCIAL DE MANABI' /
'BP BANCO COMERCIAL DE MANABI' -> mismo banco_codigo) y se mapean los nombres legales
completos de BCE. Un nombre que no resuelve ni por regla ni por crosswalk lanza
BancoNoResueltoError -- la identidad de banco es curada, no se autogenera.

El nombre a mostrar (columna `banco`) y `tipo_entidad` de cada banco_codigo viven en
etl/seeds/banco_maestro.csv, para que sean deterministas sin importar qué variante de
texto llegó primero durante la carga.
"""

import csv
import re
import unicodedata
from pathlib import Path

_SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"
_CROSSWALK_PATH = _SEEDS_DIR / "banco_crosswalk.csv"
_MAESTRO_PATH = _SEEDS_DIR / "banco_maestro.csv"

_LEGAL_SUFFIXES = re.compile(r"\s*,?\s*\b(S\.A\.?|C\.A\.?|LTDA\.?)\s*$", re.IGNORECASE)

FUENTES_VALIDAS = {"CAPCOL", "BCE", "BOLETIN"}


class BancoNoResueltoError(ValueError):
    """El nombre de banco no resolvió ni por regla determinística ni por el crosswalk."""


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _normalizar(nombre: str) -> str:
    text = str(nombre).strip().upper()
    text = re.sub(r"\s+", " ", text)
    return text


def _cargar_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


_crosswalk_cache: dict[tuple[str, str], str] | None = None
_maestro_cache: dict[str, dict] | None = None


def _crosswalk() -> dict[tuple[str, str], str]:
    global _crosswalk_cache
    if _crosswalk_cache is None:
        _crosswalk_cache = {
            (row["fuente"], _normalizar(row["nombre_fuente"])): row["banco_codigo"]
            for row in _cargar_csv(_CROSSWALK_PATH)
        }
    return _crosswalk_cache


def maestro() -> dict[str, dict]:
    """banco_codigo -> {"banco": ..., "tipo_entidad": ...}"""
    global _maestro_cache
    if _maestro_cache is None:
        _maestro_cache = {row["banco_codigo"]: row for row in _cargar_csv(_MAESTRO_PATH)}
    return _maestro_cache


def _por_regla(normalizado: str) -> str | None:
    """Regla determinística de respaldo para variaciones triviales no sembradas en el
    crosswalk (ej. un banco nuevo que ya sigue la convención 'BP <nombre>' de CAPCOL)."""
    texto = normalizado
    if texto.startswith("BP "):
        texto = texto[3:]
    elif texto.startswith("BANCO "):
        texto = texto[len("BANCO "):]
    texto = _LEGAL_SUFFIXES.sub("", texto).strip()
    texto = _strip_accents(texto)
    texto = re.sub(r"[^A-Z0-9]+", "_", texto).strip("_")
    return texto or None


def resolver_banco_codigo(nombre: str | None, fuente: str) -> str:
    """Resuelve el nombre crudo de un banco (tal como aparece en la fuente) a un
    banco_codigo canónico, estable entre fuentes.

    fuente: 'CAPCOL' | 'BCE' | 'BOLETIN'
    Lanza BancoNoResueltoError si no se puede resolver -- no autogenera identidad nueva.
    """
    if fuente not in FUENTES_VALIDAS:
        raise ValueError(f"fuente inválida: {fuente!r} (debe ser una de {FUENTES_VALIDAS})")
    if not nombre or not str(nombre).strip():
        raise BancoNoResueltoError(f"Nombre de banco vacío (fuente={fuente})")

    normalizado = _normalizar(nombre)

    codigo = _crosswalk().get((fuente, normalizado))
    if codigo:
        return codigo

    codigo = _por_regla(normalizado)
    if codigo and codigo in maestro():
        return codigo

    raise BancoNoResueltoError(
        f"No se pudo resolver banco_codigo para '{nombre}' (fuente={fuente}, "
        f"normalizado='{normalizado}'). Agregar una fila a etl/seeds/banco_crosswalk.csv."
    )


# Mapea el tipo_entidad crudo del BCE (tsp/tsa, universo completo del sistema financiero)
# a los valores canónicos de marts.dim_banco.tipo_entidad (CHECK constraint en sql/07).
_TIPO_ENTIDAD_BCE = {
    "BANCOS PRIVADOS": "BANCO PRIVADO",
    "BANCOS PUBLICOS": "BANCO PUBLICO",
    "COOPERATIVAS DE AHORRO Y CREDITO": "COOPERATIVA",
    "MUTUALISTAS": "MUTUALISTA",
    "SOCIEDAD FINANCIERA": "SOCIEDAD FINANCIERA",
    "ADMINISTRADORA DE TARJETAS DE CREDITO": "TARJETAS DE CREDITO",
}


class EntidadBceNoMapeadaError(ValueError):
    """El tipo_entidad crudo de BCE no está en _TIPO_ENTIDAD_BCE -- hay que agregar el
    mapeo (probablemente el BCE agregó una categoría nueva) antes de continuar."""


def resolver_entidad_bce(razon_social: str, ruc: str, tipo_entidad_bce: str) -> tuple[str, str, str]:
    """Resuelve una fila de BCE tsp/tsa (CUALQUIER tipo de entidad del sistema
    financiero, no solo bancos privados) a (banco_codigo, banco, tipo_entidad).

    Dos caminos deliberadamente distintos:
    - **BANCOS PRIVADOS**: identidad curada, igual que `resolver_banco_codigo()` de
      siempre -- necesitan alinearse con CAPCOL/Boletín (3 fuentes describiendo el mismo
      banco), así que un nombre no sembrado en `banco_crosswalk.csv` sigue fallando
      fuerte (`BancoNoResueltoError`).
    - **Todo lo demás** (~420 entidades reales: cooperativas de ahorro y crédito,
      mutualistas, banca pública, sociedad financiera, administradoras de tarjetas de
      crédito -- confirmado contra el archivo real sin filtro, 2026-07-19): se
      auto-registran usando el **RUC** (identificador fiscal) como `banco_codigo`
      (`BCE_<ruc>`) -- estable ante renames de razón social, mismo criterio que ya
      resolvió el bug real de continuidad de Comercial de Manabí/Amibank, aplicado acá de
      forma sistemática en vez de caso por caso. No hay curación manual porque no hay
      otra fuente (CAPCOL/Boletín) con la que alinear estas ~420 entidades todavía -- si
      el proyecto agrega una fuente específica de cooperativas más adelante, ESE día
      hace falta un crosswalk real para esas entidades, no antes.
    """
    if tipo_entidad_bce not in _TIPO_ENTIDAD_BCE:
        raise EntidadBceNoMapeadaError(
            f"tipo_entidad de BCE no mapeado: '{tipo_entidad_bce}'. "
            f"Agregar el valor a _TIPO_ENTIDAD_BCE en banco_matching.py."
        )

    if tipo_entidad_bce == "BANCOS PRIVADOS":
        codigo = resolver_banco_codigo(razon_social, "BCE")
        info = maestro()[codigo]
        return codigo, info["banco"], info["tipo_entidad"]

    codigo = f"BCE_{ruc}"
    return codigo, str(razon_social).strip(), _TIPO_ENTIDAD_BCE[tipo_entidad_bce]
