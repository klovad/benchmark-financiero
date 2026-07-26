# Gobernanza de datos

Marco de gobernanza del proyecto: quién es responsable de qué, cómo se clasifica el
dato, qué garantías de calidad existen y dónde vive cada pieza de metadata. No repite
contenido que ya vive en otro documento — **enlaza** a la fuente autoritativa de cada
pieza y añade lo que hasta ahora no estaba consolidado en ningún lado: el catálogo de
metadatos por tabla/capa y las reglas de calidad explícitas.

## Los 3 pilares de la documentación (y dónde encaja el diagrama ER)

La gobernanza de este proyecto se apoya en 3 documentos, cada uno respondiendo una
pregunta distinta — **son complementarios, no redundantes**:

| Pregunta | Documento | Qué contiene |
|---|---|---|
| ¿Cómo se relacionan las tablas? | `docs/architecture.md` (sección "Modelo de datos") + el [diagrama ER interactivo](../docs/architecture.md) | Estructura del esquema estrella: 7 dimensiones, 10 hechos, 29 relaciones, cardinalidad, PK/FK. Es la vista **estructural**. |
| ¿Qué significa cada campo? | `docs/data_dictionary.md` | Definición de negocio de cada columna, grano de cada tabla, nulabilidad y por qué, decisiones de modelado. Es la vista **semántica**. |
| ¿De dónde vino cada campo y cómo se transformó? | `docs/linaje_datos.md` (nuevo) | Mapeo campo a campo `archivo fuente → raw → staging → marts`, con la función/módulo exacto que hizo cada transformación. Es la vista **de procedencia**. |

El diagrama ER (el artifact interactivo que se generó antes, y su versión Mermaid
versionada en `docs/architecture.md`) **es la pieza estructural de la gobernanza, no
toda la gobernanza**: muestra qué se relaciona con qué y las llaves, pero no dice qué
significa un campo, quién es responsable de él, cómo se clasifica, ni de dónde vino su
valor. Esas tres preguntas las cubren `data_dictionary.md`, este documento, y
`linaje_datos.md`, respectivamente. Este documento es el que amarra los 3 bajo un marco
único de gobernanza (responsable, clasificación, calidad, huecos conocidos).

## Responsabilidad y clasificación

- **Responsable (steward)**: Kevin Flores — autor y responsable único del proyecto.
  Proyecto individual, sin equipo ni áreas separadas de negocio/TI; no hay flujo de
  aprobación formal para cambios de esquema, solo el propio código y sus tests.
- **Clasificación de datos**: **Público**, en las 3 capas. Las 4 fuentes (CAPCOL,
  BCE, Boletín Financiero) son estadísticas oficiales publicadas abiertamente por la
  Superintendencia de Bancos y el Banco Central del Ecuador. No hay datos personales
  (PII) en ningún nivel de grano — el dato más fino es banco × cantón × producto ×
  fecha, nunca cliente individual. No aplican controles de confidencialidad,
  anonimización ni cifrado en reposo más allá de las credenciales de la base (`.env`,
  no versionado).
- **Retención**: sin política de purga — las 4 fuentes son series históricas y el valor
  del proyecto depende de mantener el histórico completo. `raw.*` es append-only por
  diseño (nunca se borra), `staging.*`/`marts.*` se actualizan in-place vía CDC (ver
  `docs/architecture.md`) pero tampoco se purgan filas.

## Catálogo de metadatos

### Capa `raw` — aterrizaje sin tipar, append-only

Ver la advertencia de "`raw.*` no es un espejo bit-a-bit" en `docs/linaje_datos.md` antes
de asumir que estas tablas son el archivo fuente sin tocar.

| Tabla | Fuente | Forma | Patrón de carga | Idempotencia |
|---|---|---|---|---|
| `raw.cartera` | CAPCOL cartera | `(source_file, source_hash, sheet_name, row_number, anio, mes, data JSONB)` | `executemany` INSERT, un archivo = un año/segmento | `raw.source_files` (`source_file`+`source_hash`) — un archivo con el mismo hash no se reprocesa |
| `raw.depositos` | CAPCOL depósitos | igual forma que `raw.cartera` | igual | igual |
| `raw.bce_tasas_pasivas` | BCE tsp | `(source_file, source_hash, anio, mes, data JSONB)` | `COPY` (bulk, cientos de miles de filas) | mismo mecanismo, pero **un solo archivo acumulativo** (2008-actualidad) — se reprocesa completo solo si el ZIP que publica el BCE cambia de hash |
| `raw.bce_tasas_activas` | BCE tsa | igual forma | `COPY` | igual (archivo acumulativo propio) |
| `raw.tasas_referenciales` | BCE `TasasHistorico.htm` | igual forma | `executemany` (volumen pequeño, ~40 filas/mes) | un archivo HTML por mes, mismo mecanismo que CAPCOL |
| `raw.boletin_balance` / `raw.boletin_pyg` | Boletín BALANCE / PYG | igual forma | `COPY` | un archivo por mes, mismo mecanismo |
| `raw.source_files` | — (tabla de control) | `(source_file PK, source_hash, report_type, loaded_at)` | — | Es el mecanismo de idempotencia mismo, no una tabla de datos |

