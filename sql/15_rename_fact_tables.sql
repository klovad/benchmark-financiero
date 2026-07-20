-- Renombra las tablas de hechos a un glosario consistente de negocio (decidido con el
-- usuario, 2026-07-19): "cartera" = negocio de crédito (siempre), "depositos" = negocio
-- de captación (siempre); "saldo_" = medida de balance (CAPCOL, mensual, por cantón);
-- "colocaciones_"/"captaciones_" = tasa efectiva + monto por banco (BCE semanal tsa/tsp);
-- "tasas_referenciales_" = techo/referencial a nivel sistema (BCE mensual,
-- TasasHistorico). Antes, "tasas_activas"/"tasas_pasivas" se confundían fácilmente con
-- las tablas de tasas referenciales/máximas, y 2 de las 4 tablas de referenciales no
-- usaban la palabra "referenciales" en absoluto.
--
--   fact_cartera                      -> fact_saldo_cartera
--   fact_depositos                    -> fact_saldo_depositos
--   fact_tasas_activas                -> fact_colocaciones_cartera
--   fact_tasas_pasivas                -> fact_captaciones_depositos
--   fact_tasas_referenciales_credito  -> fact_tasas_referenciales_cartera
--   fact_tasas_pasivas_instrumento    -> fact_tasas_referenciales_depositos_instrumento
--   fact_tasas_pasivas_plazo          -> fact_tasas_referenciales_depositos_plazo
--   fact_tasas_referenciales_sistema  -> (sin cambio)
--
-- De paso, elimina 3 columnas reservadas en v1 que nunca se poblaron (saldo_x_tasa,
-- tasa_ponderada en ambas; morosidad en fact_cartera) -- la tasa real por producto ya
-- vive en fact_colocaciones_cartera/fact_captaciones_depositos, no hace falta
-- duplicarla como columna vacía en las tablas de saldo.

-- 1) Vistas que dependían de saldo_x_tasa -- ya estaban muertas en la práctica (esa
-- columna nunca se pobló, así que WHERE f.saldo_x_tasa IS NOT NULL nunca devolvía filas).
DROP VIEW IF EXISTS marts.vw_cartera_tasa_ponderada;
DROP VIEW IF EXISTS marts.vw_depositos_tasa_ponderada;

-- 2) fact_cartera: row_hash depende de tasa_ponderada/morosidad -- hay que soltarlo,
-- borrar las columnas, y recrearlo solo con saldo (la única columna mutable real).
ALTER TABLE marts.fact_cartera DROP COLUMN row_hash;
ALTER TABLE marts.fact_cartera
    DROP COLUMN saldo_x_tasa,
    DROP COLUMN tasa_ponderada,
    DROP COLUMN morosidad;
ALTER TABLE marts.fact_cartera
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (md5(saldo::text)) STORED;

-- 3) fact_depositos: row_hash ya solo depende de saldo/numero_clientes/numero_cuentas,
-- no hace falta tocarlo.
ALTER TABLE marts.fact_depositos
    DROP COLUMN saldo_x_tasa,
    DROP COLUMN tasa_ponderada;

-- 4) Renombrar tablas.
ALTER TABLE marts.fact_cartera RENAME TO fact_saldo_cartera;
ALTER TABLE marts.fact_depositos RENAME TO fact_saldo_depositos;
ALTER TABLE marts.fact_tasas_activas RENAME TO fact_colocaciones_cartera;
ALTER TABLE marts.fact_tasas_pasivas RENAME TO fact_captaciones_depositos;
ALTER TABLE marts.fact_tasas_referenciales_credito RENAME TO fact_tasas_referenciales_cartera;
ALTER TABLE marts.fact_tasas_pasivas_instrumento RENAME TO fact_tasas_referenciales_depositos_instrumento;
ALTER TABLE marts.fact_tasas_pasivas_plazo RENAME TO fact_tasas_referenciales_depositos_plazo;

