# Diccionario de datos

Esquema estrella en Postgres (`marts.*`), poblado desde 5 fuentes: CAPCOL (Superbancos,
cartera/depósitos de bancos privados y de Banca Pública), BCE (tasas de interés semanales
y `TasasHistorico.htm`), Boletín Financiero Mensual (Superbancos, balance/PyG de bancos
privados) y SEPS (cartera, depósitos y estados financieros de cooperativas S1-S3 y
mutualistas). **Las tablas de hechos mezclan tipos de entidad**: filtrar o agrupar por
`dim_entidad.tipo_entidad` antes de sumar o comparar. Identidad
de banco y catálogos de producto/plazo son compartidos entre fuentes
(`src/benchmark_bancos/transform/banco_matching.py` y `categoria_deposito_matching.py` resuelven la
identidad antes de que el dato llegue a `staging.*` — ver `docs/architecture.md` para el
patrón de carga incremental). Para qué hacer cuando un valor crudo no resuelve o
aparece una fila `estado_validacion='AUTO_INGRESADO'` pendiente de revisión, ver el runbook
`docs/mantenimiento_catalogos.md`. Una 4ta fuente (SEPS — cooperativas y mutualistas) tiene
diseño completo y aprobado pero **no está implementada**; sus tablas propuestas (2
dimensiones + 1 fact nuevos, `staging.volumen_cartera`) NO aparecen en este documento
porque no existen en el esquema vivo — ver `docs/fuentes_datos.md` sección 4 para el diseño
completo.

## Dimensiones

### marts.dim_fecha (grano día)
| Columna | Tipo | Descripción |
|---|---|---|
| fecha_id | int (YYYYMMDD) | Llave sustituta |
| fecha | date | Fecha real (fin de mes para CAPCOL/Boletín, corte semanal para BCE) |
| anio, mes, dia, trimestre, nombre_mes | — | Derivados de fecha |
| anio_mes | int (YYYYMM) | Llave de roll-up para comparar grano mensual vs. semanal sin joins extra |

### marts.dim_entidad (antes `dim_banco`, renombrada 2026-10-09 en `sql/37_dim_entidad.sql`)

Entidades del sistema financiero, no solo bancos: de 444 filas, 39 son bancos y el resto
cooperativas, mutualistas, sociedades financieras, segundo piso y emisoras de tarjetas.
El renombre cubre solo `marts` (tabla, `banco_id` → `entidad_id` en los 6 hechos, columnas
de las vistas, `vw_banco_ruc_colisiones` → `vw_entidad_ruc_colisiones`); `staging`
conserva `banco_maestro`/`banco`/`banco_codigo` como espejo de las fuentes.

| Columna | Tipo | Descripción |
|---|---|---|
| entidad_id | serial | Llave sustituta (antes `banco_id`) |
| entidad_codigo | text | Identidad canónica resuelta en ETL (`banco_matching.py`), única entre las 5 fuentes (antes `banco_codigo`; en staging sigue siendo `banco_codigo`) |
| entidad | text | Nombre a mostrar (sembrado desde `src/benchmark_bancos/seeds/banco_maestro.csv`; antes `banco`) |
| tipo_entidad | text | 7 valores permitidos (CHECK constraint, `sql/07` ampliado en `sql/29`): BANCO PRIVADO, BANCO PUBLICO, COOPERATIVA, MUTUALISTA, SOCIEDAD FINANCIERA, TARJETAS DE CREDITO, ENTIDAD DE SEGUNDO PISO (**2026-09-30**, para CONAFIPS y Caja Central FINANCOOP de la SEPS). **Hoy (2026-10-05) 444 entidades**: 36 con identidad curada (33 bancos privados + 3 públicos de CAPCOL) y 408 auto-registrados por RUC desde BCE, ver `docs/gobernanza_datos.md`). **2026-09-01**: `BANCO PUBLICO` deja de ser un valor que solo escribe BCE — `staging.cartera`/`staging.depositos` (CAPCOL, sub-portal Banca Pública) también empiezan a traerlo, resuelto vía `src/benchmark_bancos/seeds/banco_crosswalk.csv` a la MISMA fila `BCE_<ruc>` que BCE ya había auto-registrado (no crea filas nuevas de `dim_entidad`) — ver `docs/fuentes_datos.md` sección 1.1 |
| ruc | text, nullable | Identificador fiscal, poblado desde BCE tsp/tsa y, desde 2026-09-30, desde la SEPS (que también lo trae por fila; CAPCOL y el Boletín no) — 2026-07-23: activado también para los 33 bancos privados curados, antes se descartaba en ese camino (`sql/17_dim_banco_ruc_sin_tamano.sql`); 444/444 filas con `ruc` (las 2 entidades de segundo piso lo traen de la SEPS). **No es único por banco**: 7 `ruc` distintos son compartidos por 2+ `banco_codigo` (ver `docs/gobernanza_datos.md`, "Huecos de gobernanza conocidos", y la vista `marts.vw_entidad_ruc_colisiones` más abajo para consultarlos directo). **Desde 2026-08-30, el RUC de las entidades no curadas pasa por validación estructural real** antes de resolverse (`src/benchmark_bancos/transform/banco_matching.py::validar_ruc_estructura`, `sql/26` no toca esto — es puramente Python, ver `resolver_entidad_bce` y `resolver_entidad_seps`) — 13 dígitos, código de provincia 01-24, tercer dígito 9 (sociedad privada/extranjera) o 6 (sector público), dígito verificador módulo 11. Un RUC no-privado que falle esta validación lanza `RucInvalidoError` (distinto de `EntidadBceNoMapeadaError`) y bloquea la carga en vez de auto-registrarse con un RUC malformado. Los 33 bancos privados curados **no** pasan por esta validación (su identidad ya está curada por nombre, el RUC es un atributo, no la llave) |
| segmento_entidad_id | int, FK, nullable | `dim_segmento_entidad.segmento_entidad_id` — **última** clasificación normativa de tamaño/estructura conocida para el banco (2026-07-25, `sql/19_dim_segmento_entidad.sql`), SCD tipo 1, actualizada en cada `refresh_marts()` desde la fila más reciente de `fact_captaciones_depositos`/`fact_colocaciones_cartera`. Para análisis histórico (la clasificación cambia en el tiempo) usar el `segmento_entidad_id` de esos hechos, no este — ver tabla abajo |
| estado_validacion | text, `CHECK IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO')` | Nueva 2026-08-30 (`sql/26_dim_banco_estado_validacion.sql`). Distingue identidad **curada** (`CONFIRMADO` — los 33 bancos privados y, desde 2026-10-05, los 3 públicos de CAPCOL en `banco_maestro.csv`, reafirmado en cada `load_banco_maestro_seed()`) de identidad **auto-registrada sin revisión humana** (`AUTO_INGRESADO`, DEFAULT — hoy 408 entidades registradas por RUC vía `resolver_entidad_bce()`/`resolver_entidad_seps()`, ver "Identidad auto-registrada por RUC" en `docs/gobernanza_datos.md`, hueco ya documentado desde antes pero ahora consultable directo en el dato en vez de solo en texto). `RECHAZADO` reservado para uso futuro, ningún flujo actual lo escribe. Backfill retroactivo de esta migración: 33 filas a `CONFIRMADO`, 409 a `AUTO_INGRESADO`, discriminadas por `banco_codigo` (los auto-registrados siempre tienen prefijo `BCE_`, verificado exacto contra la base viva antes de escribir el backfill — sin solapamiento ni resto) |
| **`tamano` (GRANDE/MEDIANO/PEQUEÑO) eliminada** (2026-07-23, `sql/17`) **y su reemplazo real encontrado 2 días después**: se creyó "no obtenible con las fuentes actuales", pero BCE tsp/tsa sí trae esta clasificación por banco individual bajo la columna `tipo_segmento`, descartada hasta entonces sin examinar su contenido — ver `dim_segmento_entidad` abajo y `docs/gobernanza_datos.md`. | | |
| **Nota de calidad resuelta**: `BP COMERCIAL DE MANABI`/`BP BANCO COMERCIAL DE MANABI` y `BANCO AMIBANK S.A.`/`BANCO AMIBANK S.A., EN LIQUIDACION` eran el mismo banco partido en 2 filas por un rename de la fuente CAPCOL — corregido vía crosswalk, ver `src/benchmark_bancos/seeds/banco_crosswalk.csv`. | | |
| **Bug de CDC real encontrado y corregido 2026-08-30** (preexistía desde `sql/19_dim_segmento_entidad.sql`, 2026-07-25 — no lo introdujo esta migración, quedó expuesto al verificar CDC no-op de punta a punta en vez de asumirlo) | El `INSERT INTO marts.dim_entidad ... ON CONFLICT` no listaba `segmento_entidad_id` entre sus columnas — Postgres computaba `EXCLUDED.segmento_entidad_id` como `NULL` (el valor por defecto de una columna omitida del INSERT, no el valor real de la fila en conflicto), así que `EXCLUDED.row_hash` casi nunca coincidía con el `row_hash` real de un banco con `segmento_entidad_id` ya poblado (prácticamente los 442) — el guard `WHERE row_hash IS DISTINCT FROM EXCLUDED.row_hash` disparaba un `UPDATE` real (`fecha_actualizacion = now()`) en **cada** `refresh_marts()`, no solo cuando algo cambiaba de verdad. Corregido con un `LEFT JOIN` a la propia `marts.dim_entidad` para que el INSERT lleve el `segmento_entidad_id` actual (esa columna sigue sin escribirse en el `SET` del `ON CONFLICT` — la mantiene el `UPDATE` SCD1 separado más abajo en `_REFRESH_MARTS_SQL`). Verificado tras el fix: 0 filas con `fecha_actualizacion` cambiada en una corrida de `refresh_marts()` sin datos nuevos. | | |

