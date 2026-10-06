# Linaje de datos

Traza, campo por campo, el recorrido `archivo fuente → staging.* → marts.*` para cada
una de las 5 fuentes (CAPCOL incl. Banca Pública, BCE tsp/tsa, `TasasHistorico.htm`,
Boletín y SEPS; la SEPS está en la sección 7). Las tablas por fuente conservan una columna
"raw" que hoy describe la salida del parser: desde `sql/33` no hay capa `raw` en la base. Es el complemento de `docs/data_dictionary.md` (qué significa
cada campo) y `docs/architecture.md` (cómo se relacionan las tablas): este documento
responde **de dónde viene** cada campo y **qué transformación** sufrió en el camino.
Grounded directamente en el código (parsers de `src/benchmark_bancos/transform/`, `src/benchmark_bancos/load/load_postgres.py`)
al momento de escribirse — no en la ficha metodológica de la fuente, que en varios casos
está desactualizada (ver `docs/fuentes_datos.md`).

> **2026-10-05 (`sql/33`)**: la capa `raw.*` (JSONB) se eliminó de la base. Las columnas
> "raw" de las tablas de abajo describen la salida del parser, que hoy va directo a
> `staging.*`. La trazabilidad al origen es el archivo en `data/raw/**` más su sha256 en
> `meta.source_files`. La sección siguiente se conserva como registro de por qué raw no
> aportaba un espejo del origen.

## Principio: `raw.*` no es un espejo bit-a-bit del archivo origen

Antes de leer las tablas de abajo, una aclaración importante para no asumir más de lo que
`raw.*` realmente garantiza. En un modelo de gobernanza estricto, la capa "raw" preserva
cada fila del archivo origen sin ninguna transformación. **Acá no es así, por diseño**:

- **CAPCOL (cartera/depósitos)**: el archivo trae detalle a nivel de oficina/cuenta
  contable — varias filas comparten la misma llave natural (fecha, banco, cantón,
  tipo_credito/tipo_deposito, estado). El parser (`src/benchmark_bancos/transform/parse_cartera.py`,
  `parse_depositos.py`) las **suma por `groupby` antes de devolver el DataFrame**, y ese
  mismo DataFrame ya agregado es lo que llega tanto a `raw.cartera`/`raw.depositos` como a
  `staging.*`. `raw.*` nunca tiene el detalle de oficina.
- **BCE tsp/tsa**: **corregido 2026-07-19** — una versión anterior filtraba a
  `tipo_entidad == 'BANCOS PRIVADOS'` chunk por chunk antes de que el dato llegara a
  `raw.*`, perdiendo para siempre ~85% de las filas (el archivo cubre las 6 categorías
  del sistema financiero completo: bancos privados, públicos, 394-402 cooperativas de
  ahorro y crédito, mutualistas, sociedad financiera, tarjetas de crédito). El usuario lo
  detectó y pidió explícitamente que se preservara todo, sin filtro, para poder analizar
  el sistema financiero completo más adelante sin tener que re-descargar. Corregido:
  `read_raw()` (`src/benchmark_bancos/transform/parse_bce_tasas.py`) captura las 6 categorías tal cual,
  sin filtrar ni agregar — eso es lo único que alimenta `raw.bce_tasas_pasivas`/
  `raw.bce_tasas_activas`. Ver la sección 3 más abajo para el detalle completo del fix.
- **Boletín**: `raw.boletin_balance`/`raw.boletin_pyg` guardan la fila ya pivotada a
  formato largo (banco, código, valor) y con `banco_codigo`/`saldo_usd` ya resueltos —no
  la celda cruda del Excel ancho.

En los 4 casos, la trazabilidad al archivo original **no se pierde** — se mantiene por
`source_file` + `source_hash` (columna en cada fila de `raw.*`, más `raw.source_files`
para idempotencia a nivel de archivo) y por el archivo mismo, conservado en
`data/raw/**` en disco (no versionado en git, pero reproducible: cada fuente es
re-descargable y el pipeline es idempotente por hash). Lo que `raw.*` garantiza es
"estructura sin tipar, previa a resolver catálogos conformados (banco/categoría/plazo)" —
no "byte idéntico al archivo". Quien necesite el detalle de oficina de CAPCOL o el
universo completo de entidades de BCE debe volver al archivo fuente, no a `raw.*`.

---

## 1. CAPCOL — Cartera

Fuente: hoja Excel `BASE ...` (una por `tipo_credito`, dentro de un ZIP por segmento/año).
`tipo_credito` se deriva del **nombre de la hoja**, no de una columna ni del nombre del
archivo (`src/benchmark_bancos/transform/parse_cartera.py::tipo_credito_from_sheet_name`, vía
`TIPO_CREDITO_KEYWORDS` en `src/benchmark_bancos/config/`).