-- 5) Renombrar columnas PK (BIGSERIAL) para que coincidan con el nuevo nombre de tabla.
-- Las 3 tablas de referenciales con PK compuesta (fecha_id, ...) no tienen columna _id,
-- no aplica.
ALTER TABLE marts.fact_saldo_cartera RENAME COLUMN fact_cartera_id TO fact_saldo_cartera_id;
ALTER TABLE marts.fact_saldo_depositos RENAME COLUMN fact_depositos_id TO fact_saldo_depositos_id;
ALTER TABLE marts.fact_colocaciones_cartera RENAME COLUMN fact_id TO fact_colocaciones_cartera_id;
ALTER TABLE marts.fact_captaciones_depositos RENAME COLUMN fact_id TO fact_captaciones_depositos_id;

-- 6) Postgres NO renombra automáticamente constraints/índices al renombrar la tabla
-- (confirmado empíricamente) -- se renombran los que sí importan (PK, UNIQUE, CHECK,
-- índices simples de apoyo). Los _fkey autogenerados se dejan tal cual: no se
-- referencian por nombre en ningún lado del código (ON CONFLICT usa listas de columnas,
-- no nombre de constraint) y varios excederían el límite de 63 caracteres de Postgres.
ALTER TABLE marts.fact_saldo_cartera RENAME CONSTRAINT fact_cartera_pkey TO fact_saldo_cartera_pkey;
ALTER TABLE marts.fact_saldo_cartera RENAME CONSTRAINT fact_cartera_unique TO fact_saldo_cartera_unique;
ALTER TABLE marts.fact_saldo_cartera RENAME CONSTRAINT fact_cartera_estado_check TO fact_saldo_cartera_estado_check;
ALTER INDEX marts.ix_fact_cartera_banco RENAME TO ix_fact_saldo_cartera_banco;
ALTER INDEX marts.ix_fact_cartera_fecha RENAME TO ix_fact_saldo_cartera_fecha;

ALTER TABLE marts.fact_saldo_depositos RENAME CONSTRAINT fact_depositos_pkey TO fact_saldo_depositos_pkey;
ALTER INDEX marts.fact_depositos_rango_unique RENAME TO fact_saldo_depositos_rango_unique;
ALTER INDEX marts.ix_fact_depositos_banco RENAME TO ix_fact_saldo_depositos_banco;
ALTER INDEX marts.ix_fact_depositos_fecha RENAME TO ix_fact_saldo_depositos_fecha;

ALTER TABLE marts.fact_colocaciones_cartera RENAME CONSTRAINT fact_tasas_activas_pkey TO fact_colocaciones_cartera_pkey;
ALTER INDEX marts.fact_tasas_activas_unique RENAME TO fact_colocaciones_cartera_unique;

ALTER TABLE marts.fact_captaciones_depositos RENAME CONSTRAINT fact_tasas_pasivas_pkey TO fact_captaciones_depositos_pkey;
ALTER INDEX marts.fact_tasas_pasivas_unique RENAME TO fact_captaciones_depositos_unique;

ALTER TABLE marts.fact_tasas_referenciales_cartera RENAME CONSTRAINT fact_tasas_referenciales_credito_pkey TO fact_tasas_referenciales_cartera_pkey;
ALTER TABLE marts.fact_tasas_referenciales_depositos_instrumento RENAME CONSTRAINT fact_tasas_pasivas_instrumento_pkey TO fact_tasas_referenciales_depositos_instrumento_pkey;
ALTER TABLE marts.fact_tasas_referenciales_depositos_plazo RENAME CONSTRAINT fact_tasas_pasivas_plazo_pkey TO fact_tasas_referenciales_depositos_plazo_pkey;

-- 7) Recrear las 4 vistas de apoyo que sí siguen vigentes, apuntando a los nuevos nombres.
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
FROM marts.fact_saldo_cartera f
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
FROM marts.fact_saldo_depositos f
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
