# Benchmark de cartera, depósitos y tasas — sistema financiero del Ecuador

Proyecto de analítica end-to-end (ingeniería de datos + BI) sobre cartera, depósitos,
tasas de interés y estados financieros del sistema financiero del Ecuador (bancos
privados y públicos, cooperativas de ahorro y crédito y mutualistas), con el fin de
identificar oportunidades de mercado (entidad / producto / cantón / tasa) y proponer un
monitoreo continuo. 5 fuentes integradas en un único esquema estrella conformado:

- [Portal CAPCOL](https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/) (Superbancos) — cartera y depósitos de bancos privados y de [Banca Pública](https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-instituciones-publicas/), mensual.
- [Tasas de interés del BCE](https://contenido.bce.fin.ec/documentos/Estadisticas/SectorMonFin/TasasInteres/) — tasas activas/pasivas por entidad (semanal) y techos/referenciales regulatorios (mensual).
- [Boletín Financiero Mensual](https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos/) (Superbancos) — balance y estado de resultados de bancos privados, mensual.
- [Estadísticas SEPS](https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/) — cartera, depósitos y estados financieros de cooperativas (S1-S3) y mutualistas, mensual.

> **Las tablas de hechos mezclan sectores.** Cualquier total, participación o ranking
> debe filtrar o agrupar por `dim_entidad.tipo_entidad`.

## Qué incluye

1. **ETL** (`src/benchmark_bancos/`): extractores por fuente (Playwright para los 2 portales de
   Superbancos que renderizan vía plugin OneDrive/SharePoint; descarga directa para BCE y
   SEPS, que publican archivos estáticos) → parsers Python/pandas → carga idempotente a Postgres en
   2 capas (`staging` → `marts`, esquema estrella) más un registro de ingesta (`meta`).
   Carga incremental en tres niveles: archivo (sha256), fila (CDC por columnas) y refresh
   de marts (marca de agua: solo recalcula lo que cambió).
2. **Base de datos** (`sql/`): scripts para crear rol, base, esquemas y las migraciones
   incrementales de cada fuente, tanto en un Postgres local como vía `docker-compose.yml`.
3. **Consumo**: `marts.*` queda listo para cualquier herramienta de BI. El proyecto
   Power BI (`.pbip`) se retiró del repo el 2026-10-09; está en el historial de git
   (commit anterior a esa fecha) si se quiere retomar.

Ver `docs/architecture.md` para el diseño completo (catálogos conformados, patrón de CDC,
diagrama ER, evaluación de escalabilidad, inventario de portabilidad de motor —
equivalentes en SQL Server y Databricks/Delta para cada construcción específica de
Postgres) y `docs/data_dictionary.md` para el detalle de
cada tabla. `docs/fuentes_datos.md` documenta la estructura real de cada fuente (no solo
la ficha metodológica) y `docs/metricas_financieras.md` el catálogo de indicadores del
Boletín. `docs/gobernanza_datos.md` amarra todo lo anterior bajo un marco de gobernanza
(responsable, clasificación, catálogo de metadatos por capa, reglas de calidad, huecos
conocidos) y `docs/linaje_datos.md` traza cada campo `archivo fuente → staging →
marts` con la transformación exacta aplicada. `docs/mantenimiento_catalogos.md` es el
runbook operativo para cuando falla un test/carga de matching de identidad (banco,
segmento, categoría, plazo, cuenta contable): qué excepción esperar, en qué archivo
arreglarlo y qué verificar después.

## Quickstart

Para llevarlo a otro servidor (Linux o Windows, con o sin Docker) u otro Postgres,
operarlo de forma incremental, correrlo por partes, programarlo y verificar cada corrida,
ver el runbook [`docs/despliegue_y_orquestacion.md`](docs/despliegue_y_orquestacion.md).
El orden de carga importa en una base nueva: `bce` **antes** que CAPCOL, porque Banca
Pública resuelve su identidad contra entidades que registra BCE (si ya se cargó en otro
orden, `uv run benchmark-bancos refresh --full` lo corrige). `actualizar` ya respeta ese
orden.

```powershell
# 1. Entorno Python con uv (https://docs.astral.sh/uv/): crea .venv, instala Python 3.12
#    si hace falta y las dependencias exactas de uv.lock (incluye el grupo dev: pytest,
#    ruff, black). Sin uv: `pip install -e .` en un venv propio.
uv sync
uv run playwright install chromium

# 2. Variables de entorno (leidas tanto por src/benchmark_bancos/config/ como por docker-compose.yml,
#    que autocarga este .env de la raiz -- crearlo ANTES del paso 3)
copy .env.example .env    # ajustar credenciales; POSTGRES_USER/POSTGRES_DB pueden tener cualquier nombre

# 3. Base de datos -- dos caminos:

# 3a. Docker (recomendado, reproducible): levanta Postgres 17, crea rol y base con los
#     nombres del .env y aplica todo sql/ via docker-entrypoint-initdb.d. El primer
#     `migrate` comprueba que la base esta al dia y registra esas migraciones solo:
docker compose up -d
uv run benchmark-bancos migrate

# 3b. Postgres local ya instalado: sql/00 (rol y base) como superusuario, con los nombres
#     del .env pasados con -v (o tomados de POSTGRES_USER/DB/PASSWORD del entorno con
#     psql >= 15), y el resto con `migrate` corrido como ese rol, que aplica en orden
#     solo lo pendiente y lo registra en meta.schema_migrations:
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U postgres -d postgres `
    -v app_user=bp_etl -v app_db=benchmark_cartera_depositos -v app_password=changeme `
    -f sql/00_roles_db.sql
uv run benchmark-bancos migrate

# En cualquier caso, para ver lo pendiente despues de un `git pull`:
uv run benchmark-bancos migrate --status
# Base instalada antes de 2026-10-09: una vez, aceptar las migraciones editadas ese dia
# (sql/01, 02, 03, 33, 34; sin efecto sobre una base existente):
uv run benchmark-bancos migrate --aceptar-cambios

# 4. Primera carga (en este orden)
uv run benchmark-bancos bce                                            # BCE tsp/tsa semanales
uv run benchmark-bancos tasas-historicas                               # techos/referenciales mensuales
uv run benchmark-bancos all --years 2021 2022 2023 2024 2025 2026      # CAPCOL (descarga + carga)
uv run benchmark-bancos boletin --years 2021 2022 2023 2024 2025 2026  # Boletín Financiero (balance/PyG)
uv run benchmark-bancos seps --years 2021 2022 2023 2024 2025 2026     # SEPS (cooperativas S1-S3 + mutualistas)

# 5. Operacion recurrente: todas las fuentes, incremental, año en curso. Codigos de
#    salida: 0 OK, 1 error, 2 termino con errores (ver log), 75 otra corrida en curso.
uv run benchmark-bancos actualizar
uv run benchmark-bancos actualizar --fuentes bce seps   # solo algunas

# 6. Programarla (Windows, semanal, lunes 07:30; en Linux/macOS: scripts/actualizar.sh + cron)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\registrar_tarea.ps1
```

## Estructura

```
main.py               punto de entrada: `uv run main.py <etapa>` (delega en benchmark_bancos.cli)
pyproject.toml        dependencias (uv), script `benchmark-bancos`, config de ruff/black/pytest
uv.lock               versiones exactas (reproducible en local y CI)
src/benchmark_bancos/
  cli.py              línea de comandos (`uv run benchmark-bancos <etapa>`)
  pipeline.py         orquestación por fuente: load_years, load_bce, load_boletin, load_seps...
  orquestacion.py     etapa `actualizar` (todas las fuentes), bloqueo contra corridas
                      simultáneas y códigos de salida
  migrate.py          etapa `migrate`: aplica sql/ pendientes y los registra en
                      meta.schema_migrations
  config/             settings.py (entorno/.env: rutas, DB, años), sources.py (URLs, ids de
                      descarga), domain.py (catálogos de vocabulario)
  extract/            scrape_superbancos.py, scrape_boletin.py (Playwright);
                      download_bce.py, download_tasas_historicas.py, download_seps.py (directa)
  transform/          parsers por fuente + *_matching.py (identidad de banco/categoría/
                      plazo/cantón, resuelta en Python antes de staging -- ver architecture.md)
  load/               load_postgres.py: COPY a staging con CDC por columnas + refresh
                      incremental de marts
  seeds/              banco_maestro.csv / banco_crosswalk.csv / canton_provincia.csv
sql/                  DDL: 00 (roles/DB, a mano o docker-compose) + 01-03 (esquemas) +
                      migraciones incrementales; `migrate` aplica 01..NN pendientes en orden
                      (docker-compose y CI aplican todo el directorio con psql)
docker-compose.yml    Postgres 17 reproducible: bootstrap completo del schema + credenciales
                      desde .env, sin pasos manuales
docs/                 arquitectura, diccionario de datos, fuentes, linaje, gobernanza, métricas
tests/                parsers, resolución de identidad y regresiones de CDC/refresh contra
                      Postgres real (ver "Tests y CI")
scripts/              actualizar.ps1 / actualizar.sh (corrida programada de `actualizar`),
                      registrar_tarea.ps1 (tarea semanal de Windows); utilidades:
                      compute_indicadores_excel.py (motor de referencia de indicadores),
                      export_sample_parquet.py (regenera data/samples)
data/raw/             archivos descargados: fuente de verdad (no versionado)
data/samples/         muestra de marts.* en Parquet (versionada) para probar sin Postgres
```

## Tests y CI

`tests/` tiene dos tiers, separados por marker de pytest (registrado en
`pyproject.toml`, `[tool.pytest.ini_options]`):

- **Unit** (default, sin marker): parsers, matching de identidad de banco/categoría/
  plazo/cantón (incluyendo `_weighted_agg()`/`_resolve_canton()` de
  `parse_bce_tasas.py` con `canton` en el grano, ver `sql/28_bce_canton_grain.sql`),
  `sha256_file()`, el parseo de fecha-desde-nombre-de-archivo
  (`src/benchmark_bancos/pipeline.py::parse_fecha_from_*_filename`) y los parsers de la
  SEPS con fixtures sintéticos que reproducen sus variaciones reales de formato
  (`tests/test_parse_seps.py`) -- puros, sin DB ni red.
- **Integration** (`@pytest.mark.integration`, fixture `db_conn` en
  `tests/conftest.py`): requieren Postgres real ya migrado hasta el último `sql/*.sql`
  (ver Quickstart). Cubren las regresiones de `sql/10`/`sql/23`/`sql/24` (unicidad
  NULL-safe), `sql/31` (cantones homónimos en la llave de staging), `sql/21` (invariante
  de grano del pivote de `fact_saldo_cartera`), el refresh incremental de marts (una fila
  nueva llega sin refresh completo y la marca de agua avanza, `sql/34`), un round-trip real de
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
uv run pytest -m "not integration"   # unit -- sin Postgres
uv run pytest -m integration          # integration -- Postgres real arriba
uv run pytest                          # ambos
```

CI (`.github/workflows/`): ambos workflows instalan con `uv sync --locked` (mismas
versiones que local, desde `uv.lock`). `lint.yml` corre `ruff`+`black --check` (sin DB, sin red).
`test.yml` corre `test-unit` (igual que arriba, sin servicios) y `test-integration`
(levanta un service container `postgres:17` y aplica `sql/*.sql` en orden lexicográfico
vía `psql` antes de correr `pytest -m integration` -- GitHub Actions no soporta el mount
de `docker-entrypoint-initdb.d` que usa `docker-compose.yml` en local, así que ese paso
queda explícito en el workflow). Ningún job de CI ejecuta los scrapers Playwright contra
los sitios reales -- deliberado, ver `docs/propuesta_escalabilidad_etl.md` sección 2.4.

## Alcance de los datos

- **CAPCOL** (cartera/depósitos): bancos privados, 2021-01 a 2026-08, mensual; banca
  pública (BanEcuador, CFN, BdE), 2021-01 a 2026-08 (actualizado 2026-10-09). Cartera por
  tipo de crédito (comercial, consumo, inmobiliario, microcrédito, vivienda de interés
  público, educativo) y estado (por vencer / no devenga intereses / vencida). Depósitos
  por categoría (monetarios, ahorro, plazo por rango de días, garantía, restringidos,
  etc.). Ambos con desagregación geográfica (cantón/provincia/región). **No trae tasa de
  interés** (verificado contra archivos reales) — de ahí la fuente BCE.
- **BCE tsp/tsa** (tasas semanales por entidad): histórico completo 2008-01 a la fecha,
  **sistema financiero completo**. `dim_entidad` tiene 444 entidades (2026-10-05): 36 con
  identidad curada (33 bancos privados + 3 públicos) y 408 auto-registradas por RUC
  (cooperativas, mutualistas, otros bancos públicos, sociedades financieras, tarjetas de
  crédito y 2 entidades de segundo piso). Ver `docs/gobernanza_datos.md`. Activas
  por segmento de crédito (26 valores), pasivas por categoría de depósito, ambas por
  plazo y cantón (2026-09-01: grano cambiado de provincia a cantón,
  `sql/28_bce_canton_grain.sql` + reproceso del histórico completo, ver
  `src/benchmark_bancos/transform/parse_bce_tasas.py`/`src/benchmark_bancos/transform/canton_matching.py`) —
  provincia/región siguen disponibles vía `dim_canton.provincia_id → dim_provincia`.
  `fact_captaciones_depositos`: 3.157.101 filas; `fact_colocaciones_cartera`: 7.961.790
  filas, hasta la semana del 2026-09-24 (actualizado 2026-10-09; 0 `canton_id` NULL en
  ambas). La etapa `bce` descarga de forma condicional: solo baja el archivo cuando el BCE
  publica una versión nueva.
- **BCE `TasasHistorico.htm`** (techos y referenciales, nivel sistema): **2009-07 a
  2026-09** (206 meses; ampliado el 2026-10-09 desde 2022-04). Antes de 2009-07 la página
  usa segmentos que ya no existen en el catálogo; 2009-09 se omite (formato irregular). Tasas activas máximas/referenciales por segmento, pasivas por instrumento y
  plazo, TPR/TAR/Tasa Legal/Tasa Máxima Convencional.
- **Boletín Financiero Mensual** (balance/PyG de bancos privados): 2021-01 a 2026-09. Plan de
  cuentas jerárquico completo (Catálogo Único de Cuentas), valores en USD (fuente reporta
  en miles, normalizado al cargar).
- **SEPS** (cooperativas de ahorro y crédito S1-S3 y mutualistas, 2021-01 a 2026-08,
  mensual): saldos de cartera por estado y de depósitos por categoría, por entidad y
  cantón, en las mismas tablas que CAPCOL; y estados financieros por entidad en
  `fact_balance`/`fact_pyg`, para validar esos saldos contra las cuentas contables.
  Segmentos 4-5 fuera de alcance (reportan trimestral). Ver `docs/fuentes_datos.md`
  sección 4.0. Dos diferencias de criterio documentadas: la cartera de las mutualistas
  incluye vivienda VIS/VIP vendida al fideicomiso y administrada (+34% a +45% sobre su
  balance), y el consumo de las cooperativas emisoras de tarjetas excluye las tarjetas.

## Estado del proyecto

- ✅ **Datos al día y TasasHistorico desde 2009** (2026-10-09/10): todas las fuentes
  cargadas hasta lo último publicado (CAPCOL privados y Banca Pública hasta 2026-08,
  SEPS 2026 hasta 2026-08, Boletín y TasasHistorico hasta 2026-09, BCE semanal hasta
  2026-09-24). TasasHistorico ampliado a 2009-07 (antes 2022-04): el parser leía mal el
  punto decimal y no reconocía la sección "VIGENTES"; 2022-04 a 2022-07 se habían cargado
  sin tasas de cartera y se reprocesaron. Antes de 2009-07 queda fuera por decisión (otros
  segmentos, valor bajo).
- ✅ **Reintentos** (2026-10-09): descargas con reintento ante cortes de red/timeouts
  (`extract/red.py`) y una fuente fallida se reintenta una vez al final de `actualizar`.
- ✅ **Repositorio liviano** (2026-10-10): muestras Parquet reducidas a 13 meses
  (`data/samples/marts_ultimos_13_meses`, ~42 MB) y el historial de git reescrito para
  quitar las muestras viejas (de ~890 MB a ~29 MB). Los hashes de los commits cambiaron:
  una copia clonada antes de esa fecha hay que volver a clonarla.

- ✅ **Operación desatendida** (2026-10-09): etapa `migrate` con registro de migraciones
  aplicadas (`meta.schema_migrations`, `sql/38`; `--status`, `--baseline`), etapa
  `actualizar` que recoge lo nuevo de las 5 fuentes con cada fuente aislada, bloqueo en
  Postgres contra corridas simultáneas, códigos de salida 0/1/2/75 y `--log-file`.
  Programación semanal con `scripts/registrar_tarea.ps1` (Windows) o
  `scripts/actualizar.sh` + cron. Ver `docs/despliegue_y_orquestacion.md` §3 y §7.
- ✅ **Portabilidad de servidor** (2026-10-09): rol y base configurables (`sql/00` toma
  los nombres de `-v` o del `.env`; las migraciones ya no fijan `bp_etl`, los esquemas
  quedan a nombre de quien migra, y CI lo verifica con otro rol); `dim_fecha.nombre_mes`
  en español sin depender del idioma del servidor (`sql/40`); `migrate` ubica una base
  sin registro con sondas por migración (baseline automático en docker-compose/CI,
  `--baseline` parcial en bases atrasadas) y `--aceptar-cambios` para migraciones
  editadas a propósito. Ver `docs/despliegue_y_orquestacion.md` §2.5 y §3.

- ✅ **Control de conciliación automático** (2026-10-09): `sql/39` + `benchmark-bancos
  conciliar`, que también corre al final de cada `actualizar`. Compara los saldos por
  cantón (sumados por entidad) contra la contabilidad (cartera `14 − 1499`, depósitos `21`)
  con umbrales por tipo de entidad; un mes que no cuadra deja la corrida con código 2.
  Histórico 2021-2026: todo dentro de umbral.
- ✅ **Geografía con códigos INEC y `dim_entidad`** (2026-10-09): cantón y provincia
  llevan el código oficial del INEC (los 221 cantones vigentes), cada cantón real es una
  sola fila con su provincia vigente (2 duplicados por escritura y 5 pares con provincia
  anterior fusionados, totales nacionales sin cambio), y `marts.dim_banco` pasó a
  llamarse `marts.dim_entidad` (`entidad_id`). Ver `docs/data_dictionary.md`.
- ✅ **Segmento de entidad homologado** (2026-10-10, `sql/41`): las mutualistas quedan en
  un solo valor (`SEGMENTO 1 MUTUALISTA`; el BCE las rotula `MUTUALISTAS` desde 2025) y
  las entidades que no reportan al BCE (segundo piso) en `NO REPORTA AL BCE`; la columna
  ya no admite nulos en `dim_entidad` ni en los hechos BCE.

- ✅ ETL de las 5 fuentes completo y verificado (conteos `staging` = `marts` exactos, CDC
  sin updates espurios en una segunda corrida, ver `docs/data_dictionary.md` y
  `docs/architecture.md`).
- ✅ **Banca Pública y SEPS cargadas** (2026-09-30 / 2026-10-01): saldos conciliados
  contra estados financieros por entidad y mes (depósitos mediana 0,00%; cartera mediana
  0,00%, con las 4 excepciones explicadas en `docs/fuentes_datos.md` §4.0).
- ✅ **Mejoras de ingeniería** (2026-10-05): proyecto empaquetado con uv (`src/`,
  `pyproject.toml`, `uv.lock`, `main.py`), capa `raw` JSONB eliminada (la base pasó de
  22 GB a ~9,4 GB), CDC por columnas sin `row_hash` y refresh de marts incremental (196 s
  → 0,03 s sin cambios). Ver `docs/architecture.md`, "Carga incremental".
- 🗑️ **Power BI retirado del repo** (2026-10-09): el `.pbip` cubría solo los saldos de
  CAPCOL y no filtraba por tipo de entidad. Recuperable desde el historial de git.
- ✅ **`fact_saldo_cartera.estado_cartera` pivotado a columnas** (2026-07-25): era una
  dimensión degenerada (3 filas por combinación real, antipatrón EAV) — ahora
  `saldo_por_vencer`/`saldo_no_devenga_intereses`/`saldo_vencida` + `saldo_total`
  (columna `GENERATED`), mismo criterio que ya usaba `fact_tasas_referenciales_cartera`.
  Ver `docs/data_dictionary.md`.
- ⏳ `RK`/`INDICADORES` del Boletín están documentados (`docs/metricas_financieras.md`)
  pero no cargados como tabla — son ratios recalculables desde `fact_balance`/`fact_pyg`.

### Pendientes (opcionales, 2026-10-10)

1. Aviso activo cuando falla la corrida semanal (hoy: revisar `logs/` o `LastTaskResult`
   en el Programador de tareas; 0 = OK, 2 = revisar log).
2. La tarea programada de Windows corre solo con la sesión iniciada (correrla sin sesión
   requiere guardar la contraseña en Windows).
3. SEPS segmentos 4 y 5 (reporte trimestral con otro diseño).
4. `RK`/`INDICADORES` del Boletín como tablas.
5. Probar contra un Postgres gestionado real (verificado con simulación).
6. Power BI: retirado del repo y en espera; la base ya está lista (`dim_entidad` +
   `tipo_entidad`, `codigo_inec`, vistas de indicadores y conciliación, muestra Parquet).

Fuera de alcance por decisión: TasasHistorico antes de 2009-07.
