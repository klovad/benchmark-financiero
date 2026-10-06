-- Ajustes a las vistas de bloques de construcción de sql/18 tras su primera aplicación a
-- la base viva (2026-10-02), ahora que fact_balance también trae SEPS (cooperativas y
-- mutualistas, sql/30) además de los bancos privados del Boletín.
--
-- Validación de sql/18 tal cual, antes de este archivo: las 12 métricas que componen
-- (cartera bruta, cartera improductiva, liquidez, morosidad de los 5 segmentos, utilidad
-- acumulada y anualizada, ROA, ROE) coinciden SIN diferencias contra el motor de
-- referencia scripts/compute_indicadores_excel.py para los 23 bancos privados con datos al
-- corte 2026-03-31. Ese motor está verificado dígito a dígito contra el Excel real (ver
-- docs/indicadores_excel_bcos_coop.md). Este archivo no cambia ningún valor de esos 23
-- bancos en esos 5 segmentos: solo agrega casos que antes quedaban fuera.
--
-- 1. vw_cartera_bruta: COALESCE en 1499. El EEFF de la SEPS no carga saldos en cero, así
--    que una entidad sin provisiones no tiene fila 1499 y `14 - NULL` daba NULL. El motor
--    de referencia ya trataba la cuenta ausente como 0. Hoy no hay ningún caso (todas las
--    entidades tienen 1499), pero es un hueco latente.
-- 2. vw_cartera_bruta_segmento / vw_cartera_improductiva_segmento: se agregan los
--    segmentos VIVIENDA DE INTERÉS PÚBLICO y INVERSIÓN PÚBLICA (mismos nombres que
--    marts.dim_segmento_credito). Antes sus cuentas (1408...1472 y 1474...1490, 9 cada uno)
--    no caían en ningún segmento. Son los segmentos centrales de las mutualistas y del
--    BdE. Patrones verificados: 'VIVIENDA DE INTER' cubre "VIVIENDA DE INTERÉS PÚBLICO"
--    (Superbancos) y "VIVIENDA DE INTERÉS SOCIAL Y PÚBLICO" (SEPS), sin solaparse con
--    INMOBILIARIO.
--
-- Fuera a propósito: COMERCIAL ORDINARIO/PRIORITARIO (segmentación previa a 2021) y las
-- cuentas COVID-19 (14xx refinanciada/reestructurada COVID). Asignarlas cambiaría
-- PRODUCTIVO frente a lo validado contra el Excel; quedan sin segmento, igual que antes,
-- y sí cuentan en vw_cartera_bruta / vw_cartera_improductiva totales.

CREATE OR REPLACE VIEW marts.vw_cartera_bruta AS
SELECT
    f.banco_id,
    f.fecha_id,
    COALESCE(SUM(f.saldo_usd) FILTER (WHERE cc.codigo = '14'), 0)
        - COALESCE(SUM(f.saldo_usd) FILTER (WHERE cc.codigo = '1499'), 0) AS cartera_bruta
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
WHERE cc.reporte = 'BALANCE' AND cc.codigo IN ('14', '1499')
GROUP BY f.banco_id, f.fecha_id;

CREATE OR REPLACE VIEW marts.vw_cartera_improductiva_segmento AS
SELECT
    f.banco_id,
    f.fecha_id,
    seg.segmento,
    SUM(f.saldo_usd) AS cartera_improductiva
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
CROSS JOIN LATERAL (VALUES
    ('PRODUCTIVO', 'PRODUCTIVO'),
    ('CONSUMO', 'CONSUMO'),
    ('INMOBILIARIO', 'INMOBILIARIO'),
    ('MICROCRÉDITO', 'MICROCR'),   -- patrón sin tilde: evita problemas de encoding en el nombre de cuenta fuente
    ('EDUCATIVO', 'EDUCATIVO'),
    ('VIVIENDA DE INTERÉS PÚBLICO', 'VIVIENDA DE INTER'),
    ('INVERSIÓN PÚBLICA', 'INVERSI')
) AS seg(segmento, patron)
WHERE cc.reporte = 'BALANCE'
  AND cc.codigo LIKE '14%' AND cc.nivel = 4 AND cc.codigo <> '1499'
  AND (cc.cuenta ILIKE '%NO DEVENGA%' OR cc.cuenta ILIKE '%VENCIDA%')
  AND cc.cuenta NOT ILIKE '%POR VENCER%'
  AND cc.cuenta ILIKE '%' || seg.patron || '%'
GROUP BY f.banco_id, f.fecha_id, seg.segmento;

CREATE OR REPLACE VIEW marts.vw_cartera_bruta_segmento AS
SELECT
    f.banco_id,
    f.fecha_id,
    seg.segmento,
    SUM(f.saldo_usd) AS cartera_bruta_segmento
FROM marts.fact_balance f
JOIN marts.dim_cuenta_contable cc ON cc.cuenta_id = f.cuenta_id
CROSS JOIN LATERAL (VALUES
    ('PRODUCTIVO', 'PRODUCTIVO'),
    ('CONSUMO', 'CONSUMO'),
    ('INMOBILIARIO', 'INMOBILIARIO'),
    ('MICROCRÉDITO', 'MICROCR'),
    ('EDUCATIVO', 'EDUCATIVO'),
    ('VIVIENDA DE INTERÉS PÚBLICO', 'VIVIENDA DE INTER'),
    ('INVERSIÓN PÚBLICA', 'INVERSI')
) AS seg(segmento, patron)
WHERE cc.reporte = 'BALANCE'
  AND cc.codigo LIKE '14%' AND cc.nivel = 4 AND cc.codigo <> '1499'
  AND cc.cuenta ILIKE '%' || seg.patron || '%'
GROUP BY f.banco_id, f.fecha_id, seg.segmento;
