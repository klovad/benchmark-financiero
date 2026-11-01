# Catálogo de fuentes de datos

Qué es cada fuente, cómo se accede, su estructura **real** (verificada con archivos
descargados, no solo con la ficha metodológica) y qué se carga. Cobertura vigente en el
README ("Alcance de los datos"); cómo se resolvió cada fuente a lo largo del tiempo, en
`docs/historial.md`.

| Fuente | Publicador | Acceso | Cadencia | Desde | Destino en `marts` |
|---|---|---|---|---|---|
| CAPCOL bancos privados y Banca Pública | Superbancos | Playwright (plugin OneDrive) | Mensual (acumulado del año) | 2021-01 | `fact_saldo_cartera`, `fact_saldo_depositos` |
| BCE tsp / tsa | BCE | Descarga directa, condicional | Semanal (archivo único acumulado) | 2008-01 | `fact_captaciones_depositos`, `fact_colocaciones_cartera` |
| BCE `TasasHistorico.htm` | BCE | Descarga directa (HTML) | Mensual | 2009-07 | `fact_tasas_referenciales_*` |
| Boletín Financiero Mensual | Superbancos | Playwright (plugin OneDrive) | Mensual | 2021-01 | `fact_balance`, `fact_pyg` |
| SEPS (S1-S3 y mutualistas) | SEPS | Descarga directa (`download_id`) | Anual, se republica cada mes | 2021-01 | saldos en las mismas tablas que CAPCOL; EEFF en `fact_balance`/`fact_pyg` |

Ninguna fuente trae datos personales: el grano más fino es entidad × cantón × producto ×
fecha.

## 1. CAPCOL — Cartera y Depósitos (Superbancos)

- **URLs**: `https://www.superbancos.gob.ec/estadisticas/portalestudios/capcol-bancos/`
  (bancos privados) y `.../capcol-instituciones-publicas/` (Banca Pública). Definidas en
  `config/sources.py::CAPCOL_PORTALES`; un tercer sub-portal del hub no se integra.
- **Acceso**: WordPress con el plugin "Share-one-Drive" (OneDrive/SharePoint vía AJAX a
  `admin-ajax.php`), no HTML estático: requiere Playwright (ver "Por qué Playwright" en
  `docs/architecture.md`).
- **Estructura**: Año → `CARTERA`/`DEPOSITOS` (antes de 2024, `COLOCACIONES`/
  `CAPTACIONES`) → ZIP → Excel con hoja(s) `BASE ...`. Un archivo de cartera por segmento
  ("Vivienda" trae 2 hojas BASE); un archivo de depósitos por año con todos los tipos.
  **Cada archivo es acumulado del año** (el de agosto trae enero-agosto) y se republica
  cada mes, a veces con nombres de entidad o cantones cambiados: la publicación nueva
  reemplaza a la anterior (regla en `docs/gobernanza_datos.md`).
- **Columnas** (idénticas en ambos sub-portales):
  - Cartera: `FECHA, ENTIDAD, PROVINCIA, CANTON, POR VENCER, NO DEVENGA INTERESES, VENCIDA, TOTAL SALDO`.
    El tipo de crédito sale del nombre de la hoja (`tipo_credito_from_sheet_name()`,
    `config/domain.py::TIPO_CREDITO_KEYWORDS`; "inversion" → `inversion_publica`, solo
    Banca Pública).
  - Depósitos: `FECHA, ENTIDAD, REGION, PROVINCIA, CANTON, CUENTA, TIPO DE DEPOSITO, NUMERO DE CUENTAS, NUMERO DE CLIENTES, SALDO`.
    La columna `REGION` se ignora: la región sale de `dim_provincia`.
- **Grano**: mensual, entidad × cantón × tipo de crédito × estado de cartera / tipo de
  depósito. `fact_saldo_cartera` pivota el estado a 3 columnas de saldo.
- **Sin tasas de interés** ni balance (verificado contra archivos reales): por eso BCE y
  el Boletín.
