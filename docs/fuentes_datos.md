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
- **Grano**: mensual, por banco x cantón x tipo_credito/tipo_deposito x estado_cartera.
- **Sin tasas de interés** (confirmado). Sin balance/PyG.
- **Cargado**: `raw`/`staging`/`marts` en Postgres, 2021-2025, ver `docs/data_dictionary.md`.

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
  pública/cooperativas) — pero `dim_segmento_credito` siempre se sembró con los 26
  completos (decisión previa, ya correcta) y **`fact_colocaciones_cartera` (antes
  `fact_tasas_activas`, renombrada 2026-07-19 mismo día) ahora también carga las filas
  de los 4 segmentos exclusivos de banca pública/cooperativas** (2026-07-19:
  ya no se filtra tipo_entidad en ningún punto del pipeline, ver nota arriba). **Se
  necesita una tabla de mapeo `segmento_credito` → `tipo_credito`
  (CAPCOL)** para poder comparar tasas activas contra los saldos de cartera por
  segmento — no es un mapeo 1:1 trivial (ej. CAPCOL "comercial" ⊂ {COMERCIAL ORDINARIO,
  COMERCIAL PRIORITARIO *, PRODUCTIVO *}).
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
    "PRODUCTIVO - CORPORATIVO" (`dim_segmento_credito`, con guion).
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
  Power BI de CAPCOL — si coinciden, valida el modelo; si no, hay una discrepancia que
  investigar (posible causa: CAPCOL es saldo de cartera/depósitos por cantón, Boletín es
  balance contable completo, no son necesariamente la misma cifra).
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
