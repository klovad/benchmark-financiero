# Métricas financieras (Boletín Financiero Mensual, hoja `INDICADORES`)

Catálogo de los indicadores financieros que Superbancos ya calcula y publica por banco
en la hoja `INDICADORES` del Boletín Financiero Mensual. **No se cargan como tabla** —
son ratios derivados enteramente de `fact_balance`/`fact_pyg` (o directamente
recalculables desde ellos); cargarlos aparte duplicaría datos y arriesgaría reproducir la
fórmula oficial distinto de como Superbancos la calcula. Este documento existe para poder
construir las mismas medidas en Power BI con confianza, no como reemplazo de la fuente.

**Ver también**: [`glosario_cuentas.md`](glosario_cuentas.md) documenta qué significa cada
cuenta del Catálogo Único y los bloques reutilizables (`cartera_bruta`, `depositos_corto_plazo`,
promedios YTD, etc.) que no dependen de `grupo_met` — útil si se necesita construir un
indicador similar sin depender del bug de `grupo_met` descrito abajo. El catálogo `IND_NN`
del Excel de Financiero (otro catálogo distinto a este) está en
[`indicadores_excel_bcos_coop.md`](indicadores_excel_bcos_coop.md).

**Corrección de alcance**: la investigación original estimó "40 indicadores". El archivo
real (`FINANCIERO MENSUAL BANCA PRIVADA 2026_06.xlsx`, hoja `INDICADORES`) trae **48**,
organizados en 12 categorías. Se documentan los 48 por nombre y categoría; de ellos, 3 se
verificaron a mano recalculando desde los agregados de la hoja `MET` (que sí se relacionan
1:1 con códigos de `fact_balance` vía `dim_cuenta_contable.grupo_met`) y coinciden
exactamente con el valor publicado. El resto de fórmulas no se reprodujo con la misma
exactitud en esta pasada — quedan documentadas por nombre/categoría para referencia, pero
su fórmula completa requeriría más tiempo de reverse-engineering contra la
metodología oficial de Superbancos (no publicada en el archivo mismo).

## Fórmulas verificadas

Verificado contra `BP GUAYAQUIL`, junio 2026, comparando el cálculo hecho a mano contra
el valor real de la celda en `INDICADORES` (coincidencia exacta a 6 decimales):

| Indicador | Fórmula | Calculado | Real (`INDICADORES`) |
|---|---|---|---|
| ACTIVOS PRODUCTIVOS / TOTAL ACTIVOS | `grupo_met='ACTIVOS PRODUCTIVOS' / codigo='1'` (TOTAL ACTIVO) | 0.906874 | 0.906874 |
| ACTIVOS PRODUCTIVOS / PASIVOS CON COSTO | `grupo_met='ACTIVOS PRODUCTIVOS' / grupo_met='PASIVOS CON COSTO'` | 1.155592 | 1.155592 |
| ACTIVOS IMPRODUCTIVOS NETOS / TOTAL ACTIVOS | `grupo_met='ACTIVOS IMPRODUCTIVOS NETOS' / codigo='1'` | 0.093126 | 0.093126 |

Consulta SQL equivalente para el primer indicador (una vez cargado `fact_balance` con
`grupo_met`, ver `sql/13_schema_boletin.sql`):

```sql
SELECT
    SUM(f.saldo_usd) FILTER (WHERE cc.grupo_met = 'ACTIVOS PRODUCTIVOS')
    / SUM(f.saldo_usd) FILTER (WHERE cc.codigo = '1') AS activos_productivos_pct
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
JOIN marts.dim_entidad b ON b.entidad_id = f.entidad_id
JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
WHERE b.banco_codigo = 'GUAYAQUIL' AND d.fecha = '2026-06-30';
```

**Nota sobre `grupo_met`**: no es una partición limpia — un mismo código de cuenta puede
aparecer bajo más de un grupo funcional en la hoja `MET` (ej. `11 FONDOS DISPONIBLES`
contribuye tanto a `ACTIVOS LIQUIDOS` como a `ACTIVOS IMPRODUCTIVOS BRUTOS`, según qué
parte del saldo corresponda a cada concepto). `dim_cuenta_contable.grupo_met` guarda solo
el **primer** grupo encontrado por código — suficiente para los 3 indicadores de arriba
(sus grupos no se solapan con `11`), pero no asumir que `SUM(...) FILTER (WHERE grupo_met
= X)` reproduce cualquier subtotal de `MET` sin verificar primero contra el valor real,
como se hizo acá.

## Reconciliación cruzada CAPCOL vs. BALANCE — cartera bruta (2026-08-30)

