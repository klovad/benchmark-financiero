-- Bug: la llave natural de staging.cartera / staging.depositos (sql/23, sql/24) usa
-- `canton` sin `provincia`. En Ecuador hay cantones homónimos en provincias distintas
-- (BOLÍVAR: Carchi / Manabí; LA CONCORDIA, SANTO DOMINGO, LORETO, AGUARICO -- ver
-- etl/transform/canton_matching.py, que por eso siempre resuelve el PAR). Si una misma
-- entidad reporta los dos cantones homónimos en el mismo mes, las dos filas chocan en la
-- llave: con el executemany anterior la segunda pisaba a la primera sin error (pérdida
-- silenciosa de saldo); con COPY + INSERT ... SELECT falla con CardinalityViolation.
--
-- Encontrado 2026-09-30 al cargar SEPS 2021 (OSCUS y Magisterio Manabita reportan
-- BOLÍVAR/CARCHI y BOLÍVAR/MANABÍ). Verificado contra raw.cartera / raw.depositos que
-- CAPCOL (bancos privados) nunca cayó en el caso: 0 pares colisionantes, así que no hubo
-- pérdida histórica que reprocesar. Las fact tables no tienen el problema: resuelven a
-- canton_id, que ya distingue el par (canton, provincia).
--
-- Mismo patrón NULL-safe (COALESCE(col, '')) que sql/23/24.

CREATE UNIQUE INDEX IF NOT EXISTS staging_cartera_natural_key_v2
    ON staging.cartera (fecha, tipo_entidad, banco, COALESCE(provincia, ''), COALESCE(canton, ''),
                        tipo_credito, estado_cartera);
DROP INDEX IF EXISTS staging.staging_cartera_natural_key_unique;

CREATE UNIQUE INDEX IF NOT EXISTS staging_depositos_natural_key_v2
    ON staging.depositos (fecha, tipo_entidad, banco, COALESCE(provincia, ''), COALESCE(canton, ''),
                          tipo_deposito);
DROP INDEX IF EXISTS staging.staging_depositos_natural_key_unique;
