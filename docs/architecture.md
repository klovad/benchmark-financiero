# Arquitectura

## Flujo de datos

```
Superbancos (portal CAPCOL, plugin OneDrive/SharePoint vía WordPress)
        │  Playwright (etl/extract/scrape_superbancos.py)
        ▼
data/raw/{anio}/{cartera|depositos}/*.zip   (no versionado en git)
        │  parsers (etl/transform/parse_cartera.py, parse_depositos.py)
        ▼
raw.cartera / raw.depositos   (JSONB tal cual, + hash de archivo para idempotencia)
        │  upsert por llave natural
        ▼
staging.cartera / staging.depositos   (tipado, estandarizado, agregado)
        │  refresh_marts() (SQL puro, INSERT...SELECT...ON CONFLICT)
        ▼
marts.dim_* / marts.fact_*   (esquema estrella)
        │
        ▼
Power BI (.pbip, Import desde Postgres)
```

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

- **Volumen no es el riesgo**: ~336k filas en `fact_cartera` y ~229k en `fact_depositos`
  para 5 años x ~28 bancos x ~130 cantones x productos. Postgres lo maneja sin
  particionar ni tuning especial. Ampliar el histórico a más años solo crece linealmente.
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

## Power BI: qué quedó armado vs. qué falta terminar en Desktop

El `.pbip` (`powerbi/benchmark-cartera-depositos.*`) se escribió a mano en TMDL/PBIR (no
se generó desde Power BI Desktop, porque no hay forma de automatizar el diseño visual
desde este entorno). Quedó completo y debería abrir correctamente:

- **Modelo semántico completo**: 7 tablas conectadas a Postgres (`marts.*`), relaciones
  fact→dim, 13 medidas DAX (saldo, morosidad, market share, HHI, variación m/m y a/a,
  ratio cartera/depósitos).
- **5 páginas de reporte creadas pero vacías** (Overview y KPIs, Benchmark por Banco,
  Análisis Geográfico, Tendencias y Estacionalidad, Correlación Cartera vs Depósitos):
  el diseño de visuales (qué gráfico, qué campos, colores, layout) se dejó deliberadamente
  para hacerse en Power BI Desktop, porque iterar visuales a mano en JSON sin poder abrir
  el archivo para verificar es de alto riesgo de romper el reporte.

**Al abrir el `.pbip` por primera vez**: Power BI pedirá credenciales de Postgres
(usuario `bp_etl`, la contraseña que configuraste en `sql/00_roles_db.sql`) y el modo de
autenticación de privacidad de datos. También recomendable: click derecho en
`dim_fecha` → "Marcar como tabla de fechas" (necesario para que las medidas de
variación m/m y a/a con `DATEADD` funcionen correctamente).

Guía sugerida por página (campos/medidas a arrastrar):
- **Overview y KPIs**: tarjetas con `Saldo Cartera`, `Saldo Depositos`, `Morosidad %`,
  `HHI Cartera`; gráfico de línea de `Saldo Cartera` y `Saldo Depositos` por `dim_fecha[fecha]`.
- **Benchmark por Banco**: gráfico de barras `Saldo Cartera` por `dim_banco[banco]`,
  tabla con `Market Share Banco (Cartera)` y `Market Share Banco (Depositos)`.
- **Análisis Geográfico**: mapa o treemap por `dim_canton[canton]`/`provincia`/`region`
  con `Saldo Cartera` y `Saldo Depositos`.
- **Tendencias y Estacionalidad**: líneas por `mes`/`trimestre` comparando años
  (`anio` como leyenda), `Variacion Cartera MoM`/`YoY`.
- **Correlación Cartera vs Depósitos**: scatter/combo con `Ratio Cartera / Depositos`
  por banco o por mes.
