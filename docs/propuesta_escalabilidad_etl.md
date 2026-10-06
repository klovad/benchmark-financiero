> **Estado: propuesta, no aplicada.** Generada por una pasada del agente
> `data-engineer` (2026-08-22), a petición explícita: "prepara primero la
> propuesta de estructura y lógica en markdown, sin código, después la
> analizamos" — este documento no modifica `src/benchmark_bancos/`, `sql/`, `docker-compose.yml`
> ni ningún otro archivo del proyecto. Construye sobre los hallazgos ya
> routeados por el review de arquitectura (`data-architect`, mismo día) sin
> volver a levantarlos desde cero — ver ese review para el gap analysis
> completo de portabilidad de motor, gobernanza y calidad de datos. Reconciliada
> contra ese review: sin conflictos de carril bloqueantes; una única precisión
> de secuenciación (los tests de regresión de la sección 2.2 conviene
> aplicarlos después del fix de mount de migraciones de Docker, no antes,
> porque ese fix es lo que le da a CI un schema completo contra el cual
> correr esos tests) y un hallazgo nuevo a incorporar en la próxima
> actualización de `docs/gobernanza_datos.md` (el conteo de tests que cita
> ("33") quedó desactualizado — el conteo real hoy es 37).

# Propuesta: escalabilidad de ETL, reglas de QA, alineación de config y `black`+`ruff`

**Alcance de este documento**: propuesta de estructura y lógica, sin código. Basado en lectura directa del repo (`src/benchmark_bancos/`, `sql/`, `docker-compose.yml`, `requirements.txt`, `docs/`) — cifras y rutas verificadas, no genéricas. Construye sobre los hallazgos ya routeados por el review de `data-architect` (mount de migraciones en Docker, contenedor del runner ETL, tests de regresión, cobertura de orquestación, guard de migraciones) sin volver a levantarlos desde cero.

---

## 0. Línea base verificada (para que la propuesta no asuma de más)

| Área | Estado real hoy |
|---|---|
| Orquestación | `src/benchmark_bancos/pipeline.py`, 252 líneas, un solo `argparse` CLI (`extract\|load\|all\|bce\|tasas-historicas\|boletin`), 4 funciones de stage casi idénticas en forma (`load_years` L55-84, `load_bce` L87-128, `load_tasas_historicas` L134-170, `load_boletin` L180-229), secuencial, sin scheduler |
| Reintentos | **Cero** en las llamadas de red directas (`urllib.request.urlopen` en `src/benchmark_bancos/extract/download_bce.py:30` y `src/benchmark_bancos/extract/download_tasas_historicas.py:47`); Playwright solo reintenta *localización de un elemento en el DOM* (`_open_year_folder`, 3 intentos, `src/benchmark_bancos/extract/scrape_superbancos.py:37-47` y `scrape_boletin.py:31-41`), no fallos de red/timeout de navegación |
| Logging | `logging.basicConfig(...)` duplicado en **4 archivos** (`pipeline.py:49`, `scrape_superbancos.py:20`, `scrape_boletin.py:20`, y bajo `__main__` en `download_bce.py`/`download_tasas_historicas.py`) — mismo formato, hoy no rompe nada porque coinciden, pero es 4 fuentes de verdad para una sola cosa; sin `run_id`/correlación por corrida |
| Manejo de fallos parciales | `load_tasas_historicas` (`pipeline.py:151-159`) y `load_boletin` (`pipeline.py:208-215`) capturan `ValueError/KeyError/IndexError` por archivo y **continúan** con `log.warning` — si *todos* los archivos de una corrida fallan al parsear, la corrida igual termina con exit code 0, `refresh_marts()` corre, no hay señal de fallo total |
| Config declarativa | No existe. `src/benchmark_bancos/config/` (66 líneas) mezcla config de infraestructura (`DB_CONFIG`, `BCE_URLS`) con mapeos de negocio (`FOLDER_NAMES`, `TIPO_CREDITO_KEYWORDS`, `PROVINCIA_REGION`) como dicts Python |
| Dependencias | `requirements.txt`: 8 paquetes, todos con `>=` sin cota superior, sin `pyproject.toml`, sin lockfile |
| Contenerización | Solo Postgres (`docker-compose.yml`, 1 servicio); runner Python/Playwright depende de venv local |
| Lint/format | No existe `pyproject.toml`, `.flake8`, `setup.cfg`, `.pre-commit-config.yaml` ni CI (`.github/` no existe) |
| Tests | 37 tests en `tests/*.py` (verificado con grep `^def test_`, no los 33 que cita `docs/gobernanza_datos.md` §7 — el doc quedó desactualizado tras agregar `test_parse_boletin.py`/`test_parse_tasas_historicas.py`), 0 ejecutados en CI porque no hay CI |
| Cobertura de orquestación | Confirmado con `graphify god-nodes`: `load_bce()` (17 edges), `load_boletin()` (15), `load_years()` (13), `sha256_file()` (16) — **0 conexiones a archivos de test**, a diferencia de `resolver_banco_codigo()` (23 edges, cubierto por 11 tests en `tests/test_banco_matching.py`) |
| `src/benchmark_bancos/load/load_postgres.py` | 704 líneas, mecánica COPY/upsert (`_copy_rows`, `_upsert_bce_via_temp`, `_upsert_boletin_via_temp`) — **cerrado** (2026-08-29): 6 tests de integración en `tests/test_integration_regressions.py` cubren `_upsert_bce_via_temp()` vía `upsert_staging_bce_tasas_pasivas()` y `_upsert_boletin_via_temp()` vía `upsert_staging_boletin_balance()` (conteo de filas, CDC no-op, UPDATE real, y verificación positiva contra `pg_tables` de la promesa `ON COMMIT DROP`) — ver detalle en sección 2.3 |
| Python fuera de `src/benchmark_bancos/` | `scripts/compute_indicadores_excel.py` — también entraría al scope de lint |

