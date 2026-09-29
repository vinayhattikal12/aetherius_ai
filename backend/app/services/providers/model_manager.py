from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.services.providers.base import BaseModelProvider
from backend.app.services.providers.ollama_provider import OllamaProvider
from backend.app.services.providers.cloud_provider import CloudProvider
from backend.app.core.logging import logger


class ModelManager:
    """Orchestrates model execution between local (Ollama/llama.cpp) and cloud providers."""

    def __init__(self):
        self.ollama = OllamaProvider()
        self.cloud = CloudProvider()

    async def get_provider(self, model_name: str) -> BaseModelProvider:
        # Check if Ollama is running and model is local or has a tag
        if await self.ollama.is_available():
            installed = await self.ollama.get_installed_tags()
            if model_name in installed or ":" in model_name or "local" in model_name.lower():
                return self.ollama
        # Default to Cloud / Unified provider
        return self.cloud

    async def pull_model(self, model_name: str) -> bool:
        """Trigger model download via Ollama if available."""
        if await self.ollama.is_available():
            return await self.ollama.pull_model(model_name)
        return False

    async def delete_model(self, model_name: str) -> bool:
        """Trigger model deletion via Ollama if available."""
        if await self.ollama.is_available():
            return await self.ollama.delete_model(model_name)
        return False

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model_name: str = "llama3.2:3b",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        provider = await self.get_provider(model_name)
        try:
            return await provider.generate_response(messages, model_name, temperature, max_tokens)
        except Exception as e:
            logger.warning(f"Provider {provider.__class__.__name__} failed: {e}. Falling back to Cloud provider.")
            return await self.cloud.generate_response(messages, model_name, temperature, max_tokens)

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model_name: str = "llama3.2:3b",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        provider = await self.get_provider(model_name)
        try:
            async for token in provider.generate_stream(messages, model_name, temperature, max_tokens):
                yield token
        except Exception as e:
            logger.warning(f"Streaming provider {provider.__class__.__name__} failed: {e}. Falling back.")
            async for token in self.cloud.generate_stream(messages, model_name, temperature, max_tokens):
                yield token


model_manager = ModelManager()