| Campo origen | `raw.cartera.data` / `staging.cartera` | Transformación | `marts.*` |
|---|---|---|---|
| Nombre de hoja `BASE ...` | `tipo_credito` | Regex de palabras clave (`vivienda interes`→`vivienda_interes_publico`, `inmobiliario`, `productivo`→`comercial`, `consumo`, `microcredito`, `educativo`); orden importa, `vivienda interes` se evalúa antes que `inmobiliario` | `dim_segmento_credito` (JOIN por mapeo `tipo_credito`→`segmento`, ver `sql/16_dim_segmento_normativo.sql`) → `fact_saldo_cartera.segmento_id` (2026-07-19: antes columna directa `tipo_credito` sin FK) |
| Columna `FECHA` | `fecha` | `month_end_date()` — normaliza a fin de mes | `dim_fecha` (JOIN por `fecha`) → `fact_saldo_cartera.fecha_id` |
| Columna `ENTIDAD` | `banco`, `banco_codigo` | `normalize_banco()` + `resolver_banco_codigo(nombre, "CAPCOL")` (`banco_matching.py`) — falla con `BancoNoResueltoError` si no resuelve. **Pendiente de implementación, diseño aprobado 2026-09-01** (`docs/fuentes_datos.md` sección 1.1): al integrar el sub-portal Banca Pública, 3 valores nuevos de `ENTIDAD` (`BANECUADOR B. P.`, `BANCO DE DESARROLLO DEL ECUADOR B.P.`, `CORPORACION FINANCIERA NACIONAL B.P.`) resuelven vía `src/benchmark_bancos/seeds/banco_crosswalk.csv` directo al `banco_codigo` `BCE_<ruc>` que BCE ya había auto-registrado — primera vez que el crosswalk apunta fuera de `src/benchmark_bancos/seeds/banco_maestro.csv` (ver riesgo de orden de carga en `docs/gobernanza_datos.md`) | `dim_banco` (JOIN por `banco_codigo`, poblado desde `staging.banco_maestro`) → `fact_saldo_cartera.banco_id` |
| *(implícito, no una columna)* | `tipo_entidad` | **Hoy hardcodeado `'BANCO PRIVADO'` en `_parse_sheet()`** (`parse_cartera.py`) para toda fila, sin importar el origen — al integrar Banca Pública esto debe parametrizarse por sub-portal de origen (`'BANCO PUBLICO'` para `capcol-instituciones-publicas/`), pendiente en el carril de `data-engineer`; si se reapunta el scraper sin este cambio, las filas de Banca Pública quedarían mal etiquetadas `'BANCO PRIVADO'` sin error visible (ver `docs/fuentes_datos.md` sección 1.1, punto 2 de la lista de pendientes) | filtra el `WHERE s.tipo_entidad = ...` de `fact_saldo_cartera`/`fact_saldo_depositos` en `_REFRESH_MARTS_SQL` |
| Columna `PROVINCIA` | `provincia` | `normalize_provincia()` (2026-07-25, antes `normalize_text()`) | `dim_provincia` (JOIN `provincia`, con `translate()` de respaldo para una fila histórica con tilde — ver `docs/gobernanza_datos.md`) → `dim_canton.provincia_id` |
| Columna `CANTON` | `canton` | `normalize_text()` | `dim_canton` (JOIN `canton`+`provincia_id`) → `fact_saldo_cartera.canton_id` |
| *(derivado de `PROVINCIA`)* | `region` | `region_for_provincia()` vía `PROVINCIA_REGION` (`src/benchmark_bancos/config/`) | **No se materializa en `marts`** directamente — vive en `staging.cartera` (informativo) y en `dim_provincia.region` (única fuente de verdad en `marts`, 2026-07-25) |
| Columnas `POR VENCER` / `NO DEVENGA INTERESES` / `VENCIDA` (ancho→largo, una fila de salida por columna con valor) | `estado_cartera` | `ESTADO_COLUMNS` mapea el nombre de columna a `por_vencer`/`no_devenga_intereses`/`vencida` — **`staging.cartera` se queda en formato largo** (no cambió, el pivote ocurre recién en `refresh_marts()`) | `dim_segmento_credito`/`fact_saldo_cartera` ya no tienen `estado_cartera` — pivotado a columnas (ver fila siguiente), 2026-07-25 `sql/21_fact_saldo_cartera_pivot.sql` |
| Valor de la columna de estado correspondiente | `saldo` | **`SUM` por groupby** sobre `(fecha, banco, cantón, tipo_credito, estado)` en `staging.cartera` (el origen trae detalle de oficina/cuenta). En `refresh_marts()`: pivote vía `SUM(saldo) FILTER (WHERE estado_cartera = '...')`, agrupando por `(fecha, banco, cantón, segmento)` — el `estado_cartera` de staging deja de ser parte del grano de `marts`, se convierte en 3 columnas de medida | `fact_saldo_cartera.saldo_por_vencer`/`.saldo_no_devenga_intereses`/`.saldo_vencida` + `.saldo_total` (columna `GENERATED`, suma de las 3) |
| *(no existe en la fuente — confirmado contra archivos reales y la ficha metodológica)* | — | — | `tasa_ponderada`, `.morosidad`, `.saldo_x_tasa` eran columnas reservadas nunca pobladas — **eliminadas 2026-07-19** (`sql/15_rename_fact_tables.sql`, junto con el rename a `fact_saldo_cartera`); la tasa real por producto ya vive en `fact_colocaciones_cartera` |
| Nombre del ZIP | `source_file` | — | No se propaga a `marts` |
| SHA-256 del archivo | `source_hash` | `sha256_file()` | Solo usado por `meta.source_files` (idempotencia de carga) |

**Llave natural** `staging.cartera`: `(fecha, tipo_entidad, banco, canton, tipo_credito, estado_cartera)`.
Código: `src/benchmark_bancos/transform/parse_cartera.py`, `src/benchmark_bancos/load/load_postgres.py::upsert_staging_cartera`.

**Bug de descarte silencioso en el JOIN `staging.cartera`/`staging.depositos` →
`dim_canton` (encontrado y mitigado 2026-08-30)**: `refresh_marts()` puebla
`marts.dim_canton` con un `INNER JOIN` contra `marts.dim_provincia` (`provincia_id` es
`NOT NULL`) — cualquier fila cuya `provincia` no matcheara ahí (ni exacto ni vía
`translate()`) se descartaba sin error ni fila huérfana visible, para cartera y para
depósitos. `src/benchmark_bancos/load/load_postgres.py::_log_cantones_no_resueltos()` corre al inicio de
cada `refresh_marts()` y loguea WARNING con el detalle si esto ocurre (INFO "0 filas" si
no) — verificado contra la base viva en esta sesión: **0 filas afectadas hoy** en ambas
tablas. No se agregó una tabla de rechazos (`staging.catalogo_rechazos`) para este caso
específico — ver la justificación completa en `docs/gobernanza_datos.md`.

