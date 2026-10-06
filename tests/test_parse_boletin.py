from benchmark_bancos.transform.parse_boletin import (
    _SECCION_POR_DIGITO,
    BOLETIN_AGGREGATE_COLUMNS,
    _codigo_padre,
    _normalize_col,
)


def test_aggregate_columns_normalizadas_cubren_variantes_2021_y_2026():
    # 2026 usa tilde/wording distinto a 2021 para las mismas 9 columnas de agregado --
    # ambas eras deben normalizar al mismo conjunto (bug real encontrado esta sesión).
    assert _normalize_col("BANCA MÚLTIPLE") in BOLETIN_AGGREGATE_COLUMNS
    assert _normalize_col("BANCA MULTIPLE") in BOLETIN_AGGREGATE_COLUMNS
    assert _normalize_col("BANCOS PRIVADOS MICROCRÉDITO") in BOLETIN_AGGREGATE_COLUMNS
    assert (
        _normalize_col("BANCOS PRIVADOS DE MICROEMPRESA") in BOLETIN_AGGREGATE_COLUMNS
    )
    assert (
        _normalize_col("BANCOS PRIVADOS DE MICROCRÉDITO") in BOLETIN_AGGREGATE_COLUMNS
    )
    # espacios extra al final de la celda (visto en la plantilla 2021) no deben colar
    assert (
        _normalize_col("BANCOS PRIVADOS COMERCIALES     ") in BOLETIN_AGGREGATE_COLUMNS
    )


def test_nombre_de_banco_real_no_se_confunde_con_agregado():
    assert _normalize_col("BP GUAYAQUIL") not in BOLETIN_AGGREGATE_COLUMNS
    assert (
        _normalize_col("BP BANCO COMERCIAL DE MANABI") not in BOLETIN_AGGREGATE_COLUMNS
    )


def test_codigo_padre_sigue_la_jerarquia_del_catalogo_unico_de_cuentas():
    assert _codigo_padre("1") is None
    assert _codigo_padre("11") == "1"
    assert _codigo_padre("1101") == "11"
    assert _codigo_padre("110105") == "1101"


def test_seccion_se_deriva_del_primer_digito():
    assert _SECCION_POR_DIGITO["1"] == "ACTIVO"
    assert _SECCION_POR_DIGITO["2"] == "PASIVO"
    assert _SECCION_POR_DIGITO["3"] == "PATRIMONIO"
    assert _SECCION_POR_DIGITO["4"] == "GASTOS"
    assert _SECCION_POR_DIGITO["5"] == "INGRESOS"
