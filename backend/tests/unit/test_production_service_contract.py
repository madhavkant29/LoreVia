from scripts.check_production_service_contract import (
    FRONTEND_NODE_IMAGE,
    NGINX_IMAGE,
    NGINX_LIBEXPAT_REQUIREMENT,
    PYTHON_IMAGE,
    REDIS_IMAGE,
    REQUIRED_RUNTIME_SERVICES,
    compose_service_names,
    deploy_service_names,
    nginx_edge_start_contract_errors,
    production_container_contract_errors,
    production_service_contract_errors,
)


def _compose_text(services: set[str]) -> str:
    rendered = "\n".join(f"  {service}:\n    image: test" for service in sorted(services))
    return f"services:\n{rendered}\nnetworks:\n  app:\n"


def _deploy_text(services: set[str]) -> str:
    rendered = "\n".join(f"  {service}" for service in sorted(services))
    return (
        f"RUNTIME_SERVICES=(\n{rendered}\n)\n"
        'runtime_services_healthy() { for service in "${RUNTIME_SERVICES[@]}"; do true; done; }\n'
        "git status --porcelain --untracked-files=normal\n"
        'git checkout "${DEPLOY_BRANCH}"\n'
        "verify_release_data_preflight() { backend python "
        "scripts/check_release_data_preflight.py; }\n"
        'echo "Running aggregate-only read-only release data preflight."\n'
        "verify_release_data_preflight\n"
        "run_alembic upgrade head\n"
        '${COMPOSE} up -d "${RUNTIME_SERVICES[@]}"\n'
        "if runtime_services_healthy && "
        "wget http://127.0.0.1:8080/nginx-health; then true; fi\n"
    )


def _frontend_dockerfile_text(image: str = FRONTEND_NODE_IMAGE) -> str:
    return (
        f"FROM {image} AS deps\n"
        f"FROM {image} AS builder\n"
        f"FROM {image} AS runner\n"
        "RUN apk upgrade --no-cache \\\n"
        "    && rm -rf /opt/yarn-v1.22.22 \\\n"
        "        /usr/local/lib/node_modules/corepack \\\n"
        "        /usr/local/lib/node_modules/npm \\\n"
        "    && rm -f /usr/local/bin/npm /usr/local/bin/npx\n"
    )


def _python_dockerfile_text(image: str = PYTHON_IMAGE) -> str:
    return (
        f"FROM {image}\n"
        "WORKDIR /app\n"
        "RUN mkdir -p /app/storage /var/lib/lorevia-export-spool && "
        "chown -R app:app /app /var/lib/lorevia-export-spool\n"
        "ENV DATA_GYM_CACHE_DIR=/opt/lorevia/tiktoken\n"
        'RUN mkdir -p "$DATA_GYM_CACHE_DIR" && '
        'python -c "import tiktoken; '
        "tiktoken.encoding_for_model('gpt-4o-mini')\"\n"
        "ARG PREFETCH_SPACY_MODEL=0\n"
        "USER 10001:10001\n"
    )


def _workflow_text(*, gate_push: bool = True) -> str:
    needs = "[container-image-scan]" if gate_push else "[backend-tests]"
    scan = (
        "        scan-type: 'image'\n"
        "        scanners: 'vuln'\n"
        "        severity: 'HIGH,CRITICAL'\n"
        "        ignore-unfixed: true\n"
        "        exit-code: '1'\n"
    )
    image_refs = (
        "lorevia-backend-security:${{ github.sha }}",
        "lorevia-worker-security:${{ github.sha }}",
        "lorevia-nginx-security:${{ github.sha }}",
        REDIS_IMAGE,
        "lorevia-frontend-security:${{ github.sha }}",
    )
    scans = "".join(f"    - image-ref: '{image_ref}'\n{scan}" for image_ref in image_refs)
    tokenizer_probes = (
        "    - run: docker run --rm --network none --read-only "
        'lorevia-backend-security:${{ github.sha }} python -c "import tiktoken; '
        "tiktoken.encoding_for_model('gpt-4o-mini')\"\n"
        "    - run: docker run --rm --network none --read-only "
        'lorevia-worker-security:${{ github.sha }} python -c "import tiktoken; '
        "tiktoken.encoding_for_model('gpt-4o-mini')\"\n"
    )
    return (
        "jobs:\n"
        "  security-scan:\n"
        "    steps:\n"
        "    - scan-type: 'config'\n"
        "      scanners: 'misconfig'\n"
        "      severity: 'HIGH,CRITICAL'\n"
        "      exit-code: '1'\n"
        "  container-image-scan:\n"
        "    steps:\n"
        f"{scans}{tokenizer_probes}"
        "  build-and-push-docker:\n"
        f"    needs: {needs}\n"
    )


