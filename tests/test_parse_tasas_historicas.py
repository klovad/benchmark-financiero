import pandas as pd
import pytest

from etl.transform.bce_plazo_matching import PlazoNoResueltoError
from etl.transform.parse_tasas_historicas import (
    _categoria_label,
    _emitir,
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


def test_resolver_plazo_shape_valido_pero_fuera_del_universo_lanza_plazo_error():
    """dim_plazo es compartido entre fuentes y no debe crecer silenciosamente: un texto
    que matchea el shape de _PLAZO_RANGO ('PLAZO X-Y') pero no es uno de los 6 buckets
    reales verificados en producción debe fallar fuerte."""
    with pytest.raises(PlazoNoResueltoError):
        _resolver_plazo("Plazo 999-1000")


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
