import pandas as pd
import pytest

from benchmark_bancos.transform.bce_plazo_matching import PlazoNoResueltoError
from benchmark_bancos.transform.parse_tasas_historicas import (
    _categoria_label,
    _emitir,
    _normalizar_ancho,
    _parse_filas,
    _resolver_plazo,
    _segmento_label,
)


def test_segmento_alias_agrega_el_guion_que_falta_en_esta_fuente():
    assert _segmento_label("Productivo Corporativo") == "PRODUCTIVO - CORPORATIVO"


def test_segmento_label_quita_superindice_de_nota_al_pie():
    assert _segmento_label("Inmobiliario3") == "INMOBILIARIO"


def test_categoria_alias_armoniza_tarjetahabientes():
    assert (
        _categoria_label("Depósitos de Tarjetahabientes")
        == "FONDOS DE TARJETAHABIENTES"
    )


def test_categoria_label_quita_asterisco_de_nota_al_pie():
    assert _categoria_label("Depósitos a Plazo*") == "DEPÓSITOS A PLAZO"


def test_resolver_plazo_rango_y_sin_tope():
    assert _resolver_plazo("Plazo 30-60") == (30, 60)
    assert _resolver_plazo("Plazo 361 y más") == (361, None)


def test_resolver_plazo_no_reconocido_lanza_error():
    with pytest.raises(ValueError):
        _resolver_plazo("Plazo inventado")


def test_resolver_plazo_todos_los_6_buckets_reales_resuelven():
    assert _resolver_plazo("Plazo 30-60") == (30, 60)
    assert _resolver_plazo("Plazo 61-90") == (61, 90)
    assert _resolver_plazo("Plazo 91-120") == (91, 120)
    assert _resolver_plazo("Plazo 121-180") == (121, 180)
    assert _resolver_plazo("Plazo 181-360") == (181, 360)
    assert _resolver_plazo("Plazo 361 y más") == (361, None)


def test_resolver_plazo_shape_valido_pero_fuera_del_universo_no_lanza():
    """Desde sql/27_dim_plazo_estado_validacion.sql: un texto que matchea el shape de
    _PLAZO_RANGO ('PLAZO X-Y') pero no es uno de los 6 buckets reales verificados en
    producción YA NO aborta la carga -- se acepta y resuelve el rango real, quedando
    marcado AUTO_INGRESADO cuando llega a marts.dim_plazo."""
    assert _resolver_plazo("Plazo 700-900") == (700, 900)


def test_resolver_plazo_shape_invalido_sigue_lanzando():
    """Un texto que no matchea ni _PLAZO_RANGO ni _PLAZO_SIN_TOPE sigue siendo fallo
    duro -- no cambió con sql/27."""
    with pytest.raises(PlazoNoResueltoError):
        _resolver_plazo("Plazo inventado sin numeros")


def test_resolver_plazo_shape_valido_pero_rango_invertido_lanza_error():
    """Un shape válido con rango invertido (dias_desde > dias_hasta) es una anomalía real
    de parsing, no un bucket nuevo legítimo -- sigue abortando la carga."""
    with pytest.raises(PlazoNoResueltoError):
        _resolver_plazo("Plazo 900-700")


def test_parse_filas_rastrea_seccion_sin_asumir_que_tabla_0_es_activa_maxima():
    """Regresión del bug real encontrado esta sesión: para un subconjunto de meses, la
    sección 'activa_maxima' y el resto NO caen en tablas físicas separadas -- el parser
    debe rastrear la sección vigente fila por fila, sin importar en qué <table> esté."""
    fila_encabezado_maxima = ["1. TASAS DE INTERÉS ACTIVAS MÁXIMAS"] * 4
    fila_dato_maxima = ["Consumo", "Consumo", "Consumo", "16,77"]
    fila_encabezado_sistema = ["OTRAS TASAS REFERENCIALES"] * 4
    fila_dato_sistema = ["Tasa Legal", "6,85", None, None]

    tabla_unica = pd.DataFrame(
        [
            fila_encabezado_maxima,
            fila_dato_maxima,
            fila_encabezado_sistema,
            fila_dato_sistema,
        ]
    )
    filas = _parse_filas([tabla_unica])

    secciones = {f["seccion"] for f in filas}
    assert secciones == {"activa_maxima", "sistema"}
    maxima = next(f for f in filas if f["seccion"] == "activa_maxima")
    assert maxima["dimension_valor"] == "CONSUMO"
    assert maxima["valor"] == 16.77


