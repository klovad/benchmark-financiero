-- TasasHistorico.htm del BCE: techos regulatorios y tasas referenciales, grano mensual
-- a nivel de sistema financiero (no por banco) -- ver docs/fuentes_datos.md sección 2.3.
-- Reinspección contra la página real (TasasVigentes062026.htm) corrigió el conteo inicial
-- de la investigación: 13 segmentos (no 16), 5 categorías de depósito en sección de
-- instrumento (no 3), 6 buckets de plazo (no 3), y 4 métricas de sistema (no 2: además de
-- TPR/TAR trae Tasa Legal y Tasa Máxima Convencional).
--
-- staging.tasas_referenciales es una única tabla "larga" (una fila por métrica) que
-- cubre las 5 secciones de la página -- decisión explícita del plan aprobado, ya que las
-- secciones tienen grano distinto (segmento | categoria_deposito | plazo | sistema) y no
-- vale la pena forzarlas a un único ancho. marts sí queda en 4 tablas anchas normales,
-- una por sección real (las secciones 1+2 de la página comparten grano segmento y van a
-- la misma tabla marts.fact_tasas_referenciales_credito).

-- "Depósitos monetarios" en esta fuente es un agregado que NO distingue
-- generan/no-generan intereses (a diferencia de CAPCOL) -- valor nuevo y genuino, no se
-- fuerza a ninguno de los 2 existentes.
INSERT INTO marts.dim_categoria_deposito (categoria) VALUES ('DEPÓSITOS MONETARIOS')
ON CONFLICT (categoria) DO NOTHING;

ALTER TABLE raw.source_files DROP CONSTRAINT IF EXISTS source_files_report_type_check;
ALTER TABLE raw.source_files ADD CONSTRAINT source_files_report_type_check
    CHECK (report_type IN ('cartera', 'depositos', 'bce_tasas_pasivas', 'bce_tasas_activas', 'tasas_referenciales'));

CREATE TABLE IF NOT EXISTS raw.tasas_referenciales (
    id           BIGSERIAL PRIMARY KEY,
    source_file  TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    anio         INT NOT NULL,
    mes          INT NOT NULL,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    data         JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_tasas_referenciales_anio_mes ON raw.tasas_referenciales (anio, mes);

CREATE TABLE IF NOT EXISTS staging.tasas_referenciales (
    id                BIGSERIAL PRIMARY KEY,
    fecha             DATE NOT NULL,
    seccion           TEXT NOT NULL CHECK (seccion IN
                        ('activa_maxima', 'activa_referencial', 'pasiva_instrumento', 'pasiva_plazo', 'sistema')),
    dimension_valor   TEXT,     -- segmento_credito (activa_*) o categoria_deposito (pasiva_instrumento); NULL en pasiva_plazo/sistema
    plazo_dias_desde  INT,
    plazo_dias_hasta  INT,
    metrica           TEXT NOT NULL,   -- nombre de la métrica (ver etl/transform/parse_tasas_historicas.py)
    valor             NUMERIC(9,4) NOT NULL,
    source_file       TEXT NOT NULL,
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash          TEXT GENERATED ALWAYS AS (md5(valor::text)) STORED
);
CREATE UNIQUE INDEX IF NOT EXISTS staging_tasas_referenciales_unique
    ON staging.tasas_referenciales (fecha, seccion, COALESCE(dimension_valor, ''),
                                     COALESCE(plazo_dias_desde, -1), COALESCE(plazo_dias_hasta, -1), metrica);
CREATE INDEX IF NOT EXISTS ix_staging_tasas_referenciales_fecha ON staging.tasas_referenciales (fecha);

CREATE TABLE IF NOT EXISTS marts.fact_tasas_referenciales_credito (
    fecha_id                 INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    segmento_id              INT NOT NULL REFERENCES marts.dim_segmento_credito (segmento_id),
    tasa_activa_maxima       NUMERIC(9,4),
    tasa_activa_referencial  NUMERIC(9,4),
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash TEXT GENERATED ALWAYS AS (
        md5(COALESCE(tasa_activa_maxima::text, '') || '|' || COALESCE(tasa_activa_referencial::text, ''))
    ) STORED,
    PRIMARY KEY (fecha_id, segmento_id)
);

CREATE TABLE IF NOT EXISTS marts.fact_tasas_pasivas_instrumento (
    fecha_id              INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    categoria_deposito_id INT NOT NULL REFERENCES marts.dim_categoria_deposito (categoria_deposito_id),
    tasa_pasiva_promedio  NUMERIC(9,4),
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash TEXT GENERATED ALWAYS AS (md5(COALESCE(tasa_pasiva_promedio::text, ''))) STORED,
    PRIMARY KEY (fecha_id, categoria_deposito_id)
);

CREATE TABLE IF NOT EXISTS marts.fact_tasas_pasivas_plazo (
    fecha_id                 INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    plazo_id                 INT NOT NULL REFERENCES marts.dim_plazo (plazo_id),
    tasa_pasiva_referencial  NUMERIC(9,4),
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash TEXT GENERATED ALWAYS AS (md5(COALESCE(tasa_pasiva_referencial::text, ''))) STORED,
    PRIMARY KEY (fecha_id, plazo_id)
);

-- 4 métricas reales encontradas en "OTRAS TASAS REFERENCIALES" (la investigación inicial
-- solo había confirmado TPR/TAR; la página real trae también Tasa Legal y Tasa Máxima
-- Convencional -- se guardan las 4, no se descartan 2 por no haber sido anticipadas).
CREATE TABLE IF NOT EXISTS marts.fact_tasas_referenciales_sistema (
    fecha_id                          INT PRIMARY KEY REFERENCES marts.dim_fecha (fecha_id),
    tasa_pasiva_referencial_sistema   NUMERIC(9,4),
    tasa_activa_referencial_sistema   NUMERIC(9,4),
    tasa_legal                        NUMERIC(9,4),
    tasa_maxima_convencional          NUMERIC(9,4),
    fecha_carga           TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash TEXT GENERATED ALWAYS AS (
        md5(COALESCE(tasa_pasiva_referencial_sistema::text, '') || '|' || COALESCE(tasa_activa_referencial_sistema::text, '') || '|' ||
            COALESCE(tasa_legal::text, '') || '|' || COALESCE(tasa_maxima_convencional::text, ''))
    ) STORED
);