### marts.dim_provincia (2026-07-25, `sql/20_dim_provincia.sql`)
| provincia_id | serial | Llave sustituta |
| provincia | text, único | 24 provincias del Ecuador (ortografía canónica de CAPCOL: sin tilde salvo la Ñ — `BOLIVAR`, `CAÑAR`) + `ZONA NO DELIMITADA` (CAPCOL) + `S/N` (BCE, filas a nivel nacional sin desagregar), ambas con `region = NULL` |
| codigo_inec | char(2), único, nullable | Código oficial de provincia del INEC (Clasificador Geográfico Estadístico / DPA): `01` Azuay … `24` Santa Elena, `90` Zona no delimitada; `NULL` solo para `S/N`. 2026-10-09, `sql/36_codigos_inec.sql`, fuente `config/domain.py::PROVINCIA_CODIGO_INEC`. Ojo: `provincia_id` es una llave sustituta y **no** coincide con el código INEC (Napo: id 19, código 15) |
| region | text, nullable | Costa / Sierra / Oriente / Insular — **única fuente de verdad** en `marts` (antes duplicada como texto suelto en `dim_canton` y en `staging.depositos`, con valores inconsistentes entre sí para al menos una provincia — ver `docs/gobernanza_datos.md`, "Normalización de provincia") |
| **Compartida entre grano cantón (`dim_canton`) y grano provincia (BCE, sin cantón)** — antes `dim_canton` guardaba `provincia`/`region` como texto propio y `fact_captaciones_depositos`/`fact_colocaciones_cartera` guardaban `provincia` como texto suelto sin FK; ambas normalizadas contra este catálogo único. | | |