---

## 1. Escalabilidad del pipeline

### 1.1 `src/benchmark_bancos/sources.yml` vs. tuplas hardcodeadas — veredicto: **no todavía, y no como se pediría por defecto**

La tentación es "las 4 fuentes son simétricas, muevan la config a YAML". Mirando el código real, **no son simétricas**:

| Stage | Forma de iteración | Fecha derivada de |
|---|---|---|
| `load_years` | 2 reportes × N años, cada uno un ZIP por año | nombre de carpeta/columna |
| `load_bce` | 1 archivo acumulativo por clave (`tsp`/`tsa`), sin años | no aplica (histórico completo en 1 archivo) |
| `load_tasas_historicas` | 1 archivo HTML por mes, regex sobre nombre de archivo | `_NOMBRE_ARCHIVO` regex, `pipeline.py:131` |
| `load_boletin` | scrape previo + 1 ZIP por mes, regex + diccionario de meses en español | `_NOMBRE_BOLETIN` + `_MESES_ES`, `pipeline.py:173-177` |

Solo `load_years` tiene el shape "tabla de (report_type, tabla, parse_fn, upsert_fn)" que un YAML genérico resolvería bien — y ahí ya es literalmente una tupla de 2 elementos declarativa. Las otras 3 tienen *una sola fuente cada una*: forzarlas a un esquema YAML común hoy es inventar indirección para algo que, por regla del propio playbook de este agente ("no inventar indirección para lo que solo tiene una forma"), no la necesita todavía.

**Lo que sí es una violación real de DRY, y es donde está el ROI**: las 4 funciones repiten, casi carácter por carácter, el mismo esqueleto de control — `get_connection()` → `try` → loop de archivos → `is_source_loaded`/`sha256_file` → parse → `load_raw*` → `upsert_fn` → `register_source_file` → `conn.commit()` por archivo → `except: conn.rollback(); raise` → `finally: conn.close()` → `refresh_marts(conn)` + commit final. Eso se repite 4 veces (~140 de las 252 líneas de `pipeline.py`).

**Propuesta concreta**: extraer ese esqueleto a un runner genérico de un solo stage (algo como `run_stage(conn_factory, file_iterator, parse_fn, load_raw_fn, upsert_fn, report_type)`), y que las 4 funciones actuales se reduzcan a construir su `file_iterator` específico (que sí difiere legítimamente entre ellas) y llamar al runner. Ilustrativo, no literal:

```
# forma, no código real
run_stage(files=iter_capcol_years(years, "cartera"), parse=parse_cartera_file, upsert=upsert_staging_cartera, report_type="cartera")
```

Esto reduce el costo de agregar una 5ª fuente a "escribir un iterador de archivos + un parser + un upsert", sin forzar un esquema YAML sobre 3 fuentes que no lo necesitan. **Cuándo sí vale la pena `src/benchmark_bancos/sources.yml`**: el día que llegue una 5ª/6ª fuente con el mismo shape que `load_years` (ZIP anual + parser + upsert, sin lógica de fecha especial) — en ese momento, convertir la tupla de `load_years` en una lista YAML consumida por el runner ya factorizado es un cambio de 15 minutos, no una reingeniería.

