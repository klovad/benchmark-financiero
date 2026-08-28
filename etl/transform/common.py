import hashlib
import re
import unicodedata
import zipfile
from pathlib import Path

import openpyxl

from etl.config import PROVINCIA_REGION


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_single_xlsx(zip_path: Path, extract_dir: Path) -> Path:
    """Los ZIP de Superbancos contienen exactamente un .xlsx -- salvo boletines
    antiguos (~2021-2022) que traen .xlsm (macro-enabled), mismo formato para
    openpyxl."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        xlsx_names = [
            n for n in zf.namelist() if n.lower().endswith((".xlsx", ".xlsm"))
        ]
        if len(xlsx_names) != 1:
            raise ValueError(
                f"{zip_path.name}: se esperaba 1 .xlsx/.xlsm dentro del zip, se encontraron {len(xlsx_names)}"
            )
        zf.extract(xlsx_names[0], extract_dir)
        return extract_dir / xlsx_names[0]


def find_base_sheets(workbook: openpyxl.Workbook) -> list[str]:
    """Casi todos los archivos traen 1 sola hoja 'BASE ...', pero el de vivienda trae 2
    (inmobiliario y vivienda de interés público van en hojas BASE separadas)."""
    candidates = [s for s in workbook.sheetnames if s.upper().startswith("BASE")]
    if not candidates:
        raise ValueError("No se encontró ninguna hoja 'BASE...'")
    return candidates


def normalize_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return re.sub(r"\s+", " ", text).upper() or None


def normalize_banco(value) -> str | None:
    return normalize_text(value)


def normalize_provincia(value) -> str | None:
    """CAPCOL escribe provincias sin tilde (BOLIVAR, GALAPAGOS, LOS RIOS...) pero SÍ
    conserva la Ñ (CAÑAR); BCE trae las mismas provincias con tilde (BOLÍVAR, GALÁPAGOS).
    marts.dim_provincia usa la convención de CAPCOL (histórico, más largo) como canónica
    -- así que se quita solo el acento agudo (U+0301) tras descomponer NFKD, NO cualquier
    marca combinante, para no perder la Ñ (que en NFKD es N + tilde combinante U+0303,
    una marca distinta)."""
    text = normalize_text(value)
    if text is None:
        return None
    decomposed = unicodedata.normalize("NFKD", text)
    sin_agudo = "".join(c for c in decomposed if c != "́")
    return unicodedata.normalize("NFC", sin_agudo)


_PROVINCIA_REGION_NORM = {_strip_accents(k): v for k, v in PROVINCIA_REGION.items()}


def region_for_provincia(provincia: str | None) -> str | None:
    if provincia is None:
        return None
    return _PROVINCIA_REGION_NORM.get(_strip_accents(provincia.strip().upper()))


def month_end_date(value):
    """Las fechas del origen ya vienen como fin de mes (ej. 31/01/2024); se normaliza a date."""
    if value is None:
        return None
    return value.date() if hasattr(value, "date") else value
