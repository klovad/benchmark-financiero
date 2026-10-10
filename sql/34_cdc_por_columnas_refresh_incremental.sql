-- CDC por columnas + refresh incremental de marts (2026-10-05).
--
-- 1. Se eliminan las columnas GENERATED row_hash de staging.* y marts.*.
--    Cada row_hash era md5() de 1 a 6 columnas de la propia fila y solo se usaba en el
--    guard `WHERE t.row_hash IS DISTINCT FROM EXCLUDED.row_hash` de los upserts. La
--    comparación directa `(t.a, t.b) IS DISTINCT FROM (EXCLUDED.a, EXCLUDED.b)` sobre las
--    MISMAS columnas es equivalente (mismo resultado, incluidos los NULL) y no ocupa
--    espacio. El hash solo compensa cuando la fila es ancha o se compara contra otro
--    sistema; aquí las filas son angostas y la comparación es dentro de la misma base.
--    Ocupaban ~1,3 GB (medido con pg_stats). Las columnas comparadas viven en
--    load_postgres.py (CDC_COLUMNS y los guards de _REFRESH_MARTS_SQL); son exactamente
--    las que cubría cada md5.
--    Nota: DROP COLUMN es instantáneo pero no devuelve el espacio en disco hasta un
--    VACUUM FULL (o reescritura) de la tabla.
--
-- 2. meta.refresh_watermark: marca de agua del refresh incremental. refresh_marts()
--    recalcula solo el alcance (fecha, banco_codigo) de las filas de staging con
--    fecha_actualizacion posterior a la marca. Sin fila (base nueva) hace un refresh
--    completo y la crea.
--
-- 3. Índices sobre staging.*.fecha_actualizacion para encontrar esas filas sin recorrer
--    la tabla completa (bce_tasas_activas tiene 7,7 M de filas).

ALTER TABLE staging.cartera              DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.depositos            DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.bce_tasas_pasivas    DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.bce_tasas_activas    DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.tasas_referenciales  DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.boletin_balance      DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.boletin_pyg          DROP COLUMN IF EXISTS row_hash;

ALTER TABLE marts.dim_banco                                    DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_saldo_cartera                           DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_saldo_depositos                         DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_captaciones_depositos                   DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_colocaciones_cartera                    DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_tasas_referenciales_cartera             DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_tasas_referenciales_depositos_instrumento DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_tasas_referenciales_depositos_plazo     DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_tasas_referenciales_sistema             DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_balance                                 DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_pyg                                     DROP COLUMN IF EXISTS row_hash;

CREATE SCHEMA IF NOT EXISTS meta;  -- dueño: el rol que aplica la migración (sql/00)

CREATE TABLE IF NOT EXISTS meta.refresh_watermark (
    proceso TEXT PRIMARY KEY,           -- hoy solo 'marts'
    hasta   TIMESTAMPTZ NOT NULL        -- inicio de la última corrida exitosa
);

CREATE INDEX IF NOT EXISTS ix_staging_cartera_fecha_actualizacion
    ON staging.cartera (fecha_actualizacion);
CREATE INDEX IF NOT EXISTS ix_staging_depositos_fecha_actualizacion
    ON staging.depositos (fecha_actualizacion);
CREATE INDEX IF NOT EXISTS ix_staging_bce_tasas_pasivas_fecha_actualizacion
    ON staging.bce_tasas_pasivas (fecha_actualizacion);
CREATE INDEX IF NOT EXISTS ix_staging_bce_tasas_activas_fecha_actualizacion
    ON staging.bce_tasas_activas (fecha_actualizacion);
CREATE INDEX IF NOT EXISTS ix_staging_tasas_referenciales_fecha_actualizacion
    ON staging.tasas_referenciales (fecha_actualizacion);
CREATE INDEX IF NOT EXISTS ix_staging_boletin_balance_fecha_actualizacion
    ON staging.boletin_balance (fecha_actualizacion);
CREATE INDEX IF NOT EXISTS ix_staging_boletin_pyg_fecha_actualizacion
    ON staging.boletin_pyg (fecha_actualizacion);
