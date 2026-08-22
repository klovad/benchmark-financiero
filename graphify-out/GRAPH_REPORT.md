# Graph Report - benchmark-bancos  (2026-08-22)

## Corpus Check
- 83 files · ~47,325 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 742 nodes · 1084 edges · 99 communities (52 shown, 47 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ca77fa87`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pipeline.py
- benchmark_cartera_depositos
- parse_cartera.py
- parse_bce_tasas.py
- resolver_banco_codigo
- test_parse_tasas_historicas.py
- position
- position
- position
- position
- position
- position
- parse_boletin.py
- settings
- position
- position
- position
- position
- position
- 18_glosario_cuentas_views.sql
- resolver_categoria_deposito
- 04_indexes_views.sql
- 11_schema_bce.sql
- scrape_superbancos.py
- 12_schema_tasas_historicas.sql
- compute_indicadores_excel.py
- 13_schema_boletin.sql
- scrape_boletin.py
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
- staging.bce_tasas_activas
- staging.bce_tasas_pasivas
- staging.cartera

## God Nodes (most connected - your core abstractions)
1. `resolver_banco_codigo()` - 23 edges
2. `parse_depositos_file()` - 18 edges
3. `load_bce()` - 17 edges
4. `sha256_file()` - 16 edges
5. `load_boletin()` - 15 edges
6. `load_years()` - 13 edges
7. `parse_tsa_file()` - 13 edges
8. `parse_tsp_file()` - 13 edges
9. `_clean()` - 12 edges
10. `load_tasas_historicas()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `test_empty_value_raises()` --uses--> `CategoriaNoResueltaError`  [INFERRED]
  tests/test_categoria_deposito_matching.py → etl/transform/categoria_deposito_matching.py
- `test_unresolved_value_raises()` --uses--> `CategoriaNoResueltaError`  [INFERRED]
  tests/test_categoria_deposito_matching.py → etl/transform/categoria_deposito_matching.py
- `test_plazo_no_reconocido_lanza_error()` --uses--> `PlazoNoResueltoError`  [INFERRED]
  tests/test_bce_plazo_matching.py → etl/transform/bce_plazo_matching.py
- `test_plazo_vacio_lanza_error()` --uses--> `PlazoNoResueltoError`  [INFERRED]
  tests/test_bce_plazo_matching.py → etl/transform/bce_plazo_matching.py
- `test_empty_name_raises()` --uses--> `BancoNoResueltoError`  [INFERRED]
  tests/test_banco_matching.py → etl/transform/banco_matching.py

## Import Cycles
- None detected.

## Communities (99 total, 47 thin omitted)

### Community 0 - "pipeline.py"
Cohesion: 0.09
Nodes (55): Connection, download_all(), download_bce_file(), Path, Descarga directa de los archivos semanales de tasas de interés del BCE…, clave: 'tsp' o 'tsa'. Descarga si no existe ya un archivo con ese nombre., download_tasas_historicas(), _meses_hasta_hoy() (+47 more)

### Community 1 - "benchmark_cartera_depositos"
Cohesion: 0.10
Nodes (40): "marts"."dim_banco", "marts"."dim_canton", "marts"."dim_categoria_deposito", "marts"."dim_cuenta_contable", "marts"."dim_fecha", "marts"."dim_plazo", "marts"."dim_provincia", "marts"."dim_segmento_credito" (+32 more)

### Community 2 - "parse_cartera.py"
Cohesion: 0.11
Nodes (33): export_full(), export_sample(), Path, Exporta marts.* a Parquet, para poder probar el modelo de datos (Power BI,…, extract_single_xlsx(), find_base_sheets(), month_end_date(), normalize_banco() (+25 more)

### Community 3 - "parse_bce_tasas.py"
Cohesion: 0.11
Nodes (33): PlazoNoResueltoError, ValueError, Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de…, El texto crudo de plazo del BCE no matchea ningún patrón conocido., Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto…, resolver_plazo_bce(), _add_common_columns(), parse_tsa_file() (+25 more)

### Community 4 - "resolver_banco_codigo"
Cohesion: 0.13
Nodes (30): BancoNoResueltoError, _cargar_csv(), _crosswalk(), EntidadBceNoMapeadaError, maestro(), _normalizar(), _por_regla(), Path (+22 more)

### Community 5 - "test_parse_tasas_historicas.py"
Cohesion: 0.17
Nodes (21): _categoria_label(), _clean_label(), _emitir(), _parse_filas(), parse_tasas_historicas_file(), DataFrame, Path, Parser de las páginas mensuales TasasVigentes{MM}{YYYY}.htm del BCE. Cada… (+13 more)

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

### Community 12 - "parse_boletin.py"
Cohesion: 0.17
Nodes (17): _codigo_padre(), _find_header_row(), _normalize_col(), parse_boletin_file(), _parse_hoja(), _parse_met(), DataFrame, Path (+9 more)

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
Nodes (14): marts.dim_cuenta_contable, marts.fact_balance, marts.fact_pyg, marts.vw_activo_promedio_ytd, marts.vw_cartera_bruta, marts.vw_cartera_bruta_segmento, marts.vw_cartera_improductiva, marts.vw_cartera_improductiva_segmento (+6 more)

### Community 20 - "resolver_categoria_deposito"
Cohesion: 0.26
Nodes (12): CategoriaNoResueltaError, ValueError, Resuelve el texto crudo de `tipo_deposito` (CAPCOL) o `instrumento_captacion`…, El texto crudo no es ni una categoría conocida ni un bucket de plazo…, Devuelve (categoria, dias_desde, dias_hasta). dias_* son None salvo que la…, resolver_categoria_deposito(), test_all_13_real_capcol_values_resolve(), test_empty_value_raises() (+4 more)

### Community 21 - "04_indexes_views.sql"
Cohesion: 0.29
Nodes (11): marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_cartera_tasa_ponderada, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.vw_depositos_tasa_ponderada, marts.dim_banco, marts.dim_categoria_deposito (+3 more)

### Community 22 - "11_schema_bce.sql"
Cohesion: 0.21
Nodes (11): marts.fact_tasas_activas, marts.fact_tasas_pasivas, raw.bce_tasas_activas, raw.bce_tasas_pasivas, marts.dim_banco, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo (+3 more)

### Community 23 - "scrape_superbancos.py"
Cohesion: 0.33
Nodes (10): _download_all_files(), main(), _open_report_folder(), _open_year_folder(), Path, Descarga los archivos ZIP de cartera y depósitos del portal CAPCOL de…, Vuelve al listado raíz de años vía el breadcrumb 'Inicio'. OJO: recargar la…, _reset_to_root() (+2 more)

### Community 24 - "12_schema_tasas_historicas.sql"
Cohesion: 0.24
Nodes (10): marts.fact_tasas_pasivas_instrumento, marts.fact_tasas_pasivas_plazo, marts.fact_tasas_referenciales_credito, marts.fact_tasas_referenciales_sistema, raw.tasas_referenciales, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo (+2 more)

### Community 25 - "compute_indicadores_excel.py"
Cohesion: 0.33
Nodes (9): cod(), main(), promedio_ytd(), Motor de referencia del catálogo `IND_NN` (indicadores del Excel de…, Promedio de saldos fin de mes de `codigo` (1=activo, 3=patrimonio), desde…, rd_one(), rd_years(), segmento_bruto() (+1 more)

### Community 26 - "13_schema_boletin.sql"
Cohesion: 0.29
Nodes (9): marts.dim_cuenta_contable, marts.fact_balance, marts.fact_pyg, raw.boletin_balance, raw.boletin_pyg, marts.dim_banco, marts.dim_fecha, staging.boletin_balance (+1 more)

### Community 27 - "scrape_boletin.py"
Cohesion: 0.42
Nodes (8): _download_all_files(), main(), _open_year_folder(), Path, Descarga los ZIP del Boletín Financiero Mensual (Balance y PyG) de bancos…, _reset_to_root(), scrape(), scrape_year()

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

## Knowledge Gaps
- **217 isolated node(s):** `graphify`, `projections`, `filters`, `name`, `height` (+212 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **47 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `resolver_banco_codigo()` connect `resolver_banco_codigo` to `parse_cartera.py`, `parse_boletin.py`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Why does `parse_depositos_file()` connect `parse_cartera.py` to `pipeline.py`, `resolver_banco_codigo`, `resolver_categoria_deposito`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Why does `resolver_categoria_deposito()` connect `resolver_categoria_deposito` to `parse_cartera.py`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `load_bce()` (e.g. with `upsert_staging_bce_tasas_activas()` and `upsert_staging_bce_tasas_pasivas()`) actually correct?**
  _`load_bce()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `graphify`, `projections`, `filters` to the rest of the system?**
  _217 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pipeline.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09059029807130334 - nodes in this community are weakly interconnected._
- **Should `benchmark_cartera_depositos` be split into smaller, more focused modules?**
  _Cohesion score 0.10121951219512196 - nodes in this community are weakly interconnected._