### marts.dim_canton
| canton_id | serial | Llave sustituta |
| canton | text | Ubicación de la oficina donde se registró la operación (no la residencia del cliente) |
| provincia_id | int, FK | `dim_provincia.provincia_id` — antes `provincia`/`region` como texto propio (ver `dim_provincia` arriba) |
| codigo_inec | char(4), único, nullable | Código oficial de cantón del INEC (DPA vigente, censo 2022), p. ej. `0901` Guayaquil, `2302` La Concordia. 2026-10-09, `sql/36_codigos_inec.sql`. Fuente de verdad: `seeds/canton_provincia.csv`; `refresh_marts()` lo sincroniza en cada corrida (`load_postgres.py::sincronizar_cantones_seed`) y marca esos pares `CONFIRMADO`. Hoy 223 filas: los 221 cantones vigentes con código, `LAS GOLONDRINAS` con el `9001` de la DPA 2012 y el placeholder `NACIONAL` sin código. Un cantón `AUTO_INGRESADO` nuevo queda sin código y el refresh avisa con WARNING. Es la llave para cruzar con mapas y datos del censo del INEC |
| **Provincia anterior fusionada (2026-10-09, `sql/36`)** | AGUARICO, LA JOYA DE LOS SACHAS y LORETO en Napo (Orellana desde 1998), SANTO DOMINGO en Pichincha (Santo Domingo de los Tsáchilas desde 2007) y LA CONCORDIA en Esmeraldas (Santo Domingo de los Tsáchilas desde 2012) eran el mismo cantón que su par vigente, pero algunas entidades los siguen reportando así (2015-2026). Se llevaron a la provincia vigente en toda la serie (geografía actual): `canton_matching.py::_ALIASES_PROVINCIA_ANTERIOR`. Los totales nacionales no cambiaron; se movieron, por ejemplo, ~929 M de cartera y ~1.161 M de depósitos de Esmeraldas a Santo Domingo de los Tsáchilas. Los homónimos reales del INEC (BOLIVAR Carchi/Manabí, OLMEDO Loja/Manabí) siguen siendo filas distintas | | |
| estado_validacion | text, `CHECK IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO')` | Nueva 2026-09-01 (`sql/28_bce_canton_grain.sql`), mismo mecanismo two-tier que `dim_plazo` (`sql/27`) — ver bloque debajo. Backfill retroactivo: las 228 filas vivas tras esta migración (132 preexistentes de CAPCOL + 96 sembradas por `sql/28`, incluido el placeholder `NACIONAL`) quedaron `CONFIRMADO`. Todo cantón nuevo insertado de aquí en adelante hereda el DEFAULT `AUTO_INGRESADO` sin cambio de código en `refresh_marts()` (el `INSERT INTO marts.dim_canton` no lista esta columna). `RECHAZADO` reservado, ningún flujo actual lo escribe |
| **Bug de descarte silencioso encontrado y mitigado 2026-08-30 (`src/benchmark_bancos/load/load_postgres.py::_log_cantones_no_resueltos`)** | El `INSERT INTO marts.dim_canton` de `refresh_marts()` usa un `INNER JOIN` contra `dim_provincia` (necesario: `provincia_id` es `NOT NULL`) — cualquier fila de `staging.cartera`/`staging.depositos` cuya `provincia` no matcheara contra `dim_provincia` (ni exacto ni vía `translate()`) se descartaba ahí sin error ni rastro. **No convertido en fail-fast ni en tabla de rechazos**: a diferencia de `dim_plazo`/`banco_codigo` (catálogos regulatorios cerrados donde un valor no resuelto es un dato mal identificado), `dim_canton` es geografía de bajo riesgo y, verificado contra la base viva en esta sesión, **0 filas de `staging.cartera`/`staging.depositos` caen hoy en este caso** — construir infraestructura de rechazos para 0 filas afectadas sería sobre-ingeniería. Se agregó `_log_cantones_no_resueltos(conn)`, llamada al inicio de cada `refresh_marts()`, que loguea WARNING con el detalle (provincia, filas, cantones distintos) si alguna vez ocurre, INFO "0 filas" si no — visible en cualquier corrida normal del pipeline en vez de requerir ir a buscarlo. | | |
| **Cambio de grano de BCE a cantón (2026-09-01, `sql/28_bce_canton_grain.sql`)** | `dim_canton` pasó de 132 a 228 filas: 95 pares `(canton, provincia)` net-new de BCE tsp/tsa (cooperativas/mutualistas pequeñas con oficina donde CAPCOL no opera, ej. `24 DE MAYO`, `ARCHIDONA`, `OLMEDO`) + 1 fila placeholder `canton='NACIONAL'` (`provincia_id` = la fila `S/N` ya sembrada en `dim_provincia`, `sql/20`) para las filas de BCE sin cantón desagregado — ver "Grano de BCE tsp/tsa" en `fact_captaciones_depositos`/`fact_colocaciones_cartera` más abajo para el detalle completo (universo neto, 5 alias descartados, homónimos en 2 provincias, sumabilidad). Resuelto en Python vía `src/benchmark_bancos/transform/canton_matching.py::resolver_canton_bce()`, universo curado en `src/benchmark_bancos/seeds/canton_provincia.csv` (228 pares; 223 con código INEC desde 2026-10-09, ver `codigo_inec` arriba). | | |
| **`marts.vw_dim_canton_geografia`** (vista, `sql/28`) | `es_geografia_conocida = (region IS NOT NULL)` por `canton_id`, vía `JOIN` a `dim_provincia`. **No** es una columna `GENERATED` en `dim_canton` — Postgres no permite que una columna `GENERATED ALWAYS AS (...) STORED` referencie otra tabla, y duplicar la nulidad de `region` como columna propia de `dim_canton` reabriría exactamente la redundancia que `sql/20_dim_provincia.sql` eliminó (2 fuentes de verdad para lo mismo). La vista da la misma ergonomía (sin recordar los valores mágicos `'NACIONAL'`/`'ZONA NO DELIMITADA'`) sin almacenamiento duplicado. Hoy 2 filas con `es_geografia_conocida=false`: `NACIONAL` (`S/N`) y `LAS GOLONDRINAS` (`ZONA NO DELIMITADA`, preexistente de CAPCOL). | | |

### marts.dim_segmento_entidad (2026-07-25, `sql/19_dim_segmento_entidad.sql`)
| segmento_entidad_id | serial | Llave sustituta |
| tipo_segmento | text, único | Clasificación normativa de tamaño/estructura de la ENTIDAD (no del producto — no confundir con `dim_segmento_credito`/`dim_subsegmento_credito`), 14 valores: `BANCO GRANDE`/`BANCO MEDIANO`/`BANCO PEQUEÑO` (bancos privados), `SEGMENTO 1`..`SEGMENTO 5`/`SIN SEGMENTO` (cooperativas, JPRF-F-2023-074, segmentación por activos), `SEGMENTO 1 MUTUALISTA` (mutualistas), una categoría única para bancos públicos/sociedad financiera/tarjetas de crédito |
| **Fuente**: columna `tipo_segmento` de BCE tsp/tsa, preservada en `raw.*` desde el inicio pero descartada antes de `staging` sin examinar su contenido — detectado 2026-07-25 (el usuario preguntó dónde se había considerado). **Es un atributo de la entidad EN CADA FECHA, no fijo** (verificado: cooperativas reales cambian de segmento con los años según crecen) — por eso vive al grano semanal de `fact_captaciones_depositos`/`fact_colocaciones_cartera`, no como columna estática; `dim_entidad.segmento_entidad_id` solo guarda la última clasificación conocida, de conveniencia. | | |

### marts.dim_segmento_credito (nivel grueso — 2026-07-19: nombre reasignado, antes lo tenía la tabla ahora `dim_subsegmento_credito`, ver abajo)
| segmento_id | serial | Llave sustituta |
| segmento | text | Segmento normativo de crédito (7 valores, MAYÚSCULAS): `PRODUCTIVO`, `CONSUMO`, `EDUCATIVO`, `INMOBILIARIO`, `VIVIENDA DE INTERÉS PÚBLICO`, `MICROCRÉDITO`, `INVERSIÓN PÚBLICA` |

### marts.dim_subsegmento_credito (nivel fino de BCE; antes `dim_segmento_credito`, renombrada 2026-07-19)
| subsegmento_id | serial | Llave sustituta |
| subsegmento | text | Sub-segmento tal como lo reporta BCE (26 valores, universo completo sin filtrar por tipo de entidad) |
| segmento_id | int, FK | `dim_segmento_credito.segmento_id` — reemplaza la columna `tipo_credito_capcol` (texto libre, nullable para 4 de los 26). Ahora es FK obligatoria: los 4 subsegmentos que antes quedaban NULL por no tener equivalente en CAPCOL sí tienen segmento normativo real (INVERSIÓN PÚBLICA es su propio segmento; las 3 variantes microcrédito "(SE)" son `MICROCRÉDITO`) — mapeo completo y su justificación en `sql/16_dim_segmento_normativo.sql` |

