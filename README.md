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
diagrama ER, evaluación de escalabilidad, inventario de portabilidad de motor —
equivalentes en SQL Server y Databricks/Delta para cada construcción específica de
Postgres) y `docs/data_dictionary.md` para el detalle de
cada tabla. `docs/fuentes_datos.md` documenta la estructura real de cada fuente (no solo
la ficha metodológica) y `docs/metricas_financieras.md` el catálogo de indicadores del
Boletín. `docs/gobernanza_datos.md` amarra todo lo anterior bajo un marco de gobernanza
(responsable, clasificación, catálogo de metadatos por capa, reglas de calidad, huecos
conocidos) y `docs/linaje_datos.md` traza cada campo `archivo fuente → raw → staging →
marts` con la transformación exacta aplicada. `docs/mantenimiento_catalogos.md` es el
runbook operativo para cuando falla un test/carga de matching de identidad (banco,
segmento, categoría, plazo, cuenta contable): qué excepción esperar, en qué archivo
arreglarlo y qué verificar después.

## Quickstart

```powershell
# 1. Entorno Python
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium

# 2. Variables de entorno (leidas tanto por etl/config.py como por docker-compose.yml,
#    que autocarga este .env de la raiz -- crearlo ANTES del paso 3)
copy .env.example .env    # ajustar credenciales si no usaste las de ejemplo

# 3. Base de datos -- dos caminos:

# 3a. Docker (recomendado, reproducible): levanta Postgres 17 y aplica TODAS las
#     migraciones (sql/00_roles_db.sql ... la ultima en sql/, en orden lexicografico)
#     automaticamente via docker-entrypoint-initdb.d, con credenciales tomadas del
#     .env del paso 2. No hace falta ningun psql manual.
docker compose up -d

# 3b. Postgres local ya instalado (alternativa a 3a): aplicar cada sql/*.sql a mano,
#     en orden, empezando por 00 (conectado como superusuario) y luego 01, 02, 03...
#     hasta la ultima migracion existente en sql/:
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U postgres -d postgres -f sql/00_roles_db.sql
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/01_schema_raw.sql
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/02_schema_staging.sql
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/03_schema_marts.sql
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U bp_etl -d benchmark_cartera_depositos -f sql/04_indexes_views.sql
# ... 05 a la ultima, en orden (ver sql/*.sql) ...

# 4. Pipeline CAPCOL (descarga + carga) para 2021-2025
.venv\Scripts\python -m etl.pipeline all --years 2021 2022 2023 2024 2025

# 5. BCE (tasas semanales tsp/tsa + techos/referenciales TasasHistorico.htm)
.venv\Scripts\python -m etl.pipeline bce
.venv\Scripts\python -m etl.pipeline tasas-historicas

# 6. Boletín Financiero Mensual (balance/PyG)
.venv\Scripts\python -m etl.pipeline boletin --years 2021 2022 2023 2024 2025 2026

# 6b. Operaciones Especiales (Banco de Guayaquil): requiere copiar primero el xlsx a data/raw
#     (ver docs/fuentes_datos.md, sección "Operaciones Especiales")
.venv\Scripts\python -m etl.pipeline operaciones-especiales

# 7. Power BI: abrir powerbi/benchmark-cartera-depositos.pbip en Power BI Desktop
```

## Estructura

