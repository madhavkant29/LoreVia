# Hetzner Service Management

This repo uses Docker Compose for the app stack and systemd to make sure the stack starts after a VPS reboot.

## What systemd does here

- Starts the Compose stack on boot
- Stops the Compose stack cleanly on shutdown
- Lets Docker handle per-container restarts with `restart: unless-stopped`

## Install the unit

The recommended path is to let [`deploy.sh`](/C:/Users/madha/.vscode/prod/LoreVia2/deploy.sh) handle this automatically.

If you need to do it manually:

1. Copy [ops/systemd/lorevia-compose.service](/C:/Users/madha/.vscode/prod/LoreVia2/ops/systemd/lorevia-compose.service) to:
   - `/etc/systemd/system/lorevia-compose.service`
2. Make sure the repo is deployed at:
   - `/opt/lorevia/current`
3. Reload systemd:
   - `sudo systemctl daemon-reload`
4. Enable the service:
   - `sudo systemctl enable lorevia-compose.service`
5. Start it:
   - `sudo systemctl start lorevia-compose.service`

## Deploy script behavior

- `deploy.sh` installs the systemd unit from `ops/systemd/lorevia-compose.service`
- It runs `systemctl daemon-reload`
- It enables `lorevia-compose.service`
- It can be disabled by setting `ENABLE_SYSTEMD_UNIT=0`

## Daily commands

- Check status:
  - `sudo systemctl status lorevia-compose.service`
- Restart the full stack:
  - `sudo systemctl restart lorevia-compose.service`
- Stop the full stack:
  - `sudo systemctl stop lorevia-compose.service`
- View boot/runtime logs for the unit:
  - `journalctl -u lorevia-compose.service -f`

## Container logs

Once the stack is up, use Docker for service-level logs:

- `docker compose -f docker-compose.yml logs -f nginx`
- `docker compose -f docker-compose.yml logs -f backend`
- `docker compose -f docker-compose.yml logs -f worker-extraction`
- `docker compose -f docker-compose.yml logs -f worker-analysis`
- `docker compose -f docker-compose.yml logs -f worker-intelligence`
- `docker compose -f docker-compose.yml logs -f celery-beat`

## Notes

- Keep `restart: unless-stopped` on the Compose services.
- Do not add a second supervisor for the same containers unless you are replacing systemd entirely.
- If you move the repo path, update `WorkingDirectory` in the unit file.
