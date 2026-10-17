from app.utils.release_utils import UNKNOWN_RELEASE_SHA, normalize_release_sha


def test_normalize_release_sha_accepts_git_revisions() -> None:
    assert normalize_release_sha(" ABCDEF1234567 ") == "abcdef1234567"
    assert normalize_release_sha("a" * 40) == "a" * 40


def test_normalize_release_sha_rejects_missing_or_untrusted_values() -> None:
    assert normalize_release_sha(None) == UNKNOWN_RELEASE_SHA
    assert normalize_release_sha("unknown") == UNKNOWN_RELEASE_SHA
    assert normalize_release_sha("abc123\r\nX-Injected: true") == UNKNOWN_RELEASE_SHA
    assert normalize_release_sha("a" * 65) == UNKNOWN_RELEASE_SHA
