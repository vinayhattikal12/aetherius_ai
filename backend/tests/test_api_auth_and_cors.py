import pytest
import os
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.security import LAUNCH_TOKEN


@pytest.mark.asyncio
async def test_health_check_unauthenticated():
    """Verify health endpoint is openly accessible for diagnostic checks."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "online"


@pytest.mark.asyncio
async def test_disallowed_cross_origin_rejected():
    """Verify requests originating from unauthorized external web domains are blocked with 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = {"Origin": "https://malicious-tracker-site.com"}
        response = await ac.get("/api/v1/diagnostics/last-requests", headers=headers)
        assert response.status_code == 403
        assert "forbidden" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_allowed_origin_with_token_succeeds():
    """Verify requests with allowed desktop/web origin and valid token succeed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = {
            "Origin": "http://localhost:5173",
            "Authorization": f"Bearer {LAUNCH_TOKEN}"
        }
        response = await ac.get("/api/v1/diagnostics/last-requests", headers=headers)
        # Should be 200 OK
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_strict_token_auth_mode():
    """Verify unauthorized requests are rejected with 401 when AETHERIUS_REQUIRE_AUTH is active."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AETHERIUS_REQUIRE_AUTH", "true")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {
                "Origin": "http://localhost:5173",
                "Authorization": "Bearer invalid-wrong-token"
            }
            response = await ac.get("/api/v1/diagnostics/last-requests", headers=headers)
            assert response.status_code == 401
