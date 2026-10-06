import pytest

from benchmark_bancos.transform.bce_plazo_matching import PlazoNoResueltoError
from benchmark_bancos.transform.categoria_deposito_matching import (
    CategoriaNoResueltaError,
    resolver_categoria_deposito,
)


def test_plazo_bucket_with_range_separates_categoria_and_plazo():
    categoria, desde, hasta = resolver_categoria_deposito("DE 1 A 30 DÍAS")
    assert categoria == "DEPÓSITOS A PLAZO"
    assert (desde, hasta) == (1, 30)


def test_plazo_bucket_without_upper_bound():
    categoria, desde, hasta = resolver_categoria_deposito("DE MÁS DE 361 DÍAS")
    assert categoria == "DEPÓSITOS A PLAZO"
    assert (desde, hasta) == (361, None)


def test_plain_category_passes_through_without_plazo():
    categoria, desde, hasta = resolver_categoria_deposito("DEPÓSITOS DE AHORRO")
    assert categoria == "DEPÓSITOS DE AHORRO"
    assert (desde, hasta) == (None, None)


def test_all_13_real_capcol_values_resolve():
    valores = [
        "DE 1 A 30 DÍAS",
        "DE 31 A 90 DÍAS",
        "DE 91 A 180 DÍAS",
        "DE 181 A 360 DÍAS",
        "DE MÁS DE 361 DÍAS",
        "DEPÓSITOS DE AHORRO",
        "DEPÓSITOS DE CUENTA BÁSICA",
        "DEPÓSITOS DE GARANTÍA",
        "DEPÓSITOS MONETARIOS DE INSTITUCIONES FINANCIERAS",
        "DEPÓSITOS MONETARIOS QUE GENERAN INTERESES",
        "DEPÓSITOS MONETARIOS QUE NO GENERAN INTERESES",
        "DEPÓSITOS POR CONFIRMAR",
        "DEPÓSITOS RESTRINGIDOS",
    ]
    for v in valores:
        resolver_categoria_deposito(v)  # no debe lanzar


def test_unresolved_value_raises():
    with pytest.raises(CategoriaNoResueltaError):
        resolver_categoria_deposito("UN TIPO DE DEPOSITO INVENTADO")


def test_empty_value_raises():
    with pytest.raises(CategoriaNoResueltaError):
        resolver_categoria_deposito("")


def test_plazo_bucket_con_shape_valido_pero_desconocido_no_lanza():
    """Desde sql/27_dim_plazo_estado_validacion.sql: un texto que matchea el *shape* de
    un bucket de plazo CAPCOL ('DE X A Y DÍAS') pero no es uno de los 5 buckets reales
    verificados en producción YA NO aborta la carga -- se acepta y resuelve el rango
    real, quedando marcado AUTO_INGRESADO cuando llega a marts.dim_plazo."""
    categoria, desde, hasta = resolver_categoria_deposito("DE 500 A 600 DÍAS")
    assert categoria == "DEPÓSITOS A PLAZO"
    assert (desde, hasta) == (500, 600)


def test_plazo_bucket_sin_tope_con_shape_valido_pero_desconocido_no_lanza():
    categoria, desde, hasta = resolver_categoria_deposito("DE MÁS DE 999 DÍAS")
    assert categoria == "DEPÓSITOS A PLAZO"
    assert (desde, hasta) == (999, None)


def test_plazo_bucket_shape_invalido_sigue_lanzando():
    """Un texto que no matchea ni _RANGO ni _SIN_TOPE ni CATEGORIAS_VALIDAS sigue siendo
    fallo duro -- CategoriaNoResueltaError, no cambió con sql/27."""
    with pytest.raises(CategoriaNoResueltaError):
        resolver_categoria_deposito("DE ALGO A OTRO ALGO DÍAS")


def test_plazo_bucket_shape_valido_pero_rango_invertido_lanza_plazo_error():
    """Un shape válido con rango invertido (dias_desde > dias_hasta) es una anomalía real
    de parsing, no un bucket nuevo legítimo -- sigue abortando la carga."""
    with pytest.raises(PlazoNoResueltoError):
        resolver_categoria_deposito("DE 600 A 500 DÍAS")
