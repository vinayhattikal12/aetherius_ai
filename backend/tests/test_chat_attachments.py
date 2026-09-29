import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_file_upload_document(async_client: AsyncClient):
    # 1. Upload a text/markdown document attachment
    file_content = b"# Production Deployment Guide\n1. Ensure PostgreSQL is running.\n2. Configure GPU accelerators."
    files = {
        "file": ("deployment_guide.md", io.BytesIO(file_content), "text/markdown")
    }

    res = await async_client.post("/api/v1/chat/upload", files=files)
    assert res.status_code == 200
    data = res.json()

    assert data["filename"] == "deployment_guide.md"
    assert data["is_image"] is False
    assert data["file_size_bytes"] == len(file_content)
    assert "Production Deployment Guide" in data["extracted_text"]
    assert data["storage_path"] is not None


@pytest.mark.asyncio
async def test_chat_file_upload_image(async_client: AsyncClient):
    # 1. Upload a dummy PNG image attachment
    png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    files = {
        "file": ("system_diagram.png", io.BytesIO(png_header), "image/png")
    }

    res = await async_client.post("/api/v1/chat/upload", files=files)
    assert res.status_code == 200
    data = res.json()

    assert data["filename"] == "system_diagram.png"
    assert data["is_image"] is True
    assert data["preview_url"] is not None
    assert "data:image/png;base64," in data["preview_url"]


@pytest.mark.asyncio
async def test_chat_completion_with_attachments_and_persistence(async_client: AsyncClient):
    # 1. Upload Document
    doc_content = b"Aetherius Cluster Configuration:\n- Worker nodes: 8\n- Primary database: PostgreSQL 16 pgvector\n- Max concurrency: 128"
    doc_res = await async_client.post(
        "/api/v1/chat/upload",
        files={"file": ("cluster_config.txt", io.BytesIO(doc_content), "text/plain")}
    )
    assert doc_res.status_code == 200
    doc_attachment = doc_res.json()

    # 2. Upload Image
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    img_res = await async_client.post(
        "/api/v1/chat/upload",
        files={"file": ("architecture_mockup.png", io.BytesIO(png_bytes), "image/png")}
    )
    assert img_res.status_code == 200
    img_attachment = img_res.json()

    # 3. Create conversation and send completion with attachments
    chat_payload = {
        "workspace_slug": "developer",
        "model_name": "qwen2.5-coder:7b",
        "message": "Analyze the attached cluster configuration and architecture mockup.",
        "attachments": [doc_attachment, img_attachment],
        "enable_web_search": False,
        "enable_knowledge_rag": False
    }

    res = await async_client.post("/api/v1/chat/completions", json=chat_payload)
    assert res.status_code == 200
    chat_data = res.json()

    assert chat_data["conversation_id"] is not None
    assert len(chat_data["user_message"]["attachments"]) == 2
    assert len(chat_data["citations"]) >= 2

    # 4. Verify conversation persistence in PostgreSQL
    conv_id = chat_data["conversation_id"]
    get_res = await async_client.get(f"/api/v1/conversations/{conv_id}")
    assert get_res.status_code == 200
    conv_data = get_res.json()

    assert len(conv_data["messages"]) == 2
    user_msg = conv_data["messages"][0]
    assert user_msg["role"] == "user"
    assert len(user_msg["attachments"]) == 2
    assert user_msg["attachments"][0]["filename"] == "cluster_config.txt"
    assert user_msg["attachments"][1]["filename"] == "architecture_mockup.png"
