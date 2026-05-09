#!/bin/bash
# Start cloudflared tunnel in background if token is set,
# then start uvicorn in foreground.

set -e

if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
  echo "Starting Cloudflare tunnel..."
  cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" &
  sleep 2
fi

if [ "${NORMALIZE_LOCAL_STORAGE_PERMISSIONS:-}" = "1" ] && [ "$(id -u)" = "0" ]; then
  echo "Normalizing local storage permissions for local compose..."
  python -c "from app.core.storage import ensure_local_storage_permissions; ensure_local_storage_permissions()"
fi

WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"

if [ "${RUN_MIGRATIONS:-}" = "1" ]; then
  echo "RUN_MIGRATIONS is no longer handled by the web startup path."
  echo "Run Alembic from the deploy job or a dedicated migration step before starting uvicorn."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "$WEB_CONCURRENCY"
