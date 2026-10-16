from __future__ import annotations

import pytest

from scripts import verify_public_asset_origin


def test_origin_contract_accepts_bounded_public_cache_and_denied_private_paths():
    errors = verify_public_asset_origin.public_asset_origin_errors(
        public_probe=verify_public_asset_origin.OriginProbe(
            200,
            content_type="text/plain; charset=utf-8",
            cache_control="public, max-age=60, must-revalidate",
        ),
        private_probe=verify_public_asset_origin.OriginProbe(403),
        listing_probe=verify_public_asset_origin.OriginProbe(404),
        maximum_cache_age=60,
    )

    assert errors == []


def test_origin_contract_rejects_private_exposure_listing_and_long_cache():
    errors = verify_public_asset_origin.public_asset_origin_errors(
        public_probe=verify_public_asset_origin.OriginProbe(
            200,
            content_type="application/octet-stream",
            cache_control="public, max-age=3600",
        ),
        private_probe=verify_public_asset_origin.OriginProbe(200),
        listing_probe=verify_public_asset_origin.OriginProbe(200),
        maximum_cache_age=60,
    )

    assert errors == [
        "public probe is not served as text/plain",
        "public probe max-age 3600s exceeds the allowed 60s",
        "public probe is missing Cache-Control must-revalidate",
        "known private object returned HTTP 200, expected 401/403/404",
        "public prefix listing returned HTTP 200, expected 401/403/404",
    ]


@pytest.mark.parametrize(
    ("value", "public"),
    [
        ("chapters/private.json", True),
        ("public-assets/book/chapter/v1.txt", False),
        ("../private", False),
        ("", True),
    ],
)
def test_probe_keys_enforce_public_private_boundary(value, public):
    with pytest.raises(ValueError):
        verify_public_asset_origin.validate_probe_key(value, public=public)


def test_origin_url_requires_credential_free_https_and_quotes_key():
    assert (
        verify_public_asset_origin.origin_url(
            "https://assets.getlorevia.com/root/",
            "public-assets/book/chapter name/v1.txt",
        )
        == "https://assets.getlorevia.com/root/public-assets/book/chapter%20name/v1.txt"
    )

    with pytest.raises(ValueError):
        verify_public_asset_origin.validate_base_url("http://assets.getlorevia.com")
    with pytest.raises(ValueError):
        verify_public_asset_origin.validate_base_url("https://user:secret@example.com")