def _production_compose_text() -> str:
    return (
        "x-runtime-hardening: &runtime-hardening\n"
        "  read_only: true\n"
        "  security_opt:\n"
        "    - no-new-privileges:true\n"
        "  cap_drop:\n"
        "    - ALL\n"
        "  tmpfs:\n"
        "    - /tmp:rw,noexec,nosuid,nodev\n"
        "services:\n"
        "  nginx:\n"
        "    <<: *runtime-hardening\n"
        "    build:\n"
        "      dockerfile: ops/nginx/Dockerfile\n"
        "    environment:\n"
        "      EDGE_PROXY_SECRET: ${EDGE_PROXY_SECRET:?EDGE_PROXY_SECRET is required}\n"
        "    ports:\n"
        '      - "80:8080"\n'
        '      - "443:8443"\n'
        "    healthcheck:\n"
        "      test: https://127.0.0.1:8443/nginx-health\n"
        "  backend:\n"
        "    environment:\n"
        "      EDGE_PROXY_SECRET: ${EDGE_PROXY_SECRET:?EDGE_PROXY_SECRET is required}\n"
        "  redis:\n"
        "    <<: *runtime-hardening\n"
        f"    image: {REDIS_IMAGE}\n"
        '    user: "999:1000"\n'
        "    command: umask 077; printf config > /tmp/redis.conf; "
        "exec redis-server /tmp/redis.conf\n"
        '    healthcheck: REDISCLI_AUTH="$${REDIS_PASSWORD}" redis-cli ping\n'
        "  worker-maintenance:\n"
        "    <<: *runtime-hardening\n"
        "    environment:\n"
        '      MANUSCRIPT_EXPORT_SPOOL_DIRECTORY: "/var/lib/lorevia-export-spool"\n'
        "    volumes:\n"
        "      - export_spool:/var/lib/lorevia-export-spool\n"
        "    healthcheck: tempfile.TemporaryFile MANUSCRIPT_EXPORT_SPOOL_DIRECTORY\n"
        + "".join(f"  service-{index}:\n    <<: *runtime-hardening\n" for index in range(8))
        + "volumes:\n  export_spool:\n"
    )


def _nginx_dockerfile_text() -> str:
    return (
        f"FROM {NGINX_IMAGE}\n"
        f"RUN apk add --no-cache '{NGINX_LIBEXPAT_REQUIREMENT}'\n"
        "RUN apk upgrade --no-cache\n"
        "RUN sed -i 's#pid        /run/nginx.pid;#pid        /tmp/nginx.pid;#' "
        "/etc/nginx/nginx.conf\n"
        "COPY ops/nginx/runtime-paths.conf /opt/lorevia/nginx/runtime-paths.conf\n"
        "COPY ops/nginx/start.sh /usr/local/bin/lorevia-nginx-start\n"
        "USER 101:101\n"
        'ENTRYPOINT ["/usr/local/bin/lorevia-nginx-start"]\n'
    )


def _nginx_start_text() -> str:
    return (
        'edge_proxy_secret="${EDGE_PROXY_SECRET:-}"\n'
        'secret_file="${EDGE_PROXY_SECRET_FILE:-/run/secrets/edge_proxy_secret}"\n'
        'if [ "${secret_length}" -lt 32 ] || [ "${secret_length}" -gt 128 ]; then exit 1; fi\n'
        "grep -Eq '^[A-Za-z0-9_-]+$'\n"
        "umask 077\n"
        "envsubst '${EDGE_PROXY_SECRET}'\n"
        "unset edge_proxy_secret EDGE_PROXY_SECRET\n"
    )


def test_service_parsers_handle_compose_and_runtime_service_array() -> None:
    compose_text = _compose_text(set(REQUIRED_RUNTIME_SERVICES) | {"flower"})
    deploy_text = _deploy_text(set(REQUIRED_RUNTIME_SERVICES))

    assert compose_service_names(compose_text) == REQUIRED_RUNTIME_SERVICES | {"flower"}
    assert deploy_service_names(deploy_text) == REQUIRED_RUNTIME_SERVICES
    assert production_service_contract_errors(compose_text, deploy_text) == []


def test_contract_reports_omitted_maintenance_worker() -> None:
    incomplete_services = set(REQUIRED_RUNTIME_SERVICES) - {"worker-maintenance"}

    errors = production_service_contract_errors(
        _compose_text(set(REQUIRED_RUNTIME_SERVICES)),
        _deploy_text(incomplete_services),
    )

    assert errors == ["Required runtime services missing from deploy.sh: worker-maintenance"]


