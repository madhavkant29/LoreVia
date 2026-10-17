import re

UNKNOWN_RELEASE_SHA = "unknown"
_RELEASE_SHA_PATTERN = re.compile(r"^[0-9a-f]{7,64}$")


def normalize_release_sha(value: str | None) -> str:
    """Return a safe lowercase Git revision or an explicit unknown marker."""
    normalized = str(value or "").strip().lower()
    if not _RELEASE_SHA_PATTERN.fullmatch(normalized):
        return UNKNOWN_RELEASE_SHA
    return normalized
