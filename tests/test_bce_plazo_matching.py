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


def test_bucket_con_shape_valido_pero_fuera_del_universo_tsp_no_lanza():
    """Desde sql/27_dim_plazo_estado_validacion.sql: un texto que matchea el shape de
    resolver_plazo_bce() (ej. un bucket "h." nuevo que tsp nunca ha reportado) YA NO
    aborta la carga -- se deja pasar y se auto-ingresa en marts.dim_plazo con
    estado_validacion='AUTO_INGRESADO' para revisión posterior (ver
    etl/load/load_postgres.py, INSERT INTO marts.dim_plazo sin listar
    estado_validacion -> hereda el DEFAULT)."""
    validar_universo_plazos_bce(["h. MAS DE 1000 DIAS"], PLAZOS_TSP_VALIDOS, "tsp")


def test_bucket_fuera_del_universo_tsa_no_lanza():
    validar_universo_plazos_bce(["o. 12 - 20 AÑOS"], PLAZOS_TSA_VALIDOS, "tsa")


def test_bucket_shape_invalido_sigue_lanzando_incluso_fuera_del_universo():
    """Un texto que NO matchea ningún shape regex conocido sigue siendo fallo duro --
    esa parte del comportamiento no cambió con sql/27."""
    with pytest.raises(PlazoNoResueltoError):
        validar_universo_plazos_bce(["ESTO NO ES UN PLAZO"], PLAZOS_TSP_VALIDOS, "tsp")


def test_bucket_shape_valido_pero_rango_invertido_sigue_lanzando():
    """Un shape válido con rango invertido (dias_desde > dias_hasta) es una anomalía real
    de parsing, no un bucket nuevo legítimo -- sigue abortando la carga."""
    with pytest.raises(PlazoNoResueltoError):
        resolver_plazo_bce("h. 100 - 50 DIAS")


def test_bucket_shape_valido_fuera_del_universo_resuelve_rango_correcto():
    """Ejercita el camino completo de auto-ingesta: un bucket nuevo y desconocido pero
    con shape+rango válidos debe seguir resolviendo el rango real de días, no solo no
    lanzar."""
    assert resolver_plazo_bce("h. 1000 - 1100 DIAS") == (1000, 1100)
