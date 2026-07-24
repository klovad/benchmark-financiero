# Muestras de `marts.*` en Parquet

Snapshot de un mes del esquema estrella completo (18 tablas: 8 dimensiones + 10 hechos),
exportado directo de Postgres con `etl/export_sample_parquet.py`. Pensado para poder
probar el modelo de datos (notebooks, Power BI import, lo que sea) **sin tener Postgres
cargado** — por ejemplo en otra sesión/máquina donde el ETL todavía no corrió.

## `marts_2026-03/`

- **Catálogos** (`dim_banco`, `dim_canton`, `dim_segmento_credito`,
  `dim_subsegmento_credito`, `dim_categoria_deposito`, `dim_plazo`,
  `dim_cuenta_contable`): completos, no recortados por fecha — son chicos y los hechos
  necesitan el catálogo completo para resolver sus FK.
- **`dim_fecha`**: acotada a las fechas que realmente aparecen en los hechos exportados
  (5 fechas: el corte mensual de CAPCOL/`TasasHistorico`/Boletín + los cortes semanales
  de BCE tsp/tsa dentro de marzo 2026).
- **Hechos**: filtrados a `anio=2026, mes=3` vía `dim_fecha`. CAPCOL es mensual (una
  fecha), BCE tsp/tsa es semanal (~4-5 fechas), `TasasHistorico`/Boletín son mensuales.
- 104.717 filas totales, ~4.2 MB.

## Regenerar para otro mes

```powershell
.venv\Scripts\python -m etl.export_sample_parquet --anio 2026 --mes 3
```

Requiere Postgres cargado con ese mes (`sql/*.sql` aplicado + `python -m etl.pipeline`
corrido para las fuentes que lo cubran). Si un mes no tiene cobertura en alguna fuente
(ej. CAPCOL solo llega hasta donde el ETL se haya corrido — ver "Alcance de los datos"
en el `README.md` del repo), esa tabla sale con 0 filas, no falla.

## Uso típico

```python
import pandas as pd
fact_saldo_cartera = pd.read_parquet("data/samples/marts_2026-03/fact_saldo_cartera.parquet")
dim_banco = pd.read_parquet("data/samples/marts_2026-03/dim_banco.parquet")
df = fact_saldo_cartera.merge(dim_banco, on="banco_id")
```

Grano, tipos y relaciones de cada tabla: `docs/data_dictionary.md` y
`docs/architecture.md` en la raíz del repo — el Parquet es un espejo 1:1 de `marts.*`,
sin transformación adicional.
