#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/lorevia/current}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-./backend/.env}"
COMPOSE="docker compose --env-file ${COMPOSE_ENV_FILE} -f ${COMPOSE_FILE}"
BACKUP_DIR="${BACKUP_DIR:-/opt/lorevia/backups/supabase}"
SYSTEMD_UNIT_SOURCE="${SYSTEMD_UNIT_SOURCE:-${APP_DIR}/ops/systemd/lorevia-compose.service}"
SYSTEMD_UNIT_TARGET="${SYSTEMD_UNIT_TARGET:-/etc/systemd/system/lorevia-compose.service}"
ENABLE_SYSTEMD_UNIT="${ENABLE_SYSTEMD_UNIT:-1}"
SYSTEMD_RELOAD="${SYSTEMD_RELOAD:-1}"
RUNTIME_SERVICES=(
  redis
  nginx
  backend
  worker-extraction
  worker-analysis
  worker-embedding
  worker-intelligence
  worker-maintenance
  celery-beat
)

if [[ -z "${SUDO:-}" ]]; then
  if [[ "$(id -u)" -eq 0 ]]; then
    SUDO=""
  else
    SUDO="sudo"
  fi
fi

enable_systemd_unit() {
  if [[ "${ENABLE_SYSTEMD_UNIT}" != "1" ]]; then
    echo "Skipping systemd unit installation because ENABLE_SYSTEMD_UNIT is not 1."
    return 0
  fi

  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl is not available; cannot enable lorevia-compose.service."
    return 0
  fi

  if [[ ! -f "${SYSTEMD_UNIT_SOURCE}" ]]; then
    echo "Missing systemd unit source: ${SYSTEMD_UNIT_SOURCE}"
    exit 1
  fi

  echo "Installing systemd unit to ${SYSTEMD_UNIT_TARGET}."
  ${SUDO} install -m 0644 "${SYSTEMD_UNIT_SOURCE}" "${SYSTEMD_UNIT_TARGET}"

  if [[ "${SYSTEMD_RELOAD}" == "1" ]]; then
    ${SUDO} systemctl daemon-reload
  fi

  ${SUDO} systemctl enable lorevia-compose.service
}

runtime_services_healthy() {
  local service
  local container_id
  local health_status

  for service in "${RUNTIME_SERVICES[@]}"; do
    container_id="$(${COMPOSE} ps -q "${service}")"
    if [[ -z "${container_id}" ]]; then
      return 1
    fi
    health_status="$(docker inspect \
      --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      "${container_id}")"
    if [[ "${health_status}" != "healthy" ]]; then
      return 1
    fi
  done
}

cd "${APP_DIR}"

if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo "Refusing to deploy from a dirty checkout."
  git status --short
  exit 1
fi

git fetch --prune origin
git checkout "${DEPLOY_BRANCH}"
git pull --ff-only origin "${DEPLOY_BRANCH}"

