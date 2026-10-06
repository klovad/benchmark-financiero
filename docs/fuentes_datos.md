# Catálogo de fuentes de datos

Registro vivo de cada fuente: qué es, cómo se accede, la estructura **real** descubierta
(no solo la documentada), y el estado de integración. Se actualiza cada vez que se
investiga o integra una fuente nueva — es la referencia antes de rediseñar nada.

## 1. CAPCOL — Cartera y Depósitos (Superbancos) — ✅ integrada

- **URL**: `https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/`
- **Acceso**: portal WordPress con plugin "Share-one-Drive" (OneDrive/SharePoint vía AJAX
  a `admin-ajax.php`), no HTML estático. Requiere Playwright. Detalle completo en
  `docs/architecture.md`.
- **Estructura**: Año → CARTERA/DEPOSITOS (o COLOCACIONES/CAPTACIONES antes de 2024) →
  ZIP → Excel con hoja(s) `BASE ...`. Un archivo de cartera por segmento (excepto
  "Vivienda", que trae 2 hojas BASE). Un archivo de depósitos por año con todos los
  tipos.
- **Grano**: mensual, por banco x cantón x tipo_credito/tipo_deposito x estado_cartera
  (grano del archivo fuente/`staging.cartera`; `marts.fact_saldo_cartera` pivota
  `estado_cartera` a columnas desde 2026-07-25, ver `docs/data_dictionary.md`).
- **Sin tasas de interés** (confirmado). Sin balance/PyG.
- **Cargado**: `raw`/`staging`/`marts` en Postgres, 2021-01 a 2026-06, ver `docs/data_dictionary.md`.

### 1.1 Banca Pública (`capcol-instituciones-publicas/`) — ✅ cargada 2021-2025 (2026-10-01)

> **Carga 2026-10-01** (`python -m etl.pipeline all --portales publica`): 26 archivos
> (7,7 MB). 2021 trae además `vivienda`, con un solo corte (ene-2021, CFN, 3 filas). Quedan
> 22.339 filas en `fact_saldo_cartera` y 74.082 en `fact_saldo_depositos`, para 3 entidades
> y 60 meses. Staging = marts en filas y en saldo, 0 `canton_id` NULL, 1 cantón nuevo
> `AUTO_INGRESADO` (PABLO VI, Morona Santiago). Las filas de bancos privados y SEPS no
> cambiaron (hash idéntico antes y después) y una segunda corrida no actualizó nada. El
> Banco de Desarrollo del Ecuador (BdE) solo reporta cartera (Inversión Pública y
> Productivo), no depósitos. (Hasta 2026-10-05 aparecía en `dim_banco` como "BANCO DEL
> ESTADO", su razón social histórica en BCE. Ahora es "BANCO DE DESARROLLO DEL ECUADOR",
> curado en `banco_maestro.csv` junto con CFN y BanEcuador.) Dic-2025: BdE 1.718 M de cartera, BanEcuador
> 1.361 M de cartera y 1.452 M de depósitos, CFN 1.290 M de cartera y 963 M de depósitos.
> No hay contra qué conciliar: el Boletín cargado solo trae bancos privados.

Superbancos publica el hub CAPCOL en 3 sub-portales; hoy solo `capcol-bancos/` (bancos
privados) estaba integrado. Investigado con Playwright (mismo mecanismo que `capcol-bancos`,
ver "Por qué Playwright" en `docs/architecture.md`) contra la instancia Postgres nativa viva
(`pg_postmaster_start_time()` confirmó ~7 días de uptime, no un contenedor
`docker-compose` recién levantado):

- **`capcol-instituciones-publicas/`** (Banca Pública) — **mismo plugin "Share-one-Drive"**
  que `capcol-bancos`, **mismo layout de carpetas** (Año → `CARTERA`/`DEPOSITOS` desde 2024,
  `COLOCACIONES`/`CAPTACIONES` antes — idéntico rename 2024 ya documentado para bancos
  privados) y, dentro de cada Excel, **la misma hoja `BASE ...` plana** con columnas
  idénticas a las de bancos privados:
  - Cartera: `FECHA, ENTIDAD, PROVINCIA, CANTON, POR VENCER, NO DEVENGA INTERESES, VENCIDA, TOTAL SALDO`
    (hoja `BASE B PUBLICA <SEGMENTO>`, tipo_credito derivado del nombre de hoja igual que
    bancos privados — ver `tipo_credito_from_sheet_name()`).
  - Depósitos: `FECHA, ENTIDAD, REGION, PROVINCIA, CANTON, CUENTA, TIPO DE DEPOSITO, NUMERO DE CUENTAS, NUMERO DE CLIENTES, SALDO`
    (hoja `BASE BANCA PUBLICA`), idéntico a `capcol-bancos`.
  - **Años disponibles en el portal: 2016-2026** (11 carpetas), pero la hoja `BASE ...`
    plana **solo existe desde el año 2021 en adelante** — verificado descargando y abriendo
    archivos reales de 2017, 2019, 2021, 2022, 2023, 2025: 2017/2019 no tienen ninguna hoja
    `BASE ...` (solo un formato "pretty" pivotado por cantón×mes, sin columna `ENTIDAD`
    explícita, no parseable por `find_base_sheets()`/`_parse_sheet()` sin un parser nuevo);
    2021 en adelante sí trae la hoja `BASE ...` plana, formato estable 2021→2025 (confirmado
    con archivos reales de esos 3 años puntuales). **Esto coincide exactamente con el rango
    ya cargado de bancos privados** (`SCRAPER_YEARS=2021,2022,2023,2024,2025` en `.env`) —
    no hace falta ajustar el alcance de años, ya calza.
  - **Segmentos de cartera**: 4 archivos por año (`Cartera Productiva`, `Cartera de
    Microcrédito`, `Cartera de Inversión Pública`, `Cartera de Consumo`) — **sin Educativo**
    (nunca visto) y **sin Vivienda desde 2022** (el archivo "Vivienda" sí existió en
    2016-2021, hoja `BASE B PUBLICA INMOBILIARIO`, tipo_credito='inmobiliario' — dejó de
    publicarse como reporte independiente después, no hay evidencia de que el segmento se
    fusionara con otro). Los 3 segmentos correspondientes ya resuelven con las keywords
    existentes de `TIPO_CREDITO_KEYWORDS` (`etl/config.py`): "productivo"→comercial,
    "consumo"→consumo, "microcredito"→microcredito. **`INVERSIÓN PÚBLICA` es la única
    excepción real**: la hoja se llama `BASE B PUBLICA INVERSION PUBLIC(A)` y no matchea
    ninguna keyword actual (`vivienda interes`/`inmobiliario`/`productivo`/`consumo`/
    `microcredito`/`educativo`) — hace falta agregar una keyword nueva ("inversion" →
    p.ej. `inversion_publica`) en `etl/config.py::TIPO_CREDITO_KEYWORDS` y extender el
    `CASE` de mapeo `tipo_credito → dim_segmento_credito.segmento` en
    `etl/load/load_postgres.py::_REFRESH_MARTS_SQL` con
    `WHEN 'inversion_publica' THEN 'INVERSIÓN PÚBLICA'`. **No hace falta tocar
    `marts.dim_segmento_credito`**: el segmento `INVERSIÓN PÚBLICA` ya existe como 7ma fila
    desde `sql/16_dim_segmento_normativo.sql` (poblado hasta ahora solo por BCE tsa, nunca
    por CAPCOL) — es exactamente el caso que `sql/16` ya previó al modelar el rollup
    completo de 26 sub-segmentos BCE, aunque nunca lo hubiera necesitado un reporte de
    cartera de Superbancos hasta ahora.
  - **Entidades reales encontradas** (cartera+depósitos, 2021-2025, universo estable en
    los 3 años de muestra): `BANECUADOR B. P.`, `BANCO DE DESARROLLO DEL ECUADOR B.P.`
    (nombre legal vigente de BANCO DEL ESTADO/BEDE tras su renombre de 2015 — BCE también
    muestra ese mismo RUC bajo 3 razones sociales distintas en el tiempo: `BANCO DEL
    ESTADO` → `BANCO DE DESARROLLO` → `BANCO DE DESARROLLO DEL ECUADOR`, verificado
    contra `raw.bce_tasas_pasivas`), `CORPORACION FINANCIERA NACIONAL B.P.`. **Solo 3 de
    los 6 bancos públicos ya presentes en `marts.dim_banco` aparecen en este reporte**
    (BIESS, BANCO NACIONAL DE FOMENTO e IECE no reportan cartera/depósitos de banca
    comercial a Superbancos bajo este hub — consistente con su naturaleza: seguridad
    social, absorbido en BanEcuador en 2018, y crédito educativo respectivamente).
  - **Categorías de depósito y buckets de plazo: 100% ya cubiertos por el catálogo curado
    existente** (`etl/transform/categoria_deposito_matching.py::CATEGORIAS_VALIDAS`/
    `PLAZOS_VALIDOS`) — verificado contra las 15.417 filas del archivo real de depósitos
    2025 (12 cortes mensuales): las 8 categorías (`Depósitos de ahorro`, `Depósitos de
    garantía`, `Depósitos monetarios que generan/no generan intereses`, `Depósitos
    monetarios de instituciones financieras`, `Depósitos por confirmar`, `Depósitos
    restringidos`, `Depósitos de cuenta básica`) y los 5 buckets de plazo (`De 1 a 30
    días` ... `De más de 361 días`) están todos en el universo ya sembrado — **cero
    catálogos nuevos que crear**.

**Identidad de banco — decisión de diseño** (tarea explícita: resolver contra la MISMA
fila de `dim_banco` que ya generó BCE, no una identidad paralela): los 3 nombres crudos de
`ENTIDAD` (`BANECUADOR B. P.`, `BANCO DE DESARROLLO DEL ECUADOR B.P.`, `CORPORACION
FINANCIERA NACIONAL B.P.`) no matchean `_por_regla()` (el sufijo `B. P.`/`B.P.` no es
ni el prefijo `BP `/`BANCO ` ni un sufijo legal `S.A./C.A./LTDA` que la regla despoja) —
resuelven vía **`etl/seeds/banco_crosswalk.csv`**, con `banco_codigo` apuntando
**directo al `BCE_<ruc>` que `resolver_entidad_bce()` ya generó al auto-registrar estos 3
bancos desde BCE tsp/tsa** (verificado contra `marts.dim_banco` en la instancia viva:
`BCE_1768183520001`/BANECUADOR, `BCE_1760002950001`/BANCO DE DESARROLLO DEL ECUADOR (BdE),
`BCE_1760003090001`/CFN):
```csv
CAPCOL,BANCO DE DESARROLLO DEL ECUADOR B.P.,BCE_1760002950001
CAPCOL,BANECUADOR B. P.,BCE_1768183520001
CAPCOL,CORPORACION FINANCIERA NACIONAL B.P.,BCE_1760003090001
```
Es el primer uso del crosswalk donde `banco_codigo` no vive en `etl/seeds/banco_maestro.csv`
(los 33 bancos privados curados) sino en `marts.dim_banco` únicamente por el camino
auto-registrado de BCE — válido porque `resolver_banco_codigo()` no valida el `banco_codigo`
contra ninguna fuente, solo lo devuelve; ver la nota nueva en
`docs/mantenimiento_catalogos.md` sección 1 sobre el riesgo real que esto introduce (el
`INNER JOIN` de `fact_saldo_cartera`/`fact_saldo_depositos` en `refresh_marts()` descarta en
silencio una fila cuyo `banco_codigo` todavía no exista en `marts.dim_banco` — para estos 3
`banco_codigo` eso implica que BCE tsp/tsa debe haberse cargado al menos una vez antes;
verificado hoy que las 3 filas ya existen en la base viva, así que no es un problema para la
implementación actual, pero si algún día se reconstruye la base desde cero el orden de carga
del pipeline importa para esta fuente específicamente — antes no importaba porque CAPCOL/
Boletín solo usaban identidad curada, nunca dependían de que BCE hubiera corrido primero).
Las 3 filas se agregaron a `etl/seeds/banco_crosswalk.csv` y se verificaron con un test
nuevo (`tests/test_banco_matching.py::test_capcol_banca_publica_resuelve_al_mismo_codigo_bce_por_ruc`)
en esta sesión (2026-09-01) — el crosswalk y el test son el único código tocado en la Fase 1;
el resto (parser, extractor, `_REFRESH_MARTS_SQL`) queda para `data-engineer`, ver más abajo.

