-- Ejecutar conectado a la base benchmark_cartera_depositos.
-- psql -h localhost -p 5432 -U bp_etl -d benchmark_cartera_depositos -f sql/01_schema_meta.sql
--
-- Schema meta: control de ingesta (no datos de negocio).
--
-- Hasta 2026-10-05 este archivo creaba la capa `raw` (filas parseadas en JSONB). Se
-- eliminó: ningún proceso la leía y duplicaba staging (ver sql/33 y
-- docs/architecture.md, "Carga incremental"). La fuente de verdad son los archivos en
-- data/raw/**; meta.source_files registra cada uno con su sha256.
--
-- Bases ya existentes: sql/33 hace la migración equivalente (mueve raw.source_files a
-- meta y borra las tablas raw). En una base nueva sql/33 no tiene nada que hacer.

CREATE SCHEMA IF NOT EXISTS meta AUTHORIZATION bp_etl;

-- Idempotencia a nivel de archivo: un archivo con el mismo sha256 no se reprocesa.
CREATE TABLE IF NOT EXISTS meta.source_files (
    source_file  TEXT PRIMARY KEY,
    source_hash  TEXT NOT NULL,
    report_type  TEXT NOT NULL CONSTRAINT source_files_report_type_check
                 CHECK (report_type IN ('cartera', 'depositos', 'bce_tasas_pasivas',
                                        'bce_tasas_activas', 'tasas_referenciales',
                                        'boletin_balance', 'boletin_pyg')),
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
