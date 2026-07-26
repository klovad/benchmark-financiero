# Diccionario de datos

Esquema estrella en Postgres (`marts.*`), poblado desde 3 fuentes: CAPCOL (Superbancos,
cartera/depósitos), BCE (tasas de interés) y Boletín Financiero Mensual (Superbancos,
balance/PyG). Identidad de banco y catálogos de producto/plazo son compartidos entre
fuentes (`etl/transform/banco_matching.py` y `categoria_deposito_matching.py` resuelven
la identidad antes de que el dato llegue a `staging.*` — ver `docs/architecture.md` para
el patrón de carga incremental por hash).

## Dimensiones

### marts.dim_fecha (grano día)
| Columna | Tipo | Descripción |
|---|---|---|
| fecha_id | int (YYYYMMDD) | Llave sustituta |
| fecha | date | Fecha real (fin de mes para CAPCOL/Boletín, corte semanal para BCE) |
| anio, mes, dia, trimestre, nombre_mes | — | Derivados de fecha |
| anio_mes | int (YYYYMM) | Llave de roll-up para comparar grano mensual vs. semanal sin joins extra |

### marts.dim_banco
| Columna | Tipo | Descripción |
|---|---|---|
| banco_id | serial | Llave sustituta |
| banco_codigo | text | Identidad canónica resuelta en ETL (`banco_matching.py`), única entre las 3 fuentes |
| banco | text | Nombre a mostrar (sembrado desde `etl/seeds/banco_maestro.csv`) |
| tipo_entidad | text | 6 valores reales (CHECK constraint, `sql/07`): BANCO PRIVADO, BANCO PUBLICO, COOPERATIVA, MUTUALISTA, SOCIEDAD FINANCIERA, TARJETAS DE CREDITO — 442 bancos totales (33 privados con identidad curada + 409 auto-registrados por RUC desde BCE, ver `docs/gobernanza_datos.md`) |
| ruc | text, nullable | Identificador fiscal, poblado desde BCE tsp/tsa (única fuente que lo trae) — 2026-07-23: activado también para los 33 bancos privados curados, antes se descartaba en ese camino (`sql/17_dim_banco_ruc_sin_tamano.sql`); 442/442 filas con `ruc`. **No es único por banco**: al menos 7 pares de `banco_codigo` distintos comparten el mismo RUC (ver `docs/gobernanza_datos.md`, "RUC compartido entre identidades") |
| segmento_entidad_id | int, FK, nullable | `dim_segmento_entidad.segmento_entidad_id` — **última** clasificación normativa de tamaño/estructura conocida para el banco (2026-07-25, `sql/19_dim_segmento_entidad.sql`), SCD tipo 1, actualizada en cada `refresh_marts()` desde la fila más reciente de `fact_captaciones_depositos`/`fact_colocaciones_cartera`. Para análisis histórico (la clasificación cambia en el tiempo) usar el `segmento_entidad_id` de esos hechos, no este — ver tabla abajo |
| **`tamano` (GRANDE/MEDIANO/PEQUEÑO) eliminada** (2026-07-23, `sql/17`) **y su reemplazo real encontrado 2 días después**: se creyó "no obtenible con las fuentes actuales", pero BCE tsp/tsa sí trae esta clasificación por banco individual bajo la columna `tipo_segmento`, descartada hasta entonces sin examinar su contenido — ver `dim_segmento_entidad` abajo y `docs/gobernanza_datos.md`. | | |
| **Nota de calidad resuelta**: `BP COMERCIAL DE MANABI`/`BP BANCO COMERCIAL DE MANABI` y `BANCO AMIBANK S.A.`/`BANCO AMIBANK S.A., EN LIQUIDACION` eran el mismo banco partido en 2 filas por un rename de la fuente CAPCOL — corregido vía crosswalk, ver `etl/seeds/banco_crosswalk.csv`. | | |

### marts.dim_provincia (2026-07-25, `sql/20_dim_provincia.sql`)
| provincia_id | serial | Llave sustituta |
| provincia | text, único | 24 provincias del Ecuador (ortografía canónica de CAPCOL: sin tilde salvo la Ñ — `BOLIVAR`, `CAÑAR`) + `ZONA NO DELIMITADA` (CAPCOL) + `S/N` (BCE, filas a nivel nacional sin desagregar), ambas con `region = NULL` |
| region | text, nullable | Costa / Sierra / Oriente / Insular — **única fuente de verdad** en `marts` (antes duplicada como texto suelto en `dim_canton` y en `staging.depositos`, con valores inconsistentes entre sí para al menos una provincia — ver `docs/gobernanza_datos.md`, "Normalización de provincia") |
| **Compartida entre grano cantón (`dim_canton`) y grano provincia (BCE, sin cantón)** — antes `dim_canton` guardaba `provincia`/`region` como texto propio y `fact_captaciones_depositos`/`fact_colocaciones_cartera` guardaban `provincia` como texto suelto sin FK; ambas normalizadas contra este catálogo único. | | |

