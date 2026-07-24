-- La antigua marts.dim_segmento_credito (26 valores, columna tipo_credito_capcol TEXT
-- nullable) mezclaba dos niveles reales de una jerarquía normativa (JPRF/BCE:
-- segmentación de la cartera de crédito) en una sola tabla, y el rollup a CAPCOL era
-- texto libre sin FK (podía desincronizarse entre fact_saldo_cartera.tipo_credito y
-- dim_segmento_credito.tipo_credito_capcol sin que nada lo impidiera). Se separa en 2
-- dimensiones normalizadas:
--   - marts.dim_subsegmento_credito (antes dim_segmento_credito): el subsegmento fino
--     tal como lo reporta BCE (26 valores, columna renombrada segmento -> subsegmento).
--   - marts.dim_segmento_credito (nueva): el segmento normativo superior (7 valores),
--     mismo nombre de tabla que antes tenía el nivel fino -- se libera renombrando la
--     tabla vieja primero.
-- fact_saldo_cartera (CAPCOL, solo reporta al nivel grueso) pasa de tipo_credito TEXT a
-- segmento_id INT FK -- queda normalizado contra el mismo catálogo que usan los hechos
-- de BCE, en vez de duplicar el nombre del segmento como texto suelto.
-- fact_colocaciones_cartera / fact_tasas_referenciales_cartera (BCE, reportan al nivel
-- fino) pasan su columna segmento_id -> subsegmento_id, apuntando a la tabla renombrada.
--
-- Mapeo subsegmento -> segmento: PRODUCTIVO agrupa tanto la terminología vigente
-- ("Productivo Corporativo/Empresarial/PYMES/Agrícola y Ganadero") como la terminología
-- previa a la revisión metodológica de abril-julio 2022 (JPRF-F-2022-031/053), que usaba
-- "Comercial" para el mismo segmento -- mismo segmento normativo, dos nombres según la
-- época de la serie histórica (2008-2026). INMOBILIARIO agrupa "Inmobiliario" y la forma
-- histórica "Vivienda" (crédito de vivienda ordinario, no social). VIVIENDA DE INTERÉS
-- PÚBLICO agrupa esa forma y "Vivienda de Interés Social" (mismo segmento de vivienda
-- social/pública con techo de tasa propio, dos nombres en la serie histórica). MICROCRÉDITO
-- agrupa las 7 variantes, incluidas las 3 con sufijo "(SE)" (Sector Financiero Popular y
-- Solidario -- variante del mismo subsegmento bajo la metodología de cooperativas, no un
-- segmento distinto). INVERSIÓN PÚBLICA es su propio segmento (aparece como línea propia,
-- no anidada bajo Productivo, en TASAS DE INTERÉS ACTIVAS MÁXIMAS VIGENTES -- ver
-- docs/fuentes_datos.md sección 2.3). Con este mapeo ningún subsegmento queda sin
-- segmento_id (antes había 4 en NULL por falta de correspondencia CAPCOL).

ALTER TABLE marts.dim_segmento_credito RENAME TO dim_subsegmento_credito;
ALTER TABLE marts.dim_subsegmento_credito RENAME COLUMN segmento_id TO subsegmento_id;
ALTER TABLE marts.dim_subsegmento_credito RENAME COLUMN segmento TO subsegmento;
ALTER TABLE marts.dim_subsegmento_credito RENAME CONSTRAINT dim_segmento_credito_pkey TO dim_subsegmento_credito_pkey;
ALTER TABLE marts.dim_subsegmento_credito RENAME CONSTRAINT dim_segmento_credito_segmento_key TO dim_subsegmento_credito_subsegmento_key;

CREATE TABLE marts.dim_segmento_credito (
    segmento_id SERIAL PRIMARY KEY,
    segmento    TEXT NOT NULL UNIQUE
);

INSERT INTO marts.dim_segmento_credito (segmento) VALUES
    ('PRODUCTIVO'),
    ('CONSUMO'),
    ('EDUCATIVO'),
    ('INMOBILIARIO'),
    ('VIVIENDA DE INTERÉS PÚBLICO'),
    ('MICROCRÉDITO'),
    ('INVERSIÓN PÚBLICA');

ALTER TABLE marts.dim_subsegmento_credito DROP COLUMN tipo_credito_capcol;
ALTER TABLE marts.dim_subsegmento_credito
    ADD COLUMN segmento_id INT REFERENCES marts.dim_segmento_credito (segmento_id);