**Grano y conformidad**: se integra al **mismo grano y a las mismas tablas ya existentes**
(`marts.fact_saldo_cartera`/`fact_saldo_depositos`, `dim_banco`, `dim_canton`,
`dim_segmento_credito`, `dim_categoria_deposito`, `dim_plazo`) — no hace falta ninguna
tabla ni dimensión nueva, ni un outrigger (a diferencia del choque de grano CAPCOL/BCE que
sí justificó `dim_subsegmento_credito`): Banca Pública reporta exactamente al mismo grano
`(fecha, banco, cantón, tipo_credito/tipo_deposito, estado_cartera)` que bancos privados,
con el mismo vocabulario de columnas. Es, en el sentido más literal, la misma fuente
(CAPCOL) ampliando su cobertura de `tipo_entidad`, no una fuente nueva.

**Verificado que el esquema Postgres YA soporta esto sin ninguna migración** (2026-09-01,
contra la instancia nativa viva): `staging.cartera.tipo_entidad`/`staging.depositos.tipo_entidad`
son `TEXT NOT NULL` **sin** `CHECK` constraint (el comentario de cabecera de
`sql/02_schema_staging.sql:10` ya decía "Banco Privado | Banco Público | Sociedad
Financiera" desde el diseño original, nunca se usó el segundo valor hasta ahora);
`marts.dim_banco.tipo_entidad` `CHECK` (`sql/07`) ya incluye `'BANCO PUBLICO'` (los 6
bancos públicos auto-registrados por BCE ya lo usan); `marts.dim_segmento_credito` ya
tiene las 7 filas incluida `INVERSIÓN PÚBLICA`. **Cero migraciones `sql/NN_*.sql`
necesarias para esta fuente** — es el caso raro donde el modelo ya estaba listo antes de
que la fuente se investigara, precisamente porque el proyecto ya había resuelto
`INVERSIÓN PÚBLICA`/`BANCO PUBLICO` para BCE.

**Estado 2026-09-29: puntos 1-4 implementados.** Solo queda el 5 (descarga, carga y
verificación). `etl/config.py::CAPCOL_PORTALES` define cada sub-portal (`url`,
`tipo_entidad`, `subdir`). El scraper (`scrape(..., portal=)`) y `load_years(...,
portales=)` iteran sobre esa constante. Banca Pública se descarga a
`data/raw/banca_publica/{año}/...` y se registra en `raw.source_files` con ese prefijo, para
no chocar con los nombres de bancos privados (la columna es `UNIQUE`). Los parsers reciben
`tipo_entidad` como argumento y rechazan cualquier valor fuera de `TIPOS_ENTIDAD_CAPCOL`.
`_REFRESH_MARTS_SQL` usa `IN ('BANCO PRIVADO', 'BANCO PUBLICO')` y mapea
`inversion_publica`. Se agregó `_log_bancos_no_resueltos()`, que emite un WARNING si un
`banco_codigo` de staging CAPCOL no existe en `staging.banco_maestro` (p.ej. base
reconstruida sin haber corrido BCE). Uso: `python -m etl.pipeline all --portales publica`.

**Pendiente original, carril de `data-engineer` (Fase 1, alcance bajo)** — cambios de código, no de
esquema:
1. `etl/extract/scrape_superbancos.py` (o una copia paramétrica): apuntar a
   `CAPCOL_INSTITUCIONES_PUBLICAS_URL` (nueva constante en `etl/config.py`, mismo patrón
   que `CAPCOL_URL`/`BOLETIN_URL`) — el mismo código de navegación Playwright sirve tal
   cual (mismo plugin, mismos selectores `.entry.folder`/`.entry.file`,
   `a.first-breadcrumb`).
2. `etl/transform/parse_cartera.py::_parse_sheet()` y `parse_depositos.py`: **hoy
   hardcodean `"tipo_entidad": "BANCO PRIVADO"` para toda fila parseada** (`parse_cartera.py`
   línea ~80) — hay que parametrizar esto (ej. un argumento `tipo_entidad: str` en
   `parse_cartera_file()`/`parse_depositos_file()`, pasado por el caller según de qué
   sub-portal vino el archivo) en vez de inferirlo del dato. **Bug real evitado al
   investigar esto**: si alguien simplemente reapunta el scraper a la nueva URL sin tocar
   el parser, TODAS las filas de Banca Pública quedarían mal etiquetadas
   `tipo_entidad='BANCO PRIVADO'` en `staging.cartera`/`staging.depositos` — silenciosamente
   consistentes con el filtro `WHERE s.tipo_entidad = 'BANCO PRIVADO'` de
   `_REFRESH_MARTS_SQL` (punto 3 abajo), así que el bug NO fallaría ruidoso, produciría
   datos incorrectos en `marts.fact_saldo_cartera`/`fact_saldo_depositos` (bancos públicos
   contados como privados) sin ningún error visible.
3. `etl/load/load_postgres.py::_REFRESH_MARTS_SQL`: los `INSERT INTO
   marts.fact_saldo_cartera`/`fact_saldo_depositos` filtran hoy
   `WHERE s.tipo_entidad = 'BANCO PRIVADO'` — cambiar a
   `WHERE s.tipo_entidad IN ('BANCO PRIVADO', 'BANCO PUBLICO')` (o quitar el filtro y dejar
   que el `JOIN` a `dim_banco` sea la única fuente de verdad de qué entidades existen,
   decisión de `data-engineer`). Extender también el `CASE` de `tipo_credito →
   dim_segmento_credito.segmento` con `WHEN 'inversion_publica' THEN 'INVERSIÓN PÚBLICA'`
   (punto de arriba).
4. `etl/config.py::TIPO_CREDITO_KEYWORDS`: agregar `"inversion": "inversion_publica"` (el
   orden del diccionario importa para los `in` sucesivos — no colisiona con ninguna
   keyword existente).
5. Descargar el histórico 2021-2025 con el scraper actualizado, cargar, y verificar (mismos
   quality gates que cualquier carga de este proyecto): `staging.cartera`/`.depositos`
   cuenta = `marts.fact_saldo_cartera`/`fact_saldo_depositos` cuenta para las filas nuevas
   `tipo_entidad='BANCO PUBLICO'`; CDC no-op en una segunda corrida; 0 filas huérfanas por
   `banco_codigo` no resuelto contra `dim_banco` (ver riesgo de orden de carga arriba —
   recomendable agregar una función `_log_bancos_no_resueltos()` análoga a
   `_log_cantones_no_resueltos()` si `data-engineer` quiere el mismo nivel de
   observabilidad que ya existe para `dim_canton`, en vez de descubrir filas descartadas
   solo comparando conteos a mano).

## 2. BCE — Tasas de interés activas y pasivas (semanal) — 🔎 en investigación

Fuente: Banco Central del Ecuador, sección Estadísticas > Sector Monetario y Financiero >
Tasas de Interés (`https://contenido.bce.fin.ec/documentos/Estadisticas/SectorMonFin/TasasInteres/`).

**Corrección importante (2026-07-18)**: la URL de "tasas activas" que se tenía originalmente
(`tmp_desde_200801.zip`) era incorrecta. Se investigó a fondo y se confirmó que `tmp` en
realidad trae **tasas pasivas mensuales** (mismo `instrumento_captacion` que `tsp`, solo que
con grano mensual `fecha` en formato `YYYY-MM` en vez de `semana` `DD/MM/YYYY`). El usuario
corrigió la URL real de tasas activas semanales: **`tsa_desde_200801.zip`**. También existe
un cuarto archivo, `tma_desde_200801.zip` (tasas activas mensuales, 2.77GB descomprimido,
columnas aún más ricas: `destino_credito`, `destino_hipotecario`, `destino_consumo`,
`instrumentacion_credito`, `actividad_economica`, `numero_beneficiarios`).

**Convención de nombres del BCE, ahora completamente resuelta**: `t{s|m}{p|a}` = tasas +
(semanal|mensual) + (pasiva|activa):
| Archivo | Frecuencia | Tipo | Estado |
|---|---|---|---|
| `tsp_desde_200801.zip` | Semanal | Pasiva (depósitos) | ✅ en alcance |
| `tsa_desde_200801.zip` | Semanal | Activa (crédito) | ✅ en alcance |
| `tmp_desde_200801.zip` | Mensual | Pasiva (depósitos) | ❌ fuera de alcance (usuario solo quiere semanales) |
| `tma_desde_200801.zip` | Mensual | Activa (crédito) | ❌ fuera de alcance (usuario solo quiere semanales) |

**Decisión de alcance (explícita del usuario)**: solo se integran los dos archivos
**semanales** (`tsp` + `tsa`). Los mensuales (`tmp`/`tma`) quedan descartados del proyecto.

### 2.1 `tsp_desde_200801.zip` (tasas pasivas / captaciones)
- **URL**: `.../tsp_desde_200801.zip`
- **Acceso**: descarga directa (no requiere Playwright — es un link estático).
- **Tamaño real**: ZIP 71MB → CSV descomprimido **711MB**, 3,077,977 filas.
- **Formato**: CSV delimitado por `;`, decimales con coma (`2,6764265736999`).
- **Columnas** (confirmadas leyendo el archivo real):
  `semana;ruc;razon_social;sector_financiero;tipo_entidad;tipo_segmento;instrumento_captacion;provincia;canton;plazo;monto_total;numero_operaciones;tasa_pasiva_efectiva;tasa_nominal`
- **`semana`**: fecha en formato `DD/MM/YYYY` (weekly, desde 2008-01-03).
- **`sector_financiero`** (3 valores): `SECTOR FINANCIERO PRIVADO`, `SECTOR FINANCIERO PUBLICO`, `SECTOR FINANCIERO POPULAR Y SOLIDARIO`.
- **`tipo_entidad`** (6 valores, confirmado contando entidades distintas del archivo real
  sin filtrar): `BANCOS PRIVADOS` (37 entidades históricas), `BANCOS PUBLICOS` (7),
  `COOPERATIVAS DE AHORRO Y CREDITO` (**394** — la inmensa mayoría del universo, el
  sector "popular y solidario" ecuatoriano tiene cientos de cooperativas pequeñas),
  `MUTUALISTAS` (5), `SOCIEDAD FINANCIERA` (12), `ADMINISTRADORA DE TARJETAS DE CREDITO`
  (1). 456 entidades distintas en total.
  **Corrección (2026-07-19): NO se filtra por `tipo_entidad` en ninguna capa.** Una
  versión anterior de esta nota decía "filtrar a BANCOS PRIVADOS para alinear con el
  alcance del proyecto" y así se implementó — pero eso descartaba el dato **antes de que
  llegara a `raw.*`**, perdiéndolo para siempre (si el proyecto quería analizar el
  sistema completo más adelante, había que volver a descargar y reprocesar el ZIP
  original). Corregido: `raw.bce_tasas_pasivas`/`activas` capturan las 6 categorías tal
  cual; en `staging`/`marts`, los ~33 bancos privados siguen resueltos por el crosswalk
  curado (`banco_matching.py`, necesitan alinearse con CAPCOL/Boletín), y las ~420
  entidades restantes se auto-registran por RUC (`resolver_entidad_bce()`, sin curación
  manual — a esa escala es inviable y no aporta valor todavía, ya que no hay otra fuente
  con la que alinearlas). Ver `docs/linaje_datos.md` y `docs/gobernanza_datos.md`.
- **`razon_social`** y **`ruc`**: nombre e identificador fiscal de la entidad — candidato a llave de integración con `dim_banco` de CAPCOL (los nombres no coinciden literalmente: CAPCOL usa "BP PICHINCHA", BCE probablemente usa razón social completa tipo "BANCO PICHINCHA C.A." — falta confirmar el mapeo exacto).
- **`instrumento_captacion`**: tipo de depósito (`DEPÓSITOS A PLAZO`, `DEPÓSITOS DE AHORRO`, `FONDOS DE TARJETAHABIENTES`, etc.) — más fino que CAPCOL, revisar catálogo completo.
- **`plazo`**: buckets de rango de días con prefijo de letra ordinal (`a. MENOS DE 30 DIAS`, `b. 30 - 60 DIAS`, ... `g. MAS DE 360 DIAS`) — el prefijo de letra sirve para ordenar.
- **`monto_total`, `numero_operaciones`**: agregados de la semana.
- **`tasa_pasiva_efectiva`, `tasa_nominal`**: las tasas — **esto es lo que CAPCOL no tenía**.
- Pendiente: confirmar si `provincia`/`canton` permiten cruce geográfico con `dim_canton` (muestra `S/N`/`NACIONAL` en filas iniciales — puede ser que solo algunas filas tengan geografía real).

### 2.2 `tsa_desde_200801.zip` (tasas activas / colocaciones) — ✅ confirmado
- **URL correcta**: `.../tsa_desde_200801.zip` (corregida por el usuario; `tmp` NO era esta fuente — ver nota arriba).
- **Tamaño real**: ZIP 123MB → CSV descomprimido **1.75GB**, 7,757,194 filas totales
  (466 entidades distintas del sistema financiero completo — 37 bancos privados, 8
  bancos públicos, 402 cooperativas, 5 mutualistas, 12 sociedad financiera, 2
  administradoras de tarjetas). **Ya no se filtra**, ver nota en la sección de `tsp`
  arriba — `raw.bce_tasas_activas` captura las 7,757,194 filas tal cual.
- **Formato**: mismo patrón que tsp — CSV `;`, decimales con coma, `semana` en `DD/MM/YYYY` (semanal, confirmado, desde 2008-01-03).
- **Columnas** (confirmadas leyendo el archivo real):
  `semana;ruc;razon_social;sector_financiero;tipo_entidad;tipo_segmento;segmento_credito;provincia;canton;plazo;monto_total;numero_operaciones;tasa_activa_efectiva;tasa_nominal`
  — estructura paralela a tsp, con dos diferencias clave: `segmento_credito` en vez de
  `instrumento_captacion`, y `tasa_activa_efectiva` en vez de `tasa_pasiva_efectiva`.
- **`segmento_credito`** (26 valores en todo el archivo, confirmado con `pandas`
  filtrando por comillas correctamente — validado independientemente en dos lecturas
  distintas del mismo `tsa.zip`): COMERCIAL ORDINARIO, COMERCIAL PRIORITARIO
  CORPORATIVO/EMPRESARIAL/PYMES, CONSUMO, CONSUMO MINORISTA/ORDINARIO/PRIORITARIO,
  EDUCATIVO, EDUCATIVO SOCIAL, INMOBILIARIO, INVERSIÓN PÚBLICA, MICROCRÉDITO (6
  variantes: ACUMULACIÓN AMPLIADA/SIMPLE con y sin sufijo "(SE)", AGRÍCOLA Y GANADERO,
  MINORISTA con y sin "(SE)"), PRODUCTIVO - CORPORATIVO, PRODUCTIVO AGRÍCOLA Y
  GANADERO/EMPRESARIAL/PYMES, VIVIENDA, VIVIENDA DE INTERÉS PÚBLICO/SOCIAL — mucho más
  fino que el `tipo_credito` de CAPCOL (6 valores). Solo entre bancos privados aparecen
  22 de los 26 (faltan `INVERSIÓN PÚBLICA` y las 3 variantes "(SE)", propias de banca
  pública/cooperativas) — pero `dim_subsegmento_credito` (antes `dim_segmento_credito`,
  renombrada 2026-07-19) siempre se sembró con los 26 completos (decisión previa, ya
  correcta) y **`fact_colocaciones_cartera` (antes `fact_tasas_activas`, renombrada
  2026-07-19 mismo día) ahora también carga las filas de los 4 segmentos exclusivos de
  banca pública/cooperativas** (2026-07-19: ya no se filtra tipo_entidad en ningún punto
  del pipeline, ver nota arriba). El mapeo `segmento_credito` (BCE, 26 valores fino) →
  `tipo_credito` (CAPCOL, 6 valores grueso) que se necesitaba acá **ya está resuelto**:
  es la FK `dim_subsegmento_credito.segmento_id → dim_segmento_credito.segmento_id`
  poblada en `sql/16_dim_segmento_normativo.sql` (no era 1:1 trivial — ej. CAPCOL
  "comercial" ⊂ {COMERCIAL ORDINARIO, COMERCIAL PRIORITARIO *, PRODUCTIVO *} — el mapeo
  completo con su justificación está documentado ahí y en `docs/gobernanza_datos.md`).
- **`tipo_segmento`** (14 valores en tsp y tsa, idéntico universo en ambos, verificado
  leyendo los archivos completos): clasificación normativa de **tamaño/estructura de la
  ENTIDAD** — no confundir con `segmento_credito`, que clasifica el producto. Distinta
  por `tipo_entidad`: `BANCOS PRIVADOS` → `BANCO GRANDE`/`BANCO MEDIANO`/`BANCO PEQUEÑO`;
  `COOPERATIVAS DE AHORRO Y CREDITO` → `SEGMENTO 1`..`SEGMENTO 5`/`SIN SEGMENTO`
  (segmentación por activos totales de la Junta de Política y Regulación Financiera,
  JPRF-F-2023-074 — Segmento 1 > USD 80MM, bajando por umbrales hasta Segmento 5 =
  cajas/bancos/cajas comunales; seps.gob.ec); `MUTUALISTAS` → `SEGMENTO 1 MUTUALISTA` o
  `MUTUALISTAS`; `BANCOS PUBLICOS`/`SOCIEDAD FINANCIERA`/`ADMINISTRADORA DE TARJETAS DE
  CREDITO` → una sola categoría, igual a `tipo_entidad`. **Cambia en el tiempo por
  entidad** (verificado: una cooperativa real pasa de `SIN SEGMENTO` a `SEGMENTO 3` a
  `SEGMENTO 1` entre 2009 y 2023 según crece) — no es un atributo fijo del banco, es un
  atributo de `(fecha, banco)`. En un puñado de casos (~1 en un millón de filas) no es
  estable dentro de la misma `(fecha, banco_codigo)` entre provincias/instrumentos —
  posible artefacto de una reclasificación a mitad de semana en la fuente; se resuelve
  por la fila de mayor `monto_total`, mismo criterio que ya se usa para ponderar tasas.
  Se preservaba en `raw.*` desde el inicio pero se descartaba antes de `staging` sin
  examinar su contenido (detectado 2026-07-25) — ver `marts.dim_segmento_entidad`
  (`sql/19_dim_segmento_entidad.sql`) y `docs/gobernanza_datos.md`.
- **`tipo_entidad`**: mismos 7 valores que tsp (agrega `SECTOR FINANCIERO POPULAR Y
  SOLIDARIO` como categoría propia, a diferencia de tsp que no la listó en la muestra
  previa — revisar si es la misma taxonomía de 6-7 valores en ambos archivos).
- **`plazo`**: mismos buckets con prefijo ordinal que tsp.

### 2.3 Tasas máximas y referenciales por segmento (`TasasHistorico.htm`) — ✅ cargado (Paso 4)
- **URL índice**: `https://contenido.bce.fin.ec/documentos/Estadisticas/SectorMonFin/TasasInteres/TasasHistorico.htm`
- **Acceso**: HTML estático, descarga directa (`urllib`, sin Playwright). Patrón de URL
  100% predecible: `TasasVigentes{MM}{YYYY}.htm`. No todos los meses existen (404 en
  huecos, ej. meses muy antiguos o el mes corriente aún no publicado) — se tolera y se
  sigue con el resto (`etl/extract/download_tasas_historicas.py`).
- **Estructura real de cada página** (confirmado leyendo `TasasVigentes062026.htm` con
  `pandas.read_html`, `lxml`), **corrigiendo el conteo inicial de la investigación**:
  1. **TASAS DE INTERÉS ACTIVAS MÁXIMAS VIGENTES** — **13 segmentos** (no 16): Productivo
     Corporativo/Empresarial/PYMES, Consumo, Educativo, Educativo Social, Vivienda de
     Interés Público/Social, Inmobiliario, Microcrédito Minorista/Acumulación
     Simple/Acumulación Ampliada, Inversión Pública.
  2. **TASAS DE INTERÉS ACTIVAS EFECTIVAS REFERENCIALES VIGENTES** — mismos 13 segmentos.
  3. **TASAS DE INTERÉS PASIVAS EFECTIVAS PROMEDIO POR INSTRUMENTO** — **5 categorías**
     (no 3): Depósitos a Plazo, Depósitos de Ahorro, Depósitos Monetarios (agregado, sin
     distinguir generan/no-generan intereses — valor nuevo en `dim_categoria_deposito`),
     Depósitos de Tarjetahabientes (armonizado a `FONDOS DE TARJETAHABIENTES`),
     Operaciones de Reporto.
  4. **TASAS DE INTERÉS PASIVAS EFECTIVAS REFERENCIALES POR PLAZO** — **6 buckets** (no
     3): 30-60, 61-90, 91-120, 121-180, 181-360, 361-y-más días — todos coinciden
     exactamente con rangos ya existentes en `dim_plazo` (de `tsp`/CAPCOL), sin crear
     filas nuevas.
  5. **OTRAS TASAS REFERENCIALES** — **4 métricas** (no 2): Tasa Pasiva Referencial (TPR),
     Tasa Activa Referencial (TAR), Tasa Legal, Tasa Máxima Convencional. **Valores reales
     verificados para junio 2026: TPR=5.29, TAR=6.85, Legal=6.85, Máxima Convencional=7.99**
     (corrige una nota de investigación previa que decía "TPR 6,85/TAR 7,99" — esos eran en
     realidad TAR/Máxima Convencional, no TPR/TAR).
  - **Grano: mensual, a nivel de sistema financiero completo** (no por banco).
  - **Bug de parseo encontrado y corregido**: `pandas.read_html` usa `thousands=','` por
    defecto **siempre**, incluso pasando `decimal=","` explícito — corrompe `7,99` →
    `799` silenciosamente. Fix: pasar también `thousands="."` para desactivar ese default.
  - **Segunda corrección**: en qué `<table>` física cae cada sección **no es estable a
    través de los años** — para un subconjunto de meses las 5 secciones no se reparten
    2+3 entre las 2 tablas como en 2026, sino que aparecen mezcladas. El parser final
    (`etl/transform/parse_tasas_historicas.py`) concatena las filas de todas las tablas y
    rastrea la sección vigente fila por fila (por texto de encabezado), sin asumir qué
    tabla contiene qué sección.
  - Único alias real de nombre necesario: "Productivo Corporativo" (esta fuente) →
    "PRODUCTIVO - CORPORATIVO" (`dim_subsegmento_credito`, con guion).
- **Cobertura cargada**: 51 meses (2022-04 a 2026-06); páginas anteriores a 2022-04 usan
  un layout HTML más antiguo no soportado por este parser (se omiten con warning, no
  abortan el resto del batch). Dentro del rango cargado, **4 meses consecutivos
  (2022-04 a 2022-07)** no traen la sección de segmento de crédito en absoluto —
  coincide con el período de las resoluciones JPRF-F-2022-031/053 que revisaron la
  metodología, gap real de la fuente en ese período de transición, no un error del parser.
- Esto da las tasas **máximas y referenciales regulatorias** — el techo normativo y el
  promedio de referencia contra el cual comparar las tasas efectivas reales de
  `tsp`/`tsa` banco por banco.

### 2.4 Mapeo `razon_social`/`ruc` (BCE) ↔ `banco` (CAPCOL/`marts.dim_banco`) — investigado
Se comparó la lista real de `razon_social` de BCE (filtrado `BANCOS PRIVADOS`, 37 valores,
histórico desde 2008) contra los 28 bancos ya cargados en `marts.dim_banco` (poblado desde
CAPCOL, 2021-2025). Confirma que **se necesita un crosswalk explícito, no un join por
texto**:
- BCE usa razón social legal completa: `BANCO PICHINCHA C.A.`, `BANCO DE GUAYAQUIL S.A.`,
  `BANCO DE LA PRODUCCIÓN PRODUBANCO S.A.`, `BANCO GENERAL RUMIÑAHUI S.A.`.
- CAPCOL usa códigos cortos con prefijo `BP `: `BP PICHINCHA`, `BP GUAYAQUIL`, `BP
  PRODUBANCO`, `BP GENERAL RUMIÑAHUI` — pero **no consistentemente**: unos pocos bancos en
  `dim_banco` están con el nombre legal completo en vez del código corto (`BANCO AMIBANK
  S.A.`, `BANCO ATLÁNTIDA S.A.`), rompiendo el patrón "BP + código" que sigue el resto.
- BCE trae ~9 entidades que no aparecen en `dim_banco` porque son bancos que ya no operan o
  se fusionaron antes de 2021 (`COFIEC`, `LLOYDS BANK`, `SUDAMERICANO`, `TERRITORIAL`,
  `UNIBANCO S.A.`, `M.M. JARAMILLO ARTEAGA`) — el crosswalk debe soportar entidades
  "solo-BCE" sin intentar forzarlas a un banco de `dim_banco`.
- **`ruc` es el candidato correcto de llave estable** (identificador fiscal), pero falta
  confirmar que CAPCOL en algún punto expone el RUC (no lo hace en los archivos de
  cartera/depósitos actuales) — si no, el crosswalk deberá construirse a mano
  (`banco_capcol` ↔ `razon_social_bce` ↔ `ruc_bce`), documentado como tabla de referencia,
  no derivado automáticamente.

### 🐛 Bug encontrado en el pipeline ya existente (no relacionado a BCE, pero descubierto durante esta comparación)
Al listar `marts.dim_banco` se encontró que **el mismo banco aparece dividido en dos filas**
por un cambio de nombre a mitad del histórico en la fuente CAPCOL — esto ya afecta el
dashboard de Power BI shippeado (rompe continuidad de series de tiempo/YoY para estos
bancos):
- `BP COMERCIAL DE MANABI` (filas 2021-01 a 2022-12, USD 856.5M acumulado) y `BP BANCO
  COMERCIAL DE MANABI` (filas 2023-01 a 2025-12, USD 1,514.5M acumulado) — mismo banco,
  rangos de fecha sin solape, confirma que es un rename de la fuente, no dos entidades.
- `BANCO AMIBANK S.A.` (2023-01 a 2024-12) y `BANCO AMIBANK S.A., EN LIQUIDACION`
  (2025-01 a 2025-12) — mismo caso, el banco entró en liquidación y CAPCOL cambió el
  nombre reportado.
- **Impacto**: cualquier medida `Variacion ... YoY`/`MoM` o "Market Share" para estos 2
  bancos está subestimada o rota en los períodos de transición, porque Power BI los trata
  como entidades distintas.
- **Fix pendiente** (fuera del alcance de esta sesión de investigación BCE, pero para
  hacer pronto): agregar una tabla de alias `dim_banco_alias` o normalizar en el parser de
  CAPCOL antes de cargar a `staging`, colapsando estos casos a un único `banco_id`. Este
  mismo mecanismo de alias es el que de todas formas hay que construir para el crosswalk
  CAPCOL↔BCE, así que conviene resolverlos juntos en el diseño de arquitectura.

### Preguntas abiertas antes de diseñar el modelo BCE
1. ~~¿`tmp` es semanal o mensual? ¿trae tasas activas?~~ **Resuelto**: era pasivas
   mensuales, fuera de alcance. La fuente real de activas semanales es `tsa`.
2. Confirmar si CAPCOL alguna vez expone RUC (no visto hasta ahora) para decidir si el
   crosswalk `dim_banco` puede automatizarse parcialmente o debe ser 100% manual.
3. ¿`TasasHistorico.htm` es scrapeable de forma simple o necesita Playwright? — siguiente paso.
4. Definir mapeo `segmento_credito` (BCE, 26 valores) → `tipo_credito` (CAPCOL, 6 valores) para el catálogo conformado de producto de crédito.
5. Volumen ya confirmado tras filtro `BANCOS PRIVADOS`: tsp=781,813 filas, tsa=2,236,663 filas (semanal, 2008-2026). Con ~3M filas combinadas, conviene `pandas` con `chunksize` o `DuckDB` para el parser en vez de cargar todo en memoria de una vez.

## 3. Superbancos — Boletín Financiero Mensual (Balance y PyG) — ✅ estructura confirmada

- **URL portal**: `https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos/`
  — **confirmado: mismo plugin OneDrive/SharePoint que CAPCOL**, requiere Playwright.
  Estructura de carpetas: `Año {YYYY}` (2009-2026) → archivos directamente dentro (no
  hay subcarpeta de mes), nombrados `{N}. BOLETIN BANCOS {MES} {YYYY}.zip` (ej. `6.
  BOLETÍN BANCOS JUNIO 2026.zip`). También existe una subcarpeta `Bancos Privados`
  dentro de cada año, no explorada todavía (podría tener formato alternativo o
  histórico previo a que existieran los boletines mensuales individuales).
- **Archivo real descargado y verificado**: `6. BOLETÍN BANCOS JUNIO 2026.zip` (738KB) →
  `FINANCIERO MENSUAL BANCA PRIVADA 2026_06.xlsx` (738KB).
- **⚠️ El workbook tiene 12 hojas, no solo 2** — mucho más rico de lo descrito
  originalmente: `BALANCE`, `PYG`, `BALANCE %`, `EPyG %`, `CONSCOND`, `RK`, `Gráficos
  RK`, `COMPOS CART`, `COMPOS CART %`, `MET`, `INDICADORES`, `REP GERENCIAL`. Solo
  `BALANCE` y `PYG` fueron inspeccionadas a fondo (ver abajo); las demás son candidatas
  a integrar más adelante — **`RK` e `INDICADORES` en particular son hallazgos de alto
  valor** (ver nota al final).

### 3.1 Hoja `BALANCE` (1399 filas x 35 columnas)
- **Encabezado confirma explícitamente "(en miles de dólares)"** — el usuario pidió
  validar esto, no asumirlo: **confirmado, SÍ están en miles de USD**, hay que
  multiplicar x1000 al cargar si se quiere comparar contra los saldos en USD de CAPCOL
  (que no están en miles).
- **Fila 8 = encabezado real**: `CÓDIGO`, `CUENTA`, luego una columna por banco.
- **Formato ancho confirmado**: columnas = bancos individuales, **intercaladas con
  columnas de agregado/subtotal** que hay que excluir al cargar (no son bancos reales):
  `BANCOS PRIVADOS GRANDES`, `BANCOS PRIVADOS MEDIANOS`, `BANCOS PRIVADOS PEQUEÑOS`,
  `TOTAL BANCOS PRIVADOS`, `BANCOS PRIVADOS COMERCIALES`, `BANCOS PRIVADOS CONSUMO`,
  `BANCOS PRIVADOS VIVIENDA`, `BANCOS PRIVADOS MICROCRÉDITO`, `BANCA MÚLTIPLE`.
  **Se necesita una lista explícita de estos 9 nombres de columna "no-banco" para
  filtrarlos** (no hay un patrón textual simple que los distinga de un nombre de banco
  real, hay que mantenerlos como lista hardcodeada).
- **¡Excelente noticia para el catálogo conformado!** Los 23 bancos individuales en esta
  hoja usan el **mismo formato `BP <NOMBRE>` que CAPCOL**, y en varios casos coinciden
  literalmente: `BP GUAYAQUIL`, `BP PICHINCHA`, `BP PRODUBANCO`, `BP AUSTRO`, `BP
  BOLIVARIANO`, `BP GENERAL RUMIÑAHUI`, etc. — incluso las excepciones "no-BP" de
  CAPCOL coinciden exactamente: `BANCO ATLÁNTIDA S.A.` aparece igual en ambas fuentes.
  Esto hace el crosswalk **Boletín↔CAPCOL mucho más simple que BCE↔CAPCOL** (probable
  normalización de espacios en blanco nada más, ej. `'BP BANCO  DESARROLLO DE LOS
  PUEBLOS  S.A., CODESARROLLO'` con doble espacio vs. el `'BP BANCO DESARROLLO DE LOS
  PUEBLOS S.A., CODESARROLLO'` de CAPCOL).
- **Plan de cuentas jerárquico** (Catálogo Único de Cuentas de la Superintendencia):
  código de 2 dígitos (`11` FONDOS DISPONIBLES) → 4 dígitos (`1101` Caja) → 6 dígitos
  (`110105` Efectivo). **Filas de encabezado de sección** (`ACTIVO`, y presumiblemente
  `PASIVO`/`PATRIMONIO` más abajo) tienen `CUENTA` con texto pero `CÓDIGO` vacío — hay
  que detectarlas y no tratarlas como cuenta real, o usarlas para dar contexto
  jerárquico (sección balance) a las cuentas que le siguen.
- Esto es un plan de cuentas **estándar del sistema financiero ecuatoriano** (no
  específico de este boletín) — el mismo catálogo de cuentas se usa presumiblemente en
  reportes de otras instituciones reguladas por la Superintendencia (cooperativas,
  mutualistas), relevante para la meta explícita del usuario de "reutilizable para
  distintas estructuras que vamos a armar en función a diferentes reportes de bancos".

### 3.2 Hoja `PYG` (143 filas x 36 columnas)
- Misma estructura ancha que `BALANCE`: fila 8 encabezado, `CÓDIGO`/`CUENTA` + columnas
  de banco + las mismas 9 columnas de agregado. También confirma "(en miles de
  dólares)" en el encabezado.