- **Desde 2021-01**: la hoja `BASE ...` plana solo existe desde 2021. Los años 2016-2020
  del portal traen un formato pivotado por cantón × mes, sin columna de entidad, que no
  se parsea.
- **Banca Pública**: 3 entidades (BanEcuador, CFN y Banco de Desarrollo del Ecuador,
  razón social histórica "BANCO DEL ESTADO"). BIESS, BNF e IECE no reportan en este hub.
  El BdE solo reporta cartera (Inversión Pública y Productivo). Segmentos: Productivo,
  Microcrédito, Inversión Pública y Consumo; Vivienda solo hasta 2021. Las 3 están
  curadas en `seeds/banco_maestro.csv` con código `BCE_<ruc>`, así que no dependen de que
  BCE cargue primero. El Boletín cargado solo trae bancos privados: Banca Pública no
  tiene contra qué conciliarse.
- **Identidad**: CAPCOL no trae RUC. El nombre crudo se resuelve con
  `seeds/banco_crosswalk.csv` → `banco_codigo` (ver `docs/mantenimiento_catalogos.md` §1).

## 2. BCE — Tasas de interés

Fuente: `https://contenido.bce.fin.ec/documentos/Estadisticas/SectorMonFin/TasasInteres/`.
Convención de nombres `t{s|m}{p|a}` = tasas + semanal/mensual + pasiva/activa. Solo se
integran los **semanales** (`tsp`, `tsa`); `tmp`/`tma` (mensuales) quedan fuera por
decisión.

### 2.1 `tsp_desde_200801.zip` (tasas pasivas / captaciones)

- Descarga directa; la etapa `bce` solo baja el archivo cuando el BCE publica una versión
  nueva. ZIP ~71 MB → CSV ~711 MB, ~3,1 M filas.
- CSV con `;`, coma decimal, `semana` en `DD/MM/YYYY` (semanal desde 2008-01-03).
- Columnas: `semana;ruc;razon_social;sector_financiero;tipo_entidad;tipo_segmento;instrumento_captacion;provincia;canton;plazo;monto_total;numero_operaciones;tasa_pasiva_efectiva;tasa_nominal`.
- **Universo completo del sistema financiero, sin filtrar** (~456 entidades): bancos
  privados y públicos, cooperativas (la gran mayoría), mutualistas, sociedades
  financieras y emisoras de tarjetas.
- `plazo`: buckets con prefijo ordinal (`a. MENOS DE 30 DIAS` … `g. MAS DE 360 DIAS`).
- Geografía: `provincia='S/N' ⟺ canton='NACIONAL'` siempre. Ahorro, monetarios,
  tarjetahabientes y reporto son 100% `NACIONAL`; plazo trae cantón real; antes de ~2015
  ningún instrumento trae cantón.

### 2.2 `tsa_desde_200801.zip` (tasas activas / colocaciones)

- ZIP ~123 MB → CSV ~1,75 GB, ~7,8 M filas, mismo formato que tsp.
- Columnas: iguales a tsp, con `segmento_credito` en lugar de `instrumento_captacion` y
  `tasa_activa_efectiva` en lugar de `tasa_pasiva_efectiva`.
- `segmento_credito`: 26 valores finos (incluye la terminología previa a la reforma
  JPRF de 2022, "Comercial", y las variantes "(SE)" del sector popular y solidario),
  agrupados en 7 segmentos normativos por `dim_subsegmento_credito.segmento_id`
  (`sql/16`, mapeo en `docs/data_dictionary.md`).

**Común a tsp y tsa**:
- `tipo_segmento` (14 valores) clasifica a la **entidad**, no al producto: banco
  grande/mediano/pequeño, cooperativas Segmento 1-5 / Sin segmento (JPRF-F-2023-074, por
  activos), mutualistas, y una categoría única para el resto. Cambia en el tiempo para
  una misma entidad. Desde 2025-01 el BCE rotula a las mutualistas `MUTUALISTAS` en vez de
  `SEGMENTO 1 MUTUALISTA`; el ETL homologa al segundo (`ALIAS_TIPO_SEGMENTO`, `sql/41`).
