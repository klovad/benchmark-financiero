-- fact_saldo_cartera: estado_cartera era una dimensión degenerada partiendo el saldo en
-- 3 filas por (fecha, banco, cantón, segmento) -- un antipatrón EAV, no una dimensión
-- real (los 3 estados son mutuamente excluyentes y siempre están los 3 juntos: verificado
-- 123.322 combinaciones × 3 filas exactas, ninguna combinación con menos). El proyecto ya
-- resolvía este mismo caso de otra forma en fact_tasas_referenciales_cartera (2 columnas
-- de medida en vez de una columna "tipo_tasa" + "valor") -- se aplica el mismo criterio
-- acá: grano pasa a (fecha, banco, cantón, segmento), saldo_por_vencer/
-- saldo_no_devenga_intereses/saldo_vencida como columnas, saldo_total como columna
-- GENERATED (mismo patrón que row_hash: una sola fuente de verdad, no algo que el ETL
-- tenga que mantener sincronizado). Efecto colateral: morosidad = (saldo_no_devenga_intereses
-- + saldo_vencida) / saldo_total ya no necesita filtrar nada, es una expresión directa.

CREATE TABLE marts.fact_saldo_cartera_new (
    fact_saldo_cartera_id      BIGSERIAL PRIMARY KEY,
    fecha_id                   INT NOT NULL REFERENCES marts.dim_fecha (fecha_id),
    banco_id                   INT NOT NULL REFERENCES marts.dim_banco (banco_id),
    canton_id                  INT REFERENCES marts.dim_canton (canton_id),
    segmento_id                INT NOT NULL REFERENCES marts.dim_segmento_credito (segmento_id),
    saldo_por_vencer           NUMERIC(18,2) NOT NULL DEFAULT 0,
    saldo_no_devenga_intereses NUMERIC(18,2) NOT NULL DEFAULT 0,
    saldo_vencida               NUMERIC(18,2) NOT NULL DEFAULT 0,
    saldo_total                NUMERIC(19,2) GENERATED ALWAYS AS
                                    (saldo_por_vencer + saldo_no_devenga_intereses + saldo_vencida) STORED,
    fecha_carga                TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion        TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_hash                   TEXT GENERATED ALWAYS AS (
                                    md5(saldo_por_vencer::text || '|' || saldo_no_devenga_intereses::text || '|' || saldo_vencida::text)
                                ) STORED
);

INSERT INTO marts.fact_saldo_cartera_new
    (fecha_id, banco_id, canton_id, segmento_id, saldo_por_vencer, saldo_no_devenga_intereses, saldo_vencida, fecha_carga, fecha_actualizacion)
SELECT
    fecha_id, banco_id, canton_id, segmento_id,
    COALESCE(SUM(saldo) FILTER (WHERE estado_cartera = 'por_vencer'), 0),
    COALESCE(SUM(saldo) FILTER (WHERE estado_cartera = 'no_devenga_intereses'), 0),
    COALESCE(SUM(saldo) FILTER (WHERE estado_cartera = 'vencida'), 0),
    MIN(fecha_carga),
    MAX(fecha_actualizacion)
FROM marts.fact_saldo_cartera
GROUP BY fecha_id, banco_id, canton_id, segmento_id;

CREATE UNIQUE INDEX fact_saldo_cartera_new_unique
    ON marts.fact_saldo_cartera_new (fecha_id, banco_id, COALESCE(canton_id, -1), segmento_id);

-- vw_cartera_market_share/vw_cartera_hhi (sql/15) dependen de fact_saldo_cartera.saldo,
-- que ya no existe -- se recrean sobre saldo_total tras el swap de tabla.
DROP VIEW IF EXISTS marts.vw_cartera_hhi;
DROP VIEW IF EXISTS marts.vw_cartera_market_share;

DROP TABLE marts.fact_saldo_cartera;
ALTER TABLE marts.fact_saldo_cartera_new RENAME TO fact_saldo_cartera;
ALTER INDEX marts.fact_saldo_cartera_new_unique RENAME TO fact_saldo_cartera_unique;
ALTER TABLE marts.fact_saldo_cartera RENAME CONSTRAINT fact_saldo_cartera_new_pkey TO fact_saldo_cartera_pkey;
ALTER TABLE marts.fact_saldo_cartera RENAME CONSTRAINT fact_saldo_cartera_new_fecha_id_fkey TO fact_saldo_cartera_fecha_id_fkey;
ALTER TABLE marts.fact_saldo_cartera RENAME CONSTRAINT fact_saldo_cartera_new_banco_id_fkey TO fact_saldo_cartera_banco_id_fkey;
ALTER TABLE marts.fact_saldo_cartera RENAME CONSTRAINT fact_saldo_cartera_new_canton_id_fkey TO fact_saldo_cartera_canton_id_fkey;
ALTER TABLE marts.fact_saldo_cartera RENAME CONSTRAINT fact_saldo_cartera_new_segmento_id_fkey TO fact_saldo_cartera_segmento_id_fkey;

CREATE VIEW marts.vw_cartera_market_share AS
SELECT
    f.fecha_id,
    d.fecha,
    b.banco,
    SUM(f.saldo_total) AS saldo_banco,
    SUM(SUM(f.saldo_total)) OVER (PARTITION BY f.fecha_id) AS saldo_total_mes,
    ROUND(
        SUM(f.saldo_total) / NULLIF(SUM(SUM(f.saldo_total)) OVER (PARTITION BY f.fecha_id), 0) * 100, 4
    ) AS market_share_pct
FROM marts.fact_saldo_cartera f
JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
JOIN marts.dim_banco b ON b.banco_id = f.banco_id
GROUP BY f.fecha_id, d.fecha, b.banco;

CREATE VIEW marts.vw_cartera_hhi AS
SELECT
    fecha_id,
    fecha,
    ROUND(SUM(POWER(market_share_pct, 2)), 2) AS hhi
FROM marts.vw_cartera_market_share
GROUP BY fecha_id, fecha;
