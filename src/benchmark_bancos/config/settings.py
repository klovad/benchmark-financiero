"""Configuración que depende del entorno: rutas, base de datos y años a procesar.

Todo lo que cambia entre máquinas o despliegues vive aquí y se lee de variables de
entorno (con `.env` en la raíz del proyecto como respaldo). Las constantes de las fuentes
(`sources.py`) y del dominio (`domain.py`) no dependen del entorno.

La raíz del proyecto NO se deriva de `__file__`: con el paquete instalado (no editable)
`__file__` apunta a site-packages. Se toma de `BENCHMARK_HOME` si está definida y, si no,
del primer directorio desde el cwd hacia arriba que contenga `pyproject.toml`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def _find_project_root() -> Path:
    if env := os.getenv("BENCHMARK_HOME"):
        return Path(env).resolve()
    cwd = Path.cwd().resolve()
    for d in (cwd, *cwd.parents):
        if (d / "pyproject.toml").exists():
            return d
    return cwd


PROJECT_ROOT = _find_project_root()
load_dotenv(PROJECT_ROOT / ".env")

# Seeds curados viajan DENTRO del paquete (no dependen del cwd).
SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"

RAW_DIR = PROJECT_ROOT / os.getenv("SCRAPER_DOWNLOAD_DIR", "data/raw")
BCE_DIR = RAW_DIR / "bce"
SEPS_DIR = RAW_DIR / "seps"
EXTRACT_DIR = RAW_DIR.parent / "_tmp_extract"

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "benchmark_cartera_depositos"),
    "user": os.getenv("POSTGRES_USER", "bp_etl"),
    "password": os.getenv("POSTGRES_PASSWORD", "changeme"),
}

DEFAULT_YEARS = [
    int(y)
    for y in os.getenv("SCRAPER_YEARS", "2021,2022,2023,2024,2025,2026").split(",")
]
