import pytest

from benchmark_bancos.transform.canton_matching import (
    CantonNoResueltoError,
    aplicar_alias_canton,
    es_canton_conocido,
    normalize_canton,
    resolver_canton_bce,
)


def test_par_ya_sembrado_resuelve_tal_cual():
    assert resolver_canton_bce("QUITO", "PICHINCHA") == ("QUITO", "PICHINCHA")
    assert resolver_canton_bce("GUAYAQUIL", "GUAYAS") == ("GUAYAQUIL", "GUAYAS")


def test_acentos_se_normalizan_igual_que_normalize_provincia():
    # BCE trae tilde (convención propia), dim_canton usa la ortografía de CAPCOL
    # (sin tilde salvo la Ñ) -- mismo criterio que normalize_provincia().
    assert resolver_canton_bce("BOLÍVAR", "CARCHI") == ("BOLIVAR", "CARCHI")
    assert resolver_canton_bce("OLMEDO", "MANABÍ") == ("OLMEDO", "MANABI")
    assert normalize_canton("LOGROÑO") == "LOGROÑO"  # Ñ se conserva, no es tilde


def test_placeholder_nacional_resuelve():
    assert resolver_canton_bce("NACIONAL", "S/N") == ("NACIONAL", "S/N")


def test_zona_no_delimitada_resuelve_como_provincia_especial():
    assert resolver_canton_bce("LAS GOLONDRINAS", "ZONA NO DELIMITADA") == (
        "LAS GOLONDRINAS",
        "ZONA NO DELIMITADA",
    )


class TestAliasesBce:
    """5 pares donde BCE escribe el MISMO cantón físico con una forma de texto distinta
    a la ya sembrada desde CAPCOL -- ver sql/28_bce_canton_grain.sql para el detalle
    completo de cómo se identificaron (no son cantones nuevos)."""

    def test_distrito_metropolitano_de_quito_resuelve_a_quito(self):
        assert resolver_canton_bce("DISTRITO METROPOLITANO DE QUITO", "PICHINCHA") == (
            "QUITO",
            "PICHINCHA",
        )

    def test_el_empalme_resuelve_a_empalme(self):
        assert resolver_canton_bce("EL EMPALME", "GUAYAS") == ("EMPALME", "GUAYAS")

    def test_general_antonio_elizalde_resuelve_con_apodo_bucay(self):
        assert resolver_canton_bce("GENERAL ANTONIO ELIZALDE", "GUAYAS") == (
            "GENERAL ANTONIO ELIZALDE (BUCAY)",
            "GUAYAS",
        )

    def test_puebloviejo_una_palabra_resuelve_a_pueblo_viejo(self):
        assert resolver_canton_bce("PUEBLOVIEJO", "LOS RIOS") == (
            "PUEBLO VIEJO",
            "LOS RIOS",
        )

    def test_san_francisco_de_orellana_resuelve_a_orellana(self):
        assert resolver_canton_bce("SAN FRANCISCO DE ORELLANA", "ORELLANA") == (
            "ORELLANA",
            "ORELLANA",
        )

    def test_puerto_quito_no_es_alias_de_quito(self):
        """Cantón real y distinto de Pichincha -- no debe confundirse con el alias de
        'DISTRITO METROPOLITANO DE QUITO' de arriba."""
        assert resolver_canton_bce("PUERTO QUITO", "PICHINCHA") == (
            "PUERTO QUITO",
            "PICHINCHA",
        )


