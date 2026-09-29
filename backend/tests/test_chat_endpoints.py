import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_completions_with_rag_and_persistence(async_client: AsyncClient):
    # 1. Create a conversation
    conv_res = await async_client.post("/api/v1/conversations/", json={
        "workspace_slug": "developer",
        "title": "FastAPI Auth Discussion",
        "model_name": "llama3.2:3b"
    })
    assert conv_res.status_code == 200
    conv_data = conv_res.json()
    conv_id = conv_data["id"]

    # 2. Send Chat Completion Request
    chat_payload = {
        "conversation_id": conv_id,
        "workspace_slug": "developer",
        "model_name": "qwen2.5-coder:7b",
        "message": "Explain how authentication state is persisted in Aetherius.",
        "enable_web_search": False,
        "enable_knowledge_rag": True
    }
    chat_res = await async_client.post("/api/v1/chat/completions", json=chat_payload)
    assert chat_res.status_code == 200
    resp_data = chat_res.json()
    assert resp_data["conversation_id"] == conv_id
    assert resp_data["user_message"]["content"] == chat_payload["message"]
    assert len(resp_data["assistant_message"]["content"]) > 0

    # 3. Retrieve Conversation from PostgreSQL to verify messages persisted
    get_conv = await async_client.get(f"/api/v1/conversations/{conv_id}")
    assert get_conv.status_code == 200
    retrieved = get_conv.json()
    assert len(retrieved["messages"]) == 2
    assert retrieved["messages"][0]["role"] == "user"
    assert retrieved["messages"][1]["role"] == "assistant"
