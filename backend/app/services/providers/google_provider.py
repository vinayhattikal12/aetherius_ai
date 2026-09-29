import os
import httpx
import json
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.services.providers.base import BaseModelProvider
from backend.app.core.logging import logger


class GoogleProvider(BaseModelProvider):
    """Google Gemini API Provider (Gemini 2.0 Flash, Gemini 1.5 Pro)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def update_api_key(self, api_key: str):
        self.api_key = api_key

    async def health_check(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 10)

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        return {
            "provider": "google",
            "model_name": model_name,
            "runtime": "cloud",
            "supports_tools": True,
            "supports_vision": True,
            "context_limit": 1000000,
            "is_coding": True,
            "is_reasoning": True,
        }

    def supports_vision(self) -> bool:
        return True

    def supports_context(self, context_length: int) -> bool:
        return context_length <= 1000000

    def _resolve_model(self, model_name: str) -> str:
        name_low = model_name.lower()
        if "pro" in name_low:
            return "gemini-1.5-pro"
        return "gemini-2.0-flash"

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("Google Gemini API key is not configured. Please enter your API key in Model Registry -> Cloud APIs.")

        target_model = self._resolve_model(model_name)
        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={self.api_key}"
        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": contents,
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens
                    }
                }
            )
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return ""
            raise RuntimeError(f"Google Gemini API error (HTTP {res.status_code}): {res.text}")

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        # Fallback to single generation with word streaming if SSE format is not used
        full_text = await self.generate_response(messages, model_name, temperature, max_tokens)
        for word in full_text.split(" "):
            yield word + " "
