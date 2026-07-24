import pytest

from etl.transform.banco_matching import (
    BancoNoResueltoError,
    EntidadBceNoMapeadaError,
    resolver_banco_codigo,
    resolver_entidad_bce,
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


def test_resolver_entidad_bce_privados_usa_crosswalk_curado():
    codigo, banco, tipo, ruc = resolver_entidad_bce("BANCO PICHINCHA C.A.", "1790010937001", "BANCOS PRIVADOS")
    assert codigo == "PICHINCHA"
    assert tipo == "BANCO PRIVADO"
    assert ruc == "1790010937001"


def test_resolver_entidad_bce_no_privados_se_auto_registra_por_ruc():
    codigo, banco, tipo, ruc = resolver_entidad_bce(
        "COOPERATIVA DE AHORRO Y CREDITO 4 DE OCTUBRE", "691702324001", "COOPERATIVAS DE AHORRO Y CREDITO",
    )
    assert codigo == "BCE_691702324001"
    assert banco == "COOPERATIVA DE AHORRO Y CREDITO 4 DE OCTUBRE"
    assert tipo == "COOPERATIVA"
    assert ruc == "691702324001"


def test_resolver_entidad_bce_mismo_ruc_distinta_razon_social_da_mismo_codigo():
    a, _, _, _ = resolver_entidad_bce("ASOCIACION MUTUALISTA X", "123", "MUTUALISTAS")
    b, _, _, _ = resolver_entidad_bce("ASOCIACION MUTUALISTA X (RENOMBRADA)", "123", "MUTUALISTAS")
    assert a == b == "BCE_123"


def test_resolver_entidad_bce_tipo_entidad_no_mapeado_falla_fuerte():
    with pytest.raises(EntidadBceNoMapeadaError):
        resolver_entidad_bce("ALGO NUEVO", "999", "UNA_CATEGORIA_QUE_NO_EXISTE_TODAVIA")