- `razon_social` cambia con los renombres; el **`ruc`** es la llave estable. Bancos
  privados → crosswalk curado; resto → auto-registro `BCE_<ruc>` con validación
  estructural del RUC.

### 2.3 Tasas máximas y referenciales (`TasasHistorico.htm`)

- Índice: `.../TasasInteres/TasasHistorico.htm`. HTML estático, una página por mes con
  URL predecible `TasasVigentes{MM}{YYYY}.htm` (un 404 en un mes se tolera).
  `extract/download_tasas_historicas.py`, `transform/parse_tasas_historicas.py`.
- **Grano mensual, nivel sistema** (no por entidad). 5 secciones:
  1. Activas máximas vigentes: 13 segmentos.
  2. Activas efectivas referenciales: los mismos 13 segmentos.
  3. Pasivas efectivas promedio por instrumento: 5 categorías (incluye `DEPÓSITOS
     MONETARIOS` agregado y Tarjetahabientes, armonizado a `FONDOS DE TARJETAHABIENTES`).
  4. Pasivas referenciales por plazo: 6 buckets, todos ya existentes en `dim_plazo`.
  5. Otras: TPR, TAR, Tasa Legal y Tasa Máxima Convencional.
- **Particularidades del parser** (cada una fue un bug real):
  - `pandas.read_html` aplica `thousands=','` aunque se pase `decimal=","`: hay que
    desactivarlo. Hasta 2022-03 el BCE usa punto decimal; el parser detecta el formato.
  - La `<table>` física de cada sección cambia entre años: el parser concatena todas y
    rastrea la sección fila por fila por texto de encabezado.
  - Hasta 2022-07 la sección de cartera se titula "ACTIVAS EFECTIVAS VIGENTES" (máximas y
    referenciales lado a lado).
  - Alias de nombre: "Productivo Corporativo" → `PRODUCTIVO - CORPORATIVO`; "Microcrédito
    Acumulación Ampliada/Simple" (sin "de", 2009-2015) → la forma con "de"; se limpian
    dobles espacios y notas al pie ("Consumo *").
  - Se ignoran a propósito la sección 2018-2019 "solo para el sector financiero popular
    y solidario" y la de "pasivas máximas para inversiones del sector público".
  - Un segmento o categoría fuera del catálogo registra ERROR (no se descarta en silencio).
- **Fuera de alcance**: antes de 2009-07 (segmentos que ya no existen en el catálogo) y
  2009-09 (tabla irregular, `_TASAS_HISTORICAS_EXCLUIDAS`).

## 3. Superbancos — Boletín Financiero Mensual (Balance y PyG)

- **URL**: `https://www.superbancos.gob.ec/estadisticas/portalestudios/bancos/`. Mismo
  plugin que CAPCOL (Playwright). Carpeta `Año {YYYY}` (2009-2026) con archivos
  `{N}. BOLETIN BANCOS {MES} {YYYY}.zip` → `FINANCIERO MENSUAL BANCA PRIVADA {YYYY}_{MM}.xlsx`.
  Solo bancos privados; se carga desde 2021-01 por decisión de alcance.
- **12 hojas**; se cargan `BALANCE` y `PYG`:
  - Encabezado real en la fila 8: `CÓDIGO`, `CUENTA` y una columna por banco, en
    **miles de USD** (el ETL multiplica por 1000).
  - Formato ancho con 9 columnas de agregado que no son bancos y se excluyen por lista
    explícita (`BANCOS PRIVADOS GRANDES/MEDIANOS/PEQUEÑOS`, `TOTAL BANCOS PRIVADOS`, los 4
    `BANCOS PRIVADOS <segmento>` y `BANCA MÚLTIPLE`).
  - Los nombres de banco usan el mismo formato `BP <NOMBRE>` que CAPCOL (salvo espacios
    dobles): mismo crosswalk.
  - Plan de cuentas jerárquico (Catálogo Único de Cuentas: 1 → 2 → 4 → 6 dígitos). Las
    filas de sección (`ACTIVO`…) tienen `CUENTA` sin `CÓDIGO` y se saltan.