```
etl/
  extract/            scrape_superbancos.py, scrape_boletin.py (Playwright);
                       download_bce.py, download_tasas_historicas.py (descarga directa)
  transform/           parsers por fuente + *_matching.py (identidad de banco/categoría/
                       plazo, resuelta en Python antes de staging -- ver architecture.md)
  load/                load_postgres.py: raw -> staging -> marts, upserts con CDC
  seeds/                banco_maestro.csv / banco_crosswalk.csv / canton_provincia.csv
                       (catálogos sembrados)
sql/                  DDL: 00 (roles/DB) + 01-03 (raw/staging/marts) + migraciones
                       incrementales 04+ (dim_banco/dim_fecha rework, catálogos
                       conformados, BCE, Boletín -- ver sql/*.sql); todo el directorio
                       se monta en el contenedor y se aplica en orden automáticamente
docker-compose.yml    Postgres 17 reproducible: bootstrap completo del schema (todo
                       sql/*.sql) + credenciales desde .env, sin pasos manuales
powerbi/              proyecto .pbip (modelo semántico + reporte) -- cubre CAPCOL v1
docs/                 arquitectura, diccionario de datos, catálogo de fuentes, métricas
tests/                pruebas de los parsers, módulos de resolución de identidad y
                       regresiones de CDC/idempotencia contra Postgres real (ver
                       "Tests y CI" abajo)
data/raw/             archivos descargados (no versionado; se regenera con el ETL)
data/samples/          muestra de marts.* en Parquet (versionada) para probar sin Postgres
                       cargado -- ver data/samples/README.md
```

## Tests y CI

`tests/` tiene dos tiers, separados por marker de pytest (registrado en
`pyproject.toml`, `[tool.pytest.ini_options]`):

- **Unit** (default, sin marker): parsers, matching de identidad de banco/categoría/
  plazo/cantón (incluyendo `_weighted_agg()`/`_resolve_canton()` de
  `parse_bce_tasas.py` con `canton` en el grano, ver `sql/28_bce_canton_grain.sql`),
  `sha256_file()` y el parseo de fecha-desde-nombre-de-archivo
  (`etl/pipeline.py::parse_fecha_from_*_filename`) -- puros, sin DB ni red.
- **Integration** (`@pytest.mark.integration`, fixture `db_conn` en
  `tests/conftest.py`): requieren Postgres real ya migrado hasta el último `sql/*.sql`
  (ver Quickstart). Cubren las regresiones de `sql/10`/`sql/23`/`sql/24` (unicidad
  NULL-safe) y `sql/21` (invariante de grano del pivote de `fact_saldo_cartera`), un round-trip real de
  `upsert_staging_cartera()`/`register_source_file()`/`is_source_loaded()` verificando
  el contrato de CDC (una segunda carga idéntica no dispara ningún `UPDATE`), el
  auto-ingreso two-tier de `marts.dim_canton` de punta a punta (un cantón fuera del
  universo sembrado pero con provincia válida termina `AUTO_INGRESADO`, no rechazado --
  ver `resolver_canton_bce()`), y la mecánica COPY/tabla-temporal de
  `_upsert_bce_via_temp()`/`_upsert_boletin_via_temp()`
  (vía `upsert_staging_bce_tasas_pasivas()`/`upsert_staging_boletin_balance()`): conteo
  de filas, CDC no-op, UPDATE real, y verificación contra `pg_tables` de que la tabla
  temporal existe (`pg_temp_N`) antes de un `commit()` y desaparece después (promesa de
  `ON COMMIT DROP`). La mayoría de estos tests nunca hacen `commit` -- `db_conn` siempre
  hace `rollback` al terminar, sin dejar residuos --, salvo los de tabla temporal: como
  `ON COMMIT DROP` solo dispara en un `commit` real, esos pocos sí comitean entre
  llamadas y se limpian ellos mismos con `DELETE` + `commit()` en un `finally` (**cuidado
  real, encontrado durante esta migración**: el helper de limpieza que usan esos tests,
  `_cleanup_bce_tasas_pasivas()`, hace su propio `commit()` -- si un test nuevo lo
  reutiliza sin necesitar realmente un `commit()` intermedio, comitea de paso cualquier
  otro cambio hecho antes en la misma transacción, dejando residuo real en la base pese
  a que `db_conn` en teoría siempre hace rollback; los tests que no necesitan probar
  `ON COMMIT DROP` no deben llamar a ese helper).

```powershell
.venv\Scripts\python -m pytest -m "not integration"   # unit -- sin Postgres
.venv\Scripts\python -m pytest -m integration          # integration -- Postgres real arriba
.venv\Scripts\python -m pytest                          # ambos
```