**División de responsabilidad**: este refactor toca solo `pipeline.py` (mecánica de orquestación), no toca `sql/`, grano de tabla, ni nombres de negocio — es carril mío completo, sin necesidad de involucrar a `data-architect`.

### 1.2 Retry/backoff en extractores

Dos categorías de fallo distintas, dos tratamientos:

- **Descargas directas** (`download_bce.py:30`, `download_tasas_historicas.py:47`, ambas sobre `urllib.request.urlopen`): un solo intento, sin backoff. Un timeout de red transitorio aborta toda la corrida de esa fuente. Propuesta: un decorador/helper de reintento pequeño y casero (3 intentos, backoff exponencial simple, ej. 2s/4s/8s) en un módulo compartido (`src/benchmark_bancos/extract/common.py` o similar) — **no** agregar `tenacity` como dependencia nueva para ~4 puntos de llamada; el hand-rolled es proporcional y mantiene la higiene de dependencias que pide este proyecto. Si el número de call sites o la complejidad de la política de retry crece, ahí sí se justifica `tenacity`.
- **Playwright** (`scrape_superbancos.py`, `scrape_boletin.py`): ya tiene reintento de *localización de UI* (`_open_year_folder`, 3 intentos). Falta envolver `page.goto(..., timeout=60_000)` (línea 99 / línea 79) y el ciclo completo de `scrape()` con el mismo helper de retry — hoy un timeout de navegación inicial mata toda la corrida sin reintento.

### 1.3 Logging estructurado con correlación por corrida

Consolidar los 4 `logging.basicConfig()` duplicados en un único punto de entrada (ej. una función `setup_logging()` en un módulo compartido, llamada una vez desde `pipeline.main()` y desde cada script standalone bajo `if __name__ == "__main__"`). Sobre eso, agregar un `run_id` (uuid4 corto o timestamp) inyectado vía un `contextvar` o `LoggerAdapter` al inicio de cada stage, de forma que **no** haya que tocar cada uno de los `log.info(...)` existentes en los 8 módulos — el `run_id` se agrega al `Formatter`, no a cada call site.

Escala del proyecto: no hay agregador de logs (ELK/CloudWatch) ni equipo consumiendo logs estructurados — JSON logging (`structlog`/`python-json-logger`) sería una dependencia nueva sin consumidor real hoy. Recomendación: texto plano + `run_id`, stdlib puro, ahora; JSON logging queda en "defer" hasta que exista un consumidor real.

### 1.4 Exit codes no triviales

Hoy una excepción no capturada en `main()` ya produce exit code ≠ 0 por default de Python — el mecanismo básico existe. El hueco real es el señalado en 0: `load_tasas_historicas`/`load_boletin` **tragan** errores por archivo (`log.warning` + `continue`) y terminan con éxito aparente aunque el 100% de los archivos de esa corrida hayan fallado a parsear. Propuesta: cada stage devuelve/registra un contador `(procesados, saltados_por_error)`; `main()` decide el exit code: `sys.exit(1)` si `saltados_por_error > 0` (señal fuerte para un cron/Task Scheduler que hoy no tiene visibilidad), y opcionalmente un umbral distinto para "0 procesados, N saltados" (falla total) vs. "N-1 de N procesados" (degradación parcial, aún útil para alertar sin bloquear).

### 1.5 Orquestación proporcional a la cadencia real — por qué no Airflow

`docs/architecture.md` ("Evaluación de escalabilidad") ya cerró esta discusión: cadencia semanal (BCE) como máximo, mensual el resto, proyecto de un solo responsable (`docs/gobernanza_datos.md`: "Responsable: Kevin Flores... proyecto individual, sin equipo"). No hay nada nuevo que reabra esa decisión — ni fuente sub-diaria, ni conflicto de scheduling entre equipos, ni dependencias cruzadas entre pipelines que un DAG resolvería mejor que 4 comandos secuenciales.

