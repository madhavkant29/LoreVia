"""Fail closed when tracked or pending repository files contain likely credentials.

The scanner intentionally prints only a rule name and source location. It never
echoes the matched value, which keeps CI logs useful without turning them into a
second credential exposure.

Run from the repository root:
    python backend/scripts/check_repository_secrets.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_TEXT_FILE_BYTES = 5 * 1024 * 1024
TEXT_SUFFIXES = {
    "",
    ".cjs",
    ".conf",
    ".css",
    ".csv",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mdx",
    ".mjs",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
UNQUOTED_SECRET_SUFFIXES = {
    ".conf",
    ".env",
    ".example",
    ".ini",
    ".md",
    ".mdx",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class SecretRule:
    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True, order=True)
class SecretFinding:
    path: str
    line: int
    rule: str


def _rule(name: str, pattern: str) -> SecretRule:
    return SecretRule(name=name, pattern=re.compile(pattern))


HIGH_CONFIDENCE_RULES = (
    _rule(
        "private-key",
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    ),
    _rule(
        "openai-api-key",
        r"(?<![A-Za-z0-9])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}",
    ),
    _rule("aws-access-key", r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
    _rule(
        "github-token",
        r"(?<![A-Za-z0-9])(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})",
    ),
    _rule("google-api-key", r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{35}(?![A-Za-z0-9_-])"),
    _rule("slack-token", r"(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{20,}"),
    _rule("stripe-live-key", r"(?<![A-Za-z0-9])(?:sk|rk)_live_[A-Za-z0-9]{16,}"),
    _rule("resend-api-key", r"(?<![A-Za-z0-9])re_[A-Za-z0-9]{20,}"),
    _rule(
        "paddle-api-key",
        r"(?<![A-Za-z0-9])pdl_(?:live|sandbox)_[A-Za-z0-9_-]{16,}",
    ),
)

CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?ix)"
    r"(?:^|[,{]\s*)"
    r"[\"']?("
    r"(?:[a-z0-9_.-]*(?:api[_-]?key|secret|password|access[_-]?token|refresh[_-]?token)"
    r"[a-z0-9_.-]*))"
    r"[\"']?\s*[:=]\s*[\"']([^\"'\r\n]{16,})[\"']"
)
UNQUOTED_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?ix)^\s*[\"']?"
    r"((?:[a-z0-9_.-]*(?:api[_-]?key|secret|password|access[_-]?token|refresh[_-]?token)"
    r"[a-z0-9_.-]*))"
    r"[\"']?\s*[:=]\s*([^\s#\"']{16,})\s*(?:\#.*)?$"
)
CREDENTIAL_URL = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s:/]+:([^\s/@]{12,})@")
PLACEHOLDER_MARKERS = (
    "${",
    "{{",
    "<secret",
    "<token",
    "<password",
    "change-me",
    "changeme",
    "dummy",
    "example",
    "fake",
    "key-here",
    "key_here",
    "not-a-real",
    "placeholder",
    "redacted",
    "replace",
    "replace-me",
    "replace_me",
    "secret_here",
    "test-",
    "test_",
    "your-",
    "your_",
)


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().casefold()
    if any(marker in normalized for marker in PLACEHOLDER_MARKERS):
        return True
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    return len(set(compact)) < 6


def _credential_assignment_is_secret(key: str, value: str, *, is_test_path: bool) -> bool:
    return (
        not is_test_path
        and not key.casefold().endswith(("_cookie_name", "_field_name", "_header_name", "_name"))
        and not _looks_like_placeholder(value)
    )


def scan_text(text: str, *, relative_path: str) -> list[SecretFinding]:
    """Return redacted findings for one decoded repository file."""
    findings: set[SecretFinding] = set()
    normalized_relative_path = relative_path.replace("\\", "/").casefold()
    normalized_path = f"/{normalized_relative_path}"
    is_test_path = "/tests/" in normalized_path
    allow_unquoted_assignment = Path(normalized_relative_path).suffix in UNQUOTED_SECRET_SUFFIXES
    for line_number, line in enumerate(text.splitlines(), start=1):
        if "secret-scan: allow" in line.casefold():
            continue
        for rule in HIGH_CONFIDENCE_RULES:
            for match in rule.pattern.finditer(line):
                if rule.name != "private-key" and _looks_like_placeholder(match.group(0)):
                    continue
                findings.add(SecretFinding(relative_path, line_number, rule.name))

        for match in CREDENTIAL_ASSIGNMENT.finditer(line):
            if _credential_assignment_is_secret(
                match.group(1), match.group(2), is_test_path=is_test_path
            ):
                findings.add(SecretFinding(relative_path, line_number, "credential-assignment"))

        match = UNQUOTED_CREDENTIAL_ASSIGNMENT.match(line) if allow_unquoted_assignment else None
        if match and _credential_assignment_is_secret(
            match.group(1), match.group(2), is_test_path=is_test_path
        ):
            if not CREDENTIAL_ASSIGNMENT.search(line):
                findings.add(SecretFinding(relative_path, line_number, "credential-assignment"))

        for match in CREDENTIAL_URL.finditer(line):
            if not is_test_path and not _looks_like_placeholder(match.group(1)):
                findings.add(SecretFinding(relative_path, line_number, "credential-url"))
    return sorted(findings)


def repository_candidate_paths(repo_root: Path = REPO_ROOT) -> list[Path]:
    """Return tracked and untracked, non-ignored paths in the release candidate."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        check=True,
        capture_output=True,
    )
    return [repo_root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def scan_repository(repo_root: Path = REPO_ROOT) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for path in repository_candidate_paths(repo_root):
        if not path.is_file() or path.suffix.casefold() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_TEXT_FILE_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(repo_root).as_posix()
        findings.extend(scan_text(text, relative_path=relative))
    return sorted(set(findings))


def main() -> int:
    findings = scan_repository()
    if findings:
        print("Potential repository credentials detected (values redacted):", file=sys.stderr)
        for finding in findings:
            print(f"  {finding.path}:{finding.line} [{finding.rule}]", file=sys.stderr)
        return 1
    print("Repository credential scan passed (tracked and pending non-ignored files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
