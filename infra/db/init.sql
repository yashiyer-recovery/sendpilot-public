-- Runs once on first DB init (as the postgres superuser, in the sendpilot DB).
-- Creates the non-superuser role the application connects as, so row-level
-- security is actually enforced (a superuser/BYPASSRLS role would skip it).
-- Table/sequence privileges are granted by migration 0001.

CREATE ROLE sendpilot_app LOGIN PASSWORD 'sendpilot_app';
GRANT CONNECT ON DATABASE sendpilot TO sendpilot_app;