**Paso proporcional siguiente** ("correr a mano" → algo mínimamente operado):
1. Un `Makefile` (o `justfile`, cross-platform con `just`) con targets `capcol`, `bce`, `tasas-historicas`, `boletin`, `all` que envuelven los comandos ya documentados en el README — cero lógica nueva, solo dejar de tener que recordar/copiar 4 líneas de `uv run benchmark-bancos ...`.
2. Scheduler: **condicionado a dónde vive el Postgres real**. Hoy `POSTGRES_HOST` por defecto es `localhost` — un GitHub Actions programado (`schedule:` cron) corre en un runner efímero de GitHub y **no puede alcanzar un Postgres en `localhost` del autor**. Las opciones reales, en orden de qué tan poco cambia la infraestructura actual:
   - **Windows Task Scheduler** invocando el `Makefile`/CLI existente contra el Postgres local — cero infraestructura nueva, coherente con el quickstart Windows-first documentado.
   - **cron**, si el proyecto alguna vez se mueve a un host/VM Linux (o WSL) — mismo principio.
   - **GitHub Actions programado** — viable *solo* si Postgres pasa a estar en un host alcanzable por red desde GitHub (ej. un Postgres gestionado con endpoint público/firewalled a los runners de GH) — eso es un cambio de infraestructura que no está pedido acá, así que lo dejo como prerequisito explícito, no como si ya aplicara.

   No propongo Airflow/Prefect/Dagster ni ningún motor de workflows — sería exactamente el sobre-ingeniería que `docs/architecture.md` ya descartó, y nada en el estado actual del repo lo contradice.

---

## 2. Reglas de QA

### 2.1 Invariantes de CDC/idempotencia que nunca deben regresar

Estas son el contrato que cualquier refactor de orquestación (sección 1) debe preservar intacto, verificado, no asumido:

1. **Gate por hash de archivo**: `raw.source_files (source_file, source_hash)` — un archivo con el mismo hash nunca se reprocesa (`is_source_loaded`, `load_postgres.py:36`).
2. **Upsert con guard de `row_hash`**: `ON CONFLICT (llave_natural) DO UPDATE ... WHERE row_hash IS DISTINCT FROM EXCLUDED.row_hash` — una fila sin cambios reales no dispara `UPDATE` (patrón repetido en `upsert_staging_cartera`, `upsert_staging_depositos`, y las 5 funciones BCE/Boletín).
3. **Unicidad NULL-safe**: toda columna nullable dentro de una llave natural usa `COALESCE(col, centinela)` tanto en el índice único como en el target del `ON CONFLICT` (patrón fijado en `sql/10_fix_null_unique_constraints.sql` tras el bug real de `NULL <> NULL` bajo `UNIQUE`).
4. **`refresh_marts()` puro e idempotente**: solo SQL, `INSERT...SELECT...ON CONFLICT`, sin efectos secundarios fuera de la base.
5. **Conteos `raw = staging = marts`** por fuente tras cada carga (invariante ya verificado y documentado, ej. `bce_tasas_pasivas`: 1.956.386 filas en `staging` = `marts`).
6. **Grano único post-pivote de `estado_cartera`**: exactamente una fila por `(fecha_id, banco_id, canton_id, segmento_id)` en `fact_saldo_cartera` desde `sql/21` — nunca 3 filas EAV otra vez.

### 2.2 Los 2 tests de regresión ya routeados — diseño concreto

Ambos son de **tier integración** (necesitan Postgres real, ninguno es una función pura) — encajan en el job `test-integration` de 2.4.

- **Test A — NULL-safe unique (regresión de `sql/10`)**: contra un schema ya migrado hasta `sql/21`, insertar dos filas sintéticas con la misma llave natural salvo la columna nullable (ej. dos `dim_plazo`-shape con `dias_desde` igual y `dias_hasta = NULL` ambas), vía el mismo `ON CONFLICT (a, COALESCE(b, -1))` que usa el código real — assert de que queda **1** fila, no 2. Esto encapsula exactamente el bug que `sql/10` corrigió (`NULL <> NULL` incluso bajo `UNIQUE`), como un test ejecutable en vez de solo un comentario en la migración.
- **Test B — invariante de pivote de `estado_cartera` (regresión de `sql/21`)**: tras un upsert (real o sintético) a `staging.cartera` con las 3 filas EAV-shape (`por_vencer`/`no_devenga_intereses`/`vencida`) para la misma llave, correr `refresh_marts()` y assert (a) exactamente 1 fila en `fact_saldo_cartera` para esa combinación — no 3 —, y (b) `saldo_total = saldo_por_vencer + saldo_no_devenga_intereses + saldo_vencida` para cada fila (protege el contrato de la columna `GENERATED` aunque alguien la cambie a columna normal más adelante).

### 2.3 Cobertura para la capa de orquestación sin test (item routeado)

División en dos por costo/beneficio:

