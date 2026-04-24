"""
Cloudflare Tunnel security — Option 1.

With cloudflared installed, the Railway service is only reachable through
the tunnel. The public Railway URL becomes unreachable from the internet.

Setup:
1. Install cloudflared on Railway via Dockerfile.api
2. Set CLOUDFLARE_TUNNEL_TOKEN env var
3. cloudflared tunnel run --token $CLOUDFLARE_TUNNEL_TOKEN
   (started automatically by start.sh alongside uvicorn)

This module provides a FastAPI middleware that validates the
CF-Connecting-IP header is present (set by Cloudflare on tunnelled requests).
When running via tunnel, all requests will have this header.
Direct requests to the Railway URL will not — and get rejected.
"""