- **No se cargan**: `RK` (ranking por banco), `INDICADORES` (48 indicadores, catálogo en
  `docs/metricas_financieras.md`, recalculables desde `fact_balance`/`fact_pyg`), `MET`
  (de ahí sale `dim_cuenta_contable.grupo_met`) y las versiones porcentuales.
- **Concilia con CAPCOL**: cartera CAPCOL vs. `14 − 1499` mediana ~0%; depósitos CAPCOL
  vs. `21` siempre algo por debajo (-0,5% a -1,1%) porque CAPCOL no tiene 5 sub-cuentas de
  `21` (`docs/gobernanza_datos.md`, huecos conocidos).

## 4. SEPS — Cooperativas de Ahorro y Crédito y Mutualistas

Fuente: `https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/`, descarga directa
`?sdm_process_download=1&download_id=NNNN` (plugin "Simple Download Monitor", sin
Playwright). Los `download_id` no siguen un patrón: los de 2021-2026 están fijos en
`config/sources.py`, y los de un año nuevo se leen de la página del portal
(`download_seps.descubrir_download_ids`). Código:
`extract/download_seps.py`, `transform/parse_seps.py`, `pipeline.py::load_seps`; linaje
en `docs/linaje_datos.md` §7.

### 4.0 Diferencias de criterio y conciliación (leer antes de comparar)

Saldos SEPS vs. sus propios estados financieros, por entidad × mes (2021-2025): depósitos
vs. cuenta `21` mediana 0,0000% (99%+ dentro de ±0,5%); cartera vs. `14 − 1499` mediana
0,0000% (92-94% dentro de ±0,5%). La conciliación se evalúa sola en cada `actualizar`
(`sql/39`, `benchmark-bancos conciliar`). Dos desviaciones están explicadas y **no se
corrigen**, porque reflejan cómo reporta la fuente:

- **Mutualistas: la cartera incluye la vendida al fideicomiso.** Pichincha y Azuay venden
  cartera VIS/VIP a un fideicomiso (cuenta `1619`) y siguen administrándola; sale de la
  cuenta 14 pero el reporte la sigue incluyendo, sin distinguirla, así que no se puede
  separar por cantón. Sobre `14 − 1499` quedan +44,5% y +34,0%; sumando las cuentas de
  orden `740175`/`740170` bajan a +1,0% y -1,95%. En mutualistas, `fact_saldo_cartera`
  significa "cartera originada y administrada"; para comparar contra contabilidad usar
  `14 − 1499 + 7401{70,75}`. Las cooperativas con cartera administrada no la incluyen.
- **Cooperativas emisoras de tarjetas: el consumo excluye tarjetas.** La base mensual SEPS
  rotula su cartera "cuenta 14, excepto tarjetas de crédito"; el EEFF las incluye en
  `1402`. Las 212 entidades no emisoras concilian consumo a 0,000%; las 11 emisoras quedan
  en -3,6% (JEP -13,3%, OSCUS -10,0%, Policía Nacional -8,4%). El faltante agregado
  (~230-270 M USD por mes) es estable frente a la base SEPS de tarjetas (sin RUC). La
  cartera de consumo de los bancos (CAPCOL) **sí** incluye tarjetas: no son comparables
  uno a uno.

`OPERACIONES CONTINGENTES` no es cartera de la cuenta 14 y se excluye (1,4 M USD en 2023,
30,3 M en 2024 y 9,7 M en 2025).

### 4.1 Archivos

Para cada tema la SEPS publica dos familias; se usan los *Reportes* (con RUC) y el EEFF:

