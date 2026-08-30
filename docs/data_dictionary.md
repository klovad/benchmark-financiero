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
| ruc | text, nullable | Identificador fiscal, poblado desde BCE tsp/tsa (única fuente que lo trae) — 2026-07-23: activado también para los 33 bancos privados curados, antes se descartaba en ese camino (`sql/17_dim_banco_ruc_sin_tamano.sql`); 442/442 filas con `ruc`. **No es único por banco**: 7 `ruc` distintos son compartidos por 2+ `banco_codigo` (ver `docs/gobernanza_datos.md`, "Huecos de gobernanza conocidos", y la vista `marts.vw_banco_ruc_colisiones` más abajo para consultarlos directo). **Desde 2026-08-30, el RUC de las ~409 entidades no-privadas pasa por validación estructural real** antes de resolverse (`etl/transform/banco_matching.py::validar_ruc_estructura`, `sql/26` no toca esto — es puramente Python, ver `resolver_entidad_bce`) — 13 dígitos, código de provincia 01-24, tercer dígito 9 (sociedad privada/extranjera) o 6 (sector público), dígito verificador módulo 11. Un RUC no-privado que falle esta validación lanza `RucInvalidoError` (distinto de `EntidadBceNoMapeadaError`) y bloquea la carga en vez de auto-registrarse con un RUC malformado. Los 33 bancos privados curados **no** pasan por esta validación (su identidad ya está curada por nombre, el RUC es un atributo, no la llave) |
| segmento_entidad_id | int, FK, nullable | `dim_segmento_entidad.segmento_entidad_id` — **última** clasificación normativa de tamaño/estructura conocida para el banco (2026-07-25, `sql/19_dim_segmento_entidad.sql`), SCD tipo 1, actualizada en cada `refresh_marts()` desde la fila más reciente de `fact_captaciones_depositos`/`fact_colocaciones_cartera`. Para análisis histórico (la clasificación cambia en el tiempo) usar el `segmento_entidad_id` de esos hechos, no este — ver tabla abajo |
| estado_validacion | text, `CHECK IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO')` | Nueva 2026-08-30 (`sql/26_dim_banco_estado_validacion.sql`). Distingue identidad **curada** (`CONFIRMADO` — los 33 bancos privados de `banco_maestro.csv`, reafirmado en cada `load_banco_maestro_seed()`) de identidad **auto-registrada sin revisión humana** (`AUTO_INGRESADO`, DEFAULT — las 409 entidades registradas por RUC vía `resolver_entidad_bce()`, ver "Identidad auto-registrada por RUC" en `docs/gobernanza_datos.md`, hueco ya documentado desde antes pero ahora consultable directo en el dato en vez de solo en texto). `RECHAZADO` reservado para uso futuro, ningún flujo actual lo escribe. Backfill retroactivo de esta migración: 33 filas a `CONFIRMADO`, 409 a `AUTO_INGRESADO`, discriminadas por `banco_codigo` (los auto-registrados siempre tienen prefijo `BCE_`, verificado exacto contra la base viva antes de escribir el backfill — sin solapamiento ni resto) |
| **`tamano` (GRANDE/MEDIANO/PEQUEÑO) eliminada** (2026-07-23, `sql/17`) **y su reemplazo real encontrado 2 días después**: se creyó "no obtenible con las fuentes actuales", pero BCE tsp/tsa sí trae esta clasificación por banco individual bajo la columna `tipo_segmento`, descartada hasta entonces sin examinar su contenido — ver `dim_segmento_entidad` abajo y `docs/gobernanza_datos.md`. | | |
| **Nota de calidad resuelta**: `BP COMERCIAL DE MANABI`/`BP BANCO COMERCIAL DE MANABI` y `BANCO AMIBANK S.A.`/`BANCO AMIBANK S.A., EN LIQUIDACION` eran el mismo banco partido en 2 filas por un rename de la fuente CAPCOL — corregido vía crosswalk, ver `etl/seeds/banco_crosswalk.csv`. | | |
| **Bug de CDC real encontrado y corregido 2026-08-30** (preexistía desde `sql/19_dim_segmento_entidad.sql`, 2026-07-25 — no lo introdujo esta migración, quedó expuesto al verificar CDC no-op de punta a punta en vez de asumirlo) | El `INSERT INTO marts.dim_banco ... ON CONFLICT` no listaba `segmento_entidad_id` entre sus columnas — Postgres computaba `EXCLUDED.segmento_entidad_id` como `NULL` (el valor por defecto de una columna omitida del INSERT, no el valor real de la fila en conflicto), así que `EXCLUDED.row_hash` casi nunca coincidía con el `row_hash` real de un banco con `segmento_entidad_id` ya poblado (prácticamente los 442) — el guard `WHERE row_hash IS DISTINCT FROM EXCLUDED.row_hash` disparaba un `UPDATE` real (`fecha_actualizacion = now()`) en **cada** `refresh_marts()`, no solo cuando algo cambiaba de verdad. Corregido con un `LEFT JOIN` a la propia `marts.dim_banco` para que el INSERT lleve el `segmento_entidad_id` actual (esa columna sigue sin escribirse en el `SET` del `ON CONFLICT` — la mantiene el `UPDATE` SCD1 separado más abajo en `_REFRESH_MARTS_SQL`). Verificado tras el fix: 0 filas con `fecha_actualizacion` cambiada en una corrida de `refresh_marts()` sin datos nuevos. | | |

