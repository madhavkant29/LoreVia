"""Verify the explicit VPS deploy service list against production Compose.

Run from the repository root:
    python backend/scripts/check_production_service_contract.py

Flower is deliberately optional. Every service in ``REQUIRED_RUNTIME_SERVICES``
must both exist in production Compose and be included in the explicit
``deploy.sh`` startup command.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
DEPLOY_PATH = REPO_ROOT / "deploy.sh"
BACKEND_API_DOCKERFILE_PATH = REPO_ROOT / "backend" / "Dockerfile.api"
BACKEND_WORKER_DOCKERFILE_PATH = REPO_ROOT / "backend" / "Dockerfile.worker"
FRONTEND_DOCKERFILE_PATH = REPO_ROOT / "frontend" / "Dockerfile"
NGINX_DOCKERFILE_PATH = REPO_ROOT / "ops" / "nginx" / "Dockerfile"
NGINX_START_PATH = REPO_ROOT / "ops" / "nginx" / "start.sh"
REDIS_DOCKERFILE_PATH = REPO_ROOT / "ops" / "redis" / "Dockerfile"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci-cd.yml"

PYTHON_IMAGE = (
    "python:3.12.14-slim-trixie@"
    "sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f"
)
FRONTEND_NODE_IMAGE = (
    "node:24.20.0-alpine3.23@"
    "sha256:0388af2af070cd4736a1567cfed02469ba117848845b4165d87a333edb53d2ca"
)
NGINX_IMAGE = (
    "nginx:1.30.4-alpine3.24@"
    "sha256:dc5069ad14f19660b141b21236140b91656bf89bbc3e2417c70ae650cd66104c"
)
NGINX_LIBEXPAT_REQUIREMENT = "libexpat>=2.9.0-r0"
REDIS_IMAGE = (
    "redis:7.4.11-alpine3.21@"
    "sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499"
)

REQUIRED_RUNTIME_SERVICES = frozenset(
    {
        "redis",
        "nginx",
        "backend",
        "worker-extraction",
        "worker-analysis",
        "worker-embedding",
        "worker-intelligence",
        "worker-maintenance",
        "celery-beat",
    }
)


def compose_service_names(compose_text: str) -> frozenset[str]:
    """Return top-level service names without requiring a YAML dependency."""
    services: set[str] = set()
    in_services = False
    for line in compose_text.splitlines():
        if line == "services:":
            in_services = True
            continue
        if not in_services:
            continue
        if line and not line.startswith((" ", "\t")):
            break
        match = re.fullmatch(r"  ([a-z0-9][a-z0-9-]*):\s*", line)
        if match:
            services.add(match.group(1))
    return frozenset(services)


def deploy_service_names(deploy_text: str) -> frozenset[str]:
    """Return service tokens from deploy.sh's authoritative runtime array."""
    match = re.search(r"RUNTIME_SERVICES=\((.*?)\)", deploy_text, flags=re.DOTALL)
    if not match:
        return frozenset()
    return frozenset(
        re.findall(
            r"(?m)^[ \t]*([a-z0-9][a-z0-9-]*)[ \t]*(?:#.*)?$",
            match.group(1),
        )
    )


def production_service_contract_errors(compose_text: str, deploy_text: str) -> list[str]:
    """Describe missing or unknown services in the production startup contract."""
    compose_services = compose_service_names(compose_text)
    deploy_services = deploy_service_names(deploy_text)
    errors: list[str] = []

    missing_from_compose = REQUIRED_RUNTIME_SERVICES - compose_services
    if missing_from_compose:
        errors.append(
            "Required runtime services missing from docker-compose.yml: "
            + ", ".join(sorted(missing_from_compose))
        )

    missing_from_deploy = REQUIRED_RUNTIME_SERVICES - deploy_services
    if missing_from_deploy:
        errors.append(
            "Required runtime services missing from deploy.sh: "
            + ", ".join(sorted(missing_from_deploy))
        )

    unknown_deploy_services = deploy_services - compose_services
    if unknown_deploy_services:
        errors.append(
            "deploy.sh references unknown production services: "
            + ", ".join(sorted(unknown_deploy_services))
        )
    if '${COMPOSE} up -d "${RUNTIME_SERVICES[@]}"' not in deploy_text:
        errors.append("deploy.sh does not start the authoritative runtime service list")
    if 'for service in "${RUNTIME_SERVICES[@]}"' not in deploy_text:
        errors.append("deploy.sh health checks do not cover the runtime service list")
    if "if runtime_services_healthy &&" not in deploy_text:
        errors.append("deploy.sh success is not gated on every runtime service health check")
    if "http://127.0.0.1:8080/nginx-health" not in deploy_text:
        errors.append("deploy.sh does not probe the unprivileged Nginx health port")
    dirty_guard = "git status --porcelain --untracked-files=normal"
    checkout = 'git checkout "${DEPLOY_BRANCH}"'
    if (
        dirty_guard not in deploy_text
        or checkout not in deploy_text
        or deploy_text.index(dirty_guard) > deploy_text.index(checkout)
    ):
        errors.append("deploy.sh does not reject a dirty checkout before changing branches")
    data_preflight_command = "backend python scripts/check_release_data_preflight.py"
    data_preflight_call = (
        'echo "Running aggregate-only read-only release data preflight."\n'
        "verify_release_data_preflight\n"
    )
    schema_upgrade = "run_alembic upgrade head"
    if (
        data_preflight_command not in deploy_text
        or data_preflight_call not in deploy_text
        or schema_upgrade not in deploy_text
        or deploy_text.index(data_preflight_call) > deploy_text.index(schema_upgrade)
    ):
        errors.append(
            "deploy.sh does not run the read-only release data preflight before schema upgrade"
        )
    return errors


