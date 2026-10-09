-- Fusión de 2 cantones duplicados por variante de escritura (2026-10-09).
--
-- Dos fuentes escribían un cantón ya curado con otra forma, y refresh_marts() los
-- auto-ingresó en marts.dim_canton como cantones nuevos (estado_validacion =
-- 'AUTO_INGRESADO'), partiendo los saldos del mismo cantón en dos filas:
--
--   variante (fuente)                              canónico (curado)                   INEC
--   ALFREDO BAQUERIZO MORENO (SEPS, cooperativas)  ALFREDO BAQUERIZO MORENO (JUJAN)    0902 Guayas
--   PABLO VI (CAPCOL Banca Pública)                PABLO SEXTO                         1411 Morona Santiago
--
-- Verificado contra el clasificador geográfico del INEC (DPA): en cada provincia hay un
-- solo cantón con ese nombre, así que son el mismo cantón y no homónimos. Los homónimos
-- reales (BOLIVAR Carchi/Manabí, OLMEDO Loja/Manabí) no se tocan.
--
-- La causa se corrige en el código (canton_matching.py::aplicar_alias_canton, aplicado
-- ahora a todas las fuentes). Esta migración solo corrige lo ya cargado:
--   1. staging: renombra la variante al canónico (marca fecha_actualizacion).
--   2. marts: reasigna las filas de hechos al canton_id canónico y borra el duplicado.
-- Se verificó antes que no hay choques de llave natural entre la variante y el canónico
-- en staging.cartera/depositos ni en fact_saldo_cartera/depositos.
--
-- Idempotente: en una base nueva (sin la variante) no hace nada.

BEGIN;

CREATE TEMP TABLE _alias_canton (variante text, canonico text, provincia text) ON COMMIT DROP;
INSERT INTO _alias_canton VALUES
    ('ALFREDO BAQUERIZO MORENO', 'ALFREDO BAQUERIZO MORENO (JUJAN)', 'GUAYAS'),
    ('PABLO VI',                 'PABLO SEXTO',                      'MORONA SANTIAGO');

-- 1. staging
UPDATE staging.cartera s
SET canton = a.canonico, fecha_actualizacion = now()
FROM _alias_canton a
WHERE s.canton = a.variante AND s.provincia = a.provincia;

UPDATE staging.depositos s
SET canton = a.canonico, fecha_actualizacion = now()
FROM _alias_canton a
WHERE s.canton = a.variante AND s.provincia = a.provincia;

UPDATE staging.bce_tasas_activas s
SET canton = a.canonico, fecha_actualizacion = now()
FROM _alias_canton a
WHERE s.canton = a.variante AND s.provincia = a.provincia;

UPDATE staging.bce_tasas_pasivas s
SET canton = a.canonico, fecha_actualizacion = now()
FROM _alias_canton a
WHERE s.canton = a.variante AND s.provincia = a.provincia;

-- 2. marts: pares (id duplicado -> id canónico)
CREATE TEMP TABLE _fusion_canton ON COMMIT DROP AS
SELECT dup.canton_id AS id_dup, can.canton_id AS id_canonico
FROM _alias_canton a
JOIN marts.dim_provincia p   ON p.provincia = a.provincia
JOIN marts.dim_canton dup    ON dup.canton = a.variante AND dup.provincia_id = p.provincia_id
JOIN marts.dim_canton can    ON can.canton = a.canonico AND can.provincia_id = p.provincia_id;

UPDATE marts.fact_saldo_cartera f
SET canton_id = m.id_canonico, fecha_actualizacion = now()
FROM _fusion_canton m WHERE f.canton_id = m.id_dup;

UPDATE marts.fact_saldo_depositos f
SET canton_id = m.id_canonico, fecha_actualizacion = now()
FROM _fusion_canton m WHERE f.canton_id = m.id_dup;

UPDATE marts.fact_colocaciones_cartera f
SET canton_id = m.id_canonico, fecha_actualizacion = now()
FROM _fusion_canton m WHERE f.canton_id = m.id_dup;

UPDATE marts.fact_captaciones_depositos f
SET canton_id = m.id_canonico, fecha_actualizacion = now()
FROM _fusion_canton m WHERE f.canton_id = m.id_dup;

DELETE FROM marts.dim_canton d
USING _fusion_canton m
WHERE d.canton_id = m.id_dup;

COMMIT;
