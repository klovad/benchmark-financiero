# Mantenimiento de catálogos / resolución de identidad

Runbook operativo: qué hacer cuando falla un test de matching/catálogo, cuando un valor
crudo de una fuente no resuelve, o cuando aparece una fila nueva sin curar. Es
**procedimiento**, no framework — complementa a `docs/gobernanza_datos.md` (que explica
el *porqué* de cada regla y su historia) sin repetirlo: acá solo el *qué hacer, en qué
archivo exacto, y qué verificar después*, para no tener que re-derivar la arquitectura
cada vez que esto pasa. Vive en un archivo aparte (no como sección de
`gobernanza_datos.md`) porque es de un género distinto — se abre a mitad de un fallo real
para copiar/pegar un comando, no se lee de corrido como una narrativa de decisiones.

Este documento cubre los 8 catálogos que hoy resuelven identidad en Python antes de
`staging.*` (principio de diseño en `docs/architecture.md`, sección "Catálogos
conformados"): `dim_banco` (camino curado + camino auto-registrado), `dim_segmento_credito`/
`dim_subsegmento_credito`, `dim_categoria_deposito`, `dim_segmento_entidad`, `dim_plazo`,
`dim_cuenta_contable`, `dim_canton`.

## Tabla de referencia rápida

| Catálogo | Excepción(es) | Archivo:línea | Comportamiento |
|---|---|---|---|
| `dim_banco` — curado (33) | `BancoNoResueltoError` | `etl/transform/banco_matching.py:37` (raise en :121-124) | Fail-fast absoluto |
| `dim_banco` — auto-registrado (409) | `EntidadBceNoMapeadaError` (tipo_entidad), `RucInvalidoError` (RUC) | `banco_matching.py:139`, `banco_matching.py:144` (raise en :253-256 y :270-276) | Fail-fast sobre tipo/RUC; identidad en sí **no se cura**, se auto-ingresa `AUTO_INGRESADO` |
| `dim_segmento_credito`/`dim_subsegmento_credito` | `SegmentoNoResueltoError` (BCE tsa), `ValueError` (CAPCOL, sin clase propia) | `etl/transform/parse_bce_tasas.py:156` (raise :329-331); `etl/transform/parse_cartera.py:48` | Fail-fast absoluto, sin two-tier |
| `dim_categoria_deposito` | `CategoriaNoResueltaError` (CAPCOL), `ValueError` (BCE tsp, sin clase propia) | `etl/transform/categoria_deposito_matching.py:53` (raise :88-91); `parse_bce_tasas.py:291` | Fail-fast absoluto, sin two-tier |
| `dim_segmento_entidad` | `TipoSegmentoNoResueltoError` | `parse_bce_tasas.py:160` (raise :296-299 tsp, :336-339 tsa) | Fail-fast absoluto, sin two-tier |
| `dim_plazo` | `PlazoNoResueltoError` (shape/rango inválido) | `etl/transform/bce_plazo_matching.py:27` (4 puntos de raise, ver sección) | **Two-tier**: shape+rango sano fuera del universo curado → `AUTO_INGRESADO`, no lanza |
| `dim_cuenta_contable` | Ninguna — `ValueError` genérico solo ante bug de parsing (`_find_header_row`) | `etl/transform/parse_boletin.py:104-106` | Sin gate — todo código nuevo se auto-ingresa `AUTO_INGRESADO` por diseño |
| `dim_canton` (BCE tsp/tsa) | `CantonNoResueltoError` (provincia no resoluble, o canton/provincia vacíos) | `etl/transform/canton_matching.py:81` (raise en `resolver_canton_bce()`) | **Two-tier**: provincia válida pero par (canton, provincia) fuera del universo curado → `AUTO_INGRESADO`, no lanza. Integración en `parse_bce_tasas.py` pendiente (carril de `data-engineer`, ver `docs/gobernanza_datos.md`) |

`estado_validacion` (`CONFIRMADO`/`AUTO_INGRESADO`/`RECHAZADO`) solo existe en 4 tablas:
`dim_banco` (`sql/26`), `dim_plazo` (`sql/27`), `dim_cuenta_contable` (`sql/25`),
`dim_canton` (`sql/28`) — ver sección dedicada más abajo para las queries copy-paste de
revisión/confirmación de cada una. Los otros 4 catálogos son enumeraciones cerradas por
definición normativa/regulatoria sin campo de revisión: un valor nuevo ahí siempre aborta
la carga hasta que un humano lo resuelva en el código, nunca queda "pendiente" en la base.

---

## 1. `dim_banco` — camino curado (33 bancos privados)

**Error**: `BancoNoResueltoError` — `etl/transform/banco_matching.py:37-38`, lanzado desde
`resolver_banco_codigo()` (líneas 121-124):
```
No se pudo resolver banco_codigo para '<nombre crudo>' (fuente=<CAPCOL|BCE|BOLETIN>,
normalizado='<...>'). Agregar una fila a etl/seeds/banco_crosswalk.csv.
```
Se ve al correr `python -m etl.pipeline load --years ...` (CAPCOL), `python -m etl.pipeline
bce` (camino BANCOS PRIVADOS de `resolver_entidad_bce()`, que llama a
`resolver_banco_codigo()` internamente — `banco_matching.py:260`) o
`python -m etl.pipeline boletin --years ...` — la carga aborta con traceback, no hay fila
parcial. En CI no aparece nunca de forma orgánica: `test-unit` no descarga archivos reales
(sin red, ver `.github/workflows/test.yml`), así que solo se dispara en una corrida local
contra datos reales nuevos.

**Dónde arreglarlo** — dos archivos posibles, según el diagnóstico:
- **Variante de nombre de un banco YA curado** (rename de la fuente, puntuación distinta
  de "S.A."/sufijo legal no cubierto por la regla determinística `_por_regla()` de
  `banco_matching.py:82-94`, o nombre legal completo de BCE que no matchea el código corto
  de CAPCOL): agregar una fila a `etl/seeds/banco_crosswalk.csv` (columnas exactas
  `fuente,nombre_fuente,banco_codigo` — `fuente` es literal `CAPCOL`/`BCE`/`BOLETIN`,
  `nombre_fuente` el texto crudo tal cual aparece en la fuente [no importa mayúsculas,
  `_normalizar()` lo homologa], `banco_codigo` debe ser un código YA existente en
  `etl/seeds/banco_maestro.csv` — **o, desde 2026-09-01 (Banca Pública, ver
  `docs/fuentes_datos.md` sección 1.1), un `banco_codigo` `BCE_<ruc>` ya auto-registrado en
  `marts.dim_banco` por `resolver_entidad_bce()`**, cuando el objetivo es que un nombre de
  CAPCOL/BOLETIN apunte a la MISMA identidad que BCE ya generó para esa entidad en vez de
  crear una identidad paralela. `resolver_banco_codigo()` no valida contra la base viva en
  ningún caso (es una función pura, sin conexión a Postgres) — si el `banco_codigo` del
  crosswalk no existe todavía en `marts.dim_banco` cuando el `INSERT` de `fact_saldo_cartera`/
  `fact_saldo_depositos` corre, el `INNER JOIN` de esa sentencia en `_REFRESH_MARTS_SQL`
  descarta la fila silenciosamente (mismo riesgo ya conocido para `dim_canton`, ver
  `etl/load/load_postgres.py::_log_cantones_no_resueltos`) — para el caso `BCE_<ruc>` esto
  significa que BCE tsp/tsa debe haberse cargado (al menos una vez, para poblar
  `staging.banco_maestro` vía `upsert_banco_maestro_ruc()`) ANTES de que la carga de CAPCOL
  para esa entidad llegue a `refresh_marts()`; verificar `SELECT banco_codigo FROM
  marts.dim_banco WHERE banco_codigo = 'BCE_<ruc>'` devuelve 1 fila antes de confiar en que
  el crosswalk nuevo va a producir hechos, no solo que `resolver_banco_codigo()` no lanzó
  error).
- **Banco genuinamente nuevo** (licencia bancaria nueva, nunca visto en ninguna fuente):
  primero agregar una fila a `etl/seeds/banco_maestro.csv` (columnas
  `banco_codigo,banco,tipo_entidad` — `banco_codigo` nuevo código canónico, `banco` nombre
  a mostrar, `tipo_entidad` uno de los 7 valores del `CHECK` de `sql/29_dim_banco_tipo_segundo_piso.sql`:
  `BANCO PRIVADO`, `BANCO PUBLICO`, `COOPERATIVA`, `MUTUALISTA`, `SOCIEDAD FINANCIERA`,
  `TARJETAS DE CREDITO`, `ENTIDAD DE SEGUNDO PISO`), y LUEGO la(s) fila(s) de crosswalk para cada variante de nombre
  que use en CAPCOL/BCE/BOLETIN.
- **Es en realidad un bug de parsing, no un banco nuevo**: si el nombre en el mensaje de
  error se ve como ruido (vacío, media palabra, contiene texto de encabezado de columna,
  caracteres de control) en vez de un nombre de entidad legal plausible — **no** agregarlo
  al crosswalk. El bug está en el scraper/parser (`etl/extract/scrape_superbancos.py`,
  `etl/transform/parse_cartera.py`/`parse_depositos.py`/`parse_boletin.py` según la
  fuente), arreglar ahí.

**Después de arreglarlo**:
- Test nuevo en `tests/test_banco_matching.py`, patrón `test_capcol_manabi_variants_resolve_to_same_codigo`
  (línea 13) o `test_bce_legal_name_resolves_to_same_codigo_as_capcol` (línea 25): asertar
  `resolver_banco_codigo(nombre_crudo, fuente) == banco_codigo_esperado`.
- Docs: `docs/gobernanza_datos.md` (conteo de `dim_banco` en el catálogo de metadatos si el
  banco es nuevo, o nota en "Huecos de gobernanza conocidos" si es otro caso de colisión de
  RUC como Jaramillo Arteaga/Promerica). `docs/data_dictionary.md` normalmente no cambia
  salvo que se agregue un `tipo_entidad` nuevo.
- Re-ejecutar: `python -m pytest tests/test_banco_matching.py -v` (unit, sin DB), luego el
  comando de pipeline que había fallado, luego verificar `staging.<tabla>` == `marts.<tabla>`
  en la(s) tabla(s) afectada(s) (`SELECT COUNT(*) FROM staging.cartera` vs.
  `SELECT COUNT(*) FROM marts.fact_saldo_cartera`, por ejemplo).

## 2. `dim_banco` — camino auto-registrado (409 entidades no-privadas)

**Errores** (dos clases distintas, no confundir):
- `EntidadBceNoMapeadaError` — `banco_matching.py:139-141`, lanzado en :253-256 cuando
  `tipo_entidad_bce` no está en el diccionario `_TIPO_ENTIDAD_BCE` (6 claves,
  `banco_matching.py:129-136`). Mensaje: `"tipo_entidad de BCE no mapeado: '<valor>'.
  Agregar el valor a _TIPO_ENTIDAD_BCE en banco_matching.py."`
- `RucInvalidoError` — `banco_matching.py:144-153`, lanzado en :270-276 cuando
  `validar_ruc_estructura(ruc)` (líneas 178-220) devuelve `False`. Mensaje incluye el RUC,
  la razón social y qué chequeo falló en general (no cuál de los 4 específicamente).

Ambos se ven al correr `python -m etl.pipeline bce` (dentro de `_resolve_identidad()` en
`parse_bce_tasas.py:231-261`, camino NO-`BANCOS PRIVADOS` de `resolver_entidad_bce()`).

**Dónde arreglarlo**:
- `EntidadBceNoMapeadaError`: BCE empezó a reportar una categoría de `tipo_entidad` nueva.
  Agregar la clave cruda a `_TIPO_ENTIDAD_BCE` en `banco_matching.py:129-136`, mapeada a un
  valor válido del `CHECK` de `dim_banco.tipo_entidad` (`sql/07:24`) — si ese `CHECK` no
  tiene un valor adecuado, hace falta una migración `sql/NN_....sql` que lo extienda
  (`ALTER TABLE ... DROP CONSTRAINT dim_banco_tipo_entidad_check ... ADD CONSTRAINT ...
  CHECK (tipo_entidad IN (...))`) en el mismo cambio.
- `RucInvalidoError`: **casi nunca** es "relajar la validación". Primero descartar que sea
  un artefacto de parsing (RUC leído como número y perdió un cero a la izquierda, espacio
  en blanco, truncamiento) revisando el valor crudo real en
  `raw.bce_tasas_pasivas`/`raw.bce_tasas_activas` (`SELECT data->>'ruc' FROM raw.bce_tasas_pasivas
  WHERE source_file = '<archivo>' AND data->>'razon_social' = '<entidad>' LIMIT 5;`) — el
  RUC en `raw.*` nunca se transforma (`read_raw()` lo lee como texto, sin tocar, ver
  `parse_bce_tasas.py:197`). Si el RUC crudo genuinamente no pasa el chequeo estructural
  (13 dígitos, provincia 01-24, 3er dígito 9/6, dígito verificador módulo 11), es una
  pregunta de calidad de dato real, no un bug de código — **no** aflojar
  `validar_ruc_estructura()` para "dejarlo pasar". Si aparece un caso legítimamente nuevo
  (ej. un 3er dígito distinto de 9/6 que sí es válido para algún tipo de entidad no visto
  hoy), eso exige investigación deliberada con la misma rigurosidad que la validación
  actual (contrastada contra una implementación de referencia independiente, ver
  `banco_matching.py:156-162`) antes de extender la función — no un parche rápido.

**Después de arreglarlo**: test en `tests/test_banco_matching.py`, patrón
`test_resolver_entidad_bce_tipo_entidad_no_mapeado_falla_fuerte` (línea 92) o
`test_resolver_entidad_bce_ruc_invalido_no_privado_falla_fuerte` (línea 115). Docs:
`docs/gobernanza_datos.md` (conteos de entidades cambian), `docs/data_dictionary.md`
(enumeración de `tipo_entidad` si el `CHECK` cambió), `docs/architecture.md` (diagrama ER si
hubo migración de esquema). Re-ejecutar: `pytest tests/test_banco_matching.py -v`, luego
`python -m etl.pipeline bce`, luego verificar conteos.

**Nota**: una vez que una entidad *resuelve* (RUC válido, tipo mapeado), la fila nueva en
`dim_banco` **sí se auto-ingresa** con `estado_validacion='AUTO_INGRESADO'` sin curación de
nombre — eso no es un error, es el comportamiento de diseño (ver sección "Los 4 catálogos
con `estado_validacion`" más abajo para cómo revisarla/confirmarla).

## 3. `dim_segmento_credito` / `dim_subsegmento_credito`

**Dos puntos de entrada, dos comportamientos de error distintos** (real, no unificar sin
revisar primero):
- **BCE tsa**: `SegmentoNoResueltoError` — `parse_bce_tasas.py:156-157`, lanzado en
  :329-331 dentro de `parse_tsa_file()` cuando `segmento_credito` no está en
  `SEGMENTOS_VALIDOS` (26 valores, `parse_bce_tasas.py:67-94`). Mensaje:
  `f"segmento_credito desconocido en tsa: {desconocidos}"`.
- **CAPCOL cartera**: `ValueError` **sin clase propia** — `parse_cartera.py:43-48`,
  función `tipo_credito_from_sheet_name()`, cuando ningún keyword de `TIPO_CREDITO_KEYWORDS`
  (`etl/config.py:50-57`, 6 entradas) matchea el nombre de la hoja `BASE ...`. Mensaje:
  `f"No se pudo determinar tipo_credito para la hoja '{sheet_name}'"`.

Se ven al correr `python -m etl.pipeline bce` (tsa) o `python -m etl.pipeline load
--years ...` (CAPCOL). **Sin two-tier**: ningún nivel de este catálogo se auto-ingresa, ver
justificación sintaxis-vs-semántica-regulatoria en `sql/27_dim_plazo_estado_validacion.sql:26-45`.

**Dónde arreglarlo**:
- Nombre nuevo de BCE que es variante de wording de un segmento YA existente (ej. un
  renombre metodológico como "Comercial"→"Productivo" en 2022): agregar el valor crudo a
  `SEGMENTOS_VALIDOS` (`parse_bce_tasas.py:67-94`) **y** una migración
  `sql/NN_....sql` que inserte la fila nueva en `marts.dim_subsegmento_credito` con su
  `segmento_id` ya resuelto — `dim_subsegmento_credito` se siembra una sola vez
  (`sql/08`/`sql/16`), **no** se descubre dinámicamente desde `staging` en
  `refresh_marts()` (verificado: no hay `INSERT INTO marts.dim_subsegmento_credito` en
  `_REFRESH_MARTS_SQL`, solo `JOIN` de lectura) — agregar solo al set de Python sin la
  migración deja el valor validando en Python pero sin fila en `marts` a la que unirse.
- Keyword de hoja nuevo en CAPCOL que corresponde a un `tipo_credito` YA existente:
  agregar el keyword a `TIPO_CREDITO_KEYWORDS` (`etl/config.py:50-57`).
- Si el texto se ve como ruido (encoding roto, hoja equivocada, truncamiento): bug de
  parsing, arreglar `find_base_sheets()`/`_parse_sheet()`/el regex, no el set.

**Después de arreglarlo**: no existe hoy un `tests/test_parse_bce_tasas.py` ni
`tests/test_parse_cartera.py` puros (verificado contra el listado de `tests/`) — el
precedente más cercano es `tests/test_parse_tasas_historicas.py` (tests de alias de
segmento, ej. `test_segmento_alias_agrega_el_guion_que_falta_en_esta_fuente`, línea 14).
**Esto es un hueco de cobertura real** para `SEGMENTOS_VALIDOS`/`TIPO_CREDITO_KEYWORDS`
en sí — si se toca alguno de los dos, es buen momento para crear el archivo de test
correspondiente en vez de dejarlo sin cubrir de nuevo. Docs: `docs/data_dictionary.md`
(conteos 7/26 y la tabla de mapeo subsegmento→segmento), `docs/gobernanza_datos.md`
(catálogo de metadatos). Re-ejecutar: `pytest -m "not integration" -v`, el comando de
pipeline, luego `SELECT COUNT(*) FROM marts.dim_subsegmento_credito` contra el nuevo
conteo esperado y `staging.bce_tasas_activas` == `marts.fact_colocaciones_cartera` en filas.

## 4. `dim_categoria_deposito`

**Dos puntos de entrada**:
- **CAPCOL depositos**: `CategoriaNoResueltaError` — `categoria_deposito_matching.py:53-54`,
  lanzado en :88-91 por `resolver_categoria_deposito()` cuando el texto no está en
  `CATEGORIAS_VALIDAS` (11 valores, líneas 17-29) ni matchea el shape de un bucket de
  plazo (`_RANGO`/`_SIN_TOPE`, líneas 33-34).
- **BCE tsp**: `ValueError` **sin clase propia** — `parse_bce_tasas.py:288-291`, cuando
  `instrumento_captacion` no está en el mismo `CATEGORIAS_VALIDAS` (importado en la línea
  57 desde `categoria_deposito_matching.py`).

Dentro de `resolver_categoria_deposito()` hay además un sub-camino de plazo (cuando el
texto matchea "DEPÓSITOS A PLAZO"): ese sub-camino **sí es two-tier** — ver sección 6
(`dim_plazo`) — pero la categoría en sí (`CATEGORIAS_VALIDAS`) siempre es fail-fast
absoluto, nunca se auto-ingresa un nombre de categoría nuevo.

Se ven al correr `python -m etl.pipeline load --years ...` (CAPCOL) o `python -m etl.pipeline
bce` (tsp).

**Dónde arreglarlo**: misma triage que segmento_credito — variante de wording de una
categoría existente → agregar a `CATEGORIAS_VALIDAS`
(`categoria_deposito_matching.py:17-29`) **y** migración `sql/NN_....sql` que inserte la
fila en `marts.dim_categoria_deposito` (sembrada una vez en `sql/08`/`sql/16`, sin
descubrimiento dinámico — mismo patrón que `dim_subsegmento_credito`); categoría
genuinamente nueva → mismo tratamiento; texto con pinta de ruido/columna mal leída → bug
de parser, no tocar el set.

**Después de arreglarlo**: `tests/test_categoria_deposito_matching.py` tiene el patrón
exacto — `test_unresolved_value_raises` (línea 48) / `test_empty_value_raises` (línea 53)
para el fail-fast de categoría, `test_plazo_bucket_con_shape_valido_pero_desconocido_no_lanza`
(línea 58) para el sub-caso two-tier de plazo. Extender el que aplique. Docs:
`docs/data_dictionary.md` (`dim_categoria_deposito`, hoy 12 valores: 11 sembrados + 1 alias
de `TasasHistorico`), `docs/gobernanza_datos.md`. Re-ejecutar:
`pytest tests/test_categoria_deposito_matching.py -v`, el comando de pipeline, verificar
conteos.

## 5. `dim_segmento_entidad`

**Error**: `TipoSegmentoNoResueltoError` — `parse_bce_tasas.py:160-161`, lanzado en
:296-299 (tsp) / :336-339 (tsa) cuando `tipo_segmento` no está en `TIPOS_SEGMENTO_VALIDOS`
(14 valores, `parse_bce_tasas.py:103-118`). Se ve al correr `python -m etl.pipeline bce`.
Sin two-tier, fail-fast absoluto.

**Dónde arreglarlo**: un tier regulatorio genuinamente nuevo (ej. SEPS agrega un
"SEGMENTO 6" para cooperativas) → agregar a `TIPOS_SEGMENTO_VALIDOS`
(`parse_bce_tasas.py:103-118`) **y** una migración que inserte la fila en
`marts.dim_segmento_entidad` (`sql/19_dim_segmento_entidad.sql:20-25`, `ON CONFLICT
(tipo_segmento) DO NOTHING`, sembrada una sola vez — sin `INSERT` dinámico en
`_REFRESH_MARTS_SQL`, solo `LEFT JOIN` de lectura en las líneas ~733/765 de
`load_postgres.py`).

**Nota de riesgo latente** (no activo hoy): como el `JOIN` en `fact_captaciones_depositos`/
`fact_colocaciones_cartera` es `LEFT JOIN` (no `INNER`), un `tipo_segmento` no mapeado que
lograra saltarse la validación de Python terminaría con `segmento_entidad_id = NULL` en
vez de un error — hoy es inalcanzable porque Python valida antes de `staging`, pero es el
mismo tipo de descarte silencioso ya documentado para `dim_canton` en
`docs/gobernanza_datos.md` ("Bug de descarte silencioso... mitigado 2026-08-30"). Si algún
día se sospecha, comparar `COUNT(*) FROM marts.fact_captaciones_depositos WHERE
segmento_entidad_id IS NULL` contra `COUNT(*) FROM staging.bce_tasas_pasivas WHERE
tipo_segmento IS NULL` — si el primero es mayor, hay filas con `tipo_segmento` no-NULL que
no matchearon.

**Después de arreglarlo**: no hay archivo de test dedicado a `TIPOS_SEGMENTO_VALIDOS` hoy
(mismo hueco de cobertura que la sección 3) — considerar crear uno si se toca esta
constante. Docs: `docs/data_dictionary.md` (conteo 14 → nuevo), `docs/gobernanza_datos.md`.
Re-ejecutar: `pytest -m "not integration" -v`, `python -m etl.pipeline bce`, verificar
conteos.

## 6. `dim_plazo` (two-tier, 4 puntos de entrada)

**Error** (solo para shape/rango inválido): `PlazoNoResueltoError` —
`bce_plazo_matching.py:27-41` — lanzado desde 4 lugares:
1. `bce_plazo_matching.py::resolver_plazo_bce()` línea 168-171 (BCE tsp/tsa — shape no
   reconocido).
2. `bce_plazo_matching.py::validar_rango_plazo()` línea 56-61 (chequeo de rango compartido
   por los 4 puntos — `dias_desde < 0`, o `dias_desde > dias_hasta` con `dias_hasta` no
   `NULL`).
3. `categoria_deposito_matching.py::resolver_categoria_deposito()` (CAPCOL depositos, vía
   `validar_rango_plazo()`).
4. `parse_tasas_historicas.py::_resolver_plazo()` línea 97-100 (`TasasHistorico.htm`).

**Camino sin error (2026-08-30, `sql/27`)**: shape válido + rango sano pero el texto NO
está en `PLAZOS_TSP_VALIDOS` (7)/`PLAZOS_TSA_VALIDOS` (14)/`PLAZOS_VALIDOS` (5, CAPCOL,
`categoria_deposito_matching.py:44-50`)/`PLAZOS_VALIDOS` (6, TasasHistorico,
`parse_tasas_historicas.py:63-74`) → **no lanza nada**. La fila llega a
`marts.dim_plazo` con `estado_validacion='AUTO_INGRESADO'` (DEFAULT, `sql/27`). Esto **no
se ve en ningún log de pipeline** — se descubre consultando `marts.dim_plazo` (sección de
abajo), no por un error.

**Dónde arreglarlo (caso fail-fast)**:
- Shape que no matchea ningún regex: revisar si BCE/CAPCOL/TasasHistorico cambió su
  formato de texto (nuevo prefijo, nueva unidad) — extender el regex correspondiente:
  `_RANGO_DIAS`/`_MENOS_DIAS`/`_MAS_DIAS`/`_RANGO_ANIOS`/`_MAS_ANIOS`
  (`bce_plazo_matching.py:20-24`), `_RANGO`/`_SIN_TOPE` (`categoria_deposito_matching.py:33-34`),
  o `_PLAZO_RANGO`/`_PLAZO_SIN_TOPE` (`parse_tasas_historicas.py:51-52`).
- Rango invertido/negativo: **siempre** un bug de parsing (el regex matcheó algo
  degenerado) — nunca "agregar una excepción para este caso", encontrar y arreglar la
  extracción.

**Qué hacer (caso `AUTO_INGRESADO`)**: normalmente no hay nada que "arreglar" en código —
es revisión, no reparación (ver sección de abajo para la query/confirmación). Si tras
revisar se confirma que es un bucket real y nuevo del BCE, opcionalmente se puede agregar
al set `PLAZOS_*_VALIDOS` correspondiente como documentación del universo conocido — esto
**no cambia el comportamiento** (el set ya no es un gate, ver `bce_plazo_matching.py:68-73`),
solo mantiene el comentario "universo confirmado" honesto.

**Después de arreglarlo (caso fail-fast)**: test en `tests/test_bce_plazo_matching.py`
(patrón `test_bucket_shape_invalido_sigue_lanzando_incluso_fuera_del_universo`, línea 73, o
`test_bucket_shape_valido_pero_rango_invertido_sigue_lanzando`, línea 82),
`tests/test_categoria_deposito_matching.py` (línea 74/81) o
`tests/test_parse_tasas_historicas.py` (línea 60/67), según cuál de los 4 puntos se tocó.
Docs: `docs/data_dictionary.md` (`dim_plazo`), `docs/gobernanza_datos.md` (conteo, hoy 21
filas). Re-ejecutar: `pytest tests/test_bce_plazo_matching.py
tests/test_categoria_deposito_matching.py tests/test_parse_tasas_historicas.py -v`, el
comando de pipeline, luego conteo.

## 7. `dim_cuenta_contable`

**No hay `*NoResueltoError`** — cualquier `(reporte, codigo)` descubierto en una hoja
BALANCE/PYG del Boletín se acepta y se hace upsert vía `upsert_dim_cuenta_contable()`
(`etl/load/load_postgres.py:455-465`, `ON CONFLICT (reporte, codigo) DO UPDATE`), llegando
con `estado_validacion='AUTO_INGRESADO'` (DEFAULT, `sql/25`) porque el `INSERT` no lista
esa columna. Esto es diseño deliberado, no un hueco: el Catálogo Único de Cuentas crece y
cambia legítimamente con cada archivo del Boletín.

El único fallo real posible acá es un **bug de parsing**, no de identidad de catálogo:
`_find_header_row()` (`etl/transform/parse_boletin.py:85-106`) lanza `ValueError` genérico
(`"No se encontró la fila de encabezado (columnas 'CÓDIGO'+'CUENTA')"`) si una hoja
BALANCE/PYG/MET no tiene el layout esperado — significa que Superbancos cambió la
plantilla Excel, no que un código de cuenta sea desconocido.

Se ve al correr `python -m etl.pipeline boletin --years ...`.

**Dónde arreglarlo**: si dispara el error de encabezado, siempre es drift de plantilla —
inspeccionar el `.xlsx` real (`data/raw/{anio}/boletin/`) y ajustar
`_find_header_row()`/`_parse_hoja()`/`_parse_met()` (`parse_boletin.py`) al layout nuevo,
nunca relajar el chequeo de encabezado como "workaround". No existe un "agregar al set"
para este catálogo — cuentas nuevas son esperadas y legítimas por diseño, por eso
auto-ingresa en vez de fallar.

**Después de arreglarlo** (solo si fue bug de parser): test/extensión en
`tests/test_parse_boletin.py`. Docs: normalmente ninguno para una cuenta nueva rutinaria
(el catálogo está pensado para crecer); si hubo un fix de parser por cambio real de
plantilla, actualizar `docs/linaje_datos.md` (sección Boletín) y `docs/fuentes_datos.md` si
la estructura real del archivo cambió. Re-ejecutar: `pytest tests/test_parse_boletin.py -v`,
`python -m etl.pipeline boletin --years <años afectados>`, verificar
`staging.boletin_balance`/`boletin_pyg` == `marts.fact_balance`/`fact_pyg` en filas.

## 8. `dim_canton` (two-tier, BCE tsp/tsa — 2026-09-01, `sql/28_bce_canton_grain.sql`)

**Error**: `CantonNoResueltoError` — `etl/transform/canton_matching.py:81-97`, lanzado
desde `resolver_canton_bce(canton, provincia)` en 2 casos: `canton`/`provincia` vacíos, o
`provincia` (tras `normalize_provincia()`) no está entre las 24 provincias reales del
Ecuador + `ZONA NO DELIMITADA` + `S/N` (`_PROVINCIAS_VALIDAS`, `canton_matching.py:66-68`).
Se verá al correr `python -m etl.pipeline bce` una vez que `data-engineer` integre la
llamada en `etl/transform/parse_bce_tasas.py` (a la fecha de esta entrada, esa integración
sigue pendiente — ver "Cambio de grano de BCE a cantón" en `docs/gobernanza_datos.md`).

**Camino sin error (two-tier, igual mecanismo que `dim_plazo`)**: provincia válida pero el
par `(canton, provincia)` normalizado no está en el universo sembrado
(`etl/seeds/canton_provincia.csv`, 228 pares, mismo universo que `sql/28` sembró en
`marts.dim_canton` con `estado_validacion='CONFIRMADO'`) → **no lanza nada**. La fila
llega a `marts.dim_canton` con `estado_validacion='AUTO_INGRESADO'` (DEFAULT) la próxima
vez que `refresh_marts()` corra su `INSERT ... ON CONFLICT (canton, provincia_id) DO
NOTHING`. Como con `dim_plazo`, esto **no se ve en ningún log de pipeline** — se descubre
consultando `marts.dim_canton` (sección de abajo).

**Dónde arreglarlo (caso fail-fast)**:
- `provincia` no resuelve: revisar si BCE cambió la ortografía de una provincia existente
  (poco probable, `normalize_provincia()` ya cubre tilde vs. sin tilde) o si agregó una
  provincia genuinamente nueva — si es real, agregarla a
  `etl/config.py::PROVINCIA_REGION` **y** una migración `sql/NN_....sql` que la siembre en
  `marts.dim_provincia`.
- `canton`/`provincia` vacíos: casi siempre bug de parsing (columna mal leída, fila de
  encabezado colada) — revisar `etl/transform/parse_bce_tasas.py`, no relajar la validación
  para aceptar vacíos.

**Qué hacer (caso `AUTO_INGRESADO`)**: revisión, no reparación — igual que `dim_plazo`, ver
sección de abajo. Antes de confirmar, verificar que sea un cantón real (no un typo de la
fuente ni un alias de un cantón ya sembrado con otra forma de texto — ver
`canton_matching.py::_ALIASES_BCE` para el precedente de 5 casos ya identificados así).

**Después de arreglarlo**: tests en `tests/test_canton_matching.py` — patrón
`test_provincia_no_resuelve_lanza_fail_fast` para el fail-fast,
`test_canton_fuera_del_universo_sembrado_no_lanza_two_tier` para el camino
`AUTO_INGRESADO`. Si se confirma un alias nuevo (mismo cantón, forma de texto distinta),
agregarlo a `_ALIASES_BCE` **y** un test en `TestAliasesBce`. Docs:
`docs/data_dictionary.md` (`dim_canton`, conteo), `docs/gobernanza_datos.md` (si cambia el
conteo de filas `AUTO_INGRESADO`/`CONFIRMADO`). Re-ejecutar:
`pytest tests/test_canton_matching.py -v`, el comando de pipeline, verificar
`staging.bce_tasas_pasivas`/`bce_tasas_activas` == `marts.fact_captaciones_depositos`/
`fact_colocaciones_cartera` en filas.

---

## Los 4 catálogos con `estado_validacion`: revisar y confirmar filas pendientes

`dim_banco`, `dim_plazo`, `dim_cuenta_contable` y (desde 2026-09-01) `dim_canton` tienen
esta columna (`CHECK IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO')`). `RECHAZADO` está
reservado, ningún flujo actual lo escribe — usarlo manualmente si se decide que una fila
auto-ingresada es inválida y no se quiere borrarla (preserva la fila para trazabilidad en
vez de un `DELETE`).

### `dim_banco`

**Encontrar filas pendientes**:
```sql
SELECT banco_id, banco_codigo, banco, tipo_entidad, ruc, segmento_entidad_id
FROM marts.dim_banco
WHERE estado_validacion = 'AUTO_INGRESADO'
ORDER BY banco_codigo;
```

**Confirmar una fila** — **importante**: `staging.banco_maestro` es la fuente de verdad
para esta columna, no `marts.dim_banco` — cada `refresh_marts()` copia
`staging.banco_maestro.estado_validacion` a `marts.dim_banco` sin preservar el valor
existente (`ON CONFLICT DO UPDATE SET estado_validacion = EXCLUDED.estado_validacion`,
`load_postgres.py:593-609`). Actualizar solo `marts.dim_banco` se revierte solo en la
próxima corrida de cualquier comando de pipeline (`bce`/`load`/`boletin`/`tasas-historicas`,
los 4 llaman `refresh_marts()` al final). Hay que tocar **las dos tablas**:
```sql
UPDATE staging.banco_maestro
SET estado_validacion = 'CONFIRMADO'
WHERE banco_codigo = 'BCE_1790123456001';

UPDATE marts.dim_banco
SET estado_validacion = 'CONFIRMADO', fecha_actualizacion = now()
WHERE banco_codigo = 'BCE_1790123456001';
```
(El segundo `UPDATE` es solo para ver el cambio reflejado de inmediato sin esperar la
próxima corrida de pipeline — el primero es el que de verdad importa a largo plazo.)

### `dim_plazo`

**Encontrar filas pendientes**:
```sql
SELECT plazo_id, dias_desde, dias_hasta, plazo_codigo
FROM marts.dim_plazo
WHERE estado_validacion = 'AUTO_INGRESADO'
ORDER BY dias_desde;
```

**Confirmar una fila** — acá sí basta con `marts.dim_plazo`: los 4 `INSERT INTO
marts.dim_plazo` de `_REFRESH_MARTS_SQL` usan `ON CONFLICT (dias_desde, COALESCE(dias_hasta,
-1)) DO NOTHING` (sin `estado_validacion` en la lista de columnas), así que una fila ya
existente **nunca se toca** de nuevo, confirmada o no:
```sql
UPDATE marts.dim_plazo
SET estado_validacion = 'CONFIRMADO'
WHERE plazo_id = 22;
```

### `dim_cuenta_contable`

**Encontrar filas pendientes**:
```sql
SELECT cuenta_id, reporte, codigo, cuenta, seccion, grupo_met
FROM marts.dim_cuenta_contable
WHERE estado_validacion = 'AUTO_INGRESADO'
ORDER BY reporte, codigo;
```

**Confirmar una fila** — igual que `dim_plazo`, el `ON CONFLICT (reporte, codigo) DO
UPDATE` de `upsert_dim_cuenta_contable()` (`load_postgres.py:459-462`) no lista
`estado_validacion` en su `SET`, así que persiste sin revertirse en la siguiente carga del
Boletín:
```sql
UPDATE marts.dim_cuenta_contable
SET estado_validacion = 'CONFIRMADO'
WHERE reporte = 'BALANCE' AND codigo = '1105010105';
```

### `dim_canton`

**Encontrar filas pendientes**:
```sql
SELECT canton_id, canton, provincia_id
FROM marts.dim_canton
WHERE estado_validacion = 'AUTO_INGRESADO'
ORDER BY canton;
```

**Confirmar una fila** — igual que `dim_plazo`/`dim_cuenta_contable`, el
`INSERT INTO marts.dim_canton ... ON CONFLICT (canton, provincia_id) DO NOTHING` de
`_REFRESH_MARTS_SQL` no lista `estado_validacion`, así que una fila ya existente **nunca
se toca** de nuevo:
```sql
UPDATE marts.dim_canton
SET estado_validacion = 'CONFIRMADO'
WHERE canton_id = 250;
```
Antes de confirmar, verificar en `marts.vw_dim_canton_geografia` que no sea un alias de
escritura de un cantón ya existente con otra forma de texto (ver
`etl/transform/canton_matching.py::_ALIASES_BCE` para el precedente de 5 casos así) — si
lo es, el fix correcto es agregarlo a `_ALIASES_BCE` y dejar la fila `AUTO_INGRESADO`
huérfana sin usar (o `RECHAZADO` si se prefiere dejar constancia explícita), no confirmarla
como cantón real independiente.

---

## Por qué esto se mantiene simple en CI/CD (y por qué no debería complicarse)

`.github/workflows/test.yml` tiene 2 jobs: `test-unit` (`pytest -m "not integration"`, sin
DB ni red) y `test-integration` (`pytest -m integration` contra un `postgres:17` service
container con `sql/*.sql` aplicado en orden). Ninguno de los dos valida ni debería validar
"¿ya está cada valor real del mundo en el catálogo?" — eso es un problema no acotado y de
juicio humano (¿es un nombre nuevo de un banco existente, un typo de la fuente, o un banco
genuinamente nuevo? Ningún test automatizado puede responder eso sin intervención).

Lo que CI **sí** valida, y es exactamente su trabajo:
- Que la lógica de matching/validación en sí funcione correctamente para los casos ya
  conocidos y para los casos sintéticos de fail-fast/two-tier (`test-unit`, los archivos
  de `tests/test_*_matching.py` y `tests/test_parse_*.py`).
- Que el CDC siga siendo un no-op en una segunda carga idéntica, que las llaves NULL-safe
  sigan funcionando, que las regresiones ya conocidas (`sql/10`, `sql/21`, `sql/23`,
  `sql/24`) no vuelvan a aparecer (`test-integration`,
  `tests/test_integration_regressions.py`).

Mantener un catálogo (agregar un banco al crosswalk, confirmar una fila `AUTO_INGRESADO`)
es una actividad **deliberadamente asíncrona y a ritmo humano**, desacoplada de CI por
diseño — no un paso pendiente de automatizar. El trabajo de CI es garantizar que, **cuando**
un humano agrega algo, no rompe el contrato ya establecido (NULL-safety, CDC, `row_hash`,
fail-fast donde corresponde) — no bloquear un `push`/PR porque todavía existe una fila
`AUTO_INGRESADO` sin revisar en la base, o porque el mundo real tiene un banco que el
crosswalk no conoce todavía. Si alguna vez se propone un gate de CI sobre "0 filas
`AUTO_INGRESADO` pendientes" o similar, es una señal de que se está confundiendo
mantenimiento de catálogo (humano, async) con corrección de código (CI, síncrono) — no
agregarlo sin repensar esta distinción primero.

---

## Ver también

- `docs/architecture.md` — sección "Catálogos conformados": por qué la resolución de
  identidad vive en Python antes de `staging`, no como tabla de alias en el esquema
  estrella.
- `docs/gobernanza_datos.md` — regla de calidad #1 (identidad curada) y #2 (universo
  cerrado y validado en BCE) para el marco completo; "Gestión de cambios de esquema" para
  el flujo de migración numerada que acompaña a un catálogo nuevo o extendido.
- `docs/data_dictionary.md` — definición de negocio y conteo actual de cada catálogo.
- `docs/linaje_datos.md` — de dónde viene cada campo crudo que alimenta estos catálogos.
