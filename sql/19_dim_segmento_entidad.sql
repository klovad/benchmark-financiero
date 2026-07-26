-- tipo_segmento del BCE (tsp/tsa) es la clasificación normativa de tamaño/estructura de
-- cada ENTIDAD (no del producto -- eso ya lo cubre dim_segmento_credito/dim_subsegmento_credito):
-- BANCO GRANDE/MEDIANO/PEQUEÑO para bancos privados, SEGMENTO 1-5/SIN SEGMENTO para
-- cooperativas (JPRF-F-2023-074, segmentación por activos), SEGMENTO 1 MUTUALISTA para
-- mutualistas, una sola categoría para bancos públicos/sociedad financiera/tarjetas.
-- Se preservaba en raw.* pero se descartaba antes de staging sin examinar su contenido
-- (detectado 2026-07-25, el usuario preguntó dónde se había considerado). Es un atributo
-- de la entidad EN ESA FECHA, no fijo -- verificado: cooperativas reales cambian de
-- segmento con los años según crecen -- así que se modela al grano semanal donde ya vive
-- (fecha, banco) en fact_captaciones_depositos/fact_colocaciones_cartera, no como columna
-- estática en dim_banco. dim_banco sí gana una columna de conveniencia con la ÚLTIMA
-- clasificación conocida, para análisis puntuales con la clasificación actual sin tener
-- que ir a buscar la fila más reciente de los hechos.

CREATE TABLE IF NOT EXISTS marts.dim_segmento_entidad (
    segmento_entidad_id  SERIAL PRIMARY KEY,
    tipo_segmento        TEXT NOT NULL UNIQUE
);

INSERT INTO marts.dim_segmento_entidad (tipo_segmento) VALUES
    ('BANCO GRANDE'), ('BANCO MEDIANO'), ('BANCO PEQUEÑO'), ('BANCOS PUBLICOS'),
    ('SEGMENTO 1'), ('SEGMENTO 2'), ('SEGMENTO 3'), ('SEGMENTO 4'), ('SEGMENTO 5'), ('SIN SEGMENTO'),
    ('SEGMENTO 1 MUTUALISTA'), ('MUTUALISTAS'),
    ('SOCIEDAD FINANCIERA'), ('ADMINISTRADORA DE TARJETAS DE CREDITO')
ON CONFLICT (tipo_segmento) DO NOTHING;

-- staging.bce_tasas_pasivas / bce_tasas_activas: nueva columna + row_hash recalculado
-- para que un cambio real de tipo_segmento sí dispare el guard de CDC.
ALTER TABLE staging.bce_tasas_pasivas ADD COLUMN IF NOT EXISTS tipo_segmento TEXT;
ALTER TABLE staging.bce_tasas_pasivas DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.bce_tasas_pasivas
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_pasiva_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, '') || '|' ||
            COALESCE(tipo_segmento, ''))
    ) STORED;

ALTER TABLE staging.bce_tasas_activas ADD COLUMN IF NOT EXISTS tipo_segmento TEXT;
ALTER TABLE staging.bce_tasas_activas DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.bce_tasas_activas
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_activa_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, '') || '|' ||
            COALESCE(tipo_segmento, ''))
    ) STORED;

-- marts.fact_captaciones_depositos / fact_colocaciones_cartera: FK a dim_segmento_entidad,
-- también entra al row_hash (mismo criterio: si la fuente corrige/reclasifica, se refleja).
ALTER TABLE marts.fact_captaciones_depositos
    ADD COLUMN IF NOT EXISTS segmento_entidad_id INT REFERENCES marts.dim_segmento_entidad (segmento_entidad_id);
ALTER TABLE marts.fact_captaciones_depositos DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_captaciones_depositos
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_pasiva_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, '') || '|' ||
            COALESCE(segmento_entidad_id::text, ''))
    ) STORED;

ALTER TABLE marts.fact_colocaciones_cartera
    ADD COLUMN IF NOT EXISTS segmento_entidad_id INT REFERENCES marts.dim_segmento_entidad (segmento_entidad_id);
ALTER TABLE marts.fact_colocaciones_cartera DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_colocaciones_cartera
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_activa_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, '') || '|' ||
            COALESCE(segmento_entidad_id::text, ''))
    ) STORED;

-- marts.dim_banco: columna de conveniencia con la ÚLTIMA clasificación conocida
-- (SCD tipo 1, igual criterio que se había planteado para tamano) -- poblada en
-- refresh_marts() desde la fila más reciente de los hechos BCE, no desde una fuente
-- propia (BCE es la única fuente que trae esto).
ALTER TABLE marts.dim_banco
    ADD COLUMN IF NOT EXISTS segmento_entidad_id INT REFERENCES marts.dim_segmento_entidad (segmento_entidad_id);
ALTER TABLE marts.dim_banco DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.dim_banco
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(banco || '|' || tipo_entidad || '|' || COALESCE(ruc, '') || '|' || COALESCE(segmento_entidad_id::text, ''))
    ) STORED;
