-- BCE: tasas de interés semanales por banco (tsp=pasivas/depósitos, tsa=activas/crédito).
-- Ver docs/fuentes_datos.md sección 2 y el plan aprobado. Reutiliza dim_banco/dim_fecha/
-- dim_categoria_deposito/dim_plazo/dim_segmento_credito ya existentes -- no se crea
-- ninguna dimensión nueva, solo hechos.
--
-- Grano de fact_tasas_pasivas/activas: (fecha, banco, categoria/segmento, plazo,
-- provincia) -- SIN cantón. El archivo fuente trae cantón como grano más fino dentro de
-- cada provincia; se reagrega en el parser (src/benchmark_bancos/transform/parse_bce_tasas.py): montos y
-- operaciones se suman, las tasas se promedian ponderadas por monto (no promedio simple).

ALTER TABLE raw.source_files DROP CONSTRAINT IF EXISTS source_files_report_type_check;
ALTER TABLE raw.source_files ADD CONSTRAINT source_files_report_type_check
    CHECK (report_type IN ('cartera', 'depositos', 'bce_tasas_pasivas', 'bce_tasas_activas'));

CREATE TABLE IF NOT EXISTS raw.bce_tasas_pasivas (
    id           BIGSERIAL PRIMARY KEY,
    source_file  TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    anio         INT NOT NULL,
    mes          INT,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    data         JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.bce_tasas_activas (
    id           BIGSERIAL PRIMARY KEY,
    source_file  TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    anio         INT NOT NULL,
    mes          INT,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    data         JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_raw_bce_tasas_pasivas_anio_mes ON raw.bce_tasas_pasivas (anio, mes);
CREATE INDEX IF NOT EXISTS ix_raw_bce_tasas_activas_anio_mes ON raw.bce_tasas_activas (anio, mes);

CREATE TABLE IF NOT EXISTS staging.bce_tasas_pasivas (
    id                    BIGSERIAL PRIMARY KEY,
    fecha                 DATE NOT NULL,
    banco_codigo          TEXT NOT NULL,
    categoria_deposito    TEXT NOT NULL,
    plazo_dias_desde      INT NOT NULL,
    plazo_dias_hasta      INT,
    plazo_codigo          TEXT,
    provincia             TEXT,
    monto_total           NUMERIC(18,2),
    numero_operaciones    BIGINT,
    tasa_pasiva_efectiva  NUMERIC(9,4),
    tasa_nominal          NUMERIC(9,4),
    source_file           TEXT NOT NULL,
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash              TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_pasiva_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, ''))
    ) STORED
);
CREATE UNIQUE INDEX IF NOT EXISTS staging_bce_tasas_pasivas_unique
    ON staging.bce_tasas_pasivas (fecha, banco_codigo, categoria_deposito, plazo_dias_desde,
                                   COALESCE(plazo_dias_hasta, -1), COALESCE(provincia, ''));
CREATE INDEX IF NOT EXISTS ix_staging_bce_tasas_pasivas_fecha ON staging.bce_tasas_pasivas (fecha);

CREATE TABLE IF NOT EXISTS staging.bce_tasas_activas (
    id                    BIGSERIAL PRIMARY KEY,
    fecha                 DATE NOT NULL,
    banco_codigo          TEXT NOT NULL,
    segmento_credito      TEXT NOT NULL,
    plazo_dias_desde      INT NOT NULL,
    plazo_dias_hasta      INT,
    plazo_codigo          TEXT,
    provincia             TEXT,
    monto_total           NUMERIC(18,2),
    numero_operaciones    BIGINT,
    tasa_activa_efectiva  NUMERIC(9,4),
    tasa_nominal          NUMERIC(9,4),
    source_file           TEXT NOT NULL,
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash              TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_activa_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, ''))
    ) STORED
);
CREATE UNIQUE INDEX IF NOT EXISTS staging_bce_tasas_activas_unique
    ON staging.bce_tasas_activas (fecha, banco_codigo, segmento_credito, plazo_dias_desde,
                                   COALESCE(plazo_dias_hasta, -1), COALESCE(provincia, ''));
CREATE INDEX IF NOT EXISTS ix_staging_bce_tasas_activas_fecha ON staging.bce_tasas_activas (fecha);

CREATE TABLE IF NOT EXISTS marts.fact_tasas_pasivas (
    fact_id               BIGSERIAL PRIMARY KEY,
    fecha_id              INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    banco_id              INT NOT NULL REFERENCES marts.dim_banco (banco_id),
    categoria_deposito_id INT NOT NULL REFERENCES marts.dim_categoria_deposito (categoria_deposito_id),
    plazo_id              INT NOT NULL REFERENCES marts.dim_plazo (plazo_id),
    provincia             TEXT,
    monto_total           NUMERIC(18,2),
    numero_operaciones    BIGINT,
    tasa_pasiva_efectiva  NUMERIC(9,4),
    tasa_nominal          NUMERIC(9,4),
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash              TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_pasiva_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, ''))
    ) STORED
);
-- provincia nullable en la llave: índice NULL-safe con COALESCE desde el inicio (mismo
-- bug que se corrigió en dim_plazo/fact_depositos -- ver sql/10_fix_null_unique_constraints.sql).
CREATE UNIQUE INDEX IF NOT EXISTS fact_tasas_pasivas_unique
    ON marts.fact_tasas_pasivas (fecha_id, banco_id, categoria_deposito_id, plazo_id, COALESCE(provincia, ''));

CREATE TABLE IF NOT EXISTS marts.fact_tasas_activas (
    fact_id               BIGSERIAL PRIMARY KEY,
    fecha_id              INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    banco_id              INT NOT NULL REFERENCES marts.dim_banco (banco_id),
    segmento_id           INT NOT NULL REFERENCES marts.dim_segmento_credito (segmento_id),
    plazo_id              INT NOT NULL REFERENCES marts.dim_plazo (plazo_id),
    provincia             TEXT,
    monto_total           NUMERIC(18,2),
    numero_operaciones    BIGINT,
    tasa_activa_efectiva  NUMERIC(9,4),
    tasa_nominal          NUMERIC(9,4),
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash              TEXT GENERATED ALWAYS AS (
        md5(COALESCE(monto_total::text, '') || '|' || COALESCE(numero_operaciones::text, '') || '|' ||
            COALESCE(tasa_activa_efectiva::text, '') || '|' || COALESCE(tasa_nominal::text, ''))
    ) STORED
);
CREATE UNIQUE INDEX IF NOT EXISTS fact_tasas_activas_unique
    ON marts.fact_tasas_activas (fecha_id, banco_id, segmento_id, plazo_id, COALESCE(provincia, ''));
