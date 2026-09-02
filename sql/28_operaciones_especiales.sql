-- Operaciones Especiales (Banco de Guayaquil) -- es_operacion_especial.
--
-- Las filas vienen de `operaciones_especiales.xlsx` (SharePoint:
-- DataEngineeringBG-FINANCIERO/BENCHMARK_TASAS, descarga manual a data/raw), la misma
-- estructura que BCE tsa, marcadas `es_operacion_especial = 'SI'` (el resto de la
-- cartera de tsa es 'NO'). El tablero anterior anexaba ese xlsx a Tabla_Activos; acá se
-- integran al mismo grano de marts.fact_colocaciones_cartera para que el Power BI las
-- lea directo del parquet y los totales incluyan SI (comportamiento del tablero anterior).
--
-- Como las filas SI conviven con filas NO del MISMO grano (fecha, banco, subsegmento,
-- plazo, provincia), el flag entra a la llave natural de staging y marts, y al row_hash
-- (mismo patrón CDC de sql/19). Patrón NULL-safe de sql/10/sql/23/24 para las llaves.

-- staging.bce_tasas_activas: columna + row_hash recalculado.
ALTER TABLE staging.bce_tasas_activas ADD COLUMN IF NOT EXISTS es_operacion_especial TEXT NOT NULL DEFAULT 'NO';
ALTER TABLE staging.bce_tasas_activas DROP COLUMN IF EXISTS row_hash;
ALTER TABLE staging.bce_tasas_activas
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_activa_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, '') || '|' ||
            COALESCE(tipo_segmento, '') || '|' || es_operacion_especial)
    ) STORED;

-- Llave única de staging extendida: el flag SI/NO es parte del grano.
DROP INDEX IF EXISTS staging_bce_tasas_activas_unique;
CREATE UNIQUE INDEX staging_bce_tasas_activas_unique
    ON staging.bce_tasas_activas (fecha, banco_codigo, segmento_credito, plazo_dias_desde,
                                   COALESCE(plazo_dias_hasta, -1), COALESCE(provincia, ''), es_operacion_especial);

-- marts.fact_colocaciones_cartera: columna + row_hash recalculado.
ALTER TABLE marts.fact_colocaciones_cartera ADD COLUMN IF NOT EXISTS es_operacion_especial TEXT NOT NULL DEFAULT 'NO';
ALTER TABLE marts.fact_colocaciones_cartera DROP COLUMN IF EXISTS row_hash;
ALTER TABLE marts.fact_colocaciones_cartera
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_activa_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, '') || '|' ||
            COALESCE(segmento_entidad_id::text, '') || '|' || es_operacion_especial)
    ) STORED;

-- Llave única de marts extendida (mismo criterio).
DROP INDEX IF EXISTS marts.fact_colocaciones_cartera_unique;
CREATE UNIQUE INDEX fact_colocaciones_cartera_unique
    ON marts.fact_colocaciones_cartera (fecha_id, banco_id, subsegmento_id, plazo_id, COALESCE(provincia_id, -1), es_operacion_especial);