-- Restos sin uso (2026-10-31, revisión de arquitectura).
--
-- 1. marts.dim_producto_cartera / dim_producto_deposito: creadas en sql/03, dejaron de
--    usarse en sql/08-09 (los hechos pasaron a dim_segmento_credito y
--    dim_categoria_deposito) y quedaron vacías, sin FK ni vistas que las referencien.
--    docs/gobernanza_datos.md las daba por eliminadas desde 2026-07-20; no lo estaban.
-- 2. staging.cartera.morosidad / tasa_ponderada y staging.depositos.tasa_ponderada:
--    reservadas desde la v1 y siempre NULL (CAPCOL no trae esos valores; en marts se
--    quitaron en sql/15). Ningún código las escribe ni las lee.

DROP TABLE IF EXISTS marts.dim_producto_cartera;
DROP TABLE IF EXISTS marts.dim_producto_deposito;

ALTER TABLE staging.cartera DROP COLUMN IF EXISTS morosidad;
ALTER TABLE staging.cartera DROP COLUMN IF EXISTS tasa_ponderada;
ALTER TABLE staging.depositos DROP COLUMN IF EXISTS tasa_ponderada;
