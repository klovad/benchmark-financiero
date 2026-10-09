"""
Configuracion de logging compartida por todo el pipeline.

Reemplaza los `logging.basicConfig(...)` duplicados que antes vivian en cada
modulo de entrada (`pipeline.py`, `extract/scrape_superbancos.py`,
`extract/scrape_boletin.py`, y los bloques `__main__` de `extract/download_bce.py` /
`extract/download_tasas_historicas.py`) con un unico punto de configuracion, mas un
`run_id` corto de correlacion por corrida.

El `run_id` se agrega via un `logging.Filter` sobre el handler y se referencia en el
`Formatter` -- no hace falta tocar ninguno de los `log.info(...)` ya existentes en los
demas modulos (siguen usando `logging.getLogger(__name__)` tal cual).
"""

import logging
import uuid
from pathlib import Path

RUN_ID = uuid.uuid4().hex[:8]


class _RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = RUN_ID
        return True


_FORMATO = "%(asctime)s %(levelname)s [%(run_id)s] %(message)s"


def setup_logging(level: int = logging.INFO, log_file: Path | None = None) -> None:
    """Configura el root logger una sola vez por proceso.

    Idempotente: si el root logger ya tiene handlers (porque otro modulo del
    pipeline ya llamo a `setup_logging()` en esta misma corrida, o porque un test
    importa varios modulos que lo invocan) no vuelve a agregar handlers duplicados.

    `log_file` (2026-10-09): además de la consola, escribe a ese archivo en UTF-8 (para
    corridas programadas, donde la consola de Windows rompe los acentos).
    """
    root = logging.getLogger()
    if root.handlers:
        return
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    for handler in handlers:
        handler.addFilter(_RunIdFilter())
        handler.setFormatter(logging.Formatter(_FORMATO))
        root.addHandler(handler)
    root.setLevel(level)
