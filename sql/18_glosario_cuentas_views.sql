-- Vistas de "bloques de construcción" reutilizables sobre fact_balance/fact_pyg.
-- Cada vista corresponde 1:1 a un bloque documentado en docs/glosario_cuentas.md — el
-- glosario explica QUÉ significa cada bloque (concepto), esta librería lo IMPLEMENTA una
-- sola vez (código). Cualquier catálogo de indicadores (docs/metricas_financieras.md,
-- docs/indicadores_excel_bcos_coop.md, o uno nuevo) debería componer estas vistas en vez
-- de recalcular la lógica de cuentas contables desde cero.
--
-- Grano de todas: banco_id x fecha_id (mensual, sin filtrar por tipo_entidad — hoy
-- fact_balance/fact_pyg solo traen bancos privados por diseño del Boletín, ver
-- docs/data_dictionary.md; si esa fuente algún día trae otros tipos de entidad, unir
-- contra dim_banco.tipo_entidad en el consumidor).
--
-- Fórmulas traducidas 1:1 desde scripts/compute_indicadores_excel.py (motor de referencia
-- en pandas), verificado dígito a dígito contra el Excel real (BP GUAYAQUIL y BP PACÍFICO,
-- 2026-03) -- ver docs/indicadores_excel_bcos_coop.md.
-- NO ejecutado todavía contra una instancia Postgres real (solo probado el equivalente en
-- pandas contra data/samples/marts_full) -- validar el primer uso real antes de asumir
-- cero errores de sintaxis.

-- ---------------------------------------------------------------------------------------
-- Cartera bruta = cartera total (14) menos provisión para incobrables (1499)
CREATE OR REPLACE VIEW marts.vw_cartera_bruta AS
SELECT
    f.banco_id,
    f.fecha_id,
    SUM(f.saldo_usd) FILTER (WHERE cc.codigo = '14')
        - SUM(f.saldo_usd) FILTER (WHERE cc.codigo = '1499') AS cartera_bruta
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
WHERE cc.reporte = 'BALANCE' AND cc.codigo IN ('14', '1499')
GROUP BY f.banco_id, f.fecha_id;

-- Cartera improductiva = suma de cuentas nivel-4 bajo 14 (excl. 1499) marcadas
-- "QUE NO DEVENGA INTERESES" o "VENCIDA", excluyendo "POR VENCER" -- cubre los ~40 códigos
-- resultantes de cruzar 7 segmentos x varios estados (normal/refinanciada/reestructurada/
-- COVID). No usar una lista de códigos a mano -- ver docs/glosario_cuentas.md §2.
CREATE OR REPLACE VIEW marts.vw_cartera_improductiva AS
SELECT
    f.banco_id,
    f.fecha_id,
    SUM(f.saldo_usd) AS cartera_improductiva
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
WHERE cc.reporte = 'BALANCE'
  AND cc.codigo LIKE '14%' AND cc.nivel = 4 AND cc.codigo <> '1499'
  AND (cc.cuenta ILIKE '%NO DEVENGA%' OR cc.cuenta ILIKE '%VENCIDA%')
  AND cc.cuenta NOT ILIKE '%POR VENCER%'
GROUP BY f.banco_id, f.fecha_id;

-- Mismo bloque, desagregado por segmento de crédito (para morosidad/mora por segmento).
CREATE OR REPLACE VIEW marts.vw_cartera_improductiva_segmento AS
SELECT
    f.banco_id,
    f.fecha_id,
    seg.segmento,
    SUM(f.saldo_usd) AS cartera_improductiva
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
CROSS JOIN LATERAL (VALUES
    ('PRODUCTIVO', 'PRODUCTIVO'),
    ('CONSUMO', 'CONSUMO'),
    ('INMOBILIARIO', 'INMOBILIARIO'),
    ('MICROCRÉDITO', 'MICROCR'),   -- patrón sin tilde: evita problemas de encoding en el nombre de cuenta fuente
    ('EDUCATIVO', 'EDUCATIVO')
) AS seg(segmento, patron)
WHERE cc.reporte = 'BALANCE'
  AND cc.codigo LIKE '14%' AND cc.nivel = 4 AND cc.codigo <> '1499'
  AND (cc.cuenta ILIKE '%NO DEVENGA%' OR cc.cuenta ILIKE '%VENCIDA%')
  AND cc.cuenta NOT ILIKE '%POR VENCER%'
  AND cc.cuenta ILIKE '%' || seg.patron || '%'
