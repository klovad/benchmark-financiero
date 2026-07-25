# Glosario de cuentas (Catálogo Único — Balance y PyG)

Capa conceptual de la documentación de indicadores. Este documento explica qué significa
cada cuenta contable relevante y define los "bloques de construcción" con nombre propio
que cualquier catálogo de indicadores puede reutilizar — el catálogo oficial de 48 CAMEL
(`metricas_financieras.md`), el catálogo `IND_NN` del Excel de Financiero
(`indicadores_excel_bcos_coop.md`), o uno nuevo que se necesite mañana. La implementación
de cada bloque vive **una sola vez**, como vista SQL, en
[`sql/18_glosario_cuentas_views.sql`](../sql/18_glosario_cuentas_views.sql) — los
catálogos de indicadores deberían *citar* esas vistas, no reimplementar la lógica de
cuentas contables cada vez que se documenta un ratio nuevo.

## 1. Cómo está organizado el Catálogo Único de Cuentas

- Código **jerárquico**: el primer dígito es la sección; cada dígito adicional profundiza
  un nivel. `dim_cuenta_contable.nivel` = longitud del código.
- `dim_cuenta_contable.reporte` distingue BALANCE de PYG — el mismo código numérico puede
  significar cosas distintas en cada uno (llave natural real = `(reporte, codigo)`); en la
  práctica no hay ambigüedad al consultar porque `fact_balance`/`fact_pyg` ya están
  scoped a su propio universo de `cuenta_id`.
- Una cuenta "padre" (ej. `14`) normalmente ya trae el saldo consolidado de sus hijas tal
  como lo entrega el boletín — no hay que sumar manualmente, salvo que el nivel padre
  falte (caso documentado: PyG código `4`, ver §4.6).

| Sección (1er dígito) | Nombre | Naturaleza |
|---|---|---|
| `1` | ACTIVO | Balance |
| `2` | PASIVO | Balance |
| `3` | PATRIMONIO | Balance |
| `4` | GASTOS | PyG |
| `5` | INGRESOS | PyG |
| `6` | CONTINGENTES | Balance (fuera de balance) |
| `7` | CUENTAS DE ORDEN | Balance (fuera de balance) |

---

## 2. Cuentas clave — ACTIVO (sección `1`)

| Código | Nombre | Qué es, en una línea |
|---|---|---|
| `1` | TOTAL ACTIVO | Suma de todo lo que el banco posee |
| `11` | FONDOS DISPONIBLES | Caja + depósitos en BCE/bancos — el activo más líquido |
| `13` | INVERSIONES | Portafolio de inversión (bruto) |
| `1399` | (Provisión para inversiones) | Contra-cuenta de `13`, siempre negativa en el saldo |
| `14` | CARTERA DE CRÉDITOS | El activo más grande de cualquier banco — todos los préstamos otorgados, brutos |
| `1499` | (Provisión para incobrables) | Contra-cuenta de `14`, siempre negativa — "el colchón" contra pérdidas esperadas de cartera |
| `1401`–`1408`, `1473` | Cartera por segmento, "por vencer" | Productivo, Consumo, Inmobiliario, Microcrédito, Vivienda interés público, Educativo — la parte de la cartera que **está al día** |
| `1425`–`1432`, `1479` | Cartera "que no devenga intereses", por segmento | Cartera en mora temprana — dejó de generar interés contable pero aún no se considera vencida |
| `1449`–`1456`, `1485` (y variantes refinanciada/reestructurada) | Cartera "vencida", por segmento | Cartera en mora confirmada |
| `18` | ACTIVO FIJO | Propiedad, planta y equipo |

**Bloque — `cartera_bruta`** (`14 − 1499`): denominador de casi cualquier ratio de calidad
de cartera. Vista: `marts.vw_cartera_bruta` (grano banco × fecha).

**Bloque — `cartera_improductiva`**: no es una sola cuenta. Es la suma de **todas** las
cuentas nivel-4 bajo `14` (excluyendo `1499`) cuyo nombre contiene "QUE NO DEVENGA
INTERESES" o "VENCIDA" y **no** contiene "POR VENCER" — cubre los ~40 códigos que
resultan de cruzar 7 segmentos × varios estados (normal, refinanciada, reestructurada,
COVID). Usar el patrón de texto, no una lista de códigos a mano (queda incompleta al
agregarse un segmento nuevo). Vistas: `marts.vw_cartera_improductiva` (total) y
`marts.vw_cartera_improductiva_segmento` / `marts.vw_cartera_bruta_segmento` (por
segmento, para morosidad desagregada).

---

## 3. Cuentas clave — PASIVO (sección `2`)

| Código | Nombre | Qué es |
|---|---|---|
| `2` | TOTAL PASIVO | Todo lo que el banco debe |
| `21` | DEPÓSITOS CON EL PÚBLICO | Captación — el pasivo más grande de cualquier banco |
| `2101`, `210105`, `210130` | Depósitos monetarios (cuenta corriente) | Fondeo a la vista |
| `210135` | Depósitos de ahorro | Fondeo a la vista, distinto producto |
| `210140` | Depósitos a plazo | Fondeo con vencimiento pactado |
| `210305`, `210310` | Depósitos a plazo, bandas cortas (1–30, 31–90 días) | Sub-cuentas de `21` usadas para medir el fondeo de **corto plazo** específicamente |
| `26` | OBLIGACIONES FINANCIERAS | Deuda con otras instituciones (no depósitos del público) |
| `2511` | (Provisión de aceptaciones/contingentes) | Contra-cuenta relacionada a `6401`–`6403` |