### marts.dim_provincia (2026-07-25, `sql/20_dim_provincia.sql`)
| provincia_id | serial | Llave sustituta |
| provincia | text, único | 24 provincias del Ecuador (ortografía canónica de CAPCOL: sin tilde salvo la Ñ — `BOLIVAR`, `CAÑAR`) + `ZONA NO DELIMITADA` (CAPCOL) + `S/N` (BCE, filas a nivel nacional sin desagregar), ambas con `region = NULL` |
| region | text, nullable | Costa / Sierra / Oriente / Insular — **única fuente de verdad** en `marts` (antes duplicada como texto suelto en `dim_canton` y en `staging.depositos`, con valores inconsistentes entre sí para al menos una provincia — ver `docs/gobernanza_datos.md`, "Normalización de provincia") |
| **Compartida entre grano cantón (`dim_canton`) y grano provincia (BCE, sin cantón)** — antes `dim_canton` guardaba `provincia`/`region` como texto propio y `fact_captaciones_depositos`/`fact_colocaciones_cartera` guardaban `provincia` como texto suelto sin FK; ambas normalizadas contra este catálogo único. | | |

### marts.dim_canton
| canton_id | serial | Llave sustituta |
| canton | text | Ubicación de la oficina donde se registró la operación (no la residencia del cliente) |
| provincia_id | int, FK | `dim_provincia.provincia_id` — antes `provincia`/`region` como texto propio (ver `dim_provincia` arriba) |
| **Bug de descarte silencioso encontrado y mitigado 2026-08-30 (`etl/load/load_postgres.py::_log_cantones_no_resueltos`)** | El `INSERT INTO marts.dim_canton` de `refresh_marts()` usa un `INNER JOIN` contra `dim_provincia` (necesario: `provincia_id` es `NOT NULL`) — cualquier fila de `staging.cartera`/`staging.depositos` cuya `provincia` no matcheara contra `dim_provincia` (ni exacto ni vía `translate()`) se descartaba ahí sin error ni rastro. **No convertido en fail-fast ni en tabla de rechazos**: a diferencia de `dim_plazo`/`banco_codigo` (catálogos regulatorios cerrados donde un valor no resuelto es un dato mal identificado), `dim_canton` es geografía de bajo riesgo y, verificado contra la base viva en esta sesión, **0 filas de `staging.cartera`/`staging.depositos` caen hoy en este caso** — construir infraestructura de rechazos para 0 filas afectadas sería sobre-ingeniería. Se agregó `_log_cantones_no_resueltos(conn)`, llamada al inicio de cada `refresh_marts()`, que loguea WARNING con el detalle (provincia, filas, cantones distintos) si alguna vez ocurre, INFO "0 filas" si no — visible en cualquier corrida normal del pipeline en vez de requerir ir a buscarlo. | | |

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

