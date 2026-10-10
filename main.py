"""Punto de entrada del proyecto.

    uv run main.py <etapa> [opciones]

Delega en `benchmark_bancos.cli`, que define las etapas y opciones (ver
`uv run main.py --help`). Equivale a `uv run benchmark-bancos <etapa>` y a
`python -m benchmark_bancos <etapa>`.

Etapas:
    migrate [--status|--baseline]  aplica las migraciones sql/ pendientes
    conciliar [--meses N]          control saldos vs. contabilidad (solo lectura)
    actualizar [--fuentes ...]     actualización incremental de todas las fuentes (programable)
    extract / load / all   CAPCOL (bancos privados y Banca Pública; --portales)
    bce                    BCE tasas semanales tsp/tsa
    tasas-historicas       BCE techos y tasas referenciales (TasasHistorico.htm)
    boletin                Boletín Financiero de Superbancos (balance / PyG)
    seps                   SEPS cooperativas y mutualistas (cartera, depósitos, EEFF)
    refresh [--full]       solo recalcula marts desde staging
"""

from benchmark_bancos.cli import run

if __name__ == "__main__":
    run()
