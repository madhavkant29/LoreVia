from __future__ import annotations

from app.core.config import settings


async def test_support_api_serves_config_guided_answers_and_cases(
    client, auth_headers, monkeypatch
):
    monkeypatch.setattr(
        settings, "COMMUNITY_DISCORD_URL", "https://discord.gg/mjuWtTWSh", raising=False
    )
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "", raising=False)

    config_response = await client.get("/api/v1/support/config", headers=auth_headers)
    assert config_response.status_code == 200
    config = config_response.json()
    assert config["assistant_enabled"] is True
    assert config["community_url"] == "https://discord.gg/mjuWtTWSh"
    assert config["corpus_version"]

    guides_response = await client.get("/api/v1/support/guides", headers=auth_headers)
    assert guides_response.status_code == 200
    assert any("save" in guide["title"].lower() for guide in guides_response.json()["guides"])

    chat_response = await client.post(
        "/api/v1/support/chat",
        headers=auth_headers,
        json={
            "message": "I pasted a chapter and the save did not work. What should I try?",
            "context": {
                "route": "/book-1/manuscript",
                "workspace_shell": "author",
                "account_tier": "author",
                "device_class": "desktop",
                "save_state": "error",
                "error_code": "version_conflict",
            },
        },
    )
    assert chat_response.status_code == 200
    answer = chat_response.json()
    assert answer["declined"] is False
    assert answer["sources"]
    assert any(
        "chapter" in source["title"].lower() or "save" in source["title"].lower()
        for source in answer["sources"]
    )

    case_response = await client.post(
        "/api/v1/support/incidents",
        headers=auth_headers,
        json={
            "confirmed": True,
            "category": "chapter_save",
            "feature": "manuscript",
            "summary": "I pasted a chapter and Save failed.",
            "context": {
                "route": "/book-1/manuscript",
                "workspace_shell": "author",
                "account_tier": "author",
                "device_class": "desktop",
                "save_state": "error",
            },
        },
    )
    assert case_response.status_code == 200
    case = case_response.json()
    assert case["reference"].startswith("LV-")
    assert case["category"] == "chapter_save"

    fetched_case = await client.get(f"/api/v1/support/incidents/{case['id']}", headers=auth_headers)
    assert fetched_case.status_code == 200
    assert fetched_case.json()["reference"] == case["reference"]
