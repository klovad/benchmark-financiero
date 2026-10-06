-- Rework de dim_banco: identidad canónica resuelta en ETL (src/benchmark_bancos/transform/banco_matching.py),
-- no una tabla de alias en el esquema estrella. Corrige el bug de continuidad de
-- 'BP COMERCIAL DE MANABI'/'BP BANCO COMERCIAL DE MANABI' y
-- 'BANCO AMIBANK S.A.'/'BANCO AMIBANK S.A., EN LIQUIDACION' (mismo banco partido en 2
-- filas por un rename a mitad de histórico en CAPCOL).
--
-- staging.cartera/staging.depositos ganan banco_codigo (resuelto por banco_matching.py
-- antes de llegar acá) + columnas de change-data-capture (fecha_carga/fecha_actualizacion/
-- row_hash) para poder hacer upsert incremental sin reescribir filas sin cambios.

ALTER TABLE staging.cartera
    ADD COLUMN IF NOT EXISTS banco_codigo TEXT,
    ADD COLUMN IF NOT EXISTS fecha_carga TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE staging.depositos
    ADD COLUMN IF NOT EXISTS banco_codigo TEXT,
    ADD COLUMN IF NOT EXISTS fecha_carga TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now();

-- El backfill de banco_codigo (src/benchmark_bancos/transform/banco_matching.py, vía script Python) corre
-- entre este bloque y el siguiente -- ver docs/architecture.md. Una vez poblado:

-- row_hash cubre solo las columnas MUTABLES (las que el upsert actualiza en un
-- ON CONFLICT), no las columnas de la llave natural -- esas no cambian para una llave
-- dada, por definición. Nota: concat_ws() está marcada STABLE (no IMMUTABLE) en Postgres
-- y por eso no es válida dentro de un GENERATED ALWAYS AS; se concatena con || en su
-- lugar.
ALTER TABLE staging.cartera
    ALTER COLUMN banco_codigo SET NOT NULL;
ALTER TABLE staging.cartera
    ADD COLUMN IF NOT EXISTS row_hash TEXT GENERATED ALWAYS AS (
        md5(saldo::text || '|' || COALESCE(region, '') || '|' || COALESCE(provincia, '') || '|' || source_file)
    ) STORED;

ALTER TABLE staging.depositos
    ALTER COLUMN banco_codigo SET NOT NULL;
ALTER TABLE staging.depositos
    ADD COLUMN IF NOT EXISTS row_hash TEXT GENERATED ALWAYS AS (
        md5(saldo::text || '|' || COALESCE(region, '') || '|' || COALESCE(provincia, '') || '|'
            || COALESCE(numero_clientes::text, '') || '|' || COALESCE(numero_cuentas::text, '') || '|' || source_file)
    ) STORED;
