-- Passwords are passed by psql as quoted literals, never concatenated into SQL.
CREATE ROLE analytics_agent LOGIN PASSWORD :'analytics_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
CREATE ROLE seed_writer LOGIN PASSWORD :'seed_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO analytics_agent, seed_writer',
              current_database()) \gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA core, analytics FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA core, analytics FROM PUBLIC;

GRANT USAGE ON SCHEMA analytics TO analytics_agent;
GRANT SELECT ON analytics.regions, analytics.customers, analytics.products,
    analytics.orders, analytics.order_items, analytics.payments TO analytics_agent;
GRANT USAGE ON SCHEMA core TO seed_writer;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA core TO seed_writer;

ALTER ROLE analytics_agent SET default_transaction_read_only = on;
ALTER ROLE analytics_agent SET statement_timeout = '10s';
ALTER ROLE analytics_agent SET lock_timeout = '2s';
ALTER ROLE analytics_agent SET idle_in_transaction_session_timeout = '15s';
ALTER ROLE analytics_agent SET search_path = analytics, pg_catalog;
ALTER ROLE analytics_agent SET timezone = 'America/Sao_Paulo';
ALTER ROLE seed_writer SET search_path = core, pg_catalog;
ALTER ROLE seed_writer SET timezone = 'America/Sao_Paulo';

-- New objects receive no automatic analytics grants. Review each new relation.
ALTER DEFAULT PRIVILEGES IN SCHEMA core REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics REVOKE ALL ON TABLES FROM PUBLIC;