### Capa `staging` — tipada, catálogos conformados ya resueltos, CDC

| Tabla | Llave natural (`ON CONFLICT`) | Resolución de identidad aplicada | CDC |
|---|---|---|---|
| `staging.cartera` | `(fecha, tipo_entidad, banco, canton, tipo_credito, estado_cartera)` | `banco_codigo` vía `banco_matching.py` | Sí |
| `staging.depositos` | `(fecha, tipo_entidad, banco, canton, tipo_deposito)` | `banco_codigo` + `categoria_deposito`/`plazo_dias_*` vía `banco_matching.py` + `categoria_deposito_matching.py` | Sí |
| `staging.bce_tasas_pasivas` | `(fecha, banco_codigo, categoria_deposito, plazo_dias_desde, COALESCE(plazo_dias_hasta,-1), COALESCE(provincia,''))` | `banco_codigo` + `plazo_dias_*` vía `resolver_entidad_bce()` + `bce_plazo_matching.py` — **todas las entidades del sistema financiero, no solo bancos privados** (corregido 2026-07-19, ver abajo) | Sí |
| `staging.bce_tasas_activas` | `(fecha, banco_codigo, segmento_credito, plazo_dias_desde, COALESCE(plazo_dias_hasta,-1), COALESCE(provincia,''))` | igual + `segmento_credito` validado contra universo de 26 | Sí |
| `staging.tasas_referenciales` | `(fecha, seccion, COALESCE(dimension_valor,''), COALESCE(plazo_dias_desde,-1), COALESCE(plazo_dias_hasta,-1), metrica)` | `dimension_valor` armonizado a los nombres ya sembrados en `dim_subsegmento_credito`/`dim_categoria_deposito` (alias explícitos, ver `linaje_datos.md`) | Sí |
| `staging.boletin_balance` / `boletin_pyg` | `(fecha, banco_codigo, codigo)` | `banco_codigo` vía `banco_matching.py` (fuente `"BOLETIN"`) | Sí |
| `staging.banco_maestro` | `banco_codigo` (PK) | Dos mecanismos: (1) sembrada desde `etl/seeds/banco_maestro.csv` para los ~33 bancos privados curados (`load_banco_maestro_seed`, banco/tipo_entidad); (2) **`ruc` poblado para TODAS las entidades y fila creada para las ~420 no-privadas** (`upsert_banco_maestro_ruc`, `ON CONFLICT DO UPDATE SET ruc`, 2026-07-23) — ver "Identidad para el universo completo del sistema financiero" abajo | No (se resiembra/complementa en cada corrida, `ON CONFLICT DO NOTHING`/`DO UPDATE` sin CDC propio) |

### Identidad para el universo completo del sistema financiero (BCE, 2026-07-19)

El usuario detectó que `raw.bce_tasas_pasivas`/`activas` estaban filtrados a
`tipo_entidad = 'BANCOS PRIVADOS'` **antes** de persistir cualquier fila, perdiendo para
siempre ~85% del archivo (el sistema financiero completo: 456-466 entidades reales,
confirmado contando distintos `(tipo_entidad, ruc, razon_social)` en el archivo sin
filtro — 394-402 de ellas son cooperativas de ahorro y crédito). Pidió explícitamente que
se preservara todo, en todas las capas, para poder analizar el sistema financiero
completo más adelante sin re-descargar. Corregido: `raw.*` captura las 6 categorías tal
cual (`read_raw()`); `staging`/`marts` resuelven identidad para todas con **dos caminos
deliberadamente distintos** (`etl/transform/banco_matching.py::resolver_entidad_bce`):

- **Bancos privados** (37 nombres crudos → 33 `banco_codigo` curados): identidad curada
  de siempre (`banco_crosswalk.csv`, `BancoNoResueltoError` si no resuelve) — necesitan
  alinearse con CAPCOL/Boletín, 3 fuentes describiendo el mismo banco.
