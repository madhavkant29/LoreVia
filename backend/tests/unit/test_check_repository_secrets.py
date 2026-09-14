from types import SimpleNamespace

from scripts import check_repository_secrets
from scripts.check_repository_secrets import (
    SecretFinding,
    repository_candidate_paths,
    scan_text,
)


def test_scan_text_redacts_known_provider_credentials() -> None:
    text = (
        'OPENAI_API_KEY="sk-proj-abcdefghijklmnopqrstuvwxyz123456"\n'  # secret-scan: allow
        'AWS_ACCESS_KEY_ID="AKIAABCDEFGHIJKLMNOP"\n'  # secret-scan: allow
        "SERVICE_PASSWORD=correct-horse-battery-staple\n"
    )

    findings = scan_text(text, relative_path="deploy.conf")

    assert findings == [
        SecretFinding("deploy.conf", 1, "credential-assignment"),
        SecretFinding("deploy.conf", 1, "openai-api-key"),
        SecretFinding("deploy.conf", 2, "aws-access-key"),
        SecretFinding("deploy.conf", 3, "credential-assignment"),
    ]
    assert all("abcdefghijklmnopqrstuvwxyz" not in repr(finding) for finding in findings)


def test_scan_text_ignores_documented_placeholders_and_ci_test_values() -> None:
    text = (
        "PADDLE_API_KEY=pdl_live_or_sandbox_key_here\n"
        'JWT_SECRET: "test-secret-key-for-ci"\n'
        'OPENAI_API_KEY="${OPENAI_API_KEY}"\n'
    )

    assert scan_text(text, relative_path="README.md") == []


def test_scan_text_reports_private_keys_and_embedded_passwords_without_values() -> None:
    text = (
        "-----BEGIN PRIVATE KEY-----\n"  # secret-scan: allow
        "DATABASE_URL=postgresql://user:long-production-password@database.internal/app\n"  # secret-scan: allow
    )

    findings = scan_text(text, relative_path="deploy.conf")

    assert findings == [
        SecretFinding("deploy.conf", 1, "private-key"),
        SecretFinding("deploy.conf", 2, "credential-url"),
    ]
    rendered = "\n".join(f"{item.path}:{item.line} [{item.rule}]" for item in findings)
    assert "long-production-password" not in rendered


def test_repository_candidates_request_tracked_and_untracked_non_ignored_paths(
    tmp_path, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(stdout=b".gitignore\0pending.txt\0tracked.txt\0")

    monkeypatch.setattr(check_repository_secrets.subprocess, "run", fake_run)

    paths = {path.name for path in repository_candidate_paths(tmp_path)}

    assert paths == {".gitignore", "pending.txt", "tracked.txt"}
    assert captured["args"][-3:] == ["--cached", "--others", "--exclude-standard"]
    assert captured["kwargs"] == {"check": True, "capture_output": True}