- **Ganancia rápida, sin DB**: `sha256_file()` (`src/benchmark_bancos/transform/common.py:16`) es una función pura — hashear un archivo temporal, verificar determinismo y sensibilidad al contenido. Cero excusa para que esté sin test hoy; es el primer test a agregar.
- **Lógica de nombre de archivo → fecha, hoy inline y no testeable en aislamiento**: `_NOMBRE_ARCHIVO`/`_MESES_ES`/`_NOMBRE_BOLETIN` (`pipeline.py:131-177`) están enterradas dentro de los loops de `load_tasas_historicas`/`load_boletin`. Propuesta: factorizarlas como funciones nombradas (`parse_fecha_from_tasas_historicas_filename(name) -> date`, `parse_fecha_from_boletin_filename(name) -> date`) — mismo comportamiento, ahora testeable con casos puros (nombre válido, mes no reconocido, patrón que no matchea) sin tocar DB ni red.
- **Lo que sí requiere Postgres real**: la secuencia `load_raw → upsert_fn → register_source_file → commit` de `load_years`/`load_bce`/`load_boletin` **sigue sin test** (pendiente); la mecánica COPY/temp-table de `load_postgres.py` (`_copy_rows`, `_upsert_bce_via_temp`, `_upsert_boletin_via_temp`) **ya está cerrada** (2026-08-29, `tests/test_integration_regressions.py`): conteo exacto de filas, CDC no-op, UPDATE real disparado por un cambio de valor real, y — sobre la promesa de `ON COMMIT DROP` — verificación positiva contra `pg_tables` (existe en `pg_temp_N` justo después de la llamada, sin commit; desaparece tras un `commit()` real). Detalle no anticipado acá: como `ON COMMIT DROP` solo dispara en un `COMMIT` real (nunca en el `ROLLBACK` que usa `db_conn` en el resto de la suite), estos tests SÍ necesitan un `commit()` real entre llamadas para poder ejercitar la ruta de tabla temporal más de una vez por sesión — a diferencia del resto de `test_integration_regressions.py`, se limpian ellos mismos con un `DELETE` + `commit()` en un `finally`, en vez de depender del rollback del fixture.

### 2.4 Forma del workflow de CI (jobs, no YAML)

| Job | Qué corre | Necesita DB | Necesita red |
|---|---|---|---|
| `lint` | `ruff check .` + `black --check .` sobre `src/benchmark_bancos/`, `scripts/`, `tests/` | No | No |
| `test-unit` | `pytest -m "not integration"` — matching/normalización (22 de los 37 tests actuales), parsers con fixtures locales, `sha256_file` y parsing de nombre de archivo (nuevos) | No | No |
| `test-integration` | levanta `postgres:17` (service container o el propio `docker-compose.yml` una vez arreglado el mount de migraciones), aplica `sql/00`...`sql/21` en orden, corre `pytest -m integration` (tests A/B de 2.2 + cobertura de 2.3) | Sí | No (fixtures locales, no scraping en vivo) |
| *(slot, no diseñado acá)* `schema-guard` | el check de números de migración duplicados + `schema_migrations` ya routeado a este agente en otro hallazgo — encaja naturalmente como job separado o dentro de `lint` (la parte de colisión de números es solo filesystem, sin DB) | Depende del check | No |

**Deliberadamente fuera de CI**: ningún job ejecuta los scrapers Playwright contra los sitios reales de Superbancos/BCE — es inherentemente frágil (depende de selectores CSS de un sitio de terceros, límites de tasa, tiempos de red variables) y no es lo que un gate de corrección determinístico debería validar. Eso queda en la sección 1 (reintentos + scheduling), no en QA.

`tests/test_transform.py` (3 tests) usa hoy `pytest.skip()` si `data/raw/2021/...` no existe (gitignored, se regenera con el scraper) — en CI **siempre** se saltaría. Es una limitación honesta a documentar, no un bug del job. Mejora barata y de bajo riesgo (do-soon, no bloqueante): commitear un ZIP mínimo de muestra bajo `tests/fixtures/` (los datos son estadísticas públicas oficiales, sin PII, sin problema de licencia para versionarlos) para que esos 3 tests corran de verdad en `test-unit` en vez de saltarse siempre.

---

## 3. Alineación de YAML/config con mejores prácticas

### 3.1 Inventario actual vs. propuesto

