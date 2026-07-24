# Arquitectura

## Flujo de datos

El proyecto integra **3 fuentes independientes** en un único esquema estrella conformado.
Cada fuente tiene su propio extractor/parser, pero todas convergen en la misma capa
`marts.*` — la identidad de banco y los catálogos de producto/plazo son compartidos
(resueltos en Python antes de `staging.*`, ver sección "Catálogos conformados" abajo).

```
CAPCOL (cartera/depósitos)          BCE tsp/tsa (tasas semanales)      TasasHistorico.htm       Boletín (BALANCE/PYG)
Playwright, plugin OneDrive         descarga directa (urllib)          descarga directa          Playwright, plugin OneDrive
scrape_superbancos.py               download_bce.py                    download_tasas_           scrape_boletin.py
        │                                   │                          historicas.py                     │
        ▼                                   ▼                                │                           ▼
data/raw/{anio}/*.zip           data/raw/bce/ts{p,a}_*.zip          data/raw/bce/historico/*.htm   data/raw/{anio}/boletin/*.zip
        │  parse_cartera.py/                │  parse_bce_tasas.py           │  parse_tasas_             │  parse_boletin.py
        │  parse_depositos.py               │                               │  historicas.py            │
        ▼                                   ▼                               ▼                           ▼
raw.cartera / raw.depositos      raw.bce_tasas_pasivas/activas    raw.tasas_referenciales    raw.boletin_balance/pyg
        │  upsert por llave natural (ON CONFLICT DO UPDATE ... WHERE row_hash IS DISTINCT — ver "Carga incremental")
        ▼
staging.*   (tipado, banco_codigo/categoria/segmento ya resueltos, columnas fecha_carga/fecha_actualizacion/row_hash)
        │  refresh_marts() (SQL puro, INSERT...SELECT...ON CONFLICT, idempotente)
        ▼
marts.dim_* / marts.fact_*   (esquema estrella conformado — 5 dimensiones + 9 tablas de hechos)
        │
        ▼
Power BI (.pbip, Import desde Postgres)
```

## Modelo de datos (esquema estrella)

8 dimensiones y 10 tablas de hechos en `marts.*`, resultado final del flujo anterior.
`dim_fecha`/`dim_banco` son compartidas por casi todas las fuentes; `dim_canton`,
`dim_segmento_credito`, `dim_subsegmento_credito`, `dim_categoria_deposito`, `dim_plazo`
y `dim_cuenta_contable` son compartidas solo por las fuentes que las necesitan (ver
"Catálogos conformados" abajo). Detalle de cada columna en `docs/data_dictionary.md`.

