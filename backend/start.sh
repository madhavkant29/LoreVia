#!/bin/bash
# Cloudflared tunnel startup is intentionally disabled for the Hetzner/VPS
# deployment. Keep the block below commented for reference in case a future
# tunnel-based ingress setup needs to be restored later.

set -e

# if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
#   echo "Starting Cloudflare tunnel..."
#   cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" &
#   sleep 2
# fi

if [ "${NORMALIZE_LOCAL_STORAGE_PERMISSIONS:-}" = "1" ] && [ "$(id -u)" = "0" ]; then
  echo "Normalizing local storage permissions for local compose..."
  python -c "from app.core.storage import ensure_local_storage_permissions; ensure_local_storage_permissions()"
fi

WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GUNICORN_KEEPALIVE="${GUNICORN_KEEPALIVE:-5}"
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-*}"
export FORWARDED_ALLOW_IPS

if [ "${RUN_MIGRATIONS:-}" = "1" ]; then
  echo "RUN_MIGRATIONS is no longer handled by the web startup path."
  echo "Run Alembic from the deploy job or a dedicated migration step before starting gunicorn."
fi

exec gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers "$WEB_CONCURRENCY" \
  --bind 0.0.0.0:8000 \
  --forwarded-allow-ips "$FORWARDED_ALLOW_IPS" \
  --timeout "$GUNICORN_TIMEOUT" \
  --keep-alive "$GUNICORN_KEEPALIVE" \
  --access-logfile - \
  --error-logfile -
