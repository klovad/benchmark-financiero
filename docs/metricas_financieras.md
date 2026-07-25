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
JOIN marts.dim_banco b ON b.banco_id = f.banco_id
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
