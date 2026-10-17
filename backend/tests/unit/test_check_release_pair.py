from scripts.check_release_pair import release_pair_errors


def test_release_pair_accepts_matching_full_git_shas() -> None:
    release_sha = "a" * 40

    assert (
        release_pair_errors(
            {"app": "LoreVia frontend", "release_sha": release_sha},
            {"app": "LoreVia", "release_sha": release_sha},
        )
        == []
    )


def test_release_pair_rejects_unknown_releases() -> None:
    assert release_pair_errors(
        {"release_sha": "unknown"},
        {"release_sha": "not-a-sha"},
    ) == [
        "Frontend release SHA is missing or invalid",
        "API release SHA is missing or invalid",
    ]


def test_release_pair_reports_cross_host_version_skew() -> None:
    assert release_pair_errors(
        {"release_sha": "a" * 40},
        {"release_sha": "b" * 40},
    ) == [f"Release mismatch: frontend={'a' * 40} api={'b' * 40}"]


def test_release_pair_rejects_non_object_payloads() -> None:
    assert release_pair_errors([], "not-json") == [
        "Frontend release endpoint did not return a JSON object",
        "API health endpoint did not return a JSON object",
    ]