CI (`.github/workflows/`): `lint.yml` corre `ruff`+`black --check` (sin DB, sin red).
`test.yml` corre `test-unit` (igual que arriba, sin servicios) y `test-integration`
(levanta un service container `postgres:17` y aplica `sql/*.sql` en orden lexicográfico
vía `psql` antes de correr `pytest -m integration` -- GitHub Actions no soporta el mount
de `docker-entrypoint-initdb.d` que usa `docker-compose.yml` en local, así que ese paso
queda explícito en el workflow). Ningún job de CI ejecuta los scrapers Playwright contra
los sitios reales -- deliberado, ver `docs/propuesta_escalabilidad_etl.md` sección 2.4.

## Alcance de los datos

- **CAPCOL** (cartera/depósitos): bancos privados, 2021-01 a 2026-06, mensual. Cartera por
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
  plazo y cantón (2026-09-01: grano cambiado de provincia a cantón,
  `sql/28_bce_canton_grain.sql` + reproceso del histórico completo, ver
  `etl/transform/parse_bce_tasas.py`/`etl/transform/canton_matching.py`) —
  provincia/región siguen disponibles vía `dim_canton.provincia_id → dim_provincia`.
  `fact_captaciones_depositos`: 3.077.474 filas; `fact_colocaciones_cartera`: 7.756.581
  filas (0 `canton_id` NULL en ambas, verificado tras el reproceso —
  `python -m etl.pipeline bce-reprocess-canton-grain`, backfill de un solo uso para esta
  migración, no forma parte del flujo semanal normal de `python -m etl.pipeline bce`).
- **BCE `TasasHistorico.htm`** (techos y referenciales, nivel sistema): 2022-04 a
  2026-06 (páginas anteriores usan un layout HTML distinto, no soportado por el parser
  actual). Tasas activas máximas/referenciales por segmento, pasivas por instrumento y
  plazo, TPR/TAR/Tasa Legal/Tasa Máxima Convencional.
- **Operaciones Especiales (Banco de Guayaquil)**: xlsx descargado manualmente a
  `data/raw/operaciones_especiales.xlsx` (SharePoint interno), misma estructura que BCE
  tsa pero marcado `es_operacion_especial='SI'`; se integra al mismo grano de
  `marts.fact_colocaciones_cartera`. Íntegrado 2026-09-02 — ver `docs/fuentes_datos.md`.
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
- 🧪 **Prototipo de diseño Power BI — tema "Libro Mayor"** (2026-08-27, segunda versión):
  `powerbi/prototipo-diseno-bi.*` — un `.pbip` **separado** del reporte productivo (para
  no tocar sus 5 páginas ni sus 17 medidas; un tema personalizado se registra a nivel de
  todo el reporte en PBIR, así que no se podía añadir sin re-pintar lo existente). Es una
  **plantilla/punto de partida, no un build-out de negocio**. La primera versión del tema
  fue rechazada por leer como el tema base de Power BI (paleta Okabe–Ito literal sobre
  blanco, Segoe UI en las 8 clases, slicers de lista sin estilo propio); esta versión parte
  de un concepto anclado en el dominio (bóveda/terminal de mercado bancario: lienzo oscuro,
  acento bronce único, cifras en Consolas monoespaciada) con la categórica de 8 bancos
  **validada computacionalmente** (CVD + contraste, no a mano) y los 3 controles de
  personalización (selector de métrica, comparador de periodo CY/PY, ventana móvil de
  tendencia) con estados reales (orientación horizontal, selección única forzada — corrige
  además un bug real: sin `strictSingleSelect` las medidas `SELECTEDVALUE(...)` podían caer
  en `BLANK()`). Ver `docs/prototipo_diseno_powerbi.md` para la paleta, la tipografía, el
  detalle de cada control, las divergencias explícitas entre la maqueta y el render real de
  Desktop, y cómo exportar un `.pbit` real desde Desktop.
