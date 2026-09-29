import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_knowledge_base_creation_and_search(async_client: AsyncClient):
    # 1. Create Knowledge Base
    kb_payload = {
        "name": "Engineering Handbook",
        "slug": "eng-handbook",
        "collection_type": "Company",
        "description": "Internal engineering standards and architecture.",
        "workspace_slug": "developer"
    }
    kb_res = await async_client.post("/api/v1/knowledge/", json=kb_payload)
    assert kb_res.status_code == 200
    kb_data = kb_res.json()
    assert kb_data["slug"] == "eng-handbook"

    # 2. Upload Document into Knowledge Base
    file_content = b"Aetherius Architecture Guidelines: All services must use PostgreSQL pgvector. SQLite fallback is strictly prohibited."
    files = {"file": ("architecture_guidelines.txt", file_content, "text/plain")}
    upload_res = await async_client.post("/api/v1/knowledge/eng-handbook/upload", files=files)
    assert upload_res.status_code == 200
    doc_data = upload_res.json()
    assert doc_data["filename"] == "architecture_guidelines.txt"
    assert doc_data["status"] == "ready"
    assert doc_data["chunk_count"] >= 1

    # 3. Perform Semantic Vector Search
    search_payload = {
        "query": "What database is required by Aetherius?",
        "knowledge_base_slugs": ["eng-handbook"],
        "top_k": 3
    }
    search_res = await async_client.post("/api/v1/knowledge/search", json=search_payload)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data["chunks"]) >= 1
    assert "PostgreSQL" in search_data["chunks"][0]["content"]
    assert len(search_data["sources"]) >= 1