## 2. CAPCOL — Depósitos

Fuente: un solo Excel por año, hoja `BASE ...` con `TIPO DE DEPOSITO` ya como columna
(más granular que la ficha metodológica: incluye buckets de plazo en días).

| Campo origen | `raw.depositos.data` / `staging.depositos` | Transformación | `marts.*` |
|---|---|---|---|
| `FECHA` | `fecha` | `month_end_date()` | `dim_fecha` → `fact_saldo_depositos.fecha_id` |
| `ENTIDAD` | `banco`, `banco_codigo` | igual que cartera (`resolver_banco_codigo(nombre, "CAPCOL")`) | `dim_banco` → `fact_saldo_depositos.banco_id` |
| `PROVINCIA` | `provincia` | `normalize_provincia()` (2026-07-25, antes `normalize_text()`) | `dim_provincia` (JOIN `provincia`) → `dim_canton.provincia_id` |
| `CANTON` | `canton` | `normalize_text()` | `dim_canton` → `fact_saldo_depositos.canton_id` |
| `REGION` (columna del archivo fuente) | `region` | **2026-07-25: ya NO se usa** — siempre `region_for_provincia(provincia)` (antes tenía prioridad la columna del archivo, que resultó inconsistente con `PROVINCIA_REGION` para MORONA SANTIAGO — "AMAZONICA" vs. "ORIENTE" — y producía 2 regiones distintas para la misma provincia en `dim_canton`; ver `docs/gobernanza_datos.md`) | No materializado en `marts` directamente — `dim_provincia.region` es la única fuente de verdad |
| `TIPO DE DEPOSITO` | `tipo_deposito` (crudo, preservado), `categoria_deposito`, `plazo_dias_desde`, `plazo_dias_hasta` | `resolver_categoria_deposito()` (`categoria_deposito_matching.py`) — separa 2 conceptos que CAPCOL mezcla: 5 de los 13 valores crudos son en realidad buckets de plazo de la categoría `DEPÓSITOS A PLAZO` (ej. `"DE 1 A 30 DÍAS"`), no una categoría de producto distinta; falla con `CategoriaNoResueltaError` si no resuelve | `dim_categoria_deposito` (JOIN `categoria`) → `categoria_deposito_id`; `dim_plazo` (JOIN `dias_desde`+`dias_hasta`) → `plazo_id` (`NULL` salvo `DEPÓSITOS A PLAZO`) |
| `SALDO` | `saldo` | **`SUM`** por groupby sobre `(fecha, banco, cantón, tipo_deposito)` — detalle de cuenta contable sumado | `fact_saldo_depositos.saldo` |
| `NUMERO DE CUENTAS` | `numero_cuentas` | `SUM` | `fact_saldo_depositos.numero_cuentas` |
| `NUMERO DE CLIENTES` | `numero_clientes` | `SUM` | `fact_saldo_depositos.numero_clientes` |

`saldo_x_tasa`/`tasa_ponderada` (reservadas, nunca pobladas) también se eliminaron de
`fact_saldo_depositos` el 2026-07-19, mismo motivo que en cartera.

**Llave natural** `staging.depositos`: `(fecha, tipo_entidad, banco, canton, tipo_deposito)`.
Código: `src/benchmark_bancos/transform/parse_depositos.py`, `upsert_staging_depositos`.

## 3. BCE — tsp (tasas pasivas, semanal)

Fuente: CSV dentro de ZIP (711MB–1.75GB descomprimido), columnas
`semana;ruc;razon_social;sector_financiero;tipo_entidad;tipo_segmento;instrumento_captacion;
provincia;canton;plazo;monto_total;numero_operaciones;tasa_pasiva_efectiva;tasa_nominal`.
**Sin filtro de `tipo_entidad`** (corregido 2026-07-19, ver "Principio" arriba): el
archivo cubre 456 entidades reales del sistema financiero completo — 37 bancos privados,
7 bancos públicos, 394 cooperativas de ahorro y crédito, 5 mutualistas, 12 sociedad
financiera, 1 administradora de tarjetas de crédito.

**Cambio de grano completado (2026-09-01, `sql/28_bce_canton_grain.sql` +
`data-engineer`)**: el grano de `fact_captaciones_depositos` (antes `fact_tasas_pasivas`,
renombrada 2026-07-19) pasó de `(fecha, banco, categoría, plazo, provincia)` — sin
cantón, el archivo trae cantón como grano más fino dentro de cada provincia y
`_weighted_agg()` lo reagregaba — a `(fecha, banco, categoría, plazo, cantón)`, igualando
el patrón ya usado por CAPCOL. Esquema (`staging.bce_tasas_pasivas.canton`,
`marts.dim_canton` expandido a 228 filas, `marts.fact_captaciones_depositos.canton_id`),
función de resolución (`src/benchmark_bancos/transform/canton_matching.py::resolver_canton_bce()`) e
integración en el parser (`_resolve_canton()`, `src/benchmark_bancos/transform/parse_bce_tasas.py`) están
todos en producción. Reprocesado el histórico completo vía
`reprocess_bce_staging()` (backfill de un solo uso, eliminado del código el 2026-10-05) (nuevo stage CLI
`bce-reprocess-canton-grain`): `marts.fact_captaciones_depositos` quedó en **3.077.474
filas** (0 con `canton_id` NULL), `marts.dim_canton` se mantuvo en 228 filas, todas
`CONFIRMADO` (0 pares nuevos `AUTO_INGRESADO` — el universo sembrado en `sql/28` ya
cubría el histórico real completo de BCE). 334.556 filas cayeron en el bucket
`NACIONAL`/`S-N` (sin geografía desagregada, estructural para ciertos instrumentos — ver
`docs/gobernanza_datos.md`, sumabilidad). La tabla de abajo describe el comportamiento
**actual** del parser, ya no un objetivo pendiente.

