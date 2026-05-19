#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/lorevia/current}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE="docker compose -f ${COMPOSE_FILE}"
BACKUP_DIR="${BACKUP_DIR:-/opt/lorevia/backups/supabase}"
SYSTEMD_UNIT_SOURCE="${SYSTEMD_UNIT_SOURCE:-${APP_DIR}/ops/systemd/lorevia-compose.service}"
SYSTEMD_UNIT_TARGET="${SYSTEMD_UNIT_TARGET:-/etc/systemd/system/lorevia-compose.service}"
ENABLE_SYSTEMD_UNIT="${ENABLE_SYSTEMD_UNIT:-1}"
SYSTEMD_RELOAD="${SYSTEMD_RELOAD:-1}"

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

cd "${APP_DIR}"

git fetch --prune origin
git checkout main
git pull --ff-only origin main

if [[ "${RUN_TESTS:-0}" == "1" ]]; then
  docker compose -f docker-compose-local.yml exec -T api pytest tests/integration/test_beta_reads_api.py tests/unit/test_trial_email_service.py -v
fi

if [[ ! -f "./ops/env/backend.env" ]]; then
  echo "Missing ./ops/env/backend.env"
  exit 1
fi

if [[ -z "${ALEMBIC_DATABASE_URL:-}" ]]; then
  echo "ALEMBIC_DATABASE_URL must be exported before deploy."
  exit 1
fi

export ALEMBIC_CONFIRM_REMOTE="${ALEMBIC_CONFIRM_REMOTE:-YES_I_AM_SURE}"

mkdir -p "${BACKUP_DIR}"

if [[ "${ENABLE_DB_BACKUP:-1}" == "1" ]]; then
  pg_dump "${ALEMBIC_DATABASE_URL}" -F c -f "${BACKUP_DIR}/pre_deploy_$(date +%Y%m%d_%H%M%S).dump"
fi

${COMPOSE} build --pull

run_alembic() {
  ${COMPOSE} run --rm \
    -e ALEMBIC_DATABASE_URL="${ALEMBIC_DATABASE_URL}" \
    -e ALEMBIC_CONFIRM_REMOTE="${ALEMBIC_CONFIRM_REMOTE}" \
    backend python -m alembic "$@"
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

enable_systemd_unit

${COMPOSE} up -d nginx backend worker-extraction worker-analysis worker-intelligence celery-beat

for attempt in $(seq 1 20); do
  if ${COMPOSE} exec -T nginx wget -qO- http://127.0.0.1/nginx-health >/dev/null 2>&1 && \
     ${COMPOSE} exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=5)" >/dev/null 2>&1; then
    echo "Deploy succeeded"
    exit 0
  fi
  sleep 3
done

echo "Health checks did not pass after deployment"
exit 1
