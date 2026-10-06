import pytest

from benchmark_bancos.transform.banco_matching import (
    BancoNoResueltoError,
    EntidadBceNoMapeadaError,
    RucInvalidoError,
    resolver_banco_codigo,
    resolver_entidad_bce,
    validar_ruc_estructura,
)


def test_capcol_manabi_variants_resolve_to_same_codigo():
    a = resolver_banco_codigo("BP COMERCIAL DE MANABI", "CAPCOL")
    b = resolver_banco_codigo("BP BANCO COMERCIAL DE MANABI", "CAPCOL")
    assert a == b == "COMERCIAL_MANABI"


def test_capcol_amibank_variants_resolve_to_same_codigo():
    a = resolver_banco_codigo("BANCO AMIBANK S.A.", "CAPCOL")
    b = resolver_banco_codigo("BANCO AMIBANK S.A., EN LIQUIDACION", "CAPCOL")
    assert a == b == "AMIBANK"


def test_bce_legal_name_resolves_to_same_codigo_as_capcol():
    assert resolver_banco_codigo("BANCO PICHINCHA C.A.", "BCE") == "PICHINCHA"
    assert resolver_banco_codigo("BANCO DE GUAYAQUIL S.A.", "BCE") == "GUAYAQUIL"
    assert resolver_banco_codigo("BP PICHINCHA", "CAPCOL") == "PICHINCHA"


def test_boletin_double_space_normalizes_correctly():
    nombre = "BP BANCO  DESARROLLO DE LOS PUEBLOS  S.A., CODESARROLLO"
    assert resolver_banco_codigo(nombre, "BOLETIN") == "CODESARROLLO"


def test_unresolved_name_raises_instead_of_autocreating():
    with pytest.raises(BancoNoResueltoError):
        resolver_banco_codigo("UN BANCO INVENTADO QUE NO EXISTE", "BCE")


def test_empty_name_raises():
    with pytest.raises(BancoNoResueltoError):
        resolver_banco_codigo("", "CAPCOL")
    with pytest.raises(BancoNoResueltoError):
        resolver_banco_codigo(None, "CAPCOL")


def test_invalid_fuente_raises_value_error():
    with pytest.raises(ValueError):
        resolver_banco_codigo("BP PICHINCHA", "OTRA_FUENTE")


def test_capcol_banca_publica_resuelve_al_mismo_codigo_bce_por_ruc():
    # Banca Pública (capcol-instituciones-publicas/, integrada 2026-09-01) reporta
    # ENTIDAD con sufijo "B. P."/"B.P." que no coincide con ningún patrón de
    # _por_regla() (no empieza con "BP "/"BANCO ", el sufijo no es S.A./C.A./LTDA) --
    # los 3 nombres crudos observados en archivos reales (2021-2025) se resuelven vía
    # banco_crosswalk.csv al MISMO banco_codigo "BCE_<ruc>" que ya generó
    # resolver_entidad_bce() al auto-registrar estas entidades desde BCE tsp/tsa, para
    # no crear una segunda identidad paralela para el mismo banco público. Los 3 RUC son
    # los mismos ya vigentes en marts.dim_banco (verificado contra la base viva
    # 2026-09-01) -- ver docs/fuentes_datos.md sección 1 y docs/gobernanza_datos.md.
    assert resolver_banco_codigo("BANECUADOR B. P.", "CAPCOL") == "BCE_1768183520001"
    assert (
        resolver_banco_codigo("BANCO DE DESARROLLO DEL ECUADOR B.P.", "CAPCOL")
        == "BCE_1760002950001"
    )
    assert (
        resolver_banco_codigo("CORPORACION FINANCIERA NACIONAL B.P.", "CAPCOL")
        == "BCE_1760003090001"
    )


def test_crosswalk_solo_apunta_a_identidad_curada():
    # 2026-10-05: los 3 bancos públicos de CAPCOL pasan al camino curado
    # (banco_maestro.csv), con nombre visible y estado CONFIRMADO deterministas. Antes el
    # crosswalk apuntaba a filas BCE_<ruc> que solo existían si BCE había corrido primero,
    # y el BdE se veía con su razón social histórica "BANCO DEL ESTADO".
    from benchmark_bancos.transform.banco_matching import _crosswalk, maestro

    fuera = {c for c in _crosswalk().values() if c not in maestro()}
    assert fuera == set()
    assert maestro()["BCE_1760002950001"]["banco"] == "BANCO DE DESARROLLO DEL ECUADOR"
    assert maestro()["BCE_1760002950001"]["tipo_entidad"] == "BANCO PUBLICO"


