# Production Firewall And Monitoring Notes

These steps are required on the Hetzner VPS or in the Hetzner Cloud Firewall.
They are not enforced by `docker-compose.yml`.

## Firewall

Recommended baseline:

- Allow `22/tcp` from your admin IPs only
- Allow `80/tcp` and `443/tcp` from the public internet if the VPS is the TLS terminator
- If Cloudflare still proxies the site, keep `80/tcp` and `443/tcp` restricted to Cloudflare IP ranges instead
- Deny all other inbound traffic
- If you already enforce those rules in Hetzner Cloud Firewall, that is sufficient
- Treat host-level `ufw` as optional defense in depth, not a second required source of truth

Recommended operator verification when Cloudflare proxies the site:

```bash
curl -I https://api.getlorevia.com/ready
```

Then, from a non-Cloudflare network, confirm direct requests to the VPS public IP
on `80` and `443` fail.

Do not expose:

- `8000`
- `5555`
- `6379`

## TLS

The current repo ships with a Cloudflare Origin Certificate for `api.getlorevia.com` in `ops/nginx/certs/`, so if Cloudflare is still proxying the site you do **not** need Certbot for browser traffic.

The proxy runs as the unprivileged Nginx uid/gid `101`. On the VPS, keep the
private key owned by `root`, grant group `101` read access, and do not make it
world-readable:

```bash
sudo chown root:101 ops/nginx/certs/api.getlorevia.com.key
sudo chmod 640 ops/nginx/certs/api.getlorevia.com.key
sudo chmod 644 ops/nginx/certs/api.getlorevia.com.pem
```

If Hetzner is serving the site directly without Cloudflare proxying, replace the origin certificate with a publicly trusted certificate such as Let's Encrypt via Certbot.

If you switch to Certbot, `80/tcp` must be reachable for HTTP-01 validation unless you use DNS-01.

## Monitoring

Minimum recommended production checks:

- Uptime check for `https://api.getlorevia.com/health`
- Uptime check for `https://api.getlorevia.com/ready`
- Sentry enabled for FastAPI and Celery workers
- Hetzner alerts for CPU, RAM, disk, and bandwidth
- Docker log rotation is already configured in `docker-compose.yml`

## Startup

Use systemd to start the Docker Compose stack automatically on VPS reboot. The unit template lives in [ops/systemd/lorevia-compose.service](/C:/Users/madha/.vscode/prod/LoreVia2/ops/systemd/lorevia-compose.service), with a setup guide in [docs/hetzner-service-management.md](/C:/Users/madha/.vscode/prod/LoreVia2/docs/hetzner-service-management.md). The root-level [deploy.sh](/C:/Users/madha/.vscode/prod/LoreVia2/deploy.sh) now installs and enables the unit by default.

## Protected Routes

Current app protections already exist for:

- `/api/v1/internal/*` via `X-Internal-Job-Secret`
- `/api/v1/admin/*` via admin auth

Recommended extra protection:

- Cloudflare WAF rule for `/api/v1/internal/*`
- Cloudflare WAF rule for `/api/v1/admin/*`
