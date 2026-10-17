#!/bin/bash
# Normalize local storage permissions for named volumes, then drop privileges
# back to the non-root app user before starting the requested API/worker process.

set -e

if [ "${NORMALIZE_LOCAL_STORAGE_PERMISSIONS:-}" = "1" ]; then
  echo "Normalizing local storage permissions for local compose..."
  python -c "from app.core.storage import ensure_local_storage_permissions; ensure_local_storage_permissions()"
fi

if [ "$(id -u)" = "0" ]; then
  exec su -s /bin/bash app -c 'exec "$@"' -- lorevia-entrypoint "$@"
fi

exec "$@"
