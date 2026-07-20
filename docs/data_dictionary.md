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
| tamano | text, nullable | GRANDE/MEDIANO/PEQUEÑO, SCD tipo 1 (último valor conocido, no historizado — decisión explícita: la historia se compara contra la situación actual del banco) |
| **Nota de calidad resuelta**: `BP COMERCIAL DE MANABI`/`BP BANCO COMERCIAL DE MANABI` y `BANCO AMIBANK S.A.`/`BANCO AMIBANK S.A., EN LIQUIDACION` eran el mismo banco partido en 2 filas por un rename de la fuente CAPCOL — corregido vía crosswalk, ver `etl/seeds/banco_crosswalk.csv`. | | |

### marts.dim_canton
| canton_id | serial | Llave sustituta |
| canton, provincia | text | Ubicación de la oficina donde se registró la operación (no la residencia del cliente) |
| region | text | Costa / Sierra / Oriente / Insular, derivada de la provincia |

### marts.dim_segmento_credito
| segmento_id | serial | Llave sustituta |
| segmento | text | Sub-segmento fino de BCE (26 valores, universo completo sin filtrar por tipo de entidad) |
| tipo_credito_capcol | text, nullable | Rollup a los 6 valores de `tipo_credito` de CAPCOL; NULL para los 4 segmentos sin equivalente en bancos privados (INVERSIÓN PÚBLICA y 3 variantes "(SE)") |

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

### marts.fact_saldo_cartera (antes `fact_cartera`) — grano: fecha × banco × cantón × tipo_credito × estado_cartera — CAPCOL, mensual
| saldo | numeric | Saldo en USD |
| tipo_credito, estado_cartera | text | Dimensión degenerada (columnas directas, sin FK — CAPCOL nunca trae el sub-segmento fino de BCE) |

`saldo_x_tasa`, `tasa_ponderada`, `morosidad` (columnas nunca pobladas, reservadas en v1)
**se eliminaron** en `sql/15_rename_fact_tables.sql` — la tasa real por producto ya vive
en `fact_colocaciones_cartera`; `morosidad` es derivable de `estado_cartera` si hace falta.

### marts.fact_saldo_depositos (antes `fact_depositos`) — grano: fecha × banco × cantón × categoria_deposito × plazo — CAPCOL, mensual
| saldo | numeric | Saldo en USD |
| numero_cuentas, numero_clientes | bigint | Sumados desde el detalle por cuenta contable del origen |
| plazo_id | int, nullable | NULL salvo que `categoria_deposito = 'DEPÓSITOS A PLAZO'` |

`saldo_x_tasa`/`tasa_ponderada` también eliminadas (mismo motivo — ver `fact_captaciones_depositos`).

### marts.fact_colocaciones_cartera (antes `fact_tasas_activas`) / marts.fact_captaciones_depositos (antes `fact_tasas_pasivas`) — grano: fecha × banco × categoría/segmento × plazo × provincia — BCE tsa/tsp, semanal
| monto_total, numero_operaciones | numeric, int | Agregados de la semana reportados por el BCE |
| tasa_activa_efectiva/tasa_pasiva_efectiva, tasa_nominal | numeric | Las tasas efectivas reales por banco — esto es lo que CAPCOL no tenía |
| **Sistema financiero completo, no solo bancos privados** (corregido 2026-07-19) — `dim_banco` tiene 442 entidades (33 privados curados + 409 auto-registrados por RUC: cooperativas, bancos públicos, mutualistas, sociedad financiera, tarjetas de crédito). Ver `docs/gobernanza_datos.md`. | | |
| **Nota de agregación**: el archivo fuente trae cantón como grano más fino dentro de cada provincia; se reagrega en el parser (SUM de montos, tasas ponderadas por monto, no promedio simple). | | |

### marts.fact_tasas_referenciales_cartera (antes `fact_tasas_referenciales_credito`) / fact_tasas_referenciales_depositos_instrumento (antes `fact_tasas_pasivas_instrumento`) / fact_tasas_referenciales_depositos_plazo (antes `fact_tasas_pasivas_plazo`) / fact_tasas_referenciales_sistema (sin cambio de nombre) — `TasasHistorico.htm`, mensual, nivel sistema (no por banco)
Techos regulatorios y tasas de referencia (TPR/TAR/Tasa Legal/Tasa Máxima Convencional)
contra las cuales comparar las tasas efectivas de `fact_captaciones_depositos`/
`fact_colocaciones_cartera`. Las 4 tablas comparten ahora el prefijo `tasas_referenciales_`
— antes 2 de las 4 no lo usaban (`fact_tasas_pasivas_instrumento`/`_plazo`), fácil de
confundir con las tasas efectivas por banco.

### marts.fact_balance / fact_pyg (grano: fecha × banco × cuenta_contable) — Boletín, mensual
| saldo_usd / valor_usd | numeric | Ya en USD completos (`x1000` aplicado en el parser — la fuente reporta en miles) |

## Decisiones de modelado relevantes
- **Identidad de banco resuelta en ETL, no con tabla de alias en el esquema estrella**: `etl/transform/banco_matching.py` normaliza y resuelve `banco_codigo` antes de `staging.*`; `dim_banco` se puebla desde `staging.banco_maestro` (sembrado desde `etl/seeds/banco_maestro.csv`).
- **Carga incremental por hash (CDC), no full refresh**: `staging.*` y `marts.*` tienen `fecha_carga`/`fecha_actualizacion`/`row_hash` (columna `GENERATED ALWAYS AS`); `fecha_actualizacion` solo se mueve si el dato realmente cambió. Ver `docs/architecture.md`.
- **Índices únicos NULL-safe**: cualquier `UNIQUE`/`ON CONFLICT` sobre una columna nullable (`dias_hasta`, `plazo_id`, `provincia`) usa `COALESCE(col, sentinela)` — Postgres trata `NULL <> NULL` incluso bajo `UNIQUE`, lo que causó un bug real de filas duplicadas (`dim_plazo`/`fact_depositos`) corregido en `sql/10_fix_null_unique_constraints.sql`.
- **Sin EAV en `marts`**: cada fuente de tasas tiene su propia tabla ancha con una columna por métrica real, en vez de una tabla genérica "tipo/valor". La única tabla "larga" es `staging.tasas_referenciales` (aterrizaje de las 5 secciones de `TasasHistorico.htm`, grano heterogéneo) — se ensancha a las 4 tablas de marts en `refresh_marts()`.
- **Indicadores financieros no se cargan como tabla**: son ratios recalculables desde `fact_balance`/`fact_pyg` (ver `docs/metricas_financieras.md`); cargarlos aparte arriesgaría reproducir la fórmula oficial de Superbancos distinto.
- **Alcance por fuente, no uniforme**: CAPCOL (`fact_saldo_cartera`/`fact_saldo_depositos`) y Boletín (`fact_balance`/`fact_pyg`) siguen filtrados a bancos privados en el `WHERE`/portal de origen. BCE (`fact_colocaciones_cartera`/`fact_captaciones_depositos`) **ya no se filtra** (corregido 2026-07-19) — cubre el sistema financiero completo, 442 entidades en `dim_banco`. Los catálogos (`dim_segmento_credito`, `dim_categoria_deposito`) siempre guardaron el universo completo sin filtrar.
- **Cobertura cargada** (2026-07): CAPCOL 2021-2025; BCE tsp/tsa 2008-2026 (semanal, histórico completo); `TasasHistorico.htm` 2022-04 a 2026-06 (páginas anteriores usan un layout HTML no soportado); Boletín BALANCE/PYG 2021-01 a 2026-06.
