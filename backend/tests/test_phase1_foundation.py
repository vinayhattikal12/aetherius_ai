import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.services.providers.base import BaseModelProvider
from backend.app.services.providers.ollama_provider import OllamaProvider
from backend.app.services.providers.anthropic_provider import AnthropicProvider
from backend.app.services.providers.openai_provider import OpenAIProvider
from backend.app.services.providers.groq_provider import GroqProvider
from backend.app.services.providers.google_provider import GoogleProvider
from backend.app.services.providers.openrouter_provider import OpenRouterProvider
from backend.app.services.providers.model_manager import model_manager, ModelManager
from backend.app.services.chat_service import ChatService
from backend.app.schemas.chat import ChatCompletionRequest


@pytest.mark.asyncio
async def test_provider_hierarchy_and_interfaces():
    """Verify that all concrete model providers adhere to the standard BaseModelProvider interface."""
    providers = [
        OllamaProvider(),
        AnthropicProvider(api_key="test-key"),
        OpenAIProvider(api_key="test-key"),
        GroqProvider(api_key="test-key"),
        GoogleProvider(api_key="test-key"),
        OpenRouterProvider(api_key="test-key"),
    ]

    for p in providers:
        assert isinstance(p, BaseModelProvider)
        assert hasattr(p, "generate_response")
        assert hasattr(p, "generate_stream")
        assert hasattr(p, "health_check")
        assert hasattr(p, "get_model_info")
        assert hasattr(p, "supports_tools")
        assert hasattr(p, "supports_vision")
        assert hasattr(p, "supports_context")
        assert hasattr(p, "cancel")
        info = p.get_model_info("test-model")
        assert "provider" in info
        assert "runtime" in info


@pytest.mark.asyncio
async def test_model_identity_metadata():
    """Verify execution metadata accurately reflects actual provider, runtime, and fallback flags."""
    manager = ModelManager()

    # Case 1: Local Ollama available
    with patch.object(manager.ollama, "health_check", AsyncMock(return_value=True)), \
         patch.object(manager.ollama, "get_installed_tags", AsyncMock(return_value=["llama3.2:3b", "qwen2.5-coder:7b"])), \
         patch.object(manager.ollama, "generate_response", AsyncMock(return_value="Python is a high-level programming language.")):

        resp, meta = await manager.generate_response_with_metadata(
            messages=[{"role": "user", "content": "Explain Python."}],
            model_name="llama3.2:3b",
            requested_mode="manual"
        )
        assert "Python" in resp
        assert meta.runtime == "local"
        assert meta.provider == "ollama"
        assert meta.actual_model == "llama3.2:3b"
        assert meta.fallback_used is False


@pytest.mark.asyncio
async def test_transparent_failure_when_providers_offline():
    """Verify that when no providers are available, Aetherius raises an explicit error and NEVER generates a fake answer."""
    manager = ModelManager()

    with patch.object(manager.ollama, "health_check", AsyncMock(return_value=False)), \
         patch.object(manager.cloud, "health_check", AsyncMock(return_value=False)):

        with pytest.raises(RuntimeError) as exc_info:
            await manager.generate_response(
                messages=[{"role": "user", "content": "What are loops in Java?"}],
                model_name="llama3.2:3b"
            )

        err_msg = str(exc_info.value)
        assert "Cannot execute request" in err_msg or "offline" in err_msg
        # Ensure NO canned knowledge strings are returned
        assert "Solution & Technical Deep Dive" not in err_msg
        assert "Core Principle & Definition" not in err_msg


@pytest.mark.asyncio
async def test_real_model_generation_flow(test_db: AsyncSession):
    """Verify real instruction following and code generation flow through ChatService."""
    req = ChatCompletionRequest(
        message="Write a Python function to reverse a string.",
        workspace_slug="developer",
        model_name="llama3.2:3b"
    )

    resp = await ChatService.process_chat_completion(db=test_db, request=req)
    assert resp is not None
    assert resp.assistant_message is not None
    assert len(resp.assistant_message.content) > 10

    # Ensure metadata was captured
    meta = resp.assistant_message.extra_metadata or {}
    assert "execution_metadata" in meta
    assert meta["execution_metadata"]["requested_mode"] == "manual"
