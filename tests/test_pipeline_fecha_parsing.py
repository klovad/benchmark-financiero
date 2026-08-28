"""Tests puros (sin DB ni red) para las funciones de fecha-desde-nombre-de-archivo
factorizadas fuera de load_tasas_historicas()/load_boletin() -- ver
docs/propuesta_escalabilidad_etl.md sección 2.3."""

import datetime

import pytest

from etl.pipeline import (
    parse_fecha_from_boletin_filename,
    parse_fecha_from_tasas_historicas_filename,
)


def test_parse_fecha_tasas_historicas_valid_filename():
    fecha = parse_fecha_from_tasas_historicas_filename("TasasVigentes062024.htm")
    assert fecha == datetime.date(2024, 6, 30)


def test_parse_fecha_tasas_historicas_no_matching_pattern_raises():
    with pytest.raises(ValueError):
        parse_fecha_from_tasas_historicas_filename("archivo_random.htm")


def test_parse_fecha_boletin_valid_filename():
    fecha = parse_fecha_from_boletin_filename("Boletín Bancos Enero 2023.zip")
    assert fecha == datetime.date(2023, 1, 31)


def test_parse_fecha_boletin_unrecognized_month_raises():
    with pytest.raises(ValueError):
        parse_fecha_from_boletin_filename("Boletín Bancos Xxxxx 2023.zip")


def test_parse_fecha_boletin_no_matching_pattern_raises():
    with pytest.raises(ValueError):
        parse_fecha_from_boletin_filename("archivo_random.zip")