| Campo origen | `raw.bce_tasas_pasivas.data` | Transformación (staging) | `staging.bce_tasas_pasivas` | `marts.fact_captaciones_depositos` |
|---|---|---|---|---|
| `semana` | `fecha` (derivada, `read_raw()`) | `pd.to_datetime(..., format="%d/%m/%Y")` | `fecha` | `dim_fecha` → `fecha_id` |
| `razon_social`, `ruc`, `tipo_entidad` (original) | tal cual, sin resolver | `resolver_entidad_bce(razon_social, ruc, tipo_entidad)` — **dos caminos**: si `tipo_entidad == 'BANCOS PRIVADOS'`, identidad curada igual que siempre (`resolver_banco_codigo`, `banco_crosswalk.csv`, `BancoNoResueltoError` si no resuelve, **sin** validación estructural de RUC — ver nota abajo); si no, `banco_codigo = "BCE_" + ruc` **auto-registrado sin curación manual** (~420 entidades, inviable curar a mano una por una — ver `docs/gobernanza_datos.md`), pero **desde 2026-08-30 el RUC pasa primero por `validar_ruc_estructura()`** (13 dígitos, provincia 01-24, tercer dígito 9/6, dígito verificador módulo 11 — algoritmo estándar de sociedades del SRI, verificado contra las 409 entidades no-privadas ya vigentes en `marts.dim_banco`, 0 rechazos falsos) — un RUC estructuralmente inválido lanza `RucInvalidoError` y bloquea esa fila en vez de auto-registrarse con una llave malformada. El `ruc` de la fila se devuelve siempre, privados incluidos (2026-07-23) | `banco_codigo` | `dim_banco` (JOIN `banco_codigo`) → `banco_id`/`.ruc`/`.estado_validacion` (`CONFIRMADO` para privados, `AUTO_INGRESADO` para auto-registrados, ver `docs/data_dictionary.md`). Todas las entidades pasan por `upsert_banco_maestro_ruc()` (crea la fila si no existe — no-privadas — y siempre actualiza `ruc`; `banco`/`tipo_entidad`/`estado_validacion='CONFIRMADO'` de los privados los sigue fijando `load_banco_maestro_seed()` desde el CSV, `nombre = razon_social` tal cual solo para no-privados) |
| `instrumento_captacion` | tal cual | Validado contra `CATEGORIAS_VALIDAS` (11 valores; verificado 2026-07-19 que las 5 que realmente aparecen en tsp — con o sin filtro de entidad — están todas cubiertas) | `categoria_deposito` | `dim_categoria_deposito` → `categoria_deposito_id` |
| `plazo` | tal cual | `resolver_plazo_bce()` (`bce_plazo_matching.py`) — quita prefijo ordinal (`"a. "`...), parsea rango en días (tsp: 7 buckets; verificado sin filtro, mismos 7 para todo el sistema) | `plazo_codigo`, `plazo_dias_desde`, `plazo_dias_hasta` | `dim_plazo` (JOIN `dias_desde`+`dias_hasta`) → `plazo_id` |
| `provincia`, `canton` | tal cual (raw sí preserva ambos) | `_resolve_canton()` llama `resolver_canton_bce(canton, provincia)` (`src/benchmark_bancos/transform/canton_matching.py`) sobre las ~226 combinaciones distintas (patrón `_resolve_identidad`), resuelve el PAR completo (nunca cantón solo, por los homónimos en 2 provincias) y devuelve `(canton, provincia)` normalizados sin colapsar — `CantonNoResueltoError` si la provincia no resuelve, nunca por un cantón fuera del universo sembrado (two-tier) | `provincia`, `canton` (siempre poblado, columna agregada por `sql/28`) | `dim_canton` (JOIN `canton`+`provincia` vía `dim_provincia`) → `fact_captaciones_depositos.canton_id` (columna agregada por `sql/28`, reemplaza `provincia_id`) |
| `monto_total`, `numero_operaciones` | tal cual | Sin agregar entre cantones — un valor por fila de cantón real (grano más fino ya alcanzado); `_weighted_agg()` se mantiene como red de seguridad ante duplicados reales del archivo fuente en la misma llave, no como colapso geográfico | igual | `fact_captaciones_depositos.monto_total`/`.numero_operaciones` |
| `tasa_pasiva_efectiva`, `tasa_nominal` | tal cual | Tal cual, sin reagregar (ya al grano más fino real) salvo que existan duplicados exactos en la llave, en cuyo caso `_weighted_agg()` promedia ponderado por `monto_total` | igual | `fact_captaciones_depositos.tasa_pasiva_efectiva`/`.tasa_nominal` — **nunca sumar/promediar simple al reagregar a un nivel superior, siempre reponderar por `monto_total`** (ver `docs/gobernanza_datos.md`, sumabilidad) |
| `tipo_segmento` | preservada en `raw.*` (columna original) | 2026-07-25 (antes descartada sin examinar su contenido, ver `docs/gobernanza_datos.md` "Clasificación normativa de entidad"): validada contra `TIPOS_SEGMENTO_VALIDOS` (14 valores), resuelta una vez por `(fecha, banco_codigo)` (`_resolve_segmento_entidad`, gana la fila de mayor `monto_total` en el puñado de casos donde no es estable dentro de la semana) | `tipo_segmento` | `dim_segmento_entidad` (JOIN `tipo_segmento`) → `fact_captaciones_depositos.segmento_entidad_id`; además `dim_banco.segmento_entidad_id` (última clasificación conocida, actualizada en `refresh_marts()`) |
| `sector_financiero` | preservada en `raw.*` (columna original) | descartada, no pasa a staging (redundante con `dim_banco.tipo_entidad`) | — | — |

