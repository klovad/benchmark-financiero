"""Descarga condicional de la SEPS (2026-10-09): el año en curso se republica con el
mismo download_id, así que "la carpeta ya tiene un .zip" no basta. Sin red."""

import io
import json

import pytest

from benchmark_bancos.extract import download_seps as ds

FINAL = "https://example.test/uploads/2026/09/2026-CAP.zip"


class _Resp(io.BytesIO):
    def __init__(self, data=b"", url=FINAL, headers=None):
        super().__init__(data)
        self.url = url
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@pytest.fixture
def seps(monkeypatch, tmp_path):
    monkeypatch.setattr(ds, "SEPS_DOWNLOAD_IDS", {2026: {"captaciones": 1}})
    gets = []

    def instalar(contenido, last_modified="Wed, 30 Sep 2026 17:15:16 GMT"):
        def fake(req, timeout=None):
            headers = {"Last-Modified": last_modified, "Content-Length": len(contenido)}
            if req.get_method() == "HEAD":
                return _Resp(url=FINAL, headers=headers)
            gets.append(req.full_url)
            return _Resp(contenido, url=FINAL, headers=headers)

        monkeypatch.setattr(ds.urllib.request, "urlopen", fake)

    return tmp_path, gets, instalar


def test_primera_descarga_guarda_meta(seps):
    out, gets, instalar = seps
    instalar(b"datos-agosto")
    dest = ds.download_seps_file(2026, "captaciones", out)
    assert dest.read_bytes() == b"datos-agosto" and len(gets) == 1
    meta = json.loads((dest.parent / "_descarga.json").read_text())
    assert meta["url_final"] == FINAL


def test_misma_version_no_descarga(seps):
    out, gets, instalar = seps
    instalar(b"datos-agosto")
    ds.download_seps_file(2026, "captaciones", out)
    ds.download_seps_file(2026, "captaciones", out)
    assert len(gets) == 1


def test_version_nueva_reemplaza_y_deja_un_solo_zip(seps):
    out, gets, instalar = seps
    instalar(b"datos-agosto")
    ds.download_seps_file(2026, "captaciones", out)
    instalar(b"datos-septiembre", last_modified="Fri, 30 Oct 2026 10:00:00 GMT")
    dest = ds.download_seps_file(2026, "captaciones", out)
    assert dest.read_bytes() == b"datos-septiembre" and len(gets) == 2
    assert len(list(dest.parent.glob("*.zip"))) == 1


def test_zip_local_sin_meta_que_coincide_no_se_descarga(seps):
    out, gets, instalar = seps
    carpeta = out / "2026" / "captaciones"
    carpeta.mkdir(parents=True)
    (carpeta / "2026-CAP.zip").write_bytes(b"datos-agosto")
    instalar(b"datos-agosto")  # mismo nombre y tamaño
    ds.download_seps_file(2026, "captaciones", out)
    assert gets == []
    assert (carpeta / "_descarga.json").exists()


# Estructura real del portal (2026-11-01), recortada: la sección de situación financiera
# no tiene encabezado, EEFF aparece en Reportes y en Bases de Datos (vale el segundo) y
# trae una fila extra de 2026; Volumen de crédito va antes de Colocaciones.
_PORTAL = """
<h4>Reportes</h4><h5>Estados Financieros Mensuales</h5>
<a href="?sdm_process_download=1&amp;download_id=10">2027</a>
<h4>Bases de Datos:</h4><p>Estados Financieros Mensuales</p>
<a href="?smd_process_download=1&amp;download_id=11">2027</a>
<a href="?sdm_process_download=1&amp;download_id=12">Años anteriores</a>
<a href="?sdm_process_download=1&amp;download_id=13">2027</a>
<p>Dep&oacute;sitos</p><h4>Reportes</h4><h5>Captaciones mensuales</h5>
<a href="?sdm_process_download=1&amp;download_id=20">2027</a>
<h4>Bases de Datos:</h4><h5>Captaciones mensuales</h5>
<a href="?sdm_process_download=1&amp;download_id=21">2027</a>
<p>Cartera de crédito</p><h4>Reportes</h4><h5>Volumen de crédito mensual</h5>
<a href="?sdm_process_download=1&amp;download_id=30">2027</a>
<h5>Colocaciones mensuales</h5>
<a href="?sdm_process_download=1&amp;download_id=31">2027</a>
<a href="?sdm_process_download=1&amp;download_id=32">2026</a>
"""


def test_descubrir_download_ids_del_portal():
    ids = ds.descubrir_download_ids(_PORTAL)
    assert ids[2027] == {"eeff": 11, "captaciones": 20, "colocaciones": 31}
    assert ids[2026] == {"colocaciones": 32}


def test_anio_sin_id_fijo_usa_el_portal_y_omite_si_falta(monkeypatch, tmp_path):
    monkeypatch.setattr(ds, "SEPS_DOWNLOAD_IDS", {})
    monkeypatch.setattr(
        ds, "_ids_del_portal", lambda: ds.descubrir_download_ids(_PORTAL)
    )
    bajados = []
    monkeypatch.setattr(
        ds,
        "download_seps_file",
        lambda year, reporte, out_dir, ids: bajados.append(
            (year, reporte, ids[reporte])
        ),
    )
    resultado = ds.download_seps([2026, 2027], tmp_path)
    assert list(resultado) == [2027]  # 2026 sin eeff ni captaciones en el portal
    assert sorted(bajados) == [
        (2027, "captaciones", 20),
        (2027, "colocaciones", 31),
        (2027, "eeff", 11),
    ]
