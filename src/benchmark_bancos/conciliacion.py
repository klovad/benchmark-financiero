"""Control de conciliación saldos vs. contabilidad (2026-10-09, `sql/39`).

Evalúa `marts.vw_conciliacion_resumen` de los últimos meses contra umbrales por tipo de
entidad y medida, y registra ERROR por cada mes fuera de rango: así una actualización que
trae datos que no cuadran termina con código 2 en vez de pasar inadvertida.

Umbrales medidos sobre 68 meses (2021-01 a 2026-08), con margen:

| tipo / medida               | histórico de la mediana mensual | umbral      |
|-----------------------------|---------------------------------|-------------|
| cooperativas, cartera       | 0,00% siempre (≥92% en ±0,5%)   | ±0,5%, ≥85% en ±2% |
| cooperativas, depósitos     | 0,00% siempre (≥97% en ±0,5%)   | ±0,5%, ≥90% en ±2% |
| mutualistas, depósitos      | 0,00% siempre                   | ±0,5%       |
| bancos privados, cartera    | -0,24% a +0,08%                 | ±1%, ≥70% en ±2%   |
| bancos privados, depósitos  | -1,06% a -0,52% (5 subcuentas)  | ±2%, ≥70% en ±2%   |
| mutualistas, cartera        | +1% a +47% (fideicomiso)        | no se evalúa |
"""

import logging
from dataclasses import dataclass

import psycopg

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Umbral:
    mediana_max: float  # |mediana mensual| máxima
    dentro_2pct_min: float = 0.0  # fracción mínima de entidades dentro de ±2%


UMBRALES: dict[tuple[str, str], Umbral] = {
    ("COOPERATIVA", "cartera"): Umbral(0.005, 0.85),
    ("COOPERATIVA", "depositos"): Umbral(0.005, 0.90),
    ("MUTUALISTA", "depositos"): Umbral(0.005),
    ("BANCO PRIVADO", "cartera"): Umbral(0.01, 0.70),
    ("BANCO PRIVADO", "depositos"): Umbral(0.02, 0.70),
}


@dataclass
class Resultado:
    fecha_id: int
    tipo_entidad: str
    medida: str
    entidades: int
    mediana_pct: float
    dentro_2pct: float

    def falla(self, umbral: Umbral) -> str | None:
        if abs(self.mediana_pct) > umbral.mediana_max:
            return f"mediana {self.mediana_pct:+.2%} fuera de ±{umbral.mediana_max:.1%}"
        if self.dentro_2pct < umbral.dentro_2pct_min:
            return (
                f"solo {self.dentro_2pct:.0%} de las entidades dentro de ±2% "
                f"(mínimo {umbral.dentro_2pct_min:.0%})"
            )
        return None


def evaluar(resultados: list[Resultado]) -> list[str]:
    """Devuelve un mensaje por cada (mes, tipo, medida) fuera de umbral."""
    fallas = []
    for r in resultados:
        umbral = UMBRALES.get((r.tipo_entidad, r.medida))
        if umbral is None:
            continue
        motivo = r.falla(umbral)
        if motivo:
            fallas.append(
                f"{r.fecha_id} {r.tipo_entidad} {r.medida} ({r.entidades} entidades): {motivo}"
            )
    return fallas


def verificar(conn: psycopg.Connection, meses: int = 3) -> list[str]:
    """Evalúa los últimos `meses` cortes con contabilidad cargada. Registra un ERROR por
    cada falla (el CLI termina con código 2) y devuelve la lista."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH ultimos AS (
                SELECT DISTINCT fecha_id FROM marts.fact_balance
                ORDER BY fecha_id DESC LIMIT %s
            )
            SELECT r.fecha_id, r.tipo_entidad, r.medida, r.entidades,
                   r.mediana_pct, r.dentro_2pct
            FROM marts.vw_conciliacion_resumen r
            WHERE r.fecha_id IN (SELECT fecha_id FROM ultimos)
            ORDER BY r.fecha_id, r.tipo_entidad, r.medida
            """,
            (meses,),
        )
        resultados = [
            Resultado(f, t, m, n, float(med), float(d2))
            for f, t, m, n, med, d2 in cur.fetchall()
        ]
    if not resultados:
        log.info("conciliación: sin meses con saldos y contabilidad para evaluar")
        return []
    fallas = evaluar(resultados)
    for f in fallas:
        log.error("conciliación fuera de umbral: %s", f)
    evaluados = sum(1 for r in resultados if (r.tipo_entidad, r.medida) in UMBRALES)
    if not fallas:
        log.info(
            "conciliación OK: %d combinaciones mes × tipo × medida dentro de umbral "
            "(cortes %s a %s)",
            evaluados,
            resultados[0].fecha_id,
            resultados[-1].fecha_id,
        )
    return fallas
