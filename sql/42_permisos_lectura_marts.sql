-- Permisos de solo lectura sobre marts.* para el rol de análisis (2026-10-11).
--
-- El rol marts_lectura lo crea sql/admin/rol_lectura.sql (superusuario: el rol de la app
-- no puede crear roles). Esta migración, corrida por el dueño de marts, otorga USAGE +
-- SELECT y deja privilegios por defecto para que las tablas y vistas de migraciones
-- futuras también sean legibles. Si el rol no existe (servidor sin análisis), no hace
-- nada: rol_lectura.sql otorga lo mismo cuando se cree.

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'marts_lectura') THEN
        EXECUTE 'GRANT USAGE ON SCHEMA marts TO marts_lectura';
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA marts TO marts_lectura';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO marts_lectura';
    END IF;
END $$;