En el mismo espíritu que los 3 indicadores de arriba (recalcular desde los agregados y
comparar contra el valor real antes de confiar en una cifra derivada), se verificó si el
saldo de cartera que reporta CAPCOL (`marts.fact_saldo_cartera`, grano fecha × banco ×
cantón × segmento) reconcilia contra la cartera bruta reconstruida desde el Boletín
(`marts.vw_cartera_bruta` = `14 − 1499`, ver `docs/glosario_cuentas.md` §2). Son fuentes
independientes (Superbancos consolidado por cantón vs. Superbancos consolidado por plan
de cuentas) que en teoría deberían describir el mismo universo de préstamos otorgados por
bancos privados — este es el cruce de validación que `docs/fuentes_datos.md` (sección
3.3, hoja `RK`) dejaba como pregunta abierta.

**Metodología**: `SUM(fact_saldo_cartera.saldo_total)` agrupado por `entidad_id`/`fecha_id`
(colapsando cantón y segmento, que `vw_cartera_bruta` no desagrega) comparado contra
`vw_cartera_bruta.cartera_bruta` para el mismo `entidad_id`/`fecha_id`.

**Resultado** (verificado contra la base viva, 1.559 combinaciones banco × fecha con dato
en ambas fuentes):

| Métrica | Valor |
|---|---|
| N combinaciones banco × fecha comparadas | 1.559 |
| Diferencia % mediana (CAPCOL vs. BALANCE) | ≈ −0,00000045% (esencialmente 0) |
| Diferencia % media | −0,227% |
| Desviación estándar de la diferencia % | 0,669 pp |
| Dentro de ±1% | 1.466 / 1.559 (94,03%) |
| Dentro de ±2% | 1.511 / 1.559 (96,92%) |
| Dentro de ±5% | 1.552 / 1.559 (99,55%) |

La mediana ~0% confirma que, para la gran mayoría del histórico, ambas fuentes describen
el mismo universo de cartera bruta con una diferencia despreciable — un cruce de
validación independiente más fuerte que "cargó sin error", en la misma línea que los 3
indicadores verificados arriba.

**Excepciones conocidas, no investigadas a fondo** (7 de 1.559 filas quedan fuera de
±5%, todas concentradas en 4 bancos y ventanas de fecha acotadas — devuelve las
diferencias más grandes de las 1.559 comparadas):

| Banco | Ventana con desviación >2% | N meses afectados (de los meses con overlap) | Rango de diferencia % |
|---|---|---|---|
| AMIBANK | 2023-05-31 a 2023-12-31 | 8 de 22 | −4,92% a −5,92% |
| ATLANTIDA | 2025-06-30 a 2026-05-31 | 12 de 13 (casi toda su ventana de overlap) | −2,00% a −4,87% |
| PACIFICO | 2022-09-30 a 2024-10-31 | 26 de 66 | −2,01% a −3,45% |
| FINCA | 2022-11-30 a 2022-12-31 | 2 de 24 | −2,47% a −2,77% |

En los 4 casos CAPCOL reporta **por debajo** de BALANCE (mismo signo que la desviación
mediana de fondo). No se investigó la causa raíz esta sesión (posibles hipótesis sin
verificar: reclasificación de cartera fuera de las categorías de cantón/segmento que
cubre CAPCOL, timing de corte entre ambas fuentes, o un problema puntual de carga para
esos bancos/meses) — queda registrado como hueco de gobernanza para una pasada futura,
ver `docs/gobernanza_datos.md`.

Consulta SQL usada (equivalente a `marts.vw_cartera_bruta`, expandida inline porque la
vista de `sql/18_glosario_cuentas_views.sql` no estaba aplicada en la base viva a la fecha
de esta verificación; se aplicó el 2026-10-02 — ver nota en `docs/gobernanza_datos.md`):

```sql
WITH capcol AS (
    SELECT entidad_id, fecha_id, SUM(saldo_total) AS capcol_total
    FROM marts.fact_saldo_cartera
    GROUP BY entidad_id, fecha_id
),
balance AS (
    SELECT f.entidad_id, f.fecha_id,
        SUM(f.saldo_usd) FILTER (WHERE cc.codigo = '14')
            - SUM(f.saldo_usd) FILTER (WHERE cc.codigo = '1499') AS cartera_bruta
    FROM marts.fact_balance f
    JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
    WHERE cc.reporte = 'BALANCE' AND cc.codigo IN ('14', '1499')
    GROUP BY f.entidad_id, f.fecha_id
)
SELECT b.banco_codigo, d.fecha, c.capcol_total, bal.cartera_bruta,
       100.0 * (c.capcol_total - bal.cartera_bruta) / bal.cartera_bruta AS diff_pct
FROM capcol c
JOIN balance bal ON bal.entidad_id = c.entidad_id AND bal.fecha_id = c.fecha_id
JOIN marts.dim_entidad b ON b.entidad_id = c.entidad_id
JOIN marts.dim_fecha d ON d.fecha_id = c.fecha_id;
```

