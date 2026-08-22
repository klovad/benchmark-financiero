# Graph Report - benchmark-bancos  (2026-08-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 740 nodes · 1083 edges · 99 communities (53 shown, 46 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9ae8abe6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 61
- Community 63
- Community 64
- Community 65
- Community 66
- Community 68
- Community 69
- Community 70
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97

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

## Communities (99 total, 46 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (51): Connection, download_all(), download_bce_file(), Path, Descarga directa de los archivos semanales de tasas de interés del BCE…, clave: 'tsp' o 'tsa'. Descarga si no existe ya un archivo con ese nombre., download_tasas_historicas(), _meses_hasta_hoy() (+43 more)

### Community 1 - "Community 1"
Cohesion: 0.10
Nodes (40): "marts"."dim_banco", "marts"."dim_canton", "marts"."dim_categoria_deposito", "marts"."dim_cuenta_contable", "marts"."dim_fecha", "marts"."dim_plazo", "marts"."dim_provincia", "marts"."dim_segmento_credito" (+32 more)

### Community 2 - "Community 2"
Cohesion: 0.13
Nodes (33): extract_single_xlsx(), find_base_sheets(), month_end_date(), normalize_banco(), normalize_provincia(), normalize_text(), Path, Los ZIP de Superbancos contienen exactamente un .xlsx -- salvo boletines… (+25 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (33): PlazoNoResueltoError, ValueError, Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de…, El texto crudo de plazo del BCE no matchea ningún patrón conocido., Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto…, resolver_plazo_bce(), _add_common_columns(), parse_tsa_file() (+25 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (30): BancoNoResueltoError, _cargar_csv(), _crosswalk(), EntidadBceNoMapeadaError, maestro(), _normalizar(), _por_regla(), Path (+22 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (21): _categoria_label(), _clean_label(), _emitir(), _parse_filas(), parse_tasas_historicas_file(), DataFrame, Path, Parser de las páginas mensuales TasasVigentes{MM}{YYYY}.htm del BCE. Cada… (+13 more)

### Community 6 - "Community 6"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 10 - "Community 10"
Cohesion: 0.10
Nodes (20): projections, filterConfig, filters, name, position, height, tabOrder, width (+12 more)

### Community 11 - "Community 11"
Cohesion: 0.10
Nodes (20): projections, name, position, height, tabOrder, width, x, y (+12 more)

### Community 12 - "Community 12"
Cohesion: 0.17
Nodes (17): _codigo_padre(), _find_header_row(), _normalize_col(), parse_boletin_file(), _parse_hoja(), _parse_met(), DataFrame, Path (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (19): name, reportVersionAtImport, type, objects, outspacePane, page, report, visual (+11 more)

### Community 14 - "Community 14"
Cohesion: 0.11
Nodes (18): name, position, height, tabOrder, width, x, y, z (+10 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (18): projections, filterConfig, filters, name, position, height, tabOrder, width (+10 more)

### Community 16 - "Community 16"
Cohesion: 0.12
Nodes (16): projections, name, position, height, tabOrder, width, x, y (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.12
Nodes (16): projections, name, position, height, tabOrder, width, x, y (+8 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (16): projections, name, position, height, tabOrder, width, x, y (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.31
Nodes (14): marts.dim_cuenta_contable, marts.fact_balance, marts.fact_pyg, marts.vw_activo_promedio_ytd, marts.vw_cartera_bruta, marts.vw_cartera_bruta_segmento, marts.vw_cartera_improductiva, marts.vw_cartera_improductiva_segmento (+6 more)

### Community 20 - "Community 20"
Cohesion: 0.26
Nodes (12): CategoriaNoResueltaError, ValueError, Resuelve el texto crudo de `tipo_deposito` (CAPCOL) o `instrumento_captacion`…, El texto crudo no es ni una categoría conocida ni un bucket de plazo…, Devuelve (categoria, dias_desde, dias_hasta). dias_* son None salvo que la…, resolver_categoria_deposito(), test_all_13_real_capcol_values_resolve(), test_empty_value_raises() (+4 more)

### Community 21 - "Community 21"
Cohesion: 0.29
Nodes (11): marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_cartera_tasa_ponderada, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.vw_depositos_tasa_ponderada, marts.dim_banco, marts.dim_categoria_deposito (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.21
Nodes (11): marts.fact_tasas_activas, marts.fact_tasas_pasivas, raw.bce_tasas_activas, raw.bce_tasas_pasivas, marts.dim_banco, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.33
Nodes (10): _download_all_files(), main(), _open_report_folder(), _open_year_folder(), Path, Descarga los archivos ZIP de cartera y depósitos del portal CAPCOL de…, Vuelve al listado raíz de años vía el breadcrumb 'Inicio'. OJO: recargar la…, _reset_to_root() (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.24
Nodes (10): marts.fact_tasas_pasivas_instrumento, marts.fact_tasas_pasivas_plazo, marts.fact_tasas_referenciales_credito, marts.fact_tasas_referenciales_sistema, raw.tasas_referenciales, marts.dim_categoria_deposito, marts.dim_fecha, marts.dim_plazo (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.33
Nodes (9): cod(), main(), promedio_ytd(), Motor de referencia del catálogo `IND_NN` (indicadores del Excel de…, Promedio de saldos fin de mes de `codigo` (1=activo, 3=patrimonio), desde…, rd_one(), rd_years(), segmento_bruto() (+1 more)

### Community 26 - "Community 26"
Cohesion: 0.29
Nodes (9): marts.dim_cuenta_contable, marts.fact_balance, marts.fact_pyg, raw.boletin_balance, raw.boletin_pyg, marts.dim_banco, marts.dim_fecha, staging.boletin_balance (+1 more)

### Community 27 - "Community 27"
Cohesion: 0.42
Nodes (8): _download_all_files(), main(), _open_year_folder(), Path, Descarga los ZIP del Boletín Financiero Mensual (Balance y PyG) de bancos…, _reset_to_root(), scrape(), scrape_year()

### Community 28 - "Community 28"
Cohesion: 0.33
Nodes (8): marts.fact_saldo_depositos, marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.vw_depositos_hhi, marts.vw_depositos_market_share, marts.dim_banco, marts.dim_fecha, marts.fact_saldo_cartera

### Community 29 - "Community 29"
Cohesion: 0.22
Nodes (8): activePageName, pageOrder, $schema, page-benchmark-banco, page-correlacion, page-geografico, page-overview, page-tendencias

### Community 30 - "Community 30"
Cohesion: 0.31
Nodes (8): marts.fact_saldo_cartera_new, marts.vw_cartera_hhi, marts.vw_cartera_market_share, marts.dim_banco, marts.dim_canton, marts.dim_fecha, marts.dim_segmento_credito, marts.fact_saldo_cartera

### Community 31 - "Community 31"
Cohesion: 0.54
Nodes (7): marts.dim_banco, marts.dim_canton, marts.dim_fecha, marts.dim_producto_cartera, marts.dim_producto_deposito, marts.fact_cartera, marts.fact_depositos

### Community 32 - "Community 32"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 33 - "Community 33"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 34 - "Community 34"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 35 - "Community 35"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 36 - "Community 36"
Cohesion: 0.29
Nodes (6): displayName, displayOption, height, name, $schema, width

### Community 37 - "Community 37"
Cohesion: 0.29
Nodes (6): autodetectRelationships, parallelQueryLoading, relationshipImportEnabled, $schema, shouldNotifyUserOfNameConflictResolution, typeDetectionEnabled

### Community 38 - "Community 38"
Cohesion: 0.50
Nodes (4): export_full(), export_sample(), Path, Exporta marts.* a Parquet, para poder probar el modelo de datos (Power BI,…

### Community 39 - "Community 39"
Cohesion: 0.50
Nodes (3): raw.cartera, raw.depositos, raw.source_files

### Community 40 - "Community 40"
Cohesion: 0.50
Nodes (3): marts.dim_categoria_deposito, marts.dim_plazo, marts.dim_segmento_credito

## Knowledge Gaps
- **216 isolated node(s):** `projections`, `filters`, `name`, `height`, `tabOrder` (+211 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **46 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `resolver_banco_codigo()` connect `Community 4` to `Community 2`, `Community 12`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Why does `parse_depositos_file()` connect `Community 2` to `Community 0`, `Community 4`, `Community 20`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Why does `resolver_categoria_deposito()` connect `Community 20` to `Community 2`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `load_bce()` (e.g. with `upsert_staging_bce_tasas_activas()` and `upsert_staging_bce_tasas_pasivas()`) actually correct?**
  _`load_bce()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `projections`, `filters`, `name` to the rest of the system?**
  _216 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.09764309764309764 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.10121951219512196 - nodes in this community are weakly interconnected._