class TestAliasesTodasLasFuentes:
    """Alias agregados 2026-10-09 (sql/35): crearon cantones duplicados AUTO_INGRESADO.
    Verificados contra el INEC: un solo cantón con ese nombre en la provincia."""

    def test_alfredo_baquerizo_moreno_seps_resuelve_con_apodo_jujan(self):
        assert resolver_canton_bce("ALFREDO BAQUERIZO MORENO", "GUAYAS") == (
            "ALFREDO BAQUERIZO MORENO (JUJAN)",
            "GUAYAS",
        )

    def test_pablo_vi_resuelve_a_pablo_sexto(self):
        assert resolver_canton_bce("PABLO VI", "MORONA SANTIAGO") == (
            "PABLO SEXTO",
            "MORONA SANTIAGO",
        )

    def test_capcol_usa_el_mismo_alias(self):
        # CAPCOL (parse_cartera/parse_depositos) no pasa por resolver_canton_bce.
        assert aplicar_alias_canton("PABLO VI", "MORONA SANTIAGO") == "PABLO SEXTO"
        assert aplicar_alias_canton("QUITO", "PICHINCHA") == "QUITO"
        assert aplicar_alias_canton(None, "PICHINCHA") is None

    def test_alias_depende_de_la_provincia(self):
        # El alias es por par: el mismo texto en otra provincia no se toca.
        assert aplicar_alias_canton("PABLO VI", "GUAYAS") == "PABLO VI"


class TestCantonesHomonimosEnDosProvincias:
    """Cantones reales con el mismo nombre en dos provincias distintas (reclasificación
    administrativa histórica de Ecuador) -- deben resolver a pares DISTINTOS, nunca
    colapsar a uno solo, y resolver_canton_bce() nunca debe ignorar la provincia."""

    def test_la_concordia_esmeraldas_y_santo_domingo_son_pares_distintos(self):
        assert resolver_canton_bce("LA CONCORDIA", "ESMERALDAS") == (
            "LA CONCORDIA",
            "ESMERALDAS",
        )
        assert resolver_canton_bce(
            "LA CONCORDIA", "SANTO DOMINGO DE LOS TSACHILAS"
        ) == ("LA CONCORDIA", "SANTO DOMINGO DE LOS TSACHILAS")

    def test_santo_domingo_pichincha_y_tsachilas_son_pares_distintos(self):
        assert resolver_canton_bce("SANTO DOMINGO", "PICHINCHA") == (
            "SANTO DOMINGO",
            "PICHINCHA",
        )
        assert resolver_canton_bce(
            "SANTO DOMINGO", "SANTO DOMINGO DE LOS TSACHILAS"
        ) == ("SANTO DOMINGO", "SANTO DOMINGO DE LOS TSACHILAS")

    def test_bolivar_carchi_y_manabi_son_pares_distintos(self):
        assert resolver_canton_bce("BOLIVAR", "CARCHI") == ("BOLIVAR", "CARCHI")
        assert resolver_canton_bce("BOLIVAR", "MANABI") == ("BOLIVAR", "MANABI")


def test_canton_fuera_del_universo_sembrado_no_lanza_two_tier():
    """Nivel 2 del two-tier: provincia válida pero par no sembrado -- se acepta igual,
    marts.dim_canton lo auto-ingresará AUTO_INGRESADO (no verificable acá sin DB, ver
    tests/test_integration_regressions.py para el camino con Postgres)."""
    canton, provincia = resolver_canton_bce("UN CANTON QUE NO EXISTE", "GUAYAS")
    assert canton == "UN CANTON QUE NO EXISTE"
    assert provincia == "GUAYAS"
    assert es_canton_conocido(canton, provincia) is False


def test_canton_conocido_devuelve_true_para_par_sembrado():
    assert es_canton_conocido("QUITO", "PICHINCHA") is True


def test_provincia_no_resuelve_lanza_fail_fast():
    """Nivel 1 del two-tier: SIEMPRE fail-fast, nunca se auto-ingresa una provincia
    desconocida."""
    with pytest.raises(CantonNoResueltoError):
        resolver_canton_bce("ALGUN CANTON", "PROVINCIA QUE NO EXISTE")


def test_provincia_vacia_lanza_error():
    with pytest.raises(CantonNoResueltoError):
        resolver_canton_bce("ALGUN CANTON", "")


def test_canton_vacio_lanza_error():
    with pytest.raises(CantonNoResueltoError):
        resolver_canton_bce("", "GUAYAS")


def test_canton_none_lanza_error():
    with pytest.raises(CantonNoResueltoError):
        resolver_canton_bce(None, "GUAYAS")
