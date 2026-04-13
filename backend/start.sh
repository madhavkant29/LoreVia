#!/bin/bash
# Start cloudflared tunnel in background if token is set,
# then start uvicorn in foreground.

if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
  echo "Starting Cloudflare tunnel..."
  cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" &
  sleep 2
fi

WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "$WEB_CONCURRENCY"
