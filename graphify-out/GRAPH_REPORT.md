# Graph Report - benchmark-bancos  (2026-10-09)

## Corpus Check
- 115 files · ~124,734 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1180 nodes · 1821 edges · 154 communities (70 shown, 84 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 83 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `758d993f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_postgres.py
- benchmark_cartera_depositos
- migrate.py
- banco_matching.py
- resolver_categoria_deposito
- cli.py
- test_parse_tasas_historicas.py
- test_orquestacion.py
- scrape_boletin.py
- Catálogo completo (48 indicadores, 12 categorías)
- marts.dim_banco
- parse_boletin.py
- con_reintentos
- setup_logging
- DataFrame
- marts.vw_conciliacion_saldos_balance
- 18_glosario_cuentas_views.sql
- resolver_canton_bce
- marts.vw_cartera_market_share
- marts.fact_tasas_activas
- test_integration_regressions.py
- 12_schema_tasas_historicas.sql
- compute_indicadores_excel.py
- 13_schema_boletin.sql
- Propuesta: escalabilidad de ETL, reglas de QA, alineación de config y `black`+`ruff`
- marts.vw_cartera_market_share
- marts.dim_entidad
- marts.fact_saldo_cartera_new
- 03_schema_marts.sql
- actualizar.sh script
- 38_schema_migrations.sql
- export_sample_parquet.py
- scrape_superbancos.py
- CLAUDE.md
- download_seps.py
- 08_dim_segmento_categoria_plazo.sql
- date
- 02_schema_staging.sql
- 07_dim_banco_dim_fecha_rebuild.sql
- 16_dim_segmento_normativo.sql
- 19_dim_segmento_entidad.sql
- 20_dim_provincia.sql
- parse_seps.py
- download_bce.py
- config/__init__.py
- marts.dim_subsegmento_credito
- marts.fact_tasas_activas
- marts.fact_tasas_pasivas
- marts.fact_tasas_pasivas_instrumento
- marts.fact_tasas_pasivas_plazo
- marts.fact_tasas_referenciales_credito
- 34_cdc_por_columnas_refresh_incremental.sql
- marts.fact_tasas_referenciales_sistema
- staging.depositos
- marts.dim_fecha
- marts.dim_banco
- marts.dim_fecha
- staging.depositos
- marts.fact_cartera
- marts.fact_depositos
- staging.depositos
- marts.dim_plazo
- marts.fact_depositos
- orquestacion.py
- 01_schema_meta.sql
- parametrize
- marts.fact_captaciones_depositos
- marts.fact_cartera
- marts.fact_colocaciones_cartera
- marts.fact_depositos
- marts.fact_tasas_referenciales_cartera
- marts.fact_colocaciones_cartera
- marts.fact_saldo_cartera
- marts.fact_tasas_referenciales_cartera
- marts.dim_banco
- marts.dim_banco
- marts.fact_captaciones_depositos
- marts.fact_colocaciones_cartera
- marts.dim_canton
- marts.fact_captaciones_depositos
- marts.fact_colocaciones_cartera
- staging.banco_maestro
- marts.vw_dim_canton_geografia
- staging.bce_tasas_activas
- Gobernanza de datos
- Dimensiones
- 4. SEPS — Cooperativas de Ahorro y Crédito + Mutualistas de Vivienda — ✅ **implementada y cargada 2021-2025 (2026-09-30)**
- Linaje de datos
- Despliegue y orquestación — runbook
- Muestras de `marts.*` en Parquet
- marts.vw_banco_ruc_colisiones
- staging.depositos
- marts.dim_cuenta_contable
- marts.dim_banco
- staging.banco_maestro
- staging.cartera
- staging.cartera
- staging.bce_tasas_pasivas
- Mantenimiento de catálogos / resolución de identidad
- marts.fact_captaciones_depositos
- marts.fact_colocaciones_cartera
- staging.bce_tasas_activas
- staging.bce_tasas_pasivas
- marts.dim_plazo
- parse_bce_tasas.py
- marts.vw_cartera_bruta
- benchmark-bancos
- marts.dim_banco
- test_red.py
- marts.fact_tasas_referenciales_depositos_instrumento
- marts.fact_tasas_referenciales_depositos_plazo
- marts.dim_banco
- marts.fact_balance
- marts.fact_captaciones_depositos
- marts.fact_colocaciones_cartera
- marts.fact_pyg
- marts.fact_saldo_cartera
- marts.fact_saldo_depositos
- marts.fact_tasas_referenciales_cartera
- marts.fact_tasas_referenciales_depositos_instrumento
- marts.fact_tasas_referenciales_depositos_plazo
- staging.bce_tasas_activas
- staging.bce_tasas_pasivas
- staging.cartera
- staging.depositos
- staging.boletin_balance
- staging.boletin_pyg
- staging.tasas_referenciales
- raw.source_files

## God Nodes (most connected - your core abstractions)
1. `resolver_canton_bce()` - 30 edges
2. `resolver_banco_codigo()` - 23 edges
3. `load_seps()` - 20 edges
4. `sha256_file()` - 20 edges
5. `parse_depositos_file()` - 20 edges
6. `parse_seps_colocaciones_file()` - 18 edges
7. `parse_seps_eeff_file()` - 18 edges
8. `parse_seps_captaciones_file()` - 16 edges
9. `resolver_categoria_deposito()` - 16 edges
10. `load_boletin()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `test_resolve_canton_propaga_cantonnoresueltoerror()` --uses--> `CantonNoResueltoError`  [INFERRED]
  tests/test_parse_bce_tasas.py → src/benchmark_bancos/transform/canton_matching.py
- `test_resolver_entidad_seps_reusa_llave_bce_y_rellena_ruc_numerico()` --uses--> `RucInvalidoError`  [INFERRED]
  tests/test_parse_seps.py → src/benchmark_bancos/transform/banco_matching.py
- `test_codigo_padre_sigue_la_jerarquia_del_catalogo_unico_de_cuentas()` --calls--> `_codigo_padre()`  [EXTRACTED]
  tests/test_parse_boletin.py → src/benchmark_bancos/transform/parse_boletin.py
- `test_parse_fecha_tasas_historicas_no_matching_pattern_raises()` --calls--> `parse_fecha_from_tasas_historicas_filename()`  [EXTRACTED]
  tests/test_pipeline_fecha_parsing.py → src/benchmark_bancos/pipeline.py
- `test_parse_fecha_tasas_historicas_valid_filename()` --calls--> `parse_fecha_from_tasas_historicas_filename()`  [EXTRACTED]
  tests/test_pipeline_fecha_parsing.py → src/benchmark_bancos/pipeline.py

## Import Cycles
- None detected.

## Communities (154 total, 84 thin omitted)

### Community 0 - "load_postgres.py"
Cohesion: 0.06
Nodes (73): date, _ejecutar(), _cdc_guard(), _clean(), _copy_rows(), _crear_fuentes_incrementales(), get_connection(), insert_dim_cuenta_contable_seps() (+65 more)

### Community 1 - "benchmark_cartera_depositos"
Cohesion: 0.10
Nodes (40): "marts"."dim_banco", "marts"."dim_canton", "marts"."dim_categoria_deposito", "marts"."dim_cuenta_contable", "marts"."dim_fecha", "marts"."dim_plazo", "marts"."dim_provincia", "marts"."dim_segmento_credito" (+32 more)

### Community 3 - "migrate.py"
Cohesion: 0.26
Nodes (14): archivos_migracion(), Estado, _log_notice(), MigracionError, migrar(), nivel_verificado(), Connection, Path (+6 more)

### Community 4 - "banco_matching.py"
Cohesion: 0.09
Nodes (43): BancoNoResueltoError, _cargar_csv(), _crosswalk(), EntidadBceNoMapeadaError, maestro(), _normalizar(), _por_regla(), Path (+35 more)

### Community 5 - "resolver_categoria_deposito"
Cohesion: 0.07
Nodes (50): PlazoNoResueltoError, ValueError, Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de…, Chequeo de dos niveles para TODOS los valores crudos de `plazo` observados en…, Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto…, El texto crudo de plazo no matchea ningún patrón conocido (shape inválido), o…, Sanity check de rango, aplicado DESPUÉS de que el shape ya matcheó un patrón…, resolver_plazo_bce() (+42 more)

### Community 6 - "cli.py"
Cohesion: 0.23
Nodes (9): ArgumentParser, Punto de entrada del proyecto. uv run main.py <etapa> [opciones] Delega en…, Namespace, build_parser(), _codigo_salida(), main(), Interfaz de línea de comandos del pipeline. Uso (con uv): uv run benchmark-…, Entry point del script `benchmark-bancos` (pyproject) y de `python -m`. (+1 more)

### Community 7 - "test_parse_tasas_historicas.py"
Cohesion: 0.08
Nodes (40): DataFrame, parametrize, _categoria_label(), _clean_label(), _emitir(), _normalizar_ancho(), _parse_filas(), parse_tasas_historicas_file() (+32 more)

### Community 8 - "test_orquestacion.py"
Cohesion: 0.06
Nodes (34): evaluar(), Connection, Control de conciliación saldos vs. contabilidad (2026-10-09, `sql/39`). Evalúa…, Devuelve un mensaje por cada (mes, tipo, medida) fuera de umbral., Evalúa los últimos `meses` cortes con contabilidad cargada. Registra un ERROR…, Resultado, Umbral, verificar() (+26 more)

### Community 9 - "scrape_boletin.py"
Cohesion: 0.21
Nodes (14): _download_all_files(), es_boletin(), main(), _open_year_folder(), Path, Descarga los ZIP del Boletín Financiero Mensual (Balance y PyG) de bancos…, True si el archivo es un boletín mensual. Compara sin tildes: el portal escribe…, _reset_to_root() (+6 more)

### Community 12 - "Catálogo completo (48 indicadores, 12 categorías)"
Cohesion: 0.06
Nodes (32): 1. Cómo está organizado el Catálogo Único de Cuentas, 2. Cuentas clave — ACTIVO (sección `1`), 3. Cuentas clave — PASIVO (sección `2`), 4.6 Hueco de datos conocido: PyG código `4`, 4. Cuentas clave — PATRIMONIO, INGRESOS, GASTOS (secciones `3`, `4`, `5`), 5. Bloques que combinan Balance + PyG o cruzan periodos (series de tiempo), 6. Qué NO cubre este documento (fuera de alcance, documentado en otro lado), Cómo usar este documento al escribir un ratio nuevo (+24 more)

### Community 14 - "parse_boletin.py"
Cohesion: 0.16
Nodes (16): _find_header_row(), _normalize_col(), parse_boletin_file(), _parse_hoja(), _parse_met(), DataFrame, Path, Parser del Boletín Financiero Mensual (Superbancos) -- hojas BALANCE y PYG.… (+8 more)

### Community 15 - "con_reintentos"
Cohesion: 0.25
Nodes (9): BaseException, download_tasas_historicas(), _meses_hasta_hoy(), Path, Descarga de las páginas mensuales TasasVigentes{MM}{YYYY}.htm del BCE (techos…, con_reintentos(), es_transitorio(), Reintentos para las descargas (2026-10-09). Antes un corte de red momentáneo o… (+1 more)

### Community 16 - "setup_logging"
Cohesion: 0.29
Nodes (6): LogRecord, Path, Configuracion de logging compartida por todo el pipeline. Reemplaza los…, Configura el root logger una sola vez por proceso. Idempotente: si el root…, _RunIdFilter, setup_logging()

### Community 18 - "marts.vw_conciliacion_saldos_balance"
Cohesion: 0.29
Nodes (7): marts.vw_conciliacion_resumen, marts.vw_conciliacion_saldos_balance, marts.dim_cuenta_contable, marts.dim_entidad, marts.fact_balance, marts.fact_saldo_cartera, marts.fact_saldo_depositos

### Community 19 - "18_glosario_cuentas_views.sql"
Cohesion: 0.31
Nodes (14): marts.vw_activo_promedio_ytd, marts.vw_cartera_bruta, marts.vw_cartera_bruta_segmento, marts.vw_cartera_improductiva, marts.vw_cartera_improductiva_segmento, marts.vw_depositos_corto_plazo, marts.vw_patrimonio_promedio_ytd, marts.vw_pyg_total_gastos (+6 more)

### Community 20 - "resolver_canton_bce"
Cohesion: 0.06
Nodes (36): CantonNoResueltoError, es_canton_conocido(), normalize_canton(), ValueError, Universo curado `(canton, provincia) -> codigo_inec` de…, Resuelve un par crudo (canton, provincia) de BCE tsp/tsa al par normalizado…, True si el par (ya normalizado, tal como lo devuelve `resolver_canton_bce()`)…, La `provincia` cruda no normaliza contra ninguna de las 24 provincias reales… (+28 more)

### Community 21 - "marts.vw_cartera_market_share"
Cohesion: 0.33
Nodes (8): marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.dim_banco, marts.dim_fecha, marts.fact_cartera, marts.fact_depositos

### Community 22 - "marts.fact_tasas_activas"
Cohesion: 0.27
Nodes (9): marts.fact_tasas_activas, marts.fact_tasas_pasivas, marts.dim_banco, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo, marts.dim_segmento_credito, staging.bce_tasas_activas (+1 more)

### Community 23 - "test_integration_regressions.py"
Cohesion: 0.09
Nodes (37): upsert_staging_bce_tasas_pasivas(), _bce_tasas_pasivas_row(), _boletin_balance_row(), _cleanup_bce_tasas_pasivas(), _cleanup_boletin_balance(), _dim_canton_insert_statement(), _fact_saldo_cartera_pivot_statement(), integration (+29 more)

### Community 24 - "12_schema_tasas_historicas.sql"
Cohesion: 0.27
Nodes (9): marts.fact_tasas_pasivas_instrumento, marts.fact_tasas_pasivas_plazo, marts.fact_tasas_referenciales_credito, marts.fact_tasas_referenciales_sistema, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo, marts.dim_segmento_credito (+1 more)

### Community 25 - "compute_indicadores_excel.py"
Cohesion: 0.33
Nodes (10): cod(), _leer(), main(), promedio_ytd(), Motor de referencia del catálogo `IND_NN` (indicadores del Excel de…, Promedio de saldos fin de mes de `codigo` (1=activo, 3=patrimonio), desde…, rd_one(), rd_years() (+2 more)

### Community 26 - "13_schema_boletin.sql"
Cohesion: 0.39
Nodes (7): marts.dim_cuenta_contable, marts.fact_balance, marts.fact_pyg, marts.dim_banco, marts.dim_fecha, staging.boletin_balance, staging.boletin_pyg

### Community 27 - "Propuesta: escalabilidad de ETL, reglas de QA, alineación de config y `black`+`ruff`"
Cohesion: 0.07
Nodes (26): 0. Línea base verificada (para que la propuesta no asuma de más), 1.1 `src/benchmark_bancos/sources.yml` vs. tuplas hardcodeadas — veredicto: **no todavía, y no como se pediría por defecto**, 1.2 Retry/backoff en extractores, 1.3 Logging estructurado con correlación por corrida, 1.4 Exit codes no triviales, 1.5 Orquestación proporcional a la cadencia real — por qué no Airflow, 1. Escalabilidad del pipeline, 2.1 Invariantes de CDC/idempotencia que nunca deben regresar (+18 more)

### Community 28 - "marts.vw_cartera_market_share"
Cohesion: 0.33
Nodes (8): marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.dim_banco, marts.dim_fecha, marts.fact_saldo_cartera, marts.fact_saldo_depositos

### Community 30 - "marts.fact_saldo_cartera_new"
Cohesion: 0.31
Nodes (8): marts.fact_saldo_cartera_new, marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.dim_banco, marts.dim_canton, marts.dim_fecha, marts.dim_segmento_credito, marts.fact_saldo_cartera

### Community 31 - "03_schema_marts.sql"
Cohesion: 0.54
Nodes (7): marts.dim_banco, marts.dim_canton, marts.dim_fecha, marts.dim_producto_cartera, marts.dim_producto_deposito, marts.fact_cartera, marts.fact_depositos

### Community 36 - "export_sample_parquet.py"
Cohesion: 0.38
Nodes (6): export_full(), export_recientes(), export_sample(), Path, Exporta marts.* a Parquet, para poder probar el modelo de datos (notebooks, BI,…, Catálogos completos + cada hecho con sus últimos `meses` meses con datos.

### Community 37 - "scrape_superbancos.py"
Cohesion: 0.33
Nodes (10): _download_all_files(), main(), _open_report_folder(), _open_year_folder(), Path, Descarga los archivos ZIP de cartera y depósitos del portal CAPCOL de…, Vuelve al listado raíz de años vía el breadcrumb 'Inicio'. OJO: recargar la…, _reset_to_root() (+2 more)

### Community 39 - "download_seps.py"
Cohesion: 0.36
Nodes (8): download_seps(), download_seps_file(), _nombre_zip(), Path, Descarga directa de los reportes anuales de la SEPS (captaciones, colocaciones,…, HEAD al link del portal (sigue la redirección al .zip real, sin bajarlo): URL…, Descarga solo si la SEPS publicó una versión distinta a la local. El año en…, _version_publicada()

### Community 40 - "08_dim_segmento_categoria_plazo.sql"
Cohesion: 0.50
Nodes (3): marts.dim_categoria_deposito, marts.dim_plazo, marts.dim_segmento_credito

### Community 47 - "parse_seps.py"
Cohesion: 0.08
Nodes (49): Series, Resuelve una entidad SEPS (cooperativa, mutualista o entidad de segundo piso) a…, resolver_entidad_seps(), _codigo_padre(), _a_numero(), _chunks(), extraer_zip_seps(), _fecha_corte() (+41 more)

### Community 48 - "download_bce.py"
Cohesion: 0.47
Nodes (8): _cabeceras_condicionales(), download_all(), download_bce_file(), _leer_meta(), _meta_path(), Path, Descarga directa de los archivos semanales de tasas de interés del BCE…, clave: 'tsp' o 'tsa'. Descarga solo si el servidor tiene una versión distinta a…

### Community 50 - "config/__init__.py"
Cohesion: 0.06
Nodes (53): Catálogos de dominio usados por los parsers: mapeos de vocabulario de las…, Configuración del proyecto, separada por responsabilidad: - `settings`: lo que…, _find_project_root(), Path, Configuración que depende del entorno: rutas, base de datos y años a procesar.…, Constantes de las fuentes externas: URLs, sub-portales, nombres de carpeta, ids…, aplicar_alias_canton(), Resuelve el par (canton, provincia) crudo del BCE (tsp/tsa) contra el catálogo… (+45 more)

### Community 74 - "orquestacion.py"
Cohesion: 0.15
Nodes (10): anios_en_curso(), bloqueo_corrida(), ContadorErrores, CorridaEnCurso, date, LogRecord, RuntimeError, Orquestación de corridas desatendidas (2026-10-09). - `bloqueo_corrida()`:… (+2 more)

### Community 95 - "marts.vw_dim_canton_geografia"
Cohesion: 0.50
Nodes (3): marts.dim_provincia, marts.vw_dim_canton_geografia, marts.dim_canton

### Community 99 - "Gobernanza de datos"
Cohesion: 0.06
Nodes (30): Arquitectura, Bug real encontrado y corregido: NULL en `UNIQUE`/`ON CONFLICT`, Carga incremental (CDC) — no full refresh, Catálogos conformados (identidad compartida entre fuentes), Consumo (BI), Estructura real de los archivos fuente (verificado, no solo la ficha metodológica), Evaluación de escalabilidad, Flujo de datos (+22 more)

### Community 102 - "Dimensiones"
Cohesion: 0.08
Nodes (23): Decisiones de modelado relevantes, Diccionario de datos, Dimensiones, Hechos, marts.dim_canton, marts.dim_categoria_deposito, marts.dim_cuenta_contable (plan de cuentas del Boletín, BALANCE + PYG), marts.dim_entidad (antes `dim_banco`, renombrada 2026-10-09 en `sql/37_dim_entidad.sql`) (+15 more)

### Community 111 - "4. SEPS — Cooperativas de Ahorro y Crédito + Mutualistas de Vivienda — ✅ **implementada y cargada 2021-2025 (2026-09-30)**"
Cohesion: 0.08
Nodes (23): 1.1 Banca Pública (`capcol-instituciones-publicas/`) — ✅ cargada 2021-2025 (2026-10-01), 1. CAPCOL — Cartera y Depósitos (Superbancos) — ✅ integrada, 2.1 `tsp_desde_200801.zip` (tasas pasivas / captaciones), 2.2 `tsa_desde_200801.zip` (tasas activas / colocaciones) — ✅ confirmado, 2.3 Tasas máximas y referenciales por segmento (`TasasHistorico.htm`) — ✅ cargado (Paso 4), 2.4 Mapeo `razon_social`/`ruc` (BCE) ↔ `banco` (CAPCOL/`marts.dim_entidad`) — investigado, 2. BCE — Tasas de interés activas y pasivas (semanal) — 🔎 en investigación, 3.1 Hoja `BALANCE` (1399 filas x 35 columnas) (+15 more)

### Community 112 - "Linaje de datos"
Cohesion: 0.18
Nodes (10): 1. CAPCOL — Cartera, 2. CAPCOL — Depósitos, 3. BCE — tsp (tasas pasivas, semanal), 4. BCE — tsa (tasas activas, semanal), 5. BCE — `TasasHistorico.htm` (techos y referenciales, mensual, nivel sistema), 6. Boletín Financiero Mensual — BALANCE / PYG, 7. SEPS — Captaciones, Colocaciones (saldos) y Estados Financieros (2026-09-30), Linaje de datos (+2 more)

### Community 114 - "Despliegue y orquestación — runbook"
Cohesion: 0.04
Nodes (45): 10. Problemas frecuentes, 11. Brechas de portabilidad y orquestación, 1.1 Componentes y requisitos, 1.2 Configuración (variables de entorno), 1.3.1 Códigos de salida y bloqueo [verificado: `tests/test_orquestacion.py`], 1.3 Etapas del CLI [verificado con `uv run benchmark-bancos --help`], 1.4 Dependencias entre etapas, 1. Mapa del sistema (+37 more)

### Community 115 - "Muestras de `marts.*` en Parquet"
Cohesion: 0.40
Nodes (4): `marts_ultimos_13_meses/` (versionada), Muestras de `marts.*` en Parquet, Otros exportes (no versionados), Uso típico

### Community 130 - "Mantenimiento de catálogos / resolución de identidad"
Cohesion: 0.11
Nodes (17): 1. `dim_entidad` — camino curado (33 bancos privados + 3 públicos), 2. `dim_entidad` — camino auto-registrado (408 entidades no curadas, BCE y SEPS), 3. `dim_segmento_credito` / `dim_subsegmento_credito`, 4. `dim_categoria_deposito`, 5. `dim_segmento_entidad`, 6. `dim_plazo` (two-tier, 4 puntos de entrada), 7. `dim_cuenta_contable`, 8. `dim_canton` (two-tier, BCE tsp/tsa — 2026-09-01, `sql/28_bce_canton_grain.sql`) (+9 more)

### Community 138 - "parse_bce_tasas.py"
Cohesion: 0.11
Nodes (36): _add_common_columns(), parse_tsa_file(), parse_tsp_file(), DataFrame, Path, ValueError, Parser de los archivos semanales de tasas de interés del BCE (tsp=pasivas,…, segmento_credito de tsa no está en el universo sembrado de… (+28 more)

### Community 142 - "marts.vw_cartera_bruta"
Cohesion: 0.60
Nodes (4): marts.vw_cartera_bruta, marts.vw_cartera_improductiva_segmento, marts.dim_cuenta_contable, marts.fact_balance

### Community 146 - "test_red.py"
Cohesion: 0.07
Nodes (21): bce(), fixture, Descarga condicional del BCE (2026-10-09): el archivo tsp/tsa se republica con…, _Resp, test_copia_local_desactualizada_se_reemplaza(), test_sin_copia_local_descarga_y_guarda_meta(), fixture, Descarga condicional de la SEPS (2026-10-09): el año en curso se republica con… (+13 more)

## Knowledge Gaps
- **190 isolated node(s):** `Qué incluye`, `Quickstart`, `Estructura`, `Tests y CI`, `Alcance de los datos` (+185 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **84 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `sha256_file()` connect `config/__init__.py` to `load_postgres.py`, `parse_bce_tasas.py`, `parse_seps.py`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Why does `resolver_categoria_deposito()` connect `resolver_categoria_deposito` to `config/__init__.py`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `_resolver_plazo()` connect `test_parse_tasas_historicas.py` to `resolver_categoria_deposito`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `load_seps()` (e.g. with `download_seps()` and `get_connection()`) actually correct?**
  _`load_seps()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `sha256_file()` (e.g. with `load_bce()` and `load_boletin()`) actually correct?**
  _`sha256_file()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Qué incluye`, `Quickstart`, `Estructura` to the rest of the system?**
  _190 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `load_postgres.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05649122807017544 - nodes in this community are weakly interconnected._