# Indicadores del Excel de Financiero (catálogo `IND_NN`)

Catálogo de los indicadores que hoy calcula `1.Benchmark BCOS_COOP 2026 MAR-26.xlsm`
(el reporte manual que usa el área de Financiero), reconstruido por ingeniería inversa de
la hoja `Formulas N` (solo lectura, `openpyxl`, `keep_vba=True`; el archivo nunca se
modificó). **Es un catálogo distinto** del oficial de 48 indicadores CAMEL de Superbancos
documentado en [`metricas_financieras.md`](metricas_financieras.md) — no reemplaza ese
documento, lo complementa. Mientras el catálogo de 48 usa `dim_cuenta_contable.grupo_met`
(agrupación funcional de la hoja `MET`), **el motor `IND_NN` del Excel nunca usa
`grupo_met`**: resuelve todo por `VLOOKUP` directo contra el código de cuenta contable
literal (`dim_cuenta_contable.codigo`). Por eso el bug conocido de `grupo_met` (la cuenta
`14 CARTERA DE CRÉDITOS` sin etiquetar — ver `metricas_financieras.md`) **no afecta** a
ninguno de los indicadores de este documento.

**Ver también**: [`glosario_cuentas.md`](glosario_cuentas.md) documenta a nivel conceptual
qué significa cada cuenta y define los bloques reutilizables (`cartera_bruta`,
`cartera_improductiva`, `depositos_corto_plazo`, `activo_promedio_ytd`, etc.) que las
fórmulas de este documento componen — implementados como vistas en
[`sql/18_glosario_cuentas_views.sql`](../sql/18_glosario_cuentas_views.sql). Este documento
se enfoca en el mapeo `IND_NN → fórmula` y su verificación contra el Excel; el glosario es
la referencia para el significado de cada cuenta.

## Cómo funciona el motor en el Excel

`Formulas N`/`Formulas N-1` (1650 filas × 70 columnas) resuelve 174 filas con código
`IND_NN` (~90 códigos distintos, algunos repetidos como actual/anterior). Cada fila es de
dos tipos:
- **Hoja (leaf)**: la columna de código es un literal numérico = código de cuenta del
  Catálogo Único. La fórmula es siempre un `VLOOKUP` directo contra `Balance N` (el
  balance de comprobación completo pegado a mano cada mes, cuentas 1–7 incluyendo P&G).
- **Nodo intermedio**: suma o resta de otras filas `IND_NN`, hasta 4–5 niveles de
  profundidad en cuentas de cartera.

De los 174, 97 son solo-balance, 51 solo-PyG, 13 mixtas, y 11 fuera de alcance (cadena
Patrimonio Técnico / Castigos / Impuesto a la Renta — no se cargan en este data mart).
**~93% son replicables** con `fact_balance` + `fact_pyg`.

**No confundir con `TASAS`** (hoja separada): `Interes`/`Capital Prom`, que alimentan la
tasa de cartera/fondeo del Excel, **no se calculan con fórmulas** — son valores pegados a
mano desde el Boletín de Tasas de Superbancos, con la segmentación del BCE. No son
reconstruibles desde `fact_balance`/`fact_pyg`; un indicador de tasa debe construirse
aparte desde `fact_colocaciones_cartera`/`fact_captaciones_depositos` (BCE), sabiendo que
no coincidirá numéricamente con `TASAS`.

**Segmentación por tipo de entidad**: el selector `LIST1!U2` (BANCOS+COOP / BANCOS /
COOPERATIVAS) es cosmético — solo cambia qué "TOTAL SISTEMA" se usa como denominador de
`% participación` en 2 hojas de presentación. El motor de cálculo real trata bancos
privados y cooperativas como una sola población mezclada. Los indicadores de este
documento se calculan **solo sobre `dim_banco.tipo_entidad = 'BANCO PRIVADO'`**, que es una
segmentación más estricta que la que hace el propio Excel.

