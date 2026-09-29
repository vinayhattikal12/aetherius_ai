import os
import httpx
import json
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.services.providers.base import BaseModelProvider
from backend.app.core.logging import logger


class AnthropicProvider(BaseModelProvider):
    """Anthropic Claude API Provider (Claude 3.7 Sonnet, Claude 3.5 Sonnet, Claude 3.5 Haiku)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    def update_api_key(self, api_key: str):
        self.api_key = api_key

    async def health_check(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 10)

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        return {
            "provider": "anthropic",
            "model_name": model_name,
            "runtime": "cloud",
            "supports_tools": True,
            "supports_vision": True,
            "context_limit": 200000,
            "is_coding": True,
            "is_reasoning": True,
        }

    def supports_vision(self) -> bool:
        return True

    def supports_context(self, context_length: int) -> bool:
        return context_length <= 200000

    def _resolve_model(self, model_name: str) -> str:
        name_low = model_name.lower()
        if "3.7" in name_low or "3-7" in name_low:
            return "claude-3-7-sonnet-20250219"
        if "haiku" in name_low:
            return "claude-3-5-haiku-20241022"
        return "claude-3-5-sonnet-20241022"

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("Anthropic API key is not configured. Please enter your API key in Model Registry -> Cloud APIs.")

        target_model = self._resolve_model(model_name)
        system_msg = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user_msgs = []
        for m in messages:
            if m.get("role") != "system":
                content = m.get("content", "")
                if m.get("images"):
                    content_list = [{"type": "text", "text": content}]
                    for img_b64 in m["images"]:
                        content_list.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}
                        })
                    user_msgs.append({"role": m["role"], "content": content_list})
                else:
                    user_msgs.append({"role": m["role"], "content": content})

        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": target_model,
                    "system": system_msg,
                    "messages": user_msgs,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            )
            if res.status_code == 200:
                data = res.json()
                return data.get("content", [{}])[0].get("text", "")
            raise RuntimeError(f"Anthropic API error (HTTP {res.status_code}): {res.text}")

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise RuntimeError("Anthropic API key is not configured.")

        target_model = self._resolve_model(model_name)
        system_msg = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user_msgs = [m for m in messages if m.get("role") != "system"]

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": target_model,
                    "system": system_msg,
                    "messages": user_msgs,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True
                }
            ) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    raise RuntimeError(f"Anthropic streaming error (HTTP {response.status_code}): {err.decode('utf-8', 'ignore')}")

                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str and data_str != "[DONE]":
                            try:
                                chunk = json.loads(data_str)
                                if chunk.get("type") == "content_block_delta":
                                    token = chunk.get("delta", {}).get("text", "")
                                    if token:
                                        yield token
                            except Exception:
                                pass
