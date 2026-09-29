import pytest
from httpx import AsyncClient
from backend.app.services.query_intelligence_service import QueryIntelligenceService
from backend.app.services.context_engine import ContextEngine


@pytest.mark.asyncio
async def test_continuous_anaphora_and_constraint_accumulation():
    # Turn 1
    t1 = "Find the latest AI coding tools."
    history = []
    a1 = await QueryIntelligenceService.analyze_query(t1, history)
    assert a1.canonical_prompt == "Find the latest AI coding tools."

    # Turn 2: Qualifier
    history.append({"role": "user", "content": t1})
    history.append({"role": "assistant", "content": "Here are top AI coding tools: Qwen 2.5 Coder, Continue.dev, and Cursor."})
    t2 = "Only open source."
    a2 = await QueryIntelligenceService.analyze_query(t2, history)
    assert "open source" in a2.canonical_prompt.lower()
    assert a2.extracted_constraints.get("license") == "open_source"

    # Turn 3: Platform restriction
    history.append({"role": "user", "content": t2})
    history.append({"role": "assistant", "content": "The open-source options are Qwen 2.5 Coder and Continue.dev."})
    t3 = "Which support Windows?"
    a3 = await QueryIntelligenceService.analyze_query(t3, history)
    assert "windows" in a3.canonical_prompt.lower()
    assert a3.extracted_constraints.get("platform") == "windows"
    assert a3.extracted_constraints.get("license") == "open_source"

    # Turn 4: Comparison
    history.append({"role": "user", "content": t3})
    history.append({"role": "assistant", "content": "Both Qwen 2.5 Coder and Continue.dev fully support Windows."})
    t4 = "Compare them."
    a4 = await QueryIntelligenceService.analyze_query(t4, history)
    assert "comparison" in a4.composite_intents or a4.primary_intent == "comparison"


@pytest.mark.asyncio
async def test_continuous_chat_session_api_flow(async_client: AsyncClient):
    # 1. Create session
    conv_res = await async_client.post("/api/v1/conversations/", json={
        "workspace_slug": "general",
        "title": "Continuous Multi-Turn Test",
        "model_name": "llama3.2:3b"
    })
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # Turn 1
    res1 = await async_client.post("/api/v1/chat/completions", json={
        "conversation_id": conv_id,
        "workspace_slug": "general",
        "model_name": "llama3.2:3b",
        "message": "Research scalable vector databases for AI operating systems.",
        "enable_web_search": False,
        "enable_knowledge_rag": False
    })
    assert res1.status_code == 200
    d1 = res1.json()
    assert len(d1["assistant_message"]["content"]) > 0

    # Turn 2: Follow-up constraint
    res2 = await async_client.post("/api/v1/chat/completions", json={
        "conversation_id": conv_id,
        "workspace_slug": "general",
        "model_name": "llama3.2:3b",
        "message": "Only open source with PostgreSQL compatibility.",
        "enable_web_search": False,
        "enable_knowledge_rag": False
    })
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["assistant_message"]["extra_metadata"]["constraints_applied"].get("license") == "open_source"

    # Turn 3: Follow-up comparison
    res3 = await async_client.post("/api/v1/chat/completions", json={
        "conversation_id": conv_id,
        "workspace_slug": "general",
        "model_name": "llama3.2:3b",
        "message": "Compare them in a structured table.",
        "enable_web_search": False,
        "enable_knowledge_rag": False
    })
    assert res3.status_code == 200
    d3 = res3.json()
    assert len(d3["assistant_message"]["content"]) > 0

    # Check database persistence
    get_conv = await async_client.get(f"/api/v1/conversations/{conv_id}")
    assert get_conv.status_code == 200
    c_data = get_conv.json()
    assert len(c_data["messages"]) == 6  # 3 user turns + 3 assistant responses