## Fórmulas verificadas

Verificado comparando el valor cacheado real de `Formulas N!E<fila>` (columna `E` = BP
GUAYAQUIL, código banco `1006`; columna `F` = BP PACÍFICO, código banco `1028`) contra el
recálculo desde `fact_balance`/`fact_pyg` de `data/samples/marts_full` (nombre del
sample en ese momento, corte `2026-03-31`; renombrado a `data/samples/marts_ultimos_5_anios`
el 2026-07-25, ver `data/samples/README.md`). Coincidencia exacta (diff = 0.000000) en
ambos bancos para todos los indicadores de la tabla.

| Indicador (`IND_NN`) | Fórmula (códigos Catálogo Único) | GUAYAQUIL calculado | GUAYAQUIL Excel |
|---|---|---|---|
| `IND_91` Total Activos | `codigo = '1'` | 10,455,869.41 | 10,455,869.41 |
| `IND_6` Cartera Bruta | `codigo('14') - codigo('1499')` | 7,216,997.34 | 7,216,997.34 |
| `IND_40` Índice de Liquidez | `codigo('11') / (codigo('2101') + codigo('210305') + codigo('210310'))` | 0.15505 | 0.15505 |
| `IND_45` Morosidad Cartera Bruta | ver fórmula robusta abajo | 166,079.50 (miles) | 166,079.50 (miles) |
| `IND_23` Gasto de Operación | `codigo = '45'` | 84,052.74 | 84,052.74 |
| `IND_19` Utilidades Acumuladas | `pyg('5') - pyg('4')` (ver nota `fact_pyg` código `4`) | 39,004.45 | 39,004.45 |
| `IND_86` Utilidad Anualizada | `IND_19 * (12 / mes_actual)` | 156,017.81 | 156,017.81 |
| `IND_89` Activo Promedio (YTD) | ver fórmula YTD abajo | 10,069,921.23 | 10,069,921.23 |
| `IND_87` Patrimonio Promedio (YTD) | ver fórmula YTD abajo | 886,487.37 | 886,487.37 |
| `IND_53` ROA | `IND_86 / IND_89` | 0.01549345 | 0.01549345 |
| `IND_54` ROE | `IND_86 / IND_87` | 0.17599553 | 0.17599553 |
| `IND_52` Cobertura (Provisiones/Cartera Improductiva) | `provision(1499) / cartera_improductiva` | 1.42044 | 1.42044 |

Verificación cruzada adicional en BP PACÍFICO (mismo corte) para `IND_87`/`IND_89`/`IND_53`/`IND_54`: coincidencia exacta también (activo promedio 10,162,988.96, patrimonio promedio 1,116,644.20, ROA 0.02363641, ROE 0.21512366).

### Correcciones encontradas durante la verificación (no usar la fórmula "obvia")

1. **`fact_pyg` no tiene fila para el código `4` (TOTAL GASTOS) a nivel 1** — solo existe
   `5` (TOTAL INGRESOS). Workaround verificado: sumar las 8 cuentas nivel-2 hijas
   (`41+42+43+44+45+46+47+48`) da el valor exacto de gastos totales.

2. **`IND_40` (Índice de Liquidez)**: el denominador es `2101 + 210305 + 210310`
   (depósitos a la vista + a plazo 1–30 días + a plazo 31–90 días = "depósitos de corto
   plazo"), **no** solo `2101 + 210310`.

3. **`IND_45` (Morosidad) — el numerador no es una sola cuenta** (ej. `1425`). Es el bloque
   `cartera_improductiva` del glosario (§2) — suma de **todas** las cuentas nivel-4 bajo
   `14` (excluyendo `1499`) marcadas "QUE NO DEVENGA INTERESES" o "VENCIDA" y no "POR
   VENCER", a través de todos los segmentos y estados (normal, refinanciada,
   reestructurada, COVID). Implementado en `marts.vw_cartera_improductiva` — no depende de
   listar códigos a mano. La versión por segmento (`marts.vw_cartera_improductiva_segmento`)
   da la morosidad desagregada (`PRODUCTIVO`/`CONSUMO`/`INMOBILIARIO`/`MICROCR`/
   `EDUCATIVO`) — no usar listas de códigos hardcodeadas para esto, quedan casi siempre
   incompletas (cada segmento tiene 10+ códigos entre normal/refinanciada/reestructurada).