- **Todo lo demás** (~420 entidades reales): **auto-registradas por RUC**
  (`banco_codigo = "BCE_" + ruc`), sin curación manual. A esa escala, curar 420 nombres a
  mano es inviable y de alto riesgo de error; y no hay ninguna otra fuente (CAPCOL/
  Boletín) con la que alinear estas entidades todavía, así que la curación no aporta
  valor hoy — si el proyecto agrega una fuente específica de cooperativas más adelante,
  ESE día hace falta un crosswalk real para esas ~420 entidades, no antes. El RUC se
  eligió por ser estable ante renames de razón social — mismo criterio que ya resolvió el
  bug real de continuidad de Comercial de Manabí/Amibank (ver [[project-capcol-data-source]]),
  aplicado acá de forma sistemática en vez de caso por caso.

Verificado contra archivos reales (2026-07-19): el subconjunto de bancos privados en el
resultado final es **idéntico** al conteo verificado antes del fix (485.588 filas en
`fact_captaciones_depositos`, 1.462.134 en `fact_colocaciones_cartera` — nombres desde el
renombrado de tablas del mismo día, ver más abajo) — confirma que el fix no alteró ese
subconjunto, solo agregó lo que antes se perdía. `dim_banco` terminó con 442 bancos
(33 curados + 409 auto-registrados). `staging.bce_tasas_pasivas`/`activas` no tienen
filas huérfanas: conteo `staging` = `marts` exacto en ambas (1.956.386 y 4.869.696).

### Capa `marts` — esquema estrella conformado

Detalle completo de columnas en `docs/data_dictionary.md`; acá solo el resumen de
gobernanza (rol, cadencia, volumen conocido). Nombres de tabla actualizados 2026-07-19
(ver "Renombrado de tablas de hechos" más abajo) — nombre anterior entre paréntesis.

| Tabla | Rol | Cadencia de la fuente | Cobertura cargada | Volumen (última medición) |
|---|---|---|---|---|
| `dim_fecha` | Dimensión conformada, grano día | — | derivada del resto | — |
| `dim_banco` | Dimensión conformada | — | 2021–2026 | 442 (33 bancos privados curados + 409 entidades BCE auto-registradas por RUC — cooperativas, bancos públicos, mutualistas, sociedad financiera, tarjetas de crédito; medido 2026-07-19) |
| `dim_canton` | Dimensión conformada | — | derivada de CAPCOL | — |
| `dim_segmento_credito` | Catálogo, segmento normativo de crédito (nivel grueso — 2026-07-19: nombre reasignado, ver "Normalización de la segmentación de crédito" abajo) | — | sembrado una vez (`sql/16`) | 7 filas |
| `dim_subsegmento_credito` (antes `dim_segmento_credito`) | Catálogo (universo BCE, no filtrado por entidad; nivel fino) | — | sembrado una vez (`sql/08`) | 26 filas |
| `dim_categoria_deposito` | Catálogo | — | sembrado una vez (`sql/08`) | 11 filas |
| `dim_plazo` | Catálogo abierto, auto-descubierto | — | crece con cada fuente nueva | no fijo por diseño |
| `dim_cuenta_contable` | Catálogo (Catálogo Único de Cuentas) | — | descubierto del Boletín | ~1500 cuentas (BALANCE+PYG, según comentario de `upsert_dim_cuenta_contable`) |
| `fact_saldo_cartera` (antes `fact_cartera`) | Hecho, CAPCOL | Mensual | 2021-01 a 2025-12 | 336.030 filas (medido 2026-07-19) |
| `fact_saldo_depositos` (antes `fact_depositos`) | Hecho, CAPCOL | Mensual | 2021-01 a 2025-12 | 229.034 filas (medido 2026-07-19, verificación CDC post-fix `sql/10`) |
| `fact_captaciones_depositos` (antes `fact_tasas_pasivas`) | Hecho, BCE tsp — **sistema financiero completo**, no solo bancos privados | Semanal | 2008-01 a 2026 (histórico completo) | 1.956.386 filas (medido 2026-07-19, post-fix de filtro — 485.588 bancos privados + 1.470.798 resto del sistema) |
| `fact_colocaciones_cartera` (antes `fact_tasas_activas`) | Hecho, BCE tsa — **sistema financiero completo**, no solo bancos privados | Semanal | 2008-01 a 2026 (histórico completo) | 4.869.696 filas (medido 2026-07-19, post-fix de filtro — 1.462.134 bancos privados + 3.407.562 resto del sistema) |
| `fact_tasas_referenciales_cartera` (antes `fact_tasas_referenciales_credito`) | Hecho, BCE `TasasHistorico`, nivel sistema | Mensual | 2022-04 a 2026-06 | 611 filas (medido 2026-07-19) |
| `fact_tasas_referenciales_depositos_instrumento` (antes `fact_tasas_pasivas_instrumento`) | Hecho, BCE `TasasHistorico`, nivel sistema | Mensual | 2022-04 a 2026-06 | 255 filas (medido 2026-07-19) |
| `fact_tasas_referenciales_depositos_plazo` (antes `fact_tasas_pasivas_plazo`) | Hecho, BCE `TasasHistorico`, nivel sistema | Mensual | 2022-04 a 2026-06 | 306 filas (medido 2026-07-19) |
| `fact_tasas_referenciales_sistema` (sin cambio de nombre) | Hecho, BCE `TasasHistorico`, nivel sistema | Mensual | 2022-04 a 2026-06 | 51 filas (medido 2026-07-19; ≤ 1 fila/mes por diseño, PK=`fecha_id`) |
| `fact_balance` | Hecho, Boletín | Mensual | 2021-01 a 2026-06 | 2.180.784 filas (medido 2026-07-19) |
| `fact_pyg` | Hecho, Boletín | Mensual | 2021-01 a 2026-06 | 192.489 filas (medido 2026-07-19) |

