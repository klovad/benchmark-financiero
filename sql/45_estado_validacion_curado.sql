-- estado_validacion de dim_plazo y dim_cuenta_contable se confirma contra un universo
-- curado, no contra "lo que ya existía al migrar" (2026-11-01).
--
-- sql/25 y sql/27 marcaron CONFIRMADO las filas presentes al aplicarlas. En una base
-- nueva la tabla está vacía al migrar, así que todo lo que cargaba después quedaba
-- AUTO_INGRESADO: la base reconstruida el 2026-10-10 tenía los 21 plazos y las 1.902
-- cuentas sin confirmar, y el campo no distinguía lo revisado de lo nuevo.
--
-- Desde ahora refresh_marts() reafirma el estado en cada corrida, igual que dim_canton
-- con su seed (sql/36):
--   - dim_plazo: rangos de los universos curados de cada fuente (PLAZOS_TSP_VALIDOS,
--     PLAZOS_TSA_VALIDOS y los PLAZOS_VALIDOS de CAPCOL y TasasHistorico), en
--     load_postgres.sincronizar_plazos_curados().
--   - dim_cuenta_contable: seeds/cuenta_contable.csv (plan de cuentas revisado de
--     Superbancos y la SEPS), en load_postgres.sincronizar_cuentas_seed().
-- Lo que no esté en esos universos sigue entrando AUTO_INGRESADO y genera un WARNING.
--
-- Esta migración confirma ya los 21 rangos curados (la misma lista que deriva el código)
-- y documenta la regla en el catálogo; las cuentas se confirman en el próximo refresh.

UPDATE marts.dim_plazo d SET estado_validacion = 'CONFIRMADO'
FROM (VALUES
    (1, 29), (1, 30), (30, 60), (31, 90), (61, 90), (61, 120), (91, 120), (91, 180),
    (121, 180), (181, 360), (360, NULL), (361, 450), (361, NULL), (451, 540),
    (541, 720), (720, 1440), (1440, 2160), (2160, 2880), (2880, 3600), (3600, 4320),
    (4320, NULL)
) AS c (dias_desde, dias_hasta)
WHERE d.dias_desde = c.dias_desde
  AND d.dias_hasta IS NOT DISTINCT FROM c.dias_hasta::int
  AND d.estado_validacion <> 'CONFIRMADO';

COMMENT ON COLUMN marts.dim_plazo.estado_validacion IS 'CONFIRMADO si el rango está en el universo curado de plazos de alguna fuente; AUTO_INGRESADO si es un bucket nuevo pendiente de revisión. Se reafirma en cada refresh.';
COMMENT ON COLUMN marts.dim_cuenta_contable.estado_validacion IS 'CONFIRMADO si la cuenta está en el plan de cuentas revisado (seed cuenta_contable.csv del ETL); AUTO_INGRESADO si apareció por primera vez en un archivo y falta revisarla. Se reafirma en cada refresh.';