def production_container_contract_errors(
    compose_text: str,
    backend_api_dockerfile_text: str,
    backend_worker_dockerfile_text: str,
    frontend_dockerfile_text: str,
    nginx_dockerfile_text: str,
    workflow_text: str,
    redis_dockerfile_text: str | None = None,
) -> list[str]:
    """Describe release-image lifecycle or vulnerability-gate regressions."""
    errors: list[str] = []
    if not backend_api_dockerfile_text.startswith(f"FROM {PYTHON_IMAGE}\n"):
        errors.append("backend/Dockerfile.api does not use the pinned Python image")
    if not backend_worker_dockerfile_text.startswith(f"FROM {PYTHON_IMAGE}\n"):
        errors.append("backend/Dockerfile.worker does not use the pinned Python image")
    if "\nUSER 10001:10001\n" not in backend_api_dockerfile_text:
        errors.append("backend API image does not declare its non-root app user")
    if "\nUSER 10001:10001\n" not in backend_worker_dockerfile_text:
        errors.append("backend worker image does not declare its non-root app user")
    if (
        "mkdir -p /app/storage /var/lib/lorevia-export-spool" not in backend_worker_dockerfile_text
        or "chown -R app:app /app /var/lib/lorevia-export-spool"
        not in backend_worker_dockerfile_text
    ):
        errors.append("backend worker image does not provision the disk-backed export spool")

    tokenizer_asset_marker = (
        "python -c \"import tiktoken; tiktoken.encoding_for_model('gpt-4o-mini')\""
    )
    for image_label, dockerfile_text in (
        ("backend API", backend_api_dockerfile_text),
        ("backend worker", backend_worker_dockerfile_text),
    ):
        tokenizer_asset_is_baked = (
            "ENV DATA_GYM_CACHE_DIR=/opt/lorevia/tiktoken" in dockerfile_text
            and tokenizer_asset_marker in dockerfile_text
            and dockerfile_text.find(tokenizer_asset_marker)
            < dockerfile_text.find("ARG PREFETCH_SPACY_MODEL")
        )
        if not tokenizer_asset_is_baked:
            errors.append(f"{image_label} image does not bake its tokenizer asset")

    frontend_images = re.findall(
        r"(?m)^FROM\s+(\S+)\s+AS\s+(?:deps|builder|runner)$",
        frontend_dockerfile_text,
    )
    if len(frontend_images) != 3 or any(image != FRONTEND_NODE_IMAGE for image in frontend_images):
        errors.append(
            "frontend/Dockerfile must use the pinned supported Node.js image for every stage"
        )

    runner_marker = f"FROM {FRONTEND_NODE_IMAGE} AS runner"
    runner_stage = frontend_dockerfile_text.partition(runner_marker)[2]
    if "apk upgrade --no-cache" not in runner_stage:
        errors.append("frontend runtime does not install current Alpine security fixes")

    removable_tools = (
        "/opt/yarn-v1.22.22",
        "/usr/local/lib/node_modules/corepack",
        "/usr/local/lib/node_modules/npm",
        "/usr/local/bin/npm",
        "/usr/local/bin/npx",
    )
    missing_removals = [tool for tool in removable_tools if tool not in runner_stage]
    if missing_removals:
        errors.append(
            "frontend runtime does not remove unused package-manager paths: "
            + ", ".join(missing_removals)
        )

    if f"FROM {NGINX_IMAGE}" not in nginx_dockerfile_text:
        errors.append("ops/nginx/Dockerfile does not use the pinned stable Nginx image")
    if "apk upgrade --no-cache" not in nginx_dockerfile_text:
        errors.append("Nginx runtime does not install current Alpine security fixes")
    if NGINX_LIBEXPAT_REQUIREMENT not in nginx_dockerfile_text:
        errors.append("Nginx runtime does not require the fixed libexpat version")
    if "\nUSER 101:101\n" not in nginx_dockerfile_text:
        errors.append("Nginx image does not declare its non-root runtime user")
    if "pid        /tmp/nginx.pid;" not in nginx_dockerfile_text:
        errors.append("Nginx image does not relocate its PID file for non-root runtime")
    if "COPY ops/nginx/runtime-paths.conf" not in nginx_dockerfile_text:
        errors.append("Nginx image does not install non-root runtime paths")
    if "COPY ops/nginx/start.sh" not in nginx_dockerfile_text or (
        'ENTRYPOINT ["/usr/local/bin/lorevia-nginx-start"]' not in nginx_dockerfile_text
    ):
        errors.append("Nginx image does not render its authenticated edge configuration")
    if "dockerfile: ops/nginx/Dockerfile" not in compose_text:
        errors.append("production Compose does not build the security-patched Nginx image")
    if '"80:8080"' not in compose_text or '"443:8443"' not in compose_text:
        errors.append("production Compose does not map public ports to unprivileged Nginx ports")
    if "https://127.0.0.1:8443/nginx-health" not in compose_text:
        errors.append("production Nginx health check does not use its unprivileged TLS port")
    edge_secret_requirements = {
        "required Nginx and API environment handoff": compose_text.count(
            "EDGE_PROXY_SECRET: ${EDGE_PROXY_SECRET:?EDGE_PROXY_SECRET is required}"
        )
        >= 2,
    }
    missing_edge_secret_requirements = [
        requirement for requirement, present in edge_secret_requirements.items() if not present
    ]
    if missing_edge_secret_requirements:
        errors.append(
            "production edge-proxy authentication is incomplete: "
            + ", ".join(missing_edge_secret_requirements)
        )
    redis_direct_pin = f"image: {REDIS_IMAGE}" in compose_text
    redis_hardened_build = (
        "dockerfile: ops/redis/Dockerfile" in compose_text
        and redis_dockerfile_text is not None
        and redis_dockerfile_text.startswith(f"FROM {REDIS_IMAGE}\n")
        and "apk upgrade --no-cache" in redis_dockerfile_text
    )
    if not (redis_direct_pin or redis_hardened_build):
        errors.append("production Compose does not pin the supported Redis image digest")
    if 'user: "999:1000"' not in compose_text:
        errors.append("production Redis does not declare its non-root runtime user")

    maintenance_match = re.search(
        r"(?ms)^  worker-maintenance:\s*\n.*?(?=^  [a-z0-9][a-z0-9-]*:\s*\n|^networks:|^volumes:|\Z)",
        compose_text,
    )
    maintenance_service = maintenance_match.group(0) if maintenance_match else ""
    export_spool_requirements = {
        "maintenance spool directory": (
            'MANUSCRIPT_EXPORT_SPOOL_DIRECTORY: "/var/lib/lorevia-export-spool"'
            in maintenance_service
        ),
        "maintenance disk volume": (
            "export_spool:/var/lib/lorevia-export-spool" in maintenance_service
            and "\n  export_spool:\n" in compose_text
        ),
        "maintenance spool health probe": (
            "tempfile.TemporaryFile" in maintenance_service
            and "MANUSCRIPT_EXPORT_SPOOL_DIRECTORY" in maintenance_service
        ),
    }
    missing_export_spool = [
        requirement for requirement, present in export_spool_requirements.items() if not present
    ]
    if missing_export_spool:
        errors.append(
            "production export spool contract is incomplete: " + ", ".join(missing_export_spool)
        )
    if (
        "> /tmp/redis.conf" not in compose_text
        or "exec redis-server /tmp/redis.conf" not in compose_text
    ):
        errors.append("production Redis does not keep its password out of process arguments")
    if "REDISCLI_AUTH=" not in compose_text or "redis-cli -a" in compose_text:
        errors.append("production Redis health check exposes its password in process arguments")

    runtime_hardening_requirements = {
        "read-only filesystem": "read_only: true" in compose_text,
        "no-new-privileges": "no-new-privileges:true" in compose_text,
        "dropped capabilities": re.search(r"(?m)^\s+- ALL\s*$", compose_text) is not None,
        "writable temporary filesystem": "/tmp:rw,noexec,nosuid,nodev" in compose_text,
        "all runtime services": compose_text.count("<<: *runtime-hardening") >= 10,
    }
    missing_runtime_hardening = [
        requirement
        for requirement, present in runtime_hardening_requirements.items()
        if not present
    ]
    if missing_runtime_hardening:
        errors.append(
            "production runtime hardening is incomplete: " + ", ".join(missing_runtime_hardening)
        )

    security_start = workflow_text.find("\n  security-scan:")
    image_scan_start = workflow_text.find("\n  container-image-scan:")
    security_job = (
        workflow_text[security_start:image_scan_start]
        if security_start >= 0 and image_scan_start > security_start
        else ""
    )
    config_scan_requirements = {
        "configuration scan": "scan-type: 'config'" in security_job,
        "misconfiguration scanner": "scanners: 'misconfig'" in security_job,
        "high/critical policy": "severity: 'HIGH,CRITICAL'" in security_job,
        "blocking exit code": "exit-code: '1'" in security_job,
    }
    missing_config_scan_requirements = [
        requirement for requirement, present in config_scan_requirements.items() if not present
    ]
    if missing_config_scan_requirements:
        errors.append(
            "CI container-configuration gate is incomplete: "
            + ", ".join(missing_config_scan_requirements)
        )

    scan_start = workflow_text.find("\n  container-image-scan:")
    push_start = workflow_text.find("\n  build-and-push-docker:")
    scan_job = (
        workflow_text[scan_start:push_start] if scan_start >= 0 and push_start > scan_start else ""
    )
    scan_requirements = {
        "five production images": scan_job.count("scan-type: 'image'") >= 5,
        "vulnerability-only scanners": scan_job.count("scanners: 'vuln'") >= 5,
        "fixable high/critical policy": (
            scan_job.count("severity: 'HIGH,CRITICAL'") >= 5
            and scan_job.count("ignore-unfixed: true") >= 5
        ),
        "blocking exit codes": scan_job.count("exit-code: '1'") >= 5,
        "backend image": "lorevia-backend-security:${{ github.sha }}" in scan_job,
        "worker image": "lorevia-worker-security:${{ github.sha }}" in scan_job,
        "Nginx image": "lorevia-nginx-security:${{ github.sha }}" in scan_job,
        "Redis image": (
            REDIS_IMAGE in scan_job
            or (
                "lorevia-redis-security:${{ github.sha }}" in scan_job
                and REDIS_IMAGE in (redis_dockerfile_text or "")
            )
        ),
        "frontend image": "lorevia-frontend-security:${{ github.sha }}" in scan_job,
        "offline hardened tokenizer probes": (
            scan_job.count("--network none --read-only") >= 2
            and scan_job.count("tiktoken.encoding_for_model('gpt-4o-mini')") >= 2
        ),
    }
    missing_scan_requirements = [
        requirement for requirement, present in scan_requirements.items() if not present
    ]
    if missing_scan_requirements:
        errors.append(
            "CI production-image vulnerability gate is incomplete: "
            + ", ".join(missing_scan_requirements)
        )

    gated_push = re.search(
        r"(?m)^  build-and-push-docker:\s*\n"
        r"    needs: \[container-image-scan\]\s*$",
        workflow_text,
    )
    if not gated_push:
        errors.append("CI image publishing is not gated by production-image scans")
    return errors


