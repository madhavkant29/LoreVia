#!/bin/bash
# Start cloudflared tunnel in background if token is set,
# then start uvicorn in foreground.

set -e

if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
  echo "Starting Cloudflare tunnel..."
  cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" &
  sleep 2
fi

WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"

if [ "${RUN_MIGRATIONS:-}" = "1" ]; then
  if [ -z "${ALEMBIC_DATABASE_URL:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
    export ALEMBIC_DATABASE_URL="$DATABASE_URL"
    echo "ALEMBIC_DATABASE_URL was not set; using DATABASE_URL explicitly for Alembic."
  fi
  echo "Running database migrations..."
  for i in $(seq 1 30); do
    if alembic -c alembic.ini upgrade heads; then
      break
    fi
    echo "Migrations failed (attempt $i/30). Retrying..."
    sleep 2
  done
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "$WEB_CONCURRENCY"