**Llave natural** `staging.bce_tasas_pasivas`: `(fecha, banco_codigo, categoria_deposito, plazo_dias_desde, COALESCE(plazo_dias_hasta,-1), COALESCE(provincia,''), COALESCE(canton,''))`
(`canton` agregado a la llave por `sql/28_bce_canton_grain.sql`, 2026-09-01 — antes sin
`canton`). Código: `src/benchmark_bancos/transform/parse_bce_tasas.py::read_raw` (captura), `parse_tsp_file`
(staging), `src/benchmark_bancos/transform/banco_matching.py::resolver_entidad_bce` (identidad),
`src/benchmark_bancos/transform/canton_matching.py::resolver_canton_bce` (geografía, integrada en
`parse_tsp_file` vía `_resolve_canton()`),
`src/benchmark_bancos/load/load_postgres.py::upsert_banco_maestro_ruc`. Conteos a grano provincia
(2026-07-19, previo al cambio de grano): raw 3.077.976 filas, staging = marts =
1.956.386 filas exactas (0 filas huérfanas en el JOIN a `dim_banco`), de las cuales
485.588 son de los 33 bancos privados curados y 1.470.798 de las ~399 entidades
auto-registradas. **Conteos a grano cantón, verificados en producción tras el reproceso
completo (2026-09-01, `reprocess_bce_staging()` (backfill de un solo uso, eliminado del código el 2026-10-05))**:
`marts.fact_captaciones_depositos` = **3.077.474 filas** (0 con `canton_id` NULL) — el
aumento real (~1.57x) quedó en línea con el estimado previo (~1.6x, medido sobre
combinaciones distintas de jun-2026: 26.998 a grano cantón vs. 16.393 a grano provincia).
`marts.dim_canton` se mantuvo en 228 filas, todas `CONFIRMADO` (0 pares nuevos
`AUTO_INGRESADO` — el universo sembrado en `sql/28` ya cubría el histórico real
completo).

## 4. BCE — tsa (tasas activas, semanal)

Misma estructura y mismo fix que tsp (ver arriba); difiere en la columna de segmento y
el destino de catálogo. 466 entidades distintas en el archivo real (37 privados, 8
públicos, 402 cooperativas, 5 mutualistas, 12 sociedad financiera, 2 tarjetas de
crédito).

| Campo origen | `staging.bce_tasas_activas` | Transformación | `marts.fact_colocaciones_cartera` |
|---|---|---|---|
| `segmento_credito` | `segmento_credito` | Validado contra `SEGMENTOS_VALIDOS` (26 valores, universo completo sembrado en `sql/08`; verificado 2026-07-19 sin filtro de entidad, los 26 aparecen tal cual, ninguno nuevo); desconocido → `SegmentoNoResueltoError` | `dim_subsegmento_credito` (JOIN `subsegmento`, columna renombrada de `dim_segmento_credito.segmento` en `sql/16`) → `subsegmento_id` |
| `tasa_activa_efectiva` | `tasa_activa_efectiva` | Promedio ponderado por `monto_total` (igual que tsp) | `fact_colocaciones_cartera.tasa_activa_efectiva` |
| *(resto de columnas: `semana`, `razon_social`/`ruc`/`tipo_entidad`, `plazo`, `provincia`, `canton`, `monto_total`, `numero_operaciones`, `tasa_nominal`)* | igual que tsp | igual que tsp (mismo `resolver_entidad_bce`, mismo `resolver_plazo_bce` — tsa usa 14 buckets, mezcla de días/años, verificado sin filtro) | igual que tsp |

**Llave natural**: `(fecha, banco_codigo, segmento_credito, plazo_dias_desde, COALESCE(plazo_dias_hasta,-1), COALESCE(provincia,''), COALESCE(canton,''))`
(`canton` agregado por `sql/28_bce_canton_grain.sql`, 2026-09-01, mismo cambio de grano
que tsp arriba, `resolver_canton_bce()` integrado en `parse_tsa_file` vía
`_resolve_canton()`). Código: `src/benchmark_bancos/transform/parse_bce_tasas.py::parse_tsa_file`.
Conteos a grano provincia (2026-07-19, previo al cambio de grano): raw 7.757.194 filas,
staging = marts = 4.869.696 filas exactas, de las cuales 1.462.134 son de bancos privados
y 3.407.562 de las ~408 entidades auto-registradas. `marts.dim_banco` terminó con 442
bancos totales (33 curados + 409 auto-registrados, algunos compartidos entre tsp/tsa
deduplicados por `ON CONFLICT DO NOTHING` en `staging.banco_maestro`). **Conteos a grano
cantón, verificados en producción tras el reproceso completo (2026-09-01)**:
`marts.fact_colocaciones_cartera` = **7.756.581 filas** (0 con `canton_id` NULL). De las
3.077.474 + 7.756.581 filas combinadas de ambas fact tables, 334.556 cayeron en el
bucket `NACIONAL`/`S-N` (geografía no desagregada, estructural por tipo de instrumento —
ver `docs/gobernanza_datos.md`, sumabilidad).

## 5. BCE — `TasasHistorico.htm` (techos y referenciales, mensual, nivel sistema)

