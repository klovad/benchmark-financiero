# Benchmark de cartera y depósitos — bancos privados del Ecuador

Proyecto de analítica end-to-end (ingeniería de datos + BI) sobre los saldos de cartera
y depósitos de los bancos privados del Ecuador, con el fin de identificar oportunidades
de mercado (banco / producto / cantón) y proponer un monitoreo continuo. Fuente:
[portal CAPCOL de la Superintendencia de Bancos](https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/).

> Repositorio pensado para publicarse como `benchmark-depositos-cartera-bp`.

## Qué incluye

1. **ETL** (`etl/`): scraper con Playwright (el portal renderiza los archivos vía un
   plugin de OneDrive/SharePoint, no son links HTML estáticos) → parsers Python/pandas →
   carga idempotente a Postgres en 3 capas (`raw` → `staging` → `marts`, esquema estrella).
2. **Base de datos** (`sql/`): scripts para crear rol, base y esquemas, tanto en un
   Postgres local como vía `docker-compose.yml` (reproducible sin instalar nada).
3. **Power BI** (`powerbi/`): proyecto `.pbip` (formato texto, versionable en git) con el
   modelo semántico completo (relaciones, medidas DAX) conectado a `marts.*`.

Ver `docs/architecture.md` para el diseño completo (incluyendo la evaluación de
escalabilidad) y `docs/data_dictionary.md` para el detalle de cada tabla.

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

# 4. Pipeline completo (descarga + carga) para 2021-2025
.venv\Scripts\python -m etl.pipeline all --years 2021 2022 2023 2024 2025

# 5. Power BI: abrir powerbi/benchmark-cartera-depositos.pbip en Power BI Desktop
```

## Estructura

```
etl/                  extract (Playwright) / transform (parsers) / load (Postgres)
sql/                  DDL: roles, esquemas raw/staging/marts, vistas de sanity
docker-compose.yml    Postgres reproducible para quien clone el repo
powerbi/              proyecto .pbip (modelo semántico + reporte)
docs/                 arquitectura, diccionario de datos
tests/                pruebas de los parsers
data/raw/             archivos descargados (no versionado; se regenera con el ETL)
```

## Alcance de los datos

Bancos privados del Ecuador, 2021-01 a 2025-12 (mensual). Cartera por tipo de crédito
(comercial, consumo, inmobiliario, microcrédito, vivienda de interés público, educativo)
y estado (por vencer / no devenga intereses / vencida). Depósitos por tipo (monetarios,
ahorro, plazo por rango de días, garantía, restringidos, etc.). Ambos con desagregación
geográfica (cantón/provincia/región).

**Nota**: la fuente CAPCOL no reporta tasas de interés (verificado contra archivos reales
y la ficha metodológica de Superbancos); las columnas de tasa quedan reservadas y
nulas en v1 — ver `docs/architecture.md` para el detalle y cómo extenderlo.