def nginx_edge_start_contract_errors(start_text: str) -> list[str]:
    """Describe regressions in authenticated Nginx configuration rendering."""
    requirements = {
        "direct environment input": 'edge_proxy_secret="${EDGE_PROXY_SECRET:-}"' in start_text,
        "secret-file fallback": "EDGE_PROXY_SECRET_FILE" in start_text,
        "URL-safe length validation": (
            '"${secret_length}" -lt 32' in start_text
            and '"${secret_length}" -gt 128' in start_text
            and "^[A-Za-z0-9_-]+$" in start_text
        ),
        "owner-only rendered configuration": "umask 077" in start_text,
        "template substitution": "envsubst '${EDGE_PROXY_SECRET}'" in start_text,
        "runtime environment cleanup": "unset edge_proxy_secret EDGE_PROXY_SECRET" in start_text,
    }
    missing = [requirement for requirement, present in requirements.items() if not present]
    if not missing:
        return []
    return ["Nginx edge-proxy renderer is incomplete: " + ", ".join(missing)]


def main() -> int:
    compose_text = COMPOSE_PATH.read_text(encoding="utf-8")
    errors = production_service_contract_errors(
        compose_text,
        DEPLOY_PATH.read_text(encoding="utf-8"),
    )
    errors.extend(
        production_container_contract_errors(
            compose_text,
            BACKEND_API_DOCKERFILE_PATH.read_text(encoding="utf-8"),
            BACKEND_WORKER_DOCKERFILE_PATH.read_text(encoding="utf-8"),
            FRONTEND_DOCKERFILE_PATH.read_text(encoding="utf-8"),
            NGINX_DOCKERFILE_PATH.read_text(encoding="utf-8"),
            CI_WORKFLOW_PATH.read_text(encoding="utf-8"),
            redis_dockerfile_text=REDIS_DOCKERFILE_PATH.read_text(encoding="utf-8"),
        )
    )
    errors.extend(nginx_edge_start_contract_errors(NGINX_START_PATH.read_text(encoding="utf-8")))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Production service contract is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
