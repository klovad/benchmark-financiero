-- Migra fact_cartera (producto_cartera_id -> tipo_credito/estado_cartera directo) y
-- fact_depositos (producto_deposito_id -> categoria_deposito_id/plazo_id), agrega CDC
-- (fecha_carga/fecha_actualizacion/row_hash), y trunca ambas para repoblarlas desde
-- staging con refresh_marts() (igual que se hizo con dim_banco/dim_fecha: más simple y
-- seguro que migrar los datos de las FKs en sitio).

ALTER TABLE staging.depositos
    ALTER COLUMN categoria_deposito SET NOT NULL;

TRUNCATE TABLE marts.fact_cartera, marts.fact_depositos;

ALTER TABLE marts.fact_cartera
    DROP COLUMN producto_cartera_id,
    ADD COLUMN tipo_credito TEXT,
    ADD COLUMN estado_cartera TEXT,
    ADD COLUMN fecha_carga TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE marts.fact_cartera
    ALTER COLUMN tipo_credito SET NOT NULL,
    ALTER COLUMN estado_cartera SET NOT NULL,
    ADD CONSTRAINT fact_cartera_estado_check CHECK (estado_cartera IN
        ('por_vencer', 'no_devenga_intereses', 'vencida')),
    ADD CONSTRAINT fact_cartera_unique UNIQUE (fecha_id, banco_id, canton_id, tipo_credito, estado_cartera);

ALTER TABLE marts.fact_cartera
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(saldo::text || '|' || COALESCE(tasa_ponderada::text, '') || '|' || COALESCE(morosidad::text, ''))
    ) STORED;

ALTER TABLE marts.fact_depositos
    DROP COLUMN producto_deposito_id,
    ADD COLUMN categoria_deposito_id INT REFERENCES marts.dim_categoria_deposito (categoria_deposito_id),
    ADD COLUMN plazo_id INT REFERENCES marts.dim_plazo (plazo_id),
    ADD COLUMN fecha_carga TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE marts.fact_depositos
    ALTER COLUMN categoria_deposito_id SET NOT NULL,
    ADD CONSTRAINT fact_depositos_unique UNIQUE (fecha_id, banco_id, canton_id, categoria_deposito_id, plazo_id);

ALTER TABLE marts.fact_depositos
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(saldo::text || '|' || COALESCE(numero_clientes::text, '') || '|' || COALESCE(numero_cuentas::text, ''))
    ) STORED;

-- dim_producto_cartera / dim_producto_deposito quedan reemplazadas por lo de arriba;
-- se eliminan las vistas que las referenciaban antes de poder eliminarlas (ver
-- 04b_views_rework.sql), y luego las tablas mismas.
