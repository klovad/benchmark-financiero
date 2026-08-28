# Prototipo de diseño Power BI — tema "Libro Mayor", personalización y plantilla de página

> **Esto es un prototipo/plantilla, no un entregable de negocio.** Vive en un proyecto
> `.pbip` separado (`powerbi/prototipo-diseno-bi.*`) y **no toca** el reporte productivo
> (`powerbi/benchmark-cartera-depositos.*`, sus 5 páginas ni sus 17 medidas). Demuestra un
> tema visual, tres patrones de personalización y una página de ejemplo con datos reales de
> `marts.*` (CAPCOL, solo `fact_saldo_cartera`/`fact_saldo_depositos` + `dim_banco`/
> `dim_fecha`) — no es un build-out multi-página de todas las líneas de negocio.

## 0. Segundo intento — qué cambió y por qué

La primera versión de este prototipo (paleta `#0F4C81` + Okabe–Ito literal sobre blanco,
Segoe UI en las 8 clases de texto, slicers de lista sin ningún estilo propio) fue
**rechazada**: leía como el tema base de Power BI Desktop (`CY26SU02`) con otros números
hex, no como un punto de vista de diseño real, y los controles de personalización eran
slicers por defecto con solo el título sobreescrito.

Esta versión — **"Libro Mayor"** — parte de un concepto concreto anclado en el dominio
(benchmark de mercado bancario, concentración/HHI, posiciones entre bancos): un lienzo
oscuro tipo bóveda/terminal de mercado, un único acento de marca color bronce/latón, y
cifras en tipografía monoespaciada para que los números de un KPI o de una tabla alineen
como en un balance contable real. La maqueta HTML completa —paleta con hex reales,
tipografía real, layout con nombres de campo/medida reales, y los 3 controles rediseñados
con sus estados (reposo/hover/seleccionado)— está publicada aquí:

**→ [Artifact: Libro Mayor](https://claude.ai/code/artifact/b11b6df0-3482-4d53-9bc5-317a5916d1cf)**

Esa maqueta es el entregable que hay que revisar primero — el `.pbip` descrito abajo
implementa lo mismo hasta donde el formato TMDL/PBIR lo permite (ver §7 para las
divergencias explícitas entre la maqueta y lo que Power BI Desktop va a renderizar).

## 1. Por qué un `.pbip` separado y no una página nueva en el reporte productivo

El tema personalizado se registra en `report.json` vía `themeCollection.customTheme` +
`resourcePackages` (tipo `RegisteredResources`). Esa propiedad es **a nivel de todo el
reporte**, no por página — el formato PBIR no tiene un mecanismo de "tema por página".
Registrar el tema nuevo en el `report.json` del proyecto productivo habría re-pintado
silenciosamente las 5 páginas existentes, violando el requisito explícito de no tocarlas.
Por eso el prototipo vive en su propio `.pbip`:

```
powerbi/prototipo-diseno-bi.pbip
powerbi/prototipo-diseno-bi.Report/          (tema + 1 página de ejemplo)
powerbi/prototipo-diseno-bi.SemanticModel/   (subconjunto de marts.*, Import, mismo Postgres)
```

El modelo semántico del prototipo importa un subconjunto deliberadamente chico de
`marts.*` — `dim_fecha`, `dim_banco`, `fact_saldo_cartera`, `fact_saldo_depositos` — con
la misma cadena de conexión PostgreSQL que usa `benchmark-cartera-depositos.SemanticModel`
(mismas medidas base, mismos nombres de columna). No se reutiliza el modelo semántico
productivo porque las 3 tablas de parámetros desconectados (sección 5) son aditivas al
modelo y el objetivo era mantener el prototipo completamente aislado, no solo la capa de
reporte.

## 2. Paleta de color — "Libro Mayor"

Definida en
`powerbi/prototipo-diseno-bi.Report/StaticResources/RegisteredResources/LibroMayor.json`
(nombre de tema `LibroMayor`, reemplaza al archivo `PrototipoDisenoBI.json` de la primera
versión, que fue borrado), validada contra el
[Report Theme JSON Schema 2.156](https://github.com/microsoft/PowerBI-Desktop-Samples/tree/main/Report%20Theme%20JSON%20Schema)
de Microsoft (ver §7).

| Rol | Hex | Contraste vs. lienzo (`#14171C`) | Uso |
|---|---|---|---|
| Lienzo (`background`) | `#14171C` | — | Canvas de página — bóveda/terminal, no blanco |
| Tarjeta (`secondaryBackground`) | `#1B2029` | — | Fondo de cada `visualContainerObjects.background` |
| Tarjeta elevada (`backgroundNeutral`) | `#232836` | — | Reservado para paneles secundarios |
| Primario/marca (`tableAccent`) | `#C9A24B` | 7.49:1 | KPI callout, hairline de tarjetas, checkmark de selección — **único** rol de marca, nunca en la categórica |
| Texto principal (`foreground`) | `#F3EEE3` | 15.53:1 | Texto de cuerpo, labels — pergamino, no blanco puro |
| Texto secundario | `#A79E8C` | 6.77:1 | Subtítulos, `dataTitle` |
| Texto terciario | `#7C7566` | 3.93:1 | Notas al pie / hints (no requiere el piso de 4.5:1 de texto normal) |
| Positivo (`good`) | `#4FAE7D` | 6.57:1 | MoM/YoY/vs-benchmark positivo — **el mismo verde en todo el reporte** |
| Negativo (`bad`) | `#D9714F` | 5.50:1 | MoM/YoY/vs-benchmark negativo — **el mismo rojo/terracota en todo el reporte** |
| Neutral | `#8B8371` | 4.78:1 | Variación ~0%, estados sin cambio |
| Divergente: máximo/centro/mínimo | `#4FAE7D` / `#3A3F49` / `#D9714F` | — | Escala de desviación vs. benchmark — reutiliza el par positivo/negativo, centro en piedra neutra (no blanco, este es un tema oscuro) |
| Categórica 1–8 (orden fijo) | `#407AEA` `#9E7E00` `#008BDB` `#D05500` `#0096C4` `#7E68E3` `#009DA7` `#A459CC` | 4.4–7.8:1 sobre lienzo | Series por banco — **validada computacionalmente**, ver §2.1 |
| Hipervínculo / visitado | `#6FB3D9` / `#B08FE0` | 7.81:1 / 6.72:1 | — |

### 2.1 Por qué esto no es "Okabe–Ito con otro nombre"

La categórica se generó y **validó con la skill `dataviz`** (`scripts/validate_palette.js`
del proyecto, no a mano):

1. Se restringieron los 8 tonos casi enteramente al **arco frío** (teal→plum, ~165°–320°
   en OKLCH) con solo **2 acentos cálidos** (oro `#9E7E00`, ámbar `#D05500`) — la regla de
   diseño explícita es que ningún banco compita visualmente con el bronce de marca
   (`tableAccent`) ni con el verde/rojo semántico. Esto es más estricto que la paleta
   anterior, que solo excluía verde/rojo puro y dejaba el resto del círculo libre.
2. Búsqueda por fuerza bruta de permutaciones (`scratchpad/search_palette3.mjs`, no
   versionado — reproducible con la fórmula de `dataviz/references/color-formula.md`)
   sobre una grilla de L/C dentro de la banda categórica oscura (L 0.48–0.67, C ≥ 0.10),
   evaluando cada candidato con `validate()` del validador real.
3. Resultado que pasa las 5 verificaciones automáticas — **no eyeballed**:

   ```
   Lightness band:      todos los 8 dentro de L 0.48–0.67
   Chroma floor:        todos los 8 >= 0.10
   CVD separation:      peor par adyacente #7E68E3↔#0096C4 ΔE 8.5 (deutan) · tritan 9.7  [pass, meta >=8]
   Normal-vision floor: peor par adyacente #7E68E3↔#0096C4 ΔE 16.0 (normal)               [pass, piso >=15]
   Contrast vs surface: los 8 >= 3:1 sobre #14171C
   ```

4. **Límite honesto, no escondido**: como cualquier paleta categórica de 8 tonos (incluida
   la paleta de referencia de la propia skill `dataviz`), no todos los **28 pares
   no-adyacentes** están garantizados distinguibles bajo daltonismo — el propio validador
   documenta que ningún orden de 8 colores pasa `--pairs all` más allá de los primeros 3–4
   slots. La mitigación real: los dos gráficos que usan esta categórica
   (`v08BarBenchmarkBanco`, un `clusteredBarChart`) llevan `dim_banco[banco]` como
   etiqueta del eje de categoría — el color nunca es el único canal de identidad del
   banco, siempre hay texto al lado.

### 2.2 Secuencial y qué no tiene campo de tema global

No existe un campo de tema para "rampa secuencial de un color" — se configura por visual
en Desktop (Format > Data colors > escala). Recomendación para saldos/magnitud/heat de
HHI: una rampa de un solo matiz del primario, de `#3A2F14` (oscuro, casi-lienzo) a
`#C9A24B` (bronce pleno) — en un tema oscuro la rampa "recede hacia la superficie" en el
extremo bajo en vez de aclarar hacia blanco, siguiendo la misma lógica de ancla-invertida
en modo oscuro que usa la skill `dataviz` para sus propias rampas.

## 3. Tipografía

| Clase (`textClasses`) | Fuente | Peso (`fontWeight`) | Tamaño | Uso |
|---|---|---|---|---|
| `largeTitle` | Georgia | bold | 20pt | Título de página (text box) |
| `title` | Georgia | bold | 13pt | Título de contenedor de cada visual |
| `header` | Segoe UI | 600 | 12pt | Encabezados de sección |
| `label` | Segoe UI | normal | 10pt | Ejes, leyendas, texto de tabla |
| `boldLabel` | Segoe UI | bold | 10pt | Totales, encabezados de tabla |
| `smallLabel` | Segoe UI | normal | 9pt | Notas al pie, texto secundario |
| `smallDataLabel` | **Consolas** | normal | 9pt | Etiquetas de dato pequeñas / ticks de eje — cifras tabulares |
| `callout` | **Consolas** | bold | 26pt | Número grande de las tarjetas KPI |
| `dataTitle` | Segoe UI | 600 | 11pt | Subtítulo de tarjeta |

Tres familias, un rol cada una — no "Segoe UI en las 8 clases" como en la primera versión:

- **Georgia** (serif) para títulos: un documento financiero formal tiene autoridad de
  serif, no de UI sans. Fuente web-safe estándar (Windows y macOS la traen).
- **Consolas** (monoespaciada) **solo** para cifras — KPI callouts y etiquetas de dato.
  Da alineación tabular real de dígitos (como un balance contable) y refuerza el concepto
  "libro mayor/terminal". Ships con Windows/Office — válido para el flujo documentado de
  este proyecto (Desktop en Windows). Confirmado en el schema real
  (`reportThemeSchema-2.156`, definición `textClass`) que **`fontWeight` es una propiedad
  de primer nivel** (`{"fontFace","fontSize","fontWeight","color"}`) — a diferencia de la
  primera versión, que dependía de que "Segoe UI Semibold" existiera como familia
  registrada aparte; aquí el peso se declara explícitamente y no depende de que exista una
  variante de familia con ese nombre exacto.
- **Segoe UI** (sans) para todo lo demás — rótulos, ejes, controles. Sigue siendo la
  familia más legible en texto pequeño y la que Power BI Desktop usa para su propio chrome,
  pero ahora es un rol de apoyo, no la única voz tipográfica del reporte.

**Riesgo igual al de la versión anterior**: si el `.pbip` se abre fuera de Windows/Office,
Georgia/Consolas podrían no estar instaladas y Desktop hace fallback a una fuente del
sistema — aceptable porque Desktop en Windows es el flujo documentado en `README.md`.

## 4. Layout de la página prototipo

Sin cambios respecto a la primera versión — el layout de 3 franjas ya era razonable, el
problema era el tema, no la composición. Página `page-prototipo-diseno` (1280×720,
`FitToPage`):

```
┌─────────────────────────────────────────────────────────────────────┐
│  Fila 1 (y=20-110): controles de personalización                     │
│  [ Métrica ]   [ Periodo ]   [ Ventana ]                              │
├─────────────────────────────────────────────────────────────────────┤
│  Fila 2 (y=130-290): tarjetas KPI                                    │
│  [ Métrica sel. (título dinámico) ] [ Morosidad ] [ HHI ] [ Var. YoY ]│
├─────────────────────────────────────────────────────────────────────┤
│  Fila 3 (y=310-700): benchmark + tendencia                           │
│  [ Barras: banco × métrica seleccionada ] [ Línea: tendencia × ventana]│
└─────────────────────────────────────────────────────────────────────┘
```

Grid de 20px de margen y separación entre columnas (`x = 20, 340, 660, 980`), alturas
consistentes por fila (90 / 160 / 390).

Cada uno de los 9 visuales ahora lleva `visualContainerObjects.background` (color
`#1B2029`), `.border` (color `#C9A24B`, `radius` 6, `width` 1) y `.dropShadow.show = false`
— la "tarjeta con hairline de bronce, sin sombra pesada" de la maqueta HTML. Esto **no**
duplica el tema (el tema no tiene un rol de "fondo de tarjeta distinto del lienzo" —
`background`/`secondaryBackground` son roles separados, no equivalentes a un fondo de
contenedor por visual), así que no viola la regla de "nada de formato hardcodeado que ya
venga del tema" — es información que el tema estructuralmente no puede expresar.

## 5. Controles de personalización — rediseñados, no solo re-coloreados

Los 3 controles (selector de métrica, comparador de periodo, ventana de tendencia) siguen
siendo los mismos 3 patrones de la primera versión (siguen sirviendo a los mismos 3
visuales reales), pero ahora con **estados reales**, no solo un título distinto sobre un
slicer de lista por defecto:

### 5.1 Qué cambió en el `.pbip` de los 3 slicers (verificado contra el schema real)

Se inspeccionó `reportThemeSchema-2.156` (definición `visual-slicer`) para conocer las
cards de formato reales de un slicer: `general`, `header`, `items`, `selection`,
`selectionIcon` (entre otras). Cada uno de los 3 `visual.json` de slicer
(`v01SlicerMetrica`, `v02SlicerPeriodo`, `v03SlicerVentana`) ahora tiene:

```json
"objects": {
  "general":   [{ "properties": { "orientation": { "expr": { "Literal": { "Value": "1L" } } } } }],
  "header":    [{ "properties": { "show": { "expr": { "Literal": { "Value": "false" } } } } }],
  "selection": [{ "properties": { "strictSingleSelect": { "expr": { "Literal": { "Value": "true" } } } } }]
}
```

- **`orientation: 1` (Horizontal)** — el slicer ya no es una lista vertical por defecto;
  se dibuja como una fila, más cerca del look de "fila de chips" de la maqueta.
- **`header.show: false`** — el slicer ya no muestra su propio rótulo de campo (p. ej.
  "Metrica") duplicado encima del título del contenedor (`visualContainerObjects.title`,
  que ya dice "Métrica a comparar"); antes había dos títulos apilados.
- **`selection.strictSingleSelect: true`** — **esto es una corrección funcional real, no
  solo estética**: las 3 medidas de parámetro (`'Valor Metrica Base'`,
  `'Valor Metrica Periodo'`, `'Incluir En Ventana'`) usan
  `SELECTEDVALUE(...)`, que devuelve `BLANK()` si hay 0 o 2+ valores seleccionados. Sin
  `strictSingleSelect`, un usuario podía deseleccionar todo o multi-seleccionar con Ctrl y
  las medidas caerían silenciosamente al valor por defecto del `SWITCH` en vez de fallar
  visiblemente. Con `strictSingleSelect: true`, Desktop fuerza exactamente una selección
  en todo momento (arranca en la primera fila si no hay selección) — el slicer ahora se
  comporta como el toggle/segmented-control que la maqueta muestra, no como una lista
  libre.

### 5.2 Lo que el schema **no** expone (verificado, no asumido)

Se revisaron también las cards `items` (background/fontColor/fontFamily/textSize/bold) y
`selectionIcon` (color) del mismo schema. **No existe una propiedad JSON para forzar el
estilo "Tile"/píldora** (List ↔ Tile ↔ Dropdown ↔ Between) — ese toggle sigue viviendo
únicamente en Format pane > Slicer settings > Options > Style de Desktop, igual que en la
primera versión de este prototipo. Tampoco hay un color de "fondo de item seleccionado"
declarable por separado del resto — la única señal de selección expuesta en el schema es
`selectionIcon.color` (el color del check/marcador), que se dejaría en el bronce de marca
si se configura a mano en Desktop. Por eso **no** se hardcodeó `items.background`/
`fontColor` en el `.pbip` — habría duplicado colores que ya vienen del tema sin lograr el
efecto de "chip con relleno bronce cuando está seleccionado" que muestra la maqueta; ese
look específico solo se cierra en Desktop (ver §7).

### 5.3 Los mismos 3 patrones de datos (sin cambios de fondo)

- **Selector de métrica** (`Parametro Metrica`, `DATATABLE` con 2 filas: "Saldo Cartera" /
  "Saldo Depósitos") → `'Valor Metrica Base'` = `SWITCH(SELECTEDVALUE(...), ...)`.
- **Periodo** (`Parametro Periodo`, 2 filas) → `'Valor Metrica Periodo'` usa `EDATE` sobre
  la última fecha real (no `DATEADD`, porque `dim_fecha` deliberadamente no está marcada
  como tabla de fechas en este prototipo — ver §8).
- **Ventana** (`Parametro Ventana`, 4 filas) → `'Incluir En Ventana'` como filtro de nivel
  de visual `Advanced` sobre el gráfico de tendencia.
- **Título dinámico** (`'Titulo Dinamico Prototipo'`) enlazado vía
  `visualContainerObjects.title[0].properties.text.expr.Measure`.

## 6. Accesibilidad

- **Contraste de texto** (todos calculados, no estimados — fórmula WCAG relativa
  luminancia): `foreground` 15.53:1, `primary` 7.49:1, `good` 6.57:1, `bad` 5.50:1,
  `neutral` 4.78:1 sobre `#14171C` — **todos superan AA** (4.5:1 texto normal), una mejora
  real sobre la primera versión (`good`/`bad` rozaban 4.35–5.4:1 ahí). `foregroundNeutralTertiary`
  da 3.93:1, por debajo de 4.5 pero aceptable para texto terciario/hint (no sujeto al piso
  de texto normal).
- **Categórica**: ver §2.1 — validada con `dataviz/scripts/validate_palette.js`, no a
  mano. Los 8 tonos superan 3:1 sobre el lienzo oscuro (gráfico); el peor par adyacente da
  ΔE 8.5 (deutan, meta ≥8) y ΔE 16.0 en visión normal (piso ≥15).
- **Daltonismo**: a diferencia de la primera versión (que citaba Okabe–Ito como referencia
  pero no corrió una simulación real), esta paleta sí se validó con simulación real
  Machado–Oliveira–Fernandes 2009 (protanopía/deuteranopía) vía el validador de la skill
  `dataviz` — no es una referencia bibliográfica sin verificar, es un resultado numérico
  reproducible.
- **No hay variante clara/oscura**: los temas de Power BI Desktop no reaccionan al modo
  claro/oscuro del SO — es un lienzo fijo. "Libro Mayor" es deliberadamente oscuro-único
  (no tiene una variante clara), igual que la maqueta HTML (que documenta explícitamente
  por qué se queda en un solo tema en vez de adaptar a `prefers-color-scheme`).

## 7. Dónde el `.pbip` diverge de la maqueta HTML (léase antes de abrir Desktop)

La maqueta HTML es el diseño aprobado en espíritu; el `.pbip` lo implementa hasta donde el
formato TMDL/PBIR lo permite. Divergencias explícitas, no implícitas:

1. **Forma del slicer**: la maqueta muestra chips tipo píldora con relleno de marca cuando
   están seleccionados. El `.pbip` deja el estilo List/Tile como toggle de Desktop (§5.2)
   — lo que el JSON sí fuerza es orientación horizontal + selección única, no la forma
   exacta del control.
2. **Tipografía**: Georgia/Consolas en el navegador (maqueta) vs. el renderer de fuentes
   de Desktop (ClearType/DirectWrite) — peso e hinting se van a ver distintos, sobre todo
   en los 26pt del `callout`.
3. **Sombras y bordes**: `dropShadow.show=false` + `border` de 1px con `radius` 6 es lo que
   el schema permite fijar; no es pixel-a-pixel la sombra/blur que CSS puede hacer
   libremente en la maqueta.
4. **Gráfico de tendencia**: en la maqueta es una polyline SVG estática de ejemplo; en
   Desktop el `lineChart` real se dibuja desde datos de Postgres vía
   `'Valor Metrica Base'` y su geometría no va a coincidir con la curva ilustrativa.
5. **Las 3 medidas basadas en `EDATE`** no se pudieron evaluar con datos reales en este
   entorno (no hay motor DAX disponible) — los valores de KPI en la maqueta son
   ilustrativos.
6. **`strictSingleSelect` y `orientation`**: son propiedades declarativas verificadas
   contra el schema (§7.1 más abajo las lista en la tabla), pero su comportamiento
   interactivo real (¿fuerza selección al abrir? ¿la fila se ve realmente horizontal con 2
   valores?) solo Desktop lo confirma.

### 7.1 Qué se validó estructuralmente aquí vs. qué falta verificar en Desktop

**Validado con JSON Schema real (`jsonschema` 4.26, Python) contra los schemas publicados
en `developer.microsoft.com`/`microsoft/json-schemas` y `microsoft/PowerBI-Desktop-Samples`,
resolviendo automáticamente los `$ref` remotos (incluida la propia librería de resolución,
ver nota abajo):**

| Archivo | Schema | Versión usada |
|---|---|---|
| `Report/definition/report.json` | `report` | 3.3.0 (igual que el reporte productivo) |
| `Report/definition/pages/pages.json` | `pagesMetadata` | 1.1.0 |
| `Report/definition/pages/*/page.json` | `page` | 2.1.0 |
| `Report/definition/pages/*/visuals/*/visual.json` (9 archivos) | `visualContainer` → `visualConfiguration` → `formattingObjectDefinitions` | 2.9.0 → 2.3.0 → 1.5.0 |
| `Report/definition/version.json` | `versionMetadata` | 1.0.0 |
| `Report/definition.pbir` | `report/definitionProperties` | 2.0.0 |
| `Report/.platform`, `SemanticModel/.platform` | `gitIntegration/platformProperties` | 2.0.0 |
| `prototipo-diseno-bi.pbip` | `pbip/pbipProperties` | 1.0.0 |
| `SemanticModel/definition.pbism` | `semanticModel/definitionProperties` | 1.0.0 |
| `StaticResources/RegisteredResources/LibroMayor.json` | Report Theme JSON Schema | 2.156 (Microsoft, `PowerBI-Desktop-Samples`) |

Los 9 `visual.json` y el `report.json` también se revisaron a mano campo por campo
(`Entity`/`Property` de cada `field.Measure`/`field.Column`) contra los nombres reales en
el TMDL — **sin cambios respecto a la primera versión** en esos bindings, esta ronda solo
tocó `objects`/`visualContainerObjects` de formato, no las referencias de datos.

**Nota nueva — inconsistencia real en el schema publicado por Microsoft**: al resolver
`visualConfiguration/2.3.0/schema-embedded.json`, ese archivo declara internamente
`"$id": ".../schema.embedded.json"` (con punto) mientras está servido en la URL con guion
(`schema-embedded.json`) — un `$id` que no coincide con su propia ruta de publicación. Un
resolutor de referencias que confía en el `$id` declarado intenta re-resolver contra la
URL con punto y recibe 404. Se confirmó en vivo (`curl` a ambas variantes) y se resolvió
cacheando el documento bajo ambas URLs en el resolutor de validación
(`scratchpad/validate_pbip.py`, no versionado) — no es un error en este `.pbip`, es una
inconsistencia del lado de Microsoft entre el `$id` interno y la ruta de publicación real.

**Lo que solo Power BI Desktop puede confirmar (no verificable en este entorno sin UI):**
ver §7 arriba — forma real del slicer, renderizado de fuentes, comportamiento interactivo
de `strictSingleSelect`/`orientation`, y evaluación real de las 3 medidas `EDATE`-based.

## 8. Simplificaciones deliberadas del modelo semántico del prototipo

Sin cambios respecto a la primera versión:

- **No se marcó `dim_fecha` como tabla de fechas** — las medidas de periodo usan `EDATE`
  sobre la columna de fecha real en vez de `DATEADD`/inteligencia de tiempo.
- Si Desktop tiene activada "Detección automática de fecha y hora", puede generar sus
  propias tablas de calendario ocultas al abrir el `.pbip` — comportamiento inofensivo de
  Desktop, desactivable en Opciones > Carga de datos.
- El modelo del prototipo **no incluye** `dim_canton`/`dim_provincia`/
  `dim_segmento_credito`/`dim_categoria_deposito`/`dim_plazo` — subconjunto deliberado.

## 9. Referencia rápida: campos reales usados

Sin cambios respecto a la primera versión — esta ronda no tocó bindings de datos:

| Tabla | Campo | Tipo | Usado en |
|---|---|---|---|
| `dim_banco` | `banco` | columna | eje del gráfico de barras |
| `dim_fecha` | `fecha` | columna | eje del gráfico de tendencia |
| `fact_saldo_cartera` | `Morosidad % (Ultimo Mes)`, `HHI Cartera (Ultimo Mes)` | medida | tarjetas KPI |
| `fact_saldo_cartera` / `fact_saldo_depositos` | `Saldo Cartera`, `Saldo Depositos` (+ variantes) | medida | consumidas por `'Valor Metrica Base'` |
| `Parametro Metrica` | `Metrica`, `Valor Metrica Base`, `Valor Metrica (Ultimo Mes)`, `Titulo Dinamico Prototipo` | columna/medida | slicer, gráficos, título dinámico |
| `Parametro Periodo` | `Periodo`, `Valor Metrica Periodo`, `Variacion Metrica Periodo` | columna/medida | slicer, tarjetas |
| `Parametro Ventana` | `Ventana`, `Meses`, `Incluir En Ventana` | columna/medida | slicer, filtro de visual |

## 10. Cómo exportar un `.pbit` real desde este prototipo

Sin cambios — `.pbit` es un formato binario/ofuscado distinto de `.pbip`/TMDL/PBIR, no
hand-authorable con la disciplina del resto de este proyecto:

1. Abrir `powerbi/prototipo-diseno-bi.pbip` en Power BI Desktop.
2. Verificar que carga (credenciales de PostgreSQL local — ver `README.md` Quickstart).
3. **Archivo > Exportar > Guardar como plantilla de Power BI**.
4. Desktop genera el `.pbit` — estructura + consultas, sin datos importados.

## 11. Cómo abrir y probar el prototipo

```powershell
# mismas credenciales/DB que el reporte productivo (ver README.md Quickstart)
powerbi\prototipo-diseno-bi.pbip
```

No requiere ninguna migración de base de datos adicional — usa las mismas tablas
`marts.dim_fecha`, `marts.dim_banco`, `marts.fact_saldo_cartera`,
`marts.fact_saldo_depositos` que ya consume el reporte productivo.

**Al abrir, comparar contra la maqueta HTML**
(https://claude.ai/code/artifact/b11b6df0-3482-4d53-9bc5-317a5916d1cf) y anotar cualquier
divergencia no prevista en §7 — esa lista se hizo con la mejor información disponible sin
poder renderizar Desktop en este entorno, pero no reemplaza una revisión visual real.