| Config | Hoy | Evaluación | Propuesta |
|---|---|---|---|
| `.env` / `.env.example` | 8 vars (`POSTGRES_*`, `SCRAPER_YEARS`, `SCRAPER_DOWNLOAD_DIR`), leídas vía `os.getenv` con defaults sensatos en `src/benchmark_bancos/config/` | Ya alineado con buena práctica — env-driven, gitignored, sin secretos hardcodeados en código | Sin cambios |
| `docker-compose.yml` | `POSTGRES_PASSWORD: changeme` **hardcodeado inline**, no interpolado desde `.env` | Diverge silenciosamente de `.env.example` — hoy coinciden por casualidad, pero nada los mantiene sincronizados; cambiar la password en `.env` no cambia el contenedor | Interpolar `${POSTGRES_DB}`/`${POSTGRES_USER}`/`${POSTGRES_PASSWORD}` desde el `.env` raíz (Docker Compose lo autocarga) — una sola fuente de verdad para credenciales entre app y contenedor |
| `docker-compose.yml` — mount de migraciones | Solo `sql/01_schema_raw.sql`...`sql/04_indexes_views.sql` (4 de 22 archivos `sql/00`-`sql/21`) | **Ya routeado por `data-architect`** — lo confirmo y agrego un detalle mecánico: los scripts de `docker-entrypoint-initdb.d` corren en orden **lexicográfico de nombre de archivo**, así que montar el directorio completo (`./sql:/docker-entrypoint-initdb.d:ro`) en vez de 22 líneas de volumen individuales resuelve el gap actual **y** evita que cada migración futura (`sql/22`, `sql/23`...) requiera otra edición de `docker-compose.yml` | Detalle para quien implemente el fix routeado; no lo aplico yo en esta entrega (es proposal-only) |
| `src/benchmark_bancos/config/` — `DB_CONFIG`, `BCE_URLS` | Dicts Python, ya efectivamente externalizados (env-driven / constantes de infraestructura) | Carril mío, ya en buen estado | Sin cambios; candidatos naturales si algún día se arma `src/benchmark_bancos/sources.yml` (sección 1.1) |
| `src/benchmark_bancos/config/` — `FOLDER_NAMES`, `TIPO_CREDITO_KEYWORDS`, `PROVINCIA_REGION` | Dicts Python que codifican mapeos de negocio (geografía de Ecuador, taxonomía de segmento de crédito) | **No recomiendo moverlos a YAML** aunque "mover a config" suene bien por default: son conocimiento de modelado (carril `data-architect`), y YAML no reduce el riesgo de un typo — de hecho lo aumenta, porque Python falla en el `import` con un `KeyError` inmediato y YAML fallaría silenciosamente más adelante dentro de un parser, en tiempo de ejecución | Dejar en Python; si se tocan, es hallazgo para `data-architect`, no mío |
| `requirements.txt` | 8 deps, solo `>=`, sin cota superior, sin lockfile | Riesgo real: un `pip install` hoy puede traer una versión mayor futura de `pandas`/`psycopg`/`playwright` que rompa compatibilidad sin aviso | Pinnear con especificador de release compatible las 3 que importan para reproducibilidad (persona lo pide explícito): `pandas>=2.2,<3`, `psycopg[binary]>=3.1,<4`, `playwright>=1.45,<2`. Dejar `pyarrow`/`openpyxl`/`python-dotenv`/`pyyaml`/`pytest` como están (menor superficie de rotura, o dev-only) |
| `requirements.txt` → `pyproject.toml` | No existe `pyproject.toml` | `black`/`ruff` leen su config de `pyproject.toml` por convención — hace falta el archivo de todas formas | **Migración acotada, no completa**: crear `pyproject.toml` con **solo** `[tool.black]`/`[tool.ruff]` (no requiere tabla `[project]` para que las herramientas funcionen), dejando `requirements.txt` intacto por ahora. La migración completa de dependencias/empaquetado (`pip install -e .` reemplazando `pip install -r requirements.txt`) cambia el contrato de quickstart del README — la marco como decisión aparte a confirmar con el usuario antes de aplicar, no la asumo incluida |

### 3.2 Contenerización del runner ETL (item routeado, sin diseñar acá)

Confirmo el hallazgo: solo Postgres está contenerizado; el lado Python/Playwright sigue dependiendo de un venv local. No lo diseño en detalle en esta entrega porque el propio prompt del review de arquitectura lo lista como pendiente separado y la persona pide chequear con el usuario antes de asumir que se quiere (cambia el contrato de quickstart del README). Lo dejo anotado para que el usuario decida si entra en el plan de trabajo, con la nota de que un `Dockerfile` para el runner necesitaría pinnear Python + instalar browsers de Playwright (`playwright install chromium` dentro de la imagen, no en tiempo de ejecución) para ser reproducible de verdad.

