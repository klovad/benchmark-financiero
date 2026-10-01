"""Parsers SEPS con fixtures sintéticos que reproducen las variaciones reales 2021-2025
(docs/fuentes_datos.md sección 4.0) -- sin red ni DB."""

import datetime
import zipfile

import openpyxl
import pytest

from etl.transform.banco_matching import RucInvalidoError, resolver_entidad_seps
from etl.transform.categoria_deposito_matching import (
    CategoriaNoResueltaError,
    resolver_categoria_deposito_seps,
)
from etl.transform.parse_seps import (
    SubtipoCreditoSepsNoMapeadoError,
    parse_seps_captaciones_file,
    parse_seps_colocaciones_file,
    parse_seps_eeff_file,
    tipo_entidad_desde_archivo,
)

# RUC reales de entidades SEPS (estructuralmente válidos, ver validar_ruc_estructura)
RUC_COOP = "0190155722001"
RUC_MUT = "1790075494001"
RUC_CONAFIPS = "1768168480001"

COLOC_HDR = [
    "CARTERA POR VENCER", "CARTERA QUE NO DEVENGA INTERESES", "CARTERA VENCIDA",
    "CARTERA TOTAL", "NUMERO OPERACIONES", "NUMERO SUJETOS CREDITO", "FECHA DE CORTE",
    "REGION", "PROVINCIA", "CANTON", "SUBTIPO DE CREDITO", "ORIGEN OPERACION",
    "LINEA CREDITO", "ESTADO OPERACION", "CLASE DE CREDITO", "ACTIVIDAD ECONOMICA",
    "RUC", "RAZON SOCIAL",
]  # fmt: skip


def _coloc_row(fecha, subtipo, pv, nd, v, canton="QUITO", provincia="PICHINCHA",
               estado="ORIGINAL", ruc=RUC_COOP, razon="JEP LTDA"):  # fmt: skip
    return [pv, nd, v, pv + nd + v, 1, 1, fecha, "SIERRA", provincia, canton, subtipo,
            "CONCEDIDA POR LA ENTIDAD", None, estado, "INDIVIDUAL", "COMERCIO", ruc,
            razon]  # fmt: skip


def _zip_xlsx(tmp_path, zip_name, libros: dict[str, dict[str, list[list]]]):
    """libros: {nombre_archivo.xlsm: {hoja: filas}} -> ZIP con esos libros."""
    zpath = tmp_path / zip_name
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, hojas in libros.items():
            wb = openpyxl.Workbook()
            wb.remove(wb.active)
            for hoja, filas in hojas.items():
                ws = wb.create_sheet(hoja)
                for f in filas:
                    ws.append(f)
            local = tmp_path / nombre
            wb.save(local)
            z.write(local, f"carpeta/{nombre}")
    return zpath


def test_tipo_entidad_desde_archivo_variantes_reales():
    assert (
        tipo_entidad_desde_archivo("Boletin_captaciones_Dic25_Mut.xlsm") == "MUTUALISTA"
    )
    assert (
        tipo_entidad_desde_archivo("Boletin_captaciones_Dic22_Mut_1.xlsm")
        == "MUTUALISTA"
    )
    assert (
        tipo_entidad_desde_archivo("Reporte_colocaciones_dic_2025_MUT.xlsm")
        == "MUTUALISTA"
    )
    assert (
        tipo_entidad_desde_archivo("Boletin_captaciones_dic21_S1.xlsx") == "COOPERATIVA"
    )
    assert (
        tipo_entidad_desde_archivo("Reporte_colocaciones_dic_2023_SG1.xlsm")
        == "COOPERATIVA"
    )
    with pytest.raises(ValueError):
        tipo_entidad_desde_archivo("Reporte_colocaciones_dic_2025.xlsm")


def test_resolver_entidad_seps_reusa_llave_bce_y_rellena_ruc_numerico():
    assert resolver_entidad_seps("JEP", RUC_COOP, "COOPERATIVA") == (
        f"BCE_{RUC_COOP}",
        "JEP",
        "COOPERATIVA",
        RUC_COOP,
    )
    # Excel puede entregar el RUC como int (pierde el 0 inicial)
    assert resolver_entidad_seps("JEP", int(RUC_COOP), "COOPERATIVA")[3] == RUC_COOP
    with pytest.raises(RucInvalidoError):
        resolver_entidad_seps(
            "X", "0190155723001", "COOPERATIVA"
        )  # dígito verificador alterado


def test_categoria_deposito_seps_sin_tildes_a_canonica():
    assert (
        resolver_categoria_deposito_seps("DEPOSITOS A LA VISTA")
        == "DEPÓSITOS A LA VISTA"
    )
    assert (
        resolver_categoria_deposito_seps("DEPOSITOS DE GARANTIA")
        == "DEPÓSITOS DE GARANTÍA"
    )
    assert (
        resolver_categoria_deposito_seps("OPERACIONES DE REPORTO")
        == "OPERACIONES DE REPORTO"
    )
    with pytest.raises(CategoriaNoResueltaError):
        resolver_categoria_deposito_seps("DEPOSITOS DE AHORRO PROGRAMADO")