### marts.dim_plazo (catálogo por rango numérico, compartido entre fuentes)
| plazo_id | serial | Llave sustituta |
| dias_desde, dias_hasta | int, int nullable | `dias_hasta = NULL` significa sin límite superior |
| plazo_codigo | text | Texto original de la fuente, informativo |
| **No se fuerza equivalencia entre convenciones de distintas fuentes** — ej. CAPCOL "DE MÁS DE 361 DÍAS" y BCE tsp "g. MAS DE 360 DIAS" son filas distintas ((361,NULL) vs (360,NULL)), cada una con el límite real que reporta su fuente. | | |
| **Fail-fast desde 2026-08-27** (antes: catálogo abierto, auto-descubierto vía `INSERT ... ON CONFLICT DO NOTHING` en `refresh_marts()` sin validar contra ningún universo conocido) — cada fuente ahora valida el texto crudo de plazo contra un universo cerrado y verificado ANTES de que el dato llegue a `staging`, igual que `categoria_deposito`/`segmento_credito`: `PLAZOS_TSP_VALIDOS` (7)/`PLAZOS_TSA_VALIDOS` (14) en `etl/transform/bce_plazo_matching.py::validar_universo_plazos_bce()`, `PLAZOS_VALIDOS` (5) en `etl/transform/categoria_deposito_matching.py`, `PLAZOS_VALIDOS` (6) en `etl/transform/parse_tasas_historicas.py`. Un texto que matchea el *shape* regex de un bucket pero no está en el universo válido de su fuente lanza `PlazoNoResueltoError` en vez de crear una fila nueva silenciosa — dim_plazo solo crece cuando alguien agrega deliberadamente el bucket nuevo a uno de esos 3 sets (mismo criterio que `SEGMENTOS_VALIDOS`/`CATEGORIAS_VALIDAS`). El `INSERT ... ON CONFLICT DO NOTHING` en `refresh_marts()` (`etl/load/load_postgres.py`, líneas ~593-610) sigue existiendo a nivel `marts` por razones de CDC/idempotencia, pero ya no es la barrera de validación real: por diseño, en operación normal nunca debería insertar un bucket que no pasó ya por el gate de Python. | | |

### marts.dim_cuenta_contable (plan de cuentas del Boletín, BALANCE + PYG)
| cuenta_id | serial | Llave sustituta |
| reporte | text | BALANCE o PYG (llave natural es (reporte, codigo): el mismo código puede significar cosas distintas en cada reporte) |
| codigo, cuenta | text | Código jerárquico del Catálogo Único de Cuentas (1/2/4/6 dígitos) y su nombre |
| nivel | int | Profundidad = longitud del código |
| codigo_padre | text, nullable | Código del nivel inmediato superior |
| seccion | text | Derivada del primer dígito del código: 1 ACTIVO, 2 PASIVO, 3 PATRIMONIO, 4 GASTOS, 5 INGRESOS, 6 CONTINGENTE, 7 CUENTAS_DE_ORDEN |
| grupo_met | text, nullable | Agrupación funcional de la hoja `MET` (ACTIVOS LIQUIDOS, PASIVOS EXIGIBLES, etc.) — **no es partición limpia**, se guarda el primer grupo encontrado por código; ver `docs/metricas_financieras.md` |
| estado_validacion | text, `CHECK IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO')` | Nueva 2026-08-30 (`sql/25_dim_cuenta_contable_estado_validacion.sql`). `upsert_dim_cuenta_contable()` descubre cuentas nuevas del plan de cuentas directo de cada archivo del Boletín, sin curación humana (`ON CONFLICT DO UPDATE`, ver `etl/load/load_postgres.py`) — esta columna hace ese hecho consultable. Backfill retroactivo: las 1.736 cuentas que ya existían antes de esta migración se marcaron `CONFIRMADO` (han sobrevivido múltiples cargas del Boletín sin incidentes); toda cuenta nueva insertada de aquí en adelante hereda el DEFAULT `AUTO_INGRESADO` sin necesitar cambio de código en `upsert_dim_cuenta_contable()` (no lista la columna en su INSERT). `RECHAZADO` reservado, ningún flujo actual lo escribe. **Nota de portabilidad**: a diferencia de casi toda `staging`/`marts`, esta tabla no tiene `fecha_carga`/`fecha_actualizacion`/`row_hash` — no participa del patrón CDC del proyecto (se resiembra/enriquece en cada archivo, mismo criterio que `staging.banco_maestro`), así que no hubo `row_hash` que extender al agregar esta columna |

## Hechos

Nombres renombrados 2026-07-19 a un glosario de negocio consistente (decisión explícita
del usuario): **cartera** = negocio de crédito (siempre), **depositos** = negocio de
captación (siempre); **saldo_** = medida de balance (CAPCOL, mensual); **colocaciones_**/
**captaciones_** = tasa efectiva + monto por banco (BCE semanal); **tasas_referenciales_**
= techo/referencial a nivel sistema (BCE mensual, `TasasHistorico`). Nombre anterior
entre paréntesis en cada tabla, para quien busque referencias viejas.