### marts.dim_categoria_deposito
| categoria_deposito_id | serial | Llave sustituta |
| categoria | text | 13 valores: 11 de CAPCOL/BCE + `DEPÓSITOS MONETARIOS` (agregado sin distinguir generan/no-generan intereses, encontrado en `TasasHistorico.htm`) + `DEPÓSITOS A LA VISTA` (SEPS, `sql/30`, 2026-09-30: taxonomía cooperativa vista/plazo/garantía/restringidos; no se asimila a ahorro ni a monetarios) |
| **Hueco de alcance real frente al plan de cuentas regulatorio** (verificado 2026-08-30): este catálogo curado (`src/benchmark_bancos/transform/categoria_deposito_matching.py::CATEGORIAS_VALIDAS`, fail-fast) no tiene equivalente para 5 sub-cuentas nivel-6 de `marts.dim_cuenta_contable` bajo `codigo='21'` (BALANCE): `210120` EJECUCIÓN PRESUPUESTARIA, `210125` DEPÓSITOS DE OTRAS INSTITUCIONES PARA ENCAJE, `210130` CHEQUES CERTIFICADOS, `210131` CHEQUES DE EMERGENCIA, `210140` OTROS DEPÓSITOS — CAPCOL nunca reportó estas 5 como categoría de producto propia. Es la causa estructural de por qué `SUM(fact_saldo_depositos.saldo)` no reconcilia exactamente contra `fact_balance` `codigo='21'` (mediana −0,7376% por banco × fecha, explica ~48% del gap agregado del histórico). Detalle completo: `docs/gobernanza_datos.md` (tabla "Huecos de gobernanza conocidos") y `docs/glosario_cuentas.md` §3. | | |

### marts.dim_plazo (catálogo por rango numérico, compartido entre fuentes)
| plazo_id | serial | Llave sustituta |
| dias_desde, dias_hasta | int, int nullable | `dias_hasta = NULL` significa sin límite superior |
| plazo_codigo | text | Texto original de la fuente, informativo |
| estado_validacion | text, `CHECK IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO')` | Nueva 2026-08-30 (`sql/27_dim_plazo_estado_validacion.sql`). Ver el bloque "Two-tier validation" justo abajo para el mecanismo completo. Backfill retroactivo: las 21 filas que ya existían antes de esta migración (el universo curado verificado el 2026-08-27) se marcaron `CONFIRMADO`. Todo bucket nuevo insertado de aquí en adelante hereda el DEFAULT `AUTO_INGRESADO` sin necesitar cambio de código en `_REFRESH_MARTS_SQL` (los 4 `INSERT INTO marts.dim_plazo` no listan esta columna). `RECHAZADO` reservado, ningún flujo actual lo escribe. **Misma nota de portabilidad/CDC que `dim_cuenta_contable`** (`sql/25`): `dim_plazo` no tiene `fecha_carga`/`fecha_actualizacion`/`row_hash` — se puebla vía `INSERT ... ON CONFLICT DO NOTHING` (catálogo auto-descubierto, no upsert-con-CDC), verificado directo contra el esquema vivo antes de escribir la migración |
| **No se fuerza equivalencia entre convenciones de distintas fuentes** — ej. CAPCOL "DE MÁS DE 361 DÍAS" y BCE tsp "g. MAS DE 360 DIAS" son filas distintas ((361,NULL) vs (360,NULL)), cada una con el límite real que reporta su fuente. | | |
| **Fail-fast desde 2026-08-27, relajado a two-tier desde 2026-08-30 (`sql/27_dim_plazo_estado_validacion.sql`)** — cada uno de los 4 puntos de validación de plazo (`src/benchmark_bancos/transform/bce_plazo_matching.py::validar_universo_plazos_bce()`/`resolver_plazo_bce()`, `src/benchmark_bancos/transform/categoria_deposito_matching.py::resolver_categoria_deposito()`, `src/benchmark_bancos/transform/parse_tasas_historicas.py::_resolver_plazo()`) hace ahora un chequeo en 2 niveles sobre el texto crudo de plazo, en vez de un gate único contra el universo enumerado: **(1) shape (regex de esa fuente) inválido, o rango inválido una vez resuelto** (`dias_desde < 0`, o `dias_desde > dias_hasta` cuando `dias_hasta` no es `NULL`, ver `bce_plazo_matching.py::validar_rango_plazo()`) **→ sigue lanzando `PlazoNoResueltoError`**, aborta la carga igual que antes — eso sigue siendo una anomalía real de parsing (ej. un rango invertido), no un bucket nuevo. **(2) shape válido y rango sano pero el texto no está en el universo enumerado** (`PLAZOS_TSP_VALIDOS` 7/`PLAZOS_TSA_VALIDOS` 14/`PLAZOS_VALIDOS` 5 CAPCOL/`PLAZOS_VALIDOS` 6 TasasHistorico, que siguen existiendo como referencia del universo CONFIRMADO pero ya no son un gate) **→ YA NO lanza**: se acepta, y al llegar a `marts.dim_plazo` vía el mismo `INSERT ... ON CONFLICT DO NOTHING` de siempre (`src/benchmark_bancos/load/load_postgres.py`, `_REFRESH_MARTS_SQL`) queda marcado `estado_validacion='AUTO_INGRESADO'` para revisión posterior, sin abortar el resto de la carga. **Por qué `dim_plazo` recibe two-tier y `dim_segmento_credito`/`dim_subsegmento_credito`/`dim_categoria_deposito`/`dim_segmento_entidad` NO** (siguen con fail-fast absoluto, `SEGMENTOS_VALIDOS`/`CATEGORIAS_VALIDAS` sin relajar): la distinción es sintaxis vs. semántica regulatoria. `dim_plazo` es un catálogo abierto por RANGO NUMÉRICO — el propio dato `(dias_desde, dias_hasta)` es autoexplicativo una vez que el shape matcheó, no requiere interpretación humana para saber qué significa un tramo de días nuevo. Los otros 4 catálogos son enumeraciones CERRADAS por definición normativa/regulatoria (los 7 segmentos de crédito de la JPRF, las 14 clasificaciones de tamaño de entidad, etc.) — un texto nuevo ahí podría ser un nombre distinto para un concepto ya existente (requiere mapeo, ver `sql/16_dim_segmento_normativo.sql`), un error de tipeo de la fuente, o un concepto regulatorio genuinamente nuevo, y distinguir esos 3 casos requiere revisión humana ANTES de aceptar la fila, no después. Verificado tras el cambio contra `staging.*` completo: los 4 universos previamente cerrados coinciden exactamente con lo observado (7 tsp, 14 tsa, 13 `tipo_deposito` de CAPCOL — de los cuales los 5 buckets de plazo resuelven igual que antes —, 6 pares `(dias_desde,dias_hasta)` de `pasiva_plazo`), y una corrida repetida del `INSERT` de `dim_plazo` produce las mismas 21 filas `CONFIRMADO` / 0 `AUTO_INGRESADO` en ambas pasadas (idempotente por construcción: `ON CONFLICT DO NOTHING`, sin `UPDATE`). | | |

