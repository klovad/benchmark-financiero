"""Motor de referencia del catálogo `IND_NN` (indicadores del Excel de Financiero).

Implementa en pandas las fórmulas documentadas y verificadas dígito a dígito contra el
Excel real en docs/indicadores_excel_bcos_coop.md — liquidez, morosidad (total y por
segmento), cobertura, ROA/ROE (con promedio YTD), eficiencia — para los bancos privados
del data mart, al corte más reciente disponible en data/samples/marts_ultimos_5_anios (o
el que se indique con --fecha-id).

Uso:
    python scripts/compute_indicadores_excel.py [--fecha-id 20260630]

Requiere pandas + pyarrow (ver requirements.txt). Lee `data/samples/marts_ultimos_5_anios/`
por defecto (2026-07-25: antes `marts_full/`, histórico completo -- reemplazado por la
ventana de 5 años para no versionar ~394MB; el corte más reciente sigue estando ahí) --
para correr contra Postgres real, reemplazar `rd_one`/`rd_years` por consultas a
`marts.*` (o, mejor, usar directamente las vistas de sql/18_glosario_cuentas_views.sql,
que implementan estos mismos bloques del lado de la base).
"""

import argparse
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "samples" / "marts_ultimos_5_anios"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

SEGMENTOS = ["PRODUCTIVO", "CONSUMO", "INMOBILIARIO", "MICROCR", "EDUCATIVO"]


def rd_one(name):
    return pd.read_parquet(DATA_DIR / f"{name}.parquet")


def rd_years(prefix, years):
    dfs = []
    for y in years:
        p = DATA_DIR / f"{prefix}_{y}.parquet"
        if p.exists():
            dfs.append(pd.read_parquet(p))
    return pd.concat(dfs, ignore_index=True)


def cod(df, codigo):
    col = "saldo_usd" if "saldo_usd" in df.columns else "valor_usd"
    v = df.loc[df.codigo == codigo, col]
    return v.sum() if len(v) else 0.0


def segmento_bruto(fb14, keyword):
    rows = fb14[fb14.cuenta.str.contains(keyword, case=False, na=False)]
    return rows.saldo_usd.sum()


def segmento_improductiva(fb14, keyword):
    rows = fb14[
        fb14.cuenta.str.contains(keyword, case=False, na=False)
        & (
            fb14.cuenta.str.contains("NO DEVENGA", case=False, na=False)
            | fb14.cuenta.str.contains("VENCIDA", case=False, na=False)
        )
        & ~fb14.cuenta.str.contains("POR VENCER", case=False, na=False)
    ]
    return rows.saldo_usd.sum()


