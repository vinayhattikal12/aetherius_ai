import pytest
from unittest.mock import patch, MagicMock
from backend.app.services.context_engine import ContextEngine
from backend.app.services.providers.ollama_provider import OllamaProvider
from backend.app.models.knowledge import DocumentChunk


def test_context_engine_deterministic_trimming_preserves_system_prompt():
    """
    Verify that an oversized prompt payload exceeding model_context_limit is trimmed
    in order: oldest history -> lowest scoring RAG -> web, while strictly preserving system prompt.
    """
    system_instruction = "CRITICAL_SYSTEM_DIRECTIVE_THAT_MUST_NEVER_BE_TRIMMED"
    
    # 20 turns of chat history (~2,000 tokens)
    oversized_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}: " + ("x " * 100)}
        for i in range(20)
    ]
    
    # Low-scoring and high-scoring RAG chunks
    chunk_low = DocumentChunk(
        knowledge_base_id="kb-1",
        content="Low scoring content " * 60,
        chunk_metadata={"filename": "low.txt"}
    )
    chunk_high = DocumentChunk(
        knowledge_base_id="kb-1",
        content="High scoring prioritized content summary.",
        chunk_metadata={"filename": "high.txt"}
    )
    rag_chunks = [(chunk_low, 0.2), (chunk_high, 0.95)]
    
    # Budget limit = 2048 tokens total, with 1024 output reserved
    assembled = ContextEngine.assemble_context(
        model_context_limit=2048,
        max_output_tokens=1024,
        system_instruction=system_instruction,
        rag_chunks=rag_chunks,
        chat_history=oversized_history,
        current_user_message="Current test question"
    )
    
    # 1. System prompt must contain the critical directive intact
    assert system_instruction in assembled["system_prompt"]
    
    # 2. History must be trimmed (not all 20 turns included)
    assert len(assembled["fitted_history"]) < 20
    
    # 3. High-scoring RAG chunk is prioritized over low-scoring chunk
    assert "high.txt" in assembled["augmented_prompt"]
    
    # 4. Total estimated tokens fit comfortably within the context limit
    assert assembled["stats"]["total_estimated_tokens"] <= 2048


@pytest.mark.asyncio
async def test_ollama_provider_get_model_info_async_stable_context():
    """Verify OllamaProvider queries /api/show, caches model info, and assigns stable_num_ctx."""
    provider = OllamaProvider()
    
    mock_show_response = MagicMock()
    mock_show_response.status_code = 200
    mock_show_response.json.return_value = {
        "model_info": {"llama.context_length": 131072},
        "details": {"parameter_size": "8B"},
        "capabilities": ["tools"]
    }
    
    with patch("httpx.AsyncClient.post", return_value=mock_show_response):
        info1 = await provider.get_model_info_async("qwen2.5-coder:7b")
        assert info1["stable_num_ctx"] in [4096, 8192]
        assert info1["max_context_length"] == 131072
        
        # Second call must hit cache immediately without HTTP call
        info2 = provider.get_model_info("qwen2.5-coder:7b")
        assert info2["stable_num_ctx"] == info1["stable_num_ctx"]
