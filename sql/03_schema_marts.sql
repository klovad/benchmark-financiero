-- Capa marts: esquema estrella listo para consumo en Power BI.
-- Alcance: bancos privados del Ecuador (staging.*.tipo_entidad = 'Banco Privado').

CREATE SCHEMA IF NOT EXISTS marts;  -- dueño: el rol que aplica la migración (sql/00)

CREATE TABLE IF NOT EXISTS marts.dim_fecha (
    fecha_id     INT PRIMARY KEY,          -- YYYYMM
    fecha        DATE NOT NULL UNIQUE,
    anio         INT NOT NULL,
    mes          INT NOT NULL,
    trimestre    INT NOT NULL,
    nombre_mes   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marts.dim_banco (
    banco_id     SERIAL PRIMARY KEY,
    banco        TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS marts.dim_canton (
    canton_id    SERIAL PRIMARY KEY,
    canton       TEXT NOT NULL,
    provincia    TEXT,
    region       TEXT,
    UNIQUE (canton, provincia)
);

CREATE TABLE IF NOT EXISTS marts.dim_producto_cartera (
    producto_cartera_id  SERIAL PRIMARY KEY,
    tipo_credito         TEXT NOT NULL,
    estado_cartera       TEXT NOT NULL,
    UNIQUE (tipo_credito, estado_cartera)
);

CREATE TABLE IF NOT EXISTS marts.dim_producto_deposito (
    producto_deposito_id SERIAL PRIMARY KEY,
    tipo_deposito         TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS marts.fact_cartera (
    fact_cartera_id      BIGSERIAL PRIMARY KEY,
    fecha_id             INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    banco_id             INT NOT NULL REFERENCES marts.dim_banco (banco_id),
    canton_id            INT REFERENCES marts.dim_canton (canton_id),
    producto_cartera_id  INT NOT NULL REFERENCES marts.dim_producto_cartera (producto_cartera_id),
    saldo                NUMERIC(18,2) NOT NULL,
    saldo_x_tasa         NUMERIC(22,4),     -- saldo * tasa_ponderada; numerador para reagregar tasas ponderadas correctamente
    tasa_ponderada        NUMERIC(9,4),
    morosidad            NUMERIC(9,4),
    UNIQUE (fecha_id, banco_id, canton_id, producto_cartera_id)
);

CREATE TABLE IF NOT EXISTS marts.fact_depositos (
    fact_depositos_id     BIGSERIAL PRIMARY KEY,
    fecha_id              INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    banco_id              INT NOT NULL REFERENCES marts.dim_banco (banco_id),
    canton_id             INT REFERENCES marts.dim_canton (canton_id),
    producto_deposito_id  INT NOT NULL REFERENCES marts.dim_producto_deposito (producto_deposito_id),
    saldo                 NUMERIC(18,2) NOT NULL,
    saldo_x_tasa          NUMERIC(22,4),
    tasa_ponderada         NUMERIC(9,4),
    numero_clientes       BIGINT,
    numero_cuentas        BIGINT,
    UNIQUE (fecha_id, banco_id, canton_id, producto_deposito_id)
);

CREATE INDEX IF NOT EXISTS ix_fact_cartera_fecha ON marts.fact_cartera (fecha_id);
CREATE INDEX IF NOT EXISTS ix_fact_cartera_banco ON marts.fact_cartera (banco_id);
CREATE INDEX IF NOT EXISTS ix_fact_depositos_fecha ON marts.fact_depositos (fecha_id);
CREATE INDEX IF NOT EXISTS ix_fact_depositos_banco ON marts.fact_depositos (banco_id);
