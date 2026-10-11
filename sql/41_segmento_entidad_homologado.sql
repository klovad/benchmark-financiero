-- Homologación de dim_segmento_entidad y fin de los nulos (2026-10-10).
--
-- 1. Mutualistas: el BCE las etiquetó "SEGMENTO 1 MUTUALISTA" hasta 2024-12 y
--    "MUTUALISTAS" desde 2025-01 -- mismas entidades, misma clasificación normativa
--    (la norma de segmentación del sector popular y solidario las ubica en el Segmento 1,
--    y la SEPS sigue publicando "SEGMENTO 1 MUTUALISTA"). Se deja un solo valor: los
--    hechos y staging de 2025+ pasan al de siempre y "MUTUALISTAS" sale del catálogo.
--    parse_bce_tasas.ALIAS_TIPO_SEGMENTO homologa las cargas futuras.
-- 2. "NO REPORTA AL BCE": valor para las entidades sin filas en tsp/tsa (segundo piso:
--    CONAFIPS, Caja Central FINANCOOP; o una entidad nueva que solo llega por SEPS/CAPCOL).
--    refresh_marts() lo asigna por defecto al dar de alta una entidad, y el UPDATE desde los
--    hechos BCE lo reemplaza si después aparecen.
-- 3. segmento_entidad_id pasa a NOT NULL en dim_entidad y en los dos hechos BCE. En
--    dim_entidad su DEFAULT es el id de 'NO REPORTA AL BCE', así un alta manual que no
--    indique segmento tampoco deja nulo (el id depende del servidor: se resuelve acá).
--
-- El resto de valores (BANCO GRANDE, BANCOS PUBLICOS, SIN SEGMENTO, ...) queda como lo
-- publica el BCE.

-- Sin ON CONFLICT: un INSERT en conflicto igual gasta un id de la secuencia.
INSERT INTO marts.dim_segmento_entidad (tipo_segmento)
SELECT 'SEGMENTO 1 MUTUALISTA'
WHERE NOT EXISTS (SELECT 1 FROM marts.dim_segmento_entidad WHERE tipo_segmento = 'SEGMENTO 1 MUTUALISTA');

UPDATE staging.bce_tasas_pasivas SET tipo_segmento = 'SEGMENTO 1 MUTUALISTA'
WHERE tipo_segmento = 'MUTUALISTAS';
UPDATE staging.bce_tasas_activas SET tipo_segmento = 'SEGMENTO 1 MUTUALISTA'
WHERE tipo_segmento = 'MUTUALISTAS';

UPDATE marts.fact_captaciones_depositos f
SET segmento_entidad_id = nuevo.segmento_entidad_id
FROM marts.dim_segmento_entidad viejo, marts.dim_segmento_entidad nuevo
WHERE f.segmento_entidad_id = viejo.segmento_entidad_id
  AND viejo.tipo_segmento = 'MUTUALISTAS' AND nuevo.tipo_segmento = 'SEGMENTO 1 MUTUALISTA';

UPDATE marts.fact_colocaciones_cartera f
SET segmento_entidad_id = nuevo.segmento_entidad_id
FROM marts.dim_segmento_entidad viejo, marts.dim_segmento_entidad nuevo
WHERE f.segmento_entidad_id = viejo.segmento_entidad_id
  AND viejo.tipo_segmento = 'MUTUALISTAS' AND nuevo.tipo_segmento = 'SEGMENTO 1 MUTUALISTA';

UPDATE marts.dim_entidad e
SET segmento_entidad_id = nuevo.segmento_entidad_id, fecha_actualizacion = now()
FROM marts.dim_segmento_entidad viejo, marts.dim_segmento_entidad nuevo
WHERE e.segmento_entidad_id = viejo.segmento_entidad_id
  AND viejo.tipo_segmento = 'MUTUALISTAS' AND nuevo.tipo_segmento = 'SEGMENTO 1 MUTUALISTA';

-- La fila 'MUTUALISTAS' ya no tiene referencias: se reusa (mismo id) como
-- 'NO REPORTA AL BCE', así el catálogo queda con ids 1..14 sin huecos. Si no existiera,
-- se crea.
UPDATE marts.dim_segmento_entidad SET tipo_segmento = 'NO REPORTA AL BCE'
WHERE tipo_segmento = 'MUTUALISTAS'
  AND NOT EXISTS (SELECT 1 FROM marts.dim_segmento_entidad WHERE tipo_segmento = 'NO REPORTA AL BCE');
DELETE FROM marts.dim_segmento_entidad WHERE tipo_segmento = 'MUTUALISTAS';
INSERT INTO marts.dim_segmento_entidad (tipo_segmento)
SELECT 'NO REPORTA AL BCE'
WHERE NOT EXISTS (SELECT 1 FROM marts.dim_segmento_entidad WHERE tipo_segmento = 'NO REPORTA AL BCE');

UPDATE marts.dim_entidad e
SET segmento_entidad_id = s.segmento_entidad_id, fecha_actualizacion = now()
FROM marts.dim_segmento_entidad s
WHERE e.segmento_entidad_id IS NULL AND s.tipo_segmento = 'NO REPORTA AL BCE';

ALTER TABLE marts.dim_entidad ALTER COLUMN segmento_entidad_id SET NOT NULL;
ALTER TABLE marts.fact_captaciones_depositos ALTER COLUMN segmento_entidad_id SET NOT NULL;
ALTER TABLE marts.fact_colocaciones_cartera ALTER COLUMN segmento_entidad_id SET NOT NULL;

DO $$
BEGIN
    EXECUTE format('ALTER TABLE marts.dim_entidad ALTER COLUMN segmento_entidad_id SET DEFAULT %s',
        (SELECT segmento_entidad_id FROM marts.dim_segmento_entidad WHERE tipo_segmento = 'NO REPORTA AL BCE'));
END $$;