## Renombrado de tablas de hechos (2026-07-19)

El usuario revisó los nombres originales y encontró 2 problemas reales: (1)
`fact_tasas_pasivas`/`fact_tasas_activas` describían el mecanismo de la fuente (tasas
del BCE), no el negocio (captaciones de depósitos / colocaciones de crédito), y se
confundían fácilmente con las tablas de techos/referenciales; (2) de esas 4 tablas de
referenciales, solo 2 usaban la palabra "referenciales" en el nombre. Se acordó un
glosario de negocio consistente (`sql/15_rename_fact_tables.sql`):

| Nombre anterior | Nombre actual |
|---|---|
| `fact_cartera` | `fact_saldo_cartera` |
| `fact_depositos` | `fact_saldo_depositos` |
| `fact_tasas_activas` | `fact_colocaciones_cartera` |
| `fact_tasas_pasivas` | `fact_captaciones_depositos` |
| `fact_tasas_referenciales_credito` | `fact_tasas_referenciales_cartera` |
| `fact_tasas_pasivas_instrumento` | `fact_tasas_referenciales_depositos_instrumento` |
| `fact_tasas_pasivas_plazo` | `fact_tasas_referenciales_depositos_plazo` |
| `fact_tasas_referenciales_sistema` | (sin cambio) |

Regla de plural/singular aplicada (a pedido explícito del usuario): el esquema ya era
mayormente singular (`dim_banco`, `dim_fecha`, `fact_balance`...); el calificador genérico va
singular (`saldo_`, no `saldos_`) para mantener esa convención, pero los términos de
negocio que son naturalmente plurales en español financiero (`depositos`,
`colocaciones`, `captaciones`, `tasas`, `referenciales`) se dejan en su número real —
forzarlos a singular distorsionaría el término tal como lo usa el sector. De paso se
eliminaron 3 columnas nunca pobladas (`saldo_x_tasa`/`tasa_ponderada` en las 2 tablas de
saldo; `morosidad` en `fact_saldo_cartera`) y 2 vistas que dependían de ellas y ya
estaban muertas en la práctica (`vw_cartera_tasa_ponderada`, `vw_depositos_tasa_ponderada`).
Verificado: conteos idénticos antes/después del rename en las 10 tablas, `refresh_marts()`
corre sin error, CDC no-op confirmado, 37 tests pasan.

Los volúmenes de esta tabla y la del renombrado son mediciones puntuales de 2026-07-19,
no se actualizan automáticamente; `SELECT COUNT(*)` directo contra la base es la fuente
de verdad si se necesita un valor vigente.

## Normalización de la segmentación de crédito (2026-07-19)

El usuario notó que `fact_saldo_cartera.tipo_credito` era texto libre en vez de FK, y
preguntó por qué no referenciaba `dim_segmento_credito` — la respuesta reveló un choque de
grano real, no un descuido: `dim_segmento_credito` (como se llamaba entonces) tenía el
grano del **sub-segmento fino de BCE** (26 valores), y CAPCOL nunca reporta a ese nivel,
solo al **segmento normativo grueso** (6 valores). El rollup entre ambos vivía como una
columna `tipo_credito_capcol TEXT` nullable en la misma tabla — texto libre, sin FK, sin
garantía de que coincidiera con `fact_cartera.tipo_credito` (también texto libre) si
alguno de los dos cambiaba. Y 4 de los 26 sub-segmentos quedaban con `tipo_credito_capcol
= NULL` por no tener equivalente en bancos privados, en vez de tener su segmento
normativo real asignado.