RELEASE_SHA="$(git rev-parse --verify HEAD)"
if [[ ! "${RELEASE_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Could not resolve a full Git release SHA."
  exit 1
fi
export RELEASE_SHA
echo "Building LoreVia release ${RELEASE_SHA}."

if [[ "${RUN_TESTS:-0}" == "1" ]]; then
  docker compose -f docker-compose-local.yml exec -T api pytest tests/integration/test_beta_reads_api.py tests/unit/test_trial_email_service.py -v
fi

if [[ ! -f "${COMPOSE_ENV_FILE}" ]]; then
  echo "Missing Compose env file: ${COMPOSE_ENV_FILE}"
  exit 1
fi

# Source env vars from the compose env file for variable substitution in docker-compose.yml.
# systemd supplies these via EnvironmentFile; manual runs source from here as a fallback.
if [[ -z "${REDIS_PASSWORD:-}" ]] || [[ -z "${LOREVIA_ENV_FILE:-}" ]]; then
  set -a
  source "${COMPOSE_ENV_FILE}"
  set +a
fi

if [[ -z "${REDIS_PASSWORD:-}" ]]; then
  echo "REDIS_PASSWORD must be set in ${COMPOSE_ENV_FILE}"
  exit 1
fi

# E2E bypass flags must never exist in a production deploy environment,
# including anything that leaked in through the Compose env file.
for e2e_flag in NEXT_PUBLIC_E2E_MOCK_API ADMIN_E2E_TEST_SECRET ADMIN_E2E_ALLOW_PRODUCTION; do
  if [[ -n "${!e2e_flag:-}" ]]; then
    echo "Refusing to deploy: ${e2e_flag} is set in the deploy environment."
    exit 1
  fi
done

if [[ -z "${ALEMBIC_DATABASE_URL:-}" ]]; then
  echo "ALEMBIC_DATABASE_URL must be exported before deploy."
  exit 1
fi

if [[ "${ALEMBIC_CONFIRM_REMOTE:-}" != "YES_I_AM_SURE" ]]; then
  echo "ALEMBIC_CONFIRM_REMOTE must be explicitly exported as YES_I_AM_SURE before deploy."
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

if [[ "${ENABLE_DB_BACKUP:-1}" == "1" ]]; then
  pg_dump "${ALEMBIC_DATABASE_URL}" -F c -f "${BACKUP_DIR}/pre_deploy_$(date +%Y%m%d_%H%M%S).dump"
fi

SECURITY_REFRESH="$(date -u +%Y%m%dT%H%M%SZ)"
export SECURITY_REFRESH
${COMPOSE} build --pull

# One-time legacy cutoff cutover (see DEPLOY_AND_FREEZE.md).
# Stop the application stack BEFORE migrations and cutoff recording so that:
#   - no queued or retrying job can start a provider call during the window,
#   - no new manuscript can be uploaded before the cutoff exists.
# Redis stays up so the one-off migration/record containers can connect.
echo "Stopping application services for the legacy cutoff cutover."
${COMPOSE} stop nginx backend \
  worker-extraction worker-analysis worker-embedding worker-intelligence \
  worker-maintenance celery-beat >/dev/null 2>&1 || true

run_alembic() {
  local alembic_env_args=()
  if [[ -n "${ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES:-}" ]]; then
    alembic_env_args+=(-e ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES="${ALEMBIC_ALLOW_DESTRUCTIVE_UPGRADES}")
  fi
  if [[ -n "${ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES:-}" ]]; then
    alembic_env_args+=(-e ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES="${ALEMBIC_ALLOW_DESTRUCTIVE_DOWNGRADES}")
  fi
  if [[ -n "${ALEMBIC_ALLOWED_DESTRUCTIVE_UPGRADE_REVISIONS:-}" ]]; then
    alembic_env_args+=(-e ALEMBIC_ALLOWED_DESTRUCTIVE_UPGRADE_REVISIONS="${ALEMBIC_ALLOWED_DESTRUCTIVE_UPGRADE_REVISIONS}")
  fi

  ${COMPOSE} run --rm \
    -e ALEMBIC_DATABASE_URL="${ALEMBIC_DATABASE_URL}" \
    -e ALEMBIC_CONFIRM_REMOTE="${ALEMBIC_CONFIRM_REMOTE}" \
    "${alembic_env_args[@]}" \
    backend python -m alembic "$@"
}

verify_runtime_schema() {
  ${COMPOSE} run --rm \
    -e DATABASE_URL="${ALEMBIC_DATABASE_URL}" \
    backend python -c 'import asyncio
from app.core.database import engine
from app.utils.schema_utils import assert_core_runtime_schema_compatible_from_engine

async def main():
    try:
        await assert_core_runtime_schema_compatible_from_engine(engine)
    finally:
        await engine.dispose()

asyncio.run(main())
'
}

verify_release_data_preflight() {
  ${COMPOSE} run --rm \
    -e DATABASE_URL="${ALEMBIC_DATABASE_URL}" \
    backend python scripts/check_release_data_preflight.py
}

current_output="$(run_alembic current -q || true)"
heads_output="$(run_alembic heads -q)"

head_count="$(printf '%s\n' "${heads_output}" | awk 'NF {count++} END {print count+0}')"
if [[ "${head_count}" -ne 1 ]]; then
  echo "Expected exactly one Alembic head before deploy. Resolve migration branches first."
  printf '%s\n' "${heads_output}"
  exit 1
fi

head_rev="$(printf '%s\n' "${heads_output}" | awk 'NF {print $1; exit}')"
current_revs="$(printf '%s\n' "${current_output}" | awk 'NF {print $1}')"

echo "Running aggregate-only read-only release data preflight."
verify_release_data_preflight

if printf '%s\n' "${current_revs}" | grep -Fx "${head_rev}" >/dev/null 2>&1; then
  echo "Database already at Alembic head ${head_rev}; skipping upgrade."
else
  echo "Upgrading database to Alembic head ${head_rev}."
  run_alembic upgrade head
fi

post_current_output="$(run_alembic current -q)"
if ! printf '%s\n' "${post_current_output}" | awk 'NF {print $1}' | grep -Fx "${head_rev}" >/dev/null 2>&1; then
  echo "Database did not land on expected Alembic head ${head_rev}."
  printf '%s\n' "${post_current_output}"
  exit 1
fi

echo "Verifying runtime schema compatibility."
verify_runtime_schema

# Record the write-once legacy freeze cutoff BEFORE the API starts accepting
# requests. The cutoff is the moment the previous deployment stopped processing;
# any manuscript uploaded after this instant is never touched by the freeze.
if [[ "${SKIP_LEGACY_CUTOFF_RECORD:-0}" == "1" ]]; then
  echo "SKIP_LEGACY_CUTOFF_RECORD=1 set; skipping cutoff recording. Record it manually before uploads resume."
else
  echo "Recording the one-time legacy freeze cutoff (write-once, no book changes)."
  ${COMPOSE} run --rm \
    -e ALEMBIC_DATABASE_URL="${ALEMBIC_DATABASE_URL}" \
    -e ALEMBIC_CONFIRM_REMOTE="${ALEMBIC_CONFIRM_REMOTE}" \
    backend python scripts/freeze_legacy_manuscripts.py \
      --record-cutoff --execute --confirm YES_I_UNDERSTAND
fi

enable_systemd_unit

${COMPOSE} up -d "${RUNTIME_SERVICES[@]}"

for retry_index in $(seq 0 8); do
  if runtime_services_healthy && \
     ${COMPOSE} exec -T nginx wget -qO- http://127.0.0.1:8080/nginx-health >/dev/null 2>&1 && \
     ${COMPOSE} exec -T nginx curl --noproxy '*' -kfsS --max-time 5 --resolve api.getlorevia.com:8443:127.0.0.1 https://api.getlorevia.com:8443/ready >/dev/null 2>&1 && \
     ${COMPOSE} exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=5)" >/dev/null 2>&1; then
    echo "Deploy succeeded"
    exit 0
  fi
  if [[ "${retry_index}" -lt 8 ]]; then
    retry_delay=$((2 ** retry_index))
    if [[ "${retry_delay}" -gt 16 ]]; then
      retry_delay=16
    fi
    sleep "${retry_delay}"
  fi
done

echo "Health checks did not pass after deployment"
${COMPOSE} ps
exit 1
