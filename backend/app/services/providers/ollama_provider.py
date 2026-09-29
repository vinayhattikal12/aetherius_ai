import httpx
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional
from backend.app.services.providers.base import BaseModelProvider
from backend.app.core.logging import logger


class OllamaProvider(BaseModelProvider):
    """Local Ollama model provider with dynamic tags detection and pull operations."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def get_installed_tags(self) -> List[str]:
        """Return list of locally installed model tags in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = data.get("models", [])
                    return [m.get("name") for m in models if "name" in m]
        except Exception as e:
            logger.debug(f"Ollama tags check notice: {e}")
        return []

    async def pull_model(self, model_name: str) -> bool:
        """Trigger model download in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                res = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": False}
                )
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to pull model {model_name} via Ollama: {e}")
            return False

    async def delete_model(self, model_name: str) -> bool:
        """Trigger model deletion in Ollama to free disk space."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.request(
                    "DELETE",
                    f"{self.base_url}/api/delete",
                    json={"name": model_name}
                )
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to delete model {model_name} via Ollama: {e}")
            return False

    async def resolve_target_model(self, model_name: str, has_images: bool = False) -> str:
        """Resolve requested model to the best available locally installed Ollama chat tag."""
        installed = await self.get_installed_tags()
        if not installed:
            return model_name
        
        # Filter out non-chat embedding models (e.g. nomic-embed-text, bge-large)
        chat_installed = [t for t in installed if "embed" not in t.lower()]
        if not chat_installed:
            chat_installed = installed

        # 1. If images are present, check for installed vision models first
        if has_images:
            for vision_tag in ["llama3.2-vision:11b", "llama3.2-vision:latest", "qwen2.5-vl:7b", "llava:13b", "llava:7b", "llava:latest", "moondream:1.8b", "bakllava:latest"]:
                for tag in chat_installed:
                    if vision_tag in tag or tag.startswith(vision_tag.split(":")[0]):
                        return tag

        # 2. Exact match (as long as it's not an embedding model)
        if model_name in chat_installed:
            return model_name
        
        # 3. Normalized family / prefix match (e.g. "deepseek-r1:8b" -> "deepseek-r1:8b", "llama3.2:3b" -> "llama3.2:3b")
        req_clean = model_name.lower().replace("-", "").replace(".", "").replace(":", "")
        for tag in chat_installed:
            tag_clean = tag.lower().replace("-", "").replace(".", "").replace(":", "")
            if req_clean in tag_clean or tag_clean in req_clean:
                return tag

        # 4. Base prefix match (e.g. "deepseek" in "deepseek-r1:8b")
        base = model_name.split(":")[0].lower().replace("-", "")
        for tag in chat_installed:
            clean_tag = tag.lower().replace("-", "")
            if clean_tag.startswith(base) or base in clean_tag:
                return tag
        
        # 5. Fallback to best available installed lightweight coding/reasoning model
        for preferred in ["llama3.2:3b", "qwen2.5-coder:1.5b", "qwen2.5-coder:7b", "deepseek-r1:8b", "mistral:7b", "llama3:latest", "qwen2.5-coder:14b", "qwen3:8b"]:
            for tag in chat_installed:
                if preferred.split(":")[0] in tag:
                    return tag

        return chat_installed[0]

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        has_images = any("images" in m and m["images"] for m in messages)
        target_model = await self.resolve_target_model(model_name, has_images=has_images)
        
        # Strip system prefix if empty and normalize payload
        clean_messages = []
        for m in messages:
            if m.get("content") or m.get("images"):
                entry = {"role": m["role"], "content": m.get("content", "")}
                if m.get("images"):
                    entry["images"] = m["images"]
                clean_messages.append(entry)

        async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=4.0)) as client:
            res = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": target_model,
                    "messages": clean_messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            )
            if res.status_code == 200:
                data = res.json()
                return data.get("message", {}).get("content", "")
            raise RuntimeError(f"Ollama returned {res.status_code}: {res.text}")

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        has_images = any("images" in m and m["images"] for m in messages)
        target_model = await self.resolve_target_model(model_name, has_images=has_images)

        clean_messages = []
        for m in messages:
            if m.get("content") or m.get("images"):
                entry = {"role": m["role"], "content": m.get("content", "")}
                if m.get("images"):
                    entry["images"] = m["images"]
                clean_messages.append(entry)

        async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=4.0)) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": target_model,
                    "messages": clean_messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield token
                        except Exception:
                            pass