**Solución acordada con el usuario** (`sql/16_dim_segmento_normativo.sql`): dos
dimensiones normalizadas por FK, patrón Kimball de "outrigger" — dos hechos en grano
distinto comparten la dimensión gruesa en vez de forzar uno al grano fino del otro:

- **`marts.dim_segmento_credito`** (nueva, 7 filas, MAYÚSCULAS): el segmento normativo de
  la cartera de crédito — `PRODUCTIVO`, `CONSUMO`, `EDUCATIVO`, `INMOBILIARIO`, `VIVIENDA
  DE INTERÉS PÚBLICO`, `MICROCRÉDITO`, `INVERSIÓN PÚBLICA`.
- **`marts.dim_subsegmento_credito`** (antes `dim_segmento_credito`, 26 filas): el
  sub-segmento fino tal como lo reporta BCE, con `segmento_id` FK obligatoria (ya no
  `tipo_credito_capcol` texto nullable) a la tabla anterior.
- **`fact_saldo_cartera`** (CAPCOL, solo reporta al nivel grueso): `tipo_credito` TEXT →
  `segmento_id` FK a `dim_segmento_credito`.
- **`fact_colocaciones_cartera`** / **`fact_tasas_referenciales_cartera`** (BCE, reportan
  al nivel fino): columna `segmento_id` renombrada a `subsegmento_id`, FK actualizada a
  `dim_subsegmento_credito`.

**Mapeo subsegmento → segmento**, con precisión sobre los 4 que antes quedaban en NULL:
`PRODUCTIVO` agrupa tanto la terminología vigente (Productivo Corporativo/Empresarial/
PYMES/Agrícola y Ganadero) como la previa a la revisión metodológica de abril-julio 2022
(JPRF-F-2022-031/053), que usaba "Comercial" para el mismo segmento — mismo segmento
normativo, dos nombres según la época de la serie histórica (2008-2026). `INMOBILIARIO`
agrupa esa forma y la forma histórica "Vivienda" (crédito de vivienda ordinario, no
social). `VIVIENDA DE INTERÉS PÚBLICO` agrupa esa forma y "Vivienda de Interés Social"
(mismo segmento de vivienda social/pública con techo de tasa propio). `MICROCRÉDITO`
agrupa las 7 variantes, incluidas las 3 con sufijo "(SE)" — Sector Financiero Popular y
Solidario, variante del mismo sub-segmento bajo la metodología de cooperativas, no un
segmento distinto. `INVERSIÓN PÚBLICA` es su propio segmento (aparece como línea propia,
no anidada bajo Productivo, en la sección "TASAS DE INTERÉS ACTIVAS MÁXIMAS VIGENTES" de
`TasasHistorico.htm` — ver `docs/fuentes_datos.md` sección 2.3). Con este mapeo ningún
sub-segmento queda sin `segmento_id`.

**Casing**: `dim_segmento_credito.segmento` se sembró en MAYÚSCULAS para mantener
consistencia con `dim_subsegmento_credito.subsegmento` y `dim_categoria_deposito.categoria`
(ambos ya en mayúsculas, tal como los reporta BCE) — evita mezclar convenciones dentro de
la misma jerarquía normativa. `staging.cartera.tipo_credito` (snake_case minúsculas,
convención de CAPCOL) no cambia — es la capa `staging`, se resuelve a `segmento_id` recién
en `refresh_marts()`, igual que `banco_codigo` se resuelve a `banco_id`.

Verificado: conteos idénticos antes/después de la migración en las 3 tablas afectadas
(`fact_saldo_cartera`=336.030, `fact_colocaciones_cartera`=4.869.696,
`fact_tasas_referenciales_cartera`=611), los 26 sub-segmentos con `segmento_id` no nulo,
`refresh_marts()` corre sin error, CDC no-op confirmado (0 filas con
`fecha_actualizacion > fecha_carga` tras el refresh), 37 tests pasan.

## Reglas de calidad de datos

Todas verificadas en código, no solo documentadas:

1. **Identidad curada, nunca autogenerada**: `banco_matching.py`, `categoria_deposito_matching.py`
   y `bce_plazo_matching.py` lanzan una excepción propia (`BancoNoResueltoError`,
   `CategoriaNoResueltaError`, `PlazoNoResueltoError`) ante un valor crudo no reconocido,
   en vez de crear una fila nueva silenciosa en el catálogo. Cubierto por
   `tests/test_banco_matching.py`, `tests/test_categoria_deposito_matching.py`,
   `tests/test_bce_plazo_matching.py`.
