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
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


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
        _maestro_cache = {
            row["banco_codigo"]: row for row in _cargar_csv(_MAESTRO_PATH)
        }
    return _maestro_cache


def _por_regla(normalizado: str) -> str | None:
    """Regla determinística de respaldo para variaciones triviales no sembradas en el
    crosswalk (ej. un banco nuevo que ya sigue la convención 'BP <nombre>' de CAPCOL).
    """
    texto = normalizado
    if texto.startswith("BP "):
        texto = texto[3:]
    elif texto.startswith("BANCO "):
        texto = texto[len("BANCO ") :]
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
        raise ValueError(
            f"fuente inválida: {fuente!r} (debe ser una de {FUENTES_VALIDAS})"
        )
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


class RucInvalidoError(ValueError):
    """El RUC de una entidad no-privada de BCE no pasa la validación estructural
    (longitud, código de provincia, tercer dígito o dígito verificador módulo 11) --
    distinta de EntidadBceNoMapeadaError, que es sobre tipo_entidad, no sobre el RUC en
    sí. Solo se aplica al camino NO-privado de resolver_entidad_bce(): los bancos
    privados curados siguen resolviendo por banco_crosswalk.csv/banco_maestro.csv
    exactamente como antes, con o sin RUC estructuralmente válido (ver "7 pares de
    dim_banco.banco_codigo distintos comparten el mismo ruc" en
    docs/gobernanza_datos.md -- no se quiere que una validación nueva rompa esa vía
    curada ya establecida)."""


# Coeficientes del algoritmo estándar de dígito verificador módulo 11 para RUC de
# Ecuador -- verificados en esta sesión (2026-08-30) contra las 409 entidades no-privadas
# vigentes en marts.dim_banco (403 tercer-dígito 9, 6 tercer-dígito 6): 0 falsos
# negativos, el algoritmo no rechaza ningún RUC real ya cargado en producción. También
# contrastados contra una implementación de referencia pública e independiente
# (github.com/macool/id_ecuador, gema Ruby "id_ecuador", coeficientes idénticos) antes de
# confiar en el resultado.
_RUC_COEFS_SOCIEDAD_PRIVADA = [4, 3, 2, 7, 6, 5, 4, 3, 2]  # tercer dígito 9
_RUC_COEFS_SECTOR_PUBLICO = [3, 2, 7, 6, 5, 4, 3, 2]  # tercer dígito 6


def _ruc_digito_verificador_modulo11(digitos: list[int], coeficientes: list[int]) -> int | None:
    """Dígito verificador módulo 11 estándar (SRI Ecuador, sociedades). Devuelve None si
    el resultado matemático es 10 -- ese caso no tiene dígito verificador válido posible,
    así que cualquier RUC que caiga ahí es estructuralmente inválido por definición del
    propio algoritmo, no un bug de esta función."""
    suma = sum(d * c for d, c in zip(digitos, coeficientes))
    residuo = suma % 11
    verificador = 0 if residuo == 0 else 11 - residuo
    return None if verificador == 10 else verificador