def test_resolver_entidad_bce_privados_usa_crosswalk_curado():
    codigo, banco, tipo, ruc = resolver_entidad_bce(
        "BANCO PICHINCHA C.A.", "1790010937001", "BANCOS PRIVADOS"
    )
    assert codigo == "PICHINCHA"
    assert tipo == "BANCO PRIVADO"
    assert ruc == "1790010937001"


def test_resolver_entidad_bce_no_privados_se_auto_registra_por_ruc():
    # RUC real de "COOPERATIVA DE AHORRO Y CREDITO 4 DE OCTUBRE" tal como vive hoy en
    # marts.dim_banco (13 dígitos, con el cero inicial de provincia -- el fixture viejo
    # de este test tenía "691702324001" (12 dígitos, sin el cero), un typo que quedó
    # invisible mientras no había validación estructural real de RUC (2026-08-30).
    codigo, banco, tipo, ruc = resolver_entidad_bce(
        "COOPERATIVA DE AHORRO Y CREDITO 4 DE OCTUBRE",
        "0691702324001",
        "COOPERATIVAS DE AHORRO Y CREDITO",
    )
    assert codigo == "BCE_0691702324001"
    assert banco == "COOPERATIVA DE AHORRO Y CREDITO 4 DE OCTUBRE"
    assert tipo == "COOPERATIVA"
    assert ruc == "0691702324001"


def test_resolver_entidad_bce_mismo_ruc_distinta_razon_social_da_mismo_codigo():
    # RUC real de una mutualista ya vigente en marts.dim_banco (13 dígitos,
    # estructuralmente válido) -- el fixture viejo "123" solo servía mientras no había
    # validación estructural real de RUC (2026-08-30).
    ruc_valido = "0190006247001"
    a, _, _, _ = resolver_entidad_bce(
        "ASOCIACION MUTUALISTA X", ruc_valido, "MUTUALISTAS"
    )
    b, _, _, _ = resolver_entidad_bce(
        "ASOCIACION MUTUALISTA X (RENOMBRADA)", ruc_valido, "MUTUALISTAS"
    )
    assert a == b == f"BCE_{ruc_valido}"


def test_resolver_entidad_bce_tipo_entidad_no_mapeado_falla_fuerte():
    # Falla por EntidadBceNoMapeadaError ANTES de llegar a validar el RUC -- por eso
    # "999" (estructuralmente inválido) no importa acá, es intencional.
    with pytest.raises(EntidadBceNoMapeadaError):
        resolver_entidad_bce("ALGO NUEVO", "999", "UNA_CATEGORIA_QUE_NO_EXISTE_TODAVIA")


def test_validar_ruc_estructura_ruc_real_valido():
    # RUC real de una cooperativa vigente en marts.dim_banco (2026-08-30).
    assert validar_ruc_estructura("0691702324001") is True


def test_validar_ruc_estructura_longitud_incorrecta_es_invalida():
    assert validar_ruc_estructura("691702324001") is False  # 12 dígitos, no 13
    assert validar_ruc_estructura("12345") is False


def test_validar_ruc_estructura_digito_verificador_incorrecto_es_invalido():
    # "0691702324001" es válido (ver test de arriba) -- se altera el dígito verificador
    # (posición 10, índice 9: '4' -> '5') manteniendo todo lo demás igual.
    assert validar_ruc_estructura("0691702325001") is False


def test_resolver_entidad_bce_ruc_invalido_no_privado_falla_fuerte():
    with pytest.raises(RucInvalidoError):
        resolver_entidad_bce(
            "COOPERATIVA INVENTADA", "691702324001", "COOPERATIVAS DE AHORRO Y CREDITO"
        )


def test_resolver_entidad_bce_privados_no_valida_estructura_de_ruc():
    # El camino BANCOS PRIVADOS nunca debe llamar a validar_ruc_estructura() -- un RUC
    # con formato inválido en ese camino no debe romper la resolución curada por nombre.
    codigo, _, _, ruc = resolver_entidad_bce(
        "BANCO PICHINCHA C.A.", "999", "BANCOS PRIVADOS"
    )
    assert codigo == "PICHINCHA"
    assert ruc == "999"
