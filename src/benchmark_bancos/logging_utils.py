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

RUN_ID = uuid.uuid4().hex[:8]


class _RunIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = RUN_ID
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configura el root logger una sola vez por proceso.

    Idempotente: si el root logger ya tiene handlers (porque otro modulo del
    pipeline ya llamo a `setup_logging()` en esta misma corrida, o porque un test
    importa varios modulos que lo invocan) no vuelve a agregar handlers duplicados.
    """
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.addFilter(_RunIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(run_id)s] %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)