def test_contract_reports_unknown_deploy_service() -> None:
    errors = production_service_contract_errors(
        _compose_text(set(REQUIRED_RUNTIME_SERVICES)),
        _deploy_text(set(REQUIRED_RUNTIME_SERVICES) | {"worker-unknown"}),
    )

    assert errors == ["deploy.sh references unknown production services: worker-unknown"]


def test_contract_requires_all_service_health_to_gate_deploy_success() -> None:
    deploy_text = _deploy_text(set(REQUIRED_RUNTIME_SERVICES)).replace(
        "if runtime_services_healthy &&", "if true &&"
    )

    errors = production_service_contract_errors(
        _compose_text(set(REQUIRED_RUNTIME_SERVICES)),
        deploy_text,
    )

    assert errors == ["deploy.sh success is not gated on every runtime service health check"]


def test_contract_requires_unprivileged_nginx_health_port() -> None:
    deploy_text = _deploy_text(set(REQUIRED_RUNTIME_SERVICES)).replace(
        "http://127.0.0.1:8080/nginx-health",
        "http://127.0.0.1/nginx-health",
    )

    errors = production_service_contract_errors(
        _compose_text(set(REQUIRED_RUNTIME_SERVICES)),
        deploy_text,
    )

    assert errors == ["deploy.sh does not probe the unprivileged Nginx health port"]


def test_contract_requires_dirty_checkout_guard_before_checkout() -> None:
    deploy_text = _deploy_text(set(REQUIRED_RUNTIME_SERVICES)).replace(
        'git status --porcelain --untracked-files=normal\ngit checkout "${DEPLOY_BRANCH}"\n',
        'git checkout "${DEPLOY_BRANCH}"\ngit status --porcelain --untracked-files=normal\n',
    )

    errors = production_service_contract_errors(
        _compose_text(set(REQUIRED_RUNTIME_SERVICES)),
        deploy_text,
    )

    assert errors == ["deploy.sh does not reject a dirty checkout before changing branches"]


def test_contract_requires_read_only_data_preflight_before_schema_upgrade() -> None:
    deploy_text = _deploy_text(set(REQUIRED_RUNTIME_SERVICES)).replace(
        'echo "Running aggregate-only read-only release data preflight."\n'
        "verify_release_data_preflight\n",
        "",
    )

    errors = production_service_contract_errors(
        _compose_text(set(REQUIRED_RUNTIME_SERVICES)),
        deploy_text,
    )

    assert errors == [
        "deploy.sh does not run the read-only release data preflight before schema upgrade"
    ]


def test_contract_rejects_data_preflight_after_schema_upgrade() -> None:
    deploy_text = _deploy_text(set(REQUIRED_RUNTIME_SERVICES)).replace(
        'echo "Running aggregate-only read-only release data preflight."\n'
        "verify_release_data_preflight\n"
        "run_alembic upgrade head\n",
        "run_alembic upgrade head\n"
        'echo "Running aggregate-only read-only release data preflight."\n'
        "verify_release_data_preflight\n",
    )

    errors = production_service_contract_errors(
        _compose_text(set(REQUIRED_RUNTIME_SERVICES)),
        deploy_text,
    )

    assert errors == [
        "deploy.sh does not run the read-only release data preflight before schema upgrade"
    ]


def test_container_contract_accepts_pinned_runtime_and_blocking_image_scans() -> None:
    assert (
        production_container_contract_errors(
            _production_compose_text(),
            _python_dockerfile_text(),
            _python_dockerfile_text(),
            _frontend_dockerfile_text(),
            _nginx_dockerfile_text(),
            _workflow_text(),
        )
        == []
    )


def test_container_contract_accepts_hardened_redis_build() -> None:
    compose_text = _production_compose_text().replace(
        f"    image: {REDIS_IMAGE}\n",
        "    build:\n      dockerfile: ops/redis/Dockerfile\n",
    )
    workflow_text = _workflow_text().replace(
        REDIS_IMAGE, "lorevia-redis-security:${{ github.sha }}"
    )

    assert (
        production_container_contract_errors(
            compose_text,
            _python_dockerfile_text(),
            _python_dockerfile_text(),
            _frontend_dockerfile_text(),
            _nginx_dockerfile_text(),
            workflow_text,
            redis_dockerfile_text=f"FROM {REDIS_IMAGE}\nRUN apk upgrade --no-cache\n",
        )
        == []
    )


