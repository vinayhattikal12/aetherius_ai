import os
import httpx
import json
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.services.providers.base import BaseModelProvider
from backend.app.core.logging import logger


class GroqProvider(BaseModelProvider):
    """Groq LPU Ultra-Low Latency Cloud Provider (Llama 3.3 70B, Llama 3.1 8B, Mixtral)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")

    def update_api_key(self, api_key: str):
        self.api_key = api_key

    async def health_check(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 10)

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        return {
            "provider": "groq",
            "model_name": model_name,
            "runtime": "cloud",
            "supports_tools": True,
            "supports_vision": False,
            "context_limit": 128000,
            "is_coding": True,
            "is_reasoning": True,
        }

    def _resolve_model(self, model_name: str) -> str:
        name_low = model_name.lower()
        if "70b" in name_low or "versatile" in name_low:
            return "llama-3.3-70b-versatile"
        if "8b" in name_low or "instant" in name_low:
            return "llama-3.1-8b-instant"
        return "llama-3.3-70b-versatile"

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("Groq API key is not configured. Please enter your API key in Model Registry -> Cloud APIs.")

        target_model = self._resolve_model(model_name)
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": target_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            )
            if res.status_code == 200:
                data = res.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            raise RuntimeError(f"Groq API error (HTTP {res.status_code}): {res.text}")

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise RuntimeError("Groq API key is not configured.")

        target_model = self._resolve_model(model_name)
        async with httpx.AsyncClient(timeout=45.0) as client:
            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": target_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True
                }
            ) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    raise RuntimeError(f"Groq streaming error (HTTP {response.status_code}): {err.decode('utf-8', 'ignore')}")

                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str and data_str != "[DONE]":
                            try:
                                chunk = json.loads(data_str)
                                token = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if token:
                                    yield token
                            except Exception:
                                pass
