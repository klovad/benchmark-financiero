-- Rol de SOLO LECTURA sobre marts.* para análisis (2026-10-11). Se ejecuta UNA vez,
-- conectado como superusuario (o un admin con CREATEROLE), igual que sql/00. Vive en
-- sql/admin/ para que `benchmark-bancos migrate`, CI y docker-compose no lo apliquen
-- (todos leen solo sql/*.sql).
--
-- Crea dos roles:
--   marts_lectura   NOLOGIN, el "grupo" con los permisos (USAGE + SELECT sobre marts).
--                   Nombre fijo: es el contrato que usa la migración sql/42.
--   <lector_user>   LOGIN, miembro de marts_lectura, con default_transaction_read_only
--                   (aunque alguien le diera más permisos, sus sesiones arrancan en
--                   solo lectura). Por defecto 'analista'.
-- Staging y meta quedan fuera: el análisis consume solo el esquema estrella.
--
-- Uso (PowerShell; pide la contraseña del nuevo rol si no se pasa con -v):
--   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -p 5432 -U postgres -d postgres `
--       -v ON_ERROR_STOP=1 -v app_db=benchmark_cartera_depositos -f sql/admin/rol_lectura.sql
-- Opcionales: -v lector_user=otro_nombre  -v lector_password=...
--
-- Idempotente: si los roles ya existen no los recrea ni cambia la contraseña (para
-- cambiarla: ALTER ROLE analista PASSWORD '...'). Los permisos se vuelven a otorgar sin
-- error. Si marts todavía no existe (servidor recién instalado), los permisos los otorga
-- sql/42 al migrar.

\getenv env_db POSTGRES_DB
\if :{?app_db}
\elif :{?env_db}
    \set app_db :env_db
\else
    \set app_db benchmark_cartera_depositos
\endif
\if :{?lector_user}
\else
    \set lector_user analista
\endif
\if :{?lector_password}
\else
    \prompt 'Contraseña para el rol de solo lectura: ' lector_password
\endif

SELECT 'CREATE ROLE marts_lectura NOLOGIN'
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'marts_lectura')
\gexec

SELECT format('CREATE ROLE %I WITH LOGIN PASSWORD %L', :'lector_user', :'lector_password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = :'lector_user')
\gexec

SELECT format('GRANT marts_lectura TO %I', :'lector_user')
\gexec
SELECT format('ALTER ROLE %I SET default_transaction_read_only = on', :'lector_user')
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO marts_lectura', :'app_db')
\gexec

\connect :app_db

-- Mismo contenido que sql/42, por si la base ya estaba migrada cuando se crea el rol.
SELECT 'GRANT USAGE ON SCHEMA marts TO marts_lectura'
WHERE to_regnamespace('marts') IS NOT NULL
\gexec
SELECT 'GRANT SELECT ON ALL TABLES IN SCHEMA marts TO marts_lectura'
WHERE to_regnamespace('marts') IS NOT NULL
\gexec
-- Tablas y vistas que cree el dueño de marts en el futuro (nuevas migraciones).
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA marts GRANT SELECT ON TABLES TO marts_lectura',
              pg_get_userbyid(nspowner))
FROM pg_namespace WHERE nspname = 'marts'
\gexec
