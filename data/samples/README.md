# Muestras de `marts.*` en Parquet

Exportes de `marts.*` a Parquet con `etl/export_sample_parquet.py`. Pensado para poder
probar el modelo de datos (notebooks, Power BI import, lo que sea) **sin tener Postgres
cargado** — por ejemplo en otra sesión/máquina donde el ETL todavía no corrió. Dos
variantes: una muestra chica de un mes (`marts_AAAA-MM/`) y una ventana de años recientes
(`marts_ultimos_5_anios/`).

## `marts_ultimos_5_anios/`

Todo `marts.*` tal cual está en Postgres, limitado a los últimos 5 años calendario con
datos (2022-2026 a esta fecha; 5.398.866 filas, ~201 MB — el histórico completo desde
2008 pesa ~394 MB, se descartó versionar eso para no inflar el repo sin necesidad real).
Los 10 catálogos (`dim_banco`, `dim_canton`, `dim_provincia`, `dim_segmento_credito`,
`dim_subsegmento_credito`, `dim_segmento_entidad`, `dim_categoria_deposito`, `dim_plazo`,
`dim_cuenta_contable`, `dim_fecha`) van completos en un solo archivo cada uno — son
chicos y los hechos filtrados igual necesitan el catálogo completo para resolver sus FK
(`dim_fecha` no se recorta a la ventana de 5 años tampoco, mismo motivo). Los 10 hechos
se **particionan por año** (`{tabla}_{anio}.parquet`, vía `dim_fecha.anio`): sin
particionar, `fact_colocaciones_cartera` del histórico completo pesaría 230 MB, por
encima del límite de 100 MB/archivo de GitHub sin Git LFS; particionado, el archivo más
grande de esta ventana pesa ~24 MB. Para reconstruir una tabla completa en pandas:

```python
import glob
import pandas as pd
fact_colocaciones_cartera = pd.concat(
    pd.read_parquet(f) for f in sorted(glob.glob("data/samples/marts_ultimos_5_anios/fact_colocaciones_cartera_*.parquet"))
)
```

Regenerar: `.venv\Scripts\python -m etl.export_sample_parquet --full --anios-recientes 5`
(requiere Postgres cargado). Para el histórico completo sin recortar, `--full` solo (sin
`--anios-recientes`) exporta a `marts_full/` — no versionado por defecto, generarlo aparte
si hace falta.

## `marts_AAAA-MM/` (muestra de un mes)

No versionada por defecto (se regenera al vuelo cuando hace falta un sample chico
puntual) — genera una carpeta como esta:

- **Catálogos** (`dim_banco`, `dim_canton`, `dim_segmento_credito`,
  `dim_subsegmento_credito`, `dim_categoria_deposito`, `dim_plazo`,
  `dim_cuenta_contable`): completos, no recortados por fecha — son chicos y los hechos
  necesitan el catálogo completo para resolver sus FK.
- **`dim_fecha`**: acotada a las fechas que realmente aparecen en los hechos exportados
  (el corte mensual de CAPCOL/`TasasHistorico`/Boletín + los cortes semanales de BCE
  tsp/tsa dentro del mes).
- **Hechos**: filtrados por `(anio, mes)` vía `dim_fecha`. CAPCOL es mensual (una
  fecha), BCE tsp/tsa es semanal (~4-5 fechas), `TasasHistorico`/Boletín son mensuales.

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
fact_saldo_cartera = pd.read_parquet("data/samples/marts_ultimos_5_anios/fact_saldo_cartera_2026.parquet")
dim_banco = pd.read_parquet("data/samples/marts_ultimos_5_anios/dim_banco.parquet")
df = fact_saldo_cartera.merge(dim_banco, on="banco_id")
```

Grano, tipos y relaciones de cada tabla: `docs/data_dictionary.md` y
`docs/architecture.md` en la raíz del repo — el Parquet es un espejo 1:1 de `marts.*`,
sin transformación adicional.

Nota: `fact_colocaciones_cartera_*.parquet` incluye `es_operacion_especial` (`'NO'` para
la cartera BCE normal, `'SI'` para las Operaciones Especiales de Banco de Guayaquil,
integrada desde `operaciones_especiales.xlsx` — ver `docs/fuentes_datos.md`).
