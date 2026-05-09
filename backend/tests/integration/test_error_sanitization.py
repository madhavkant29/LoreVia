import pytest


@pytest.mark.asyncio
async def test_missing_route_returns_generic_not_found(client):
    response = await client.get("/api/v1/this-route-does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found."}


@pytest.mark.asyncio
async def test_validation_error_returns_generic_message(client):
    response = await client.post("/api/v1/auth/register", json={})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request."}
