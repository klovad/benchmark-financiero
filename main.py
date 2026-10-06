"""Punto de entrada del proyecto.

    uv run main.py <etapa> [opciones]

Delega en `benchmark_bancos.cli`, que define las etapas y opciones (ver
`uv run main.py --help`). Equivale a `uv run benchmark-bancos <etapa>` y a
`python -m benchmark_bancos <etapa>`.

Etapas:
    extract / load / all   CAPCOL (bancos privados y Banca Pública; --portales)
    bce                    BCE tasas semanales tsp/tsa
    tasas-historicas       BCE techos y tasas referenciales (TasasHistorico.htm)
    boletin                Boletín Financiero de Superbancos (balance / PyG)
    seps                   SEPS cooperativas y mutualistas (cartera, depósitos, EEFF)
    refresh [--full]       solo recalcula marts desde staging
"""

from benchmark_bancos.cli import main

if __name__ == "__main__":
    main()