def test_container_contract_rejects_unpinned_hardened_redis_build() -> None:
    compose_text = _production_compose_text().replace(
        f"    image: {REDIS_IMAGE}\n",
        "    build:\n      dockerfile: ops/redis/Dockerfile\n",
    )
    workflow_text = _workflow_text().replace(
        REDIS_IMAGE, "lorevia-redis-security:${{ github.sha }}"
    )

    errors = production_container_contract_errors(
        compose_text,
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        workflow_text,
        redis_dockerfile_text="FROM redis:7-alpine\nRUN apk upgrade --no-cache\n",
    )

    assert "production Compose does not pin the supported Redis image digest" in errors
    assert "CI production-image vulnerability gate is incomplete: Redis image" in errors


def test_container_contract_requires_disk_backed_export_spool() -> None:
    compose_text = (
        _production_compose_text()
        .replace(
            '      MANUSCRIPT_EXPORT_SPOOL_DIRECTORY: "/var/lib/lorevia-export-spool"\n',
            "",
        )
        .replace("      - export_spool:/var/lib/lorevia-export-spool\n", "")
        .replace(
            "    healthcheck: tempfile.TemporaryFile MANUSCRIPT_EXPORT_SPOOL_DIRECTORY\n",
            "",
        )
    )
    worker_dockerfile = _python_dockerfile_text().replace(
        "RUN mkdir -p /app/storage /var/lib/lorevia-export-spool && "
        "chown -R app:app /app /var/lib/lorevia-export-spool\n",
        "",
    )

    errors = production_container_contract_errors(
        compose_text,
        _python_dockerfile_text(),
        worker_dockerfile,
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        _workflow_text(),
    )

    assert errors == [
        "backend worker image does not provision the disk-backed export spool",
        "production export spool contract is incomplete: maintenance spool directory, "
        "maintenance disk volume, maintenance spool health probe",
    ]


def test_container_contract_requires_authenticated_edge_secret_handoff() -> None:
    compose_text = _production_compose_text().replace(
        "      EDGE_PROXY_SECRET: ${EDGE_PROXY_SECRET:?EDGE_PROXY_SECRET is required}\n",
        "",
        2,
    )

    errors = production_container_contract_errors(
        compose_text,
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        _workflow_text(),
    )

    assert errors == [
        "production edge-proxy authentication is incomplete: required Nginx and API "
        "environment handoff"
    ]


def test_container_contract_requires_nginx_edge_configuration_renderer() -> None:
    nginx_dockerfile = _nginx_dockerfile_text().replace(
        "COPY ops/nginx/start.sh /usr/local/bin/lorevia-nginx-start\n",
        "",
    )

    errors = production_container_contract_errors(
        _production_compose_text(),
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        nginx_dockerfile,
        _workflow_text(),
    )

    assert errors == ["Nginx image does not render its authenticated edge configuration"]


def test_nginx_edge_start_contract_accepts_hardened_renderer() -> None:
    assert nginx_edge_start_contract_errors(_nginx_start_text()) == []


def test_nginx_edge_start_contract_requires_private_output_and_environment_cleanup() -> None:
    start_text = (
        _nginx_start_text()
        .replace("umask 077\n", "")
        .replace("unset edge_proxy_secret EDGE_PROXY_SECRET\n", "")
    )

    assert nginx_edge_start_contract_errors(start_text) == [
        "Nginx edge-proxy renderer is incomplete: owner-only rendered configuration, "
        "runtime environment cleanup"
    ]


def test_container_contract_rejects_end_of_life_node_image() -> None:
    errors = production_container_contract_errors(
        _production_compose_text(),
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text("node:20-alpine"),
        _nginx_dockerfile_text(),
        _workflow_text(),
    )

    assert errors == [
        "frontend/Dockerfile must use the pinned supported Node.js image for every stage",
        "frontend runtime does not install current Alpine security fixes",
        "frontend runtime does not remove unused package-manager paths: "
        "/opt/yarn-v1.22.22, /usr/local/lib/node_modules/corepack, "
        "/usr/local/lib/node_modules/npm, /usr/local/bin/npm, /usr/local/bin/npx",
    ]


def test_container_contract_requires_scan_gate_before_image_publish() -> None:
    errors = production_container_contract_errors(
        _production_compose_text(),
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        _workflow_text(gate_push=False),
    )

    assert errors == ["CI image publishing is not gated by production-image scans"]