Fuente: página HTML `TasasVigentes{MM}{YYYY}.htm`, 2 `<table>` físicas que mezclan 5
secciones lógicas vía celdas combinadas — la sección de cada fila se detecta **por su
contenido** (texto de encabezado fusionado), no por en qué tabla física cae, porque esa
asignación **no es estable entre años** (ver `parse_tasas_historicas.py`, docstring).
`staging.tasas_referenciales` es la única tabla "larga" del proyecto (una fila por
sección/métrica, no ancha) — se ensancha a 4 tablas en `marts` dentro de `refresh_marts()`.

| Campo origen | `staging.tasas_referenciales` | Transformación | `marts.*` |
|---|---|---|---|
| Nombre de archivo `TasasVigentes{MM}{YYYY}.htm` | `fecha` | Fin de mes derivado del **nombre del archivo** (no del texto "Junio 2026" dentro del HTML) | `dim_fecha` → `fecha_id` en las 4 tablas |
| Encabezado fusionado "TASAS DE INTERÉS ACTIVAS MÁXIMAS" + fila (label=segmento, valor) | `seccion='activa_maxima'`, `dimension_valor`, `metrica='tasa_activa_maxima'`, `valor` | `_segmento_label()` (quita superíndices de nota al pie; alias `PRODUCTIVO CORPORATIVO`→`PRODUCTIVO - CORPORATIVO`, única discrepancia real de nombre vs. el universo tsa) | `dim_subsegmento_credito` (JOIN `subsegmento`=`dimension_valor`) → `fact_tasas_referenciales_cartera.tasa_activa_maxima` (pivotado con `FILTER`) |
| "...ACTIVAS EFECTIVAS REFERENCIALES" + fila | `seccion='activa_referencial'`, `metrica='tasa_activa_referencial'` | igual | mismo grano (fecha×subsegmento) → `fact_tasas_referenciales_cartera.tasa_activa_referencial` |
| "...PASIVAS EFECTIVAS PROMEDIO POR INSTRUMENTO" + fila (label=categoría, valor) | `seccion='pasiva_instrumento'`, `dimension_valor`, `metrica='tasa_pasiva_promedio'` | `_categoria_label()` (alias `DEPÓSITOS DE TARJETAHABIENTES`→`FONDOS DE TARJETAHABIENTES`, armoniza con el nombre ya sembrado) | `dim_categoria_deposito` (JOIN `categoria`) → `fact_tasas_referenciales_depositos_instrumento.tasa_pasiva_promedio` |
| "...PASIVAS EFECTIVAS REFERENCIALES POR PLAZO" + fila (label `"PLAZO X-Y"`/`"PLAZO X Y MÁS"`, valor) | `seccion='pasiva_plazo'`, `plazo_dias_desde`/`plazo_dias_hasta`, `metrica='tasa_pasiva_referencial'` | `_resolver_plazo()` (regex propio, distinto del de tsp/tsa) | `dim_plazo` → `fact_tasas_referenciales_depositos_plazo.tasa_pasiva_referencial` |
| "OTRAS TASAS REFERENCIALES" + fila (label ∈ 4 métricas de sistema) | `seccion='sistema'`, `metrica` | `_METRICAS_SISTEMA` mapea el label exacto (`TASA PASIVA REFERENCIAL`, `TASA ACTIVA REFERENCIAL`, `TASA LEGAL`, `TASA MÁXIMA CONVENCIONAL`) a la columna destino | `fact_tasas_referenciales_sistema` (4 columnas, `PRIMARY KEY(fecha_id)`, pivotado con `FILTER`) |

**Llave natural** `staging.tasas_referenciales`: `(fecha, seccion, COALESCE(dimension_valor,''), COALESCE(plazo_dias_desde,-1), COALESCE(plazo_dias_hasta,-1), metrica)`.
Código: `src/benchmark_bancos/transform/parse_tasas_historicas.py`. Cobertura: solo 2022-04 a 2026-06 —
páginas anteriores usan un layout HTML distinto no soportado (ver `docs/fuentes_datos.md`).

## 6. Boletín Financiero Mensual — BALANCE / PYG

Fuente: hoja `BALANCE`/`PYG`, encabezado real en la fila con `CÓDIGO`+`CUENTA`, 23
columnas de banco individual + 9 columnas de agregado (`BOLETIN_AGGREGATE_COLUMNS`,
excluidas) — formato ancho (banco = columna), se pivota a largo. `dim_cuenta_contable` se
puebla **directo desde Python** (`upsert_dim_cuenta_contable`, antes de `refresh_marts()`),
no vía `staging.*`, porque su llave `(reporte, codigo)` no es un valor que se pueda
derivar con un `SELECT DISTINCT` de una sola columna de staging como el resto de
catálogos auto-descubiertos.