### marts.fact_saldo_cartera (antes `fact_cartera`) — grano: fecha × banco × cantón × segmento — CAPCOL, mensual
| segmento_id | int, FK | `dim_segmento_credito.segmento_id` (nivel grueso — CAPCOL nunca trae el sub-segmento fino de BCE). Hasta 2026-07-19 esta columna era `tipo_credito` (texto libre, sin FK); pasó a estar normalizada contra el mismo catálogo normativo que usan los hechos de BCE en vez de duplicar el nombre del segmento como texto suelto — ver `sql/16_dim_segmento_normativo.sql` |
| saldo_por_vencer, saldo_no_devenga_intereses, saldo_vencida | numeric | Saldo en USD por estado de cartera. **2026-07-25** (`sql/21_fact_saldo_cartera_pivot.sql`): antes `estado_cartera` era una dimensión degenerada partiendo el saldo en 3 filas por combinación de `(fecha, banco, cantón, segmento)` — un antipatrón EAV, no una dimensión real (los 3 estados son medidas mutuamente excluyentes del mismo hecho, siempre presentes juntas). Pivotado a 3 columnas, mismo criterio que ya usaba `fact_tasas_referenciales_cartera` (2 columnas de medida en vez de "tipo_tasa"+"valor"). El grano pasó de 369.966 a 123.322 filas (÷3, exacto — no había combinaciones con menos de 3 estados) |
| saldo_total | numeric, `GENERATED ALWAYS AS (...) STORED` | Suma de los 3 — una sola fuente de verdad, no algo que el ETL deba mantener sincronizado (mismo patrón que `row_hash` en todo el proyecto). `morosidad = (saldo_no_devenga_intereses + saldo_vencida) / saldo_total`, ya no requiere filtrar nada |

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
| `marts.vw_cartera_market_share` | fecha × banco | `saldo_banco`, `saldo_total_mes`, `market_share_pct` | `SUM(saldo_total)` por banco sobre `fact_saldo_cartera` (columna `saldo_total` desde 2026-07-25, antes `saldo` — ver `sql/21_fact_saldo_cartera_pivot.sql`), y `market_share_pct = saldo_banco / SUM(saldo_banco) OVER (PARTITION BY fecha_id) * 100` |
| `marts.vw_cartera_hhi` | fecha | `hhi` | Índice Herfindahl-Hirschman: `SUM(market_share_pct^2)` sobre `vw_cartera_market_share`, redondeado a 2 decimales (rango teórico 0–10.000; > 2.500 se suele leer como mercado concentrado) |
| `marts.vw_depositos_market_share` | fecha × banco | igual que `vw_cartera_market_share` | igual, sobre `fact_saldo_depositos` |
| `marts.vw_depositos_hhi` | fecha | `hhi` | igual que `vw_cartera_hhi`, sobre `vw_depositos_market_share` |

Ambas vistas de market share solo cubren CAPCOL (`fact_saldo_cartera`/`fact_saldo_depositos`,
2021-01 a 2026-06) — no existe un equivalente para las tasas de BCE ni para el Boletín todavía.

### Vista de gobernanza — `marts.vw_banco_ruc_colisiones` (`sql/22_vw_banco_ruc_colisiones.sql`)

**Para qué**: hace consultable directamente el hueco de gobernanza "7 pares de
`banco_codigo` distintos comparten el mismo `ruc`" (ver `docs/gobernanza_datos.md`,
"Huecos de gobernanza conocidos") — antes solo estaba documentado como prosa, con la
query de verificación mencionada en el propio documento pero no persistida en ningún
objeto de base de datos. Un analista que haga `SELECT * FROM marts.dim_banco` no tiene
forma de descubrir la colisión sin haber leído ese documento primero; esta vista sí lo
muestra directo.

**Grano**: una fila por `(ruc, banco_id)` — no por `ruc`. Solo incluye los `ruc` que
aparecen en 2 o más filas de `dim_banco`.

**Columnas**: `ruc`, `banco_id`, `banco_codigo`, `banco`, `tipo_entidad`.

**Cuándo usarla**: antes de cualquier análisis longitudinal o modelo predictivo que
agrupe/una por `banco_codigo` o `ruc` — hacer `LEFT JOIN`/`NOT EXISTS` contra esta vista
para saber si el banco de interés participa en una colisión. **No cambia la decisión de
negocio**: los `banco_codigo` de cada par siguen sin fusionarse (el cambio de
`tipo_entidad` — cooperativa/financiera que pasó a banco privado licenciado manteniendo
el mismo RUC en BCE — es real, y fusionar ocultaría esa transición en vez de modelarla).
Verificado contra Postgres vivo (2026-08-22): 7 `ruc` distintos, 15 filas (6 pares 2-a-2 +
1 trío AMIBANK/FINCA/BP FINCA), coincide exactamente con la lista de
`docs/gobernanza_datos.md`.

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
referencia en pandas, corrido y verificado contra `data/samples/marts_ultimos_5_anios`
-- antes `marts_full`, ver `data/samples/README.md`), pero **las
vistas SQL en sí no se ejecutaron todavía contra una instancia Postgres real** — validar
sintaxis en el primer uso real.

