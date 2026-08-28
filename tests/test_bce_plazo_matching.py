import pytest

from etl.transform.bce_plazo_matching import (
    PLAZOS_TSA_VALIDOS,
    PLAZOS_TSP_VALIDOS,
    PlazoNoResueltoError,
    resolver_plazo_bce,
    validar_universo_plazos_bce,
)


def test_tsp_7_buckets_reales_resuelven():
    assert resolver_plazo_bce("a. MENOS DE 30 DIAS") == (1, 29)
    assert resolver_plazo_bce("b. 30 - 60 DIAS") == (30, 60)
    assert resolver_plazo_bce("c. 61 - 90 DIAS") == (61, 90)
    assert resolver_plazo_bce("d. 91 - 120 DIAS") == (91, 120)
    assert resolver_plazo_bce("e. 121 - 180 DIAS") == (121, 180)
    assert resolver_plazo_bce("f. 181 - 360 DIAS") == (181, 360)
    assert resolver_plazo_bce("g. MAS DE 360 DIAS") == (360, None)


def test_tsa_14_buckets_reales_resuelven_incluyendo_anios():
    assert resolver_plazo_bce("a. 1 - 29 DIAS") == (1, 29)
    assert resolver_plazo_bce("h. 541 - 720 DIAS") == (541, 720)
    assert resolver_plazo_bce("i. 2 - 4 AÑOS") == (720, 1440)
    assert resolver_plazo_bce("n. MAS DE 12 AÑOS") == (4320, None)


def test_prefijo_ordinal_no_es_obligatorio_para_el_match():
    assert resolver_plazo_bce("30 - 60 DIAS") == (30, 60)


def test_plazo_no_reconocido_lanza_error():
    with pytest.raises(PlazoNoResueltoError):
        resolver_plazo_bce("UN PLAZO INVENTADO")


def test_plazo_vacio_lanza_error():
    with pytest.raises(PlazoNoResueltoError):
        resolver_plazo_bce("")


def test_universo_tsp_completo_no_lanza():
    validar_universo_plazos_bce(PLAZOS_TSP_VALIDOS, PLAZOS_TSP_VALIDOS, "tsp")


def test_universo_tsa_completo_no_lanza():
    validar_universo_plazos_bce(PLAZOS_TSA_VALIDOS, PLAZOS_TSA_VALIDOS, "tsa")


def test_universo_tolera_minusculas_y_espacios_como_el_dato_real():
    # plazo_codigo real en staging trae la letra ordinal en minúscula ("a. ", "b. ", ...)
    # con el resto en mayúscula -- ver etl/transform/parse_bce_tasas.py.
    validar_universo_plazos_bce(
        [" a. menos de 30 dias ", "b. 30 - 60 dias"], PLAZOS_TSP_VALIDOS, "tsp"
    )


def test_bucket_con_shape_valido_pero_fuera_del_universo_tsp_lanza():
    """Un texto que matchea el shape de resolver_plazo_bce() (ej. un bucket "h." nuevo
    que tsp nunca ha reportado) no debe entrar a marts.dim_plazo sin revisión."""
    with pytest.raises(PlazoNoResueltoError):
        validar_universo_plazos_bce(["h. MAS DE 1000 DIAS"], PLAZOS_TSP_VALIDOS, "tsp")


def test_bucket_fuera_del_universo_tsa_lanza():
    with pytest.raises(PlazoNoResueltoError):
        validar_universo_plazos_bce(["o. 12 - 20 AÑOS"], PLAZOS_TSA_VALIDOS, "tsa")
