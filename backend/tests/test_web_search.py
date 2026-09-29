import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_web_search_endpoint(async_client: AsyncClient):
    payload = {
        "query": "PostgreSQL pgvector latest release",
        "max_results": 3
    }
    response = await async_client.post("/api/v1/web-search/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["query"]
    assert len(data["results"]) >= 1
    assert "url" in data["results"][0]
    assert "snippet" in data["results"][0]
