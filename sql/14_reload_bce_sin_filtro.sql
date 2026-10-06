-- Fuerza el reprocesamiento completo de BCE tsp/tsa con la nueva lógica sin filtro de
-- tipo_entidad (ver src/benchmark_bancos/transform/parse_bce_tasas.py -- versión anterior filtraba a
-- BANCOS PRIVADOS antes de que el dato llegara a raw.*, perdiendo ~85% de las filas:
-- 456/466 entidades reales del sistema financiero completo, no solo los ~33 bancos
-- privados). No cambia el schema (raw.bce_tasas_pasivas/activas ya tenían la forma
-- genérica id/source_file/source_hash/anio/mes/data JSONB -- solo cambia QUÉ va dentro
-- del JSONB), así que basta con vaciar y reprocesar, no hace falta ALTER TABLE.

TRUNCATE TABLE staging.bce_tasas_pasivas, staging.bce_tasas_activas;
TRUNCATE TABLE marts.fact_tasas_pasivas, marts.fact_tasas_activas;

-- Libera el hash registrado para que is_source_loaded() no salte el reprocesamiento.
DELETE FROM meta.source_files WHERE report_type IN ('bce_tasas_pasivas', 'bce_tasas_activas');