**Bloque — `depositos_corto_plazo`** (`2101 + 210305 + 210310`): denominador del índice
de liquidez tal como lo usa el Excel (`IND_40`) — **no** confundir con solo
`2101 + 210310` (error real que se cometió en una primera pasada de este mismo proyecto,
corregido y verificado). Vista: `marts.vw_depositos_corto_plazo`.

---

## 4. Cuentas clave — PATRIMONIO, INGRESOS, GASTOS (secciones `3`, `4`, `5`)

| Código | Nombre | Qué es |
|---|---|---|
| `3` | TOTAL PATRIMONIO | Capital propio del banco |
| `3101` | Capital pagado | Aporte de los accionistas |
| `3603` / `3604` | Utilidad / Pérdida del ejercicio | Resultado acumulado del año en curso, dentro de patrimonio |
| `5` | TOTAL INGRESOS | Todo lo que el banco generó en el período |
| `51` | Intereses y descuentos ganados | Ingreso financiero — el "core" del negocio bancario |
| `4` | TOTAL GASTOS | Todo lo que el banco gastó — **ver nota de hueco de datos, §4.6** |
| `41` | Intereses causados | Lo que el banco paga por captar (costo de fondeo) |
| `44` | Provisiones (gasto) | Gasto por constituir provisión de cartera/contingentes ese período |
| `4402` | Gasto provisión de cartera | Sub-cuenta específica de `44` |
| `45` | Gastos de operación | Personal, honorarios, servicios — el "costo de operar el banco" |
| `48` | Impuestos y participación trabajadores | Gasto no operativo |

### 4.6 Hueco de datos conocido: PyG código `4`
`fact_pyg` **no trae fila para el código `4`** (TOTAL GASTOS) a nivel 1 — solo `5` (TOTAL
INGRESOS) existe como fila literal. Es un hueco del parser o de la estructura fuente del
boletín (a diferencia de BALANCE, que sí trae `1`/`2`/`3`). **Workaround verificado**:
sumar las 8 cuentas nivel-2 hijas reproduce el total exacto. Vista:
`marts.vw_pyg_total_gastos`.

**Bloque — `utilidad_acumulada`** (`ingresos(5) − total_gastos`, usando el workaround de
arriba, no `codigo='4'` directo): utilidad **YTD del año en curso**, no la del mes
individual. Vista: `marts.vw_utilidad_acumulada`.

**Bloque — `utilidad_anualizada`** (`utilidad_acumulada × (12 / mes_de_corte)`): proyecta
la utilidad YTD a un equivalente de 12 meses. Vista: `marts.vw_utilidad_anualizada`.

---

## 5. Bloques que combinan Balance + PyG o cruzan periodos (series de tiempo)

**Bloque — `activo_promedio_ytd` / `patrimonio_promedio_ytd`**: promedio de los saldos de
**fin de cada mes** de la cuenta `1` (activo) o `3` (patrimonio), desde **diciembre del
año anterior** hasta el mes de corte (inclusive) — *year-to-date de saldos fin de mes*,
no un promedio de 2 puntos (mes actual + mes anterior). Denominador correcto de
cualquier ratio de rentabilidad (ROA, ROE) que se anualice contra un balance promedio.
Vistas: `marts.vw_activo_promedio_ytd`, `marts.vw_patrimonio_promedio_ytd`.

---

## 6. Qué NO cubre este documento (fuera de alcance, documentado en otro lado)

- **`grupo_met`** (agrupación funcional de la hoja `MET`, usada por el catálogo CAMEL
  oficial): tiene un bug conocido (cuenta `14` sin etiquetar) — ver
  `metricas_financieras.md`. Los bloques de este glosario se basan en `codigo`, no en
  `grupo_met`, así que no heredan ese bug.
- **Patrimonio Técnico, Castigos, Impuesto a la Renta**: cadena de cuentas que sí se
  resuelve a nivel de código simple, pero las hojas que la consumen en el Excel dependen
  de piezas que no están en este data mart (activos ponderados por riesgo). No
  documentado aquí.
- **Tasas de interés efectivas** (`Interes`/`Capital Prom` del Excel, o cualquier "tasa"):
  no se derivan de `fact_balance`/`fact_pyg` — vienen de BCE
  (`fact_colocaciones_cartera`/`fact_captaciones_depositos`). Glosario aparte si se
  necesita (pendiente).

---

## Cómo usar este documento al escribir un ratio nuevo

Un ratio nuevo se documenta **componiendo** bloques de este glosario y sus vistas, no
redefiniendo la lógica de cuentas. Ejemplo — "cartera bruta sobre activos totales":

```sql
SELECT
    b.cartera_bruta / a.total_activos AS cartera_sobre_activos
FROM marts.vw_cartera_bruta b
JOIN (
    SELECT banco_id, fecha_id, SUM(saldo_usd) AS total_activos
    FROM marts.fact_balance f
    JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
    WHERE cc.reporte = 'BALANCE' AND cc.codigo = '1'
    GROUP BY banco_id, fecha_id
) a ON a.banco_id = b.banco_id AND a.fecha_id = b.fecha_id;
```

en vez de repetir la definición completa de `cartera_bruta` (14 − 1499, con sus reglas)
cada vez que un documento nuevo necesita el mismo concepto.

**Nota de alcance**: las vistas de `sql/18_glosario_cuentas_views.sql` no filtran por
`tipo_entidad` — hoy `fact_balance`/`fact_pyg` solo traen bancos privados por diseño del
Boletín de origen (ver `docs/data_dictionary.md`), así que no hace falta. Si esa fuente
algún día trae otros tipos de entidad, unir contra `dim_banco.tipo_entidad` en el
consumidor, no en estas vistas (mantenerlas como bloques puros, sin opinión de
segmentación).
