"""Configuración del proyecto, separada por responsabilidad:

- `settings`: lo que depende del entorno (.env): rutas, base de datos, años.
- `sources`: URLs, sub-portales e ids de descarga de cada fuente.
- `domain`: catálogos de vocabulario de las fuentes al modelo canónico.

Se reexporta todo para que `from benchmark_bancos.config import X` funcione sin importar
en qué módulo vive X.
"""

from benchmark_bancos.config.domain import *  # noqa: F401,F403
from benchmark_bancos.config.settings import *  # noqa: F401,F403
from benchmark_bancos.config.sources import *  # noqa: F401,F403
