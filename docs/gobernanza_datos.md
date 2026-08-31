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
| `staging.cartera` | `(fecha, tipo_entidad, banco, COALESCE(canton,''), tipo_credito, estado_cartera)` | `banco_codigo` vía `banco_matching.py` | Sí |
| `staging.depositos` | `(fecha, tipo_entidad, banco, COALESCE(canton,''), tipo_deposito)` | `banco_codigo` + `categoria_deposito`/`plazo_dias_*` vía `banco_matching.py` + `categoria_deposito_matching.py` | Sí |
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
  aplicado acá de forma sistemática en vez de caso por caso. **2026-08-30**: aunque no
  hay curación por nombre, el RUC que sostiene ese auto-registro sí pasa desde ahora por
  `validar_ruc_estructura()` (`etl/transform/banco_matching.py`) antes de aceptarse —
  13 dígitos, código de provincia 01-24 (sin la excepción "30 = extranjero" que aparece
  en fuentes no oficiales, deliberadamente no incluida por no poder confirmarse contra
  ninguna fuente autoritativa ni contra las 409 entidades reales ya cargadas), tercer
  dígito 9 (sociedad privada/extranjera) o 6 (sector público), dígito verificador módulo
  11 (algoritmo estándar del SRI para sociedades, contrastado contra una implementación
  de referencia pública independiente antes de confiar en el resultado). Un RUC que no
  pasa esta validación lanza `RucInvalidoError` y bloquea la fila en vez de auto-registrar
  una llave malformada — **no** es curación de identidad (sigue sin haber revisión humana
  de qué entidad es cada RUC), es una barrera de calidad de dato sobre el RUC mismo.
  Corrida contra las 409 entidades vigentes en `marts.dim_banco`: **0 rechazos** — el
  algoritmo no invalida ningún RUC ya confiado en producción (ver "Reglas de calidad de
  datos" #8 abajo para el detalle de la verificación).

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
| `dim_fecha` | Dimensión conformada, grano día | — | derivada del resto | 1.019 filas (medido 2026-07-25) |
| `dim_banco` | Dimensión conformada — `estado_validacion` (2026-08-30, `sql/26`) distingue las 2 poblaciones directo en el dato | — | 2021–2026 | 442 (33 bancos privados curados = `estado_validacion='CONFIRMADO'` + 409 entidades BCE auto-registradas por RUC = `estado_validacion='AUTO_INGRESADO'` — cooperativas, bancos públicos, mutualistas, sociedad financiera, tarjetas de crédito; medido 2026-07-19, split confirmado de nuevo 2026-08-30) |
| `dim_canton` | Dimensión conformada (2026-07-25: `provincia`/`region` texto → FK a `dim_provincia`) | — | derivada de CAPCOL | 132 filas (medido 2026-07-25) |
| `dim_provincia` | Dimensión conformada, outrigger de `dim_canton` y de los hechos BCE semanales (nueva 2026-07-25, `sql/20`) | — | sembrada una vez | 26 filas (24 provincias + `ZONA NO DELIMITADA` + `S/N`) |
| `dim_segmento_credito` | Catálogo, segmento normativo de crédito (nivel grueso — 2026-07-19: nombre reasignado, ver "Normalización de la segmentación de crédito" abajo) | — | sembrado una vez (`sql/16`) | 7 filas |
| `dim_subsegmento_credito` (antes `dim_segmento_credito`) | Catálogo (universo BCE, no filtrado por entidad; nivel fino) | — | sembrado una vez (`sql/08`) | 26 filas |
| `dim_segmento_entidad` | Catálogo, clasificación normativa de tamaño/estructura de la entidad (nueva 2026-07-25, `sql/19`) | — | sembrado una vez | 14 filas |
| `dim_categoria_deposito` | Catálogo | — | sembrado una vez (`sql/08`) | 11 filas |
| `dim_plazo` | Catálogo, two-tier desde 2026-08-30 (`sql/27` — antes fail-fast absoluto desde 2026-08-27, antes de eso abierto/sin validar; `estado_validacion` distingue las 2 poblaciones directo en el dato, mismo mecanismo que `dim_cuenta_contable`/`sql/25`) — ver "Reglas de calidad" #1/#2 abajo | — | shape+rango inválidos siguen abortando la carga (`PlazoNoResueltoError`); un bucket con shape+rango válidos pero fuera de `PLAZOS_TSP_VALIDOS`/`PLAZOS_TSA_VALIDOS`/`PLAZOS_VALIDOS` (CAPCOL)/`PLAZOS_VALIDOS` (TasasHistorico) ya no aborta — se auto-ingresa como `AUTO_INGRESADO` | 21 filas, todas `CONFIRMADO` (medido 2026-08-30 contra `marts.dim_plazo` tras `sql/27` — mismas 21 de la medición 2026-08-27, menos que 7+14+5+6=32 porque varios buckets coinciden exactamente en `(dias_desde, dias_hasta)` entre CAPCOL/tsp/tsa/TasasHistorico y comparten fila por el `UNIQUE (dias_desde, COALESCE(dias_hasta,-1))`) |
| `dim_cuenta_contable` | Catálogo (Catálogo Único de Cuentas) — `estado_validacion` (2026-08-30, `sql/25`) marca `CONFIRMADO` las cuentas preexistentes, `AUTO_INGRESADO` (default) las descubiertas de aquí en adelante sin curación | — | descubierto del Boletín | 1.736 cuentas (medido 2026-08-30 contra `marts.dim_cuenta_contable`, todas `CONFIRMADO` en el backfill retroactivo de `sql/25`) |
| `fact_saldo_cartera` (antes `fact_cartera`) | Hecho, CAPCOL — 2026-07-25: `estado_cartera` pivotado a columnas (`saldo_por_vencer`/`saldo_no_devenga_intereses`/`saldo_vencida`/`saldo_total`), ver `sql/21` | Mensual | 2021-01 a 2026-06 | 123.322 filas (medido 2026-07-25, post-pivote — antes 369.966 con `estado_cartera` como fila) |
| `fact_saldo_depositos` (antes `fact_depositos`) | Hecho, CAPCOL | Mensual | 2021-01 a 2026-06 | 251.247 filas (medido 2026-07-25) |
| `fact_captaciones_depositos` (antes `fact_tasas_pasivas`) | Hecho, BCE tsp — **sistema financiero completo**, no solo bancos privados; `provincia_id`/`segmento_entidad_id` agregados 2026-07-25 (`sql/19`, `sql/20`) | Semanal | 2008-01 a 2026-07 (histórico completo) | 1.956.386 filas (medido 2026-07-25) |
| `fact_colocaciones_cartera` (antes `fact_tasas_activas`) | Hecho, BCE tsa — **sistema financiero completo**, no solo bancos privados; `provincia_id`/`segmento_entidad_id` agregados 2026-07-25 (`sql/19`, `sql/20`) | Semanal | 2008-01 a 2026-07 (histórico completo) | 4.869.696 filas (medido 2026-07-25) |
| `fact_tasas_referenciales_cartera` (antes `fact_tasas_referenciales_credito`) | Hecho, BCE `TasasHistorico`, nivel sistema | Mensual | 2022-08 a 2026-06 | 611 filas (medido 2026-07-25) |
| `fact_tasas_referenciales_depositos_instrumento` (antes `fact_tasas_pasivas_instrumento`) | Hecho, BCE `TasasHistorico`, nivel sistema | Mensual | 2022-04 a 2026-06 | 255 filas (medido 2026-07-25) |
| `fact_tasas_referenciales_depositos_plazo` (antes `fact_tasas_pasivas_plazo`) | Hecho, BCE `TasasHistorico`, nivel sistema | Mensual | 2022-04 a 2026-06 | 306 filas (medido 2026-07-25) |
| `fact_tasas_referenciales_sistema` (sin cambio de nombre) | Hecho, BCE `TasasHistorico`, nivel sistema | Mensual | 2022-04 a 2026-06 | 51 filas (medido 2026-07-25; ≤ 1 fila/mes por diseño, PK=`fecha_id`) |
| `fact_balance` | Hecho, Boletín | Mensual | 2021-01 a 2026-06 | 2.180.784 filas (medido 2026-07-25) |
| `fact_pyg` | Hecho, Boletín | Mensual | 2021-01 a 2026-06 | 192.489 filas (medido 2026-07-25) |

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

1. **Identidad curada, nunca autogenerada**: `banco_matching.py`, `categoria_deposito_matching.py`,
   `bce_plazo_matching.py` y `parse_tasas_historicas.py` lanzan una excepción propia
   (`BancoNoResueltoError`, `CategoriaNoResueltaError`, `PlazoNoResueltoError`) ante un
   valor crudo no reconocido, en vez de crear una fila nueva silenciosa en el catálogo.
   Cubierto por `tests/test_banco_matching.py`, `tests/test_categoria_deposito_matching.py`,
   `tests/test_bce_plazo_matching.py`, `tests/test_parse_tasas_historicas.py`.
   **`dim_plazo` era la excepción a esta regla hasta 2026-08-27** (crecía vía
   `INSERT ... ON CONFLICT DO NOTHING` en `refresh_marts()`, sin validar contra ningún
   universo conocido — cualquier texto que matcheara el *shape* regex de un bucket se
   aceptaba sin revisión) — cerrado con `PLAZOS_TSP_VALIDOS`/`PLAZOS_TSA_VALIDOS`
   (`bce_plazo_matching.py::validar_universo_plazos_bce()`) y sets `PLAZOS_VALIDOS`
   análogos en `categoria_deposito_matching.py` (CAPCOL) y `parse_tasas_historicas.py`
   (`TasasHistorico.htm`); los 3 caminos ahora comparten `PlazoNoResueltoError`, igual
   que `BancoNoResueltoError` centraliza la identidad de banco. Verificado contra
   `raw.*` completo (no solo `staging`, que puede estar en una ventana más chica): los
   universos válidos codificados coinciden exactamente con el histórico completo
   ingerido en las 4 fuentes (tsp: 7, tsa: 14, CAPCOL: 5, TasasHistorico: 6) — ningún
   bucket real actual queda fuera.
   **Relajado a two-tier el 2026-08-30 (`sql/27_dim_plazo_estado_validacion.sql`,
   decisión explícita del usuario)**: el fail-fast absoluto de 2026-08-27 pasó a un
   chequeo de 2 niveles en los mismos 4 puntos de validación —
   (1) shape regex inválido, o rango inválido una vez resuelto
   (`dias_desde < 0`, o `dias_desde > dias_hasta` con `dias_hasta` no NULL, ver
   `bce_plazo_matching.py::validar_rango_plazo()`) sigue lanzando
   `PlazoNoResueltoError` y abortando la carga; (2) shape válido + rango sano pero fuera
   del universo enumerado ya NO lanza — se acepta y llega a `marts.dim_plazo`
   `AUTO_INGRESADO` (columna nueva, `sql/27`) para revisión posterior, sin abortar el
   resto de la carga. `dim_plazo` es el único de los 5 catálogos "cerrados" de este
   proyecto que recibe este tratamiento — `dim_segmento_credito`/
   `dim_subsegmento_credito`/`dim_categoria_deposito`/`dim_segmento_entidad` mantienen el
   fail-fast absoluto sin two-tier, por la distinción sintaxis-vs-semántica-regulatoria
   documentada en `docs/data_dictionary.md` (sección `dim_plazo`) y en el propio
   comentario de `sql/27`: un rango numérico de días es autoexplicativo una vez que el
   shape matcheó, un nombre nuevo de segmento/categoría regulatoria no lo es. Verificado:
   los 4 universos previamente cerrados siguen coincidiendo exactamente con `staging.*`
   completo tras el cambio (mismo alcance que la verificación de 2026-08-27), y una
   corrida repetida del `INSERT ... ON CONFLICT DO NOTHING` de `dim_plazo` produce las
   mismas 21 filas `CONFIRMADO` / 0 `AUTO_INGRESADO` en ambas pasadas — no genera ningún
   cambio real (no hay `UPDATE` en este patrón, es puramente aditivo). Se ejerció el
   camino de auto-ingesta con un bucket sintético shape-válido-pero-nunca-visto
   (`"h. 1000 - 1100 DIAS"` para tsp) insertado y confirmado con
   `estado_validacion='AUTO_INGRESADO'` contra la base viva, y luego eliminado (no forma
   parte de los datos reales) — y con un bucket sintético shape-inválido confirmando que
   sigue lanzando `PlazoNoResueltoError`. Cubierto por tests nuevos en
   `tests/test_bce_plazo_matching.py`, `tests/test_categoria_deposito_matching.py`,
   `tests/test_parse_tasas_historicas.py`.
2. **Universo cerrado y validado en BCE**: `SEGMENTOS_VALIDOS` (26), `CATEGORIAS_VALIDAS`
   (11), `PLAZOS_TSP_VALIDOS` (7) y `PLAZOS_TSA_VALIDOS` (14) se validan explícitamente
   contra el valor real de cada fila de tsp/tsa antes de escribir a `staging.*` — un
   valor fuera del universo sembrado detiene la carga (`ValueError`/
   `SegmentoNoResueltoError`/`PlazoNoResueltoError`), no se descarta silenciosamente.
3. **Índices únicos NULL-safe**: todo `UNIQUE`/`ON CONFLICT` sobre una columna nullable
   (`plazo_dias_hasta`, `plazo_id`, `provincia`, `staging.cartera.canton`,
   `staging.depositos.canton`) usa `COALESCE(col, sentinela)` — bug real encontrado y
   corregido en `sql/10_fix_null_unique_constraints.sql` (Postgres trata `NULL <> NULL`
   incluso bajo `UNIQUE`, lo que duplicaba filas silenciosamente).
   `staging.cartera.canton`/`staging.depositos.canton` tenían la misma forma de bug
   (`UNIQUE` plano, sin `COALESCE`) pero estaban latentes, no activos — verificado 0 filas
   con `canton IS NULL` de 369.966 en `staging.cartera` y 0 de 251.247 en
   `staging.depositos` antes de aplicar cada fix respectivamente, así que ninguno de los
   dos hizo falta backfill/dedupe, a diferencia de `dim_plazo`/`fact_depositos` en su
   momento. Corregidos en `sql/23_fix_staging_cartera_canton_null_safe.sql` (cartera) y
   `sql/24_fix_staging_depositos_canton_null_safe.sql` (depositos, mismo día).
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
   descargados — se salta si no están) + archivos de tests puros sobre funciones de
   matching/normalización/parsing que no requieren archivos externos
   (`test_banco_matching.py`, `test_categoria_deposito_matching.py`,
   `test_bce_plazo_matching.py`, `test_parse_boletin.py`, `test_parse_tasas_historicas.py`,
   `test_common.py`, `test_pipeline_fecha_parsing.py`) + `test_integration_regressions.py`
   (usa `db_conn`, fixture en `tests/conftest.py` — requiere Postgres vivo, se salta si no
   hay conexión), incluyendo un test de regresión
   (`test_parse_filas_rastrea_seccion_sin_asumir_que_tabla_0_es_activa_maxima`) que fija
   explícitamente el bug real de inestabilidad de tabla en `TasasHistorico.htm`.
   **Conteo puntual, no un número fijo a mantener a mano** (mismo criterio que la tabla de
   volúmenes de `marts` arriba: se degrada apenas se agrega un test) — **69 tests** medido
   2026-08-30 (incluye `test_staging_cartera_canton_null_safe_unique_regression`, agregado
   junto con `sql/23_fix_staging_cartera_canton_null_safe.sql`,
   `test_staging_depositos_canton_null_safe_unique_regression`, agregado junto con
   `sql/24_fix_staging_depositos_canton_null_safe.sql`, y 5 tests nuevos de
   `validar_ruc_estructura()`/`resolver_entidad_bce()` agregados junto con la validación
   estructural de RUC, ver #8 abajo) con `grep -rc "^def test_" tests/*.py` (o
   `pytest --collect-only -q`); ese comando, no este número, es la fuente de verdad si
   hace falta un valor vigente.