GROUP BY f.banco_id, f.fecha_id, seg.segmento;

-- Cartera bruta por segmento (denominador de la morosidad por segmento) -- misma técnica
-- de patrón de texto sobre las cuentas "POR VENCER" del segmento (cartera al día).
CREATE OR REPLACE VIEW marts.vw_cartera_bruta_segmento AS
SELECT
    f.banco_id,
    f.fecha_id,
    seg.segmento,
    SUM(f.saldo_usd) AS cartera_bruta_segmento
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
CROSS JOIN LATERAL (VALUES
    ('PRODUCTIVO', 'PRODUCTIVO'),
    ('CONSUMO', 'CONSUMO'),
    ('INMOBILIARIO', 'INMOBILIARIO'),
    ('MICROCRÉDITO', 'MICROCR'),
    ('EDUCATIVO', 'EDUCATIVO')
) AS seg(segmento, patron)
WHERE cc.reporte = 'BALANCE'
  AND cc.codigo LIKE '14%' AND cc.nivel = 4 AND cc.codigo <> '1499'
  AND cc.cuenta ILIKE '%' || seg.patron || '%'
GROUP BY f.banco_id, f.fecha_id, seg.segmento;

-- ---------------------------------------------------------------------------------------
-- Depósitos de corto plazo = a la vista (2101) + a plazo 1-30 días (210305) + a plazo
-- 31-90 días (210310). Denominador del índice de liquidez tal como lo usa el Excel.
CREATE OR REPLACE VIEW marts.vw_depositos_corto_plazo AS
SELECT
    f.banco_id,
    f.fecha_id,
    SUM(f.saldo_usd) AS depositos_corto_plazo
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
WHERE cc.reporte = 'BALANCE' AND cc.codigo IN ('2101', '210305', '210310')
GROUP BY f.banco_id, f.fecha_id;

-- ---------------------------------------------------------------------------------------
-- Total gastos (PyG) -- fact_pyg no trae fila para el código '4' a nivel 1 (hueco de
-- datos documentado en docs/glosario_cuentas.md §4.6); se reconstruye sumando las 8
-- cuentas nivel-2 hijas, que reproduce el total exacto.
CREATE OR REPLACE VIEW marts.vw_pyg_total_gastos AS
SELECT
    f.banco_id,
    f.fecha_id,
    SUM(f.valor_usd) AS total_gastos
FROM marts.fact_pyg f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
WHERE cc.reporte = 'PYG' AND cc.codigo IN ('41', '42', '43', '44', '45', '46', '47', '48')
GROUP BY f.banco_id, f.fecha_id;

-- Utilidad acumulada YTD = ingresos totales (5) - total_gastos (vw_pyg_total_gastos).
CREATE OR REPLACE VIEW marts.vw_utilidad_acumulada AS
SELECT
    f.banco_id,
    f.fecha_id,
    SUM(f.valor_usd) FILTER (WHERE cc.codigo = '5') AS ingresos,
    g.total_gastos,
    SUM(f.valor_usd) FILTER (WHERE cc.codigo = '5') - g.total_gastos AS utilidad_acumulada
FROM marts.fact_pyg f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
JOIN marts.vw_pyg_total_gastos g ON g.banco_id = f.banco_id AND g.fecha_id = f.fecha_id
WHERE cc.reporte = 'PYG' AND cc.codigo = '5'
GROUP BY f.banco_id, f.fecha_id, g.total_gastos;

