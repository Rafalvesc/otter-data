#!/bin/sh
set -eu
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 \
    --set analytics_password="$ANALYTICS_PASSWORD" \
    --set seed_password="$SEED_PASSWORD" \
    --single-transaction \
    --file /opt/datapilot/schema.sql \
    --file /opt/datapilot/roles.sql

