-- marts.dim_banco / staging.banco_maestro: distingue identidad CURADA (33 bancos
-- privados, banco_crosswalk.csv + banco_maestro.csv, revision humana) de identidad
-- AUTO-REGISTRADA (409 entidades no-privadas de BCE -- cooperativas, bancos publicos,
-- mutualistas, sociedad financiera, tarjetas de credito -- via
-- resolver_entidad_bce()/upsert_banco_maestro_ruc(), sin curacion, ver
-- docs/gobernanza_datos.md "Identidad auto-registrada por RUC (~420 entidades
-- no-privadas) no esta curada"). Ese hueco de gobernanza ya estaba documentado en texto;
-- esta migracion lo hace consultable en el propio dato.
--
-- Se agrega en las 2 tablas, mismo patron que `ruc` (sql/17_dim_banco_ruc_sin_tamano.sql):
-- staging.banco_maestro es donde load_banco_maestro_seed()/upsert_banco_maestro_ruc()
-- (etl/load/load_postgres.py) fijan el valor real segun que funcion crea/toca la fila;
-- marts.dim_banco lo hereda vía el INSERT...SELECT de _REFRESH_MARTS_SQL, igual que
-- banco/tipo_entidad/ruc.
--
-- El discriminador CONFIRMADO/AUTO_INGRESADO para el backfill retroactivo es
-- banco_codigo: los 409 auto-registrados SIEMPRE tienen el prefijo literal `BCE_`
-- (banco_codigo = "BCE_" + ruc, ver resolver_entidad_bce() en
-- etl/transform/banco_matching.py) y los 33 curados NUNCA lo tienen (vienen de
-- banco_crosswalk.csv, codigos como PICHINCHA/GUAYAQUIL/DINERS...) -- verificado contra
-- la base viva antes de escribir este backfill: 409 filas con banco_codigo LIKE 'BCE_%'
-- y 33 sin ese prefijo, exactos 442 en ambas tablas, sin solapamiento ni resto.

ALTER TABLE staging.banco_maestro
    ADD COLUMN estado_validacion TEXT NOT NULL DEFAULT 'AUTO_INGRESADO'
    CHECK (estado_validacion IN ('CONFIRMADO', 'AUTO_INGRESADO', 'RECHAZADO'));

UPDATE staging.banco_maestro SET estado_validacion = 'AUTO_INGRESADO';
UPDATE staging.banco_maestro SET estado_validacion = 'CONFIRMADO'
    WHERE left(banco_codigo, 4) <> 'BCE_';

ALTER TABLE marts.dim_banco
    ADD COLUMN estado_validacion TEXT NOT NULL DEFAULT 'AUTO_INGRESADO'
    CHECK (estado_validacion IN ('CONFIRMADO', 'AUTO_INGRESADO', 'RECHAZADO'));

UPDATE marts.dim_banco SET estado_validacion = 'AUTO_INGRESADO';
UPDATE marts.dim_banco SET estado_validacion = 'CONFIRMADO'
    WHERE left(banco_codigo, 4) <> 'BCE_';

-- row_hash de marts.dim_banco (sql/17) se extiende para cubrir la columna nueva -- mismo
-- patron de todas las migraciones anteriores que tocaron este row_hash (sql/17, sql/19):
-- DROP + re-crear con la expresion GENERATED completa, Postgres no permite ALTER de una
-- columna GENERATED existente.
ALTER TABLE marts.dim_banco DROP COLUMN row_hash;
ALTER TABLE marts.dim_banco
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(banco || '|' || tipo_entidad || '|' || COALESCE(ruc, '') || '|' ||
            COALESCE(segmento_entidad_id::text, '') || '|' || estado_validacion)
    ) STORED;