### marts.dim_cuenta_contable (plan de cuentas del Boletín, BALANCE + PYG)
| cuenta_id | serial | Llave sustituta |
| reporte | text | BALANCE o PYG (llave natural es (reporte, codigo): el mismo código puede significar cosas distintas en cada reporte) |
| codigo, cuenta | text | Código jerárquico del Catálogo Único de Cuentas (1/2/4/6 dígitos) y su nombre |
| nivel | int | Profundidad = longitud del código |
| codigo_padre | text, nullable | Código del nivel inmediato superior |
| seccion | text | Derivada del primer dígito del código: 1 ACTIVO, 2 PASIVO, 3 PATRIMONIO, 4 GASTOS, 5 INGRESOS, 6 CONTINGENTE, 7 CUENTAS_DE_ORDEN |
| grupo_met | text, nullable | Agrupación funcional de la hoja `MET` (ACTIVOS LIQUIDOS, PASIVOS EXIGIBLES, etc.) — **no es partición limpia**, se guarda el primer grupo encontrado por código; ver `docs/metricas_financieras.md` |
| estado_validacion | text, `CHECK IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO')` | Nueva 2026-08-30 (`sql/25_dim_cuenta_contable_estado_validacion.sql`). `upsert_dim_cuenta_contable()` descubre cuentas nuevas del plan de cuentas directo de cada archivo del Boletín, sin curación humana (`ON CONFLICT DO UPDATE`, ver `src/benchmark_bancos/load/load_postgres.py`) — esta columna hace ese hecho consultable. Backfill retroactivo: las 1.736 cuentas que ya existían antes de esta migración se marcaron `CONFIRMADO` (han sobrevivido múltiples cargas del Boletín sin incidentes); toda cuenta nueva insertada de aquí en adelante hereda el DEFAULT `AUTO_INGRESADO` sin necesitar cambio de código en `upsert_dim_cuenta_contable()` (no lista la columna en su INSERT). `RECHAZADO` reservado, ningún flujo actual lo escribe. **Nota de portabilidad**: a diferencia de casi toda `staging`/`marts`, esta tabla no tiene `fecha_carga`/`fecha_actualizacion`/`row_hash` — no participa del patrón CDC del proyecto (se resiembra/enriquece en cada archivo, mismo criterio que `staging.banco_maestro`), así que no hubo `row_hash` que extender al agregar esta columna |

## Hechos

Nombres renombrados 2026-07-19 a un glosario de negocio consistente (decisión explícita
del usuario): **cartera** = negocio de crédito (siempre), **depositos** = negocio de
captación (siempre); **saldo_** = medida de balance (CAPCOL, mensual); **colocaciones_**/
**captaciones_** = tasa efectiva + monto por banco (BCE semanal); **tasas_referenciales_**
= techo/referencial a nivel sistema (BCE mensual, `TasasHistorico`). Nombre anterior
entre paréntesis en cada tabla, para quien busque referencias viejas.

### marts.fact_saldo_cartera (antes `fact_cartera`) — grano: fecha × banco × cantón × segmento — CAPCOL + SEPS, mensual

**Fuentes (2026-09-30)**: CAPCOL (bancos privados y públicos) y SEPS `Reporte_colocaciones` (cooperativas S1-S3, mutualistas y entidades de segundo piso). Para SEPS se suman fuera del grano el origen, el estado y la clase de la operación y la actividad económica, y se excluye `OPERACIONES CONTINGENTES`. Filtrar por `dim_entidad.tipo_entidad` para no mezclar sectores en un benchmark. **Mutualistas**: incluye cartera VIS/VIP vendida al fideicomiso y administrada por la entidad (fuera de la cuenta 14; en cuentas de orden `740170`/`740175`). Pichincha queda ~45% y Azuay ~34% por encima de su balance; ver `docs/fuentes_datos.md` §4.0. **Cooperativas emisoras de tarjetas** (JEP, OSCUS, Policía Nacional y otras con `210145`): el segmento CONSUMO de SEPS **excluye** la cartera de tarjetas de crédito, que sí está en la cuenta 1402 del EEFF y en el consumo de CAPCOL.

| segmento_id | int, FK | `dim_segmento_credito.segmento_id` (nivel grueso — CAPCOL nunca trae el sub-segmento fino de BCE). Hasta 2026-07-19 esta columna era `tipo_credito` (texto libre, sin FK); pasó a estar normalizada contra el mismo catálogo normativo que usan los hechos de BCE en vez de duplicar el nombre del segmento como texto suelto — ver `sql/16_dim_segmento_normativo.sql`. **Pendiente de implementación, diseño ya aprobado** (`docs/fuentes_datos.md` sección 1.1): el `INSERT` de `_REFRESH_MARTS_SQL` filtra hoy `WHERE s.tipo_entidad = 'BANCO PRIVADO'` — al integrar Banca Pública debe ampliarse a `IN ('BANCO PRIVADO', 'BANCO PUBLICO')`, y el segmento `INVERSIÓN PÚBLICA` (7ma fila de `dim_segmento_credito`, hoy poblada solo por BCE tsa) empezará a recibir filas de CAPCOL también |
| saldo_por_vencer, saldo_no_devenga_intereses, saldo_vencida | numeric | Saldo en USD por estado de cartera. **2026-07-25** (`sql/21_fact_saldo_cartera_pivot.sql`): antes `estado_cartera` era una dimensión degenerada partiendo el saldo en 3 filas por combinación de `(fecha, banco, cantón, segmento)` — un antipatrón EAV, no una dimensión real (los 3 estados son medidas mutuamente excluyentes del mismo hecho, siempre presentes juntas). Pivotado a 3 columnas, mismo criterio que ya usaba `fact_tasas_referenciales_cartera` (2 columnas de medida en vez de "tipo_tasa"+"valor"). El grano pasó de 369.966 a 123.322 filas (÷3, exacto — no había combinaciones con menos de 3 estados) |
| saldo_total | numeric, `GENERATED ALWAYS AS (...) STORED` | Suma de los 3 — una sola fuente de verdad, no algo que el ETL deba mantener sincronizado (mismo patrón que `row_hash` en todo el proyecto). `morosidad = (saldo_no_devenga_intereses + saldo_vencida) / saldo_total`, ya no requiere filtrar nada |

`saldo_x_tasa`, `tasa_ponderada`, `morosidad` (columnas nunca pobladas, reservadas en v1)
**se eliminaron** en `sql/15_rename_fact_tables.sql` — la tasa real por producto ya vive
en `fact_colocaciones_cartera`; `morosidad` es derivable de `estado_cartera` si hace falta.

### marts.fact_saldo_depositos (antes `fact_depositos`) — grano: fecha × banco × cantón × categoria_deposito × plazo — CAPCOL + SEPS, mensual

**Fuentes (2026-09-30)**: CAPCOL y SEPS `Boletin_captaciones`. SEPS no trae banda de plazo, así que sus filas tienen `plazo_id` NULL también en `DEPÓSITOS A PLAZO`. A diferencia de CAPCOL, SEPS **sí** concilia contra `fact_balance` `codigo='21'` (mediana 0,0000% por entidad × mes en 2025).

