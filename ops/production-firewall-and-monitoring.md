# Production Firewall And Monitoring Notes

These steps are required on the Hetzner VPS or in the Hetzner Cloud Firewall.
They are not enforced by `docker-compose.yml`.

## Firewall

Recommended baseline:

- Allow `22/tcp` from your admin IPs only
- Allow `80/tcp` from Cloudflare IP ranges only
- Allow `443/tcp` from Cloudflare IP ranges only
- Deny all other inbound traffic

Example UFW shape:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <YOUR_ADMIN_IP>/32 to any port 22 proto tcp
```

Then allow Cloudflare ranges for `80` and `443`:

```bash
sudo ufw allow from 173.245.48.0/20 to any port 80 proto tcp
sudo ufw allow from 173.245.48.0/20 to any port 443 proto tcp
sudo ufw allow from 103.21.244.0/22 to any port 80 proto tcp
sudo ufw allow from 103.21.244.0/22 to any port 443 proto tcp
sudo ufw allow from 103.22.200.0/22 to any port 80 proto tcp
sudo ufw allow from 103.22.200.0/22 to any port 443 proto tcp
sudo ufw allow from 103.31.4.0/22 to any port 80 proto tcp
sudo ufw allow from 103.31.4.0/22 to any port 443 proto tcp
sudo ufw allow from 141.101.64.0/18 to any port 80 proto tcp
sudo ufw allow from 141.101.64.0/18 to any port 443 proto tcp
sudo ufw allow from 108.162.192.0/18 to any port 80 proto tcp
sudo ufw allow from 108.162.192.0/18 to any port 443 proto tcp
sudo ufw allow from 190.93.240.0/20 to any port 80 proto tcp
sudo ufw allow from 190.93.240.0/20 to any port 443 proto tcp
sudo ufw allow from 188.114.96.0/20 to any port 80 proto tcp
sudo ufw allow from 188.114.96.0/20 to any port 443 proto tcp
sudo ufw allow from 197.234.240.0/22 to any port 80 proto tcp
sudo ufw allow from 197.234.240.0/22 to any port 443 proto tcp
sudo ufw allow from 198.41.128.0/17 to any port 80 proto tcp
sudo ufw allow from 198.41.128.0/17 to any port 443 proto tcp
sudo ufw allow from 162.158.0.0/15 to any port 80 proto tcp
sudo ufw allow from 162.158.0.0/15 to any port 443 proto tcp
sudo ufw allow from 104.16.0.0/13 to any port 80 proto tcp
sudo ufw allow from 104.16.0.0/13 to any port 443 proto tcp
sudo ufw allow from 104.24.0.0/14 to any port 80 proto tcp
sudo ufw allow from 104.24.0.0/14 to any port 443 proto tcp
sudo ufw allow from 172.64.0.0/13 to any port 80 proto tcp
sudo ufw allow from 172.64.0.0/13 to any port 443 proto tcp
sudo ufw allow from 131.0.72.0/22 to any port 80 proto tcp
sudo ufw allow from 131.0.72.0/22 to any port 443 proto tcp
sudo ufw enable
```

Do not expose:

- `8000`
- `5555`
- `6379`

## Monitoring

Minimum recommended production checks:

- Uptime check for `https://api.getlorevia.com/health`
- Uptime check for `https://api.getlorevia.com/ready`
- Sentry enabled for FastAPI and Celery workers
- Hetzner alerts for CPU, RAM, disk, and bandwidth
- Docker log rotation is already configured in `docker-compose.yml`

## Protected Routes

Current app protections already exist for:

- `/api/v1/internal/*` via `X-Internal-Job-Secret`
- `/api/v1/admin/*` via admin auth

Recommended extra protection:

- Cloudflare WAF rule for `/api/v1/internal/*`
- Cloudflare WAF rule for `/api/v1/admin/*`
