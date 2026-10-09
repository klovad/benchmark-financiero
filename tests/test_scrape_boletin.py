"""Filtro de archivos del portal del Boletín (2026-10-09): el boletín de septiembre de
2026 venía con "BOLETI" + tilde combinante y se saltaba en silencio."""

import unicodedata

import pytest

from benchmark_bancos.extract.scrape_boletin import es_boletin


@pytest.mark.parametrize(
    "nombre",
    [
        "5. BOLETIN BANCOS MAYO 2026",
        "6. BOLETÍN BANCOS JUNIO 2026",  # Í precompuesta
        unicodedata.normalize("NFD", "9. BOLETÍN BANCOS SEPTIEMBRE 2026"),
        "boletín bancos enero 2021.zip",
    ],
)
def test_reconoce_boletin_con_o_sin_tilde(nombre):
    assert es_boletin(nombre)


def test_descarta_otros_archivos():
    assert not es_boletin("Ficha metodologica.pdf")