| saldo | numeric | Saldo en USD |
| numero_cuentas, numero_clientes | bigint | Sumados desde el detalle por cuenta contable del origen |
| plazo_id | int, nullable | NULL salvo que `categoria_deposito = 'DEPÓSITOS A PLAZO'` |
| **No reconcilia exactamente contra `fact_balance` `codigo='21'`** (verificado 2026-08-30) | `SUM(saldo)` por banco × fecha queda sistemáticamente por debajo del BALANCE (mediana de la diferencia %: −0,7376%) — hueco de alcance estructural de `dim_categoria_deposito`, no un bug. Detalle completo en la entrada de `dim_categoria_deposito` arriba y en `docs/gobernanza_datos.md`. | |

`saldo_x_tasa`/`tasa_ponderada` también eliminadas (mismo motivo — ver `fact_captaciones_depositos`).

### marts.fact_colocaciones_cartera (antes `fact_tasas_activas`) / marts.fact_captaciones_depositos (antes `fact_tasas_pasivas`) — grano: fecha × banco × categoría/subsegmento × plazo × cantón — BCE tsa/tsp, semanal
| subsegmento_id (solo cartera) | int, FK | `dim_subsegmento_credito.subsegmento_id` — nivel fino, columna llamada `segmento_id` hasta 2026-07-19 (ver `sql/16_dim_segmento_normativo.sql`) |
| canton_id | int, FK, nullable | `dim_canton.canton_id` (2026-09-01, `sql/28_bce_canton_grain.sql` — **reemplaza** `provincia_id`, ver bloque "Grano de BCE tsp/tsa" debajo). Provincia/región siguen disponibles vía el mismo snowflake que ya usan `fact_saldo_cartera`/`fact_saldo_depositos` de CAPCOL: `canton_id → dim_canton.provincia_id → dim_provincia` (o `marts.vw_dim_canton_geografia` para la versión ya resuelta con `es_geografia_conocida`) |
| segmento_entidad_id | int, FK, nullable | `dim_segmento_entidad.segmento_entidad_id` (2026-07-25, ver esa tabla arriba) — clasificación de tamaño/estructura del banco EN ESA FECHA |
| monto_total, numero_operaciones | numeric, int | Agregados de la semana reportados por el BCE |
| tasa_activa_efectiva/tasa_pasiva_efectiva, tasa_nominal | numeric | Las tasas efectivas reales por banco — esto es lo que CAPCOL no tenía |
| **Sistema financiero completo, no solo bancos privados** (corregido 2026-07-19) — `dim_entidad` tenía entonces 442 entidades (hoy 444: 36 curadas y 408 auto-registradas por RUC: cooperativas, bancos públicos, mutualistas, sociedad financiera, tarjetas de crédito y 2 de segundo piso). Ver `docs/gobernanza_datos.md`. | | |
| **Grano de BCE tsp/tsa: cantón, no provincia (2026-09-01, `sql/28_bce_canton_grain.sql`)** | Antes `src/benchmark_bancos/transform/parse_bce_tasas.py::_weighted_agg()` colapsaba cantón dentro de provincia ANTES de `staging` (el archivo fuente SÍ trae cantón). Se cambió al mismo patrón Kimball ya usado por CAPCOL (`dim_canton` FK directa, `dim_provincia` como outrigger vía `dim_canton.provincia_id`) — unifica las 2 convenciones de geografía que antes convivían en el esquema. `dim_canton` se expandió de 132 a 228 filas: 95 pares `(canton, provincia)` net-new + 1 placeholder `NACIONAL`/`S/N`. `provincia_id` **se eliminó** de estas 2 tablas (antes que canton_id, "una sola fuente de verdad por atributo", mismo criterio de `sql/20`) — `staging.bce_tasas_pasivas`/`staging.bce_tasas_activas` ganaron una columna `canton` (nullable) para sostener el nuevo grano. `fact_captaciones_depositos`/`fact_colocaciones_cartera` quedaron en 0 filas tras el `TRUNCATE` de esta migración, pero solo transitoriamente: `data-engineer` reprocesó el histórico completo (`_resolve_canton()` en el parser + `reprocess_bce_staging()` (backfill de un solo uso, eliminado del código el 2026-10-05)), verificado en producción el mismo 2026-09-01: **3.077.474 filas** (`fact_captaciones_depositos`) y **7.756.581 filas** (`fact_colocaciones_cartera`), 0 con `canton_id` NULL en ninguna. | | |
| **7 alias de escritura (5 de BCE + 2 de SEPS/Banca Pública), NO tratados como cantón nuevo** | `DISTRITO METROPOLITANO DE QUITO`→`QUITO`, `EL EMPALME`→`EMPALME`, `GENERAL ANTONIO ELIZALDE`→`GENERAL ANTONIO ELIZALDE (BUCAY)`, `PUEBLOVIEJO`→`PUEBLO VIEJO`, `SAN FRANCISCO DE ORELLANA`→`ORELLANA` — mismo cantón físico que CAPCOL ya sembraba con otra forma de texto, identificados con `difflib` + verificación manual contra la división político-administrativa real del Ecuador (no confundir con `PUERTO QUITO`, cantón real y distinto de Pichincha, que sí es net-new). Resueltos en `src/benchmark_bancos/transform/canton_matching.py::_ALIASES_CANTON`. **2026-10-09**: la tabla se aplica a todas las fuentes (también CAPCOL y SEPS, vía `aplicar_alias_canton()`) y suma 2 alias más, `ALFREDO BAQUERIZO MORENO`→`ALFREDO BAQUERIZO MORENO (JUJAN)` (SEPS) y `PABLO VI`→`PABLO SEXTO` (Banca Pública), que habían creado cantones duplicados `AUTO_INGRESADO`; verificados contra el clasificador del INEC (un solo cantón con ese nombre en la provincia) y fusionados en `sql/35_fusion_cantones_duplicados.sql`. `dim_canton` vuelve a 228 filas, todas `CONFIRMADO`. | | |
| **Homónimos reales en 2 provincias** — no rediseño de llave, solo poblarla con el par completo | `LA CONCORDIA` (Esmeraldas / Santo Domingo de los Tsáchilas, ya existía así), `SANTO DOMINGO` (Pichincha / Santo Domingo de los Tsáchilas), `BOLÍVAR` (Carchi / Manabí), `LORETO` y `AGUARICO` (Napo / Orellana, previos a la creación de la provincia de Orellana en 1998) — reclasificación administrativa histórica real, no error de dato. El `UNIQUE (canton, provincia_id)` de `dim_canton` ya soportaba esto. | | |
| **Sumabilidad — advertencia explícita** | `monto_total`/`numero_operaciones` son sumables SIEMPRE, incluyendo las filas `canton='NACIONAL'` — verificado que `NACIONAL` nunca se solapa con cantón real para la misma combinación (fecha, banco, instrumento, plazo). Un reporte que filtre solo cantones con `es_geografia_conocida=true` (excluyendo `NACIONAL`) **subcontará** — para varios instrumentos (`DEPÓSITOS DE AHORRO`, `DEPÓSITOS MONETARIOS QUE GENERAN INTERESES`, `FONDOS DE TARJETAHABIENTES`, `OPERACIONES DE REPORTO`: 100% `NACIONAL` siempre, productos sin oficina de apertura específica) perdería el 100% del volumen, no un margen menor. `tasa_activa_efectiva`/`tasa_pasiva_efectiva`/`tasa_nominal` **nunca** son sumables ni promediables simple — siempre reponderar por `monto_total` al resumir a un nivel más agregado (mismo criterio que ya aplica `_weighted_agg()` al reagregar de cantón a provincia/sistema). A grano cantón la mediana es de pocas operaciones por fila — una tasa calculada sobre 1-2 operaciones es ruido estadístico; se recomienda que la agregación POR DEFECTO de reportes de TASAS sea a nivel provincia o superior, aunque el almacenamiento quede a grano cantón (para no perder el dato crudo). | | |