### marts.dim_canton
| canton_id | serial | Llave sustituta |
| canton | text | Ubicación de la oficina donde se registró la operación (no la residencia del cliente) |
| provincia_id | int, FK | `dim_provincia.provincia_id` — antes `provincia`/`region` como texto propio (ver `dim_provincia` arriba) |

### marts.dim_segmento_entidad (2026-07-25, `sql/19_dim_segmento_entidad.sql`)
| segmento_entidad_id | serial | Llave sustituta |
| tipo_segmento | text, único | Clasificación normativa de tamaño/estructura de la ENTIDAD (no del producto — no confundir con `dim_segmento_credito`/`dim_subsegmento_credito`), 14 valores: `BANCO GRANDE`/`BANCO MEDIANO`/`BANCO PEQUEÑO` (bancos privados), `SEGMENTO 1`..`SEGMENTO 5`/`SIN SEGMENTO` (cooperativas, JPRF-F-2023-074, segmentación por activos), `SEGMENTO 1 MUTUALISTA` (mutualistas), una categoría única para bancos públicos/sociedad financiera/tarjetas de crédito |
| **Fuente**: columna `tipo_segmento` de BCE tsp/tsa, preservada en `raw.*` desde el inicio pero descartada antes de `staging` sin examinar su contenido — detectado 2026-07-25 (el usuario preguntó dónde se había considerado). **Es un atributo de la entidad EN CADA FECHA, no fijo** (verificado: cooperativas reales cambian de segmento con los años según crecen) — por eso vive al grano semanal de `fact_captaciones_depositos`/`fact_colocaciones_cartera`, no como columna estática; `dim_banco.segmento_entidad_id` solo guarda la última clasificación conocida, de conveniencia. | | |

### marts.dim_segmento_credito (nivel grueso — 2026-07-19: nombre reasignado, antes lo tenía la tabla ahora `dim_subsegmento_credito`, ver abajo)
| segmento_id | serial | Llave sustituta |
| segmento | text | Segmento normativo de crédito (7 valores, MAYÚSCULAS): `PRODUCTIVO`, `CONSUMO`, `EDUCATIVO`, `INMOBILIARIO`, `VIVIENDA DE INTERÉS PÚBLICO`, `MICROCRÉDITO`, `INVERSIÓN PÚBLICA` |

### marts.dim_subsegmento_credito (nivel fino de BCE; antes `dim_segmento_credito`, renombrada 2026-07-19)
| subsegmento_id | serial | Llave sustituta |
| subsegmento | text | Sub-segmento tal como lo reporta BCE (26 valores, universo completo sin filtrar por tipo de entidad) |
| segmento_id | int, FK | `dim_segmento_credito.segmento_id` — reemplaza la columna `tipo_credito_capcol` (texto libre, nullable para 4 de los 26). Ahora es FK obligatoria: los 4 subsegmentos que antes quedaban NULL por no tener equivalente en CAPCOL sí tienen segmento normativo real (INVERSIÓN PÚBLICA es su propio segmento; las 3 variantes microcrédito "(SE)" son `MICROCRÉDITO`) — mapeo completo y su justificación en `sql/16_dim_segmento_normativo.sql` |

### marts.dim_categoria_deposito
| categoria_deposito_id | serial | Llave sustituta |
| categoria | text | 12 valores: 11 de CAPCOL/BCE + `DEPÓSITOS MONETARIOS` (agregado sin distinguir generan/no-generan intereses, encontrado en `TasasHistorico.htm`) |

### marts.dim_plazo (catálogo abierto por rango numérico, compartido entre fuentes)
| plazo_id | serial | Llave sustituta |
| dias_desde, dias_hasta | int, int nullable | `dias_hasta = NULL` significa sin límite superior |
| plazo_codigo | text | Texto original de la fuente, informativo |
| **No se fuerza equivalencia entre convenciones de distintas fuentes** — ej. CAPCOL "DE MÁS DE 361 DÍAS" y BCE tsp "g. MAS DE 360 DIAS" son filas distintas ((361,NULL) vs (360,NULL)), cada una con el límite real que reporta su fuente. | | |

