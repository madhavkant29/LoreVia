#!/usr/bin/env bash
# Read-only cgroup and process memory snapshot for the VPS Compose deployment.
set -euo pipefail

compose_file="${LOREVIA_COMPOSE_FILE:-docker-compose.yml}"
compose_env_file="${LOREVIA_COMPOSE_ENV_FILE:-backend/.env}"
compose_args=(--env-file "$compose_env_file" -f "$compose_file")
if (($#)); then
  services=("$@")
else
  services=(backend worker-extraction worker-analysis worker-embedding worker-intelligence worker-maintenance celery-beat redis nginx)
fi

printf 'snapshot_utc=%s compose=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$compose_file"
awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/ { printf "host_%s_kib=%s\n", tolower(substr($1, 1, length($1)-1)), $2 }' /proc/meminfo
for service in "${services[@]}"; do
  container_id="$(docker compose "${compose_args[@]}" ps -q "$service")"
  if [[ -z "$container_id" ]]; then
    printf 'service=%s state=not_running\n' "$service"
    continue
  fi

  printf 'service=%s container=%s docker_stats=' "$service" "$container_id"
  docker stats --no-stream --format '{{.MemUsage}}' "$container_id"
  if ! docker exec "$container_id" sh -c 'command -v python >/dev/null 2>&1'; then
    printf 'process_memory=unavailable_without_python\n'
    continue
  fi
  docker exec "$container_id" python -c '
from pathlib import Path

root = Path("/sys/fs/cgroup")
current = root / "memory.current"
stat = root / "memory.stat"
events = root / "memory.events"
if current.exists():
    print(f"cgroup_memory_bytes={current.read_text().strip()}")
if stat.exists():
    entries = dict(line.split() for line in stat.read_text().splitlines())
    for name in ("anon", "file", "kernel", "slab", "sock"):
        if name in entries:
            print(f"cgroup_{name}_bytes={entries[name]}")
if events.exists():
    entries = dict(line.split() for line in events.read_text().splitlines())
    for name in ("oom", "oom_kill"):
        if name in entries:
            print(f"cgroup_{name}_count={entries[name]}")
totals = {name: 0 for name in ("Rss", "Pss", "Private_Clean", "Private_Dirty")}
readable = 0
for path in Path("/proc").glob("[0-9]*/smaps_rollup"):
    try:
        lines = path.read_text().splitlines()
    except (OSError, PermissionError):
        continue
    readable += 1
    for line in lines:
        name, _, value = line.partition(":")
        if name in totals:
            totals[name] += int(value.split()[0]) * 1024
print(f"processes_with_smaps={readable}")
for name, value in totals.items():
    print(f"process_{name.lower()}_bytes={value}")
'
done
