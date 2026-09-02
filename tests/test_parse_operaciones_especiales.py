"""Tests del parser de operaciones_especiales.xlsx -- puros, sin DB ni red.

El xlsx (descarga manual a data/raw, ver docs/fuentes_datos.md) tiene la estructura de
BCE tsa pero marcado es_operacion_especial='SI'. El test usa un mini-xlsx en memoria con
los rasgos de la fuente real: ruc como entero (pierde el cero inicial), canton con
espacios al final, plazos de tsa en años y días.
"""

from pathlib import Path

import pandas as pd
import pytest

from etl.transform.parse_operaciones_especiales import (
    COLUMNAS_EXPECTADAS,
    parse_operaciones_especiales_file,
)
from etl.transform.parse_bce_tasas import SegmentoNoResueltoError


def _mini_xlsx(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        {
            "semana": pd.to_datetime(["2025-01-30", "2025-02-06", "2025-02-06"]),
            "ruc": [990049459001, 990049459001, 990049459001],  # entero, pierde el cero
            "razon_social": ["BANCO DE GUAYAQUIL S.A."] * 3,
            "sector_financiero": ["SECTOR FINANCIERO PRIVADO"] * 3,
            "tipo_entidad": ["BANCOS PRIVADOS"] * 3,
            "tipo_segmento": ["BANCO GRANDE"] * 3,
            "provincia": ["GUAYAS", "GUAYAS", "PICHINCHA"],
            "canton": ["GUAYAQUIL", "GUAYAQUIL ", "DISTRITO METROPOLITANO DE QUITO"],
            "segmento_credito": [
                "PRODUCTIVO PYMES",
                "PRODUCTIVO - CORPORATIVO",
                "PRODUCTIVO - CORPORATIVO",
            ],
            "plazo": ["i. 2 - 4 AÑOS", "c. 61 - 120 DIAS", "d. 121 - 180 DIAS"],
            "monto_total": [943802.72, 10000000.00, 10000000.00],
            "numero_operaciones": [24, 2, 1],
            "tasa_activa_efectiva": [7.760, 6.685, 6.610],
            "tasa_nominal": [7.500, 6.525, 6.500],
        }
    )
    path = tmp_path / "operaciones_especiales.xlsx"
    df.to_excel(path, index=False)
    return path


def test_parse_operaciones_especiales_resuelve_y_marca_si(tmp_path):
    df = parse_operaciones_especiales_file(_mini_xlsx(tmp_path))

    assert set(df["es_operacion_especial"].unique()) == {"SI"}
    assert set(df["source_file"].unique()) == {"operaciones_especiales.xlsx"}
    assert set(df["banco_codigo"].unique()) == {"GUAYAQUIL"}

    # ruc zfill a 13 dígitos en la identidad (el 990... real es 0990049459001); banco
    # privado resuelve por crosswalk así que el ruc solo es atributo, pero el zfill
    # protege dim_banco.ruc de quedar con 12 dígitos.
    assert df["monto_total"].sum() == 20943802.72

    # Grano (fecha, banco, segmento, plazo, provincia): 2 filas Guayaquil mismo plazo pero
    # distintas provincias se mantienen separadas; Pymes + corporativo son 3 filas.
    assert len(df) == 3


def test_parse_operaciones_especiales_agrega_por_provincia(tmp_path):
    df = parse_operaciones_especiales_file(_mini_xlsx(tmp_path))
    provincias = set(df["provincia"].unique())
    assert provincias == {"GUAYAS", "PICHINCHA"}


def test_parse_operaciones_especiales_falta_columna_aborta(tmp_path):
    df = pd.read_excel(_mini_xlsx(tmp_path))
    df = df.drop(columns=["tasa_nominal"])
    path = tmp_path / "roto.xlsx"
    df.to_excel(path, index=False)
    with pytest.raises(ValueError) as e:
        parse_operaciones_especiales_file(path)
    assert "tasa_nominal" in str(e.value)


def test_parse_operaciones_especiales_segmento_invalido_aborta(tmp_path):
    df = pd.read_excel(_mini_xlsx(tmp_path))
    df.loc[0, "segmento_credito"] = "SEGMENTO INVENTADO"
    path = tmp_path / "seg.roto.xlsx"
    df.to_excel(path, index=False)
    with pytest.raises(SegmentoNoResueltoError):
        parse_operaciones_especiales_file(path)


def test_columnas_esperadas_son_las_de_bce_tsa_mas_ruc_tipo_segmento():
    # La fuente del xlsx documenta ser idéntica a tsa; el set protege de que un cambio
    # en el archivo agregue/quita columnas sin que nadie actualice el contrato.
    assert COLUMNAS_EXPECTADAS == {
        "semana",
        "ruc",
        "razon_social",
        "sector_financiero",
        "tipo_entidad",
        "tipo_segmento",
        "provincia",
        "canton",
        "segmento_credito",
        "plazo",
        "monto_total",
        "numero_operaciones",
        "tasa_activa_efectiva",
        "tasa_nominal",
    }