UPDATE marts.dim_subsegmento_credito ds
SET segmento_id = sg.segmento_id
FROM marts.dim_segmento_credito sg, (VALUES
    ('COMERCIAL ORDINARIO', 'PRODUCTIVO'),
    ('COMERCIAL PRIORITARIO CORPORATIVO', 'PRODUCTIVO'),
    ('COMERCIAL PRIORITARIO EMPRESARIAL', 'PRODUCTIVO'),
    ('COMERCIAL PRIORITARIO PYMES', 'PRODUCTIVO'),
    ('CONSUMO', 'CONSUMO'),
    ('CONSUMO MINORISTA', 'CONSUMO'),
    ('CONSUMO ORDINARIO', 'CONSUMO'),
    ('CONSUMO PRIORITARIO', 'CONSUMO'),
    ('EDUCATIVO', 'EDUCATIVO'),
    ('EDUCATIVO SOCIAL', 'EDUCATIVO'),
    ('INMOBILIARIO', 'INMOBILIARIO'),
    ('INVERSIÓN PÚBLICA', 'INVERSIÓN PÚBLICA'),
    ('MICROCRÉDITO ACUMULACIÓN AMPLIADA (SE)', 'MICROCRÉDITO'),
    ('MICROCRÉDITO ACUMULACIÓN SIMPLE (SE)', 'MICROCRÉDITO'),
    ('MICROCRÉDITO AGRÍCOLA Y GANADERO', 'MICROCRÉDITO'),
    ('MICROCRÉDITO DE ACUMULACIÓN AMPLIADA', 'MICROCRÉDITO'),
    ('MICROCRÉDITO DE ACUMULACIÓN SIMPLE', 'MICROCRÉDITO'),
    ('MICROCRÉDITO MINORISTA', 'MICROCRÉDITO'),
    ('MICROCRÉDITO MINORISTA (SE)', 'MICROCRÉDITO'),
    ('PRODUCTIVO - CORPORATIVO', 'PRODUCTIVO'),
    ('PRODUCTIVO AGRÍCOLA Y GANADERO', 'PRODUCTIVO'),
    ('PRODUCTIVO EMPRESARIAL', 'PRODUCTIVO'),
    ('PRODUCTIVO PYMES', 'PRODUCTIVO'),
    ('VIVIENDA', 'INMOBILIARIO'),
    ('VIVIENDA DE INTERÉS PÚBLICO', 'VIVIENDA DE INTERÉS PÚBLICO'),
    ('VIVIENDA DE INTERÉS SOCIAL', 'VIVIENDA DE INTERÉS PÚBLICO')
) AS m(subsegmento, segmento)
WHERE ds.subsegmento = m.subsegmento AND sg.segmento = m.segmento;

ALTER TABLE marts.dim_subsegmento_credito ALTER COLUMN segmento_id SET NOT NULL;

-- fact_colocaciones_cartera / fact_tasas_referenciales_cartera: mismo grano de antes
-- (el subsegmento fino de BCE), solo cambia el nombre de columna/FK a la tabla renombrada.
ALTER TABLE marts.fact_colocaciones_cartera RENAME COLUMN segmento_id TO subsegmento_id;
ALTER TABLE marts.fact_colocaciones_cartera
    RENAME CONSTRAINT fact_tasas_activas_segmento_id_fkey TO fact_colocaciones_cartera_subsegmento_id_fkey;
DROP INDEX marts.fact_colocaciones_cartera_unique;
CREATE UNIQUE INDEX fact_colocaciones_cartera_unique
    ON marts.fact_colocaciones_cartera (fecha_id, banco_id, subsegmento_id, plazo_id, COALESCE(provincia, ''));

ALTER TABLE marts.fact_tasas_referenciales_cartera RENAME COLUMN segmento_id TO subsegmento_id;
ALTER TABLE marts.fact_tasas_referenciales_cartera
    RENAME CONSTRAINT fact_tasas_referenciales_credito_segmento_id_fkey TO fact_tasas_referenciales_cartera_subsegmento_id_fkey;
-- PRIMARY KEY (fecha_id, segmento_id) se renombra de forma implícita con la columna;
-- el nombre del constraint (fact_tasas_referenciales_cartera_pkey) no depende del nombre
-- de columna y no requiere RENAME CONSTRAINT.

-- fact_saldo_cartera (CAPCOL): tipo_credito TEXT -> segmento_id INT FK al segmento
-- normativo grueso (su grano real -- CAPCOL nunca reporta al nivel de subsegmento).
ALTER TABLE marts.fact_saldo_cartera DROP COLUMN row_hash;
ALTER TABLE marts.fact_saldo_cartera
    ADD COLUMN segmento_id INT REFERENCES marts.dim_segmento_credito (segmento_id);

UPDATE marts.fact_saldo_cartera f
SET segmento_id = sg.segmento_id
FROM marts.dim_segmento_credito sg, (VALUES
    ('comercial', 'PRODUCTIVO'),
    ('consumo', 'CONSUMO'),
    ('inmobiliario', 'INMOBILIARIO'),
    ('microcredito', 'MICROCRÉDITO'),
    ('vivienda_interes_publico', 'VIVIENDA DE INTERÉS PÚBLICO'),
    ('educativo', 'EDUCATIVO')
) AS m(tipo_credito, segmento)
WHERE f.tipo_credito = m.tipo_credito AND sg.segmento = m.segmento;

ALTER TABLE marts.fact_saldo_cartera ALTER COLUMN segmento_id SET NOT NULL;
ALTER TABLE marts.fact_saldo_cartera DROP CONSTRAINT fact_saldo_cartera_unique;
ALTER TABLE marts.fact_saldo_cartera
    ADD CONSTRAINT fact_saldo_cartera_unique UNIQUE (fecha_id, banco_id, canton_id, segmento_id, estado_cartera);
ALTER TABLE marts.fact_saldo_cartera DROP COLUMN tipo_credito;
ALTER TABLE marts.fact_saldo_cartera
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (md5(saldo::text)) STORED;