def test_colocaciones_semestres_serial_excel_y_hoja_auxiliar(tmp_path):
    d = datetime.datetime
    libros = {
        "Reporte_colocaciones_dic_2025_S1.xlsm": {
            "Base_colocaciones": [
                COLOC_HDR,
                _coloc_row(d(2025, 7, 31), "MICROCREDITO", 100.0, 10.0, 5.0),
                # mismo grano, otro ESTADO OPERACION -> se suma
                _coloc_row(
                    d(2025, 7, 31), "MICROCREDITO", 50.0, 0.0, 0.0, estado="NOVADA"
                ),
                _coloc_row(d(2025, 7, 31), "OPERACIONES CONTINGENTES", 9.0, 0.0, 0.0),
                [None] * len(COLOC_HDR),  # relleno vacío al final
            ],
            # primer semestre: FECHA DE CORTE como serial de Excel (45688 = 2025-01-31)
            "Base_colocacionesISEM": [
                COLOC_HDR,
                _coloc_row(45688, "INMOBILARIO", 200.0, 0.0, 0.0,
                           canton="DISTRITO METROPOLITANO DE QUITO"),  # fmt: skip
            ],
            # auxiliar de la portada, fecha fija 2017 -> debe ignorarse
            "Base_para_actual": [
                COLOC_HDR[:4] + ["FECHA DE CORTE"],
                [1, 1, 1, 3, 42916],
            ],
        },
        "Reporte_colocaciones_abr_2021_MUT.xlsm": {
            "Base_colocaciones": [
                COLOC_HDR,
                _coloc_row(d(2021, 1, 31), "CONSUMO PRIORITARIO", 70.0, 0.0, 0.0,
                           ruc=RUC_MUT, razon="PICHINCHA"),  # fmt: skip
                _coloc_row(d(2021, 1, 31), "COMERCIAL ORDINARIO", 30.0, 0.0, 0.0,
                           ruc=RUC_MUT, razon="PICHINCHA"),  # fmt: skip
            ],
        },
    }
    df, entidades = parse_seps_colocaciones_file(
        _zip_xlsx(tmp_path, "2025-COL.zip", libros), tmp_path / "x"
    )
    tot = df.groupby(["fecha", "tipo_credito", "estado_cartera"]).saldo.sum()
    assert tot[(datetime.date(2025, 7, 31), "microcredito", "por_vencer")] == 150.0
    assert tot[(datetime.date(2025, 7, 31), "microcredito", "vencida")] == 5.0
    assert tot[(datetime.date(2025, 1, 31), "inmobiliario", "por_vencer")] == 200.0
    assert tot[(datetime.date(2021, 1, 31), "consumo", "por_vencer")] == 70.0
    assert tot[(datetime.date(2021, 1, 31), "comercial", "por_vencer")] == 30.0
    assert datetime.date(2017, 6, 30) not in set(df.fecha)
    assert "OPERACIONES CONTINGENTES" not in set(df.tipo_credito)
    assert df.saldo.sum() == 150 + 10 + 5 + 200 + 70 + 30
    # alias de cantón BCE aplicado (DISTRITO METROPOLITANO DE QUITO -> QUITO)
    assert set(df.canton) == {"QUITO"}
    assert {e[2] for e in entidades} == {"COOPERATIVA", "MUTUALISTA"}
    assert set(df.loc[df.banco_codigo == f"BCE_{RUC_MUT}", "tipo_entidad"]) == {
        "MUTUALISTA"
    }


def test_colocaciones_subtipo_nuevo_falla_fuerte(tmp_path):
    libros = {
        "Reporte_colocaciones_dic_2025_S2.xlsm": {
            "Base_colocaciones": [
                COLOC_HDR,
                _coloc_row(datetime.datetime(2025, 7, 31), "LEASING", 1.0, 0.0, 0.0),
            ]
        }
    }
    with pytest.raises(SubtipoCreditoSepsNoMapeadoError):
        parse_seps_colocaciones_file(
            _zip_xlsx(tmp_path, "2025-COL.zip", libros), tmp_path / "x"
        )


