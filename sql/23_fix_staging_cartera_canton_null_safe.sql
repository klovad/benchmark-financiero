-- Bug: UNIQUE (fecha, tipo_entidad, banco, canton, tipo_credito, estado_cartera) en
-- staging.cartera no detecta conflicto cuando canton es NULL, porque en SQL NULL <> NULL
-- incluso bajo UNIQUE/ON CONFLICT -- exactamente la misma clase de bug ya corregida en
-- sql/10_fix_null_unique_constraints.sql para dim_plazo/fact_depositos. Encontrado por una
-- pasada de CI/tests (no reportado como activo -- ver verificación abajo).
--
-- Verificado contra la base viva (2026-08-27) antes de aplicar este fix: canton IS NULL
-- devuelve 0 filas de 369.966 en staging.cartera (y 0 filas en staging.depositos, que
-- tiene la misma forma de UNIQUE pero está fuera del alcance de este cambio) -- el bug
-- está latente, no disparando duplicados hoy, así que este migration NO necesita el paso
-- de dedupe que sql/10 sí necesitó (esa corrida sí tenía filas fan-out reales). Aun así se
-- corrige la causa raíz para que una futura fila con canton NULL (ej. una entidad sin
-- desagregación cantonal en una fuente futura) no produzca el mismo bug de nuevo.
--
-- Fix: reemplazar el UNIQUE plano por un índice único de expresión sobre
-- COALESCE(canton, ''), mismo patrón NULL-safe que sql/10 y que las demás columnas TEXT
-- nullable en llaves naturales ya usan (provincia/ruc/tipo_segmento/dimension_valor en
-- sql/11, sql/12, sql/19: COALESCE(col, '') -- sentinela de cadena vacía para TEXT,
-- distinto del sentinela numérico -1 usado para columnas INT como plazo_id/canton_id).

ALTER TABLE staging.cartera DROP CONSTRAINT IF EXISTS cartera_fecha_tipo_entidad_banco_canton_tipo_credito_estado_key;

CREATE UNIQUE INDEX IF NOT EXISTS staging_cartera_natural_key_unique
    ON staging.cartera (fecha, tipo_entidad, banco, COALESCE(canton, ''), tipo_credito, estado_cartera);
