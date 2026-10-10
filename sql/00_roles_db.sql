-- Crea el rol de la aplicación y la base. Se ejecuta UNA vez, conectado como superusuario,
-- y no lo aplica `benchmark-bancos migrate` (las demás migraciones sí).
--
-- Nombres configurables (2026-10-09; antes 'bp_etl' y la base fijos), en este orden:
--   1. variables de psql:     psql -U postgres -v app_user=etl -v app_db=benchmark \
--                                  -v app_password='...' -f sql/00_roles_db.sql
--   2. variables de entorno:  POSTGRES_USER / POSTGRES_DB / POSTGRES_PASSWORD (las mismas
--                             del .env; docker-compose y CI ya las tienen definidas)
--   3. valores por defecto:   bp_etl / benchmark_cartera_depositos / changeme
-- Requiere psql 15 o superior (\getenv).
--
-- Idempotente: si el rol o la base ya existen no hace nada (en docker-compose y CI el
-- propio contenedor postgres los crea a partir de POSTGRES_USER/POSTGRES_DB antes de
-- correr este archivo, así que queda como no-op). Las migraciones 01..NN no nombran el rol:
-- los esquemas quedan a nombre de quien las aplica, que debe ser este rol de aplicación.

\getenv env_user POSTGRES_USER
\getenv env_db POSTGRES_DB
\getenv env_password POSTGRES_PASSWORD

\if :{?app_user}
\elif :{?env_user}
    \set app_user :env_user
\else
    \set app_user bp_etl
\endif
\if :{?app_db}
\elif :{?env_db}
    \set app_db :env_db
\else
    \set app_db benchmark_cartera_depositos
\endif
\if :{?app_password}
\elif :{?env_password}
    \set app_password :env_password
\else
    \set app_password changeme
\endif

SELECT format('CREATE ROLE %I WITH LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = :'app_user')
\gexec

-- Postgres gestionado (RDS, Azure, Cloud SQL...): el administrador no es superusuario,
-- solo tiene CREATEROLE/CREATEDB, y para crear la base a nombre de otro rol debe ser
-- miembro de ese rol ("must be able to SET ROLE"). Si hace falta, se otorga la membresía
-- a sí mismo (puede: quien crea un rol con CREATEROLE queda con ADMIN OPTION sobre él).
-- Verificado 2026-10-09 en postgres:17 con un admin NOSUPERUSER CREATEROLE CREATEDB.
-- En Postgres 16+ el creador ya es "miembro" (con ADMIN) pero sin la opción SET, que es
-- la que exige CREATE DATABASE ... OWNER; antes de 16 basta la membresía simple.
SELECT CASE WHEN current_setting('server_version_num')::int >= 160000
            THEN format('GRANT %I TO %I WITH SET TRUE', :'app_user', current_user)
            ELSE format('GRANT %I TO %I', :'app_user', current_user) END
WHERE NOT (SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname = current_user)
  AND CASE WHEN current_setting('server_version_num')::int >= 160000
           THEN NOT pg_has_role(current_user, :'app_user', 'SET')
           ELSE NOT pg_has_role(current_user, :'app_user', 'MEMBER') END
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'app_db', :'app_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'app_db')
\gexec