## Catálogo completo (48 indicadores, 12 categorías)

### Suficiencia patrimonial
- (PATRIMONIO + RESULTADOS) / ACTIVOS INMOVILIZADOS NETOS

### Estructura y calidad de activos
- ACTIVOS IMPRODUCTIVOS NETOS / TOTAL ACTIVOS ✅ verificado
- ACTIVOS PRODUCTIVOS / TOTAL ACTIVOS ✅ verificado
- ACTIVOS PRODUCTIVOS / PASIVOS CON COSTO ✅ verificado

### Índices de morosidad (por segmento de cartera)
- Morosidad cartera inmobiliario y vivienda de interés público
- Morosidad cartera créditos productivos nuevo
- Morosidad cartera créditos consumo
- Morosidad cartera créditos inmobiliario
- Morosidad cartera créditos microcrédito
- Morosidad cartera créditos vivienda de interés social y público
- Morosidad cartera créditos educativo
- Morosidad cartera crédito inversión pública
- Morosidad cartera total

### Cobertura de provisiones para cartera improductiva (por segmento, + refinanciada/reestructurada/problemática)
- Cobertura cartera inmobiliario y vivienda de interés público
- Cobertura cartera créditos productivo nuevo
- Cobertura cartera créditos consumo
- Cobertura cartera créditos inmobiliario
- Cobertura cartera créditos microcrédito
- Cobertura cartera créditos vivienda de interés social y público
- Cobertura cartera créditos educativo
- Cobertura cartera crédito inversión pública
- Cobertura cartera refinanciada
- Cobertura cartera reestructurada
- Cobertura cartera problemática

### Eficiencia microeconómica
- Gastos de operación estimados / total activo promedio
- Gastos de operación / margen financiero
- Gastos de personal estimados / activo promedio

### Rentabilidad
- Resultados del ejercicio / patrimonio promedio
- Resultados del ejercicio / activo promedio

### Intermediación financiera
- Cartera bruta / (depósitos a la vista + depósitos a plazo)

### Eficiencia financiera
- Margen de intermediación estimado / patrimonio promedio
- Margen de intermediación estimado / activo promedio

### Rendimiento de la cartera (por vencer, por segmento + refinanciada/reestructurada)
- Rendimiento cartera inmobiliario y vivienda de interés público
- Cartera créditos productivo nuevo por vencer
- Cartera créditos consumo por vencer
- Rendimiento cartera créditos inmobiliario por vencer
- Rendimiento cartera créditos microcrédito por vencer
- Rendimiento cartera créditos vivienda de interés social y público por vencer
- Rendimiento cartera créditos educativo por vencer
- Rendimiento cartera crédito inversión pública por vencer
- Rendimiento carteras de créditos refinanciadas
- Rendimiento carteras de créditos reestructuradas
- Rendimiento cartera por vencer total

### Liquidez
- Fondos disponibles / total depósitos a corto plazo

### Vulnerabilidad del patrimonio
- Cartera improductiva descubierta / (patrimonio + resultados)
- Cartera improductiva / patrimonio (dic)

### Índice de capitalización
- FK = (patrimonio + resultados − ingresos extraordinarios) / activos totales
- FI = 1 + (activos improductivos / activos totales)
- Índice de capitalización neto: FK / FI

## Grupos funcionales de `MET` (candidatos a `grupo_met`)

Nombres reales encontrados en la hoja `MET` (junio 2026) — útiles como punto de partida
si se quiere reconstruir más fórmulas de la lista de arriba:

`ACTIVOS LIQUIDOS`, `PASIVOS EXIGIBLES`, `ACTIVOS IMPRODUCTIVOS BRUTOS`, `PROVISIONES`,
`ACTIVOS LIQUIDOS IMPRODUCTIVOS`, `PASIVOS CON COSTO`, `PATRIMONIO MAS INGRESOS MENOS
GASTOS`, `PATRIMONIO`, `RESULTADOS (SOLO PARA DICIEMBRE EXCLUIR)`, `ACTIVOS PRODUCTIVOS`,
`COBERTURA PATRIMONIAL DE ACTIVOS`, `INDICE DE VULNERABILIDAD PATRIMONIAL`, `Cartera
Improductiva`, `INGRESOS - GASTOS`. Cada grupo tiene una fila `TOTAL <grupo>` en la propia
hoja `MET` con el subtotal ya calculado por Superbancos — la forma más rápida de verificar
una fórmula nueva es comparar `SUM(fact_balance.saldo_usd) FILTER (WHERE grupo_met = X)`
contra ese valor real antes de darla por buena (como se hizo para los 3 indicadores
verificados arriba).
