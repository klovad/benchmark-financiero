# Graph Report - benchmark-bancos  (2026-10-06)

## Corpus Check
- 131 files · ~109,572 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1515 nodes · 2053 edges · 172 communities (91 shown, 81 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1f8b37a7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- load_postgres.py
- benchmark_cartera_depositos
- pipeline.py
- Prototipo de diseño Power BI — tema "Libro Mayor", personalización y plantilla de página
- banco_matching.py
- PlazoNoResueltoError
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
- marts.fact_tasas_activas
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
- config/__init__.py
- 08_dim_segmento_categoria_plazo.sql
- version.json
- 02_schema_staging.sql
- 07_dim_banco_dim_fecha_rebuild.sql
- 16_dim_segmento_normativo.sql
- 19_dim_segmento_entidad.sql
- 20_dim_provincia.sql
- parse_seps.py
- setup_logging
- export_sample_parquet.py
- sha256_file
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
- scrape_boletin.py
- 01_schema_meta.sql
- settings.py
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
- Benchmark de cartera, depósitos y tasas — sistema financiero del Ecuador
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
- _log_bancos_no_resueltos
- staging.bce_tasas_pasivas
- Mantenimiento de catálogos / resolución de identidad
- marts.fact_captaciones_depositos
- marts.fact_colocaciones_cartera
- staging.bce_tasas_activas
- staging.bce_tasas_pasivas
- marts.dim_plazo
- resolver_categoria_deposito
- parse_bce_tasas.py
- _log_cantones_no_resueltos
- marts.vw_cartera_bruta
- benchmark-bancos
- marts.dim_banco
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
- cli.py
- parse_fecha_from_boletin_filename

## God Nodes (most connected - your core abstractions)
1. `resolver_canton_bce()` - 27 edges
2. `resolver_banco_codigo()` - 23 edges
3. `sha256_file()` - 21 edges
4. `parse_depositos_file()` - 20 edges
5. `load_seps()` - 19 edges
6. `parse_seps_colocaciones_file()` - 19 edges
7. `parse_seps_eeff_file()` - 19 edges
8. `parse_seps_captaciones_file()` - 17 edges
9. `load_bce()` - 16 edges
10. `resolver_categoria_deposito()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_resolver_entidad_seps_reusa_llave_bce_y_rellena_ruc_numerico()` --uses--> `RucInvalidoError`  [INFERRED]
  tests/test_parse_seps.py → src/benchmark_bancos/transform/banco_matching.py
- `test_plazo_bucket_shape_valido_pero_rango_invertido_lanza_plazo_error()` --uses--> `PlazoNoResueltoError`  [INFERRED]
  tests/test_categoria_deposito_matching.py → src/benchmark_bancos/transform/bce_plazo_matching.py
- `test_resolve_canton_propaga_cantonnoresueltoerror()` --uses--> `CantonNoResueltoError`  [INFERRED]
  tests/test_parse_bce_tasas.py → src/benchmark_bancos/transform/canton_matching.py
- `test_codigo_padre_sigue_la_jerarquia_del_catalogo_unico_de_cuentas()` --calls--> `_codigo_padre()`  [EXTRACTED]
  tests/test_parse_boletin.py → src/benchmark_bancos/transform/parse_boletin.py
- `_a_numero()` --references--> `Series`  [EXTRACTED]
  src/benchmark_bancos/transform/parse_seps.py → powerbi/benchmark-cartera-depositos.Report/definition/pages/page-tendencias/visuals/v01LineEstacionalidad/visual.json

## Import Cycles
- None detected.

## Communities (172 total, 81 thin omitted)

### Community 0 - "load_postgres.py"
Cohesion: 0.14
Nodes (27): _cdc_guard(), _clean(), _copy_rows(), _crear_fuentes_incrementales(), insert_dim_cuenta_contable_seps(), _leer_watermark(), load_banco_maestro_seed(), DataFrame (+19 more)

### Community 1 - "benchmark_cartera_depositos"
Cohesion: 0.10
Nodes (40): "marts"."dim_banco", "marts"."dim_canton", "marts"."dim_categoria_deposito", "marts"."dim_cuenta_contable", "marts"."dim_fecha", "marts"."dim_plazo", "marts"."dim_provincia", "marts"."dim_segmento_credito" (+32 more)

### Community 2 - "pipeline.py"
Cohesion: 0.16
Nodes (27): Connection, main(), download_tasas_historicas(), _meses_hasta_hoy(), Path, Descarga de las páginas mensuales TasasVigentes{MM}{YYYY}.htm del BCE (techos…, get_connection(), is_source_loaded() (+19 more)

### Community 3 - "Prototipo de diseño Power BI — tema "Libro Mayor", personalización y plantilla de página"
Cohesion: 0.10
Nodes (19): 0. Segundo intento — qué cambió y por qué, 10. Cómo exportar un `.pbit` real desde este prototipo, 11. Cómo abrir y probar el prototipo, 1. Por qué un `.pbip` separado y no una página nueva en el reporte productivo, 2.1 Por qué esto no es "Okabe–Ito con otro nombre", 2.2 Secuencial y qué no tiene campo de tema global, 2. Paleta de color — "Libro Mayor", 3. Tipografía (+11 more)

### Community 4 - "banco_matching.py"
Cohesion: 0.09
Nodes (43): BancoNoResueltoError, _cargar_csv(), _crosswalk(), EntidadBceNoMapeadaError, maestro(), _normalizar(), _por_regla(), Path (+35 more)

### Community 5 - "PlazoNoResueltoError"
Cohesion: 0.06
Nodes (56): PlazoNoResueltoError, ValueError, Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de…, Chequeo de dos niveles para TODOS los valores crudos de `plazo` observados en…, Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto…, El texto crudo de plazo no matchea ningún patrón conocido (shape inválido), o…, Sanity check de rango, aplicado DESPUÉS de que el shape ya matcheó un patrón…, resolver_plazo_bce() (+48 more)

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
Nodes (14): marts.vw_activo_promedio_ytd, marts.vw_cartera_bruta, marts.vw_cartera_bruta_segmento, marts.vw_cartera_improductiva, marts.vw_cartera_improductiva_segmento, marts.vw_depositos_corto_plazo, marts.vw_patrimonio_promedio_ytd, marts.vw_pyg_total_gastos (+6 more)

### Community 20 - "resolver_canton_bce"
Cohesion: 0.09
Nodes (29): CantonNoResueltoError, es_canton_conocido(), normalize_canton(), ValueError, Resuelve el par (canton, provincia) crudo del BCE (tsp/tsa) contra el catálogo…, Universo de 228 pares (canton, provincia) ya sembrados en `marts.dim_canton`…, Resuelve un par crudo (canton, provincia) de BCE tsp/tsa al par normalizado…, True si el par (ya normalizado, tal como lo devuelve `resolver_canton_bce()`)… (+21 more)

### Community 21 - "marts.vw_cartera_market_share"
Cohesion: 0.33
Nodes (8): marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.dim_banco, marts.dim_fecha, marts.fact_cartera, marts.fact_depositos

### Community 22 - "marts.fact_tasas_activas"
Cohesion: 0.27
Nodes (9): marts.fact_tasas_activas, marts.fact_tasas_pasivas, marts.dim_banco, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo, marts.dim_segmento_credito, staging.bce_tasas_activas (+1 more)

### Community 23 - "test_integration_regressions.py"
Cohesion: 0.09
Nodes (38): integration, _bce_tasas_pasivas_row(), _boletin_balance_row(), _cleanup_bce_tasas_pasivas(), _cleanup_boletin_balance(), _dim_canton_insert_statement(), _fact_saldo_cartera_pivot_statement(), Tests de integración (@pytest.mark.integration): requieren Postgres real ya… (+30 more)

### Community 24 - "12_schema_tasas_historicas.sql"
Cohesion: 0.27
Nodes (9): marts.fact_tasas_pasivas_instrumento, marts.fact_tasas_pasivas_plazo, marts.fact_tasas_referenciales_credito, marts.fact_tasas_referenciales_sistema, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo, marts.dim_segmento_credito (+1 more)

### Community 25 - "compute_indicadores_excel.py"
Cohesion: 0.33
Nodes (9): cod(), main(), promedio_ytd(), Motor de referencia del catálogo `IND_NN` (indicadores del Excel de…, Promedio de saldos fin de mes de `codigo` (1=activo, 3=patrimonio), desde…, rd_one(), rd_years(), segmento_bruto() (+1 more)

### Community 26 - "13_schema_boletin.sql"
Cohesion: 0.39
Nodes (7): marts.dim_cuenta_contable, marts.fact_balance, marts.fact_pyg, marts.dim_banco, marts.dim_fecha, staging.boletin_balance, staging.boletin_pyg

### Community 27 - "Propuesta: escalabilidad de ETL, reglas de QA, alineación de config y `black`+`ruff`"
Cohesion: 0.07
Nodes (26): 0. Línea base verificada (para que la propuesta no asuma de más), 1.1 `src/benchmark_bancos/sources.yml` vs. tuplas hardcodeadas — veredicto: **no todavía, y no como se pediría por defecto**, 1.2 Retry/backoff en extractores, 1.3 Logging estructurado con correlación por corrida, 1.4 Exit codes no triviales, 1.5 Orquestación proporcional a la cadencia real — por qué no Airflow, 1. Escalabilidad del pipeline, 2.1 Invariantes de CDC/idempotencia que nunca deben regresar (+18 more)

### Community 28 - "marts.vw_cartera_market_share"
Cohesion: 0.33
Nodes (8): marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.dim_banco, marts.dim_fecha, marts.fact_saldo_cartera, marts.fact_saldo_depositos

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

### Community 39 - "config/__init__.py"
Cohesion: 0.20
Nodes (6): fixture, Catálogos de dominio usados por los parsers: mapeos de vocabulario de las…, Configuración del proyecto, separada por responsabilidad: - `settings`: lo que…, Constantes de las fuentes externas: URLs, sub-portales, nombres de carpeta, ids…, db_conn(), Conexión a Postgres real para tests marcados @pytest.mark.integration. Nunca…

### Community 40 - "08_dim_segmento_categoria_plazo.sql"
Cohesion: 0.50
Nodes (3): marts.dim_categoria_deposito, marts.dim_plazo, marts.dim_segmento_credito

### Community 47 - "parse_seps.py"
Cohesion: 0.08
Nodes (48): Resuelve una entidad SEPS (cooperativa, mutualista o entidad de segundo piso) a…, resolver_entidad_seps(), _codigo_padre(), _a_numero(), _chunks(), extraer_zip_seps(), _fecha_corte(), _geo() (+40 more)

### Community 48 - "setup_logging"
Cohesion: 0.15
Nodes (15): LogRecord, download_all(), download_bce_file(), Path, Descarga directa de los archivos semanales de tasas de interés del BCE…, clave: 'tsp' o 'tsa'. Descarga si no existe ya un archivo con ese nombre., download_seps(), download_seps_file() (+7 more)

### Community 49 - "export_sample_parquet.py"
Cohesion: 0.50
Nodes (4): export_full(), export_sample(), Path, Exporta marts.* a Parquet, para poder probar el modelo de datos (Power BI,…

### Community 50 - "sha256_file"
Cohesion: 0.07
Nodes (57): extract_single_xlsx(), find_base_sheets(), month_end_date(), normalize_banco(), normalize_provincia(), normalize_text(), Path, Los ZIP de Superbancos contienen exactamente un .xlsx -- salvo boletines… (+49 more)

### Community 74 - "scrape_boletin.py"
Cohesion: 0.42
Nodes (8): _download_all_files(), main(), _open_year_folder(), Path, Descarga los ZIP del Boletín Financiero Mensual (Balance y PyG) de bancos…, _reset_to_root(), scrape(), scrape_year()

### Community 76 - "settings.py"
Cohesion: 0.50
Nodes (3): _find_project_root(), Path, Configuración que depende del entorno: rutas, base de datos y años a procesar.…

### Community 95 - "marts.vw_dim_canton_geografia"
Cohesion: 0.50
Nodes (3): marts.dim_provincia, marts.vw_dim_canton_geografia, marts.dim_canton

### Community 99 - "Gobernanza de datos"
Cohesion: 0.06
Nodes (30): Arquitectura, Bug real encontrado y corregido: NULL en `UNIQUE`/`ON CONFLICT`, Carga incremental (CDC) — no full refresh, Catálogos conformados (identidad compartida entre fuentes), Estructura real de los archivos fuente (verificado, no solo la ficha metodológica), Evaluación de escalabilidad, Flujo de datos, Modelo de datos (esquema estrella) (+22 more)

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
Nodes (23): 1.1 Banca Pública (`capcol-instituciones-publicas/`) — ✅ cargada 2021-2025 (2026-10-01), 1. CAPCOL — Cartera y Depósitos (Superbancos) — ✅ integrada, 2.1 `tsp_desde_200801.zip` (tasas pasivas / captaciones), 2.2 `tsa_desde_200801.zip` (tasas activas / colocaciones) — ✅ confirmado, 2.3 Tasas máximas y referenciales por segmento (`TasasHistorico.htm`) — ✅ cargado (Paso 4), 2.4 Mapeo `razon_social`/`ruc` (BCE) ↔ `banco` (CAPCOL/`marts.dim_banco`) — investigado, 2. BCE — Tasas de interés activas y pasivas (semanal) — 🔎 en investigación, 3.1 Hoja `BALANCE` (1399 filas x 35 columnas) (+15 more)

### Community 112 - "Linaje de datos"
Cohesion: 0.18
Nodes (10): 1. CAPCOL — Cartera, 2. CAPCOL — Depósitos, 3. BCE — tsp (tasas pasivas, semanal), 4. BCE — tsa (tasas activas, semanal), 5. BCE — `TasasHistorico.htm` (techos y referenciales, mensual, nivel sistema), 6. Boletín Financiero Mensual — BALANCE / PYG, 7. SEPS — Captaciones, Colocaciones (saldos) y Estados Financieros (2026-09-30), Linaje de datos (+2 more)

### Community 113 - "page-prototipo-diseno/page.json"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 114 - "Benchmark de cartera, depósitos y tasas — sistema financiero del Ecuador"
Cohesion: 0.25
Nodes (7): Alcance de los datos, Benchmark de cartera, depósitos y tasas — sistema financiero del Ecuador, Estado del proyecto, Estructura, Quickstart, Qué incluye, Tests y CI

### Community 115 - "Muestras de `marts.*` en Parquet"
Cohesion: 0.40
Nodes (4): `marts_AAAA-MM/` (muestra de un mes), `marts_ultimos_5_anios/`, Muestras de `marts.*` en Parquet, Uso típico

### Community 117 - "prototipo-diseno-bi.Report/definition/pages/pages.json"
Cohesion: 0.40
Nodes (4): activePageName, pageOrder, $schema, page-prototipo-diseno

### Community 130 - "Mantenimiento de catálogos / resolución de identidad"
Cohesion: 0.11
Nodes (17): 1. `dim_banco` — camino curado (33 bancos privados + 3 públicos), 2. `dim_banco` — camino auto-registrado (408 entidades no curadas, BCE y SEPS), 3. `dim_segmento_credito` / `dim_subsegmento_credito`, 4. `dim_categoria_deposito`, 5. `dim_segmento_entidad`, 6. `dim_plazo` (two-tier, 4 puntos de entrada), 7. `dim_cuenta_contable`, 8. `dim_canton` (two-tier, BCE tsp/tsa — 2026-09-01, `sql/28_bce_canton_grain.sql`) (+9 more)

### Community 137 - "resolver_categoria_deposito"
Cohesion: 0.14
Nodes (23): CategoriaNoResueltaError, ValueError, Resuelve el texto crudo de `tipo_deposito` (CAPCOL) o `instrumento_captacion`…, SEPS escribe las categorías sin tilde ('DEPOSITOS A LA VISTA', 'DEPOSITOS DE…, El texto crudo no es ni una categoría conocida ni un bucket de plazo…, Devuelve (categoria, dias_desde, dias_hasta). dias_* son None salvo que la…, resolver_categoria_deposito(), resolver_categoria_deposito_seps() (+15 more)

### Community 138 - "parse_bce_tasas.py"
Cohesion: 0.11
Nodes (36): _add_common_columns(), parse_tsa_file(), parse_tsp_file(), DataFrame, Path, ValueError, Parser de los archivos semanales de tasas de interés del BCE (tsp=pasivas,…, segmento_credito de tsa no está en el universo sembrado de… (+28 more)

### Community 142 - "marts.vw_cartera_bruta"
Cohesion: 0.60
Nodes (4): marts.vw_cartera_bruta, marts.vw_cartera_improductiva_segmento, marts.dim_cuenta_contable, marts.fact_balance

### Community 184 - "cli.py"
Cohesion: 0.16
Nodes (14): ArgumentParser, Punto de entrada del proyecto. uv run main.py <etapa> [opciones] Delega en…, build_parser(), Interfaz de línea de comandos del pipeline. Uso (con uv): uv run benchmark-…, _download_all_files(), main(), _open_report_folder(), _open_year_folder() (+6 more)

### Community 185 - "parse_fecha_from_boletin_filename"
Cohesion: 0.23
Nodes (11): parse_fecha_from_boletin_filename(), parse_fecha_from_tasas_historicas_filename(), date, Extrae la fecha (fin de mes) de un nombre de archivo TasasVigenteMMAAAA.htm.…, Extrae la fecha (fin de mes) de un nombre de archivo 'Boletín Bancos <MES_ES>…, Tests puros (sin DB ni red) para las funciones de fecha-desde-nombre-de-archivo…, test_parse_fecha_boletin_no_matching_pattern_raises(), test_parse_fecha_boletin_unrecognized_month_raises() (+3 more)

## Knowledge Gaps
- **545 isolated node(s):** `$schema`, `name`, `displayName`, `displayOption`, `height` (+540 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **81 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `resolver_canton_bce()` connect `resolver_canton_bce` to `sha256_file`, `parse_seps.py`, `parse_bce_tasas.py`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Why does `resolver_categoria_deposito()` connect `resolver_categoria_deposito` to `sha256_file`, `PlazoNoResueltoError`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **Why does `resolver_entidad_seps()` connect `parse_seps.py` to `banco_matching.py`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `load_seps()` (e.g. with `upsert_staging_cartera()` and `upsert_staging_depositos()`) actually correct?**
  _`load_seps()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `name`, `displayName` to the rest of the system?**
  _545 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `load_postgres.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._
- **Should `benchmark_cartera_depositos` be split into smaller, more focused modules?**
  _Cohesion score 0.10121951219512196 - nodes in this community are weakly interconnected._