```mermaid
erDiagram
    dim_fecha {
        int fecha_id PK
        date fecha
        int anio
        int mes
        int trimestre
        int anio_mes
    }
    dim_banco {
        int banco_id PK
        string banco_codigo
        string banco
        string tipo_entidad
        string ruc
    }
    dim_canton {
        int canton_id PK
        string canton
        string provincia
        string region
    }
    dim_segmento_credito {
        int segmento_id PK
        string segmento
    }
    dim_subsegmento_credito {
        int subsegmento_id PK
        string subsegmento
        int segmento_id FK
    }
    dim_categoria_deposito {
        int categoria_deposito_id PK
        string categoria
    }
    dim_plazo {
        int plazo_id PK
        int dias_desde
        int dias_hasta
        string plazo_codigo
    }
    dim_cuenta_contable {
        int cuenta_id PK
        string reporte
        string codigo
        string cuenta
        int nivel
        string codigo_padre
        string seccion
        string grupo_met
    }

    fact_saldo_cartera {
        int fecha_id FK
        int banco_id FK
        int canton_id FK
        int segmento_id FK
        string estado_cartera
        numeric saldo
    }
    fact_saldo_depositos {
        int fecha_id FK
        int banco_id FK
        int canton_id FK
        int categoria_deposito_id FK
        int plazo_id FK
        numeric saldo
        bigint numero_cuentas
        bigint numero_clientes
    }
    fact_captaciones_depositos {
        int fecha_id FK
        int banco_id FK
        int categoria_deposito_id FK
        int plazo_id FK
        string provincia
        numeric monto_total
        numeric tasa_pasiva_efectiva
    }
    fact_colocaciones_cartera {
        int fecha_id FK
        int banco_id FK
        int subsegmento_id FK
        int plazo_id FK
        string provincia
        numeric monto_total
        numeric tasa_activa_efectiva
    }
    fact_tasas_referenciales_cartera {
        int fecha_id FK
        int subsegmento_id FK
        numeric tasa_activa_maxima
        numeric tasa_activa_referencial
    }
    fact_tasas_referenciales_depositos_instrumento {
        int fecha_id FK
        int categoria_deposito_id FK
        numeric tasa_pasiva_promedio
    }
    fact_tasas_referenciales_depositos_plazo {
        int fecha_id FK
        int plazo_id FK
        numeric tasa_pasiva_referencial
    }
    fact_tasas_referenciales_sistema {
        int fecha_id PK
        numeric tasa_pasiva_referencial_sistema
        numeric tasa_activa_referencial_sistema
    }
    fact_balance {
        int fecha_id FK
        int banco_id FK
        int cuenta_id FK
        numeric saldo_usd
    }
    fact_pyg {
        int fecha_id FK
        int banco_id FK
        int cuenta_id FK
        numeric valor_usd
    }

    dim_fecha ||--o{ fact_saldo_cartera : fecha_id
    dim_fecha ||--o{ fact_saldo_depositos : fecha_id
    dim_fecha ||--o{ fact_captaciones_depositos : fecha_id
    dim_fecha ||--o{ fact_colocaciones_cartera : fecha_id
    dim_fecha ||--o{ fact_tasas_referenciales_cartera : fecha_id
    dim_fecha ||--o{ fact_tasas_referenciales_depositos_instrumento : fecha_id
    dim_fecha ||--o{ fact_tasas_referenciales_depositos_plazo : fecha_id
    dim_fecha ||--o| fact_tasas_referenciales_sistema : fecha_id
    dim_fecha ||--o{ fact_balance : fecha_id
    dim_fecha ||--o{ fact_pyg : fecha_id

    dim_banco ||--o{ fact_saldo_cartera : banco_id
    dim_banco ||--o{ fact_saldo_depositos : banco_id
    dim_banco ||--o{ fact_captaciones_depositos : banco_id
    dim_banco ||--o{ fact_colocaciones_cartera : banco_id
    dim_banco ||--o{ fact_balance : banco_id
    dim_banco ||--o{ fact_pyg : banco_id

    dim_canton ||--o{ fact_saldo_cartera : canton_id
    dim_canton ||--o{ fact_saldo_depositos : canton_id

    dim_segmento_credito ||--o{ fact_saldo_cartera : segmento_id
    dim_segmento_credito ||--o{ dim_subsegmento_credito : segmento_id
    dim_subsegmento_credito ||--o{ fact_colocaciones_cartera : subsegmento_id
    dim_subsegmento_credito ||--o{ fact_tasas_referenciales_cartera : subsegmento_id

    dim_categoria_deposito ||--o{ fact_saldo_depositos : categoria_deposito_id
    dim_categoria_deposito ||--o{ fact_captaciones_depositos : categoria_deposito_id
    dim_categoria_deposito ||--o{ fact_tasas_referenciales_depositos_instrumento : categoria_deposito_id

    dim_plazo ||--o{ fact_saldo_depositos : plazo_id
    dim_plazo ||--o{ fact_captaciones_depositos : plazo_id
    dim_plazo ||--o{ fact_colocaciones_cartera : plazo_id
    dim_plazo ||--o{ fact_tasas_referenciales_depositos_plazo : plazo_id

    dim_cuenta_contable ||--o{ fact_balance : cuenta_id
    dim_cuenta_contable ||--o{ fact_pyg : cuenta_id
```

