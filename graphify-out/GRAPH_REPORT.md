# Graph Report - benchmark-bancos  (2026-09-30)

## Corpus Check
- 116 files · ~98,792 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1402 nodes · 1865 edges · 144 communities (85 shown, 59 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7b946060`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PlazoNoResueltoError
- benchmark_cartera_depositos
- parse_boletin.py
- Prototipo de diseño Power BI — tema "Libro Mayor", personalización y plantilla de página
- resolver_banco_codigo
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
- pipeline.py
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
- 4. SEPS — Cooperativas de Ahorro y Crédito + Mutualistas de Vivienda — 🔎 **re-verificado con archivos reales 2025 (2026-09-29)**, no implementada
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
- scrape_superbancos.py
- staging.bce_tasas_pasivas
- Mantenimiento de catálogos / resolución de identidad
- marts.fact_captaciones_depositos
- marts.fact_colocaciones_cartera
- staging.bce_tasas_activas
- staging.bce_tasas_pasivas
- marts.dim_plazo
- resolver_categoria_deposito
- parse_bce_tasas.py
- parse_cartera_file
- common.py
- config.py
- parse_depositos_file
- sha256_file

## God Nodes (most connected - your core abstractions)
1. `resolver_canton_bce()` - 26 edges
2. `resolver_banco_codigo()` - 22 edges
3. `parse_depositos_file()` - 21 edges
4. `PlazoNoResueltoError` - 17 edges
5. `resolver_categoria_deposito()` - 16 edges
6. `resolver_entidad_bce()` - 16 edges
7. `load_bce()` - 15 edges
8. `load_boletin()` - 15 edges
9. `parse_cartera_file()` - 15 edges
10. `resolver_plazo_bce()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `test_plazo_bucket_shape_valido_pero_rango_invertido_lanza_plazo_error()` --uses--> `PlazoNoResueltoError`  [INFERRED]
  tests/test_categoria_deposito_matching.py → etl/transform/bce_plazo_matching.py
- `test_resolver_plazo_shape_invalido_sigue_lanzando()` --uses--> `PlazoNoResueltoError`  [INFERRED]
  tests/test_parse_tasas_historicas.py → etl/transform/bce_plazo_matching.py
- `test_resolver_plazo_shape_valido_pero_rango_invertido_lanza_error()` --uses--> `PlazoNoResueltoError`  [INFERRED]
  tests/test_parse_tasas_historicas.py → etl/transform/bce_plazo_matching.py
- `test_resolve_canton_propaga_cantonnoresueltoerror()` --uses--> `CantonNoResueltoError`  [INFERRED]
  tests/test_parse_bce_tasas.py → etl/transform/canton_matching.py
- `test_parse_fecha_tasas_historicas_no_matching_pattern_raises()` --calls--> `parse_fecha_from_tasas_historicas_filename()`  [EXTRACTED]
  tests/test_pipeline_fecha_parsing.py → etl/pipeline.py

## Import Cycles
- None detected.

## Communities (144 total, 59 thin omitted)

### Community 0 - "PlazoNoResueltoError"
Cohesion: 0.13
Nodes (27): PlazoNoResueltoError, ValueError, Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de…, Chequeo de dos niveles para TODOS los valores crudos de `plazo` observados en…, Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto…, El texto crudo de plazo no matchea ningún patrón conocido (shape inválido), o…, Sanity check de rango, aplicado DESPUÉS de que el shape ya matcheó un patrón…, resolver_plazo_bce() (+19 more)

### Community 1 - "benchmark_cartera_depositos"
Cohesion: 0.10
Nodes (40): "marts"."dim_banco", "marts"."dim_canton", "marts"."dim_categoria_deposito", "marts"."dim_cuenta_contable", "marts"."dim_fecha", "marts"."dim_plazo", "marts"."dim_provincia", "marts"."dim_segmento_credito" (+32 more)

### Community 2 - "parse_boletin.py"
Cohesion: 0.17
Nodes (18): normalize_text(), _codigo_padre(), _find_header_row(), _normalize_col(), parse_boletin_file(), _parse_hoja(), _parse_met(), DataFrame (+10 more)

### Community 3 - "Prototipo de diseño Power BI — tema "Libro Mayor", personalización y plantilla de página"
Cohesion: 0.10
Nodes (19): 0. Segundo intento — qué cambió y por qué, 10. Cómo exportar un `.pbit` real desde este prototipo, 11. Cómo abrir y probar el prototipo, 1. Por qué un `.pbip` separado y no una página nueva en el reporte productivo, 2.1 Por qué esto no es "Okabe–Ito con otro nombre", 2.2 Secuencial y qué no tiene campo de tema global, 2. Paleta de color — "Libro Mayor", 3. Tipografía (+11 more)

### Community 4 - "resolver_banco_codigo"
Cohesion: 0.09
Nodes (42): BancoNoResueltoError, _cargar_csv(), _crosswalk(), EntidadBceNoMapeadaError, maestro(), _normalizar(), _por_regla(), Path (+34 more)

### Community 5 - "test_parse_tasas_historicas.py"
Cohesion: 0.12
Nodes (29): _categoria_label(), _clean_label(), _emitir(), _parse_filas(), parse_tasas_historicas_file(), DataFrame, Path, Parser de las páginas mensuales TasasVigentes{MM}{YYYY}.htm del BCE. Cada… (+21 more)

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
Nodes (29): CantonNoResueltoError, es_canton_conocido(), normalize_canton(), ValueError, Resuelve el par (canton, provincia) crudo del BCE (tsp/tsa) contra el catálogo…, Universo de 228 pares (canton, provincia) ya sembrados en `marts.dim_canton`…, Resuelve un par crudo (canton, provincia) de BCE tsp/tsa al par normalizado…, True si el par (ya normalizado, tal como lo devuelve `resolver_canton_bce()`)… (+21 more)

### Community 21 - "marts.vw_cartera_market_share"
Cohesion: 0.33
Nodes (8): marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.dim_banco, marts.dim_fecha, marts.fact_cartera, marts.fact_depositos

### Community 22 - "11_schema_bce.sql"
Cohesion: 0.21
Nodes (11): marts.fact_tasas_activas, marts.fact_tasas_pasivas, raw.bce_tasas_activas, raw.bce_tasas_pasivas, marts.dim_banco, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo (+3 more)

### Community 23 - "pipeline.py"
Cohesion: 0.05
Nodes (96): Connection, date, _clean(), _copy_rows(), get_connection(), is_source_loaded(), load_banco_maestro_seed(), load_raw() (+88 more)

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
Cohesion: 0.07
Nodes (26): Arquitectura, Bug real encontrado y corregido: NULL en `UNIQUE`/`ON CONFLICT`, Carga incremental (CDC) — no full refresh, Catálogos conformados (identidad compartida entre fuentes), Estructura real de los archivos fuente (verificado, no solo la ficha metodológica), Evaluación de escalabilidad, Flujo de datos, Modelo de datos (esquema estrella) (+18 more)

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

### Community 111 - "4. SEPS — Cooperativas de Ahorro y Crédito + Mutualistas de Vivienda — 🔎 **re-verificado con archivos reales 2025 (2026-09-29)**, no implementada"
Cohesion: 0.08
Nodes (23): 1.1 Banca Pública (`capcol-instituciones-publicas/`) — ✅ diseño confirmado, esquema ya soporta la carga (2026-09-01), 1. CAPCOL — Cartera y Depósitos (Superbancos) — ✅ integrada, 2.1 `tsp_desde_200801.zip` (tasas pasivas / captaciones), 2.2 `tsa_desde_200801.zip` (tasas activas / colocaciones) — ✅ confirmado, 2.3 Tasas máximas y referenciales por segmento (`TasasHistorico.htm`) — ✅ cargado (Paso 4), 2.4 Mapeo `razon_social`/`ruc` (BCE) ↔ `banco` (CAPCOL/`marts.dim_banco`) — investigado, 2. BCE — Tasas de interés activas y pasivas (semanal) — 🔎 en investigación, 3.1 Hoja `BALANCE` (1399 filas x 35 columnas) (+15 more)

### Community 112 - "Linaje de datos"
Cohesion: 0.20
Nodes (9): 1. CAPCOL — Cartera, 2. CAPCOL — Depósitos, 3. BCE — tsp (tasas pasivas, semanal), 4. BCE — tsa (tasas activas, semanal), 5. BCE — `TasasHistorico.htm` (techos y referenciales, mensual, nivel sistema), 6. Boletín Financiero Mensual — BALANCE / PYG, Linaje de datos, Patrones de transformación transversales (+1 more)

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

### Community 128 - "scrape_superbancos.py"
Cohesion: 0.08
Nodes (32): download_all(), download_bce_file(), Path, Descarga directa de los archivos semanales de tasas de interés del BCE…, clave: 'tsp' o 'tsa'. Descarga si no existe ya un archivo con ese nombre., download_tasas_historicas(), _meses_hasta_hoy(), Path (+24 more)

### Community 130 - "Mantenimiento de catálogos / resolución de identidad"
Cohesion: 0.11
Nodes (17): 1. `dim_banco` — camino curado (33 bancos privados), 2. `dim_banco` — camino auto-registrado (409 entidades no-privadas), 3. `dim_segmento_credito` / `dim_subsegmento_credito`, 4. `dim_categoria_deposito`, 5. `dim_segmento_entidad`, 6. `dim_plazo` (two-tier, 4 puntos de entrada), 7. `dim_cuenta_contable`, 8. `dim_canton` (two-tier, BCE tsp/tsa — 2026-09-01, `sql/28_bce_canton_grain.sql`) (+9 more)

### Community 137 - "resolver_categoria_deposito"
Cohesion: 0.17
Nodes (19): CategoriaNoResueltaError, ValueError, Resuelve el texto crudo de `tipo_deposito` (CAPCOL) o `instrumento_captacion`…, El texto crudo no es ni una categoría conocida ni un bucket de plazo…, Devuelve (categoria, dias_desde, dias_hasta). dias_* son None salvo que la…, resolver_categoria_deposito(), Desde sql/27_dim_plazo_estado_validacion.sql: un texto que matchea el *shape*…, Un texto que no matchea ni _RANGO ni _SIN_TOPE ni CATEGORIAS_VALIDAS sigue… (+11 more)

### Community 138 - "parse_bce_tasas.py"
Cohesion: 0.11
Nodes (36): _add_common_columns(), parse_tsa_file(), parse_tsp_file(), DataFrame, Path, ValueError, Parser de los archivos semanales de tasas de interés del BCE (tsp=pasivas,…, segmento_credito de tsa no está en el universo sembrado de… (+28 more)

### Community 139 - "parse_cartera_file"
Cohesion: 0.23
Nodes (14): parse_cartera_file(), DataFrame, Path, tipo_entidad lo decide el caller según el sub-portal CAPCOL de origen…, _strip_accents(), tipo_credito_from_sheet_name(), _first_file(), Path (+6 more)

### Community 140 - "common.py"
Cohesion: 0.26
Nodes (10): month_end_date(), normalize_banco(), normalize_provincia(), CAPCOL escribe provincias sin tilde (BOLIVAR, GALAPAGOS, LOS RIOS...) pero SÍ…, Las fechas del origen ya vienen como fin de mes (ej. 31/01/2024); se normaliza…, region_for_provincia(), _strip_accents(), _find_header_row() (+2 more)

### Community 141 - "config.py"
Cohesion: 0.22
Nodes (7): export_full(), export_sample(), Path, Exporta marts.* a Parquet, para poder probar el modelo de datos (Power BI,…, fixture, db_conn(), Conexión a Postgres real para tests marcados @pytest.mark.integration. Nunca…

### Community 142 - "parse_depositos_file"
Cohesion: 0.22
Nodes (9): find_base_sheets(), Casi todos los archivos traen 1 sola hoja 'BASE ...', pero el de vivienda trae…, _find_header_row(), parse_depositos_file(), DataFrame, Path, Parser del reporte de depósitos (captaciones) de Superbancos. A diferencia de…, tipo_entidad lo decide el caller según el sub-portal CAPCOL de origen… (+1 more)

### Community 143 - "sha256_file"
Cohesion: 0.36
Nodes (7): extract_single_xlsx(), Path, Los ZIP de Superbancos contienen exactamente un .xlsx -- salvo boletines…, sha256_file(), Path, test_sha256_file_is_content_sensitive(), test_sha256_file_is_deterministic()

## Knowledge Gaps
- **546 isolated node(s):** `1.1 Banca Pública (`capcol-instituciones-publicas/`) — ✅ diseño confirmado, esquema ya soporta la carga (2026-09-01)`, `2.1 `tsp_desde_200801.zip` (tasas pasivas / captaciones)`, `2.2 `tsa_desde_200801.zip` (tasas activas / colocaciones) — ✅ confirmado`, `2.3 Tasas máximas y referenciales por segmento (`TasasHistorico.htm`) — ✅ cargado (Paso 4)`, `2.4 Mapeo `razon_social`/`ruc` (BCE) ↔ `banco` (CAPCOL/`marts.dim_banco`) — investigado` (+541 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **59 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `parse_depositos_file()` connect `parse_depositos_file` to `parse_boletin.py`, `resolver_banco_codigo`, `resolver_categoria_deposito`, `parse_cartera_file`, `common.py`, `sha256_file`, `pipeline.py`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Why does `validar_universo_plazos_bce()` connect `PlazoNoResueltoError` to `parse_bce_tasas.py`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._
- **Why does `resolver_categoria_deposito()` connect `resolver_categoria_deposito` to `PlazoNoResueltoError`, `parse_depositos_file`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `PlazoNoResueltoError` (e.g. with `test_bucket_shape_invalido_sigue_lanzando_incluso_fuera_del_universo()` and `test_bucket_shape_valido_pero_rango_invertido_sigue_lanzando()`) actually correct?**
  _`PlazoNoResueltoError` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `1.1 Banca Pública (`capcol-instituciones-publicas/`) — ✅ diseño confirmado, esquema ya soporta la carga (2026-09-01)`, `2.1 `tsp_desde_200801.zip` (tasas pasivas / captaciones)`, `2.2 `tsa_desde_200801.zip` (tasas activas / colocaciones) — ✅ confirmado` to the rest of the system?**
  _546 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `PlazoNoResueltoError` be split into smaller, more focused modules?**
  _Cohesion score 0.12807881773399016 - nodes in this community are weakly interconnected._
- **Should `benchmark_cartera_depositos` be split into smaller, more focused modules?**
  _Cohesion score 0.10121951219512196 - nodes in this community are weakly interconnected._