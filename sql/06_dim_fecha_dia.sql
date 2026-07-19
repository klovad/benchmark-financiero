-- dim_fecha pasa de grano mensual (fecha_id = YYYYMM) a grano día (fecha_id = YYYYMMDD).
-- Principio Kimball de "conformed dimension": una sola tabla de fecha al grano más fino
-- usado (día), en vez de una dimensión separada para datos semanales (BCE) y otra para
-- mensuales (CAPCOL/Boletín). anio_mes permite agrupar/comparar filas semanales contra
-- mensuales sin joins adicionales. Se agrega `dia`.
--
-- dim_fecha se trunca y reconstruye junto con dim_banco/fact_cartera/fact_depositos
-- (ver 07_dim_banco_dim_fecha_rebuild.sql) porque el formato de fecha_id cambia.

ALTER TABLE marts.dim_fecha
    ADD COLUMN IF NOT EXISTS dia INT,
    ADD COLUMN IF NOT EXISTS anio_mes INT;