2. **Universo cerrado y validado en BCE**: `SEGMENTOS_VALIDOS` (26) y `CATEGORIAS_VALIDAS`
   (11) se validan explícitamente contra el valor real de cada fila de tsp/tsa antes de
   escribir a `staging.*` — un valor fuera del universo sembrado detiene la carga
   (`ValueError`/`SegmentoNoResueltoError`), no se descarta silenciosamente.
3. **Índices únicos NULL-safe**: todo `UNIQUE`/`ON CONFLICT` sobre una columna nullable
   (`plazo_dias_hasta`, `plazo_id`, `provincia`) usa `COALESCE(col, sentinela)` — bug real
   encontrado y corregido en `sql/10_fix_null_unique_constraints.sql` (Postgres trata
   `NULL <> NULL` incluso bajo `UNIQUE`, lo que duplicaba filas silenciosamente).
4. **CDC verificado, no solo implementado**: para cada una de las 4 fuentes se confirmó
   explícitamente que correr el pipeline dos veces seguidas sin datos nuevos no genera
   ningún `UPDATE` real (`fecha_actualizacion` sin cambios en la segunda corrida) — no es
   una propiedad asumida del diseño, se verificó contra la base real.
5. **Conteos `raw` = `staging` = `marts`**: verificado por fuente al cargar (ver
   `docs/architecture.md`, "Carga incremental"), no solo al momento de escribir el ETL.
6. **Fórmulas de negocio verificadas contra el valor oficial**: 3 de los 48 indicadores
   financieros del Boletín (`docs/metricas_financieras.md`) se recalcularon a mano desde
   `fact_balance`/`grupo_met` y coincidieron con el valor publicado por Superbancos a 6
   decimales — usado como comprobación de que una fórmula derivada es correcta antes de
   confiar en cualquier métrica calculada, no solo en que el dato cargó sin error.
7. **Suite de tests**: `tests/test_transform.py` (parsers CAPCOL, requiere archivos reales
   descargados — se salta si no están) + 5 archivos de tests puros sobre las funciones de
   matching/normalización (no requieren archivos externos): `test_banco_matching.py`,
   `test_categoria_deposito_matching.py`, `test_bce_plazo_matching.py`,
   `test_parse_boletin.py`, `test_parse_tasas_historicas.py` — 33 tests en total,
   incluyendo un test de regresión (`test_parse_filas_rastrea_seccion_sin_asumir_que_tabla_0_es_activa_maxima`)
   que fija explícitamente el bug real de inestabilidad de tabla en `TasasHistorico.htm`.

## Huecos de gobernanza conocidos

Documentados a propósito — no son bugs silenciosos, son decisiones de alcance o
limitaciones reales de la fuente que alguien retomando el proyecto debe conocer antes de
asumir que un campo "debería" tener datos:

| Hueco | Detalle | Dónde está documentado |
|---|---|---|
| ~~`dim_banco.tamano` / `dim_banco.ruc` nunca se pueblan~~ — **resuelto 2026-07-23, corregido de nuevo 2026-07-25** | `ruc` se activó: BCE tsp/tsa sí lo trae para todas las entidades, incluidos los 33 bancos privados curados — `resolver_entidad_bce()` lo descartaba en ese camino, ahora no. 442/442 filas con `ruc`. `tamano` se eliminó el 2026-07-23 con el diagnóstico "ninguna fuente trae GRANDE/MEDIANO/PEQUEÑO por banco individual" — **ese diagnóstico era incorrecto**: BCE tsp/tsa sí lo trae, bajo la columna `tipo_segmento`, que se venía descartando desde el inicio sin examinar su contenido (mismo patrón de error que ya pasó una vez con `ruc`: "columna siempre NULL" se asumió como "la fuente no lo tiene" sin verificar). Corregido 2026-07-25 con `dim_segmento_entidad` — ver fila abajo. | `sql/17_dim_banco_ruc_sin_tamano.sql`, `sql/19_dim_segmento_entidad.sql`, `docs/data_dictionary.md` |
| **`tipo_segmento` de BCE (clasificación normativa de tamaño/estructura por entidad) se descartaba antes de `staging` sin examinar su contenido** — resuelto 2026-07-25 | El usuario preguntó dónde se había considerado ese campo; la respuesta honesta fue que no se había considerado — se documentaba como "preservada en raw, descartada, no pasa a staging" sin haber leído nunca sus valores reales. Al investigar: 14 valores reales, incluye exactamente la clasificación GRANDE/MEDIANO/PEQUEÑO que se había dado por "no obtenible" 2 días antes (ver fila de arriba), más segmentación JPRF-F-2023-074 por activos para cooperativas (SEGMENTO 1-5/SIN SEGMENTO). Es un atributo de la entidad **en cada fecha**, no fijo (verificado: cooperativas reales cambian de segmento con los años) — se modeló al grano semanal de los hechos BCE (`dim_segmento_entidad` + FK), no como columna estática, con `dim_banco.segmento_entidad_id` como conveniencia de "última clasificación conocida". | `sql/19_dim_segmento_entidad.sql`, `docs/data_dictionary.md` |
| **Normalización de provincia** — `dim_canton.region` tenía 2 valores distintos para la misma provincia (bug real, no hipotético) | `marts.dim_canton` guardaba `provincia`/`region` como texto suelto, uno por fuente: `parse_cartera.py` derivaba `region` de `PROVINCIA_REGION` (`ORIENTE` para MORONA SANTIAGO), `parse_depositos.py` confiaba en la columna `REGION` del archivo fuente de Superbancos (`AMAZONICA` para la misma provincia) — distintos cantones de Morona Santiago terminaban con regiones distintas en `dim_canton` según de qué reporte vinieran. Encontrado 2026-07-25 al normalizar `provincia` en los hechos BCE (que solo traen provincia, sin cantón, y no tenían dimensión propia). Corregido con `dim_provincia` como única fuente de verdad para `region` (ya no se puede repetir: `dim_canton`/`fact_captaciones_depositos`/`fact_colocaciones_cartera` solo referencian `provincia_id`, `region` vive una sola vez) y `parse_depositos.py` ya no confía en la columna `REGION` del archivo. También normaliza ortografía: BCE trae provincias con tilde (`BOLÍVAR`), CAPCOL sin tilde salvo la Ñ (`BOLIVAR`, `CAÑAR`) — homologado con `normalize_provincia()`. | `sql/20_dim_provincia.sql`, `etl/transform/common.py::normalize_provincia`, `docs/data_dictionary.md` |
| ~~`fact_cartera.tasa_ponderada` / `.morosidad` / `.saldo_x_tasa` nunca se pueblan~~ — **resuelto 2026-07-19** | Estaban reservadas desde v1, nunca escritas por `refresh_marts()`. Eliminadas junto con el renombrado de tablas (`sql/15_rename_fact_tables.sql`) — la tasa real ya vive en `fact_colocaciones_cartera`/`fact_captaciones_depositos` | `docs/linaje_datos.md`, `docs/data_dictionary.md`, sección "Renombrado de tablas de hechos" arriba |
| ~~`dim_producto_cartera` / `dim_producto_deposito` seguían existiendo en Postgres, huérfanas~~ — **confirmado ya no existen (2026-07-20)** | Las migraciones (`sql/08`, `sql/09`) dejaron de referenciarlas y no hay ningún `DROP TABLE` en `sql/*.sql` — pero `to_regclass('marts.dim_producto_cartera')`/`dim_producto_deposito` devuelve `NULL` en la base viva: no existen. Se dropearon en algún momento fuera de una migración versionada (no hay registro de cuándo/quién); el estado real y el modelo lógico (este catálogo, el diagrama ER) ya coinciden, solo esta fila estaba desactualizada. | Verificado directo contra Postgres en esta sesión |
| `TasasHistorico.htm` solo 2022-04 a 2026-06 | Páginas anteriores (2008–2022) usan un layout HTML distinto no soportado por el parser | `docs/fuentes_datos.md`, `docs/linaje_datos.md` |
| Boletín solo 2021-01 en adelante | No se intentó cargar años anteriores — decisión explícita de alcance | `docs/fuentes_datos.md` |
| `dim_cuenta_contable.grupo_met` no es partición limpia | Un mismo código de cuenta puede caer en 2+ grupos funcionales de la hoja `MET`; se guarda solo el primero encontrado | `docs/metricas_financieras.md` |
| ~~BCE tsp/tsa: `raw.*` no incluía el universo completo de entidades~~ — **resuelto 2026-07-19** | Estaba filtrado a bancos privados antes de persistir; corregido, `raw.*` ahora captura las 6 categorías completas y `staging`/`marts` resuelven identidad para todas (curada para privados, auto-registrada por RUC para el resto) | `docs/linaje_datos.md`, sección "Identidad para el universo completo del sistema financiero" arriba |
| Identidad auto-registrada por RUC (~420 entidades no-privadas) no está curada | A diferencia de los bancos privados, estas ~420 entidades no pasaron por revisión humana — el nombre/tipo_entidad viene tal cual del BCE. | `etl/transform/banco_matching.py::resolver_entidad_bce` |
| **7 pares de `dim_banco.banco_codigo` distintos comparten el mismo `ruc`** — confirmado 2026-07-23, no un riesgo teórico | Al activar `ruc` (ver fila de arriba) se pudo verificar por primera vez con datos reales, no solo sospechar: `DINERS CLUB`/`BP DINERS`, `BANCO AMIBANK S.A.`/`FINCA`/`BP FINCA S.A.` (3 vías, mismo RUC), `COOPERATIVA...DESARROLLO DE LOS PUEBLOS`/`BP...CODESARROLLO`, `BANCO ATLÁNTIDA S.A.`/`BP D-MIRO S.A.`, `VISIONFUND`/`BP VISIONFUND ECUADOR S.A.`, `M.M. JARAMILLO ARTEAGA`/`PROMERICA`, `COOPERATIVA...NACIONAL`/`BP COOPNACIONAL`. El patrón dominante **no es un error del BCE**, es una entidad que cambió de forma legal (cooperativa/financiera → banco privado licenciado) mientras BCE seguía usando el mismo RUC — `resolver_entidad_bce()` la resuelve por separado en cada lado porque enruta por `tipo_entidad_bce`, así que quedan como 2 filas distintas de `dim_banco` para el mismo contribuyente. **No se fusionó**: a diferencia del bug de Manabí/Amibank (mismo nombre, mismo tipo, typo de la fuente), acá el cambio de tipo de entidad es real y fusionar podría ocultar esa transición en vez de modelarla — es una decisión de negocio, no una limpieza mecánica. Cualquier análisis longitudinal por banco (o modelo predictivo) que agrupe por `banco_codigo` debe revisar esta lista si el banco de interés aparece en ella. | `SELECT ruc, count(*), string_agg(banco,' / ') FROM marts.dim_banco GROUP BY ruc HAVING count(*)>1` |
| `dim_banco` creció de ~33 a 442 filas de golpe | Efecto esperado del fix de arriba, no un bug — pero cualquier cálculo/reporte que asumía "todo `dim_banco` es banco privado" (ej. si el `.pbip` de Power BI algún día vuelve a usarse sin filtrar `tipo_entidad`) necesita revisarse | Este documento |
| ~~Power BI (`.pbip`) con nombres/columnas viejos~~ — **realineado 2026-07-23, actualizado de nuevo 2026-07-25** | Se actualizaron las 8 tablas ya modeladas (`fact_saldo_cartera`/`fact_saldo_depositos`, `dim_segmento_credito`, `dim_categoria_deposito` + `dim_plazo` nueva) para que coincidan con el esquema vivo — medidas DAX, relaciones y visuals del reporte incluidos. 2026-07-25: la normalización de `dim_canton.provincia`→`dim_provincia` (ver fila "Normalización de provincia" arriba) rompía 2 visuales del reporte (`page-geografico`, barras por provincia) que sí usaban ese campo directo — agregada `dim_provincia.tmdl` (9na tabla), relación `dim_canton→dim_provincia`, y los 2 `visual.json` actualizados a `Entity: "dim_provincia"`. **Sigue sin cubrir BCE/Boletín** (11 tablas más) ni el universo completo de `dim_banco` (el modelo solo trae bancos privados, coherente con su alcance actual) — eso es una expansión aparte, no un arreglo. | `README.md` |