### marts.dim_cuenta_contable (plan de cuentas del Boletín, BALANCE + PYG)
| cuenta_id | serial | Llave sustituta |
| reporte | text | BALANCE o PYG (llave natural es (reporte, codigo): el mismo código puede significar cosas distintas en cada reporte) |
| codigo, cuenta | text | Código jerárquico del Catálogo Único de Cuentas (1/2/4/6 dígitos) y su nombre |
| nivel | int | Profundidad = longitud del código |
| codigo_padre | text, nullable | Código del nivel inmediato superior |
| seccion | text | Derivada del primer dígito del código: 1 ACTIVO, 2 PASIVO, 3 PATRIMONIO, 4 GASTOS, 5 INGRESOS, 6 CONTINGENTE, 7 CUENTAS_DE_ORDEN |
| grupo_met | text, nullable | Agrupación funcional de la hoja `MET` (ACTIVOS LIQUIDOS, PASIVOS EXIGIBLES, etc.) — **no es partición limpia**, se guarda el primer grupo encontrado por código; ver `docs/metricas_financieras.md` |

## Hechos

Nombres renombrados 2026-07-19 a un glosario de negocio consistente (decisión explícita
del usuario): **cartera** = negocio de crédito (siempre), **depositos** = negocio de
captación (siempre); **saldo_** = medida de balance (CAPCOL, mensual); **colocaciones_**/
**captaciones_** = tasa efectiva + monto por banco (BCE semanal); **tasas_referenciales_**
= techo/referencial a nivel sistema (BCE mensual, `TasasHistorico`). Nombre anterior
entre paréntesis en cada tabla, para quien busque referencias viejas.

### marts.fact_saldo_cartera (antes `fact_cartera`) — grano: fecha × banco × cantón × segmento × estado_cartera — CAPCOL, mensual
| saldo | numeric | Saldo en USD |
| segmento_id | int, FK | `dim_segmento_credito.segmento_id` (nivel grueso — CAPCOL nunca trae el sub-segmento fino de BCE). Hasta 2026-07-19 esta columna era `tipo_credito` (texto libre, sin FK); pasó a estar normalizada contra el mismo catálogo normativo que usan los hechos de BCE en vez de duplicar el nombre del segmento como texto suelto — ver `sql/16_dim_segmento_normativo.sql` |
| estado_cartera | text | Dimensión degenerada (columna directa, sin FK — solo 3 valores fijos: por_vencer/no_devenga_intereses/vencida) |

`saldo_x_tasa`, `tasa_ponderada`, `morosidad` (columnas nunca pobladas, reservadas en v1)
**se eliminaron** en `sql/15_rename_fact_tables.sql` — la tasa real por producto ya vive
en `fact_colocaciones_cartera`; `morosidad` es derivable de `estado_cartera` si hace falta.

### marts.fact_saldo_depositos (antes `fact_depositos`) — grano: fecha × banco × cantón × categoria_deposito × plazo — CAPCOL, mensual
| saldo | numeric | Saldo en USD |
| numero_cuentas, numero_clientes | bigint | Sumados desde el detalle por cuenta contable del origen |
| plazo_id | int, nullable | NULL salvo que `categoria_deposito = 'DEPÓSITOS A PLAZO'` |

`saldo_x_tasa`/`tasa_ponderada` también eliminadas (mismo motivo — ver `fact_captaciones_depositos`).

### marts.fact_colocaciones_cartera (antes `fact_tasas_activas`) / marts.fact_captaciones_depositos (antes `fact_tasas_pasivas`) — grano: fecha × banco × categoría/subsegmento × plazo × provincia — BCE tsa/tsp, semanal
| subsegmento_id (solo cartera) | int, FK | `dim_subsegmento_credito.subsegmento_id` — nivel fino, columna llamada `segmento_id` hasta 2026-07-19 (ver `sql/16_dim_segmento_normativo.sql`) |
| provincia_id | int, FK, nullable | `dim_provincia.provincia_id` (2026-07-25, antes columna `provincia` texto suelto sin FK, ver `sql/20_dim_provincia.sql`) |
| segmento_entidad_id | int, FK, nullable | `dim_segmento_entidad.segmento_entidad_id` (2026-07-25, ver esa tabla arriba) — clasificación de tamaño/estructura del banco EN ESA FECHA |
| monto_total, numero_operaciones | numeric, int | Agregados de la semana reportados por el BCE |
| tasa_activa_efectiva/tasa_pasiva_efectiva, tasa_nominal | numeric | Las tasas efectivas reales por banco — esto es lo que CAPCOL no tenía |
| **Sistema financiero completo, no solo bancos privados** (corregido 2026-07-19) — `dim_banco` tiene 442 entidades (33 privados curados + 409 auto-registrados por RUC: cooperativas, bancos públicos, mutualistas, sociedad financiera, tarjetas de crédito). Ver `docs/gobernanza_datos.md`. | | |
| **Nota de agregación**: el archivo fuente trae cantón como grano más fino dentro de cada provincia; se reagrega en el parser (SUM de montos, tasas ponderadas por monto, no promedio simple). | | |