def test_container_contract_rejects_root_runtime_users_and_privileged_nginx_ports() -> None:
    compose_text = (
        _production_compose_text()
        .replace('"80:8080"', '"80:80"')
        .replace('"443:8443"', '"443:443"')
        .replace("https://127.0.0.1:8443/nginx-health", "https://127.0.0.1/nginx-health")
    )

    errors = production_container_contract_errors(
        compose_text,
        _python_dockerfile_text().replace("USER 10001:10001\n", ""),
        _python_dockerfile_text().replace("USER 10001:10001\n", ""),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text().replace("USER 101:101\n", ""),
        _workflow_text(),
    )

    assert errors == [
        "backend API image does not declare its non-root app user",
        "backend worker image does not declare its non-root app user",
        "Nginx image does not declare its non-root runtime user",
        "production Compose does not map public ports to unprivileged Nginx ports",
        "production Nginx health check does not use its unprivileged TLS port",
    ]


def test_container_contract_rejects_root_redis_and_missing_runtime_hardening() -> None:
    compose_text = (
        _production_compose_text()
        .replace('    user: "999:1000"\n', "")
        .replace("  read_only: true\n", "  read_only: false\n")
    )

    errors = production_container_contract_errors(
        compose_text,
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        _workflow_text(),
    )

    assert errors == [
        "production Redis does not declare its non-root runtime user",
        "production runtime hardening is incomplete: read-only filesystem",
    ]


def test_container_contract_rejects_redis_password_process_arguments() -> None:
    compose_text = (
        _production_compose_text()
        .replace(
            "umask 077; printf config > /tmp/redis.conf; exec redis-server /tmp/redis.conf",
            'redis-server --requirepass "$${REDIS_PASSWORD}"',
        )
        .replace(
            'REDISCLI_AUTH="$${REDIS_PASSWORD}" redis-cli ping',
            'redis-cli -a "$${REDIS_PASSWORD}" ping',
        )
    )

    errors = production_container_contract_errors(
        compose_text,
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        _workflow_text(),
    )

    assert errors == [
        "production Redis does not keep its password out of process arguments",
        "production Redis health check exposes its password in process arguments",
    ]


def test_container_contract_rejects_runtime_tokenizer_downloads() -> None:
    api_dockerfile = _python_dockerfile_text().replace(
        "ENV DATA_GYM_CACHE_DIR=/opt/lorevia/tiktoken\n", ""
    )
    workflow_text = _workflow_text().replace("--network none --read-only", "", 2)

    errors = production_container_contract_errors(
        _production_compose_text(),
        api_dockerfile,
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        workflow_text,
    )

    assert errors == [
        "backend API image does not bake its tokenizer asset",
        "CI production-image vulnerability gate is incomplete: offline hardened tokenizer probes",
    ]


def test_container_contract_requires_blocking_configuration_scan() -> None:
    workflow_text = _workflow_text().replace("scan-type: 'config'", "scan-type: 'fs'", 1)
    workflow_text = workflow_text.replace("scanners: 'misconfig'", "scanners: 'vuln'", 1)

    errors = production_container_contract_errors(
        _production_compose_text(),
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        workflow_text,
    )

    assert errors == [
        "CI container-configuration gate is incomplete: configuration scan, "
        "misconfiguration scanner"
    ]


def test_container_contract_rejects_unpatched_or_floating_support_images() -> None:
    errors = production_container_contract_errors(
        _production_compose_text()
        .replace("dockerfile: ops/nginx/Dockerfile", "image: nginx:stable-alpine")
        .replace(REDIS_IMAGE, "redis:7-alpine"),
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text().replace("RUN apk upgrade --no-cache\n", ""),
        _workflow_text(),
    )

    assert errors == [
        "Nginx runtime does not install current Alpine security fixes",
        "production Compose does not build the security-patched Nginx image",
        "production Compose does not pin the supported Redis image digest",
    ]


def test_container_contract_requires_fixed_libexpat_version() -> None:
    nginx_dockerfile = _nginx_dockerfile_text().replace(
        NGINX_LIBEXPAT_REQUIREMENT,
        "libexpat",
    )

    errors = production_container_contract_errors(
        _production_compose_text(),
        _python_dockerfile_text(),
        _python_dockerfile_text(),
        _frontend_dockerfile_text(),
        nginx_dockerfile,
        _workflow_text(),
    )

    assert errors == ["Nginx runtime does not require the fixed libexpat version"]


def test_container_contract_rejects_floating_python_images() -> None:
    errors = production_container_contract_errors(
        _production_compose_text(),
        _python_dockerfile_text("python:3.12-slim"),
        _python_dockerfile_text("python:3.12-slim"),
        _frontend_dockerfile_text(),
        _nginx_dockerfile_text(),
        _workflow_text(),
    )

    assert errors == [
        "backend/Dockerfile.api does not use the pinned Python image",
        "backend/Dockerfile.worker does not use the pinned Python image",
    ]