def promedio_ytd(fact_balance, dim_fecha, codigo, banco_id, fecha_id):
    """Promedio de saldos fin de mes de `codigo` (1=activo, 3=patrimonio), desde
    diciembre del año anterior hasta fecha_id (inclusive) -- ver glosario_cuentas.md §5.
    """
    anio = fecha_id // 10000
    dic_anterior_id = int(f"{anio - 1}1231")
    fechas_ytd = dim_fecha[
        (dim_fecha.fecha_id >= dic_anterior_id)
        & (dim_fecha.fecha_id <= fecha_id)
        & (dim_fecha.dia == dim_fecha.groupby("anio_mes")["dia"].transform("max"))
    ]
    fechas_ids = fechas_ytd.fecha_id.tolist()
    rows = fact_balance[
        (fact_balance.banco_id == banco_id)
        & (fact_balance.fecha_id.isin(fechas_ids))
        & (fact_balance.codigo == codigo)
    ]
    return rows.saldo_usd.mean() if len(rows) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fecha-id",
        type=int,
        default=None,
        help="Corte AAAAMMDD a calcular (por defecto: el más reciente disponible en fact_balance)",
    )
    args = parser.parse_args()

    dim_banco = rd_one("dim_banco")
    dim_cuenta = rd_one("dim_cuenta_contable")
    dim_fecha = rd_one("dim_fecha")
    dim_fecha["fecha"] = pd.to_datetime(dim_fecha["fecha"])

    privados = dim_banco[dim_banco.tipo_entidad == "BANCO PRIVADO"][
        ["banco_id", "banco", "banco_codigo"]
    ].copy()

    anios = range(dim_fecha.anio.min(), dim_fecha.anio.max() + 1)
    fact_balance = rd_years("fact_balance", anios).merge(
        dim_cuenta[["cuenta_id", "codigo", "cuenta", "nivel"]], on="cuenta_id"
    )
    fact_pyg = rd_years("fact_pyg", anios).merge(
        dim_cuenta[["cuenta_id", "codigo", "cuenta", "nivel"]], on="cuenta_id"
    )

    fecha_id = args.fecha_id or int(fact_balance.fecha_id.max())

    rows_out = []
    skipped = []
    for _, b in privados.iterrows():
        bid, bname, bcod = b.banco_id, b.banco, b.banco_codigo
        fb = fact_balance[
            (fact_balance.fecha_id == fecha_id) & (fact_balance.banco_id == bid)
        ]
        fp = fact_pyg[(fact_pyg.fecha_id == fecha_id) & (fact_pyg.banco_id == bid)]
        if fb.empty:
            skipped.append((bname, "sin fact_balance en fecha"))
            continue

        total_activos = cod(fb, "1")
        total_pasivos = cod(fb, "2")
        patrimonio = cod(fb, "3")
        fondos_disp = cod(fb, "11")
        cartera_bruta = cod(fb, "14") - cod(fb, "1499")
        provision_cartera = -cod(fb, "1499")  # positivo

        fb14 = fb[
            fb.codigo.str.startswith("14") & (fb.nivel == 4) & (fb.codigo != "1499")
        ]
        cartera_improductiva = fb14[
            (
                fb14.cuenta.str.contains("NO DEVENGA", case=False, na=False)
                | fb14.cuenta.str.contains("VENCIDA", case=False, na=False)
            )
            & ~fb14.cuenta.str.contains("POR VENCER", case=False, na=False)
        ].saldo_usd.sum()

        dep_corto_plazo = cod(fb, "2101") + cod(fb, "210305") + cod(fb, "210310")
        indice_liquidez = fondos_disp / dep_corto_plazo if dep_corto_plazo else None

        morosidad_total = (
            cartera_improductiva / cartera_bruta if cartera_bruta else None
        )
        cobertura = (
            provision_cartera / cartera_improductiva if cartera_improductiva else None
        )

        mora_seg = {}
        for seg in SEGMENTOS:
            bruto = segmento_bruto(fb14, seg)
            improd = segmento_improductiva(fb14, seg)
            mora_seg[seg] = improd / bruto if bruto else None

        # fact_pyg no trae fila para codigo='4' (TOTAL GASTOS) a nivel 1 -- ver
        # glosario_cuentas.md §4.6. Workaround verificado: sumar las 8 cuentas nivel-2.
        ingresos = cod(fp, "5")
        gastos_top = cod(fp, "4")
        if gastos_top == 0:
            gastos_top = fp[
                fp.codigo.isin(["41", "42", "43", "44", "45", "46", "47", "48"])
            ].valor_usd.sum()
        utilidad_neta = ingresos - gastos_top
        gasto_operacion = cod(fp, "45")

        mes = fecha_id % 10000 // 100
        utilidad_anualizada = utilidad_neta * (12.0 / mes)

        act_prom = promedio_ytd(fact_balance, dim_fecha, "1", bid, fecha_id)
        pat_prom = promedio_ytd(fact_balance, dim_fecha, "3", bid, fecha_id)
        roa = utilidad_anualizada / act_prom if act_prom else None
        roe = utilidad_anualizada / pat_prom if pat_prom else None

        eficiencia = gasto_operacion / total_activos if total_activos else None

        rows_out.append(
            {
                "banco": bname,
                "banco_codigo": bcod,
                "total_activos": total_activos,
                "total_pasivos": total_pasivos,
                "patrimonio": patrimonio,
                "cartera_bruta": cartera_bruta,
                "cartera_improductiva": cartera_improductiva,
                "provision_cartera": provision_cartera,
                "indice_liquidez": indice_liquidez,
                "morosidad_total": morosidad_total,
                "cobertura": cobertura,
                "mora_productivo": mora_seg["PRODUCTIVO"],
                "mora_consumo": mora_seg["CONSUMO"],
                "mora_inmobiliario": mora_seg["INMOBILIARIO"],
                "mora_microcredito": mora_seg["MICROCR"],
                "mora_educativo": mora_seg["EDUCATIVO"],
                "utilidad_neta_periodo": utilidad_neta,
                "utilidad_anualizada": utilidad_anualizada,
                "gasto_operacion": gasto_operacion,
                "roa": roa,
                "roe": roe,
                "eficiencia": eficiencia,
            }
        )

    df_out = pd.DataFrame(rows_out).sort_values("total_activos", ascending=False)

    print(f"=== Corte: {fecha_id} ===")
    print("\n=== Bancos con fact_balance pero SIN fila (omitidos) ===")
    for s in skipped:
        print(" ", s)
    print(
        f"\n=== Bancos incluidos: {len(df_out)} de {len(privados)} privados totales ==="
    )

    print("\n=== Revisión de posibles outliers ===")
    print("morosidad_total fuera de [0,1]:")
    print(
        df_out[(df_out.morosidad_total < 0) | (df_out.morosidad_total > 1)][
            ["banco", "morosidad_total", "cartera_bruta", "cartera_improductiva"]
        ]
    )
    print(
        "\ncobertura > 1000% (10x) -- no necesariamente un error, ver nota en docs/indicadores_excel_bcos_coop.md:"
    )
    print(
        df_out[df_out.cobertura > 10][
            ["banco", "cobertura", "provision_cartera", "cartera_improductiva"]
        ]
    )
    print("\nroa/roe nulos:")
    print(
        df_out[df_out.roa.isna() | df_out.roe.isna()][
            ["banco", "roa", "roe", "total_activos"]
        ]
    )

    print("\n", df_out.to_string())

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"indicadores_excel_{fecha_id}.json"
    clean = json.loads(df_out.where(pd.notnull(df_out), None).to_json(orient="records"))
    out_path.write_text(
        json.dumps(
            {"fecha_cierre": str(fecha_id), "indicadores": clean},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\nEscrito:", out_path)


if __name__ == "__main__":
    main()