### marts.fact_tasas_referenciales_cartera (antes `fact_tasas_referenciales_credito`) / fact_tasas_referenciales_depositos_instrumento (antes `fact_tasas_pasivas_instrumento`) / fact_tasas_referenciales_depositos_plazo (antes `fact_tasas_pasivas_plazo`) / fact_tasas_referenciales_sistema (sin cambio de nombre) — `TasasHistorico.htm`, mensual, nivel sistema (no por banco)
Techos regulatorios y tasas de referencia (TPR/TAR/Tasa Legal/Tasa Máxima Convencional)
contra las cuales comparar las tasas efectivas de `fact_captaciones_depositos`/
`fact_colocaciones_cartera`. Las 4 tablas comparten ahora el prefijo `tasas_referenciales_`
— antes 2 de las 4 no lo usaban (`fact_tasas_pasivas_instrumento`/`_plazo`), fácil de
confundir con las tasas efectivas por banco. `fact_tasas_referenciales_cartera.subsegmento_id`
(columna llamada `segmento_id` hasta 2026-07-19) FK a `dim_subsegmento_credito` — mismo
nivel fino que `fact_colocaciones_cartera`, no el segmento normativo grueso.

### marts.fact_balance / fact_pyg (grano: fecha × banco × cuenta_contable) — Boletín, mensual
| saldo_usd / valor_usd | numeric | Ya en USD completos (`x1000` aplicado en el parser — la fuente reporta en miles) |

## Vistas analíticas (`sql/04_indexes_views.sql`)

4 vistas, no tablas materializadas (se recalculan en cada consulta) — features de
concentración de mercado ya resueltas, útiles como punto de partida para análisis o
modelos predictivos en vez de recalcular market share/HHI desde los `fact_*` cada vez:

| Vista | Grano | Columnas | Fórmula |
|---|---|---|---|
| `marts.vw_cartera_market_share` | fecha × banco | `saldo_banco`, `saldo_total_mes`, `market_share_pct` | `SUM(saldo)` por banco sobre `fact_saldo_cartera`, y `market_share_pct = saldo_banco / SUM(saldo_banco) OVER (PARTITION BY fecha_id) * 100` |
| `marts.vw_cartera_hhi` | fecha | `hhi` | Índice Herfindahl-Hirschman: `SUM(market_share_pct^2)` sobre `vw_cartera_market_share`, redondeado a 2 decimales (rango teórico 0–10.000; > 2.500 se suele leer como mercado concentrado) |
| `marts.vw_depositos_market_share` | fecha × banco | igual que `vw_cartera_market_share` | igual, sobre `fact_saldo_depositos` |
| `marts.vw_depositos_hhi` | fecha | `hhi` | igual que `vw_cartera_hhi`, sobre `vw_depositos_market_share` |

Ambas vistas de market share solo cubren CAPCOL (`fact_saldo_cartera`/`fact_saldo_depositos`,
2021-2025) — no existe un equivalente para las tasas de BCE ni para el Boletín todavía.

### Vistas de bloques de construcción — Balance/PyG (`sql/18_glosario_cuentas_views.sql`)

9 vistas, grano banco × fecha, que implementan los "bloques con nombre propio" documentados
conceptualmente en `docs/glosario_cuentas.md` (qué cuentas del Catálogo Único componen cada
bloque y por qué) — cualquier catálogo de indicadores nuevo debería componer estas vistas en
vez de recalcular la lógica de cuentas desde cero. Ver el glosario para el detalle de cada
fórmula; aquí solo el mapeo vista → bloque:

| Vista | Bloque (glosario §) |
|---|---|
| `marts.vw_cartera_bruta` | `cartera_bruta` (§2) |
| `marts.vw_cartera_improductiva` | `cartera_improductiva`, total (§2) |
| `marts.vw_cartera_improductiva_segmento` | `cartera_improductiva`, por segmento (§2) |
| `marts.vw_cartera_bruta_segmento` | `cartera_bruta`, por segmento (§2) |
| `marts.vw_depositos_corto_plazo` | `depositos_corto_plazo` (§3) |
| `marts.vw_pyg_total_gastos` | `total_gastos` PyG, workaround del hueco `codigo='4'` (§4.6) |
| `marts.vw_utilidad_acumulada` | `utilidad_acumulada` (§4) |
| `marts.vw_utilidad_anualizada` | `utilidad_anualizada` (§4) |
| `marts.vw_activo_promedio_ytd` / `marts.vw_patrimonio_promedio_ytd` | promedio YTD (§5) — ventana diciembre año anterior → fecha de corte |

No filtran por `tipo_entidad` (no hace falta: `fact_balance`/`fact_pyg` ya vienen
solo-privados por diseño del Boletín). Escritas siguiendo la misma lógica de
[`scripts/compute_indicadores_excel.py`](../scripts/compute_indicadores_excel.py) (motor de
referencia en pandas, corrido y verificado contra `data/samples/marts_full`), pero **las
vistas SQL en sí no se ejecutaron todavía contra una instancia Postgres real** — validar
sintaxis en el primer uso real.

## Decisiones de modelado relevantes
- **Identidad de banco resuelta en ETL, no con tabla de alias en el esquema estrella**: `etl/transform/banco_matching.py` normaliza y resuelve `banco_codigo` antes de `staging.*`; `dim_banco` se puebla desde `staging.banco_maestro` (sembrado desde `etl/seeds/banco_maestro.csv`).
- **Carga incremental por hash (CDC), no full refresh**: `staging.*` y `marts.*` tienen `fecha_carga`/`fecha_actualizacion`/`row_hash` (columna `GENERATED ALWAYS AS`); `fecha_actualizacion` solo se mueve si el dato realmente cambió. Ver `docs/architecture.md`.
- **Índices únicos NULL-safe**: cualquier `UNIQUE`/`ON CONFLICT` sobre una columna nullable (`dias_hasta`, `plazo_id`, `provincia`) usa `COALESCE(col, sentinela)` — Postgres trata `NULL <> NULL` incluso bajo `UNIQUE`, lo que causó un bug real de filas duplicadas (`dim_plazo`/`fact_depositos`) corregido en `sql/10_fix_null_unique_constraints.sql`.
- **Sin EAV en `marts`**: cada fuente de tasas tiene su propia tabla ancha con una columna por métrica real, en vez de una tabla genérica "tipo/valor". La única tabla "larga" es `staging.tasas_referenciales` (aterrizaje de las 5 secciones de `TasasHistorico.htm`, grano heterogéneo) — se ensancha a las 4 tablas de marts en `refresh_marts()`.
- **Indicadores financieros no se cargan como tabla**: son ratios recalculables desde `fact_balance`/`fact_pyg` (ver `docs/metricas_financieras.md`); cargarlos aparte arriesgaría reproducir la fórmula oficial de Superbancos distinto.
- **Alcance por fuente, no uniforme**: CAPCOL (`fact_saldo_cartera`/`fact_saldo_depositos`) y Boletín (`fact_balance`/`fact_pyg`) siguen filtrados a bancos privados en el `WHERE`/portal de origen. BCE (`fact_colocaciones_cartera`/`fact_captaciones_depositos`) **ya no se filtra** (corregido 2026-07-19) — cubre el sistema financiero completo, 442 entidades en `dim_banco`. Los catálogos (`dim_subsegmento_credito`, `dim_categoria_deposito`) siempre guardaron el universo completo sin filtrar.
- **`dim_segmento_credito`/`dim_subsegmento_credito`: jerarquía normativa de 2 niveles, no un rollup de texto libre** (2026-07-19): el segmento grueso (7 valores) y el subsegmento fino de BCE (26 valores) son dos dimensiones separadas unidas por FK — antes había una sola tabla con el rollup a CAPCOL como columna `TEXT` nullable, sin garantía de que coincidiera con `fact_cartera.tipo_credito` (también texto libre). `fact_saldo_cartera` (CAPCOL, solo reporta al nivel grueso) ahora referencia `dim_segmento_credito` directo; `fact_colocaciones_cartera`/`fact_tasas_referenciales_cartera` (BCE, reportan al nivel fino) referencian `dim_subsegmento_credito`. Ver `sql/16_dim_segmento_normativo.sql`.
- **Cobertura cargada** (2026-07): CAPCOL 2021-2025; BCE tsp/tsa 2008-2026 (semanal, histórico completo); `TasasHistorico.htm` 2022-04 a 2026-06 (páginas anteriores usan un layout HTML no soportado); Boletín BALANCE/PYG 2021-01 a 2026-06.
