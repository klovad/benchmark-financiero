-- Capa staging: datos tipados y estandarizados a partir de raw.*
-- Nomenclatura y categorías según las fichas metodológicas de Superbancos
-- (colocaciones -> cartera, captaciones -> depositos, renombradas en 2024).

CREATE SCHEMA IF NOT EXISTS staging;  -- dueño: el rol que aplica la migración (sql/00)

CREATE TABLE IF NOT EXISTS staging.cartera (
    id               BIGSERIAL PRIMARY KEY,
    fecha            DATE NOT NULL,                 -- primer día del mes de corte
    tipo_entidad     TEXT NOT NULL,                  -- Banco Privado | Banco Público | Sociedad Financiera
    banco            TEXT NOT NULL,
    region           TEXT,
    provincia        TEXT,
    canton           TEXT,
    tipo_credito     TEXT NOT NULL,                  -- comercial | consumo | inmobiliario | microcredito | vivienda_interes_publico | educativo
    estado_cartera   TEXT NOT NULL,                  -- por_vencer | no_devenga_intereses | vencida
    saldo            NUMERIC(18,2) NOT NULL,
    tasa_ponderada   NUMERIC(9,4),                   -- % anual, si la fuente la reporta
    morosidad        NUMERIC(9,4),                   -- % si la fuente la reporta
    source_file      TEXT NOT NULL,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fecha, tipo_entidad, banco, canton, tipo_credito, estado_cartera)
);

CREATE TABLE IF NOT EXISTS staging.depositos (
    id               BIGSERIAL PRIMARY KEY,
    fecha            DATE NOT NULL,
    tipo_entidad     TEXT NOT NULL,
    banco            TEXT NOT NULL,
    region           TEXT,
    provincia        TEXT,
    canton           TEXT,
    tipo_deposito    TEXT NOT NULL,                  -- monetario_genera_interes | monetario_no_genera_interes | ahorro | cuenta_basica | plazo | por_confirmar | reporto | garantia | restringido
    saldo            NUMERIC(18,2) NOT NULL,
    numero_clientes  BIGINT,
    numero_cuentas   BIGINT,
    tasa_ponderada   NUMERIC(9,4),
    source_file      TEXT NOT NULL,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fecha, tipo_entidad, banco, canton, tipo_deposito)
);

CREATE INDEX IF NOT EXISTS ix_staging_cartera_fecha ON staging.cartera (fecha);
CREATE INDEX IF NOT EXISTS ix_staging_depositos_fecha ON staging.depositos (fecha);
