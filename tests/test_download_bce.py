"""Descarga condicional del BCE (2026-10-09): el archivo tsp/tsa se republica con el
mismo nombre, así que "existe en disco" no basta para saltar la descarga. Sin red: se
reemplaza urllib.request.urlopen."""

import io
import json
import urllib.error

import pytest

from benchmark_bancos.extract import download_bce

URL = "https://example.test/tsp_desde_200801.zip"
LAST_MODIFIED = "Mon, 05 Oct 2026 16:22:07 GMT"


class _Resp(io.BytesIO):
    def __init__(self, data, headers):
        super().__init__(data)
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@pytest.fixture
def bce(monkeypatch, tmp_path):
    monkeypatch.setattr(download_bce, "BCE_URLS", {"tsp": URL})
    pedidos = []

    def instalar(respuesta):
        def fake_urlopen(req, timeout=None):
            pedidos.append(dict(req.header_items()))
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta

        monkeypatch.setattr(download_bce.urllib.request, "urlopen", fake_urlopen)

    return tmp_path, pedidos, instalar


def test_sin_copia_local_descarga_y_guarda_meta(bce):
    out, pedidos, instalar = bce
    instalar(_Resp(b"nuevo", {"ETag": '"abc"', "Last-Modified": LAST_MODIFIED}))
    dest = download_bce.download_bce_file("tsp", out)
    assert dest.read_bytes() == b"nuevo"
    meta = json.loads((out / "tsp_desde_200801.zip.meta.json").read_text())
    assert meta["etag"] == '"abc"'
    assert "If-none-match" not in pedidos[0]  # sin copia local no hay condición


def test_copia_local_sin_cambios_304_conserva_archivo(bce):
    out, pedidos, instalar = bce
    dest = out / "tsp_desde_200801.zip"
    dest.write_bytes(b"viejo")
    (out / "tsp_desde_200801.zip.meta.json").write_text(
        json.dumps({"etag": '"abc"', "last_modified": LAST_MODIFIED})
    )
    instalar(urllib.error.HTTPError(URL, 304, "Not Modified", {}, None))
    assert download_bce.download_bce_file("tsp", out) == dest
    assert dest.read_bytes() == b"viejo"
    assert pedidos[0]["If-none-match"] == '"abc"'
    assert pedidos[0]["If-modified-since"] == LAST_MODIFIED
    assert not (out / "tsp_desde_200801.zip.part").exists()


def test_copia_local_desactualizada_se_reemplaza(bce):
    out, pedidos, instalar = bce
    dest = out / "tsp_desde_200801.zip"
    dest.write_bytes(b"viejo")  # bajado antes del cambio: sin .meta.json
    instalar(_Resp(b"nuevo", {"ETag": '"def"', "Last-Modified": LAST_MODIFIED}))
    download_bce.download_bce_file("tsp", out)
    assert dest.read_bytes() == b"nuevo"
    assert "If-modified-since" in pedidos[0]  # usa la fecha del archivo local


def test_otro_error_http_se_propaga(bce):
    out, _, instalar = bce
    instalar(urllib.error.HTTPError(URL, 500, "Server Error", {}, None))
    with pytest.raises(urllib.error.HTTPError):
        download_bce.download_bce_file("tsp", out)