## Decisiones de modelado relevantes
- **Identidad de banco resuelta en ETL, no con tabla de alias en el esquema estrella**: `etl/transform/banco_matching.py` normaliza y resuelve `banco_codigo` antes de `staging.*`; `dim_banco` se puebla desde `staging.banco_maestro` (sembrado desde `etl/seeds/banco_maestro.csv`).
- **Carga incremental por hash (CDC), no full refresh**: `staging.*` y `marts.*` tienen `fecha_carga`/`fecha_actualizacion`/`row_hash` (columna `GENERATED ALWAYS AS`); `fecha_actualizacion` solo se mueve si el dato realmente cambió. Ver `docs/architecture.md`.
- **Índices únicos NULL-safe**: cualquier `UNIQUE`/`ON CONFLICT` sobre una columna nullable (`dias_hasta`, `plazo_id`, `provincia_id`, `canton_id`, `staging.cartera.canton`, `staging.depositos.canton`) usa `COALESCE(col, sentinela)` — Postgres trata `NULL <> NULL` incluso bajo `UNIQUE`, lo que causó un bug real de filas duplicadas (`dim_plazo`/`fact_depositos`) corregido en `sql/10_fix_null_unique_constraints.sql`. La misma clase de bug estaba latente (no disparando aún, verificado 0 filas con `canton IS NULL` en 369.966/`staging.cartera` y 251.247/`staging.depositos`) en la llave natural de ambas tablas — corregida en `sql/23_fix_staging_cartera_canton_null_safe.sql` (índice de expresión `staging_cartera_natural_key_unique`) y `sql/24_fix_staging_depositos_canton_null_safe.sql` (índice de expresión `staging_depositos_natural_key_unique`), ambos sobre `COALESCE(canton, '')`, sentinela de cadena vacía consistente con el resto de columnas TEXT nullable en llaves naturales — `provincia`/`ruc`/`tipo_segmento`/`dimension_valor`.
- **Sin EAV en `marts`**: cada fuente de tasas tiene su propia tabla ancha con una columna por métrica real, en vez de una tabla genérica "tipo/valor". La única tabla "larga" es `staging.tasas_referenciales` (aterrizaje de las 5 secciones de `TasasHistorico.htm`, grano heterogéneo) — se ensancha a las 4 tablas de marts en `refresh_marts()`.
- **Indicadores financieros no se cargan como tabla**: son ratios recalculables desde `fact_balance`/`fact_pyg` (ver `docs/metricas_financieras.md`); cargarlos aparte arriesgaría reproducir la fórmula oficial de Superbancos distinto.
- **Alcance por fuente, no uniforme**: CAPCOL (`fact_saldo_cartera`/`fact_saldo_depositos`) y Boletín (`fact_balance`/`fact_pyg`) siguen filtrados a bancos privados en el `WHERE`/portal de origen. BCE (`fact_colocaciones_cartera`/`fact_captaciones_depositos`) **ya no se filtra** (corregido 2026-07-19) — cubre el sistema financiero completo, 442 entidades en `dim_banco`. Los catálogos (`dim_subsegmento_credito`, `dim_categoria_deposito`) siempre guardaron el universo completo sin filtrar.
- **`dim_segmento_credito`/`dim_subsegmento_credito`: jerarquía normativa de 2 niveles, no un rollup de texto libre** (2026-07-19): el segmento grueso (7 valores) y el subsegmento fino de BCE (26 valores) son dos dimensiones separadas unidas por FK — antes había una sola tabla con el rollup a CAPCOL como columna `TEXT` nullable, sin garantía de que coincidiera con `fact_cartera.tipo_credito` (también texto libre). `fact_saldo_cartera` (CAPCOL, solo reporta al nivel grueso) ahora referencia `dim_segmento_credito` directo; `fact_colocaciones_cartera`/`fact_tasas_referenciales_cartera` (BCE, reportan al nivel fino) referencian `dim_subsegmento_credito`. Ver `sql/16_dim_segmento_normativo.sql`.
- **Cobertura cargada** (2026-07): CAPCOL 2021-01 a 2026-06; BCE tsp/tsa 2008-2026 (semanal, histórico completo); `TasasHistorico.htm` 2022-04 a 2026-06 (páginas anteriores usan un layout HTML no soportado); Boletín BALANCE/PYG 2021-01 a 2026-06.
