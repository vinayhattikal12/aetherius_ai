import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.services.rag_service import RAGService
from backend.app.services.hardware_detector import HardwareDetector
from backend.app.schemas.knowledge import KnowledgeBaseCreate


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_time_sse_streaming_protocol(async_client: AsyncClient):
    """Validates real-time Server-Sent Events (SSE) token and metadata streaming protocol."""
    # 1. Create a conversation
    conv_res = await async_client.post("/api/v1/conversations/", json={
        "workspace_slug": "general",
        "title": "SSE Streaming Protocol Test",
        "model_name": "llama3.2:3b"
    })
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # 2. Call SSE streaming endpoint
    req_body = {
        "conversation_id": conv_id,
        "workspace_slug": "general",
        "model_name": "llama3.2:3b",
        "message": "Write a 2-sentence summary of modern operating systems.",
        "max_tokens": 100,
        "enable_web_search": False,
        "enable_knowledge_rag": False
    }

    async with async_client.stream("POST", "/api/v1/chat/stream", json=req_body) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = []
        token_count = 0
        has_init = False
        has_done = False

        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:].strip()
                if data_str:
                    event = json.loads(data_str)
                    events.append(event)
                    if event.get("type") == "init":
                        has_init = True
                        assert "conversation_id" in event
                        assert event["conversation_id"] == conv_id
                    elif event.get("type") == "token":
                        token_count += 1
                    elif event.get("type") == "done":
                        has_done = True
                        assert "content" in event
                        assert len(event["content"]) > 0

        assert has_init is True, "Stream must emit 'init' event first."
        assert has_done is True, "Stream must emit 'done' event at completion."
        assert token_count > 0, "Stream must emit incremental 'token' events."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pgvector_rag_ingestion_and_similarity_retrieval(test_db: AsyncSession):
    """Validates document ingestion, chunking, vector embeddings, and similarity retrieval in PostgreSQL."""
    # 1. Create Knowledge Base
    kb = await RAGService.create_or_get_knowledge_base(
        db=test_db,
        name="Architecture Knowledge Base",
        slug="arch-kb",
        collection_type="Engineering",
        workspace_slug="general",
        description="System architecture whitepapers and technical specs."
    )
    assert kb.id is not None

    # 2. Ingest Document
    sample_text = (
        "Aetherius AI utilizes an asynchronous microkernel architecture designed for zero-copy IPC. "
        "The storage subsystem relies on PostgreSQL with pgvector for high-dimensional vector search. "
        "Memory management partitions state into episodic, semantic, and working scopes."
    )
    doc = await RAGService.ingest_document(
        db=test_db,
        knowledge_base_id=kb.id,
        filename="system_architecture.txt",
        file_bytes=sample_text.encode("utf-8"),
        file_type="txt"
    )
    assert doc.status == "ready"
    assert doc.chunk_count >= 1

    # 3. Vector Similarity Search
    chunks = await RAGService.search_relevant_chunks(
        db=test_db,
        query="What database is used for vector search in Aetherius?",
        knowledge_base_slugs=["arch-kb"],
        top_k=2
    )
    assert len(chunks) > 0
    top_chunk, score = chunks[0]
    assert "PostgreSQL" in top_chunk.content or "pgvector" in top_chunk.content
    assert score > 0.0

    # 4. Citation Generation
    citations = RAGService.build_citations(chunks)
    assert len(citations) == len(chunks)
    assert citations[0].source_type == "document"
    assert citations[0].title == "system_architecture.txt"


@pytest.mark.asyncio
async def test_system_hardware_profile_and_telemetry():
    """Validates hardware capability detection and compute profile detection."""
    profile = HardwareDetector.get_hardware_profile()
    assert profile is not None
    assert profile.cpu.physical_cores > 0
    assert profile.ram.total_gb > 0
    assert profile.os is not None
    assert profile.compute_tier in ["Ultra", "High", "Medium", "Low", "Minimum"]