def test_emitir_ignora_seccion_desconocida():
    assert _emitir("seccion_inventada", "X", 1.0) is None


# --- Histórico 2009-07 a 2022-07 (2026-10-09) ---


def test_activas_vigentes_par_izquierdo_referencial_derecho_maxima():
    """Hasta 2022-07 una sola sección 'VIGENTES' trae Referenciales y Máximas lado a lado;
    los valores con punto decimal ('7.23') se leen bien."""
    tabla = pd.DataFrame(
        [
            ["1. TASAS DE INTERÉS ACTIVAS EFECTIVAS VIGENTES"] * 4,
            [
                "Tasas Referenciales",
                "Tasas Referenciales",
                "Tasas Máximas",
                "Tasas Máximas",
            ],
            ["Consumo", "15.98", "Consumo", "16.77"],
        ]
    )
    filas = _parse_filas([tabla])
    por_seccion = {f["seccion"]: f["valor"] for f in filas}
    assert por_seccion == {"activa_referencial": 15.98, "activa_maxima": 16.77}


def test_seccion_de_inversiones_del_sector_publico_se_ignora():
    """Su cabecera trae la última celda vacía; antes no se detectaba y sus plazos se
    mezclaban con los de 'pasiva_plazo'."""
    tabla = pd.DataFrame(
        [
            ["3. TASAS DE INTERÉS PASIVAS EFECTIVAS REFERENCIALES POR PLAZO"] * 4,
            ["Plazo 30-60", "4.00", "Plazo 121-180", "5.00"],
            ["4. TASAS DE INTERÉS PASIVAS EFECTIVAS MÁXIMAS PARA LAS INVERSIONES"] * 3
            + [None],
            ["Plazo 30-60", "9.99", "Plazo 121-180", "9.99"],
        ]
    )
    valores = sorted(f["valor"] for f in _parse_filas([tabla]))
    assert valores == [4.0, 5.0]


def test_nota_dentro_de_la_seccion_de_plazos_no_rompe_el_archivo():
    tabla = pd.DataFrame(
        [
            ["3. TASAS DE INTERÉS PASIVAS EFECTIVAS REFERENCIALES POR PLAZO"] * 4,
            ["De las instituciones financieras", "1.00", None, None],
            ["Plazo 30-60", "4.00", None, None],
        ]
    )
    assert [f["valor"] for f in _parse_filas([tabla])] == [4.0]


@pytest.mark.parametrize(
    "crudo,esperado",
    [
        ("Consumo *", "CONSUMO"),
        ("Consumo /1", "CONSUMO"),
        ("Microcrédito Minorista 1*.", "MICROCRÉDITO MINORISTA"),
        (
            "Productivo Empresarial (* Este segmento entra en vigencia a partir del 18/06/2009 *)",
            "PRODUCTIVO EMPRESARIAL",
        ),
        ("Microcrédito Acumulación Ampliada", "MICROCRÉDITO DE ACUMULACIÓN AMPLIADA"),
    ],
)
def test_segmento_label_historico(crudo, esperado):
    assert _segmento_label(crudo) == esperado


def test_categoria_label_colapsa_espacios_dobles():
    assert _categoria_label("Depósitos  de Ahorro") == "DEPÓSITOS DE AHORRO"


def test_normalizar_ancho_quita_columna_vacia_o_duplicada():
    vacia = pd.DataFrame([["a", "1", "b", "2", None], ["c", "3", "d", "4", None]])
    assert _normalizar_ancho(vacia).shape[1] == 4
    duplicada = pd.DataFrame([["a", "1", "b", "2", "2"], ["c", "3", "d", "4", "4"]])
    assert _normalizar_ancho(duplicada).shape[1] == 4
    normal = pd.DataFrame([["x"] * 4, ["a", "1", "b", "2"]])
    assert _normalizar_ancho(normal).shape[1] == 4
