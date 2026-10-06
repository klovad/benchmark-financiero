-- Agrega las columnas nuevas a dim_banco, trunca dim_banco/dim_fecha/fact_cartera/
-- fact_depositos (marts.* es reconstruible desde staging.* por diseño), y deja las
-- restricciones finales listas para que refresh_marts() repueble todo desde staging
-- (ya con banco_codigo resuelto) usando la nueva lógica.
--
-- Truncar en vez de migrar los IDs en sitio es deliberado: es la forma más simple y
-- segura de aplicar el fix del bug de continuidad de banco (Comercial de Manabí /
-- Amibank) sin un UPDATE manual de FKs, y de paso resuelve el cambio de formato de
-- fecha_id (YYYYMM -> YYYYMMDD) sin fricción.

ALTER TABLE marts.dim_banco
    ADD COLUMN IF NOT EXISTS banco_codigo TEXT,
    ADD COLUMN IF NOT EXISTS tipo_entidad TEXT,
    ADD COLUMN IF NOT EXISTS tamano TEXT,
    ADD COLUMN IF NOT EXISTS ruc TEXT,
    ADD COLUMN IF NOT EXISTS fecha_carga TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now();

TRUNCATE TABLE marts.fact_cartera, marts.fact_depositos, marts.dim_banco, marts.dim_fecha;

ALTER TABLE marts.dim_banco
    ALTER COLUMN banco_codigo SET NOT NULL,
    ALTER COLUMN tipo_entidad SET NOT NULL,
    ADD CONSTRAINT dim_banco_tipo_entidad_check CHECK (tipo_entidad IN
        ('BANCO PRIVADO', 'BANCO PUBLICO', 'COOPERATIVA', 'MUTUALISTA',
         'SOCIEDAD FINANCIERA', 'TARJETAS DE CREDITO')),
    ADD CONSTRAINT dim_banco_tamano_check CHECK (tamano IN ('GRANDE', 'MEDIANO', 'PEQUEÑO')),
    ADD CONSTRAINT dim_banco_codigo_unique UNIQUE (banco_codigo);

ALTER TABLE marts.dim_banco
    ADD COLUMN IF NOT EXISTS row_hash TEXT GENERATED ALWAYS AS (
        md5(banco || '|' || tipo_entidad || '|' || COALESCE(tamano, '') || '|' || COALESCE(ruc, ''))
    ) STORED;

ALTER TABLE marts.dim_fecha
    ALTER COLUMN dia SET NOT NULL,
    ALTER COLUMN anio_mes SET NOT NULL;

-- Tabla de referencia (sembrada desde src/benchmark_bancos/seeds/banco_maestro.csv por
-- src/benchmark_bancos/load/load_postgres.py::load_banco_maestro_seed()) con el nombre canónico a
-- mostrar y tipo_entidad de cada banco_codigo -- deterministas, no derivados
-- oportunísticamente de cualquier texto crudo que haya llegado primero durante la carga.
CREATE TABLE IF NOT EXISTS staging.banco_maestro (
    banco_codigo TEXT PRIMARY KEY,
    banco        TEXT NOT NULL,
    tipo_entidad TEXT NOT NULL
);
