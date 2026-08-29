-- Bug: UNIQUE (fecha, tipo_entidad, banco, canton, tipo_deposito) en staging.depositos
-- no detecta conflicto cuando canton es NULL, porque en SQL NULL <> NULL incluso bajo
-- UNIQUE/ON CONFLICT -- misma clase de bug ya corregida en sql/10_fix_null_unique_constraints.sql
-- (dim_plazo/fact_depositos) y en sql/23_fix_staging_cartera_canton_null_safe.sql
-- (staging.cartera, misma columna canton). Ese migration anterior dejó staging.depositos
-- señalado como hueco de gobernanza pendiente (mismo defecto, fuera de alcance de ese cambio);
-- este migration lo cierra.
--
-- Verificado contra la base viva (2026-08-27) antes de aplicar este fix: canton IS NULL
-- devuelve 0 filas de 251.247 en staging.depositos -- el bug está latente, no disparando
-- duplicados hoy, así que este migration NO necesita el paso de dedupe que sql/10 sí
-- necesitó (esa corrida sí tenía filas fan-out reales). Aun así se corrige la causa raíz
-- para que una futura fila con canton NULL (ej. una entidad sin desagregación cantonal en
-- una fuente futura) no produzca el mismo bug de nuevo.
--
-- Fix: reemplazar el UNIQUE plano por un índice único de expresión sobre
-- COALESCE(canton, ''), mismo patrón NULL-safe que sql/10, sql/23 y las demás columnas
-- TEXT nullable en llaves naturales (provincia/ruc/tipo_segmento/dimension_valor en
-- sql/11, sql/12, sql/19: COALESCE(col, '') -- sentinela de cadena vacía para TEXT,
-- distinto del sentinela numérico -1 usado para columnas INT como plazo_id/canton_id).

ALTER TABLE staging.depositos DROP CONSTRAINT IF EXISTS depositos_fecha_tipo_entidad_banco_canton_tipo_deposito_key;

CREATE UNIQUE INDEX IF NOT EXISTS staging_depositos_natural_key_unique
    ON staging.depositos (fecha, tipo_entidad, banco, COALESCE(canton, ''), tipo_deposito);
