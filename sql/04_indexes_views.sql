-- Vistas de apoyo para validar la capa marts antes de conectar Power BI.
-- Power BI recalcula estas mismas métricas vía medidas DAX (ver docs/architecture.md);
-- estas vistas existen para pruebas de sanity con psql, no para consumo directo del reporte.

CREATE OR REPLACE VIEW marts.vw_cartera_market_share AS
SELECT
    f.fecha_id,
    d.fecha,
    b.banco,
    SUM(f.saldo) AS saldo_banco,
    SUM(SUM(f.saldo)) OVER (PARTITION BY f.fecha_id) AS saldo_total_mes,
    ROUND(
        SUM(f.saldo) / NULLIF(SUM(SUM(f.saldo)) OVER (PARTITION BY f.fecha_id), 0) * 100, 4
    ) AS market_share_pct
FROM marts.fact_cartera f
JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
JOIN marts.dim_banco b ON b.banco_id = f.banco_id
GROUP BY f.fecha_id, d.fecha, b.banco;

CREATE OR REPLACE VIEW marts.vw_cartera_hhi AS
SELECT
    fecha_id,
    fecha,
    ROUND(SUM(POWER(market_share_pct, 2)), 2) AS hhi
FROM marts.vw_cartera_market_share
GROUP BY fecha_id, fecha;

CREATE OR REPLACE VIEW marts.vw_depositos_market_share AS
SELECT
    f.fecha_id,
    d.fecha,
    b.banco,
    SUM(f.saldo) AS saldo_banco,
    SUM(SUM(f.saldo)) OVER (PARTITION BY f.fecha_id) AS saldo_total_mes,
    ROUND(
        SUM(f.saldo) / NULLIF(SUM(SUM(f.saldo)) OVER (PARTITION BY f.fecha_id), 0) * 100, 4
    ) AS market_share_pct
FROM marts.fact_depositos f
JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
JOIN marts.dim_banco b ON b.banco_id = f.banco_id
GROUP BY f.fecha_id, d.fecha, b.banco;

CREATE OR REPLACE VIEW marts.vw_depositos_hhi AS
SELECT
    fecha_id,
    fecha,
    ROUND(SUM(POWER(market_share_pct, 2)), 2) AS hhi
FROM marts.vw_depositos_market_share
GROUP BY fecha_id, fecha;

-- Tasa ponderada correctamente reagregada (numerador saldo*tasa / saldo), no promedio simple de tasas.
-- tipo_credito es columna directa en fact_cartera (dimensión degenerada, ver
-- sql/09_fact_cartera_depositos_rework.sql) -- no hace falta join a un catálogo de producto.
CREATE OR REPLACE VIEW marts.vw_cartera_tasa_ponderada AS
SELECT
    d.fecha,
    f.tipo_credito,
    ROUND(SUM(f.saldo_x_tasa) / NULLIF(SUM(f.saldo), 0), 4) AS tasa_ponderada
FROM marts.fact_cartera f
JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
WHERE f.saldo_x_tasa IS NOT NULL
GROUP BY d.fecha, f.tipo_credito;

CREATE OR REPLACE VIEW marts.vw_depositos_tasa_ponderada AS
SELECT
    d.fecha,
    cd.categoria AS categoria_deposito,
    ROUND(SUM(f.saldo_x_tasa) / NULLIF(SUM(f.saldo), 0), 4) AS tasa_ponderada
FROM marts.fact_depositos f
JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
JOIN marts.dim_categoria_deposito cd ON cd.categoria_deposito_id = f.categoria_deposito_id
WHERE f.saldo_x_tasa IS NOT NULL
GROUP BY d.fecha, cd.categoria;