| Campo origen | Destino | Transformación | `marts.*` |
|---|---|---|---|
| Columna `CÓDIGO` | `dim_cuenta_contable.codigo`; `staging.boletin_balance/pyg.codigo` | Válido solo si matchea `^\d+$` — filas sin código (encabezado de sección tipo "ACTIVO", o subtotal tipo "MARGEN NETO INTERESES") se descartan, no son cuentas reales | `dim_cuenta_contable` (JOIN `reporte`+`codigo`) → `fact_balance/fact_pyg.cuenta_id` |
| Columna `CUENTA` | `dim_cuenta_contable.cuenta` | — (no se propaga a `staging.boletin_balance/pyg`, solo al plan de cuentas) | `dim_cuenta_contable.cuenta` |
| *(derivado de `codigo`)* | `dim_cuenta_contable.nivel`, `.codigo_padre`, `.seccion` | `nivel = len(codigo)`; `codigo_padre` = 2 dígitos menos; `seccion` = primer dígito vía `_SECCION_POR_DIGITO` (1 ACTIVO...7 CUENTAS_DE_ORDEN) — **no** de la posición de la fila, porque en PYG los códigos 4 y 5 están intercalados por margen | `dim_cuenta_contable.seccion` |
| Hoja `MET` (agrupación funcional) | `dim_cuenta_contable.grupo_met` | Primer grupo encontrado por código (**no es partición limpia** — un código puede aparecer en 2+ grupos, ver `docs/metricas_financieras.md`); solo aplica a `BALANCE`, `PYG` queda `NULL` | `dim_cuenta_contable.grupo_met` |
| *(no viene de ninguna columna del archivo — atributo de gobernanza, no de negocio)* | `dim_cuenta_contable.estado_validacion` | Nueva 2026-08-30 (`sql/25_dim_cuenta_contable_estado_validacion.sql`) — `upsert_dim_cuenta_contable()` no la lista en su `INSERT`, así que toda cuenta descubierta de aquí en adelante hereda el `DEFAULT 'AUTO_INGRESADO'` sin cambio de código; las 1.736 cuentas preexistentes se marcaron `CONFIRMADO` en la migración (backfill explícito, no vía `DEFAULT`) | `dim_cuenta_contable.estado_validacion` |
| Nombre de columna de banco individual (excluidas las 9 de agregado) | `banco` (crudo), `banco_codigo` | `resolver_banco_codigo(nombre, "BOLETIN")` | `dim_banco` → `fact_balance/fact_pyg.banco_id` |
| Valor de celda (miles de USD, confirmado en el encabezado real "en miles de dólares") | `saldo_usd` (BALANCE) / `valor_usd` (PYG) | **× 1000** | `fact_balance.saldo_usd` / `fact_pyg.valor_usd` |
| *(parámetro del pipeline, derivado del nombre de carpeta/archivo, no de una celda del Excel)* | `fecha` | — | `dim_fecha` → `fecha_id` |

**Llave natural** `staging.boletin_balance`/`boletin_pyg`: `(fecha, banco_codigo, codigo)`.
Código: `src/benchmark_bancos/transform/parse_boletin.py`, `upsert_staging_boletin_balance/pyg`,
`upsert_dim_cuenta_contable`. Cobertura: 2021-01 a 2026-06 (no se intentó cargar años
anteriores, decisión explícita de alcance, ver `docs/fuentes_datos.md`).

---

## 7. SEPS — Captaciones, Colocaciones (saldos) y Estados Financieros (2026-09-30)

Fuente: portal `estadisticas.seps.gob.ec`, descarga directa por `download_id`
(`src/benchmark_bancos/extract/download_seps.py`, ids en `src/benchmark_bancos/config/sources.py::SEPS_DOWNLOAD_IDS`). Un ZIP por
año y reporte, con Deflate64 (se lee con `stream_unzip`). Cobertura: cooperativas de
segmentos 1-3 y mutualistas. Los segmentos 4-5 publican trimestralmente y quedan fuera de
alcance. Código: `src/benchmark_bancos/transform/parse_seps.py`, `src/benchmark_bancos/pipeline.py::load_seps`. **No hay
tablas nuevas**: los tres reportes conforman contra las de CAPCOL y del Boletín.

| Campo origen | Destino | Transformación | `marts.*` |
|---|---|---|---|
| `RUC` (captaciones, colocaciones, EEFF) | `banco_codigo` | `resolver_entidad_seps()`: rellena a 13 dígitos (Excel puede entregarlo como int), valida estructura y devuelve `BCE_<ruc>`, la misma llave que BCE. Registra entidades nuevas con `upsert_banco_maestro_ruc()` | `dim_banco` → `banco_id` |
| Sufijo del archivo (`_S1`/`_S2`/`_S3`/`_SG1` o `_Mut`/`_MUT`); en EEFF, `SEGMENTO` | `tipo_entidad` | `COOPERATIVA` o `MUTUALISTA`. RUC en `SEPS_RUC_SEGUNDO_PISO` → `ENTIDAD DE SEGUNDO PISO` (`sql/29`). Solo aplica a entidades nuevas: las que ya existen conservan el tipo que les puso BCE | `dim_banco.tipo_entidad` |
| `RAZON SOCIAL` | `banco` (etiqueta de staging) | `"<razón social> (<ruc>)"`, porque la llave natural de `staging.cartera`/`depositos` usa `banco` y las razones sociales abreviadas de los reportes pueden repetirse | — (el nombre visible sale de `staging.banco_maestro`) |
| `FECHA DE CORTE` | `fecha` | `datetime` o **serial de Excel** (hoja `Base_colocacionesISEM` 2025) → fin de mes. Se ignora la hoja `Base_para_actual` (auxiliar con fecha fija 2017-06-30) | `dim_fecha` |
| `PROVINCIA`, `CANTON` | `provincia`, `canton`, `region` | `resolver_canton_bce()` (misma normalización y alias que BCE); `region` derivada de la provincia, no de la columna `REGION` de la fuente | `dim_canton` (two-tier) |
| `TIPO DE DEPOSITO` (captaciones) | `tipo_deposito`, `categoria_deposito` | `resolver_categoria_deposito_seps()`: compara sin tildes contra `CATEGORIAS_VALIDAS`. `DEPÓSITOS A LA VISTA` es nueva (`sql/30`). Sin banda de plazo → `plazo_*` NULL | `dim_categoria_deposito`; `plazo_id` NULL |
| `SALDO`, `NUMERO DE CLIENTES`, `NUMERO DE CUENTAS` | mismas medidas | Suma sobre `ESTADO OPERACIÓN` (NUEVA/VIGENTE/RENOVADA particionan el stock) | `fact_saldo_depositos` |
| `SUBTIPO DE CREDITO` (colocaciones) | `tipo_credito` | `SUBTIPO_CREDITO_SEPS` → vocabulario CAPCOL (incluye la segmentación previa a mayo 2021: `CONSUMO/COMERCIAL PRIORITARIO/ORDINARIO`). `OPERACIONES CONTINGENTES` se excluye porque no es cuenta 14. Un valor nuevo hace fallar la carga | `dim_segmento_credito` |
| `CARTERA POR VENCER` / `QUE NO DEVENGA INTERESES` / `VENCIDA` | `estado_cartera` + `saldo` (largo) | Suma sobre origen, estado y clase de operación y actividad económica (fuera del grano de `fact_saldo_cartera`) | `fact_saldo_cartera.saldo_*` |
| EEFF `CUENTA`, `DESCRIPCION CUENTA` | `codigo`; `dim_cuenta_contable` | 4* y 5* → `PYG`; el resto → `BALANCE`. `insert_dim_cuenta_contable_seps()` hace `ON CONFLICT DO NOTHING`: un código compartido conserva la descripción de Superbancos | `fact_balance`/`fact_pyg.cuenta_id` |
| EEFF `SALDO (USD)` / `SALDO_USD` | `saldo_usd` / `valor_usd` | Ya en USD (sin ×1000). Decimal `.` o `,` según el año; vacío o 0 se descarta (~70% de las filas; la ausencia equivale a 0) | `fact_balance.saldo_usd` / `fact_pyg.valor_usd` |