## Gestión de cambios de esquema

No hay proceso formal (proyecto individual), pero el patrón que se ha seguido
consistentemente y debe mantenerse:

1. Cambios de esquema van en un archivo `sql/NN_descripcion.sql` numerado secuencialmente,
   nunca editando una migración ya aplicada.
2. Un catálogo nuevo o un valor nuevo de un catálogo existente (ej. un segmento de
   crédito nuevo) se agrega primero al *seed* o al set validado en Python
   (`etl/seeds/*.csv`, `SEGMENTOS_VALIDOS`, `CATEGORIAS_VALIDAS`) — nunca se relaja una
   validación para "dejar pasar" un valor no reconocido.
3. Toda columna nullable que entre a formar parte de una llave natural/`UNIQUE` debe
   usar el patrón `COALESCE(col, sentinela)` desde el inicio (regla adoptada después del
   bug real de `sql/10`, ver "Reglas de calidad" arriba).
4. Después de un cambio de esquema, actualizar en el mismo cambio: `docs/data_dictionary.md`
   (si cambian columnas), `docs/linaje_datos.md` (si cambia una transformación) y el
   diagrama ER en `docs/architecture.md` (si cambian tablas o relaciones) — los 3
   documentos deben describir el mismo estado vivo, no una versión pasada.
