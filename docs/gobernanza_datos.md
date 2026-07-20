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
| `staging.tasas_referenciales` | `(fecha, seccion, COALESCE(dimension_valor,''), COALESCE(plazo_dias_desde,-1), COALESCE(plazo_dias_hasta,-1), metrica)` | `dimension_valor` armonizado a los nombres ya sembrados en `dim_segmento_credito`/`dim_categoria_deposito` (alias explícitos, ver `linaje_datos.md`) | Sí |
| `staging.boletin_balance` / `boletin_pyg` | `(fecha, banco_codigo, codigo)` | `banco_codigo` vía `banco_matching.py` (fuente `"BOLETIN"`) | Sí |
| `staging.banco_maestro` | `banco_codigo` (PK) | Dos mecanismos: (1) sembrada desde `etl/seeds/banco_maestro.csv` para los ~33 bancos privados curados (`load_banco_maestro_seed`); (2) **auto-registrada por RUC** para las ~420 entidades no-privadas de BCE (`upsert_banco_maestro_auto`, `ON CONFLICT DO NOTHING`) — ver "Identidad para el universo completo del sistema financiero" abajo | No (se resiembra/complementa en cada corrida, `ON CONFLICT DO NOTHING`/`DO UPDATE` sin CDC propio) |

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
| `dim_segmento_credito` | Catálogo (universo BCE, no filtrado por entidad) | — | sembrado una vez (`sql/08`) | 26 filas |
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
| `dim_banco.tamano` / `dim_banco.ruc` nunca se pueblan | Las columnas existen en el esquema (`sql/07`) pero `refresh_marts()` solo inserta `(banco_codigo, banco, tipo_entidad)` — `etl/seeds/banco_maestro.csv` no trae esas 2 columnas. Quedan `NULL` siempre. Confirmado leyendo el código en esta sesión, no documentado antes. | Este documento (nuevo hallazgo) |
| ~~`fact_cartera.tasa_ponderada` / `.morosidad` / `.saldo_x_tasa` nunca se pueblan~~ — **resuelto 2026-07-19** | Estaban reservadas desde v1, nunca escritas por `refresh_marts()`. Eliminadas junto con el renombrado de tablas (`sql/15_rename_fact_tables.sql`) — la tasa real ya vive en `fact_colocaciones_cartera`/`fact_captaciones_depositos` | `docs/linaje_datos.md`, `docs/data_dictionary.md`, sección "Renombrado de tablas de hechos" arriba |
| `dim_producto_cartera` / `dim_producto_deposito` siguen existiendo en Postgres, huérfanas | Las migraciones (`sql/08`, `sql/09`) dejaron de referenciarlas pero **nunca ejecutaron un `DROP TABLE`** — siguen físicamente en la base sin ningún `fact_*` apuntándoles. El modelo lógico vivo (este catálogo, el diagrama ER) no las incluye porque no son parte del esquema en uso. | Detectado en la sesión que generó el diagrama ER; falta un `DROP TABLE` explícito si se quiere una base limpia |
| `TasasHistorico.htm` solo 2022-04 a 2026-06 | Páginas anteriores (2008–2022) usan un layout HTML distinto no soportado por el parser | `docs/fuentes_datos.md`, `docs/linaje_datos.md` |
| Boletín solo 2021-01 en adelante | No se intentó cargar años anteriores — decisión explícita de alcance | `docs/fuentes_datos.md` |
| `dim_cuenta_contable.grupo_met` no es partición limpia | Un mismo código de cuenta puede caer en 2+ grupos funcionales de la hoja `MET`; se guarda solo el primero encontrado | `docs/metricas_financieras.md` |
| ~~BCE tsp/tsa: `raw.*` no incluía el universo completo de entidades~~ — **resuelto 2026-07-19** | Estaba filtrado a bancos privados antes de persistir; corregido, `raw.*` ahora captura las 6 categorías completas y `staging`/`marts` resuelven identidad para todas (curada para privados, auto-registrada por RUC para el resto) | `docs/linaje_datos.md`, sección "Identidad para el universo completo del sistema financiero" arriba |
| Identidad auto-registrada por RUC (~420 entidades no-privadas) no está curada | A diferencia de los bancos privados, estas ~420 entidades no pasaron por revisión humana — el nombre/tipo_entidad viene tal cual del BCE. Riesgo real (bajo pero no cero): si el BCE reutiliza un RUC entre 2 entidades distintas por error de origen (se observaron un par de casos de RUC compartido entre nombres de bancos privados en el archivo real), se fusionarían en un solo `banco_codigo` — aceptable para este nivel de curación, pero no verificado exhaustivamente | `docs/gobernanza_datos.md` (esta fila), `etl/transform/banco_matching.py::resolver_entidad_bce` |
| `dim_banco` creció de ~33 a 442 filas de golpe | Efecto esperado del fix de arriba, no un bug — pero cualquier cálculo/reporte que asumía "todo `dim_banco` es banco privado" (ej. si el `.pbip` de Power BI algún día vuelve a usarse sin filtrar `tipo_entidad`) necesita revisarse | Este documento |
| Power BI (`.pbip`) desactualizado | Solo modela el esquema original de CAPCOL (7 tablas); las tablas de BCE/Boletín añadidas después no están en el modelo semántico, y tampoco contempla el universo completo de `dim_banco` (asumía solo bancos privados) | `README.md`, memoria de sesión |

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