---

## 4. Introducción de `black` + `ruff`

### 4.1 Alcance

`src/benchmark_bancos/` (19 archivos, 19 `.py`), `scripts/compute_indicadores_excel.py`, `tests/` (7 archivos). `sql/`, `docs/`, `powerbi/` quedan fuera (no son Python). `data/` está gitignored, no aplica.

### 4.2 Qué tan estricto

**`black`**: adoptar el default (line-length 88) sin overrides — es el punto donde menos hay que discutir configuración, y el propio equipo de `black` desaconseja tocar el largo de línea salvo razón fuerte.

**`ruff`**: empezar con un set mínimo y subir después, no al revés. Concretamente:
- Fase 1 (ahora): `E`/`F` (pyflakes + pycodestyle core — imports sin usar, variables sin usar, sintaxis, lo que ya rompería en tiempo de ejecución o es ruido obvio) + `I` (isort, orden de imports — barato y determinístico).
- Fase 2 (defer, no ahora): `B` (bugbear — atrapa antipatrones reales como mutable default arguments) y `UP` (pyupgrade — sintaxis moderna) son candidatos razonables una vez que la Fase 1 esté limpia y el flujo de commit con el linter ya sea rutina.
- No adoptar un preset agresivo (`ALL`, o sumar `D` para docstrings, `ANN` para type hints obligatorios) de entrada — el código tiene docstrings de módulo largos y en español con detalle narrativo real (ver 4.3), y forzar reglas de estilo de docstring generaría cientos de hallazgos sin valor de corrección, solo ruido.

### 4.3 Qué generaría ruido en la primera pasada (medido, no estimado)

Escaneé longitud de línea en los 28 archivos `.py` de `src/benchmark_bancos/`+`tests/` (3.008 líneas totales):

| Umbral | Líneas que lo exceden |
|---|---|
| >88 (default `black`) | 226 |
| >100 | 73 |
| >120 | 24 |
| línea más larga | 161 caracteres (`src/benchmark_bancos/load/load_postgres.py:530`) |

Concentración: `src/benchmark_bancos/load/load_postgres.py` por sí solo aporta 5 de las 15 líneas más largas del repo (líneas 530, 603, 559, 297, 504, todas >140 caracteres) — son comentarios/docstrings narrativos explicando decisiones de diseño (el estilo documentado en `docs/architecture.md` de "explicar el porqué, no solo el qué"), no código denso. `src/benchmark_bancos/transform/parse_tasas_historicas.py` y `parse_cartera.py` también aparecen repetidamente.

**Lo que esto significa en la práctica**: `black` va a reformatear (mayormente re-envolver líneas largas, normalizar comillas y espaciado) en prácticamente todos los 19 archivos de `src/benchmark_bancos/` — es un cambio grande mecánico de una sola vez, no incremental. `ruff` con solo `E`/`F`/`I` debería generar muchas menos correcciones reales (el código ya no tiene imports muertos obvios a simple vista en lo leído), así que la mayor parte del "primer PR de lint" será formato, no bugs. Vale correr `black --diff`/`ruff check --diff` antes de aplicar para que el usuario vea el tamaño real del diff antes de aceptarlo.

### 4.4 Dónde vive la config

`pyproject.toml` en la raíz, secciones `[tool.black]` (línea 88, target los Python soportados) y `[tool.ruff]` (+ `[tool.ruff.lint]` para el set de reglas de 4.2) — es el archivo estándar que ambas herramientas buscan por default, y ya lo propuse en 3.1 como el vehículo natural para esta config sin forzar una migración completa de empaquetado.

### 4.5 Pre-commit hook vs. solo CI check

Recomiendo **CI check primero, pre-commit después de que el primer pase de formato ya esté aplicado y aceptado**. Razón: si se instala un hook de pre-commit *antes* de correr `black`/`ruff` sobre el código existente, cada commit normal (incluso uno que no toca los archivos con problemas) puede bloquearse por el ruido preexistente descrito en 4.3, generando fricción inmediata sin que el usuario haya decidido aceptar ese diff grande. Orden propuesto:
1. Correr `black`+`ruff --fix` una vez sobre todo el scope (commit dedicado, revisado por el usuario, sin cambios de lógica mezclados).
2. Agregar el job `lint` a CI (sección 2.4) — desde ahí, cualquier PR nuevo se valida automáticamente.
3. Solo después, si el usuario quiere feedback antes del push, agregar `.pre-commit-config.yaml` con los mismos hooks — es redundante con el CI check en términos de qué detecta, pero da feedback más rápido localmente. No es indispensable para un proyecto de un solo colaborador; lo trato como "nice to have", no como parte del "hazlo ahora".

