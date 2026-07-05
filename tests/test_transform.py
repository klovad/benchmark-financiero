from pathlib import Path

import pytest

from etl.transform.parse_cartera import parse_cartera_file, tipo_credito_from_sheet_name
from etl.transform.parse_depositos import parse_depositos_file

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
EXTRACT_DIR = Path(__file__).resolve().parent.parent / "data" / "_tmp_extract"

CARTERA_COLUMNS = {
    "fecha", "tipo_entidad", "banco", "region", "provincia", "canton",
    "tipo_credito", "estado_cartera", "saldo", "source_file", "source_hash",
}
DEPOSITOS_COLUMNS = {
    "fecha", "tipo_entidad", "banco", "region", "provincia", "canton",
    "tipo_deposito", "saldo", "numero_cuentas", "numero_clientes",
    "source_file", "source_hash",
}


def _first_file(subdir: str) -> Path:
    matches = sorted((RAW_DIR / "2021" / subdir).glob("*.zip"))
    if not matches:
        pytest.skip(f"No hay archivos de muestra en data/raw/2021/{subdir} (correr el scraper primero)")
    return matches[0]


def test_tipo_credito_from_sheet_name_handles_accents():
    assert tipo_credito_from_sheet_name("BASE B PRIVADA EDUCATIVO") == "educativo"
    assert tipo_credito_from_sheet_name("BASE B PRIVADA VIVIENDA INTERES") == "vivienda_interes_publico"
    assert tipo_credito_from_sheet_name("BASE B PRIVADA INMOBILIARIO") == "inmobiliario"


def test_parse_cartera_file_schema_and_no_duplicates():
    df = parse_cartera_file(_first_file("cartera"), EXTRACT_DIR)
    assert set(df.columns) == CARTERA_COLUMNS
    assert len(df) > 0
    key_cols = ["fecha", "tipo_entidad", "banco", "canton", "tipo_credito", "estado_cartera"]
    assert not df.duplicated(subset=key_cols).any()
    assert df["saldo"].notna().all()


def test_parse_depositos_file_schema_and_no_duplicates():
    df = parse_depositos_file(_first_file("depositos"), EXTRACT_DIR)
    assert set(df.columns) == DEPOSITOS_COLUMNS
    assert len(df) > 0
    key_cols = ["fecha", "tipo_entidad", "banco", "canton", "tipo_deposito"]
    assert not df.duplicated(subset=key_cols).any()
    assert df["saldo"].notna().all()
