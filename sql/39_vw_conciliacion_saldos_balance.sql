-- Conciliación de saldos por cantón contra la contabilidad (2026-10-09).
--
-- El balance no tiene detalle geográfico, así que se concilia a nivel entidad × mes: la
-- suma de todos los cantones de una entidad contra sus cuentas contables.
--   cartera   : fact_saldo_cartera.saldo_total  vs  14 - 1499 (cartera neta + provisiones
--               = cartera bruta), igual que marts.vw_cartera_bruta
--   depósitos : fact_saldo_depositos.saldo      vs  21 (obligaciones con el público)
-- Solo entidades con estados financieros cargados: bancos privados (Boletín) y
-- cooperativas/mutualistas (EEFF SEPS). La Banca Pública no tiene contra qué conciliar.
--
-- Hasta ahora esto se verificaba con consultas puntuales (docs/fuentes_datos.md §4.0). Con
-- estas vistas queda consultable, y `benchmark-bancos conciliar` (también al final de
-- `actualizar`) compara el resumen mensual contra umbrales por tipo de entidad
-- (src/benchmark_bancos/conciliacion.py) y registra ERROR si un mes se sale.
--
-- Desvíos conocidos y explicados (no son errores de carga):
--   - mutualistas, cartera: +1% a +47%, reportan la cartera VIS/VIP vendida al fideicomiso
--     que siguen administrando (cuentas de orden 740170/740175);
--   - bancos privados, depósitos: mediana -0,5% a -1,1%, CAPCOL no cubre 5 subcuentas de 21;
--   - JEP, Policía Nacional y emisoras de tarjetas (SEPS): al consumo le faltan las tarjetas.

CREATE OR REPLACE VIEW marts.vw_conciliacion_saldos_balance AS
WITH contable AS (
    SELECT f.fecha_id, f.entidad_id,
           sum(f.saldo_usd) FILTER (WHERE cc.codigo = '14')
             - coalesce(sum(f.saldo_usd) FILTER (WHERE cc.codigo = '1499'), 0) AS cartera,
           sum(f.saldo_usd) FILTER (WHERE cc.codigo = '21') AS depositos
    FROM marts.fact_balance f
    JOIN marts.dim_cuenta_contable cc USING (cuenta_id)
    WHERE cc.codigo IN ('14', '1499', '21')
    GROUP BY f.fecha_id, f.entidad_id
),
cartera AS (
    SELECT fecha_id, entidad_id, sum(saldo_total) AS saldo
    FROM marts.fact_saldo_cartera GROUP BY fecha_id, entidad_id
),
depositos AS (
    SELECT fecha_id, entidad_id, sum(saldo) AS saldo
    FROM marts.fact_saldo_depositos GROUP BY fecha_id, entidad_id
)
SELECT c.fecha_id, c.entidad_id, e.tipo_entidad, 'cartera'::text AS medida,
       k.saldo AS saldo_reportado, c.cartera AS saldo_contable,
       (k.saldo - c.cartera) / nullif(c.cartera, 0) AS diferencia_pct
FROM contable c
JOIN cartera k USING (fecha_id, entidad_id)
JOIN marts.dim_entidad e USING (entidad_id)
WHERE c.cartera > 0
UNION ALL
SELECT c.fecha_id, c.entidad_id, e.tipo_entidad, 'depositos'::text,
       d.saldo, c.depositos,
       (d.saldo - c.depositos) / nullif(c.depositos, 0)
FROM contable c
JOIN depositos d USING (fecha_id, entidad_id)
JOIN marts.dim_entidad e USING (entidad_id)
WHERE c.depositos > 0;

COMMENT ON VIEW marts.vw_conciliacion_saldos_balance IS
    'Saldos por cantón sumados por entidad × mes vs. cuentas contables (cartera: 14 - 1499; depósitos: 21). Ver sql/39.';

-- Resumen mensual por tipo de entidad: lo que evalúa conciliacion.py.
CREATE OR REPLACE VIEW marts.vw_conciliacion_resumen AS
SELECT fecha_id, tipo_entidad, medida,
       count(*) AS entidades,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY diferencia_pct) AS mediana_pct,
       avg((abs(diferencia_pct) <= 0.005)::int) AS dentro_05pct,
       avg((abs(diferencia_pct) <= 0.02)::int) AS dentro_2pct,
       sum(saldo_reportado) / nullif(sum(saldo_contable), 0) - 1 AS diferencia_agregada_pct
FROM marts.vw_conciliacion_saldos_balance
GROUP BY fecha_id, tipo_entidad, medida;

COMMENT ON VIEW marts.vw_conciliacion_resumen IS
    'Resumen mensual de vw_conciliacion_saldos_balance por tipo de entidad y medida. Ver sql/39 y conciliacion.py.';
