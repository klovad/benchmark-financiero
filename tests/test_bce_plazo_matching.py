import pytest

from etl.transform.bce_plazo_matching import PlazoNoResueltoError, resolver_plazo_bce


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
