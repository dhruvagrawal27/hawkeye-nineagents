-- HAWKEYE Postgres init — runs once on a fresh data volume.
-- Schema is owned by Alembic (backend/alembic/versions/0001_initial.py).
-- This file just enables a couple of extensions we use.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
