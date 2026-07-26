# Benchmark de cartera, depósitos y tasas — bancos privados del Ecuador

Proyecto de analítica end-to-end (ingeniería de datos + BI) sobre cartera, depósitos,
tasas de interés y estados financieros de los bancos privados del Ecuador, con el fin de
identificar oportunidades de mercado (banco / producto / cantón / tasa) y proponer un
monitoreo continuo. 4 fuentes integradas en un único esquema estrella conformado:

- [Portal CAPCOL](https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/) (Superbancos) — cartera y depósitos, mensual.
- [Tasas de interés del BCE](https://contenido.bce.fin.ec/documentos/Estadisticas/SectorMonFin/TasasInteres/) — tasas activas/pasivas por banco (semanal) y techos/referenciales regulatorios (mensual).
- [Boletín Financiero Mensual](https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos/) (Superbancos) — balance y estado de resultados por banco, mensual.

> Repositorio pensado para publicarse como `benchmark-depositos-cartera-bp`.

## Qué incluye

1. **ETL** (`etl/`): extractores por fuente (Playwright para los 2 portales de
   Superbancos que renderizan vía plugin OneDrive/SharePoint; descarga directa para BCE,
   que sí es HTML/CSV estático) → parsers Python/pandas → carga idempotente a Postgres en
   3 capas (`raw` → `staging` → `marts`, esquema estrella), con carga incremental por hash
   (CDC) en vez de full refresh.
2. **Base de datos** (`sql/`): scripts para crear rol, base, esquemas y las migraciones
   incrementales de cada fuente, tanto en un Postgres local como vía `docker-compose.yml`.
3. **Power BI** (`powerbi/`): proyecto `.pbip` (formato texto, versionable en git) con el
   modelo semántico conectado a `marts.*` — **cubre el esquema original de CAPCOL**; las
   tablas de BCE/Boletín añadidas después aún no están incorporadas al modelo semántico
   (ver "Estado del proyecto" abajo).

Ver `docs/architecture.md` para el diseño completo (catálogos conformados, patrón de CDC,
diagrama ER, evaluación de escalabilidad) y `docs/data_dictionary.md` para el detalle de
cada tabla. `docs/fuentes_datos.md` documenta la estructura real de cada fuente (no solo
la ficha metodológica) y `docs/metricas_financieras.md` el catálogo de indicadores del
Boletín. `docs/gobernanza_datos.md` amarra todo lo anterior bajo un marco de gobernanza
(responsable, clasificación, catálogo de metadatos por capa, reglas de calidad, huecos
conocidos) y `docs/linaje_datos.md` traza cada campo `archivo fuente → raw → staging →
marts` con la transformación exacta aplicada.

## Quickstart

```powershell
# 1. Entorno Python
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium

# 2. Base de datos (local, con Postgres ya instalado)
#    o alternativamente: docker compose up -d
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U postgres -d postgres -f sql/00_roles_db.sql
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/01_schema_raw.sql
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/02_schema_staging.sql
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/03_schema_marts.sql
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/04_indexes_views.sql

# 3. Variables de entorno
copy .env.example .env    # ajustar credenciales si no usaste las de ejemplo

# 4. Migraciones incrementales (además de 00-04, agregadas al expandir a BCE/Boletín)
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/05_dim_banco_rework.sql
# ... 06 a 13, en orden (ver sql/*.sql) ...

# 5. Pipeline CAPCOL (descarga + carga) para 2021-2025
.venv\Scripts\python -m etl.pipeline all --years 2021 2022 2023 2024 2025

# 6. BCE (tasas semanales tsp/tsa + techos/referenciales TasasHistorico.htm)
.venv\Scripts\python -m etl.pipeline bce
.venv\Scripts\python -m etl.pipeline tasas-historicas

# 7. Boletín Financiero Mensual (balance/PyG)
.venv\Scripts\python -m etl.pipeline boletin --years 2021 2022 2023 2024 2025 2026

# 8. Power BI: abrir powerbi/benchmark-cartera-depositos.pbip en Power BI Desktop
```

## Estructura

```
etl/
  extract/            scrape_superbancos.py, scrape_boletin.py (Playwright);
                       download_bce.py, download_tasas_historicas.py (descarga directa)
  transform/           parsers por fuente + *_matching.py (identidad de banco/categoría/
                       plazo, resuelta en Python antes de staging -- ver architecture.md)
  load/                load_postgres.py: raw -> staging -> marts, upserts con CDC
  seeds/                banco_maestro.csv / banco_crosswalk.csv (catálogos sembrados)
sql/                  DDL: roles, esquemas raw/staging/marts + migraciones 05-13
                       (dim_banco/dim_fecha rework, catálogos conformados, BCE, Boletín)
docker-compose.yml    Postgres reproducible para quien clone el repo
powerbi/              proyecto .pbip (modelo semántico + reporte) -- cubre CAPCOL v1
docs/                 arquitectura, diccionario de datos, catálogo de fuentes, métricas
tests/                pruebas de los parsers y módulos de resolución de identidad
data/raw/             archivos descargados (no versionado; se regenera con el ETL)
data/samples/          muestra de marts.* en Parquet (versionada) para probar sin Postgres
                       cargado -- ver data/samples/README.md
```

## Alcance de los datos

- **CAPCOL** (cartera/depósitos): bancos privados, 2021-01 a 2025-12, mensual. Cartera por
  tipo de crédito (comercial, consumo, inmobiliario, microcrédito, vivienda de interés
  público, educativo) y estado (por vencer / no devenga intereses / vencida). Depósitos
  por categoría (monetarios, ahorro, plazo por rango de días, garantía, restringidos,
  etc.). Ambos con desagregación geográfica (cantón/provincia/región). **No trae tasa de
  interés** (verificado contra archivos reales) — de ahí la fuente BCE.
- **BCE tsp/tsa** (tasas semanales por entidad): histórico completo 2008-01 a la fecha,
  **sistema financiero completo** (442 entidades en `dim_banco`: 33 bancos privados con
  identidad curada + 409 bancos públicos/cooperativas/mutualistas/sociedad financiera/
  tarjetas de crédito auto-registrados por RUC — ver `docs/gobernanza_datos.md`). Activas
  por segmento de crédito (26 valores), pasivas por categoría de depósito, ambas por
  plazo y provincia.
- **BCE `TasasHistorico.htm`** (techos y referenciales, nivel sistema): 2022-04 a
  2026-06 (páginas anteriores usan un layout HTML distinto, no soportado por el parser
  actual). Tasas activas máximas/referenciales por segmento, pasivas por instrumento y
  plazo, TPR/TAR/Tasa Legal/Tasa Máxima Convencional.
- **Boletín Financiero Mensual** (balance/PyG por banco): 2021-01 a 2026-06. Plan de
  cuentas jerárquico completo (Catálogo Único de Cuentas), valores en USD (fuente reporta
  en miles, normalizado al cargar).

## Estado del proyecto

- ✅ ETL de las 4 fuentes completo y verificado (conteos `staging` = `marts` exactos, CDC
  sin updates espurios en una segunda corrida, ver `docs/data_dictionary.md` y
  `docs/architecture.md`).
- ✅ **Power BI (`.pbip`) realineado con el esquema actual de CAPCOL** (2026-07-23,
  actualizado 2026-07-25): `fact_cartera`/`fact_depositos` → `fact_saldo_cartera`/
  `fact_saldo_depositos`, `dim_producto_cartera`/`dim_producto_deposito` →
  `dim_segmento_credito` + `dim_categoria_deposito`/`dim_plazo`, `dim_provincia` agregada
  (2 visuales dependían de `dim_canton[provincia]`), medidas de morosidad/cartera vencida
  actualizadas al pivote de `estado_cartera` (ver abajo). Sigue cubriendo **solo CAPCOL**
  — incorporar las tablas de BCE/Boletín (11 tablas más) es un trabajo aparte, no hecho
  todavía.
- ✅ **`fact_saldo_cartera.estado_cartera` pivotado a columnas** (2026-07-25): era una
  dimensión degenerada (3 filas por combinación real, antipatrón EAV) — ahora
  `saldo_por_vencer`/`saldo_no_devenga_intereses`/`saldo_vencida` + `saldo_total`
  (columna `GENERATED`), mismo criterio que ya usaba `fact_tasas_referenciales_cartera`.
  Ver `docs/data_dictionary.md`.
- ⏳ `RK`/`INDICADORES` del Boletín están documentados (`docs/metricas_financieras.md`)
  pero no cargados como tabla — son ratios recalculables desde `fact_balance`/`fact_pyg`.
