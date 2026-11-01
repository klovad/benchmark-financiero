"""Universos curados que confirman estado_validacion de dim_plazo y dim_cuenta_contable
(sql/45). No necesitan base."""

import csv
import re

from benchmark_bancos.config import PROJECT_ROOT, SEEDS_DIR
from benchmark_bancos.load.load_postgres import plazos_curados


def test_plazos_curados_son_los_21_rangos_de_sql_45():
    """sql/45 confirma una lista fija de rangos; si un universo de plazo cambia, la
    lista de la migración deja de coincidir y conviene saberlo (la migración no se
    edita: el refresh ya confirma lo nuevo)."""
    sql = (PROJECT_ROOT / "sql" / "45_estado_validacion_curado.sql").read_text("utf-8")
    en_sql = {
        (int(a), None if b == "NULL" else int(b))
        for a, b in re.findall(r"\((\d+), (\d+|NULL)\)", sql)
    }
    assert len(en_sql) == 21
    assert plazos_curados() == en_sql


def test_seed_cuentas_sin_duplicados_ni_vacios():
    with open(SEEDS_DIR / "cuenta_contable.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    llaves = [(r["reporte"], r["codigo"]) for r in filas]
    assert len(llaves) == len(set(llaves))
    assert {r["reporte"] for r in filas} == {"BALANCE", "PYG"}
    assert all(r["codigo"] and r["cuenta"] for r in filas)
