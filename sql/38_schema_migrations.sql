-- Registro de migraciones aplicadas (2026-10-09).
--
-- `benchmark-bancos migrate` (src/benchmark_bancos/migrate.py) crea esta tabla si no
-- existe y anota cada sql/NN_*.sql que aplica, con su sha256. Este archivo la crea
-- también para las bases que se arman aplicando todo sql/ con psql (docker-compose, CI):
-- en ese caso el registro queda vacío y hay que correr una vez
-- `benchmark-bancos migrate --baseline` para marcar como aplicados los archivos actuales.
-- Mismo DDL que migrate.py::_DDL_REGISTRO.

CREATE TABLE IF NOT EXISTS meta.schema_migrations (
    archivo     text PRIMARY KEY,
    sha256      text NOT NULL,
    aplicada_en timestamptz NOT NULL DEFAULT now(),
    modo        text NOT NULL DEFAULT 'aplicada'
                CHECK (modo IN ('aplicada', 'baseline'))
);