- Plan de cuentas de resultados: código `5` INGRESOS → `51` INTERESES Y DESCUENTOS
  GANADOS → niveles más finos debajo (mismo patrón jerárquico que BALANCE).

### 3.3 Hallazgo de alto valor: hojas `RK` e `INDICADORES` (no pedidas originalmente, pero muy relevantes)
- **`RK`** (Ranking, 170 filas x 16 columnas): Superbancos **ya calcula el ranking/market
  share por banco** para las principales cuentas del balance, con comparación mes
  anterior vs. mes actual en USD y % — ej. sección `ACTIVOS`: filas = bancos, columnas
  `{Mes-1} (USD)`, `{Mes-1} (%)`, `{Mes} (USD)`, `{Mes} (%)`. Probablemente tiene
  secciones similares para `PASIVOS` (depósitos) y `PATRIMONIO` más abajo en la misma
  hoja (no confirmado todavía, pendiente de revisar filas >10). Esto es un **cruce de
  validación directo** contra los `Market Share`/`HHI` que ya calculamos en el modelo
  Power BI de CAPCOL.

  **Pregunta resuelta 2026-08-30** (no vía la hoja `RK` en sí, sino comparando
  directamente los agregados de ambas fuentes en Postgres): sí reconcilian, con una
  diferencia despreciable en la gran mayoría del histórico — CAPCOL cartera agregada
  (`fact_saldo_cartera`) vs. cartera bruta reconstruida del Boletín (`14 − 1499`,
  `marts.vw_cartera_bruta`) da una diferencia % mediana de ~0% en 1.559 combinaciones
  banco × fecha, 96,92% dentro de ±2%, con 4 bancos (AMIBANK, ATLANTIDA, PACIFICO, FINCA)
  desviándose 2-6% en ventanas de fecha acotadas y no investigadas a fondo. Para
  depósitos la reconciliación es más floja (mediana −0,7376%, CAPCOL siempre por debajo)
  por un hueco de alcance real y entendido: `dim_categoria_deposito` no cubre 5
  sub-cuentas nivel-6 de `21` (cheques certificados/emergencia, otros depósitos, 2
  cuentas institucionales de nicho), que explican ~48% del gap agregado. Registro
  completo con metodología, números exactos y consulta SQL: `docs/metricas_financieras.md`
  (sección "Reconciliación cruzada CAPCOL vs. BALANCE — cartera bruta"),
  `docs/glosario_cuentas.md` §2-3, y `docs/gobernanza_datos.md` (tabla "Huecos de
  gobernanza conocidos", filas de los 4 bancos outlier y del hueco de `dim_categoria_deposito`).
- **`INDICADORES`** (80 filas x 35 columnas): indicadores financieros regulatorios
  estilo CAMEL por banco — confirmado ver `SUFICIENCIA PATRIMONIAL`, `ESTRUCTURA Y
  CALIDAD DE ACTIVOS` como secciones, con métricas como `(PATRIMONIO + RESULTADOS) /
  ACTIVOS INMOVILIZADOS NETOS`, `ACTIVOS IMPRODUCTIVOS NETOS / TOTAL ACTIVOS`.
  Presumiblemente cubre también rentabilidad (ROE/ROA), liquidez y morosidad más abajo
  en la hoja (no confirmado, pendiente). **Esto es exactamente el tipo de dato que
  faltaba para el análisis de "oportunidades de negocio"** que se hizo antes en el
  dashboard HTML (salud financiera real por banco, no solo saldos) — vale la pena
  integrarlo cuando se construya el parser, no solo BALANCE/PYG.
- Las hojas `BALANCE %`, `EPyG %`, `COMPOS CART`, `COMPOS CART %` parecen ser versiones
  porcentuales/derivadas de BALANCE y PYG (no inspeccionadas a fondo) — probablemente no
  hace falta cargarlas si se recalculan en Power BI desde los valores absolutos, pero
  `COMPOS CART` (composición de cartera) podría dar una vista de cartera consistente con
  CAPCOL desde la óptica contable — a evaluar en el diseño de arquitectura.

## 4. SEPS — Cooperativas de Ahorro y Crédito + Mutualistas de Vivienda — ✅ **implementada y cargada 2021-2025 (2026-09-30)**

### 4.0 Revisión con archivos reales 2025 (2026-09-29) — **reemplaza 4.1-4.4 donde se contradicen**

> **Implementado 2026-09-30.** Las subsecciones 4.1-4.6 quedan como registro histórico del
> primer diseño; **este 4.0 es lo vigente**. Código: `etl/extract/download_seps.py`,
> `etl/transform/parse_seps.py`, `etl/pipeline.py::load_seps`. Linaje campo a campo en
> `docs/linaje_datos.md` sección 7. Variaciones de formato 2021-2025 absorbidas (verificadas
> descargando los 15 archivos): en 2021 el ZIP de cartera trae dos juegos (`abr_2021` =
> ene-abr con la segmentación previa a la reforma de mayo 2021, y `dic_2021` = may-dic);
> en 2023 el archivo de S1 se llama `_SG1`; el EEFF 2021 usa `;`, encabezados con `_` y
> BOM, y el decimal pasa de `.` a `,` en 2025. La partición semestral de S1 solo ocurre en
> 2025: en 2021-2024 S1 cabía en una hoja (1,03 M filas en 2024).
>
> **Resultado de la carga 2021-01 a 2025-12** (base nativa viva, 2026-09-30):
>
> | Tabla | Filas SEPS | Entidades |
> |---|---|---|
> | `fact_saldo_cartera` | 805.470 (780.315 cooperativas, 19.351 mutualistas, 5.804 segundo piso) | 221 |
> | `fact_saldo_depositos` | 334.768 | 221 |
> | `fact_balance` | 2.699.804 | 220 |
> | `fact_pyg` | 898.998 | 220 |
>
> Verificado: staging = marts en filas y en saldo (1.095.187.816.368,07 USD de cartera
> acumulada), 0 `canton_id` NULL, 1 cantón nuevo `AUTO_INGRESADO` (ALFREDO BAQUERIZO
> MORENO, Guayas), 2 entidades nuevas en `dim_banco` (CONAFIPS y FINANCOOP, `ENTIDAD DE
> SEGUNDO PISO`). Las filas de bancos de `fact_saldo_cartera`, `fact_saldo_depositos` y
> `fact_balance` no cambiaron (hash idéntico a la línea base previa a la carga). La segunda
> corrida saltó los 15 archivos y no actualizó ninguna fila (CDC sin cambios).
>
> **Conciliación por entidad × mes contra EEFF, dentro de `marts`:**
>
> | Año | Depósitos vs. cuenta 21: mediana / ±0,5% | Cartera vs. 14 − 1499: mediana / ±0,5% / ±5% | Cartera, dif. agregada |
> |---|---|---|---|
> | 2021 | 0,0000% / 99,3% | 0,0000% / 93,7% / 98,0% | −0,38% |
> | 2022 | 0,0000% / 99,6% | 0,0000% / 94,0% / 97,6% | −0,36% |
> | 2023 | 0,0000% / 99,0% | 0,0000% / 92,6% / 97,9% | −0,12% |
> | 2024 | 0,0000% / 99,6% | 0,0000% / 92,4% / 96,8% | +0,60% |
> | 2025 | 0,0000% / 99,8% | 0,0000% / 92,3% / 96,7% | +1,32% |
>
> Entidades con desvío mediano de cartera mayor a 5% en los 60 meses, pendientes de
> investigar antes de publicarlas en un benchmark: Mutualista Pichincha (+44,5%),
> Mutualista Azuay (+34,0%), COAC Juventud Ecuatoriana Progresista (−8,1%), COAC Policía
> Nacional (−7,0%).
>
> **Mutualistas — explicado (2026-10-01).** Las dos mutualistas venden cartera de vivienda
> de interés social y público a un fideicomiso (cuenta `1619` "cuentas por cobrar por
> cartera de VIS/VIP vendida al fideicomiso") y siguen administrándola. Esa cartera sale
> de la cuenta 14 y se registra en cuentas de orden acreedoras, pero `Reporte_colocaciones`
> **la sigue reportando** como cartera de la entidad, marcada igual que la propia
> (`CONCEDIDA POR LA ENTIDAD` / `ORIGINAL`), así que no se puede separar por cantón.
> Prueba en los 60 meses: al sumar a `14 − 1499` la cartera en administración
> (`740170` VIS/VIP en Azuay, `740175` inmobiliario en Pichincha), la diferencia mediana
> pasa de +44,5% a +1,0% en Pichincha y de +34,0% a −1,95% en Azuay. Es propio de las
> mutualistas: las cooperativas con cuentas `7401xx` en administración no la incluyen en
> el reporte (ya concilian a 0% sin sumarla). **Decisión: no se corrige el dato.**
> `fact_saldo_cartera` de una mutualista significa "cartera originada y administrada", no
> "cartera en balance". Para comparar contra contabilidad, en mutualistas usar
> `14 − 1499 + 7401{70,75}`.
>
> **JEP y Policía Nacional — explicado con evidencia agregada (2026-10-01): tarjetas de
> crédito.** Todo el faltante está en **consumo** (los demás segmentos cuadran casi al
> centavo), principalmente en "por vencer". Ejemplos: JEP dic-2025, 1.051,0 M en el
> reporte vs. 1.257,8 M en EEFF; Policía dic-2021, 748,7 vs. 836,1 M. La base mensual SEPS
> rotula su cartera "cuenta 14, excepto tarjetas de crédito", y la SEPS publica aparte una
> base de "Consumos de tarjetas de crédito". En el EEFF la cartera de tarjetas está dentro
> de `1402`, sin subcuenta propia. Evidencia:
> - Las 212 entidades sin `210145 FONDOS DE TARJETAHABIENTES` tienen diferencia mediana de
>   consumo de **0,000%**. Las 11 emisoras tienen **−3,6%**, y las mayores diferencias son
>   justo JEP (−13,3%), OSCUS (−10,0%) y Policía (−8,4%).
> - Faltante agregado de consumo de las emisoras: ~230-270 M USD por mes. Cartera total de
>   tarjetas SEPS (`YYYY-Tarjetas-MEN.zip`, sin RUC, total del sistema): ~330-350 M. La
>   razón se mantiene estable en 0,70-0,80 durante 23 meses (2024-2025). No es 1 porque la
>   base de tarjetas cubre a todas las emisoras SEPS y porque Mutualista Pichincha, también
>   emisora, tiene el consumo inflado por el efecto VIP. Dic-2025 da 1,04, pero la base de
>   tarjetas cae de 323 a 254 M ese mes, lo que sugiere un corte incompleto.
>
> No se puede confirmar por entidad: la base de tarjetas no trae RUC y el EEFF no separa
> tarjetas dentro de 1402. **Decisión: no se corrige.** Para las emisoras,
> `fact_saldo_cartera` segmento CONSUMO **excluye tarjetas de crédito**, mientras que la
> cartera de consumo de los bancos (CAPCOL) sí las incluye. Verificado con BP Diners, cuya
> cartera es casi toda de tarjetas: CAPCOL vs. Boletín `14 − 1499` da mediana 0,00% en 66
> meses. Al comparar consumo entre
> cooperativas emisoras y bancos, o contra el EEFF, hay que tenerlo presente. `OPERACIONES CONTINGENTES` excluidas por año: 2023 1,4 M, 2024 30,3 M,
> 2025 9,7 M USD.

Descargados y perfilados en streaming (sin descomprimir a disco) desde
`estadisticas.seps.gob.ec/index.php/estadisticas-sfps/`. Para cada tema, la SEPS publica
**dos familias de archivos distintas**. El diseño original mezclaba las propiedades de ambas.

| Tema | Archivo | Formato | ¿Trae entidad (RUC)? | Grano | Filas 2025 |
|---|---|---|---|---|---|
| Depósitos — *Reportes* | `2025-CAP.zip` → `Boletin_captaciones_Dic25_{S1,S2,S3,Mut}.xlsm`, hoja `Base_captaciones` | xlsm (~14 MB zip) | **Sí** (`RUC`, `RAZON SOCIAL`) | fecha × entidad × cantón × tipo depósito × estado operación | 120.045 |
| Cartera — *Reportes* | `2025-COL.zip` → `Reporte_colocaciones_dic_2025_{S1,S2,S3,MUT}.xlsm`, hoja `Base_colocaciones` | xlsm (~237 MB zip) | **Sí** | fecha × entidad × cantón × subtipo × origen × estado × clase × actividad | 1.302.688 |
| Depósitos — *Bases de datos* | `2025-CAP-Men.zip` → `.txt` TSV (1,3 GB) | TSV | **No** (solo `SEGMENTO`) | + parroquia, sexo, edad, instrucción, rango saldo, banda de plazo | 5.749.334 |
| Cartera — *Bases de datos* ("Operaciones de crédito vigentes") | `2025-COL-MEN.zip` → `.txt` TSV (**11,3 GB**) | TSV | **No** | + parroquia, CIIU, destino, demografía | 16.426.673 |
| Estados financieros | `2025_EEFF-Men.zip` → `.txt` TSV (418 MB) | TSV | **Sí** (`RUC`, `RAZON SOCIAL`) | fecha × entidad × cuenta (1, 2, 4 y 6 dígitos) | 2.954.291 |

Los ZIP usan Deflate64 y `zipfile` de Python no los abre (`NotImplementedError`). Hay que
usar `unzip -p` (o `7z`) como subproceso. Los números vienen con coma decimal y sin
separador de miles.

**1. La cartera "colocaciones" de la SEPS SÍ son saldos y SÍ conforma con
`fact_saldo_cartera`.** Esto corrige la sección 4.2, que concluía lo contrario. El archivo se
llama `Reporte_colocaciones`/`COL`, pero `Base_colocaciones` trae `CARTERA POR VENCER`,
`CARTERA QUE NO DEVENGA INTERESES`, `CARTERA VENCIDA`, `CARTERA TOTAL`, `NUMERO
OPERACIONES` y `NUMERO SUJETOS CREDITO`. Es la misma foto de stock por estado de morosidad
que CAPCOL. El análisis anterior partió de `Base_vcredito`, del reporte *VOL*
("Operaciones concedidas"), que es volumen de desembolsos: otro proceso de negocio.
**`fact_volumen_cartera` deja de ser necesaria** para tener saldos por cantón. Queda solo
como opción futura si se quiere el flujo de desembolsos.

**2. Conciliación contra EEFF (por RUC × mes, 2025):**

| Cruce | Pares comparados | Mediana dif. | Dentro de ±0,5% | Dentro de ±1% |
|---|---|---|---|---|
| `Base_captaciones.SALDO` vs. EEFF cuenta `21` (= 2101+2103+2104+2105) | 2.458 | 0,0000% | 99,8% | 99,9% |
| `Base_colocaciones.CARTERA TOTAL` vs. EEFF `14 − 1499` | 2.219 | 0,0000% | 94,8% | 95,5% |

Depósitos concilia casi exacto. Eso también confirma que sumar los 3 valores de
`ESTADO OPERACIÓN` (NUEVA / VIGENTE / RENOVADA) **no** cuenta dos veces: son una partición
del stock, no un filtro. En cartera, los pocos RUC fuera de ±5% se concentran en unas pocas
entidades (p.ej. `0190006247001`, entre 80% y 94% por encima de EEFF en jul-dic).

**3. ✅ Resuelto (2026-09-30): la cartera de S1 está partida por semestre dentro del mismo `.xlsm`.**
Desde 2025, `Reporte_colocaciones_dic_2025_S1.xlsm` trae **dos** hojas base ocultas:
`Base_colocaciones` (jul-dic, 585.362 filas) y `Base_colocacionesISEM` (ene-jun, 571.744
filas). Tienen las mismas 18 columnas, pero en `ISEM` la columna `FECHA DE CORTE` viene como
**serial de Excel** (`int`, 45688 = 2025-01-31, …, 45838 = 2025-06-30), no como fecha. El
parser debe leer todas las hojas `Base_colocaciones*`, excluir `Base_para_actual` (hoja
auxiliar de la portada, con una fecha fija 42916 = 2017-06-30 que no es un corte real) y
convertir el serial a fecha. Con ambas hojas, el año queda completo: 206-211 RUC por mes, y
la conciliación por RUC × mes contra EEFF `14 − 1499` da mediana 0,0000% (92,3% de los
2.478 pares dentro de ±0,5%, 96,7% dentro de ±5%). El exceso agregado de +1,2% a +1,4% por
mes se concentra en pocas entidades: `0190006247001` (mediana +76,5%), `1790075494001`
(+73%), `1790451801001` (+19%). Quedan por revisar antes de publicarlas en un benchmark.
Pendiente: confirmar la partición en 2021-2024, donde S1 era más chico y probablemente
cabía en una sola hoja.

<details><summary>Texto original del hallazgo (2026-09-29), antes de encontrar la hoja ISEM</summary>

**3. ⚠️ Hueco real: el `.xlsm` de cartera del Segmento 1 solo trae julio-diciembre.**
`Reporte_colocaciones_dic_2025_S1.xlsm` tiene 585.362 filas para 6 meses (45-46
entidades). El año completo serían ~1,17 M filas, más que el límite de Excel (1.048.576).
Hipótesis fuerte: la SEPS truncó el archivo. S2, S3 y Mut sí traen los 12 meses. En
consecuencia, en ene-jun 2025 el reporte cubre 161 de 210 RUC: ~4,4 mil M USD frente a
~19,2 mil M en EEFF. **Opciones, pendientes de decisión:**
- (a) Aceptar el hueco de S1 en ene-jun y exponerlo como cobertura parcial.
- (b) Buscar si la SEPS publica un corte de junio (u otro archivo) que traiga los meses
  faltantes.
- (c) Para S1 en ene-jun, usar la base TSV (sin entidad) solo en vistas agregadas por
  segmento × cantón.

Antes de cargar el histórico hay que revisar si 2021-2024 tienen el mismo truncamiento.

</details>

**4. Las bases TSV (CAP-Men y COL-MEN) no sirven para benchmark por entidad**, porque no
traen RUC ni razón social. Sí sirven para una vista del *sistema cooperativo* por segmento ×
cantón × parroquia, con demografía. CAP-Men 2025 trae solo 10 cortes (faltan enero y
febrero). Quedan fuera del alcance de v1.

**5. Identidad: 209 de 211 RUC ya existen en `marts.dim_banco`.** Son 205 `COOPERATIVA` y 4
`MUTUALISTA`, auto-registradas por BCE. Verificado contra la base nativa viva (uptime
desde 2026-09-26). Faltan solo dos entidades de segundo piso:
- `CORPORACION NACIONAL DE FINANZAS POPULARES Y SOLIDARIAS` (CONAFIPS, `1768168480001`).
- `CAJA CENTRAL FINANCOOP` (`1791708040001`).

Su `tipo_entidad` no calzaba en el `CHECK` de `dim_banco` (`sql/07`). **Decidido
(2026-09-30):** nuevo valor `'ENTIDAD DE SEGUNDO PISO'`, en `sql/29_dim_banco_tipo_segundo_piso.sql`,
ya aplicado a la base viva. Se registran como filas propias, no se fuerzan como
`COOPERATIVA`. La
resolución por RUC (`BCE_<ruc>`, sección 4.3) queda confirmada: no hace falta ningún
crosswalk manual.

**6. Estados financieros → `marts.fact_balance`/`fact_pyg` tal cual.** Mismo grano que el
Boletín de Superbancos (fecha × entidad × cuenta), pero en USD completos, no en miles.
También usa el mismo Catálogo Único de Cuentas:
- De 1.214 códigos SEPS, 1.063 ya existen en `marts.dim_cuenta_contable`. De esos, 831
  tienen descripción idéntica y el resto difiere en redacción menor (p.ej.
  "interfinancieras" vs. "interbancarias").
- Las cuentas que usan las vistas (`1`, `14`, `1499`, `21`, `2101`-`2105`, `4`, `5`) son
  idénticas. Por eso `vw_cartera_bruta`, `vw_depositos_corto_plazo` y el resto funcionan sin
  cambios para cooperativas.
- Los 151 códigos que solo existen en SEPS (incluidas las cuentas de orden `6` y `7`) entran
  por el two-tier que ya tiene `dim_cuenta_contable` (`AUTO_INGRESADO`, `sql/25`).
- `1499` viene con signo negativo, igual que en Superbancos.

**7. Vocabulario a mapear** (valores reales contados):
- `TIPO DE DEPOSITO` (4 valores): `DEPOSITOS A PLAZO`, `DEPOSITOS RESTRINGIDOS` y
  `DEPOSITOS DE GARANTIA` ya existen. `DEPOSITOS A LA VISTA` es **nuevo**: no está en
  `CATEGORIAS_VALIDAS` y entra como 12vo valor, sin fusionarlo con otro (como ya proponía
  4.2). El `.xlsm` **no** trae banda de plazo, así que `plazo_id` queda NULL para SEPS.
- `SUBTIPO DE CREDITO` (7 valores) → `dim_segmento_credito`:
  - `CONSUMO`, `MICROCREDITO`, `PRODUCTIVO` y `EDUCATIVO` mapean directo.
  - `INMOBILARIO` (sic, le falta una "I") → `INMOBILIARIO`.
  - `VIVIENDA DE INTERÉS SOCIAL Y PÚBLICO` → `VIVIENDA DE INTERÉS PÚBLICO`.
  - `OPERACIONES CONTINGENTES` no es cuenta 14: **excluir** (1,4 M USD en 2023, 30,3 M en 2024 y 9,7 M en 2025).
- Estos atributos se suman al grano de `fact_saldo_cartera` en v1:
  - `ESTADO OPERACION` de cartera (ORIGINAL / NOVADA / REFINANCIADA / REESTRUCTURADA /
    RECOMPRA / …).
  - `ORIGEN OPERACION` (7), `CLASE DE CREDITO` (2) y `ACTIVIDAD ECONOMICA` (24 secciones
    CIIU).
  - Si más adelante se quiere cartera por actividad económica, va en un outrigger aparte.
- `LINEA CREDITO` viene 100% vacía.
- `REGION`: la SEPS usa `AMAZONIA`/`INSULAR`. Se ignora y se deriva con
  `region_for_provincia()`, igual que en CAPCOL.

**Diseño revisado (reemplaza 4.4).** No hace falta ninguna fact table nueva:
- Depósitos SEPS → `staging.depositos` → `fact_saldo_depositos`.
- Cartera SEPS → `staging.cartera` → `fact_saldo_cartera`.
- EEFF → `staging.boletin_balance`/`boletin_pyg` (o tablas `staging.seps_eeff_*`
  equivalentes) → `fact_balance`/`fact_pyg`.

`tipo_entidad` = `COOPERATIVA` o `MUTUALISTA` según el sufijo del archivo (`S1`-`S3` o
`Mut`). Los filtros `IN (...)` de `_REFRESH_MARTS_SQL` se amplían a esos dos valores. La
migración es mínima: tablas `raw.seps_*` (JSONB), ampliar el `CHECK` de
`raw.source_files.report_type` y, si se incluyen CONAFIPS/FINANCOOP, el de `tipo_entidad`.
El extractor es de descarga directa, sin Playwright (la sección 4.5 sigue vigente).


Fuente: Superintendencia de Economía Popular y Solidaria,
`https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/`, descarga directa
`?sdm_process_download=1&download_id=NNNN` (enlaces `.zip` estáticos — **a diferencia de
CAPCOL, no requiere Playwright**, ver "Portabilidad de ingesta" más abajo). Investigación de
columnas/grano ya completa y validada contra archivos reales de diciembre-2025 (no
repetida acá — ver el resumen de columnas y conteos ya confirmados en la tarea que originó
este diseño). Esta sección documenta la **decisión de arquitectura**, siguiendo el mismo
patrón que este proyecto ya usó para aprobar CAPCOL/BCE/Boletín antes de construirlos
(documento primero, código después). **Nada de esta sección está implementado** — ni
extractor, ni parser, ni migración `sql/NN_*.sql`. Es la referencia para cuando se priorice
esta fase.

### 4.1 Estructura de archivos

Un ZIP por año con 4 sub-archivos Excel `.xlsm` (uno por Segmento 1/2/3 + Mutualistas) —
a diferencia de CAPCOL, donde es un archivo por tipo de reporte/segmento de crédito. El
boletín de diciembre trae el año calendario completo (12 cortes) en una sola hoja
`Base_*`, no incremental mes a mes (implica: cada descarga de diciembre reemplaza/re-cubre
todo el año, no solo agrega el mes 12 — el parser debe tratar cada archivo anual como la
fuente de verdad completa de ese año, mismo patrón de "reproceso completo desde un archivo
acumulativo" que ya usa BCE tsp/tsa, no un patrón incremental mensual como CAPCOL/Boletín).
Segmentos 4 y 5 (cooperativas más pequeñas) reportan trimestral con un catálogo de cuentas
a 4 dígitos en un reporte separado ("Estados Financieros Trimestrales") — **fuera del
alcance de esta Fase 2**: no se confirmó si también traen cartera/depósitos por cantón al
mismo nivel que 1-3+Mutualistas, y mezclar una cadencia trimestral con estructura de cuentas
distinta en el mismo diseño sería forzar un grano que no se ha validado. Si se decide
incluirlos, es una investigación y un diseño aparte, no una extensión automática de este.

### 4.2 Grano y conformidad — decisión clave: 2 fuentes, 2 formas de negocio distintas

Las 2 hojas SEPS no son "el mismo reporte con más columnas" — son **procesos de negocio
distintos**, y eso decide si conforman contra el modelo existente o necesitan una tabla
nueva (regla de diseño ya establecida en este proyecto: "hecho nuevo = proceso de negocio
nuevo", ver `docs/architecture.md` sección de renombrado de tablas):

- **`Base_captaciones` (depósitos) — SÍ conforma, reutiliza `marts.fact_saldo_depositos`
  tal cual**: `SALDO` es una foto de balance a la fecha de corte (stock), igual que CAPCOL
  depósitos — mismo concepto de negocio, mismo grano `(fecha, banco, cantón,
  categoría_depósito, plazo)`, mismas medidas (`saldo`, `numero_cuentas`,
  `numero_clientes` — nombres casi calcados: `NUMERO DE CUENTAS`/`NUMERO DE CLIENTES`).
  **No hace falta un fact nuevo, ni una dimensión nueva** para este lado.
- **`Base_vcredito` (cartera) — NO conforma contra `fact_saldo_cartera`, necesita un fact
  nuevo**: las columnas (`VAL_OPERACION`, `OPERACIONES`, `TIPO_OPERACION`, `SUJETOS DE
  CREDITO`) describen **operaciones de crédito originadas en el período** (un flujo/volumen
  de desembolsos, consistente con que el propio boletín se llama "volumen de crédito"), no
  un saldo de fin de mes por estado de mora — `fact_saldo_cartera` está diseñada
  específicamente para la segunda forma (`saldo_por_vencer`/`saldo_no_devenga_intereses`/
  `saldo_vencida` + `saldo_total` `GENERATED`, ver `sql/21_fact_saldo_cartera_pivot.sql`) y
  SEPS cartera **no trae esas 3 categorías en absoluto**. Tampoco conforma limpio contra
  `fact_colocaciones_cartera` (BCE, que sí es flujo): esa tabla promete una tasa efectiva
  por diseño (`tasa_activa_efectiva`, parte del contrato de nombre "colocaciones_" —
  "monto + tasa efectiva reportada por banco", ver el glosario de negocio en
  `docs/architecture.md`) y **SEPS cartera no trae ninguna columna de tasa** — forzar estos
  datos en `fact_colocaciones_cartera` violaría esa promesa de nombre para todas las filas
  ya cargadas de BCE. Es un proceso de negocio genuinamente distinto (volumen de operaciones
  de crédito, sin tasa, con dimensiones que ninguna fuente actual reporta) → **fact table
  nueva**: `marts.fact_volumen_cartera`.

**`ACTIVIDAD_ECONOMICA`/`DESTINO_FINANCIERO`** (columnas que ninguna fuente actual trae):
se agregan como 2 dimensiones nuevas, no como texto suelto en el fact (ambas son atributos
reutilizables de la operación de crédito, con su propio ciclo de vida/catálogo, exactamente
el criterio ya usado para `dim_actividad_economica`-style decisiones en este proyecto —
ver principio de "outrigger sobre forzar grano" en `docs/architecture.md`):

```sql
-- Propuesta, NO aplicada -- para cuando se priorice esta fase.
CREATE TABLE marts.dim_actividad_economica (
    actividad_economica_id SERIAL PRIMARY KEY,
    actividad_economica    TEXT NOT NULL UNIQUE,  -- texto tal como lo reporta SEPS
    estado_validacion      TEXT NOT NULL DEFAULT 'AUTO_INGRESADO'
                            CHECK (estado_validacion IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO'))
);

CREATE TABLE marts.dim_destino_financiero (
    destino_financiero_id  SERIAL PRIMARY KEY,
    destino_financiero     TEXT NOT NULL UNIQUE,
    estado_validacion      TEXT NOT NULL DEFAULT 'AUTO_INGRESADO'
                            CHECK (estado_validacion IN ('CONFIRMADO','AUTO_INGRESADO','RECHAZADO'))
);
```

**Two-tier por defecto para ambas, pendiente de confirmar con el archivo real antes de
implementar** (no se investigó la cardinalidad/estabilidad de estos 2 campos en esta
sesión, a diferencia de todo lo demás en esta sección): `ACTIVIDAD_ECONOMICA` en Ecuador
normalmente sigue la clasificación CIIU (decenas/cientos de valores, catálogo nacional
grande pero no cerrado a nivel de este proyecto) — candidato natural a two-tier igual que
`dim_plazo`/`dim_canton` (`sql/27`/`sql/28`), no a fail-fast absoluto. `DESTINO_FINANCIERO`
suena a un catálogo más chico y regulatoriamente cerrado (tipo "capital de trabajo",
"activos fijos") — candidato más natural a fail-fast absoluto como
`dim_segmento_credito`/`dim_categoria_deposito`. **Esta es una hipótesis a validar contando
valores distintos reales antes de escribir el `CHECK`/two-tier definitivo** — no se decide
en frío igual que los otros 5 catálogos two-tier de este proyecto no se decidieron sin
contar el universo real primero.

`TIPO_OPERACION` y `SUJETOS DE CREDITO` (cardinalidad tampoco confirmada): se proponen como
**columnas degeneradas** (`TEXT` directo en `fact_volumen_cartera`, sin tabla propia) para
v1 — a diferencia de `ACTIVIDAD_ECONOMICA`/`DESTINO_FINANCIERO`, no hay indicio de que
tengan atributos descriptivos propios más allá de la etiqueta (mismo criterio que ya
distingue "dimensión real" de "degenerada" en este proyecto, ver principio #6). Si al
implementar se confirma que tienen cardinalidad baja y fija (regulatoriamente cerrada,
como `estado_cartera` antes del pivote), reevaluar si conviene un catálogo propio — no
asumirlo de entrada sin contar valores reales.

`SEGMENTO` (viene ya resuelto por fila en SEPS, ej. `'SEGMENTO 1'` — a diferencia de BCE,
donde `tipo_segmento` hay que resolverlo aparte): **conforma directo contra
`marts.dim_segmento_entidad`**, que ya tiene exactamente los valores `SEGMENTO 1`..
`SEGMENTO 5`/`SIN SEGMENTO` para cooperativas y `SEGMENTO 1 MUTUALISTA` para mutualistas
(sembrado por BCE en `sql/19_dim_segmento_entidad.sql`) — **no hace falta un catálogo
nuevo**, es el mismo outrigger que ya usan `fact_captaciones_depositos`/
`fact_colocaciones_cartera` vía `segmento_entidad_id`. Esto es una confirmación fuerte de
que el modelo conformado ya anticipó este caso sin saberlo.

`TIPO DE CRÉDITO` de SEPS: candidato a conformar contra `marts.dim_segmento_credito` (7
valores, nivel grueso, misma taxonomía regulatoria JPRF que ya usan CAPCOL/BCE) — **no
confirmado con archivo real qué vocabulario exacto usa SEPS** (la tarea que originó este
diseño no enumeró los valores distintos de esta columna); antes de implementar, contar
valores distintos y mapearlos igual que se hizo para BCE (`sql/16_dim_segmento_normativo.sql`)
y para Banca Pública (sección 1.1 arriba, la keyword `inversion` nueva) — probablemente
necesite 1-2 alias nuevos, no una dimensión nueva.

`DEPÓSITOS A LA VISTA` (uno de los 4 `TIPO DE DEPOSITO` de SEPS): **no está en el universo
actual de `CATEGORIAS_VALIDAS`** (`etl/transform/categoria_deposito_matching.py`, 11
valores) — el sector cooperativo usa una taxonomía más simple (vista/plazo/garantía/
restringidos) que el sector bancario (que distingue ahorro/monetarios con y sin interés/
tarjetahabientes/reporto). **No asumir que "a la vista" equivale a `DEPÓSITOS DE AHORRO` o
a `DEPÓSITOS MONETARIOS...`** sin confirmarlo contra la ficha metodológica de SEPS — el
default seguro es agregarlo como 12vo valor nuevo de `CATEGORIAS_VALIDAS` (mismo patrón que
ya se siguió para agregar `DEPÓSITOS MONETARIOS` al integrar `TasasHistorico.htm`), no
fusionarlo por similitud de nombre. Los otros 3 (`DEPÓSITOS A PLAZO`, `DE GARANTÍA`,
`RESTRINGIDOS`) ya están en el catálogo tal cual. `ESTADO OPERACIÓN` (depósitos) y
`ESTADO_OPERACION` (cartera) tampoco se caracterizaron en esta sesión — confirmar sus
valores reales (¿vigente/cancelada/castigada? ¿aplica un filtro antes de sumar, para no
doble-contar?) antes de escribir el `INSERT` de `refresh_marts()`.

### 4.3 Identidad de entidad — RUC nativo en el archivo, mismo patrón RUC que BCE

A diferencia de Banca Pública (sección 1.1, que necesitó un crosswalk por nombre porque
CAPCOL no trae RUC), **SEPS SÍ trae `RUC`/`NUM_RUC` y `RAZON SOCIAL`/`RAZON_SOCIAL`
directo en cada fila** — no hace falta resolver por nombre en absoluto.
`etl/transform/banco_matching.py::validar_ruc_estructura()` ya es reutilizable tal cual
(no depende de BCE, es una función pura sobre el string de RUC). Diseño propuesto: una
función nueva `resolver_entidad_seps(razon_social, ruc, tipo_entidad_seps)` con la MISMA
forma que `resolver_entidad_bce()` (`tipo_entidad_seps` derivado del sufijo del nombre de
archivo — `S1`/`S2`/`S3` → `COOPERATIVA`, `Mut` → `MUTUALISTA` — no de una columna, ya que
SEPS separa por archivo en vez de por columna) que:
1. Valida el RUC con `validar_ruc_estructura()` (reutilizada, sin cambios) →
   `RucInvalidoError` si falla.
2. Deriva `banco_codigo = "BCE_" + ruc"` — **el mismo prefijo y la misma llave que ya usa
   BCE para el universo auto-registrado**, deliberado: la meta explícita de la tarea es
   resolver contra la MISMA fila de `dim_banco`, y la mayoría de las ~400+ cooperativas que
   trae SEPS ya deberían existir en `dim_banco` desde el fix de 2026-07-19 (BCE tsp/tsa ya
   trae "COOPERATIVAS DE AHORRO Y CREDITO" sin filtrar, ~394-402 entidades).

**Riesgo real, distinto del de Banca Pública, que hay que diseñar explícitamente**: Banca
Pública reutiliza 3 entidades que YA existían en `dim_banco` por BCE — con SEPS **no hay
esa garantía**: es plausible que existan cooperativas pequeñas que reportan a SEPS pero
nunca llegaron al umbral de reporte de BCE tsp/tsa (o viceversa), o que SEPS cubra
Segmento 1-3 mientras BCE trae el universo completo sin distinguir segmento en el archivo
mismo. Si `resolver_entidad_seps()` simplemente reutilizara `"BCE_" + ruc"` sin registrar la
entidad cuando no existe, cualquier RUC no visto antes por BCE produciría un `banco_codigo`
que el `INNER JOIN` de `refresh_marts()` descartaría en silencio (mismo riesgo ya
documentado en la sección 1.1 para Banca Pública, pero ahí mitigado porque las 3 entidades
ya estaban confirmadas vigentes; acá NO se puede asumir eso para las ~400 de SEPS sin
contarlas contra `marts.dim_banco` primero). **Diseño recomendado**: `resolver_entidad_seps()`
debe llamar al mismo mecanismo de auto-registro que ya usa BCE
(`etl/load/load_postgres.py::upsert_banco_maestro_ruc()`, hoy invocado solo desde el flujo
BCE) para registrar en `staging.banco_maestro` cualquier RUC de SEPS que aún no tenga fila
— haciendo esa función **fuente-agnóstica** en vez de asumir que siempre corre después de
BCE. Esto es exactamente el mismo patrón de two-tier/AUTO_INGRESADO que ya gobierna
`dim_banco`, solo que con un segundo punto de entrada.

**Nota de nomenclatura a decidir explícitamente al implementar, no antes**: el prefijo
`BCE_` en `banco_codigo` deja de ser 100% descriptivo el día que una segunda fuente
(SEPS) también registra entidades bajo ese mismo prefijo — es una imprecisión de nombre,
no un bug funcional (la llave sigue siendo única y estable, solo el prefijo ya no dice "de
dónde vino primero" con precisión). Dos opciones, ninguna aplicada acá: (a) mantener `BCE_`
tal cual por pragmatismo — renombrar tocaría la llave natural de potencialmente cientos de
miles de filas ya vivas en `fact_captaciones_depositos`/`fact_colocaciones_cartera`
(3M+7.7M filas), una migración cara y de alto riesgo para una ganancia puramente cosmética;
(b) introducir un prefijo neutral (`RUC_<ruc>`) solo para las entidades que SEPS registre
por primera vez (BCE sigue usando `BCE_` para las que ya existían), aceptando que el
prefijo históricamente no sea 100% uniforme. Recomendación: (a), documentado como deuda de
nomenclatura deliberada, no como pendiente de arreglar.

### 4.4 Nuevas tablas propuestas (ninguna aplicada — diseño para una migración futura)

```sql
-- sql/NN_seps_schema.sql (NO aplicado, propuesta)

-- raw: 2 tablas nuevas, mismo patrón que raw.cartera/raw.depositos/raw.bce_tasas_*
-- (JSONB append-only, un archivo = un año completo con las 4 hojas S1/S2/S3/Mut).
CREATE TABLE raw.seps_depositos (
    id            BIGSERIAL PRIMARY KEY,
    source_file   TEXT NOT NULL,
    source_hash   TEXT NOT NULL,
    sheet_name    TEXT NOT NULL,       -- 'Base_captaciones', uno por sub-archivo S1/S2/S3/Mut
    row_number    INT NOT NULL,
    anio          INT NOT NULL,
    data          JSONB NOT NULL,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE raw.seps_cartera (
    id            BIGSERIAL PRIMARY KEY,
    source_file   TEXT NOT NULL,
    source_hash   TEXT NOT NULL,
    sheet_name    TEXT NOT NULL,       -- 'Base_vcredito'
    row_number    INT NOT NULL,
    anio          INT NOT NULL,
    data          JSONB NOT NULL,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- staging.depositos NO necesita tabla nueva -- SEPS entra a la MISMA tabla que CAPCOL,
-- mismo grano/llave natural, tipo_entidad='COOPERATIVA'/'MUTUALISTA' (valores ya
-- válidos en el CHECK de marts.dim_banco.tipo_entidad, sql/07).

-- staging.volumen_cartera: tabla nueva, grano SEPS (flujo, no saldo).
CREATE TABLE staging.volumen_cartera (
    id                      BIGSERIAL PRIMARY KEY,
    fecha                   DATE NOT NULL,
    tipo_entidad            TEXT NOT NULL,   -- 'COOPERATIVA' | 'MUTUALISTA'
    banco_codigo            TEXT NOT NULL,   -- resolver_entidad_seps()
    region                  TEXT,
    provincia               TEXT,
    canton                  TEXT,
    tipo_credito            TEXT NOT NULL,   -- -> dim_segmento_credito (grueso), pendiente confirmar mapeo
    tipo_segmento           TEXT,            -- -> dim_segmento_entidad, "SEGMENTO 1".. (ya viene resuelto)
    actividad_economica     TEXT,
    destino_financiero      TEXT,
    tipo_operacion          TEXT,            -- degenerada
    sujetos_credito         TEXT,            -- degenerada
    estado_operacion        TEXT,            -- pendiente confirmar universo/filtro
    monto_operaciones       NUMERIC NOT NULL,
    numero_operaciones      BIGINT NOT NULL,
    source_file             TEXT NOT NULL,
    fecha_carga             TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion     TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash                TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_operaciones::text,'') || '|' || COALESCE(numero_operaciones::text,''))
    ) STORED,
    UNIQUE (fecha, banco_codigo, COALESCE(canton,''), tipo_credito, COALESCE(tipo_segmento,''),
            COALESCE(actividad_economica,''), COALESCE(destino_financiero,''),
            COALESCE(tipo_operacion,''), COALESCE(estado_operacion,''))
    -- NULL-safe desde el diseño (regla del proyecto, sql/10) -- no repetir el bug de
    -- staging.cartera/depositos pre-sql/23-24.
);

-- marts: 2 dimensiones nuevas + 1 fact nuevo.
CREATE TABLE marts.dim_actividad_economica ( ... );  -- ver 4.2
CREATE TABLE marts.dim_destino_financiero ( ... );   -- ver 4.2

CREATE TABLE marts.fact_volumen_cartera (
    fecha_id                INT NOT NULL REFERENCES marts.dim_fecha,
    banco_id                INT NOT NULL REFERENCES marts.dim_banco,
    canton_id                INT REFERENCES marts.dim_canton,
    segmento_id             INT NOT NULL REFERENCES marts.dim_segmento_credito,
    segmento_entidad_id     INT REFERENCES marts.dim_segmento_entidad,
    actividad_economica_id  INT REFERENCES marts.dim_actividad_economica,
    destino_financiero_id   INT REFERENCES marts.dim_destino_financiero,
    tipo_operacion          TEXT,
    estado_operacion        TEXT,
    monto_operaciones       NUMERIC NOT NULL DEFAULT 0,
    numero_operaciones      BIGINT NOT NULL DEFAULT 0,
    fecha_carga             TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion     TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash                TEXT GENERATED ALWAYS AS (
        md5(monto_operaciones::text || '|' || numero_operaciones::text)
    ) STORED,
    PRIMARY KEY (fecha_id, banco_id, COALESCE(canton_id,-1), segmento_id,
                 COALESCE(segmento_entidad_id,-1), COALESCE(actividad_economica_id,-1),
                 COALESCE(destino_financiero_id,-1), COALESCE(tipo_operacion,''),
                 COALESCE(estado_operacion,''))
);
```

(La sintaxis de `PRIMARY KEY` con `COALESCE` arriba es ilustrativa de la llave natural — en
Postgres real esto se implementa como `UNIQUE INDEX` sobre las expresiones `COALESCE`, no
como `PRIMARY KEY` literal con funciones, mismo patrón que `sql/23`/`sql/24`/`sql/28` ya
usan. Detallar la sintaxis exacta es trabajo de la migración real cuando se implemente,
no de este documento de diseño.)

### 4.5 Portabilidad de ingesta — SEPS es más simple que CAPCOL, no más compleja

CAPCOL necesita Playwright porque el listado de archivos es un explorador AJAX (plugin
"Share-one-Drive", ver `docs/architecture.md`). **SEPS usa enlaces de descarga directa**
(`?sdm_process_download=1&download_id=NNNN`, plugin "Simple Download Monitor" de WordPress,
a diferencia del plugin OneDrive de Superbancos) — un extractor `etl/extract/download_seps.py`
con `urllib`/`requests` basta, mismo patrón que `download_tasas_historicas.py` (BCE
`TasasHistorico.htm`, también descarga directa). La única pieza no trivial es que los
`download_id` numéricos deben mapearse a año/tipo de reporte a mano (no hay un patrón de URL
predecible como `TasasVigentes{MM}{YYYY}.htm`) — recolectar esos IDs es tarea de
`data-engineer` al implementar, no de este diseño.

### 4.6 Fases de implementación — qué queda para después

**Fase 2 completa (esta sección) queda como diseño aprobado, sin código.** Antes de
implementar, en este orden:
1. Confirmar cardinalidad real de `ACTIVIDAD_ECONOMICA`, `DESTINO_FINANCIERO`,
   `TIPO_OPERACION`, `SUJETOS DE CREDITO`, `ESTADO OPERACIÓN`/`ESTADO_OPERACION` y los
   valores distintos de `TIPO DE CRÉDITO` (SEPS) contra archivos reales de más de un
   segmento/año — decide two-tier vs. fail-fast para las 2 dimensiones nuevas y si
   `TIPO_OPERACION`/`SUJETOS DE CREDITO` de verdad deben quedarse degeneradas.
   confirmar si `DEPÓSITOS A LA VISTA` es un valor nuevo o un alias.
2. Migración `sql/NN_seps_schema.sql` (2 tablas `raw.*`, 1 tabla `staging.volumen_cartera`,
   2 dimensiones + 1 fact en `marts.*`) siguiendo la plantilla de la sección 4.4.
3. `etl/extract/download_seps.py`, `etl/transform/parse_seps_depositos.py`/
   `parse_seps_cartera.py`, `resolver_entidad_seps()` en `banco_matching.py` (reutilizando
   `validar_ruc_estructura()` y haciendo `upsert_banco_maestro_ruc()` fuente-agnóstico, ver
   4.3).
4. Extender `refresh_marts()` para escribir en `fact_saldo_depositos` (reutilizando el
   `INSERT` existente, ampliando el filtro `WHERE tipo_entidad IN (...)` una vez más —
   para ese punto ya incluiría `'BANCO PRIVADO', 'BANCO PUBLICO', 'COOPERATIVA',
   'MUTUALISTA'`, candidato a simplificarse a "sin filtro, el `JOIN` a `dim_banco` ya
   decide qué existe") y un `INSERT` nuevo para `fact_volumen_cartera`.
5. Actualizar los 4 documentos de gobernanza (este archivo ya actualizado; falta
   `docs/architecture.md` con el fact/dimensiones nuevas en el diagrama Mermaid,
   `docs/data_dictionary.md` con las columnas reales, `docs/gobernanza_datos.md` con el
   catálogo de metadatos y conteos) — mismo patrón que cualquier migración de este
   proyecto (ver "Gestión de cambios de esquema" en `docs/gobernanza_datos.md`).

## Próximos pasos de investigación (en orden)

1. ~~Terminar de caracterizar `tmp.zip`~~ ✅ Hecho — resultó ser pasivas mensuales, fuera
   de alcance; la fuente real de activas semanales es `tsa_desde_200801.zip`, ya
   caracterizada.
2. ~~Investigar `TasasHistorico.htm`~~ ✅ Hecho — HTML estático, sin Playwright, ~222
   páginas mensuales con patrón de URL predecible.
3. ~~Probar el portal `bancos/` y descargar un boletín real~~ ✅ Hecho — mismo plugin que
   CAPCOL, estructura BALANCE/PYG confirmada (miles de USD confirmado, plan de cuentas
   jerárquico, 9 columnas de agregado a excluir), más 10 hojas adicionales encontradas
   (`RK`/`INDICADORES` de alto valor, no exploradas a fondo todavía).
4. ~~Diseñar el catálogo conformado y proponer la arquitectura de integración~~ ✅ Hecho
   — plan aprobado, ver `docs/architecture.md` sección "Catálogos conformados".
5. ~~Construir e integrar las 3 fuentes~~ ✅ Hecho — BCE tsp/tsa, `TasasHistorico.htm` y
   Boletín BALANCE/PYG cargados en Postgres con CDC verificado. Cobertura real: BCE
   semanal 2008-2026 completo; `TasasHistorico.htm` 2022-04 a 2026-06 (páginas más
   antiguas usan un layout HTML distinto, no soportado); Boletín 2021-01 a 2026-06. Ver
   `docs/data_dictionary.md` para el esquema final y `docs/metricas_financieras.md` para
   el catálogo de indicadores financieros del Boletín.
6. **Pendiente, fuera de alcance de esta expansión**: cargar `RK`/`INDICADORES` como
   tablas (documentados pero no cargados, ver `docs/metricas_financieras.md`); extender
   `TasasHistorico.htm`/Boletín a años anteriores a 2021-2022 (requeriría soportar layouts
   HTML/Excel adicionales); actualizar el modelo Power BI (`.pbip`) para incorporar las
   nuevas tablas de hechos.
7. ~~Investigar `capcol-instituciones-publicas/` (Banca Pública) con Playwright~~ ✅ Hecho
   (2026-09-01) — mismo plugin/formato que `capcol-bancos`, rango parseable 2021-2025
   (coincide con lo ya cargado de bancos privados), 0 migraciones `sql/*` necesarias,
   identidad resuelta vía `etl/seeds/banco_crosswalk.csv` contra los `banco_codigo` que BCE
   ya auto-registró. Ver sección 1.1 arriba. **Diseño completo, crosswalk implementado
   (`etl/seeds/banco_crosswalk.csv`, `tests/test_banco_matching.py`); extractor/parser/
   `_REFRESH_MARTS_SQL` pendientes, carril de `data-engineer`** (lista de 5 cambios en
   sección 1.1).
8. ~~Diseñar la arquitectura de SEPS (cooperativas + mutualistas)~~ ✅ Hecho (2026-09-01) —
   ver sección 4 arriba. **Solo diseño — nada implementado**: sin extractor, sin parser,
   sin migración `sql/NN_*.sql`. Pendiente: confirmar cardinalidad de 5 campos no
   caracterizados (sección 4.6 punto 1) antes de escribir la migración real.
