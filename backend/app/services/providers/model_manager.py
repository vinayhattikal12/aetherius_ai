import os
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from backend.app.services.providers.base import BaseModelProvider
from backend.app.services.providers.ollama_provider import OllamaProvider
from backend.app.services.providers.cloud_provider import CloudProvider
from backend.app.core.logging import logger


class ModelExecutionMetadata:
    def __init__(
        self,
        requested_mode: str,
        selected_model: str,
        actual_model: str,
        provider: str,
        runtime: str,
        fallback_used: bool = False,
        reason: str = "Standard execution"
    ):
        self.requested_mode = requested_mode
        self.selected_model = selected_model
        self.actual_model = actual_model
        self.provider = provider
        self.runtime = runtime
        self.fallback_used = fallback_used
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_mode": self.requested_mode,
            "selected_model": self.selected_model,
            "actual_model": self.actual_model,
            "provider": self.provider,
            "runtime": self.runtime,
            "fallback_used": self.fallback_used,
            "reason": self.reason
        }


class ModelManager:
    """
    Central Model Execution Orchestrator.
    Manages provider lifecycles, health checks, execution metadata, and transparent fallbacks.
    Zero hallucinated fallback responses.
    """

    def __init__(self):
        self.ollama = OllamaProvider()
        self.cloud = CloudProvider()
        self._ollama_healthy: Optional[bool] = None
        self._ollama_health_checked_at: float = 0.0
        self._HEALTH_TTL: float = 5.0  # Re-check Ollama health at most every 5 seconds

    async def _is_ollama_healthy(self) -> bool:
        """Cached health check — avoids an HTTP ping on every single request."""
        now = time.time()
        if self._ollama_healthy is not None and (now - self._ollama_health_checked_at) < self._HEALTH_TTL:
            return self._ollama_healthy
        self._ollama_healthy = await self.ollama.health_check()
        self._ollama_health_checked_at = now
        return self._ollama_healthy

    async def get_provider_and_metadata(
        self,
        model_name: str,
        requested_mode: str = "manual"
    ) -> Tuple[BaseModelProvider, ModelExecutionMetadata]:
        is_cloud_explicit = any(k in model_name.lower() for k in ["claude", "sonnet", "haiku", "opus", "gpt", "openai", "anthropic", "groq", "gemini", "google", "cloud"])
        ollama_healthy = await self._is_ollama_healthy()

        # 1. Explicit Cloud Request
        if is_cloud_explicit:
            if await self.cloud.health_check():
                active_cloud = await self.cloud.get_active_provider(model_name)
                provider_name = active_cloud.__class__.__name__.replace("Provider", "").lower()
                meta = ModelExecutionMetadata(
                    requested_mode=requested_mode,
                    selected_model=model_name,
                    actual_model=model_name,
                    provider=provider_name,
                    runtime="cloud",
                    fallback_used=False,
                    reason=f"Explicit cloud model routed to {provider_name.title()}"
                )
                return self.cloud, meta
            elif ollama_healthy:
                # Fallback to local Ollama if cloud key missing
                installed = await self.ollama.get_installed_tags()
                actual = installed[0] if installed else "llama3.2:3b"
                meta = ModelExecutionMetadata(
                    requested_mode=requested_mode,
                    selected_model=model_name,
                    actual_model=actual,
                    provider="ollama",
                    runtime="local",
                    fallback_used=True,
                    reason="Cloud API key unconfigured; routed to local Ollama"
                )
                return self.ollama, meta
            else:
                raise RuntimeError(
                    f"Model '{model_name}' requires Cloud API keys which are not configured, "
                    "and local Ollama is offline."
                )

        # 2. Local Request
        if ollama_healthy:
            resolved = await self.ollama.resolve_target_model(model_name)
            meta = ModelExecutionMetadata(
                requested_mode=requested_mode,
                selected_model=model_name,
                actual_model=resolved,
                provider="ollama",
                runtime="local",
                fallback_used=False,
                reason="Executed via local Ollama engine"
            )
            return self.ollama, meta

        # 3. Local offline, check if Cloud fallback is available
        if await self.cloud.health_check():
            active_cloud = await self.cloud.get_active_provider(model_name)
            provider_name = active_cloud.__class__.__name__.replace("Provider", "").lower()
            meta = ModelExecutionMetadata(
                requested_mode=requested_mode,
                selected_model=model_name,
                actual_model=model_name,
                provider=provider_name,
                runtime="cloud",
                fallback_used=True,
                reason="Local Ollama is offline; transparently fell back to active Cloud API"
            )
            return self.cloud, meta

        # 4. Neither available
        raise RuntimeError(
            f"Cannot execute request: Local Ollama engine is not running at {self.ollama.base_url}, "
            "and no cloud API keys (Anthropic, OpenAI, Groq) are configured in Settings."
        )

    async def generate_response_with_metadata(
        self,
        messages: List[Dict[str, Any]],
        model_name: str = "llama3.2:3b",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        requested_mode: str = "manual",
    ) -> Tuple[str, ModelExecutionMetadata]:
        provider, meta = await self.get_provider_and_metadata(model_name, requested_mode=requested_mode)
        try:
            content = await provider.generate_response(messages, model_name, temperature, max_tokens)
            return content, meta
        except Exception as e:
            logger.warning(f"Primary provider {provider.__class__.__name__} failed during execution: {e}")
            # Try alternate provider if available
            if provider == self.ollama and await self.cloud.health_check():
                logger.info("Retrying via Cloud Provider fallback...")
                cloud_p = await self.cloud.get_active_provider(model_name)
                content = await cloud_p.generate_response(messages, model_name, temperature, max_tokens)
                meta.fallback_used = True
                meta.provider = cloud_p.__class__.__name__.replace("Provider", "").lower()
                meta.runtime = "cloud"
                meta.reason = f"Ollama execution failed ({e}); retried via Cloud"
                return content, meta
            raise

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str = "llama3.2:3b",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        content, _ = await self.generate_response_with_metadata(messages, model_name, temperature, max_tokens)
        return content

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        model_name: str = "llama3.2:3b",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        requested_mode: str = "manual",
    ) -> AsyncGenerator[str, None]:
        provider, _ = await self.get_provider_and_metadata(model_name, requested_mode=requested_mode)
        try:
            async for token in provider.generate_stream(messages, model_name, temperature, max_tokens):
                yield token
        except Exception as e:
            logger.warning(f"Primary streaming provider {provider.__class__.__name__} failed: {e}")
            if provider == self.ollama and await self.cloud.health_check():
                logger.info("Retrying stream via Cloud Provider fallback...")
                cloud_p = await self.cloud.get_active_provider(model_name)
                async for token in cloud_p.generate_stream(messages, model_name, temperature, max_tokens):
                    yield token
            else:
                raise

    async def stream_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str = "llama3.2:3b",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        requested_mode: str = "manual",
    ) -> AsyncGenerator[str, None]:
        """Streaming generator alias for generate_stream."""
        async for token in self.generate_stream(
            messages=messages,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            requested_mode=requested_mode,
        ):
            yield token


model_manager = ModelManager()