def validar_ruc_estructura(ruc: str) -> bool:
    """Valida la estructura de un RUC ecuatoriano de sociedad privada/extranjera (tercer
    dígito '9') o del sector público (tercer dígito '6') -- los 2 únicos tipos que
    aparecen hoy entre las entidades no-privadas de BCE (auditado 2026-08-30 contra las
    409 vigentes en marts.dim_banco: 403 tipo 9, 6 tipo 6, ningún otro tercer dígito).

    No cubre el algoritmo de cédula/RUC de persona natural (tercer dígito 0-5, módulo 10)
    porque ninguna entidad de BCE lo usa hoy -- si algún día aparece una, agregar esa
    rama explícitamente, no relajar esta función para "dejarla pasar".

    Reglas:
    - 13 dígitos, todos numéricos (formato).
    - Código de provincia (2 primeros dígitos) entre 01 y 24. La excepción "30 =
      extranjero/otro" que aparece mencionada en algunas fuentes NO oficiales no se pudo
      confirmar contra ninguna fuente autoritativa (SRI) ni contra las 409 entidades
      reales ya cargadas (todas caen en 01-24) -- deliberadamente NO incluida. Si aparece
      en el futuro un RUC real con código 30, es un caso a investigar con evidencia
      nueva, no algo que deba pre-autorizarse sin confirmar.
    - Tercer dígito '9' (sociedad privada/extranjera) o '6' (sector público). Cualquier
      otro valor no está cubierto por esta función y se trata como inválido en este
      contexto (no significa que el RUC sea inválido en general, solo que está fuera del
      universo esperado para una entidad no-privada de BCE).
    - Dígito verificador módulo 11 sobre los coeficientes estándar de cada tipo
      (posición 10 para tipo 9, posición 9 para tipo 6 -- 1-indexado).
    """
    if not ruc or not str(ruc).isdigit() or len(ruc) != 13:
        return False
    provincia = int(ruc[0:2])
    if not (1 <= provincia <= 24):
        return False
    tercer_digito = ruc[2]
    digitos = [int(d) for d in ruc]
    if tercer_digito == "9":
        verificador = _ruc_digito_verificador_modulo11(
            digitos[0:9], _RUC_COEFS_SOCIEDAD_PRIVADA
        )
        return verificador is not None and verificador == digitos[9]
    if tercer_digito == "6":
        verificador = _ruc_digito_verificador_modulo11(
            digitos[0:8], _RUC_COEFS_SECTOR_PUBLICO
        )
        return verificador is not None and verificador == digitos[8]
    return False


def resolver_entidad_bce(
    razon_social: str, ruc: str, tipo_entidad_bce: str
) -> tuple[str, str, str, str]:
    """Resuelve una fila de BCE tsp/tsa (CUALQUIER tipo de entidad del sistema
    financiero, no solo bancos privados) a (banco_codigo, banco, tipo_entidad, ruc).

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

    El `ruc` de la fila se devuelve siempre (también para BANCOS PRIVADOS, donde antes se
    descartaba) -- BCE es la única de las 3 fuentes que trae RUC, así que es la única vía
    para poblar `dim_banco.ruc` (2026-07-23). Nota de calidad conocida: al menos un par de
    bancos privados reales comparten RUC en el archivo fuente (ej. Atlántida/D-MIRO) --
    ver "huecos de gobernanza" en docs/gobernanza_datos.md antes de tratar `ruc` como
    único por banco.
    """
    if tipo_entidad_bce not in _TIPO_ENTIDAD_BCE:
        raise EntidadBceNoMapeadaError(
            f"tipo_entidad de BCE no mapeado: '{tipo_entidad_bce}'. "
            f"Agregar el valor a _TIPO_ENTIDAD_BCE en banco_matching.py."
        )

    ruc = str(ruc).strip()
    if tipo_entidad_bce == "BANCOS PRIVADOS":
        codigo = resolver_banco_codigo(razon_social, "BCE")
        info = maestro()[codigo]
        return codigo, info["banco"], info["tipo_entidad"], ruc

    # Validación estructural real del RUC -- SOLO en el camino no-privado: banco_codigo
    # se deriva directo del RUC acá ("BCE_" + ruc), así que un RUC malformado no solo
    # sería un dato de mala calidad, sería la llave natural misma de la entidad. Los
    # bancos privados (arriba) no pasan por esto -- su identidad ya está curada por
    # nombre, el RUC es un atributo más, no la llave.
    if not validar_ruc_estructura(ruc):
        raise RucInvalidoError(
            f"RUC '{ruc}' de la entidad '{razon_social}' (tipo_entidad_bce="
            f"'{tipo_entidad_bce}') no pasa la validación estructural (13 dígitos, "
            f"código de provincia 01-24, tercer dígito 9 o 6, dígito verificador "
            f"módulo 11). Revisar el dato de origen antes de forzar el registro -- "
            f"ver validar_ruc_estructura() en banco_matching.py."
        )

    codigo = f"BCE_{ruc}"
    return codigo, str(razon_social).strip(), _TIPO_ENTIDAD_BCE[tipo_entidad_bce], ruc
