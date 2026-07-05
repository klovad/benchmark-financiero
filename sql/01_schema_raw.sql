-- Ejecutar conectado a la base benchmark_cartera_depositos.
-- psql -h localhost -p 5432 -U bp_etl -d benchmark_cartera_depositos -f sql/01_schema_raw.sql
--
-- Capa raw: preserva cada fila del Excel origen tal cual, sin tipar ni normalizar.
-- Se usa JSONB en vez de columnas fijas porque el layout de columnas de la fuente
-- (Superbancos) ha cambiado entre años (ej. renombre colocaciones/captaciones -> cartera/depositos
-- en 2024) y la capa raw no debe romperse ni perder datos ante ese drift.

CREATE SCHEMA IF NOT EXISTS raw AUTHORIZATION bp_etl;

CREATE TABLE IF NOT EXISTS raw.cartera (
    id           BIGSERIAL PRIMARY KEY,
    source_file  TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    sheet_name   TEXT,
    row_number   INT,
    anio         INT NOT NULL,
    mes          INT,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    data         JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.depositos (
    id           BIGSERIAL PRIMARY KEY,
    source_file  TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    sheet_name   TEXT,
    row_number   INT,
    anio         INT NOT NULL,
    mes          INT,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    data         JSONB NOT NULL
);

-- Evita recargar el mismo archivo fuente dos veces (idempotencia a nivel de archivo).
CREATE TABLE IF NOT EXISTS raw.source_files (
    source_file  TEXT PRIMARY KEY,
    source_hash  TEXT NOT NULL,
    report_type  TEXT NOT NULL CHECK (report_type IN ('cartera', 'depositos')),
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_raw_cartera_anio_mes ON raw.cartera (anio, mes);
CREATE INDEX IF NOT EXISTS ix_raw_depositos_anio_mes ON raw.depositos (anio, mes);
CREATE INDEX IF NOT EXISTS ix_raw_cartera_data_gin ON raw.cartera USING GIN (data);
CREATE INDEX IF NOT EXISTS ix_raw_depositos_data_gin ON raw.depositos USING GIN (data);
