import pytest
from httpx import AsyncClient
from backend.app.services.memory_service import MemoryService
from backend.app.services.workspace_service import WorkspaceService


@pytest.mark.asyncio
async def test_memory_creation_search_and_extraction(async_client: AsyncClient, test_db):
    # 0. Clean slate
    await MemoryService.clear_memories(test_db)

    # 1. Create Memory
    mem_payload = {
        "workspace_slug": "developer",
        "memory_type": "preference",
        "content": "I prefer TypeScript and strict linting rules for all frontend components.",
        "confidence_score": 0.95,
        "importance_weight": 4.0
    }
    create_res = await async_client.post("/api/v1/memory/", json=mem_payload)
    assert create_res.status_code == 200
    mem_data = create_res.json()
    assert mem_data["workspace_slug"] == "developer"
    assert mem_data["memory_type"] == "preference"
    assert "TypeScript" in mem_data["content"]
    memory_id = mem_data["id"]

    # 2. List Memories
    list_res = await async_client.get("/api/v1/memory/?workspace_slug=developer")
    assert list_res.status_code == 200
    memories = list_res.json()
    assert len(memories) >= 1
    assert any(m["id"] == memory_id for m in memories)

    # 3. Update Memory
    update_res = await async_client.put(f"/api/v1/memory/{memory_id}", json={
        "content": "I prefer TypeScript and Tailwind CSS for all UI development.",
        "importance_weight": 5.0
    })
    assert update_res.status_code == 200
    assert "Tailwind CSS" in update_res.json()["content"]

    # 4. Perform Semantic Vector Search on Memory
    search_payload = {
        "query": "What language does the developer prefer for frontend?",
        "workspace_slug": "developer",
        "top_k": 3,
        "min_similarity": 0.05
    }
    search_res = await async_client.post("/api/v1/memory/search", json=search_payload)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data["memories"]) >= 1
    assert "Tailwind" in search_data["memories"][0]["content"]

    # 5. Test Automatic Heuristic Extraction
    extracted = await MemoryService.extract_and_store_from_text(
        db=test_db,
        text="My name is Vinay. I work as a Lead Architect at ERBrains. Please always format as concise bullet points.",
        workspace_slug="general"
    )
    assert len(extracted) >= 2
    contents = [e.content for e in extracted]
    assert any("Vinay" in c for c in contents)
    assert any("concise" in c.lower() for c in contents)

    # 6. Test Explicit Memory Commands
    rem_resp = await MemoryService.handle_explicit_memory_commands(
        db=test_db,
        text="Remember that we use PostgreSQL pgvector on port 5432.",
        workspace_slug="developer"
    )
    assert rem_resp is not None
    assert "Memory Updated" in rem_resp

    query_resp = await MemoryService.handle_explicit_memory_commands(
        db=test_db,
        text="What do you remember about me?",
        workspace_slug="developer"
    )
    assert query_resp is not None
    assert "saved to memory" in query_resp

    forget_resp = await MemoryService.handle_explicit_memory_commands(
        db=test_db,
        text="Forget that we use PostgreSQL pgvector",
        workspace_slug="developer"
    )
    assert forget_resp is not None
    assert "Memory Cleared" in forget_resp

    # 7. Delete Memory
    del_res = await async_client.delete(f"/api/v1/memory/{memory_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_workspace_cognitive_blueprints(test_db):
    await WorkspaceService.seed_default_workspaces(test_db)
    workspaces = await WorkspaceService.get_all(test_db)
    slug_map = {w.slug: w for w in workspaces}

    assert "student" in slug_map
    assert "Feynman" in slug_map["student"].instructions
    assert "finance" in slug_map
    assert "GAAP" in slug_map["finance"].instructions
    assert "hr" in slug_map
    assert "STAR" in slug_map["hr"].instructions
    assert "developer" in slug_map
    assert "Architecture" in slug_map["developer"].instructions

