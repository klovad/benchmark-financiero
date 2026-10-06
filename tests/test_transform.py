from pathlib import Path

import pytest

from benchmark_bancos.transform.parse_cartera import (
    parse_cartera_file,
    tipo_credito_from_sheet_name,
)
from benchmark_bancos.transform.parse_depositos import parse_depositos_file

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
EXTRACT_DIR = Path(__file__).resolve().parent.parent / "data" / "_tmp_extract"

CARTERA_COLUMNS = {
    "fecha",
    "tipo_entidad",
    "banco",
    "banco_codigo",
    "region",
    "provincia",
    "canton",
    "tipo_credito",
    "estado_cartera",
    "saldo",
    "source_file",
    "source_hash",
}
DEPOSITOS_COLUMNS = {
    "fecha",
    "tipo_entidad",
    "banco",
    "banco_codigo",
    "region",
    "provincia",
    "canton",
    "tipo_deposito",
    "categoria_deposito",
    "plazo_dias_desde",
    "plazo_dias_hasta",
    "saldo",
    "numero_cuentas",
    "numero_clientes",
    "source_file",
    "source_hash",
}


def _first_file(subdir: str) -> Path:
    matches = sorted((RAW_DIR / "2021" / subdir).glob("*.zip"))
    if not matches:
        pytest.skip(
            f"No hay archivos de muestra en data/raw/2021/{subdir} (correr el scraper primero)"
        )
    return matches[0]


def test_tipo_credito_from_sheet_name_handles_accents():
    assert tipo_credito_from_sheet_name("BASE B PRIVADA EDUCATIVO") == "educativo"
    assert (
        tipo_credito_from_sheet_name("BASE B PRIVADA VIVIENDA INTERES")
        == "vivienda_interes_publico"
    )
    assert tipo_credito_from_sheet_name("BASE B PRIVADA INMOBILIARIO") == "inmobiliario"


def test_parse_cartera_file_schema_and_no_duplicates():
    df = parse_cartera_file(_first_file("cartera"), EXTRACT_DIR)
    assert set(df.columns) == CARTERA_COLUMNS
    assert len(df) > 0
    key_cols = [
        "fecha",
        "tipo_entidad",
        "banco",
        "canton",
        "tipo_credito",
        "estado_cartera",
    ]
    assert not df.duplicated(subset=key_cols).any()
    assert df["saldo"].notna().all()


def test_parse_depositos_file_schema_and_no_duplicates():
    df = parse_depositos_file(_first_file("depositos"), EXTRACT_DIR)
    assert set(df.columns) == DEPOSITOS_COLUMNS
    assert len(df) > 0
    key_cols = ["fecha", "tipo_entidad", "banco", "canton", "tipo_deposito"]
    assert not df.duplicated(subset=key_cols).any()
    assert df["saldo"].notna().all()


def test_tipo_credito_inversion_publica_banca_publica():
    # Hoja real de capcol-instituciones-publicas (docs/fuentes_datos.md sección 1.1).
    assert (
        tipo_credito_from_sheet_name("BASE B PUBLICA INVERSION PUBLICA")
        == "inversion_publica"
    )
    assert (
        tipo_credito_from_sheet_name("BASE B PUBLICA INVERSION PUBLIC")
        == "inversion_publica"
    )


def test_parsers_propagan_tipo_entidad_del_portal():
    # El parser no debe hardcodear 'BANCO PRIVADO': lo fija el sub-portal de origen.
    df = parse_cartera_file(_first_file("cartera"), EXTRACT_DIR, "BANCO PUBLICO")
    assert set(df["tipo_entidad"]) == {"BANCO PUBLICO"}
    df = parse_depositos_file(_first_file("depositos"), EXTRACT_DIR, "BANCO PUBLICO")
    assert set(df["tipo_entidad"]) == {"BANCO PUBLICO"}


def test_parsers_rechazan_tipo_entidad_fuera_de_capcol():
    import pytest

    with pytest.raises(ValueError, match="tipo_entidad inválido"):
        parse_cartera_file(_first_file("cartera"), EXTRACT_DIR, "COOPERATIVA")
    with pytest.raises(ValueError, match="tipo_entidad inválido"):
        parse_depositos_file(_first_file("depositos"), EXTRACT_DIR, "COOPERATIVA")