**Registro de ingesta**: `meta.source_files` registra cada archivo como
`seps/{año}/{archivo}` con su sha256. (Al cargarse por primera vez, el 2026-09-30, la salida
del parser también se copiaba como JSONB a `raw.*`; esa capa se eliminó en `sql/33`.)
Orden por año: primero EEFF (trae la razón social completa para las entidades nuevas),
luego captaciones y colocaciones.

---

## Patrones de transformación transversales

Válidos para las 5 fuentes, no repetidos en cada tabla arriba:

- **Identidad de banco**: siempre resuelta por `src/benchmark_bancos/transform/banco_matching.py::resolver_banco_codigo(nombre, fuente)`
  antes de `staging.*` — nunca en SQL. `fuente` ∈ `{CAPCOL, BCE, BOLETIN}` porque cada una
  tiene su propia convención de nombre crudo (código corto CAPCOL/Boletín vs. razón
  social legal completa de BCE). Un nombre no resuelto lanza `BancoNoResueltoError` — la
  identidad de banco es curada (`src/benchmark_bancos/seeds/banco_crosswalk.csv`), nunca autogenerada.
  Para BCE específicamente (`resolver_entidad_bce()`), desde 2026-08-30 el camino
  no-privado además exige que el RUC pase `validar_ruc_estructura()` (`RucInvalidoError`
  si falla) antes de auto-registrar `banco_codigo = "BCE_" + ruc` — ver sección 3/4 arriba
  y `docs/gobernanza_datos.md`. La SEPS trae RUC por fila y usa
  `resolver_entidad_seps()`, con la misma llave `BCE_<ruc>` y la misma validación.
- **Categoría de depósito / plazo**: resueltos antes de `staging.*` por
  `categoria_deposito_matching.py` (CAPCOL, BCE tsp) y `bce_plazo_matching.py` (BCE
  tsp/tsa) — mismo principio "fail loud, no autogenerar" que banco. **Plazo
  específicamente** (los 4 puntos: `bce_plazo_matching.py` tsp/tsa,
  `categoria_deposito_matching.py` CAPCOL, `parse_tasas_historicas.py` TasasHistorico) es
  el único catálogo de este proyecto que desde 2026-08-30 (`sql/27_dim_plazo_estado_validacion.sql`)
  relaja "fail loud" a dos niveles: shape regex inválido o rango inválido
  (`dias_desde > dias_hasta`) sigue siendo `PlazoNoResueltoError` duro; shape+rango
  válidos pero fuera del universo curado (`PLAZOS_*_VALIDOS`) ya no lanza, se auto-ingresa
  en `dim_plazo` con `estado_validacion='AUTO_INGRESADO'` — ver `docs/data_dictionary.md`
  y `docs/gobernanza_datos.md` (regla de calidad #1) para el detalle completo y la
  justificación de por qué `dim_plazo` es la excepción entre los 5 catálogos "cerrados".
- **CDC (`fecha_carga`/`fecha_actualizacion`)**: se aplica en `staging.*` y en los
  `fact_*`/`dim_banco` de `marts`, comparando directamente las columnas mutables en el
  `ON CONFLICT` (desde `sql/34` no hay `row_hash`). El refresh de `marts` es incremental
  por marca de agua (`meta.refresh_watermark`). A nivel de archivo, `meta.source_files`
  evita reprocesar un archivo con el mismo sha256. No hay CDC en los catálogos pequeños
  (`dim_plazo`, `dim_categoria_deposito`, `dim_segmento_credito`,
  `dim_subsegmento_credito`, `dim_cuenta_contable`, `staging.banco_maestro`), que se
  insertan/mapean/resiembran sin guard propio; `estado_validacion` (2026-08-30) se agregó
  a esos catálogos sin tocar CDC. Detalle del patrón en `docs/architecture.md`.
- **`fecha_id` (marts)**: siempre `TO_CHAR(fecha, 'YYYYMMDD')::INT`, calculado en el
  `INSERT...SELECT` de `refresh_marts()` — nunca almacenado en `staging.*`.
