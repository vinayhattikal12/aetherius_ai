import os
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.services.providers.base import BaseModelProvider
from backend.app.services.providers.anthropic_provider import AnthropicProvider
from backend.app.services.providers.openai_provider import OpenAIProvider
from backend.app.services.providers.groq_provider import GroqProvider
from backend.app.services.providers.google_provider import GoogleProvider
from backend.app.services.providers.openrouter_provider import OpenRouterProvider
from backend.app.core.logging import logger


class CloudProvider(BaseModelProvider):
    """
    Unified Frontier Cloud Model Provider.
    Orchestrates real requests across Anthropic, OpenAI, Groq, Google Gemini, and OpenRouter.
    Zero canned responses or hardcoded fallback templates.
    """

    def __init__(self):
        self.anthropic = AnthropicProvider()
        self.openai = OpenAIProvider()
        self.groq = GroqProvider()
        self.google = GoogleProvider()
        self.openrouter = OpenRouterProvider()

    def update_keys(
        self,
        anthropic_key: Optional[str] = None,
        openai_key: Optional[str] = None,
        groq_key: Optional[str] = None,
        gemini_key: Optional[str] = None,
        openrouter_key: Optional[str] = None,
    ):
        if anthropic_key is not None:
            self.anthropic.update_api_key(anthropic_key)
        if openai_key is not None:
            self.openai.update_api_key(openai_key)
        if groq_key is not None:
            self.groq.update_api_key(groq_key)
        if gemini_key is not None:
            self.google.update_api_key(gemini_key)
        if openrouter_key is not None:
            self.openrouter.update_api_key(openrouter_key)

    async def get_active_provider(self, model_name: str) -> BaseModelProvider:
        name_low = model_name.lower()

        # 1. Anthropic Claude
        if any(k in name_low for k in ["claude", "sonnet", "haiku", "opus", "anthropic"]):
            if await self.anthropic.health_check():
                return self.anthropic

        # 2. OpenAI GPT
        if any(k in name_low for k in ["gpt", "o1", "o3", "openai"]):
            if await self.openai.health_check():
                return self.openai

        # 3. Google Gemini
        if any(k in name_low for k in ["gemini", "google"]):
            if await self.google.health_check():
                return self.google

        # 4. Groq Fast Llama
        if any(k in name_low for k in ["groq"]):
            if await self.groq.health_check():
                return self.groq

        # 5. OpenRouter
        if any(k in name_low for k in ["openrouter", "deepseek-cloud"]):
            if await self.openrouter.health_check():
                return self.openrouter

        # Priority fallback to whatever cloud provider has valid keys configured
        if await self.anthropic.health_check():
            return self.anthropic
        if await self.openai.health_check():
            return self.openai
        if await self.groq.health_check():
            return self.groq
        if await self.google.health_check():
            return self.google
        if await self.openrouter.health_check():
            return self.openrouter

        raise RuntimeError(
            "No cloud API keys are configured. "
            "Please paste and save your Anthropic, OpenAI, or Groq API key in the Model Registry -> Cloud APIs tab, "
            "or run a local Ollama model."
        )

    async def health_check(self) -> bool:
        return (
            await self.anthropic.health_check()
            or await self.openai.health_check()
            or await self.groq.health_check()
            or await self.google.health_check()
            or await self.openrouter.health_check()
        )

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        name_low = model_name.lower()
        if "claude" in name_low:
            return self.anthropic.get_model_info(model_name)
        if "gpt" in name_low or "o1" in name_low:
            return self.openai.get_model_info(model_name)
        if "gemini" in name_low:
            return self.google.get_model_info(model_name)
        return self.groq.get_model_info(model_name)

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        provider = await self.get_active_provider(model_name)
        return await provider.generate_response(messages, model_name, temperature, max_tokens)

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        provider = await self.get_active_provider(model_name)
        async for token in provider.generate_stream(messages, model_name, temperature, max_tokens):
            yield token
