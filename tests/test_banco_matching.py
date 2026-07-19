import pytest

from etl.transform.banco_matching import BancoNoResueltoError, resolver_banco_codigo


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
