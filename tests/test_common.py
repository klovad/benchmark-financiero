from pathlib import Path

from benchmark_bancos.transform.common import sha256_file


def test_sha256_file_is_deterministic(tmp_path: Path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"contenido de prueba")

    assert sha256_file(path) == sha256_file(path)


def test_sha256_file_is_content_sensitive(tmp_path: Path):
    path_a = tmp_path / "a.txt"
    path_b = tmp_path / "b.txt"
    path_a.write_bytes(b"contenido A")
    path_b.write_bytes(b"contenido B")

    assert sha256_file(path_a) != sha256_file(path_b)