---

## 5. Priorización

Misma estructura que el review de arquitectura (do-now / do-soon / defer) para que ambas propuestas se lean de forma consistente.

### Do now (bajo costo, alto valor, sin ambigüedad de diseño)

1. `pyproject.toml` con `[tool.black]`/`[tool.ruff]` (fase 1: `E`/`F`/`I`) + pase único de formato sobre `src/benchmark_bancos/`, `scripts/`, `tests/` (sección 4).
2. Job `lint` en CI (`ruff check` + `black --check`) — no necesita DB ni red, es el job más barato de todos.
3. Consolidar los 4 `logging.basicConfig()` duplicados en un punto único + agregar `run_id` (sección 1.3) — cambio contenido, sin tocar lógica de negocio.
4. Test de `sha256_file()` (función pura, cero excusa) — primer ítem de la cobertura routeada (sección 2.3).
5. Pinnear `pandas`/`psycopg`/`playwright` con cota superior en `requirements.txt` (sección 3.1) — una línea por paquete, cero riesgo.
6. `docker-compose.yml`: interpolar credenciales desde `.env` en vez de `changeme` hardcodeado — se hace en el mismo cambio que el fix de mount de migraciones ya routeado (mismo archivo, mismo commit, por regla de la persona de actualizar README+compose juntos).

### Do soon (requiere algo de diseño/tiempo, pero sin decisiones abiertas pendientes)

1. Extraer el runner genérico de stage en `pipeline.py` (sección 1.1) — refactor mecánico, sin tocar SQL ni nombres de negocio, pero toca las 4 funciones de orquestación y merece tests antes/después para verificar que el CDC no regresa (usar `graphify affected` sobre `load_bce`/`load_boletin`/`load_years`/`load_tasas_historicas` antes de tocarlas, por ser god-nodes).
2. Retry/backoff casero en los 4 puntos de llamada de red (descargas + `page.goto`) (sección 1.2).
3. Tests de regresión A y B (`sql/10`, `sql/21`) + tests de orquestación/COPY-upsert contra Postgres real (secciones 2.2-2.3) + job `test-integration` en CI (sección 2.4) — conviene secuenciarlo después de que el fix de mount de migraciones esté aplicado, porque ese fix es literalmente el mecanismo que le da a CI un schema completo contra el cual correr estos tests.
4. `Makefile`/`justfile` con los targets de la sección 1.5.
5. Exit codes no triviales en `load_tasas_historicas`/`load_boletin` cuando todos los archivos de una corrida fallan (sección 1.4).
6. Fixture mínima de CAPCOL en `tests/fixtures/` para que los 3 tests de `test_transform.py` corran en CI en vez de saltarse siempre (sección 2.4).
7. Migración acotada de `pyproject.toml` a incluir `[project.dependencies]` (reemplazo completo de `requirements.txt`) — **solo si el usuario confirma** que quiere cambiar el comando de quickstart del README.

### Defer (sin trigger real hoy, o depende de una decisión del usuario que no está tomada)

1. Contenerización del runner ETL (`Dockerfile` para Python/Playwright) — cambia el contrato de quickstart, requiere confirmación explícita del usuario antes de diseñarlo (persona, regla 4).
2. `src/benchmark_bancos/sources.yml` como config declarativa completa — sin un 5º/6º source con el shape de `load_years`, no hay problema real que resuelva todavía (sección 1.1).
3. Reglas `ruff` de fase 2 (`B`, `UP`) y cualquier preset de docstrings/type-hints — esperar a que la fase 1 esté estable en el flujo normal de trabajo.
4. `.pre-commit-config.yaml` — redundante con el CI check para un proyecto de un solo colaborador; agregar solo si la fricción de esperar al CI se vuelve un problema real.
5. Scheduler vía GitHub Actions programado — bloqueado en un prerequisito de infraestructura (Postgres alcanzable por red desde GitHub) que no existe hoy; Windows Task Scheduler cubre la necesidad inmediata sin ese prerequisito.
6. Logging estructurado en JSON / `structlog` — sin consumidor (no hay agregador de logs) que lo justifique todavía.