8. **Validación estructural real de RUC para entidades BCE no-privadas** (2026-08-30,
   `etl/transform/banco_matching.py::validar_ruc_estructura`): antes, cualquier texto que
   BCE reportara como RUC se aceptaba tal cual como llave (`banco_codigo = "BCE_" + ruc`)
   sin verificar que tuviera la forma de un RUC real. Ahora se valida longitud (13
   dígitos), código de provincia (01-24), tercer dígito (9 = sociedad privada/extranjera,
   6 = sector público — los 2 únicos tipos presentes hoy en las 409 entidades no-privadas
   vigentes) y dígito verificador módulo 11 (algoritmo estándar del SRI para sociedades).
   Un RUC que no pasa la validación lanza `RucInvalidoError` (distinto de
   `EntidadBceNoMapeadaError`, que es sobre `tipo_entidad`) y bloquea la carga de esa fila
   en vez de auto-registrar una llave malformada. **Verificado contra las 409 entidades
   reales vigentes en `marts.dim_banco` antes de dar por buena la implementación**
   (2026-08-30): 403 con tercer dígito 9, 6 con tercer dígito 6, **0 rechazos** — el
   algoritmo no invalida ningún RUC ya confiado en producción. También verificado contra
   los 33 RUC de bancos privados curados (no pasan por esta validación en producción,
   pero se corrieron igual como control): igualmente 0 rechazos. La excepción "código de
   provincia 30 = extranjero/otro", mencionada en algunas fuentes no oficiales sobre el
   algoritmo de RUC ecuatoriano, se dejó **deliberadamente fuera** por no poder
   confirmarse contra ninguna fuente autoritativa (SRI) ni ser necesaria para ningún RUC
   real ya cargado (los 409 caen todos en 01-24). Cubierto por 5 tests nuevos en
   `tests/test_banco_matching.py` (RUC real válido, longitud incorrecta, dígito
   verificador incorrecto, `resolver_entidad_bce` con RUC inválido en el camino
   no-privado, y confirmación de que el camino BANCOS PRIVADOS no queda afectado por esta
   validación).

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
| Identidad auto-registrada por RUC (~420 entidades no-privadas) no está curada | A diferencia de los bancos privados, estas ~420 entidades no pasaron por revisión humana — el nombre/tipo_entidad viene tal cual del BCE. Decisión deliberada, no un descuido: a esta escala curar 420 nombres a mano es inviable y no hay hoy ninguna otra fuente (CAPCOL/Boletín) con la que reconciliar estas entidades, así que la curación no aportaría valor todavía. **Condición de salida explícita** (no es un "más adelante" abierto): la curación deja de ser diferible el día que ocurra CUALQUIERA de (1) el proyecto agrega una fuente específica de cooperativas/mutualistas/sociedades financieras (dato con el que sí se podría reconciliar el crosswalk de las ~420), o (2) aparece una colisión de RUC *entre* dos entidades del set auto-registrado (distinto de la colisión ya conocida y documentada entre banco-privado-curado y entidad-auto-registrada, ver fila `vw_banco_ruc_colisiones` abajo) — ese caso significaría que el RUC, la única llave que sostiene hoy el auto-registro sin curación, dejó de ser confiable como identificador único para ese subconjunto. Ninguna de las 2 condiciones se ha cumplido a la fecha de esta nota (2026-08-27). | `etl/transform/banco_matching.py::resolver_entidad_bce` |
| **7 pares de `dim_banco.banco_codigo` distintos comparten el mismo `ruc`** — confirmado 2026-07-23, no un riesgo teórico; **discoverability resuelta 2026-08-22**; **contexto histórico del par `JARAMILLO_ARTEAGA`/`PROMERICA` añadido 2026-08-29** | Al activar `ruc` (ver fila de arriba) se pudo verificar por primera vez con datos reales, no solo sospechar: `DINERS CLUB`/`BP DINERS`, `BANCO AMIBANK S.A.`/`FINCA`/`BP FINCA S.A.` (3 vías, mismo RUC), `COOPERATIVA...DESARROLLO DE LOS PUEBLOS`/`BP...CODESARROLLO`, `BANCO ATLÁNTIDA S.A.`/`BP D-MIRO S.A.`, `VISIONFUND`/`BP VISIONFUND ECUADOR S.A.`, `M.M. JARAMILLO ARTEAGA`/`PROMERICA`, `COOPERATIVA...NACIONAL`/`BP COOPNACIONAL`. El patrón dominante **no es un error del BCE**, es una entidad que cambió de forma legal (cooperativa/financiera → banco privado licenciado) mientras BCE seguía usando el mismo RUC — `resolver_entidad_bce()` la resuelve por separado en cada lado porque enruta por `tipo_entidad_bce`, así que quedan como 2 filas distintas de `dim_banco` para el mismo contribuyente. **No se fusionó y sigue sin fusionarse**: a diferencia del bug de Manabí/Amibank (mismo nombre, mismo tipo, typo de la fuente), acá el cambio de tipo de entidad es real y fusionar podría ocultar esa transición en vez de modelarla — es una decisión de negocio, no una limpieza mecánica, y esta fila documenta esa decisión, no un pendiente. Lo que sí era un hueco real: la única forma de descubrir la colisión era haber leído esta fila — la query de verificación no estaba persistida en ningún objeto consultable. **Resuelto 2026-08-22**: `marts.vw_banco_ruc_colisiones` (`sql/22_vw_banco_ruc_colisiones.sql`) surface los 7 pares/15 filas directo desde SQL — cualquier análisis longitudinal por banco (o modelo predictivo) que agrupe por `banco_codigo` debe cruzar contra esa vista si el banco de interés aparece en ella.<br><br>**Por qué el par `JARAMILLO_ARTEAGA`/`PROMERICA` cambió de nombre** (investigado 2026-08-29, hecho externo/histórico, no verificable contra la base — se cita como investigado en la web, no como dato verificado en Postgres): Banco M.M. Jaramillo Arteaga era un banco mediano ecuatoriano que pasó a ser propiedad de Promerica Financial Corporation (Grupo Promerica, grupo bancario centroamericano) y se renombró a Banco Promerica Ecuador. En marzo de 2014 Grupo Promerica adquirió ~56% de Produbanco; en octubre de 2014 Banco Promerica Ecuador se fusionó con Produbanco y la entidad combinada mantuvo la marca Produbanco (fuentes: produbanco.com.ec/produbanco-grupo-promerica, revistalideres.ec — "Ricardo Cuesta: 'Se comprará alrededor del 55% de Produbanco'"). Esto **explica** la colisión de RUC ya documentada arriba, no agrega una nueva: es el mismo RUC (`1790477142001`) usado antes y después del rename de razón social. **Verificado contra `staging.*` en esta sesión** (2026-08-29), y la cronología de fechas en BCE coincide exactamente con la historia investigada: `staging.bce_tasas_pasivas`/`bce_tasas_activas` para `banco_codigo='JARAMILLO_ARTEAGA'` cubren 2008-01-03 a 2009-02-26; para `banco_codigo='PROMERICA'` cubren 2009-02-26 a 2014-10-09 (arranca exactamente donde termina Jaramillo Arteaga, termina exactamente en la fecha de la fusión con Produbanco); no hay filas de `PROMERICA` en `staging.cartera`/`staging.depositos`/`staging.boletin_balance`/`staging.boletin_pyg` en ninguna fecha. | `sql/22_vw_banco_ruc_colisiones.sql`, `docs/data_dictionary.md` |
| **`PRODUBANCO` y `PROMERICA` NO son una colisión de RUC — son entidades legales distintas del mismo grupo corporativo, categoría de relación que `vw_banco_ruc_colisiones` no cubre y no puede cubrir** (añadido 2026-08-29) | Verificado 2026-08-29 contra `marts.dim_banco`: `PRODUBANCO` tiene `ruc = '1790368718001'`, `PROMERICA` tiene `ruc = '1790477142001'` — dos RUCs distintos, dos filas de `dim_banco` legítimamente independientes, ninguna aparece junto a la otra en `vw_banco_ruc_colisiones` (que solo agrupa por `ruc` compartido). Su relación es corporativa, no de identidad de contribuyente: desde la fusión de octubre de 2014 (ver fila de arriba), Produbanco es la marca bajo la que opera el negocio combinado del Grupo Promerica en Ecuador, mientras `PROMERICA` en `dim_banco` es el remanente histórico del RUC de Banco Promerica Ecuador/M.M. Jaramillo Arteaga tal como lo reportó BCE **antes** de la fusión. Verificado por fuente en `staging.*`: `PRODUBANCO` tiene filas en las 4 fuentes (`cartera` 27.207, `depositos` 16.087, `bce_tasas_pasivas` 27.492 [2008–2026], `bce_tasas_activas` 91.154 [2008–2026], `boletin_balance` 91.726, `boletin_pyg` 8.096); `PROMERICA` tiene filas **solo** en `bce_tasas_pasivas`/`bce_tasas_activas` (2.204 y 7.267 filas, ambas 2009-02-26 a 2014-10-09) y **cero** en `cartera`/`depositos`/`boletin_balance`/`boletin_pyg`. No es un hueco de carga: CAPCOL y Boletín están acotados a 2021 en adelante por alcance del proyecto (ver filas "`TasasHistorico.htm` solo 2022-04..."/"Boletín solo 2021-01..." abajo), muy posterior a la fusión de 2014 — para esas 2 fuentes, `PROMERICA` como entidad separada ya no existía cuando arranca la ventana cargada, por eso nunca puede tener filas ahí. BCE sí alcanza el histórico completo desde 2008, así que es la única fuente donde `PROMERICA` aparece como línea propia. **Gotcha analítico real para quien use este modelo**: cualquier análisis de participación de mercado o serie longitudinal por banco que trate `PRODUBANCO` y `PROMERICA` como 2 competidores independientes en `fact_captaciones_depositos`/`fact_colocaciones_cartera` (las únicas 2 tablas donde ambos códigos tienen filas) está malinterpretando la estructura corporativa real — no son comparables como pares, son el mismo grupo en 2 ventanas temporales distintas con 2 identidades BCE distintas. `vw_banco_ruc_colisiones` no los va a marcar porque no comparten RUC, y no debería fusionarse mecánicamente (mismo criterio de la fila de arriba: colapsar ocultaría la transición real en vez de modelarla) — pero cualquiera haciendo ese tipo de análisis necesita saberlo antes de agrupar por `banco_codigo` sin revisar el grupo corporativo. | Esta sesión (2026-08-29), `marts.dim_banco`, `staging.cartera`/`depositos`/`bce_tasas_pasivas`/`bce_tasas_activas`/`boletin_balance`/`boletin_pyg` |
| `dim_banco` creció de ~33 a 442 filas de golpe | Efecto esperado del fix de arriba, no un bug — pero cualquier cálculo/reporte que asumía "todo `dim_banco` es banco privado" (ej. si el `.pbip` de Power BI algún día vuelve a usarse sin filtrar `tipo_entidad`) necesita revisarse | Este documento |
| ~~Power BI (`.pbip`) con nombres/columnas viejos~~ — **realineado 2026-07-23, actualizado de nuevo 2026-07-25 (dos veces)** | Se actualizaron las 8 tablas ya modeladas (`fact_saldo_cartera`/`fact_saldo_depositos`, `dim_segmento_credito`, `dim_categoria_deposito` + `dim_plazo` nueva) para que coincidan con el esquema vivo — medidas DAX, relaciones y visuals del reporte incluidos. 2026-07-25: la normalización de `dim_canton.provincia`→`dim_provincia` (ver fila "Normalización de provincia" arriba) rompía 2 visuales del reporte (`page-geografico`, barras por provincia) que sí usaban ese campo directo — agregada `dim_provincia.tmdl` (9na tabla), relación `dim_canton→dim_provincia`, y los 2 `visual.json` actualizados a `Entity: "dim_provincia"`. Mismo día, el pivote de `estado_cartera` (ver fila "Pivote de estado_cartera" abajo) rompía 3 medidas DAX que filtraban `fact_saldo_cartera[estado_cartera]` — corregidas a `SUM()` directo sobre las nuevas columnas; ningún visual necesitó cambios (todos usan medidas, no columnas crudas — confirmado con grep antes de asumirlo). **Sigue sin cubrir BCE/Boletín** (11 tablas más) ni el universo completo de `dim_banco` (el modelo solo trae bancos privados, coherente con su alcance actual) — eso es una expansión aparte, no un arreglo. | `README.md` |
| **Pivote de `estado_cartera`** — antipatrón EAV corregido, no un bug de datos | `fact_saldo_cartera` tenía `estado_cartera` como dimensión degenerada (3 filas por `(fecha, banco, cantón, segmento)`, una por estado) cuando en realidad son 3 medidas mutuamente excluyentes del mismo hecho — el usuario lo identificó explícitamente al revisar el modelo. Mismo criterio que ya usaba `fact_tasas_referenciales_cartera` (columnas de medida, no "tipo"+"valor"). Pivotado a `saldo_por_vencer`/`saldo_no_devenga_intereses`/`saldo_vencida` + `saldo_total` (columna `GENERATED`, suma de las 3) — grano pasó de 369.966 a 123.322 filas (÷3 exacto, sin combinaciones parciales). `vw_cartera_market_share`/`vw_cartera_hhi` (`sql/15`) dependían de la columna `saldo` vieja — recreadas sobre `saldo_total` en la misma migración. Verificado: `SUM(saldo_total)` pre/post migración idéntico, `refresh_marts()` idempotente. | `sql/21_fact_saldo_cartera_pivot.sql`, `docs/data_dictionary.md` |
| ~~`staging.depositos` tenía el mismo bug de `UNIQUE` sin `COALESCE` sobre `canton` que `staging.cartera` tenía~~ — **resuelto 2026-08-27** | `sql/23_fix_staging_cartera_canton_null_safe.sql` había corregido únicamente `staging.cartera` (alcance puntual del cambio que lo originó), dejando `staging.depositos` con el mismo bug class de `sql/10`/`sql/23` (`UNIQUE` plano sobre `canton`, `NULL <> NULL` incluso bajo `UNIQUE`) pendiente. Cerrado en `sql/24_fix_staging_depositos_canton_null_safe.sql`: verificado de nuevo contra la base viva (0 filas con `canton IS NULL` de 251.247, así que tampoco hizo falta backfill/dedupe), `UNIQUE` plano reemplazado por índice de expresión `staging_depositos_natural_key_unique (fecha, tipo_entidad, banco, COALESCE(canton, ''), tipo_deposito)`, y `upsert_staging_depositos()` (`etl/load/load_postgres.py`) actualizado al mismo `ON CONFLICT (..., COALESCE(canton, ''), ...)`. CDC no-op reverificado con doble carga idéntica (segunda corrida no cambia `fecha_actualizacion`). | `sql/24_fix_staging_depositos_canton_null_safe.sql`, `etl/load/load_postgres.py::upsert_staging_depositos`, `tests/test_integration_regressions.py::test_staging_depositos_canton_null_safe_unique_regression` |
| **`marts.dim_canton` descartaba silenciosamente filas de `staging.cartera`/`staging.depositos` cuya `provincia` no resolvía contra `dim_provincia`** — encontrado y mitigado 2026-08-30 | El `INSERT INTO marts.dim_canton` de `refresh_marts()` usa un `INNER JOIN` contra `marts.dim_provincia` (`provincia_id` es `NOT NULL` en `dim_canton`, así que no puede ser `LEFT JOIN` con `NULL`) — cualquier fila cuya `provincia` no matcheara ahí (ni exacto ni vía `translate()`) se descartaba sin error, sin fila huérfana, sin rastro; nadie lo habría notado sin ir a comparar conteos a mano. **Verificado contra la base viva antes de concluir si era un riesgo teórico o un bug activo**: 0 filas de `staging.cartera`/`staging.depositos` caen hoy en este caso (los 132 pares `(canton, provincia_id)` de `staging` y de `marts.dim_canton` coinciden exactamente). **No se agregó una tabla `staging.catalogo_rechazos`** para este caso — a diferencia de `dim_plazo`/`banco_codigo` (catálogos regulatorios cerrados donde un valor no resuelto es un dato mal identificado que alguien podría contar como otra entidad distinta), `dim_canton` es geografía de bajo riesgo, y con 0 filas afectadas hoy esa infraestructura sería sobre-ingeniería. Se agregó en cambio `etl/load/load_postgres.py::_log_cantones_no_resueltos()`, que corre al inicio de cada `refresh_marts()` y loguea WARNING con el detalle (provincia, filas, cantones distintos afectados) si esto llega a ocurrir, INFO "0 filas" si no — visible en cualquier corrida normal del pipeline en vez de requerir ir a buscarlo. Si esta función alguna vez emite un WARNING real, ESE es el momento de reevaluar si hace falta algo más que un log. | `etl/load/load_postgres.py::_log_cantones_no_resueltos`, `docs/linaje_datos.md`, `docs/data_dictionary.md` |
| **Bug de CDC real en `marts.dim_banco`: `fecha_actualizacion` se pisaba en cada `refresh_marts()` sin cambio real** — preexistía desde `sql/19_dim_segmento_entidad.sql` (2026-07-25), encontrado y corregido 2026-08-30 | El `INSERT INTO marts.dim_banco ... ON CONFLICT` no listaba `segmento_entidad_id` entre sus columnas — Postgres computa `EXCLUDED.segmento_entidad_id` como el valor por defecto de una columna omitida del `INSERT` (`NULL`), no como el valor real de la fila en conflicto. Como `row_hash` (columna `GENERATED`) incluye `segmento_entidad_id`, `EXCLUDED.row_hash` casi nunca coincidía con el `row_hash` real de un banco con `segmento_entidad_id` ya poblado (prácticamente los 442) — el guard `WHERE row_hash IS DISTINCT FROM EXCLUDED.row_hash` disparaba un `UPDATE` real en **cada** corrida, no solo cuando algo cambiaba de verdad. Quedó expuesto al verificar CDC no-op de punta a punta para esta migración (`estado_validacion`) en vez de asumirlo — la migración en sí no lo introdujo, pero tampoco se habría descubierto sin esa verificación explícita. Corregido con un `LEFT JOIN` a la propia `marts.dim_banco` en el `INSERT` para que `segmento_entidad_id` (y por lo tanto `EXCLUDED.row_hash`) refleje el valor real actual — esa columna sigue sin escribirse en el `SET` del `ON CONFLICT`, la sigue manteniendo el `UPDATE` SCD1 separado. Verificado: 0 filas con `fecha_actualizacion` cambiada en una corrida de `refresh_marts()` sin datos nuevos (antes del fix: 442/442 cambiaban en cada corrida). | `etl/load/load_postgres.py` (INSERT de `dim_banco` en `_REFRESH_MARTS_SQL`), `docs/data_dictionary.md`, `docs/architecture.md` |
| **4 bancos con desviación de 2-6% entre CAPCOL cartera y BALANCE cartera bruta en ventanas de fecha acotadas** — encontrado 2026-08-30, no investigado a fondo | La reconciliación cruzada `SUM(fact_saldo_cartera.saldo_total)` (banco × fecha) vs. `vw_cartera_bruta` (`14 − 1499`, ver `docs/glosario_cuentas.md` §2 y `docs/metricas_financieras.md`) reconcilia con mediana ~0% y 96,92% de las 1.559 combinaciones banco × fecha dentro de ±2% — pero **AMIBANK** (2023-05-31 a 2023-12-31, 8 de 22 meses de overlap, −4,92% a −5,92%), **ATLANTIDA** (2025-06-30 a 2026-05-31, 12 de 13 meses — casi toda su ventana de overlap, −2,00% a −4,87%), **PACIFICO** (2022-09-30 a 2024-10-31, 26 de 66 meses, −2,01% a −3,45%) y **FINCA** (2022-11-30 a 2022-12-31, 2 de 24 meses, −2,47% a −2,77%) se salen de esa tolerancia en esas ventanas específicas, siempre con CAPCOL por debajo de BALANCE. No se investigó la causa raíz esta sesión (hipótesis sin verificar: reclasificación de cartera fuera de las categorías de cantón/segmento de CAPCOL, timing de corte entre fuentes, o un problema de carga puntual para esos bancos/meses) — queda marcado para una pasada futura. | `docs/metricas_financieras.md` (tabla completa de la reconciliación), `docs/glosario_cuentas.md` §2 |
| **CAPCOL depósitos no cubre 5 sub-cuentas nivel-6 del plan de cuentas regulatorio bajo `21` (BALANCE) — hueco de alcance real, no un bug** | `SUM(fact_saldo_depositos.saldo)` (banco × fecha) queda sistemáticamente **por debajo** de `codigo='21'` de BALANCE (mediana de la diferencia % por banco × fecha: −0,7376%; CAPCOL por debajo en 1.509/1.556 = 96,98% de las combinaciones; gap agregado sobre la suma total del histórico: −1,12%, `−$35.014.233.134,70` sobre `$3.127.015.362.802,94`). Causa estructural verificada: `marts.dim_categoria_deposito` (12 valores curados, `etl/transform/categoria_deposito_matching.py::CATEGORIAS_VALIDAS`) no tiene equivalente para 5 sub-cuentas nivel-6 de `21` que sí existen en el Catálogo Único — `210120` EJECUCIÓN PRESUPUESTARIA, `210125` DEPÓSITOS DE OTRAS INSTITUCIONES PARA ENCAJE (ambas institucionales/nicho), `210130` CHEQUES CERTIFICADOS, `210131` CHEQUES DE EMERGENCIA y `210140` OTROS DEPÓSITOS. `SUM(saldo_usd)` de esas 5 cuentas sobre el mismo conjunto banco × fecha con overlap explica el **47,81%** del gap agregado total (`$16.740.024.139,94` de `$35.014.233.134,70`) — el 52,19% restante no se explica por cuentas estructuralmente ausentes del catálogo CAPCOL; es probablemente hueco de reporte intermitente banco-mes dentro de categorías que CAPCOL sí tiene, no investigado más a fondo esta sesión. **No es un bug a corregir**: es una limitación real y permanente de la taxonomía de producto de CAPCOL frente al plan de cuentas regulatorio completo — CAPCOL nunca reportó esas 5 sub-cuentas como categoría propia, no es un valor que dejó de resolver. | `etl/transform/categoria_deposito_matching.py`, `docs/data_dictionary.md` (`dim_categoria_deposito`/`fact_saldo_depositos`), `docs/glosario_cuentas.md` §3 |
| **`sql/18_glosario_cuentas_views.sql` (vistas `vw_cartera_bruta`/`vw_cartera_improductiva`/etc.) no está aplicado en la base de producción viva** — encontrado 2026-08-30 al intentar usar `marts.vw_cartera_bruta` para la reconciliación de arriba | `to_regclass`/`information_schema.views` confirma que ninguna de las vistas de `sql/18` existe en `marts` en la instancia nativa viva, pese a que migraciones **posteriores** (`sql/22`, `25`, `26`, `27`) sí están aplicadas (`dim_cuenta_contable.estado_validacion`, `dim_banco.estado_validacion`, `dim_plazo.estado_validacion`, `vw_banco_ruc_colisiones` existen y funcionan) — es decir, `sql/18` se saltó específicamente, no es que las migraciones se detuvieran en algún punto. Consistente con el propio comentario de cabecera de `sql/18` ("NO ejecutado todavía contra una instancia Postgres real (solo probado el equivalente en pandas)"), escrito cuando se creó el archivo — parece que nunca se corrió después tampoco. La reconciliación de esta sesión se hizo con la lógica de la vista expandida inline (ver consulta en `docs/metricas_financieras.md`) precisamente por esto. **No se aplicó la migración en esta sesión** (alcance explícito: solo documentación) — si alguien retoma el proyecto y `marts.vw_cartera_bruta` (u otra vista de `sql/18`) falla con "relation does not exist", esta es la causa; aplicar `sql/18_glosario_cuentas_views.sql` (es `CREATE OR REPLACE VIEW`, no destructivo) es la resolución directa. | `sql/18_glosario_cuentas_views.sql`, `docs/metricas_financieras.md` |

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

Para el procedimiento paso a paso de qué hacer cuando falla un test de matching, un valor
crudo no resuelve (`*NoResueltoError`) o aparece una fila `AUTO_INGRESADO` para revisar —
qué archivo tocar, qué test agregar, qué query correr — ver
`docs/mantenimiento_catalogos.md`. Ese documento es el runbook operativo; este documento
(`gobernanza_datos.md`) sigue siendo la referencia de *por qué* cada regla existe.
