# Muestras de `marts.*` en Parquet

Exportes de `marts.*` con `scripts/export_sample_parquet.py`, para probar el modelo de
datos (notebooks, BI, lo que sea) **sin tener Postgres cargado**. **No es data
productiva**: la fuente de verdad es la base, que se actualiza cada semana
(`benchmark-bancos actualizar`); estas muestras se regeneran solo cuando hace falta.

## `marts_ultimos_13_meses/` (versionada)

Regenerada el 2026-10-09. Antes se versionaban 5 años (~178 MB); se acotó a 13 meses
(~42 MB) porque alcanza para probar el modelo y comparar un mes contra el mismo mes del
año anterior.

- **Catálogos y `dim_fecha`**: completos, un archivo cada uno (`dim_entidad`,
  `dim_canton` con `codigo_inec`, `dim_provincia`, `dim_segmento_credito`,
  `dim_subsegmento_credito`, `dim_segmento_entidad`, `dim_categoria_deposito`,
  `dim_plazo`, `dim_cuenta_contable`, `dim_fecha`). Son chicos y los hechos necesitan el
  catálogo completo para resolver sus FK.
- **Hechos**: un archivo por tabla con **los últimos 13 meses con datos de esa tabla**.
  Cada fuente llega a un mes distinto, así que las ventanas no coinciden exactamente: al
  2026-10-09, saldos CAPCOL/SEPS hasta 2026-08, Boletín y tasas referenciales hasta
  2026-09, BCE semanal hasta la semana del 2026-09-24.

| Hecho | Filas |
|---|---|
| `fact_saldo_cartera` | 228.470 |
| `fact_saldo_depositos` | 149.228 |
| `fact_colocaciones_cartera` | 910.746 |
| `fact_captaciones_depositos` | 379.654 |
| `fact_balance` | 996.557 |
| `fact_pyg` | 229.509 |
| `fact_tasas_referenciales_*` (4) | 325 |

Nombres actuales (`sql/36`/`sql/37`): `dim_entidad`/`entidad_id` (antes `dim_banco`/
`banco_id`) y `codigo_inec` en la geografía. `scripts/compute_indicadores_excel.py` lee esta
carpeta por defecto (y todavía entiende los exportes viejos con `dim_banco`).

```powershell
uv run scripts/export_sample_parquet.py                       # regenera esta carpeta
uv run scripts/export_sample_parquet.py --meses-recientes 24  # otra ventana (no versionar)
```

## Otros exportes (no versionados)

- `--full` → `marts_full/`: todo el histórico, hechos particionados por año
  (`{tabla}_{anio}.parquet`) para no pasar el límite de 100 MB por archivo de GitHub.
- `--anio 2026 --mes 3` → `marts_2026-03/`: un mes puntual, con `dim_fecha` acotada a las
  fechas usadas.

Todos requieren Postgres cargado.

## Uso típico

```python
import pandas as pd
base = "data/samples/marts_ultimos_13_meses"
fact_saldo_cartera = pd.read_parquet(f"{base}/fact_saldo_cartera.parquet")
dim_entidad = pd.read_parquet(f"{base}/dim_entidad.parquet")
df = fact_saldo_cartera.merge(dim_entidad, on="entidad_id")
df = df[df.tipo_entidad == "COOPERATIVA"]  # las tablas mezclan tipos de entidad
```

Grano, tipos y relaciones de cada tabla: `docs/data_dictionary.md` y
`docs/architecture.md`. El Parquet es un espejo 1:1 de `marts.*`, sin transformación.
