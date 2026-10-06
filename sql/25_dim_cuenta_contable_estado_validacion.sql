-- dim_cuenta_contable no tenia forma de distinguir una cuenta ya vista/estable de un
-- codigo nuevo que aparece por primera vez en un archivo del Boletin: upsert_dim_cuenta_
-- contable() (src/benchmark_bancos/load/load_postgres.py) descubre e inserta cuentas nuevas via
-- ON CONFLICT DO UPDATE sin ninguna curacion humana -- ver principio de gobernanza
-- "identidad curada, nunca autogenerada" en docs/gobernanza_datos.md, que hasta ahora
-- dim_cuenta_contable no cumplia de forma visible (no fallaba, pero tampoco marcaba que
-- una fila nueva no habia sido revisada).
--
-- Nota de portabilidad: dim_cuenta_contable NO tiene fecha_carga/fecha_actualizacion/
-- row_hash (a diferencia de casi todo staging/marts) -- no participa del patron CDC de
-- este proyecto porque no es una tabla de hechos con carga incremental por row_hash,
-- es un catalogo descubierto que se resiembra en cada archivo (mismo criterio que
-- staging.banco_maestro). Verificado contra el esquema vivo antes de escribir esta
-- migracion: no hay row_hash que extender aqui.

ALTER TABLE marts.dim_cuenta_contable
    ADD COLUMN estado_validacion TEXT NOT NULL DEFAULT 'AUTO_INGRESADO'
    CHECK (estado_validacion IN ('CONFIRMADO', 'AUTO_INGRESADO', 'RECHAZADO'));

-- Backfill explicito (no se confia en el DEFAULT de la columna para las filas
-- preexistentes): toda cuenta que ya vivia en la tabla antes de esta migracion ha
-- sobrevivido multiples cargas del Boletin sin incidentes -- se marca CONFIRMADO. El
-- DEFAULT de arriba solo aplica de aqui en adelante, a cuentas nuevas insertadas por
-- upsert_dim_cuenta_contable() (que no lista estado_validacion en su INSERT, asi que
-- hereda AUTO_INGRESADO sin necesitar cambio de codigo).
UPDATE marts.dim_cuenta_contable SET estado_validacion = 'CONFIRMADO';
