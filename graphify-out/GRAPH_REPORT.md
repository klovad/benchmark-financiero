# Graph Report - benchmark-bancos  (2026-10-10)

## Corpus Check
- 115 files · ~125,012 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1178 nodes · 1871 edges · 144 communities (63 shown, 81 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 43 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `194befbf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- pipeline.py
- benchmark_cartera_depositos
- cli.py
- banco_matching.py
- resolver_categoria_deposito
- test_parse_tasas_historicas.py
- test_orquestacion.py
- con_reintentos
- Catálogo completo (48 indicadores, 12 categorías)
- marts.dim_banco
- parse_boletin.py
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
- CLAUDE.md
- 08_dim_segmento_categoria_plazo.sql
- 02_schema_staging.sql
- 07_dim_banco_dim_fecha_rebuild.sql
- 16_dim_segmento_normativo.sql
- 19_dim_segmento_entidad.sql
- 20_dim_provincia.sql
- parse_seps.py
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
- 01_schema_meta.sql
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
3. `sha256_file()` - 21 edges
4. `parse_depositos_file()` - 21 edges
5. `load_seps()` - 20 edges
6. `parse_seps_colocaciones_file()` - 19 edges
7. `parse_seps_eeff_file()` - 19 edges
8. `parse_seps_captaciones_file()` - 17 edges
9. `refresh_marts()` - 16 edges
10. `load_bce()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_resolver_entidad_seps_reusa_llave_bce_y_rellena_ruc_numerico()` --uses--> `RucInvalidoError`  [INFERRED]
  tests/test_parse_seps.py → src/benchmark_bancos/transform/banco_matching.py
- `test_plazo_bucket_shape_valido_pero_rango_invertido_lanza_plazo_error()` --uses--> `PlazoNoResueltoError`  [INFERRED]
  tests/test_categoria_deposito_matching.py → src/benchmark_bancos/transform/bce_plazo_matching.py
- `test_resolve_canton_propaga_cantonnoresueltoerror()` --uses--> `CantonNoResueltoError`  [INFERRED]
  tests/test_parse_bce_tasas.py → src/benchmark_bancos/transform/canton_matching.py
- `test_desvio_conocido_de_bancos_privados_en_depositos_no_falla()` --uses--> `Resultado`  [INFERRED]
  tests/test_conciliacion.py → src/benchmark_bancos/conciliacion.py
- `test_mediana_fuera_de_umbral_falla()` --uses--> `Resultado`  [INFERRED]
  tests/test_conciliacion.py → src/benchmark_bancos/conciliacion.py

## Import Cycles
- None detected.

## Communities (144 total, 81 thin omitted)

### Community 0 - "pipeline.py"
Cohesion: 0.06
Nodes (72): _ejecutar(), _cdc_guard(), _clean(), _copy_rows(), _crear_fuentes_incrementales(), get_connection(), insert_dim_cuenta_contable_seps(), is_source_loaded() (+64 more)

### Community 1 - "benchmark_cartera_depositos"
Cohesion: 0.10
Nodes (40): "marts"."dim_banco", "marts"."dim_canton", "marts"."dim_categoria_deposito", "marts"."dim_cuenta_contable", "marts"."dim_fecha", "marts"."dim_plazo", "marts"."dim_provincia", "marts"."dim_segmento_credito" (+32 more)

### Community 3 - "cli.py"
Cohesion: 0.07
Nodes (33): ArgumentParser, Punto de entrada del proyecto. uv run main.py <etapa> [opciones] Delega en…, Namespace, build_parser(), _codigo_salida(), main(), Interfaz de línea de comandos del pipeline. Uso (con uv): uv run benchmark-…, Entry point del script `benchmark-bancos` (pyproject) y de `python -m`. (+25 more)

### Community 4 - "banco_matching.py"
Cohesion: 0.09
Nodes (43): BancoNoResueltoError, _cargar_csv(), _crosswalk(), EntidadBceNoMapeadaError, maestro(), _normalizar(), _por_regla(), Path (+35 more)

### Community 5 - "resolver_categoria_deposito"
Cohesion: 0.14
Nodes (23): CategoriaNoResueltaError, ValueError, Resuelve el texto crudo de `tipo_deposito` (CAPCOL) o `instrumento_captacion`…, SEPS escribe las categorías sin tilde ('DEPOSITOS A LA VISTA', 'DEPOSITOS DE…, El texto crudo no es ni una categoría conocida ni un bucket de plazo…, Devuelve (categoria, dias_desde, dias_hasta). dias_* son None salvo que la…, resolver_categoria_deposito(), resolver_categoria_deposito_seps() (+15 more)

### Community 7 - "test_parse_tasas_historicas.py"
Cohesion: 0.05
Nodes (67): PlazoNoResueltoError, ValueError, Resuelve el texto crudo de `plazo` del BCE (tsp/tsa) a un rango numérico de…, Chequeo de dos niveles para TODOS los valores crudos de `plazo` observados en…, Devuelve (dias_desde, dias_hasta); dias_hasta es None si el bucket es abierto…, El texto crudo de plazo no matchea ningún patrón conocido (shape inválido), o…, Sanity check de rango, aplicado DESPUÉS de que el shape ya matcheó un patrón…, resolver_plazo_bce() (+59 more)

### Community 8 - "test_orquestacion.py"
Cohesion: 0.06
Nodes (34): evaluar(), Connection, Control de conciliación saldos vs. contabilidad (2026-10-09, `sql/39`). Evalúa…, Devuelve un mensaje por cada (mes, tipo, medida) fuera de umbral., Evalúa los últimos `meses` cortes con contabilidad cargada. Registra un ERROR…, Resultado, Umbral, verificar() (+26 more)

### Community 9 - "con_reintentos"
Cohesion: 0.06
Nodes (55): BaseException, _cabeceras_condicionales(), download_all(), download_bce_file(), _leer_meta(), _meta_path(), Path, Descarga directa de los archivos semanales de tasas de interés del BCE… (+47 more)

### Community 12 - "Catálogo completo (48 indicadores, 12 categorías)"
Cohesion: 0.06
Nodes (32): 1. Cómo está organizado el Catálogo Único de Cuentas, 2. Cuentas clave — ACTIVO (sección `1`), 3. Cuentas clave — PASIVO (sección `2`), 4.6 Hueco de datos conocido: PyG código `4`, 4. Cuentas clave — PATRIMONIO, INGRESOS, GASTOS (secciones `3`, `4`, `5`), 5. Bloques que combinan Balance + PyG o cruzan periodos (series de tiempo), 6. Qué NO cubre este documento (fuera de alcance, documentado en otro lado), Cómo usar este documento al escribir un ratio nuevo (+24 more)

### Community 14 - "parse_boletin.py"
Cohesion: 0.16
Nodes (17): _codigo_padre(), _find_header_row(), _normalize_col(), parse_boletin_file(), _parse_hoja(), _parse_met(), DataFrame, Path (+9 more)

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
Nodes (38): _bce_tasas_pasivas_row(), _boletin_balance_row(), _cleanup_bce_tasas_pasivas(), _cleanup_boletin_balance(), _dim_canton_insert_statement(), _fact_saldo_cartera_pivot_statement(), integration, Tests de integración (@pytest.mark.integration): requieren Postgres real ya… (+30 more)

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

### Community 40 - "08_dim_segmento_categoria_plazo.sql"
Cohesion: 0.50
Nodes (3): marts.dim_categoria_deposito, marts.dim_plazo, marts.dim_segmento_credito

### Community 47 - "parse_seps.py"
Cohesion: 0.08
Nodes (48): Series, Resuelve una entidad SEPS (cooperativa, mutualista o entidad de segundo piso) a…, resolver_entidad_seps(), _a_numero(), _chunks(), extraer_zip_seps(), _fecha_corte(), _geo() (+40 more)

### Community 50 - "config/__init__.py"
Cohesion: 0.06
Nodes (53): Catálogos de dominio usados por los parsers: mapeos de vocabulario de las…, Configuración del proyecto, separada por responsabilidad: - `settings`: lo que…, _find_project_root(), Path, Configuración que depende del entorno: rutas, base de datos y años a procesar.…, Constantes de las fuentes externas: URLs, sub-portales, nombres de carpeta, ids…, aplicar_alias_canton(), Resuelve el par (canton, provincia) crudo del BCE (tsp/tsa) contra el catálogo… (+45 more)

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
Nodes (46): 10. Problemas frecuentes, 11. Brechas de portabilidad y orquestación, 1.1 Componentes y requisitos, 1.2 Configuración (variables de entorno), 1.3.1 Códigos de salida y bloqueo [verificado: `tests/test_orquestacion.py`], 1.3 Etapas del CLI [verificado con `uv run benchmark-bancos --help`], 1.4 Dependencias entre etapas, 1. Mapa del sistema (+38 more)

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
- **190 isolated node(s):** `benchmark-bancos`, `actualizar.sh script`, `meta.source_files`, `staging.cartera`, `staging.depositos` (+185 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **81 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `resolver_canton_bce()` connect `resolver_canton_bce` to `config/__init__.py`, `parse_seps.py`, `parse_bce_tasas.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `validar_universo_plazos_bce()` connect `test_parse_tasas_historicas.py` to `parse_bce_tasas.py`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Why does `parse_boletin_file()` connect `parse_boletin.py` to `pipeline.py`, `config/__init__.py`, `banco_matching.py`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `load_seps()` (e.g. with `upsert_staging_cartera()` and `upsert_staging_depositos()`) actually correct?**
  _`load_seps()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `benchmark-bancos`, `actualizar.sh script`, `meta.source_files` to the rest of the system?**
  _190 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `pipeline.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06378378378378378 - nodes in this community are weakly interconnected._
- **Should `benchmark_cartera_depositos` be split into smaller, more focused modules?**
  _Cohesion score 0.10121951219512196 - nodes in this community are weakly interconnected._