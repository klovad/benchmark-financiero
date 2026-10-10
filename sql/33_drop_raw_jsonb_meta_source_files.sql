-- Elimina las tablas JSONB de la capa `raw` y mueve el registro de ingesta a `meta`.
--
-- Evaluación (2026-10-05, base nativa viva):
-- - `raw` ocupaba 12,1 GB de una base de 22 GB (55%), con 20 M de filas. Las fuentes en
--   disco (data/raw/**, los ZIP/HTML descargados) suman 2,2 GB.
-- - Ningún código, test ni modelo de Power BI hacía SELECT sobre raw.cartera/depositos/
--   bce_tasas_*/tasas_referenciales/boletin_*: eran tablas de solo escritura. Incluso el
--   reproceso de grano de BCE (sql/28) relee el archivo en disco, no raw.
-- - No guardaban el dato original: guardaban la fila YA parseada (agregada por llave
--   natural en CAPCOL, pivotada en el Boletín, con catálogos resueltos) -- ver
--   docs/linaje_datos.md, "Principio: raw.* no es un espejo bit-a-bit". Es decir,
--   duplicaban staging en JSONB, ~1,5x más pesado.
--
-- La trazabilidad no se pierde: la fuente de verdad son los archivos en data/raw/**
-- (conservados, re-descargables) y meta.source_files registra cada archivo cargado con
-- su sha256 (gate de idempotencia: un archivo con el mismo hash no se reprocesa). Todo
-- staging/marts se puede reconstruir reprocesando esos archivos.
--
-- meta.source_files conserva sus columnas, PK y CHECK tal cual (ALTER ... SET SCHEMA
-- mueve también constraints e índices).

CREATE SCHEMA IF NOT EXISTS meta;  -- dueño: el rol que aplica la migración (sql/00)

ALTER TABLE IF EXISTS raw.source_files SET SCHEMA meta;

DROP TABLE IF EXISTS
    raw.cartera,
    raw.depositos,
    raw.bce_tasas_pasivas,
    raw.bce_tasas_activas,
    raw.tasas_referenciales,
    raw.boletin_balance,
    raw.boletin_pyg;

-- Sin CASCADE: si quedara algún objeto inesperado en raw, la migración falla en vez de
-- borrarlo en silencio.
DROP SCHEMA IF EXISTS raw;