### marts.fact_tasas_referenciales_cartera (antes `fact_tasas_referenciales_credito`) / fact_tasas_referenciales_depositos_instrumento (antes `fact_tasas_pasivas_instrumento`) / fact_tasas_referenciales_depositos_plazo (antes `fact_tasas_pasivas_plazo`) / fact_tasas_referenciales_sistema (sin cambio de nombre) — `TasasHistorico.htm`, mensual, nivel sistema (no por banco)
Techos regulatorios y tasas de referencia (TPR/TAR/Tasa Legal/Tasa Máxima Convencional)
contra las cuales comparar las tasas efectivas de `fact_captaciones_depositos`/
`fact_colocaciones_cartera`. Las 4 tablas comparten ahora el prefijo `tasas_referenciales_`
— antes 2 de las 4 no lo usaban (`fact_tasas_pasivas_instrumento`/`_plazo`), fácil de
confundir con las tasas efectivas por banco. `fact_tasas_referenciales_cartera.subsegmento_id`
(columna llamada `segmento_id` hasta 2026-07-19) FK a `dim_subsegmento_credito` — mismo
nivel fino que `fact_colocaciones_cartera`, no el segmento normativo grueso.

### marts.fact_balance / fact_pyg (grano: fecha × banco × cuenta_contable) — Boletín + SEPS EEFF, mensual
| saldo_usd / valor_usd | numeric | Ya en USD completos. Boletín: `x1000` aplicado en el parser (la fuente reporta en miles). SEPS: la fuente ya viene en USD |
| **SEPS (2026-09-30)** | Estados financieros mensuales de cooperativas S1-S3 y mutualistas, a 6 dígitos. Cuentas `4*`/`5*` → `fact_pyg`; el resto → `fact_balance`. **No se cargan filas con saldo 0 o vacío** (~70% del archivo): un código ausente para una entidad y fecha equivale a 0. Mismo Catálogo Único de Cuentas: las vistas `vw_cartera_bruta`, `vw_depositos_corto_plazo`, etc. funcionan igual para cooperativas | |

## Vistas analíticas (`sql/04_indexes_views.sql`)

4 vistas, no tablas materializadas (se recalculan en cada consulta) — features de
concentración de mercado ya resueltas, útiles como punto de partida para análisis o
modelos predictivos en vez de recalcular market share/HHI desde los `fact_*` cada vez:

| Vista | Grano | Columnas | Fórmula |
|---|---|---|---|
| `marts.vw_cartera_market_share` | fecha × banco | `saldo_entidad`, `saldo_total_mes`, `market_share_pct` | `SUM(saldo_total)` por banco sobre `fact_saldo_cartera` (columna `saldo_total` desde 2026-07-25, antes `saldo` — ver `sql/21_fact_saldo_cartera_pivot.sql`), y `market_share_pct = saldo_entidad / SUM(saldo_entidad) OVER (PARTITION BY fecha_id) * 100` |
| `marts.vw_cartera_hhi` | fecha | `hhi` | Índice Herfindahl-Hirschman: `SUM(market_share_pct^2)` sobre `vw_cartera_market_share`, redondeado a 2 decimales (rango teórico 0–10.000; > 2.500 se suele leer como mercado concentrado) |
| `marts.vw_depositos_market_share` | fecha × banco | igual que `vw_cartera_market_share` | igual, sobre `fact_saldo_depositos` |
| `marts.vw_depositos_hhi` | fecha | `hhi` | igual que `vw_cartera_hhi`, sobre `vw_depositos_market_share` |

Ambas vistas de market share solo cubren CAPCOL (`fact_saldo_cartera`/`fact_saldo_depositos`,
2021-01 a 2026-06) — no existe un equivalente para las tasas de BCE ni para el Boletín todavía.

### Vistas de conciliación — `marts.vw_conciliacion_saldos_balance` / `marts.vw_conciliacion_resumen` (`sql/39`, 2026-10-09)

| Vista | Grano | Columnas |
|---|---|---|
| `vw_conciliacion_saldos_balance` | entidad × mes × medida (`cartera`, `depositos`) | `fecha_id`, `entidad_id`, `tipo_entidad`, `medida`, `saldo_reportado` (suma de cantones de `fact_saldo_cartera.saldo_total` / `fact_saldo_depositos.saldo`), `saldo_contable` (`14 − 1499` / `21` de `fact_balance`), `diferencia_pct` |
| `vw_conciliacion_resumen` | mes × tipo de entidad × medida | `entidades`, `mediana_pct`, `dentro_05pct`, `dentro_2pct` (fracción de entidades dentro de ±0,5% / ±2%), `diferencia_agregada_pct` |

Solo entidades con estados financieros cargados (bancos privados vía Boletín, cooperativas y
mutualistas vía EEFF SEPS); la Banca Pública no tiene contra qué conciliar. Umbrales y
desvíos conocidos: `src/benchmark_bancos/conciliacion.py` y `docs/gobernanza_datos.md`,
regla 9.

### Vista de gobernanza — `marts.vw_entidad_ruc_colisiones` (`sql/22_vw_banco_ruc_colisiones.sql`)

**Para qué**: hace consultable directamente el hueco de gobernanza "7 pares de
`banco_codigo` distintos comparten el mismo `ruc`" (ver `docs/gobernanza_datos.md`,
"Huecos de gobernanza conocidos") — antes solo estaba documentado como prosa, con la
query de verificación mencionada en el propio documento pero no persistida en ningún
objeto de base de datos. Un analista que haga `SELECT * FROM marts.dim_entidad` no tiene
forma de descubrir la colisión sin haber leído ese documento primero; esta vista sí lo
muestra directo.

**Grano**: una fila por `(ruc, entidad_id)` — no por `ruc`. Solo incluye los `ruc` que
aparecen en 2 o más filas de `dim_entidad`.

**Columnas**: `ruc`, `entidad_id`, `banco_codigo`, `banco`, `tipo_entidad`.

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

