import pytest

from etl.transform.bce_plazo_matching import PlazoNoResueltoError
from etl.transform.categoria_deposito_matching import (
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


def test_plazo_bucket_con_shape_valido_pero_desconocido_lanza_plazo_error():
    """dim_plazo es un catálogo abierto por rango, no debe crecer silenciosamente: un
    texto que matchea el *shape* de un bucket de plazo CAPCOL ('DE X A Y DÍAS') pero no
    es uno de los 5 buckets reales verificados en producción debe fallar fuerte, no
    auto-aceptarse."""
    with pytest.raises(PlazoNoResueltoError):
        resolver_categoria_deposito("DE 500 A 600 DÍAS")


def test_plazo_bucket_sin_tope_con_shape_valido_pero_desconocido_lanza_plazo_error():
    with pytest.raises(PlazoNoResueltoError):
        resolver_categoria_deposito("DE MÁS DE 999 DÍAS")