Nombres renombrados 2026-07-19 a un glosario de negocio consistente: **cartera** = negocio
de crédito (siempre), **depositos** = negocio de captación (siempre); **saldo_** = medida
de balance (CAPCOL); **colocaciones_**/**captaciones_** = tasa efectiva + monto por banco
(BCE semanal); **tasas_referenciales_** = techo/referencial a nivel sistema (BCE mensual).
Nombres anteriores: `fact_cartera`→`fact_saldo_cartera`, `fact_depositos`→`fact_saldo_depositos`,
`fact_tasas_activas`→`fact_colocaciones_cartera`, `fact_tasas_pasivas`→`fact_captaciones_depositos`,
`fact_tasas_referenciales_credito`→`fact_tasas_referenciales_cartera`,
`fact_tasas_pasivas_instrumento`→`fact_tasas_referenciales_depositos_instrumento`,
`fact_tasas_pasivas_plazo`→`fact_tasas_referenciales_depositos_plazo`. De paso se
eliminaron 3 columnas nunca pobladas (`saldo_x_tasa`, `tasa_ponderada` en ambas tablas de
saldo; `morosidad` en `fact_saldo_cartera`) — la tasa real ya vive en
`fact_colocaciones_cartera`/`fact_captaciones_depositos`. Ver `sql/15_rename_fact_tables.sql`.

**Segmentación de crédito: 2 dimensiones normativas, no una** (2026-07-19,
`sql/16_dim_segmento_normativo.sql`): `dim_segmento_credito` (7 valores, nivel grueso:
PRODUCTIVO/CONSUMO/EDUCATIVO/INMOBILIARIO/VIVIENDA DE INTERÉS PÚBLICO/MICROCRÉDITO/
INVERSIÓN PÚBLICA) y `dim_subsegmento_credito` (26 valores, nivel fino tal como lo
reporta BCE) están unidas por FK propia — antes eran una sola tabla con el rollup a
CAPCOL como columna `TEXT` nullable (`tipo_credito_capcol`), sin garantía de que
coincidiera con el `tipo_credito` (también texto libre) de `fact_cartera`. CAPCOL nunca
trae el sub-segmento fino, así que `fact_saldo_cartera.segmento_id` referencia el nivel
grueso directo; BCE sí reporta al nivel fino, así que `fact_colocaciones_cartera`/
`fact_tasas_referenciales_cartera` referencian `dim_subsegmento_credito` vía
`subsegmento_id`. `estado_cartera` en `fact_saldo_cartera` sigue como dimensión
degenerada (columna directa, solo 3 valores fijos, no una jerarquía real). `plazo_id` en
`fact_saldo_depositos` es nullable (`NULL` salvo `categoria_deposito = 'DEPÓSITOS A PLAZO'`)
y las 4 tablas de `tasas_referenciales_*` son a nivel sistema (sin `dim_banco`, ver
`docs/data_dictionary.md`).

Este diagrama es la vista **estructural** del modelo (qué se relaciona con qué). No
sustituye la definición de negocio de cada campo (`docs/data_dictionary.md`), la
procedencia campo a campo (`docs/linaje_datos.md`) ni el marco de responsable/
clasificación/calidad (`docs/gobernanza_datos.md`) — las 4 piezas juntas son la
gobernanza de datos completa del proyecto, ver `docs/gobernanza_datos.md` para cómo
encajan entre sí.

## Catálogos conformados (identidad compartida entre fuentes)

La identidad de banco (`banco_codigo`) y los catálogos de segmento de crédito/categoría de
depósito/plazo se resuelven **en Python, en la capa `transform`, antes de que el dato
llegue a `staging.*`** — no como tabla de alias en el esquema estrella:

- `etl/transform/banco_matching.py`: `resolver_banco_codigo(nombre, fuente)`. Reglas
  determinísticas (tildes, mayúsculas, prefijos `BP `/`BANCO`, sufijos legales) resuelven
  variaciones triviales; lo que la regla no cubre (nombre legal completo de BCE vs. código
  corto de CAPCOL/Boletín, o los 2 renames reales de CAPCOL) se resuelve contra
  `etl/seeds/banco_crosswalk.csv`, sembrado a mano y versionado en git. Un nombre no
  resuelto **falla fuerte** (`BancoNoResueltoError`) — nunca se autogenera un banco nuevo
  silenciosamente.
- `etl/transform/categoria_deposito_matching.py` y `bce_plazo_matching.py`: mismo patrón
  para separar categoría/plazo (CAPCOL mezclaba ambos conceptos en `tipo_deposito`) y para
  resolver los buckets de plazo con prefijo ordinal de BCE (`a. MENOS DE 30 DIAS`, etc.).
- `dim_subsegmento_credito` (26 valores, universo completo de BCE) y `dim_categoria_deposito`
  (12 valores) **no se filtran por tipo de entidad**. Desde 2026-07-19 esto ya no es solo
  el catálogo: `fact_captaciones_depositos`/`fact_colocaciones_cartera` (BCE tsp/tsa) tampoco filtran —
  cargan el sistema financiero completo (442 bancos en `dim_banco`: 33 privados curados +
  409 entidades auto-registradas por RUC, ver `docs/gobernanza_datos.md`). Corrige una
  versión anterior que sí filtraba a bancos privados **antes de llegar a `raw.*`**,
  perdiendo el resto del sistema para siempre.
- `dim_plazo` es un catálogo abierto por rango numérico de días, auto-descubierto por cada
  fuente (`INSERT ... ON CONFLICT DO NOTHING`) — **no se fuerza una equivalencia entre
  convenciones distintas** (ej. CAPCOL "DE MÁS DE 361 DÍAS" y BCE tsp "MAS DE 360 DIAS"
  quedan como filas distintas, cada una con el límite real de su fuente).

## Carga incremental (CDC) — no full refresh

`staging.*` y los `fact_*`/`dim_banco` de `marts` tienen 3 columnas de control:
`fecha_carga` (se pone una vez), `fecha_actualizacion` (solo se mueve si el dato
realmente cambió) y `row_hash` (columna `GENERATED ALWAYS AS (...) STORED`, cubre solo
las columnas mutables, no la llave natural). El patrón de carga es:

```sql
INSERT INTO staging.tabla (...) VALUES (...)
ON CONFLICT (llave_natural)
DO UPDATE SET col = EXCLUDED.col, fecha_actualizacion = now()
WHERE staging.tabla.row_hash IS DISTINCT FROM EXCLUDED.row_hash;
```

Correr el pipeline dos veces seguidas sin datos nuevos no genera ningún `UPDATE` real —
verificado explícitamente para cada fuente (`fecha_actualizacion` sin cambios en la
segunda corrida). `raw.*` sigue siendo append-only, idempotente por `source_hash` a nivel
de archivo (vía `raw.source_files`).

**¿Por qué no Data Vault?** Data Vault (Hub/Link/Satellite) resuelve integrar muchas
fuentes de alta velocidad de cambio con auditoría regulatoria estricta, normalmente como
capa de integración *debajo* de un modelo Kimball. Con 3 fuentes y cadencia
mensual/semanal, sería sobre-ingeniería — la capa `raw.*` (JSONB + `source_hash`) ya da la
parte valiosa de esa filosofía (nunca se pierde el dato original) sin el formalismo
completo de Hub/Link/Satellite.

### Bug real encontrado y corregido: NULL en `UNIQUE`/`ON CONFLICT`

SQL trata `NULL <> NULL` **incluso bajo una restricción `UNIQUE`**, así que
`UNIQUE (a, b)` con `b` nullable no detecta conflicto entre dos filas `(1, NULL)` — cada
corrida de `refresh_marts()` insertaba una fila "nueva" para el bucket de plazo sin límite
superior (`dias_hasta IS NULL`), duplicando `dim_plazo` y produciendo fan-out en el JOIN
de `fact_depositos` (hoy `fact_saldo_depositos`, ver renombrado 2026-07-19 arriba). Fix (ver `sql/10_fix_null_unique_constraints.sql`): reemplazar el
`UNIQUE` plano por un índice único sobre `COALESCE(col, sentinela)`, y apuntar
`ON CONFLICT` a esa misma expresión — verificado que `ON CONFLICT (a, COALESCE(b, -1))`
sí detecta el conflicto. Este mismo patrón se aplicó preventivamente a toda columna
nullable dentro de una llave natural nueva (`plazo_id`, `provincia`, `dias_hasta`).

## Por qué Playwright y no requests/httpx

El listado de archivos por año en `capcol-bancos` no es HTML estático: se renderiza con
un plugin WordPress ("Share-one-Drive") que trae los archivos desde una carpeta de
OneDrive/SharePoint vía llamadas AJAX a `admin-ajax.php`. Además, el plugin **persiste
la última carpeta vista** entre navegaciones (recargar la página con `page.goto()` no
resetea al listado raíz de años, hay que usar el breadcrumb "Inicio" — ver
`_reset_to_root()` en el scraper). Sin un navegador real esto no es scrapeable de forma
simple.

## Estructura real de los archivos fuente (verificado, no solo la ficha metodológica)

- **Cartera**: un ZIP por segmento de crédito y año (`Cartera de Consumo DICIEMBRE
  2024.zip`, etc.), cada uno con una hoja `BASE ...` en formato ancho (una columna por
  estado de cartera). El archivo de "Vivienda" es la excepción: trae **dos** hojas BASE
  (inmobiliario y vivienda de interés público son tipo_credito distintos aunque
  compartan archivo). `tipo_credito` se deriva del **nombre de la hoja**, no del nombre
  del archivo, precisamente por este caso.
- **Depósitos**: un solo ZIP por año con todos los tipos de depósito en una hoja `BASE
  ...`, con una columna `TIPO DE DEPOSITO` ya granular (incluye buckets de plazo por
  rango de días, más fino que la ficha metodológica de 2017).
- **Ambos reportes traen el detalle a nivel de cuenta contable/oficina**: múltiples filas
  pueden compartir la llave (fecha, banco, cantón, tipo_credito/tipo_deposito) y deben
  **sumarse**, no sobrescribirse. Se detectó con datos reales (no era evidente en la
  documentación) y se corrigió agregando en el parser antes de cargar a staging.
- **Nombres de carpeta cambiaron en 2024**: `COLOCACIONES`/`CAPTACIONES` (2021-2023) →
  `CARTERA`/`DEPOSITOS` (2024-2025). El layout de columnas internas es idéntico entre
  ambos periodos — el "cambio de esquema" es solo de nomenclatura de carpeta/archivo,
  no de estructura de datos.
- **No hay tasa de interés en ninguno de los dos reportes.** Se confirmó contra la ficha
  metodológica y contra archivos reales descargados. Decisión (con el usuario): dejar
  `tasa_ponderada`/`saldo_x_tasa` como columnas nullable en `marts.fact_*`, sin poblar en
  v1. Para incorporarlas habría que sumar el reporte separado de tasas de interés
  activas/pasivas de Superbancos como una nueva fuente.

## Evaluación de escalabilidad

- **Volumen no es el riesgo**: ~336k filas en `fact_saldo_cartera`, ~229k en `fact_saldo_depositos`
  (CAPCOL, 2021-2025); **~1.96M en `fact_captaciones_depositos` y ~4.87M en `fact_colocaciones_cartera`**
  (BCE semanal, histórico completo 2008-2026, sistema financiero completo — no solo
  bancos privados, ver `docs/gobernanza_datos.md`); ~2.18M en `fact_balance` y ~192k en
  `fact_pyg` (Boletín, 2021-2026). `raw.bce_tasas_pasivas`/`activas` son más grandes
  todavía (~3.08M y ~7.76M filas respectivamente — grano cantón, sin agregar; los nombres
  `raw.*` no cambiaron, solo los de `marts.*`). El BCE
  semanal es el volumen dominante con margen — se cargó vía `COPY` (no `executemany`) por
  esa razón, ~10-100x más rápido a este volumen. Postgres lo maneja sin particionar ni
  tuning especial; `refresh_marts()` completo sobre todo el dataset acumulado toma
  ~5-6 minutos (subió desde ~1-2 min al dejar de filtrar BCE a solo bancos privados).
- **El riesgo real es el *schema drift* de la fuente**: ya se observó un cambio de
  nomenclatura de carpetas/archivos en 2024. Mitigación: `raw.*` preserva el archivo tal
  cual (JSONB) para poder reprocesar sin volver a descargar si un parser cambia; la
  detección de `tipo_credito` por nombre de hoja (no de archivo) y de `tipo_deposito` por
  columna (no por archivo) hace el parser más robusto a estos cambios superficiales.
- **El riesgo de extracción es el acoplamiento al plugin del sitio** (selectores CSS,
  comportamiento de navegación). Aislado en `etl/extract/scrape_superbancos.py`; si el
  sitio cambia, solo ese módulo necesita ajustarse — transform/load no se ven afectados
  porque trabajan desde `data/raw/` ya descargado.
- **Idempotencia end-to-end**: `raw.source_files` evita reprocesar un archivo sin
  cambios (por hash); `staging.*` y `marts.*` usan `ON CONFLICT DO UPDATE` sobre la
  llave natural, así que correr el pipeline de nuevo (o solo para un año) siempre
  converge al mismo resultado.
- **Para portafolio/distribución**: `docker-compose.yml` deja Postgres + esquema listos
  con un solo comando, sin depender de la instalación local del autor.
- Pandas es suficiente a esta escala; Airflow/Spark serían sobre-ingeniería para una
  fuente que publica mensualmente. Si el proyecto creciera a más reportes (morosidad,
  liquidez) o más países, el patrón raw→staging→marts ya soporta agregarlos sin
  rediseño: un parser + un mapping nuevo por reporte.

## Power BI: cómo se construyó y qué quedó armado

El `.pbip` (`powerbi/benchmark-cartera-depositos.*`) se escribió a mano en TMDL/PBIR (no
se generó desde Power BI Desktop, porque no hay forma de automatizar el diseño visual
desde este entorno). Para reducir el riesgo de un archivo corrupto, el modelo semántico y
el reporte se validaron estructuralmente contra los **JSON Schema oficiales de Microsoft**
(`report.schema.json`, `page.schema.json`, `pagesMetadata.schema.json`,
`visualContainer.schema.json`) antes de darlos por terminados, y cada `Entity`/`Property`
referenciado en un visual se verificó contra las medidas/columnas reales del TMDL. Esto no
sustituye abrirlo en Power BI Desktop, pero elimina la clase de error más común (URLs de
`$schema` desactualizadas, campos requeridos faltantes, nombres de medida mal escritos).

- **Modelo semántico completo**: 7 tablas conectadas a Postgres (`marts.*`), relaciones
  fact→dim, 17 medidas DAX (saldo, saldo "último mes", morosidad, market share, HHI,
  variación m/m y a/a, ratio cartera/depósitos).
- **5 páginas de reporte con visuales reales** (no solo el lienzo vacío):
  - **Overview y KPIs**: 4 tarjetas (`Saldo Cartera (Ultimo Mes)`, `Saldo Depositos
    (Ultimo Mes)`, `Morosidad % (Ultimo Mes)`, `HHI Cartera (Ultimo Mes)`) + línea de
    tendencia mensual `Saldo Cartera`/`Saldo Depositos` 2021-2025.
  - **Benchmark por Banco**: dos barras horizontales (cartera y depósitos del último mes
    por `dim_banco[banco]`).
  - **Análisis Geográfico**: dos barras horizontales por `dim_canton[provincia]`.
  - **Tendencias y Estacionalidad**: línea de `Saldo Cartera` por mes, una serie por año
    (`dim_fecha[anio]` como leyenda) para ver estacionalidad.
  - **Correlación Cartera vs Depósitos**: tabla por banco con saldo de cartera, saldo de
    depósitos y `Ratio Cartera / Depositos`.
  - Las medidas `*(Ultimo Mes)` filtran internamente a `MAX(dim_fecha[fecha])` para que
    las tarjetas y barras muestren la foto del mes más reciente, no la suma de los 60
    meses cargados (que no tendría sentido como cifra "actual").

**Al abrir el `.pbip` por primera vez**: Power BI pedirá credenciales de Postgres
(usuario `bp_etl`, la contraseña que configuraste en `sql/00_roles_db.sql`) y el modo de
autenticación de privacidad de datos. También recomendable: click derecho en
`dim_fecha` → "Marcar como tabla de fechas" (necesario para que `Variacion Cartera
MoM`/`YoY` con `DATEADD` funcionen correctamente).

**Qué queda para terminar tú en Desktop** (diseño, no estructura): colores, formato de
tarjetas, un mapa real en la página geográfica (se usó barras por ser más simple de
generar por JSON sin errores; un mapa/treemap es una mejora fácil de aplicar en Desktop),
slicers de fecha/banco, y cualquier ajuste de layout — todo esto es iteración visual que
es más confiable hacer en el diseñador de Desktop que a mano en JSON.

**Herramienta usada para validar/construir los visuales**: se clonó y consultó (no se
instaló como skill de Claude) el repo público
[lukasreese/powerbi-claude-skills](https://github.com/lukasreese/powerbi-claude-skills),
que trae copias locales de los JSON Schema de Microsoft para PBIR y templates de
visuales ya probados. Confirma que **no existe forma de controlar Power BI Desktop en
vivo** (ni esa herramienta ni ninguna otra conocida lo hace) — el método siempre es
escribir los archivos `.pbip`/PBIR y abrirlos después en Desktop.
