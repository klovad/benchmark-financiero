-- dim_provincia: catálogo canónico de provincia/región, compartido entre CAPCOL
-- (dim_canton, grano cantón) y BCE tsp/tsa (fact_captaciones_depositos/
-- fact_colocaciones_cartera, grano provincia -- no traen cantón). Antes cada tabla
-- guardaba su propio texto suelto de provincia/región; detectado 2026-07-25 (el usuario
-- preguntó si hacía falta normalizar provincia en los hechos BCE) que esto ya escondía
-- un bug real: marts.dim_canton tenía DOS regiones distintas para MORONA SANTIAGO
-- (depositos confiaba en la columna REGION del archivo fuente = "AMAZONICA"; cartera la
-- derivaba de PROVINCIA_REGION = "ORIENTE", el mapeo canónico -- ver
-- etl/transform/parse_depositos.py, ya corregido para no usar la columna del archivo).
-- dim_provincia es ahora la ÚNICA fuente de region -- el bug queda estructuralmente
-- imposible de repetir. Sembrada desde etl/config.py::PROVINCIA_REGION (24 provincias)
-- + 2 valores especiales sin provincia real: 'ZONA NO DELIMITADA' (CAPCOL) y 'S/N' (BCE,
-- filas a nivel nacional sin desagregar).
--
-- Ortografía canónica: la de CAPCOL (histórico más largo, ya en dim_canton) -- sin tilde
-- excepto en la Ñ (BOLIVAR, GALAPAGOS, LOS RIOS... pero CAÑAR). BCE trae las mismas
-- provincias CON tilde (BOLÍVAR, GALÁPAGOS); se homologa en el parser con
-- etl/transform/common.py::normalize_provincia() (quita solo el acento agudo tras
-- descomponer NFKD, conserva la Ñ -- ver docstring de la función).

CREATE TABLE IF NOT EXISTS marts.dim_provincia (
    provincia_id  SERIAL PRIMARY KEY,
    provincia     TEXT NOT NULL UNIQUE,
    region        TEXT
);

INSERT INTO marts.dim_provincia (provincia, region) VALUES
    ('AZUAY', 'SIERRA'), ('BOLIVAR', 'SIERRA'), ('CAÑAR', 'SIERRA'), ('CARCHI', 'SIERRA'),
    ('COTOPAXI', 'SIERRA'), ('CHIMBORAZO', 'SIERRA'), ('IMBABURA', 'SIERRA'), ('LOJA', 'SIERRA'),
    ('PICHINCHA', 'SIERRA'), ('TUNGURAHUA', 'SIERRA'), ('SANTO DOMINGO DE LOS TSACHILAS', 'SIERRA'),
    ('EL ORO', 'COSTA'), ('ESMERALDAS', 'COSTA'), ('GUAYAS', 'COSTA'), ('LOS RIOS', 'COSTA'),
    ('MANABI', 'COSTA'), ('SANTA ELENA', 'COSTA'),
    ('MORONA SANTIAGO', 'ORIENTE'), ('NAPO', 'ORIENTE'), ('ORELLANA', 'ORIENTE'),
    ('PASTAZA', 'ORIENTE'), ('SUCUMBIOS', 'ORIENTE'), ('ZAMORA CHINCHIPE', 'ORIENTE'),
    ('GALAPAGOS', 'INSULAR'),
    ('ZONA NO DELIMITADA', NULL), ('S/N', NULL)
ON CONFLICT (provincia) DO NOTHING;

-- dim_canton: provincia/region (texto) -> provincia_id (FK). Backfill directo por texto
-- exacto: el valor ya almacenado en dim_canton viene de CAPCOL, que ya usa la ortografía
-- canónica (de ahí se sembró dim_provincia), así que no hay fila que no matchee.
-- translate() en vez de igualdad exacta: al menos una provincia ya cargada
-- ("SANTO DOMINGO DE LOS TSÁCHILAS") conserva tilde en el archivo CAPCOL histórico,
-- a diferencia del resto (que la fuente ya escribe sin tilde) -- mismo criterio que
-- normalize_provincia() en Python (quita vocal acentuada, conserva Ñ), aplicado acá en
-- SQL porque este backfill corre una sola vez sobre datos ya cargados.
ALTER TABLE marts.dim_canton ADD COLUMN IF NOT EXISTS provincia_id INT REFERENCES marts.dim_provincia (provincia_id);
UPDATE marts.dim_canton c SET provincia_id = dp.provincia_id
FROM marts.dim_provincia dp
WHERE dp.provincia = translate(c.provincia, 'ÁÉÍÓÚ', 'AEIOU') AND c.provincia_id IS NULL;
ALTER TABLE marts.dim_canton ALTER COLUMN provincia_id SET NOT NULL;
ALTER TABLE marts.dim_canton DROP CONSTRAINT IF EXISTS dim_canton_canton_provincia_key;
ALTER TABLE marts.dim_canton ADD CONSTRAINT dim_canton_canton_provincia_key UNIQUE (canton, provincia_id);
ALTER TABLE marts.dim_canton DROP COLUMN IF EXISTS provincia;
ALTER TABLE marts.dim_canton DROP COLUMN IF EXISTS region;

-- fact_captaciones_depositos / fact_colocaciones_cartera: provincia (texto) -> provincia_id
-- (FK). A diferencia de dim_canton, varias filas ya cargadas traen provincia CON tilde
-- (BOLÍVAR, GALÁPAGOS...) que no matchea la ortografía canónica -- en vez de un backfill
-- parcial + reconciliar contra un UNIQUE INDEX que está cambiando de forma, se trunca y
-- se reconstruye completo desde staging (vía el reproceso de tsp/tsa que sigue a esta
-- migración): no se pierde nada, staging.bce_tasas_pasivas/activas ya tiene el histórico
-- completo y va a quedar con provincia ya homologada por el parser actualizado.
TRUNCATE marts.fact_captaciones_depositos;
TRUNCATE marts.fact_colocaciones_cartera;

ALTER TABLE marts.fact_captaciones_depositos DROP COLUMN IF EXISTS provincia;
ALTER TABLE marts.fact_captaciones_depositos
    ADD COLUMN IF NOT EXISTS provincia_id INT REFERENCES marts.dim_provincia (provincia_id);
DROP INDEX IF EXISTS marts.fact_captaciones_depositos_unique;
CREATE UNIQUE INDEX fact_captaciones_depositos_unique
    ON marts.fact_captaciones_depositos (fecha_id, banco_id, categoria_deposito_id, plazo_id, COALESCE(provincia_id, -1));

ALTER TABLE marts.fact_colocaciones_cartera DROP COLUMN IF EXISTS provincia;
ALTER TABLE marts.fact_colocaciones_cartera
    ADD COLUMN IF NOT EXISTS provincia_id INT REFERENCES marts.dim_provincia (provincia_id);
DROP INDEX IF EXISTS marts.fact_colocaciones_cartera_unique;
CREATE UNIQUE INDEX fact_colocaciones_cartera_unique
    ON marts.fact_colocaciones_cartera (fecha_id, banco_id, subsegmento_id, plazo_id, COALESCE(provincia_id, -1));
