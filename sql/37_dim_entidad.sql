-- marts.dim_banco -> marts.dim_entidad (2026-10-09).
--
-- La dimensión ya no es de bancos: de sus 444 filas, 39 son bancos (33 privados y 6
-- públicos); el resto son 384 cooperativas, 12 sociedades financieras, 5 mutualistas,
-- 2 entidades de segundo piso y 2 emisoras de tarjetas. Se renombra el contrato de
-- consumo (solo el schema marts, decisión 2026-10-09):
--
--   marts.dim_banco                       -> marts.dim_entidad
--     banco_id / banco / banco_codigo     -> entidad_id / entidad / entidad_codigo
--   marts.fact_*.banco_id                 -> entidad_id (las FK siguen apuntando bien)
--   vistas: columnas banco_id / banco / banco_codigo / saldo_banco
--                                         -> entidad_id / entidad / entidad_codigo / saldo_entidad
--   marts.vw_banco_ruc_colisiones         -> marts.vw_entidad_ruc_colisiones
--   restricciones, índices y secuencia con "banco" en el nombre -> "entidad"
--
-- staging NO cambia (staging.banco_maestro, columnas banco/banco_codigo): es el espejo de
-- las fuentes y el código de carga lo mapea a marts.dim_entidad en refresh_marts().
--
-- Postgres guarda las vistas por OID, así que los RENAME de tabla y columna se propagan
-- solos a su definición; lo único que no cambia solo es el nombre de las columnas que
-- exponen, y eso se renombra abajo. Las migraciones anteriores (04, 18, 22, 32, ...)
-- siguen creando los objetos con el nombre viejo en una base nueva, y esta los renombra:
-- toda migración nueva debe usar ya los nombres dim_entidad / entidad_id.
--
-- Idempotente: si marts.dim_banco ya no existe, no hace nada.

DO $$
DECLARE
    r record;
BEGIN
    IF to_regclass('marts.dim_banco') IS NULL THEN
        RAISE NOTICE 'sql/37: marts.dim_banco no existe, nada que renombrar';
        RETURN;
    END IF;

    -- 1. Dimensión
    ALTER TABLE marts.dim_banco RENAME TO dim_entidad;
    ALTER TABLE marts.dim_entidad RENAME COLUMN banco_id TO entidad_id;
    ALTER TABLE marts.dim_entidad RENAME COLUMN banco TO entidad;
    ALTER TABLE marts.dim_entidad RENAME COLUMN banco_codigo TO entidad_codigo;

    -- 2. banco_id en los hechos
    FOR r IN
        SELECT c.table_name
        FROM information_schema.columns c
        JOIN information_schema.tables t USING (table_schema, table_name)
        WHERE c.table_schema = 'marts' AND c.column_name = 'banco_id'
          AND t.table_type = 'BASE TABLE'
    LOOP
        EXECUTE format('ALTER TABLE marts.%I RENAME COLUMN banco_id TO entidad_id', r.table_name);
    END LOOP;

    -- 3. Columnas expuestas por las vistas
    FOR r IN
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t USING (table_schema, table_name)
        WHERE c.table_schema = 'marts' AND t.table_type = 'VIEW'
          AND c.column_name IN ('banco_id', 'banco', 'banco_codigo', 'saldo_banco')
    LOOP
        EXECUTE format('ALTER VIEW marts.%I RENAME COLUMN %I TO %I',
                       r.table_name, r.column_name, replace(r.column_name, 'banco', 'entidad'));
    END LOOP;

    IF to_regclass('marts.vw_banco_ruc_colisiones') IS NOT NULL THEN
        ALTER VIEW marts.vw_banco_ruc_colisiones RENAME TO vw_entidad_ruc_colisiones;
    END IF;

    -- 4. Nombres de restricciones (renombrar una restricción con índice renombra el índice),
    --    luego índices sueltos y la secuencia
    FOR r IN
        SELECT con.conrelid::regclass AS tabla, con.conname
        FROM pg_constraint con
        WHERE con.connamespace = 'marts'::regnamespace AND con.conname LIKE '%banco%'
    LOOP
        EXECUTE format('ALTER TABLE %s RENAME CONSTRAINT %I TO %I',
                       r.tabla, r.conname, replace(r.conname, 'banco', 'entidad'));
    END LOOP;

    FOR r IN
        SELECT relname FROM pg_class
        WHERE relnamespace = 'marts'::regnamespace AND relkind = 'i' AND relname LIKE '%banco%'
    LOOP
        EXECUTE format('ALTER INDEX marts.%I RENAME TO %I', r.relname, replace(r.relname, 'banco', 'entidad'));
    END LOOP;

    FOR r IN
        SELECT relname FROM pg_class
        WHERE relnamespace = 'marts'::regnamespace AND relkind = 'S' AND relname LIKE '%banco%'
    LOOP
        EXECUTE format('ALTER SEQUENCE marts.%I RENAME TO %I', r.relname, replace(r.relname, 'banco', 'entidad'));
    END LOOP;
END $$;
