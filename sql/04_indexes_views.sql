-- Vistas de apoyo para validar la capa marts antes de conectar Power BI.
-- Power BI recalcula estas mismas métricas vía medidas DAX (ver docs/architecture.md);
-- estas vistas existen para pruebas de sanity con psql, no para consumo directo del reporte.

CREATE OR REPLACE VIEW marts.vw_cartera_market_share AS
SELECT
    f.fecha_id,
    d.fecha,
    b.banco,
    SUM(f.saldo) AS saldo_banco,
    SUM(SUM(f.saldo)) OVER (PARTITION BY f.fecha_id) AS saldo_total_mes,
    ROUND(
        SUM(f.saldo) / NULLIF(SUM(SUM(f.saldo)) OVER (PARTITION BY f.fecha_id), 0) * 100, 4
    ) AS market_share_pct
FROM marts.fact_cartera f
JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
JOIN marts.dim_banco b ON b.banco_id = f.banco_id
GROUP BY f.fecha_id, d.fecha, b.banco;

CREATE OR REPLACE VIEW marts.vw_cartera_hhi AS
SELECT
    fecha_id,
    fecha,
    ROUND(SUM(POWER(market_share_pct, 2)), 2) AS hhi
FROM marts.vw_cartera_market_share
GROUP BY fecha_id, fecha;

CREATE OR REPLACE VIEW marts.vw_depositos_market_share AS
SELECT
    f.fecha_id,
    d.fecha,
    b.banco,
    SUM(f.saldo) AS saldo_banco,
    SUM(SUM(f.saldo)) OVER (PARTITION BY f.fecha_id) AS saldo_total_mes,
    ROUND(
        SUM(f.saldo) / NULLIF(SUM(SUM(f.saldo)) OVER (PARTITION BY f.fecha_id), 0) * 100, 4
    ) AS market_share_pct
FROM marts.fact_depositos f
JOIN marts.dim_fecha d ON d.fecha_id = f.fecha_id
JOIN marts.dim_banco b ON b.banco_id = f.banco_id
GROUP BY f.fecha_id, d.fecha, b.banco;

CREATE OR REPLACE VIEW marts.vw_depositos_hhi AS
SELECT
    fecha_id,
    fecha,
    ROUND(SUM(POWER(market_share_pct, 2)), 2) AS hhi
FROM marts.vw_depositos_market_share
GROUP BY fecha_id, fecha;

-- vw_cartera_tasa_ponderada / vw_depositos_tasa_ponderada NO se definen aquí: la forma
-- que llegó a estar en este archivo (referenciando f.tipo_credito directo en fact_cartera
-- y marts.dim_categoria_deposito) solo es válida DESPUÉS de sql/08/09 -- ambos corren
-- después de este archivo en el orden lexicográfico que usa docker-entrypoint-initdb.d,
-- así que un `docker compose up` desde un volumen limpio fallaba aquí mismo (columna
-- f.tipo_credito inexistente en el fact_cartera de sql/03) y abortaba TODO el resto de
-- migraciones (05-24), dejando la base sin staging.bce_*/boletin_* pese a que el mount
-- del directorio completo (ver docker-compose.yml) ya estaba arreglado -- confirmado
-- reproduciendo un `docker compose up -d` limpio, 2026-08-29. Bug de mecánica de
-- migraciones (nunca de modelo), corregido acá restaurando sql/04 a ser válido contra el
-- esquema que existe cuando corre (regla de gobernanza: nunca editar una migración ya
-- aplicada -- pero estas 2 sentencias, tal como estaban, nunca pudieron ejecutarse con
-- éxito en ningún ambiente inicializado de punto limpio, así que no había ningún estado
-- real que preservar). No hace falta recrearlas en su forma transicional: sql/15 ya las
-- DROPea para siempre pocas migraciones después, documentando que la columna que
-- consumían (saldo_x_tasa) nunca llegó a poblarse desde el ETL -- la vista nunca devolvió
-- filas ni en su forma correcta, así que no se pierde nada quitándolas de acá.