-- Utilidad anualizada = utilidad_acumulada * (12 / mes_de_corte) -- proyecta el YTD a un
-- equivalente de 12 meses.
CREATE OR REPLACE VIEW marts.vw_utilidad_anualizada AS
SELECT
    u.banco_id,
    u.fecha_id,
    d.mes,
    u.utilidad_acumulada,
    ROUND(u.utilidad_acumulada * (12.0 / d.mes), 2) AS utilidad_anualizada
FROM marts.vw_utilidad_acumulada u
JOIN marts.dim_fecha d ON d.fecha_id = u.fecha_id;

-- ---------------------------------------------------------------------------------------
-- Activo / patrimonio promedio YTD = promedio de saldos de fin de mes de la cuenta 1
-- (activo) o 3 (patrimonio), desde diciembre del año anterior hasta el mes de corte
-- (inclusive) -- NO un promedio de 2 puntos. Denominador correcto de ROA/ROE anualizado.
-- Implementado con LATERAL porque la ventana cruza el límite de año (incluye diciembre
-- del año anterior), lo que un simple OVER() particionado por año no puede expresar.
CREATE OR REPLACE VIEW marts.vw_activo_promedio_ytd AS
SELECT
    me.banco_id,
    me.fecha_id,
    prom.activo_promedio_ytd
FROM (
    SELECT DISTINCT f.banco_id, d.fecha_id, d.anio
    FROM marts.fact_balance f
    JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
    JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
    WHERE cc.reporte = 'BALANCE' AND cc.codigo = '1'
      AND d.dia = (SELECT MAX(d2.dia) FROM marts.dim_fecha d2 WHERE d2.anio_mes = d.anio_mes)
) me
JOIN LATERAL (
    SELECT ROUND(AVG(f2.saldo_usd), 2) AS activo_promedio_ytd
    FROM marts.fact_balance f2
    JOIN marts.dim_cuenta_contable cc2 ON cc2.cuenta_id = f2.cuenta_id
    JOIN marts.dim_fecha d2 ON d2.fecha_id = f2.fecha_id
    WHERE cc2.reporte = 'BALANCE' AND cc2.codigo = '1'
      AND f2.banco_id = me.banco_id
      AND d2.fecha_id BETWEEN (me.anio - 1) * 10000 + 1231 AND me.fecha_id
      AND d2.dia = (SELECT MAX(d3.dia) FROM marts.dim_fecha d3 WHERE d3.anio_mes = d2.anio_mes)
) prom ON TRUE;

CREATE OR REPLACE VIEW marts.vw_patrimonio_promedio_ytd AS
SELECT
    me.banco_id,
    me.fecha_id,
    prom.patrimonio_promedio_ytd
FROM (
    SELECT DISTINCT f.banco_id, d.fecha_id, d.anio
    FROM marts.fact_balance f
    JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
    JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
    WHERE cc.reporte = 'BALANCE' AND cc.codigo = '3'
      AND d.dia = (SELECT MAX(d2.dia) FROM marts.dim_fecha d2 WHERE d2.anio_mes = d.anio_mes)
) me
JOIN LATERAL (
    SELECT ROUND(AVG(f2.saldo_usd), 2) AS patrimonio_promedio_ytd
    FROM marts.fact_balance f2
    JOIN marts.dim_cuenta_contable cc2 ON cc2.cuenta_id = f2.cuenta_id
    JOIN marts.dim_fecha d2 ON d2.fecha_id = f2.fecha_id
    WHERE cc2.reporte = 'BALANCE' AND cc2.codigo = '3'
      AND f2.banco_id = me.banco_id
      AND d2.fecha_id BETWEEN (me.anio - 1) * 10000 + 1231 AND me.fecha_id
      AND d2.dia = (SELECT MAX(d3.dia) FROM marts.dim_fecha d3 WHERE d3.anio_mes = d2.anio_mes)
) prom ON TRUE;
