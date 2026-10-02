# Graph Report - benchmark-bancos  (2026-10-01)

## Corpus Check
- 122 files · ~106,200 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1480 nodes · 2046 edges · 150 communities (86 shown, 64 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 36 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9c3893f6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_pipeline_fecha_parsing.py
- benchmark_cartera_depositos
- parse_depositos_file
- Prototipo de diseño Power BI — tema "Libro Mayor", personalización y plantilla de página
- test_banco_matching.py
- test_parse_tasas_historicas.py
- position
- position
- position
- position
- position
- position
- Catálogo completo (48 indicadores, 12 categorías)
- settings
- position
- position
- position
- position
- position
- 18_glosario_cuentas_views.sql
- resolver_canton_bce
- marts.vw_cartera_market_share
- 11_schema_bce.sql
- test_integration_regressions.py
- 12_schema_tasas_historicas.sql
- compute_indicadores_excel.py
- 13_schema_boletin.sql
- Propuesta: escalabilidad de ETL, reglas de QA, alineación de config y `black`+`ruff`
- marts.vw_cartera_market_share
- pageOrder
- marts.fact_saldo_cartera_new
- 03_schema_marts.sql
- page-benchmark-banco/page.json
- page-correlacion/page.json
- page-geografico/page.json
- page-overview/page.json
- page-tendencias/page.json
- editorSettings.json
- CLAUDE.md
- 01_schema_raw.sql
- 08_dim_segmento_categoria_plazo.sql
- version.json
- 02_schema_staging.sql
- 07_dim_banco_dim_fecha_rebuild.sql
- 16_dim_segmento_normativo.sql
- 19_dim_segmento_entidad.sql
- 20_dim_provincia.sql
- marts.dim_subsegmento_credito
- marts.fact_tasas_activas
- marts.fact_tasas_pasivas
- marts.fact_tasas_pasivas_instrumento
- marts.fact_tasas_pasivas_plazo
- marts.fact_tasas_referenciales_credito
- marts.fact_tasas_referenciales_depositos_instrumento
- marts.fact_tasas_referenciales_depositos_plazo
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
- raw.source_files
- raw.source_files
- raw.source_files
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
- position
- settings
- Dimensiones
- position
- position
- position
- position
- position
- position
- position
- position
- 4. SEPS — Cooperativas de Ahorro y Crédito + Mutualistas de Vivienda — ✅ **implementada y cargada 2021-2025 (2026-09-30)**
- Linaje de datos
- page-prototipo-diseno/page.json
- Benchmark de cartera, depósitos y tasas — bancos privados del Ecuador
- Muestras de `marts.*` en Parquet
- prototipo-diseno-bi.Report/definition/pages/pages.json
- prototipo-diseno-bi.Report/definition/version.json
- marts.vw_banco_ruc_colisiones
- staging.depositos
- marts.dim_cuenta_contable
- marts.dim_banco
- staging.banco_maestro
- staging.cartera
- staging.cartera
- config.py
- staging.bce_tasas_pasivas
- Mantenimiento de catálogos / resolución de identidad
- marts.fact_captaciones_depositos
- marts.fact_colocaciones_cartera
- staging.bce_tasas_activas
- staging.bce_tasas_pasivas
- marts.dim_plazo
- parse_seps.py
- parse_bce_tasas.py
- date
- pipeline.py
- load_postgres.py
- marts.dim_banco
- sha256_file
- load_banco_maestro_seed
- _log_bancos_no_resueltos
- _log_cantones_no_resueltos

## God Nodes (most connected - your core abstractions)
1. `resolver_canton_bce()` - 27 edges
2. `resolver_banco_codigo()` - 22 edges
3. `load_seps()` - 21 edges
4. `parse_seps_colocaciones_file()` - 20 edges
5. `parse_seps_eeff_file()` - 20 edges
6. `parse_depositos_file()` - 20 edges
7. `parse_seps_captaciones_file()` - 18 edges
8. `sha256_file()` - 18 edges
9. `resolver_categoria_deposito()` - 16 edges
10. `resolver_entidad_bce()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_categoria_deposito_seps_sin_tildes_a_canonica()` --uses--> `CategoriaNoResueltaError`  [INFERRED]
  tests/test_parse_seps.py → etl/transform/categoria_deposito_matching.py
- `test_resolve_canton_propaga_cantonnoresueltoerror()` --uses--> `CantonNoResueltoError`  [INFERRED]
  tests/test_parse_bce_tasas.py → etl/transform/canton_matching.py
- `test_empty_value_raises()` --uses--> `CategoriaNoResueltaError`  [INFERRED]
  tests/test_categoria_deposito_matching.py → etl/transform/categoria_deposito_matching.py
- `test_plazo_bucket_shape_invalido_sigue_lanzando()` --uses--> `CategoriaNoResueltaError`  [INFERRED]
  tests/test_categoria_deposito_matching.py → etl/transform/categoria_deposito_matching.py
- `test_unresolved_value_raises()` --uses--> `CategoriaNoResueltaError`  [INFERRED]
  tests/test_categoria_deposito_matching.py → etl/transform/categoria_deposito_matching.py

## Import Cycles
- None detected.

## Communities (150 total, 64 thin omitted)

### Community 0 - "test_pipeline_fecha_parsing.py"
Cohesion: 0.26
Nodes (11): parse_fecha_from_boletin_filename(), parse_fecha_from_tasas_historicas_filename(), date, Extrae la fecha (fin de mes) de un nombre de archivo TasasVigenteMMAAAA.htm.…, Extrae la fecha (fin de mes) de un nombre de archivo 'Boletín Bancos <MES_ES>…, Tests puros (sin DB ni red) para las funciones de fecha-desde-nombre-de-archivo…, test_parse_fecha_boletin_no_matching_pattern_raises(), test_parse_fecha_boletin_unrecognized_month_raises() (+3 more)

### Community 1 - "benchmark_cartera_depositos"
Cohesion: 0.10
Nodes (40): "marts"."dim_banco", "marts"."dim_canton", "marts"."dim_categoria_deposito", "marts"."dim_cuenta_contable", "marts"."dim_fecha", "marts"."dim_plazo", "marts"."dim_provincia", "marts"."dim_segmento_credito" (+32 more)

### Community 2 - "parse_depositos_file"
Cohesion: 0.07
Nodes (52): extract_single_xlsx(), find_base_sheets(), month_end_date(), normalize_banco(), normalize_text(), Path, Los ZIP de Superbancos contienen exactamente un .xlsx -- salvo boletines…, Casi todos los archivos traen 1 sola hoja 'BASE ...', pero el de vivienda trae… (+44 more)

### Community 3 - "Prototipo de diseño Power BI — tema "Libro Mayor", personalización y plantilla de página"
Cohesion: 0.10
Nodes (19): 0. Segundo intento — qué cambió y por qué, 10. Cómo exportar un `.pbit` real desde este prototipo, 11. Cómo abrir y probar el prototipo, 1. Por qué un `.pbip` separado y no una página nueva en el reporte productivo, 2.1 Por qué esto no es "Okabe–Ito con otro nombre", 2.2 Secuencial y qué no tiene campo de tema global, 2. Paleta de color — "Libro Mayor", 3. Tipografía (+11 more)

### Community 4 - "test_banco_matching.py"
Cohesion: 0.09
Nodes (45): BancoNoResueltoError, _cargar_csv(), _crosswalk(), EntidadBceNoMapeadaError, maestro(), _normalizar(), _por_regla(), Path (+37 more)

### Community 5 - "test_parse_tasas_historicas.py"
Cohesion: 0.07
Nodes (54): PlazoNoResueltoError, ValueError, Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de…, El texto crudo de plazo no matchea ningún patrón conocido (shape inválido), o…, Sanity check de rango, aplicado DESPUÉS de que el shape ya matcheó un patrón…, validar_rango_plazo(), CategoriaNoResueltaError, ValueError (+46 more)

### Community 6 - "position"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 7 - "position"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 8 - "position"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 9 - "position"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 10 - "position"
Cohesion: 0.10
Nodes (20): projections, filterConfig, filters, name, position, height, tabOrder, width (+12 more)

### Community 11 - "position"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 12 - "Catálogo completo (48 indicadores, 12 categorías)"
Cohesion: 0.06
Nodes (32): 1. Cómo está organizado el Catálogo Único de Cuentas, 2. Cuentas clave — ACTIVO (sección `1`), 3. Cuentas clave — PASIVO (sección `2`), 4.6 Hueco de datos conocido: PyG código `4`, 4. Cuentas clave — PATRIMONIO, INGRESOS, GASTOS (secciones `3`, `4`, `5`), 5. Bloques que combinan Balance + PyG o cruzan periodos (series de tiempo), 6. Qué NO cubre este documento (fuera de alcance, documentado en otro lado), Cómo usar este documento al escribir un ratio nuevo (+24 more)

### Community 13 - "settings"
Cohesion: 0.10
Nodes (19): name, reportVersionAtImport, type, objects, outspacePane, page, report, visual (+11 more)

### Community 14 - "position"
Cohesion: 0.11
Nodes (18): name, position, height, tabOrder, width, x, y, z (+10 more)

### Community 15 - "position"
Cohesion: 0.11
Nodes (18): projections, filterConfig, filters, name, position, height, tabOrder, width (+10 more)

### Community 16 - "position"
Cohesion: 0.12
Nodes (16): projections, name, position, height, tabOrder, width, x, y (+8 more)

### Community 17 - "position"
Cohesion: 0.12
Nodes (16): projections, name, position, height, tabOrder, width, x, y (+8 more)

### Community 18 - "position"
Cohesion: 0.12
Nodes (16): projections, name, position, height, tabOrder, width, x, y (+8 more)

### Community 19 - "18_glosario_cuentas_views.sql"
Cohesion: 0.31
Nodes (14): marts.fact_balance, marts.fact_pyg, marts.vw_activo_promedio_ytd, marts.vw_cartera_bruta, marts.vw_cartera_bruta_segmento, marts.vw_cartera_improductiva, marts.vw_cartera_improductiva_segmento, marts.vw_depositos_corto_plazo (+6 more)

### Community 20 - "resolver_canton_bce"
Cohesion: 0.09
Nodes (31): CantonNoResueltoError, es_canton_conocido(), normalize_canton(), ValueError, Resuelve el par (canton, provincia) crudo del BCE (tsp/tsa) contra el catálogo…, Universo de 228 pares (canton, provincia) ya sembrados en `marts.dim_canton`…, Resuelve un par crudo (canton, provincia) de BCE tsp/tsa al par normalizado…, True si el par (ya normalizado, tal como lo devuelve `resolver_canton_bce()`)… (+23 more)

### Community 21 - "marts.vw_cartera_market_share"
Cohesion: 0.33
Nodes (8): marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.dim_banco, marts.dim_fecha, marts.fact_cartera, marts.fact_depositos

### Community 22 - "11_schema_bce.sql"
Cohesion: 0.21
Nodes (11): marts.fact_tasas_activas, marts.fact_tasas_pasivas, raw.bce_tasas_activas, raw.bce_tasas_pasivas, marts.dim_banco, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo (+3 more)

### Community 23 - "test_integration_regressions.py"
Cohesion: 0.09
Nodes (38): upsert_staging_bce_tasas_pasivas(), upsert_staging_boletin_balance(), integration, _bce_tasas_pasivas_row(), _boletin_balance_row(), _cleanup_bce_tasas_pasivas(), _cleanup_boletin_balance(), _dim_canton_insert_statement() (+30 more)

### Community 24 - "12_schema_tasas_historicas.sql"
Cohesion: 0.24
Nodes (10): marts.fact_tasas_pasivas_instrumento, marts.fact_tasas_pasivas_plazo, marts.fact_tasas_referenciales_credito, marts.fact_tasas_referenciales_sistema, raw.tasas_referenciales, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo (+2 more)

### Community 25 - "compute_indicadores_excel.py"
Cohesion: 0.33
Nodes (9): cod(), main(), promedio_ytd(), Motor de referencia del catálogo `IND_NN` (indicadores del Excel de…, Promedio de saldos fin de mes de `codigo` (1=activo, 3=patrimonio), desde…, rd_one(), rd_years(), segmento_bruto() (+1 more)

### Community 26 - "13_schema_boletin.sql"
Cohesion: 0.29
Nodes (9): marts.dim_cuenta_contable, marts.fact_balance, marts.fact_pyg, raw.boletin_balance, raw.boletin_pyg, marts.dim_banco, marts.dim_fecha, staging.boletin_balance (+1 more)

### Community 27 - "Propuesta: escalabilidad de ETL, reglas de QA, alineación de config y `black`+`ruff`"
Cohesion: 0.07
Nodes (26): 0. Línea base verificada (para que la propuesta no asuma de más), 1.1 `etl/sources.yml` vs. tuplas hardcodeadas — veredicto: **no todavía, y no como se pediría por defecto**, 1.2 Retry/backoff en extractores, 1.3 Logging estructurado con correlación por corrida, 1.4 Exit codes no triviales, 1.5 Orquestación proporcional a la cadencia real — por qué no Airflow, 1. Escalabilidad del pipeline, 2.1 Invariantes de CDC/idempotencia que nunca deben regresar (+18 more)

### Community 28 - "marts.vw_cartera_market_share"
Cohesion: 0.33
Nodes (8): marts.fact_saldo_depositos, marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.dim_banco, marts.dim_fecha, marts.fact_saldo_cartera

### Community 29 - "pageOrder"
Cohesion: 0.22
Nodes (8): activePageName, pageOrder, $schema, page-benchmark-banco, page-correlacion, page-geografico, page-overview, page-tendencias

### Community 30 - "marts.fact_saldo_cartera_new"
Cohesion: 0.31
Nodes (8): marts.fact_saldo_cartera_new, marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.dim_banco, marts.dim_canton, marts.dim_fecha, marts.dim_segmento_credito, marts.fact_saldo_cartera

### Community 31 - "03_schema_marts.sql"
Cohesion: 0.54
Nodes (7): marts.dim_banco, marts.dim_canton, marts.dim_fecha, marts.dim_producto_cartera, marts.dim_producto_deposito, marts.fact_cartera, marts.fact_depositos

### Community 32 - "page-benchmark-banco/page.json"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 33 - "page-correlacion/page.json"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 34 - "page-geografico/page.json"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 35 - "page-overview/page.json"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 36 - "page-tendencias/page.json"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 37 - "editorSettings.json"
Cohesion: 0.29
Nodes (6): autodetectRelationships, parallelQueryLoading, relationshipImportEnabled, $schema, shouldNotifyUserOfNameConflictResolution, typeDetectionEnabled

### Community 39 - "01_schema_raw.sql"
Cohesion: 0.50
Nodes (3): raw.cartera, raw.depositos, raw.source_files

### Community 40 - "08_dim_segmento_categoria_plazo.sql"
Cohesion: 0.50
Nodes (3): marts.dim_categoria_deposito, marts.dim_plazo, marts.dim_segmento_credito

### Community 95 - "marts.vw_dim_canton_geografia"
Cohesion: 0.50
Nodes (3): marts.dim_provincia, marts.vw_dim_canton_geografia, marts.dim_canton

### Community 99 - "Gobernanza de datos"
Cohesion: 0.06
Nodes (29): Arquitectura, Bug real encontrado y corregido: NULL en `UNIQUE`/`ON CONFLICT`, Carga incremental (CDC) — no full refresh, Catálogos conformados (identidad compartida entre fuentes), Estructura real de los archivos fuente (verificado, no solo la ficha metodológica), Evaluación de escalabilidad, Flujo de datos, Modelo de datos (esquema estrella) (+21 more)

### Community 100 - "position"
Cohesion: 0.07
Nodes (27): projections, filterConfig, filters, name, position, height, tabOrder, width (+19 more)

### Community 101 - "settings"
Cohesion: 0.09
Nodes (23): name, reportVersionAtImport, type, name, reportVersionAtImport, type, objects, outspacePane (+15 more)

### Community 102 - "Dimensiones"
Cohesion: 0.09
Nodes (22): Decisiones de modelado relevantes, Diccionario de datos, Dimensiones, Hechos, marts.dim_banco, marts.dim_canton, marts.dim_categoria_deposito, marts.dim_cuenta_contable (plan de cuentas del Boletín, BALANCE + PYG) (+14 more)

### Community 103 - "position"
Cohesion: 0.07
Nodes (27): projections, filterConfig, filters, name, dataPoint, position, height, tabOrder (+19 more)

### Community 104 - "position"
Cohesion: 0.08
Nodes (23): projections, filterConfig, filters, name, position, height, tabOrder, width (+15 more)

### Community 105 - "position"
Cohesion: 0.08
Nodes (23): projections, filterConfig, filters, name, position, height, tabOrder, width (+15 more)

### Community 106 - "position"
Cohesion: 0.08
Nodes (23): projections, filterConfig, filters, name, position, height, tabOrder, width (+15 more)

### Community 107 - "position"
Cohesion: 0.08
Nodes (23): projections, filterConfig, filters, name, position, height, tabOrder, width (+15 more)

### Community 108 - "position"
Cohesion: 0.08
Nodes (25): name, general, header, selection, position, height, tabOrder, width (+17 more)

### Community 109 - "position"
Cohesion: 0.08
Nodes (25): name, general, header, selection, position, height, tabOrder, width (+17 more)

### Community 110 - "position"
Cohesion: 0.08
Nodes (25): name, general, header, selection, position, height, tabOrder, width (+17 more)

### Community 111 - "4. SEPS — Cooperativas de Ahorro y Crédito + Mutualistas de Vivienda — ✅ **implementada y cargada 2021-2025 (2026-09-30)**"
Cohesion: 0.08
Nodes (23): 1.1 Banca Pública (`capcol-instituciones-publicas/`) — ✅ diseño confirmado, esquema ya soporta la carga (2026-09-01), 1. CAPCOL — Cartera y Depósitos (Superbancos) — ✅ integrada, 2.1 `tsp_desde_200801.zip` (tasas pasivas / captaciones), 2.2 `tsa_desde_200801.zip` (tasas activas / colocaciones) — ✅ confirmado, 2.3 Tasas máximas y referenciales por segmento (`TasasHistorico.htm`) — ✅ cargado (Paso 4), 2.4 Mapeo `razon_social`/`ruc` (BCE) ↔ `banco` (CAPCOL/`marts.dim_banco`) — investigado, 2. BCE — Tasas de interés activas y pasivas (semanal) — 🔎 en investigación, 3.1 Hoja `BALANCE` (1399 filas x 35 columnas) (+15 more)

### Community 112 - "Linaje de datos"
Cohesion: 0.18
Nodes (10): 1. CAPCOL — Cartera, 2. CAPCOL — Depósitos, 3. BCE — tsp (tasas pasivas, semanal), 4. BCE — tsa (tasas activas, semanal), 5. BCE — `TasasHistorico.htm` (techos y referenciales, mensual, nivel sistema), 6. Boletín Financiero Mensual — BALANCE / PYG, 7. SEPS — Captaciones, Colocaciones (saldos) y Estados Financieros (2026-09-30), Linaje de datos (+2 more)

### Community 113 - "page-prototipo-diseno/page.json"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 114 - "Benchmark de cartera, depósitos y tasas — bancos privados del Ecuador"
Cohesion: 0.25
Nodes (7): Alcance de los datos, Benchmark de cartera, depósitos y tasas — bancos privados del Ecuador, Estado del proyecto, Estructura, Quickstart, Qué incluye, Tests y CI

### Community 115 - "Muestras de `marts.*` en Parquet"
Cohesion: 0.40
Nodes (4): `marts_AAAA-MM/` (muestra de un mes), `marts_ultimos_5_anios/`, Muestras de `marts.*` en Parquet, Uso típico

### Community 117 - "prototipo-diseno-bi.Report/definition/pages/pages.json"
Cohesion: 0.40
Nodes (4): activePageName, pageOrder, $schema, page-prototipo-diseno

### Community 128 - "config.py"
Cohesion: 0.06
Nodes (44): export_full(), export_sample(), Path, Exporta marts.* a Parquet, para poder probar el modelo de datos (Power BI,…, download_all(), download_bce_file(), Path, Descarga directa de los archivos semanales de tasas de interés del BCE… (+36 more)

### Community 130 - "Mantenimiento de catálogos / resolución de identidad"
Cohesion: 0.11
Nodes (17): 1. `dim_banco` — camino curado (33 bancos privados), 2. `dim_banco` — camino auto-registrado (409 entidades no-privadas), 3. `dim_segmento_credito` / `dim_subsegmento_credito`, 4. `dim_categoria_deposito`, 5. `dim_segmento_entidad`, 6. `dim_plazo` (two-tier, 4 puntos de entrada), 7. `dim_cuenta_contable`, 8. `dim_canton` (two-tier, BCE tsp/tsa — 2026-09-01, `sql/28_bce_canton_grain.sql`) (+9 more)

### Community 137 - "parse_seps.py"
Cohesion: 0.08
Nodes (49): SEPS escribe las categorías sin tilde ('DEPOSITOS A LA VISTA', 'DEPOSITOS DE…, resolver_categoria_deposito_seps(), _sin_tildes(), _a_numero(), _chunks(), extraer_zip_seps(), _fecha_corte(), _geo() (+41 more)

### Community 138 - "parse_bce_tasas.py"
Cohesion: 0.06
Nodes (57): Chequeo de dos niveles para TODOS los valores crudos de `plazo` observados en…, Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto…, resolver_plazo_bce(), validar_universo_plazos_bce(), _add_common_columns(), parse_tsa_file(), parse_tsp_file(), DataFrame (+49 more)

### Community 142 - "pipeline.py"
Cohesion: 0.20
Nodes (24): Connection, get_connection(), is_source_loaded(), Vacía staging.bce_tasas_pasivas/activas -- necesario ÚNICAMENTE para el…, Registra el RUC de TODAS las entidades resueltas por BCE (bancos privados…, refresh_marts(), register_source_file(), truncate_staging_bce() (+16 more)

### Community 143 - "load_postgres.py"
Cohesion: 0.20
Nodes (23): _clean(), _copy_rows(), insert_dim_cuenta_contable_seps(), load_raw(), load_raw_bce(), load_raw_boletin(), load_raw_tasas_referenciales(), DataFrame (+15 more)

### Community 146 - "sha256_file"
Cohesion: 0.70
Nodes (4): sha256_file(), Path, test_sha256_file_is_content_sensitive(), test_sha256_file_is_deterministic()

## Knowledge Gaps
- **549 isolated node(s):** `marts.dim_fecha (grano día)`, `marts.dim_banco`, `marts.dim_provincia (2026-07-25, `sql/20_dim_provincia.sql`)`, `marts.dim_canton`, `marts.dim_segmento_entidad (2026-07-25, `sql/19_dim_segmento_entidad.sql`)` (+544 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **64 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `resolver_canton_bce()` connect `resolver_canton_bce` to `parse_seps.py`, `parse_bce_tasas.py`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Why does `resolver_plazo_bce()` connect `parse_bce_tasas.py` to `test_parse_tasas_historicas.py`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._
- **Why does `resolver_categoria_deposito()` connect `test_parse_tasas_historicas.py` to `parse_depositos_file`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `load_seps()` (e.g. with `upsert_staging_cartera()` and `upsert_staging_depositos()`) actually correct?**
  _`load_seps()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `parse_seps_eeff_file()` (e.g. with `_codigo_padre()` and `month_end_date()`) actually correct?**
  _`parse_seps_eeff_file()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `marts.dim_fecha (grano día)`, `marts.dim_banco`, `marts.dim_provincia (2026-07-25, `sql/20_dim_provincia.sql`)` to the rest of the system?**
  _549 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `benchmark_cartera_depositos` be split into smaller, more focused modules?**
  _Cohesion score 0.10121951219512196 - nodes in this community are weakly interconnected._