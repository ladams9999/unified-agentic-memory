#!/bin/bash
set -euo pipefail

psql --username "$POSTGRES_USER" --dbname postgres <<'SQL'
CREATE EXTENSION IF NOT EXISTS pg_cron;
SQL
