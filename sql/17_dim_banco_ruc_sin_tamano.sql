-- dim_banco.ruc/.tamano llevaban desde sql/07 permanentemente NULL: refresh_marts()
-- nunca los poblaba, y etl/seeds/banco_maestro.csv tampoco los traía. Investigado
-- 2026-07-23 (el usuario preguntó por qué): son dos casos distintos.
--   - ruc SÍ es obtenible: BCE tsp/tsa trae `ruc` para TODAS las entidades, incluidos los
--     33 bancos privados curados -- resolver_entidad_bce() lo descartaba en ese camino
--     (etl/transform/banco_matching.py, etl/transform/parse_bce_tasas.py). Se activa acá.
--     Nota de calidad conocida: al menos un par de bancos privados reales comparten RUC
--     en el archivo fuente (ej. Atlántida/D-MIRO) -- ver docs/gobernanza_datos.md.
--   - tamano (GRANDE/MEDIANO/PEQUEÑO) NO es obtenible con las fuentes actuales: Superbancos
--     solo expone esa clasificación como columnas de agregado del Boletín (ya excluidas
--     por BOLETIN_AGGREGATE_COLUMNS), nunca como etiqueta por banco individual en ningún
--     campo de CAPCOL/BCE/Boletín. Se descarta la columna en vez de dejarla NULL para
--     siempre o inventar un proxy propio (decisión explícita del usuario: no se va a usar).

ALTER TABLE staging.banco_maestro ADD COLUMN IF NOT EXISTS ruc TEXT;

ALTER TABLE marts.dim_banco DROP COLUMN row_hash;
ALTER TABLE marts.dim_banco DROP CONSTRAINT dim_banco_tamano_check;
ALTER TABLE marts.dim_banco DROP COLUMN tamano;
ALTER TABLE marts.dim_banco
    ADD COLUMN row_hash TEXT GENERATED ALWAYS AS (
        md5(banco || '|' || tipo_entidad || '|' || COALESCE(ruc, ''))
    ) STORED;
