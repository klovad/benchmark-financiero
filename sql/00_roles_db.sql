-- Ejecutar conectado como superusuario (postgres) contra la instancia local.
-- psql -h localhost -p 5432 -U postgres -f sql/00_roles_db.sql

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bp_etl') THEN
        CREATE ROLE bp_etl WITH LOGIN PASSWORD 'changeme';
    END IF;
END
$$;

SELECT 'CREATE DATABASE benchmark_cartera_depositos OWNER bp_etl'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'benchmark_cartera_depositos')
\gexec