| Tema | Archivo | ¿RUC? | Grano | Uso |
|---|---|---|---|---|
| Depósitos | `{año}-CAP.zip` → `Boletin_captaciones_*_{S1,S2,S3,Mut}.xlsm`, hoja `Base_captaciones` | Sí | fecha × entidad × cantón × tipo de depósito × estado de operación | `staging.depositos` |
| Cartera | `{año}-COL.zip` → `Reporte_colocaciones_*_{S1,S2,S3,MUT}.xlsm`, hojas `Base_colocaciones*` | Sí | fecha × entidad × cantón × subtipo × origen × estado × clase × actividad | `staging.cartera` |
| Estados financieros | `{año}_EEFF-Men.zip` → TSV | Sí | fecha × entidad × cuenta (1, 2, 4 y 6 dígitos), USD completos | `staging.boletin_balance`/`boletin_pyg` |
| Bases de datos | `*-CAP-Men`, `*-COL-MEN` (TSV, hasta 11 GB) | **No** | + parroquia y demografía | Fuera de alcance |

- La "colocaciones" de la SEPS **son saldos** (por vencer, no devenga, vencida, total):
  la misma foto de stock que CAPCOL, no desembolsos. Sumar los 3 `ESTADO OPERACIÓN` de
  depósitos (NUEVA / VIGENTE / RENOVADA) no duplica: son una partición del stock.
- El archivo anual se republica cada mes: cada descarga cubre el año completo publicado.
- Variaciones de formato absorbidas por el parser:
  - Los ZIP usan Deflate64: `zipfile` no los abre, se usa `unzip -p` / `7z`.
  - Coma decimal y sin separador de miles.
  - 2021: el ZIP de cartera trae dos juegos (`abr_2021`, ene-abr con la segmentación
    previa a mayo 2021, y `dic_2021`).
  - 2023: el archivo de S1 se llama `_SG1`.
  - El EEFF 2021 usa `;`, encabezados con `_` y BOM; el decimal pasa de `.` a `,` en 2025.
  - Desde 2025 la cartera de S1 viene partida por semestre en dos hojas del mismo `.xlsm`:
    `Base_colocaciones` (jul-dic) y `Base_colocacionesISEM` (ene-jun, con la fecha como
    serial de Excel). Se excluye la hoja auxiliar `Base_para_actual`.
- Segmentos 4 y 5 reportan trimestral, con cuentas a 4 dígitos: fuera de alcance.

### 4.2 Vocabulario e identidad

- **Identidad**: RUC nativo en cada fila → `BCE_<ruc>`, la misma fila de `dim_entidad` que
  registra BCE; las entidades nuevas se auto-registran (`upsert_banco_maestro_ruc()`,
  común a BCE y SEPS). CONAFIPS y Caja Central FINANCOOP son `ENTIDAD DE SEGUNDO PISO`
  (`sql/29`). `tipo_entidad` sale del sufijo del archivo (`S1`-`S3` → `COOPERATIVA`,
  `Mut` → `MUTUALISTA`).
- **Tipo de depósito** (4): plazo, restringidos y garantía ya existían; `DEPÓSITOS A LA
  VISTA` es una categoría propia (`sql/30`), no un alias de ahorro o monetarios. El
  `.xlsm` no trae plazo: `plazo_id` NULL.
- **Subtipo de crédito** (7) → `dim_segmento_credito`: consumo, microcrédito, productivo y
  educativo directos; `INMOBILARIO` (sic) → `INMOBILIARIO`; `VIVIENDA DE INTERÉS SOCIAL Y
  PÚBLICO` → `VIVIENDA DE INTERÉS PÚBLICO`; `OPERACIONES CONTINGENTES` se excluye.
- `REGION` (`AMAZONIA`/`INSULAR`) se ignora y se deriva de la provincia; `LINEA CREDITO`
  viene vacía. Origen, clase y actividad económica se suman al grano (no se modelan como
  dimensión).
- **EEFF**: el mismo Catálogo Único que el Boletín. Los códigos compartidos conservan la
  descripción de Superbancos; los solo-SEPS (incluidas cuentas de orden 6 y 7) entran
  `AUTO_INGRESADO`. `1499` viene negativo, como en Superbancos. No se cargan saldos 0 o
  vacíos (~70% del archivo).