4. **`IND_87`/`IND_89` (Patrimonio/Activo Promedio) usan una ventana YTD**, no un
   promedio de 2 periodos: `AVERAGE` de los saldos de **fin de cada mes** de la cuenta
   correspondiente (`1` para activo, `3` para patrimonio), desde **diciembre del año
   anterior hasta el mes de corte** (inclusive). Es la fórmula que de verdad usan
   `IND_53`/`IND_54`/`IND_55`/`IND_55_1`/`IND_56` — el Excel tiene una variante
   "PROMEDIO DICIEMBRE" (que sí resta utilidad/pérdida del patrimonio) pero queda
   vestigial, sin conectar a ningún indicador activo. Bloque `activo_promedio_ytd` /
   `patrimonio_promedio_ytd` del glosario (§5), implementado en
   `marts.vw_activo_promedio_ytd` / `marts.vw_patrimonio_promedio_ytd`.

5. **`IND_86` (Utilidad Anualizada)** = `IND_19 * (12 / mes_actual)`, donde `IND_19` es la
   utilidad **acumulada** del año (ingresos − gastos YTD, no del mes individual) y
   `mes_actual` es el número de mes del corte (1–12). Verificado exacto: GUAYAQUIL marzo
   (`mes=3`) → `39,004.45298 * 4 = 156,017.81192`, coincide con `IND_86` real.

## Motor de referencia (Python/pandas)

[`scripts/compute_indicadores_excel.py`](../scripts/compute_indicadores_excel.py) implementa
estas fórmulas para los bancos privados del data mart, al corte más reciente disponible en
`data/samples/marts_ultimos_5_anios` (antes `marts_full`, ver `data/samples/README.md`; o
el que se indique con `--fecha-id`). Corrió limpio para 23/33
bancos privados a `2026-06-30` (10 sin `fact_balance` ese corte: AMIBANK, COFIEC, D-MIRO,
FINCA, JARAMILLO ARTEAGA, LLOYDS BANK, PROMERICA, SUDAMERICANO, TERRITORIAL, UNIBANCO —
pendiente confirmar si es hueco de carga o ausencia real de boletín ese mes).

**Nota sobre valores extremos de cobertura**: en bancos con cartera improductiva casi nula
(ej. BP CITIBANK: USD 1 vencido sobre una provisión de USD 19M), el ratio
`provisión / cartera_improductiva` se dispara matemáticamente por encima de 1.000.000%.
No es un error de la fórmula — es el comportamiento correcto de un ratio con denominador
casi cero; conviene capar la presentación (ej. mostrar ">1.000%") en vez de el número
crudo.

## Fuera de alcance (documentado, no mapeado)

Los códigos de la cadena Patrimonio Técnico / Castigos / Impuesto a la Renta (`IND_19B`,
`IND_19C`, `IND_19D`, `IND_19E`, `IND_7B`, `IND_25B`, `IND_61`, `IND_CAST`, `IND_25M`) se
resuelven técnicamente a cuentas contables simples y serían replicables, pero las hojas
que los consumen (`PT`, `CASTIGOS`, `IMPTOS`) dependen además de piezas que si están fuera
de alcance real (activos ponderados por riesgo, patrimonio técnico secundario) que no se
calculan en `Formulas N` — se generan en otra parte del libro no rastreada. Tampoco se
mapeó el módulo propio de Margen Financiero de Banco Guayaquil (data interna, sin fuente
pública).
