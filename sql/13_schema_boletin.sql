-- Boletín Financiero Mensual (Superbancos) -- BALANCE y PYG, formato ancho (bancos en
-- columnas, plan de cuentas jerárquico en filas). Ver docs/fuentes_datos.md sección 3.
--
-- dim_cuenta_contable: plan de cuentas único compartido por BALANCE y PYG (llave natural
-- (reporte, codigo) porque el mismo código puede significar cosas distintas en cada
-- reporte -- ej. código '4' en BALANCE es un bloque memo de "GASTOS" adicional al activo,
-- en PYG es la cuenta real de gastos). seccion se deriva del primer dígito del código
-- (convención del Catálogo Único de Cuentas: 1 activo, 2 pasivo, 3 patrimonio, 4 gastos,
-- 5 ingresos). grupo_met es nullable y es una conveniencia (la hoja MET no particiona
-- limpio: un mismo código puede aparecer en más de un grupo funcional -- se guarda el
-- primer grupo encontrado, ver src/benchmark_bancos/transform/parse_boletin.py).

CREATE TABLE IF NOT EXISTS marts.dim_cuenta_contable (
    cuenta_id     SERIAL PRIMARY KEY,
    reporte       TEXT NOT NULL CHECK (reporte IN ('BALANCE', 'PYG')),
    codigo        TEXT NOT NULL,
    cuenta        TEXT NOT NULL,
    nivel         INT NOT NULL,
    codigo_padre  TEXT,
    seccion       TEXT,
    grupo_met     TEXT,
    UNIQUE (reporte, codigo)
);

CREATE TABLE IF NOT EXISTS raw.boletin_balance (
    id           BIGSERIAL PRIMARY KEY,
    source_file  TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    anio         INT NOT NULL,
    mes          INT NOT NULL,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    data         JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS raw.boletin_pyg (
    id           BIGSERIAL PRIMARY KEY,
    source_file  TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    anio         INT NOT NULL,
    mes          INT NOT NULL,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    data         JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_boletin_balance_anio_mes ON raw.boletin_balance (anio, mes);
CREATE INDEX IF NOT EXISTS ix_raw_boletin_pyg_anio_mes ON raw.boletin_pyg (anio, mes);

-- staging guarda el valor ya en USD completos (x1000 aplicado en el parser -- la fuente
-- reporta en miles, confirmado en el encabezado real del archivo).
CREATE TABLE IF NOT EXISTS staging.boletin_balance (
    id          BIGSERIAL PRIMARY KEY,
    fecha       DATE NOT NULL,
    banco       TEXT NOT NULL,
    banco_codigo TEXT NOT NULL,
    codigo      TEXT NOT NULL,
    saldo_usd   NUMERIC(18,2) NOT NULL,
    source_file TEXT NOT NULL,
    fecha_carga         TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash    TEXT GENERATED ALWAYS AS (md5(saldo_usd::text)) STORED
);
CREATE UNIQUE INDEX IF NOT EXISTS staging_boletin_balance_unique
    ON staging.boletin_balance (fecha, banco_codigo, codigo);
CREATE INDEX IF NOT EXISTS ix_staging_boletin_balance_fecha ON staging.boletin_balance (fecha);

CREATE TABLE IF NOT EXISTS staging.boletin_pyg (
    id          BIGSERIAL PRIMARY KEY,
    fecha       DATE NOT NULL,
    banco       TEXT NOT NULL,
    banco_codigo TEXT NOT NULL,
    codigo      TEXT NOT NULL,
    valor_usd   NUMERIC(18,2) NOT NULL,
    source_file TEXT NOT NULL,
    fecha_carga         TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash    TEXT GENERATED ALWAYS AS (md5(valor_usd::text)) STORED
);
CREATE UNIQUE INDEX IF NOT EXISTS staging_boletin_pyg_unique
    ON staging.boletin_pyg (fecha, banco_codigo, codigo);
CREATE INDEX IF NOT EXISTS ix_staging_boletin_pyg_fecha ON staging.boletin_pyg (fecha);

CREATE TABLE IF NOT EXISTS marts.fact_balance (
    fact_id    BIGSERIAL PRIMARY KEY,
    fecha_id   INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    banco_id   INT NOT NULL REFERENCES marts.dim_banco (banco_id),
    cuenta_id  INT NOT NULL REFERENCES marts.dim_cuenta_contable (cuenta_id),
    saldo_usd  NUMERIC(18,2) NOT NULL,
    fecha_carga         TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash   TEXT GENERATED ALWAYS AS (md5(saldo_usd::text)) STORED,
    UNIQUE (fecha_id, banco_id, cuenta_id)
);

CREATE TABLE IF NOT EXISTS marts.fact_pyg (
    fact_id    BIGSERIAL PRIMARY KEY,
    fecha_id   INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    banco_id   INT NOT NULL REFERENCES marts.dim_banco (banco_id),
    cuenta_id  INT NOT NULL REFERENCES marts.dim_cuenta_contable (cuenta_id),
    valor_usd  NUMERIC(18,2) NOT NULL,
    fecha_carga         TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash   TEXT GENERATED ALWAYS AS (md5(valor_usd::text)) STORED,
    UNIQUE (fecha_id, banco_id, cuenta_id)
);

ALTER TABLE raw.source_files DROP CONSTRAINT IF EXISTS source_files_report_type_check;
ALTER TABLE raw.source_files ADD CONSTRAINT source_files_report_type_check
    CHECK (report_type IN ('cartera', 'depositos', 'bce_tasas_pasivas', 'bce_tasas_activas',
                            'tasas_referenciales', 'boletin_balance', 'boletin_pyg'));
