"""Cobertura de las funciones puras de src/benchmark_bancos/transform/parse_bce_tasas.py relacionadas con
el cambio de grano de cantón (sql/28_bce_canton_grain.sql, 2026-09-01) -- sin archivo ni
DB, mismo criterio que el resto de tests/test_*_matching.py.

parse_tsp_file()/parse_tsa_file() de punta a punta (con archivo real) ya se ejercitaron
manualmente contra data/raw/bce/tsp_desde_200801.zip y tsa_desde_200801.zip (7.76M/3.08M
filas, ver docstring del módulo para el hallazgo de duplicados reales) -- no se agrega acá
un test de archivo completo porque sha256_file() dentro de esas funciones requiere que el
zip exista en disco (no versionado, ~70-130MB), y sería redundante con la cobertura de
_weighted_agg/_resolve_canton en aislamiento."""

import pandas as pd
import pytest

from benchmark_bancos.transform.canton_matching import CantonNoResueltoError
from benchmark_bancos.transform.parse_bce_tasas import _resolve_canton, _weighted_agg


def _row(canton: str, provincia: str, monto_total: float, **overrides) -> dict:
    row = {
        "fecha": "2026-01-01",
        "banco_codigo": "B1",
        "categoria_deposito": "DEPÓSITOS DE AHORRO",
        "plazo_dias_desde": 0,
        "plazo_dias_hasta": 30,
        "plazo_codigo": "A",
        "provincia": provincia,
        "canton": canton,
        "monto_total": monto_total,
        "numero_operaciones": 1,
        "tasa_pasiva_efectiva": 2.0,
        "tasa_nominal": 1.8,
    }
    row.update(overrides)
    return row


_GROUP_COLS = [
    "fecha",
    "banco_codigo",
    "categoria_deposito",
    "plazo_dias_desde",
    "plazo_dias_hasta",
    "plazo_codigo",
    "provincia",
    "canton",
]


def test_weighted_agg_colapsa_duplicados_del_mismo_canton_pero_no_entre_cantones():
    """Con `canton` en group_cols (desde sql/28), dos filas del MISMO cantón para la
    misma llave deben seguir colapsando (SUM + promedio ponderado) -- pero una tercera
    fila de un cantón DISTINTO en la misma provincia/llave NO debe colapsar con las
    otras dos (antes de sql/28, sí colapsaba, porque canton no estaba en group_cols)."""
    df = pd.DataFrame(
        [
            _row(
                "GUAYAQUIL",
                "GUAYAS",
                100.0,
                numero_operaciones=2,
                tasa_pasiva_efectiva=2.0,
                tasa_nominal=1.8,
            ),
            _row(
                "GUAYAQUIL",
                "GUAYAS",
                300.0,
                numero_operaciones=3,
                tasa_pasiva_efectiva=4.0,
                tasa_nominal=3.0,
            ),
            _row(
                "DAULE",
                "GUAYAS",
                50.0,
                numero_operaciones=1,
                tasa_pasiva_efectiva=10.0,
                tasa_nominal=9.0,
            ),
        ]
    )

    result = _weighted_agg(df, _GROUP_COLS, ["tasa_pasiva_efectiva", "tasa_nominal"])

    assert len(result) == 2  # GUAYAQUIL: 2 filas -> 1; DAULE: se mantiene aparte

    guayaquil = result[result["canton"] == "GUAYAQUIL"].iloc[0]
    assert guayaquil["monto_total"] == pytest.approx(400.0)
    assert guayaquil["numero_operaciones"] == 5
    assert guayaquil["tasa_pasiva_efectiva"] == pytest.approx(
        (100 * 2.0 + 300 * 4.0) / 400
    )
    assert guayaquil["tasa_nominal"] == pytest.approx((100 * 1.8 + 300 * 3.0) / 400)

    daule = result[result["canton"] == "DAULE"].iloc[0]
    assert daule["monto_total"] == pytest.approx(50.0)
    assert daule["numero_operaciones"] == 1


def test_weighted_agg_pondera_por_monto_no_promedio_simple():
    """El promedio de tasas debe ser ponderado por monto_total, no un promedio simple
    entre filas -- una fila con monto muy superior debe dominar el resultado."""
    df = pd.DataFrame(
        [
            _row("QUITO", "PICHINCHA", 1.0, tasa_pasiva_efectiva=100.0),
            _row("QUITO", "PICHINCHA", 999.0, tasa_pasiva_efectiva=1.0),
        ]
    )
    result = _weighted_agg(df, _GROUP_COLS, ["tasa_pasiva_efectiva"])
    assert len(result) == 1
    tasa = result.iloc[0]["tasa_pasiva_efectiva"]
    assert tasa == pytest.approx((1.0 * 100.0 + 999.0 * 1.0) / 1000.0)
    assert tasa < 2.0  # dominado por la fila de monto grande, no ~50 (promedio simple)


def test_resolve_canton_normaliza_y_propaga_a_todas_las_filas_del_par():
    """_resolve_canton() resuelve solo las combinaciones DISTINTAS de (canton, provincia)
    -- verifica que el resultado se propague correctamente a TODAS las filas que
    comparten el par, incluidos los 5 alias de sql/28_bce_canton_grain.sql."""
    df = pd.DataFrame(
        [
            _row("DISTRITO METROPOLITANO DE QUITO", "PICHINCHA", 1.0),
            _row("DISTRITO METROPOLITANO DE QUITO", "PICHINCHA", 2.0),
            _row("BOLÍVAR", "CARCHI", 3.0),
        ]
    )
    result = _resolve_canton(df)
    assert result["canton"].tolist() == ["QUITO", "QUITO", "BOLIVAR"]
    assert result["provincia"].tolist() == ["PICHINCHA", "PICHINCHA", "CARCHI"]
    # monto_total no se toca -- solo canton/provincia se resuelven acá.
    assert result["monto_total"].tolist() == [1.0, 2.0, 3.0]


def test_resolve_canton_propaga_cantonnoresueltoerror():
    """Nivel 1 del two-tier (canton_matching.py): provincia que no resuelve debe
    propagar CantonNoResueltoError sin capturar, igual que SegmentoNoResueltoError/
    TipoSegmentoNoResueltoError en este mismo módulo."""
    df = pd.DataFrame([_row("ALGUN CANTON", "PROVINCIA QUE NO EXISTE", 1.0)])
    with pytest.raises(CantonNoResueltoError):
        _resolve_canton(df)


def test_resolve_canton_no_lanza_para_canton_fuera_del_universo_sembrado():
    """Nivel 2 del two-tier: un cantón fuera de src/benchmark_bancos/seeds/canton_provincia.csv pero con
    provincia válida se acepta tal cual (se auto-ingresará en marts.dim_canton más
    adelante, en el JOIN de refresh_marts() -- ver
    tests/test_integration_regressions.py::test_bce_canton_auto_ingresado_end_to_end).
    """
    df = pd.DataFrame([_row("UN CANTON QUE NO EXISTE", "GUAYAS", 1.0)])
    result = _resolve_canton(df)
    assert result["canton"].iloc[0] == "UN CANTON QUE NO EXISTE"
    assert result["provincia"].iloc[0] == "GUAYAS"