**Estado (2026-10-02): aplicadas en la base viva**, junto con los ajustes de
`sql/32_vistas_glosario_seps_banca_publica.sql`. Validación: las 12 métricas que componen
(cartera bruta e improductiva, liquidez, morosidad de 5 segmentos, utilidad acumulada y
anualizada, ROA, ROE) coinciden **sin diferencias** contra
`scripts/compute_indicadores_excel.py` (verificado contra el Excel) para los 23 bancos
privados al corte 2026-03-31. En SEPS: `vw_pyg_total_gastos` = cuenta `4` en 11.585 de
11.585 entidad×mes, y los 7 segmentos cubren el 100% de la cartera bruta. `sql/32` agrega
los segmentos VIVIENDA DE INTERÉS PÚBLICO e INVERSIÓN PÚBLICA y `COALESCE` en 1499; deja
sin segmento, a propósito, las cuentas COVID-19 y COMERCIAL ORDINARIO/PRIORITARIO (en
bancos explican que la suma de segmentos dé 96,9%-100% de la cartera bruta). Costo:
`vw_activo_promedio_ytd`/`vw_patrimonio_promedio_ytd` tardan ~26 s en materializarse
completas (subconsultas correlacionadas); filtrar por `fecha_id`/`entidad_id` al consultarlas.

10 vistas, grano banco × fecha, que implementan los "bloques con nombre propio" documentados
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

No filtran por `tipo_entidad`, y **desde 2026-09-30 sí hace falta filtrar en el
consumidor**: `fact_balance`/`fact_pyg` traen bancos privados (Boletín) y cooperativas y
mutualistas (EEFF SEPS). Unir contra `dim_entidad.tipo_entidad` para no mezclar sectores. Escritas siguiendo la misma lógica de
[`scripts/compute_indicadores_excel.py`](../scripts/compute_indicadores_excel.py) (motor de
referencia en pandas, corrido y verificado contra `data/samples/marts_ultimos_13_meses`
-- antes `marts_full`, ver `data/samples/README.md`), pero **las
vistas SQL en sí no se ejecutaron todavía contra una instancia Postgres real** — validar
sintaxis en el primer uso real.

## Decisiones de modelado relevantes
- **Identidad de banco resuelta en ETL, no con tabla de alias en el esquema estrella**: `src/benchmark_bancos/transform/banco_matching.py` normaliza y resuelve `banco_codigo` antes de `staging.*`; `dim_entidad` se puebla desde `staging.banco_maestro` (sembrado desde `src/benchmark_bancos/seeds/banco_maestro.csv`).
- **Carga incremental (CDC), no full refresh**: `staging.*` y `marts.*` tienen `fecha_carga`/`fecha_actualizacion`; `fecha_actualizacion` solo se mueve si el dato realmente cambió (comparación directa de columnas en el upsert). Desde 2026-10-05 (`sql/34`) ya no existe la columna `row_hash`, y el refresh de marts es incremental por marca de agua (`meta.refresh_watermark`). Las menciones a `row_hash` en entradas anteriores de este documento son históricas. Ver `docs/architecture.md`.
- **Índices únicos NULL-safe**: cualquier `UNIQUE`/`ON CONFLICT` sobre una columna nullable (`dias_hasta`, `plazo_id`, `provincia_id`, `canton_id`, `staging.cartera.canton`, `staging.depositos.canton`) usa `COALESCE(col, sentinela)` — Postgres trata `NULL <> NULL` incluso bajo `UNIQUE`, lo que causó un bug real de filas duplicadas (`dim_plazo`/`fact_depositos`) corregido en `sql/10_fix_null_unique_constraints.sql`. La misma clase de bug estaba latente (no disparando aún, verificado 0 filas con `canton IS NULL` en 369.966/`staging.cartera` y 251.247/`staging.depositos`) en la llave natural de ambas tablas — corregida en `sql/23_fix_staging_cartera_canton_null_safe.sql` (índice de expresión `staging_cartera_natural_key_unique`) y `sql/24_fix_staging_depositos_canton_null_safe.sql` (índice de expresión `staging_depositos_natural_key_unique`), ambos sobre `COALESCE(canton, '')`, sentinela de cadena vacía consistente con el resto de columnas TEXT nullable en llaves naturales — `provincia`/`ruc`/`tipo_segmento`/`dimension_valor`.
- **Sin EAV en `marts`**: cada fuente de tasas tiene su propia tabla ancha con una columna por métrica real, en vez de una tabla genérica "tipo/valor". La única tabla "larga" es `staging.tasas_referenciales` (aterrizaje de las 5 secciones de `TasasHistorico.htm`, grano heterogéneo) — se ensancha a las 4 tablas de marts en `refresh_marts()`.
- **Indicadores financieros no se cargan como tabla**: son ratios recalculables desde `fact_balance`/`fact_pyg` (ver `docs/metricas_financieras.md`); cargarlos aparte arriesgaría reproducir la fórmula oficial de Superbancos distinto.
- **Alcance por tabla (2026-10-05)**: `fact_saldo_cartera`/`fact_saldo_depositos` = bancos privados y públicos (CAPCOL) + cooperativas, mutualistas y 2 entidades de segundo piso (SEPS). `fact_balance`/`fact_pyg` = bancos privados (Boletín) + cooperativas y mutualistas (EEFF SEPS); los bancos públicos no tienen fuente de balance cargada. BCE (`fact_colocaciones_cartera`/`fact_captaciones_depositos`) cubre el sistema financiero completo desde 2026-07-19. `dim_entidad` tiene 444 entidades (36 curadas, 408 auto-registradas). Los catálogos (`dim_subsegmento_credito`, `dim_categoria_deposito`) siempre guardaron el universo completo sin filtrar.
- **`dim_segmento_credito`/`dim_subsegmento_credito`: jerarquía normativa de 2 niveles, no un rollup de texto libre** (2026-07-19): el segmento grueso (7 valores) y el subsegmento fino de BCE (26 valores) son dos dimensiones separadas unidas por FK — antes había una sola tabla con el rollup a CAPCOL como columna `TEXT` nullable, sin garantía de que coincidiera con `fact_cartera.tipo_credito` (también texto libre). `fact_saldo_cartera` (CAPCOL, solo reporta al nivel grueso) ahora referencia `dim_segmento_credito` directo; `fact_colocaciones_cartera`/`fact_tasas_referenciales_cartera` (BCE, reportan al nivel fino) referencian `dim_subsegmento_credito`. Ver `sql/16_dim_segmento_normativo.sql`.
- **Cobertura cargada** (actualizada 2026-10-10): CAPCOL bancos privados y Banca Pública 2021-01 a 2026-08; SEPS (saldos y EEFF) 2021-01 a 2026-08; BCE tsp/tsa 2008-01 a 2026-09-24 (semanal, histórico completo); `TasasHistorico.htm` 2009-07 a 2026-09 (antes de 2009-07 fuera de alcance por decisión; 2009-09 excluido por formato irregular); Boletín BALANCE/PYG 2021-01 a 2026-09. Se actualiza solo cada semana (`benchmark-bancos actualizar`, tarea programada).