def test_captaciones_suma_estados_y_marca_segundo_piso(tmp_path):
    hdr = ["SALDO", "NUMERO DE CLIENTES", "NUMERO DE CUENTAS", "FECHA DE CORTE",
           "REGION", "PROVINCIA", "CANTON", "TIPO DE DEPOSITO", "ESTADO OPERACIÓN",
           "RUC", "RAZON SOCIAL"]  # fmt: skip
    f = datetime.datetime(2024, 12, 31)
    libros = {
        "Boletin_captaciones_Dic24_S1.xlsm": {
            "Base_captaciones": [
                hdr,
                [100.0, 3, 4, f, "SIERRA", "AZUAY", "CUENCA", "DEPOSITOS A PLAZO",
                 "NUEVA - ...", RUC_COOP, "JEP"],  # fmt: skip
                [900.0, 7, 8, f, "SIERRA", "AZUAY", "CUENCA", "DEPOSITOS A PLAZO",
                 "VIGENTE - ...", RUC_COOP, "JEP"],  # fmt: skip
                [5.0, 1, 1, f, "SIERRA", "PICHINCHA", "QUITO", "DEPOSITOS A LA VISTA",
                 "VIGENTE - ...", RUC_CONAFIPS, "CONAFIPS"],  # fmt: skip
            ]
        }
    }
    df, entidades = parse_seps_captaciones_file(
        _zip_xlsx(tmp_path, "2024-CAP.zip", libros), tmp_path / "x"
    )
    plazo = df[df.categoria_deposito == "DEPÓSITOS A PLAZO"].iloc[0]
    assert (plazo.saldo, plazo.numero_clientes, plazo.numero_cuentas) == (
        1000.0,
        10,
        12,
    )
    assert plazo.plazo_dias_desde is None
    assert set(df.loc[df.banco_codigo == f"BCE_{RUC_CONAFIPS}", "tipo_entidad"]) == {
        "ENTIDAD DE SEGUNDO PISO"
    }
    assert len(entidades) == 2


def _zip_txt(tmp_path, nombre, contenido: bytes):
    zpath = tmp_path / (nombre + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nombre, contenido)
    return zpath


def test_eeff_formato_2021_punto_y_coma_bom_decimal_punto(tmp_path):
    txt = (
        "﻿FECHA_DE_CORTE;SEGMENTO;RUC;RAZON_SOCIAL;CUENTA;DESCRIPCION_CUENTA;SALDO_USD\n"
        f"2021-1-31;SEGMENTO 1 MUTUALISTA;{RUC_MUT};MUTUALISTA PICHINCHA;14;CARTERA;1000.5\n"
        f"2021-1-31;SEGMENTO 1 MUTUALISTA;{RUC_MUT};MUTUALISTA PICHINCHA;1499;PROV;-100\n"
        f"2021-1-31;SEGMENTO 1 MUTUALISTA;{RUC_MUT};MUTUALISTA PICHINCHA;21;OBLIG;0\n"
        f"2021-1-31;SEGMENTO 1 MUTUALISTA;{RUC_MUT};MUTUALISTA PICHINCHA;5101;INTERESES;7\n"
    ).encode("utf-8")
    r = parse_seps_eeff_file(_zip_txt(tmp_path, "2021 EEFF MEN.txt", txt))
    b = r["balance"].set_index("codigo").saldo_usd
    assert b.to_dict() == {"14": 1000.5, "1499": -100.0}  # el 0 se descarta
    assert r["pyg"].codigo.tolist() == ["5101"]
    assert r["balance"].fecha.iloc[0] == datetime.date(2021, 1, 31)
    assert r["entidades"] == [
        (f"BCE_{RUC_MUT}", "MUTUALISTA PICHINCHA", "MUTUALISTA", RUC_MUT)
    ]
    assert set(r["cuentas"].query("codigo == '5101'").reporte) == {"PYG"}
    assert "21" in set(r["cuentas"].codigo)  # la cuenta existe aunque su saldo sea 0


def test_eeff_formato_2025_tab_comillas_coma_decimal_y_vacios(tmp_path):
    txt = (
        "FECHA DE CORTE\tSEGMENTO\tRUC\tRAZON SOCIAL\tCUENTA\tDESCRIPCION CUENTA\tSALDO (USD)\n"
        f'"2025-6-30"\t"SEGMENTO 1"\t"{RUC_COOP}"\t"COAC JEP"\t"21"\t"OBLIG"\t25159,6\n'
        f'"2025-6-30"\t"SEGMENTO 1"\t"{RUC_COOP}"\t"COAC JEP"\t"2101"\t"VISTA"\t\n'
    ).encode("utf-8")
    r = parse_seps_eeff_file(_zip_txt(tmp_path, "EEFF MEN 2025.txt", txt))
    assert r["balance"].saldo_usd.tolist() == [25159.6]
    assert r["entidades"][0][2] == "COOPERATIVA"


def test_eeff_saldo_no_numerico_falla_fuerte(tmp_path):
    txt = (
        "FECHA DE CORTE\tSEGMENTO\tRUC\tRAZON SOCIAL\tCUENTA\tDESCRIPCION CUENTA\tSALDO (USD)\n"
        f'"2025-6-30"\t"SEGMENTO 1"\t"{RUC_COOP}"\t"COAC"\t"21"\t"OBLIG"\t1.234,5\n'
    ).encode("utf-8")
    with pytest.raises(ValueError, match="no numéricos"):
        parse_seps_eeff_file(_zip_txt(tmp_path, "EEFF MEN 2025.txt", txt))
