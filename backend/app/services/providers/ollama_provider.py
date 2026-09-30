import os
import time
import httpx
import json
import asyncio
import psutil
from typing import AsyncGenerator, Dict, Any, List, Optional, Set
from backend.app.services.providers.base import BaseModelProvider
from backend.app.core.logging import logger


class OllamaProvider(BaseModelProvider):
    """
    High-Performance Local Ollama Provider.
    Includes memory persistence (keep_alive: 30m), physical-core thread optimization,
    dynamic context window scaling, installed tag caching, and idle model eviction.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url
        # Use physical CPU cores to eliminate hyperthreading cache contention
        self._cpu_threads = max(1, psutil.cpu_count(logical=False) or (os.cpu_count() or 4))
        self._cached_tags: List[str] = []
        self._last_tags_check: float = 0.0
        self._current_active_model: Optional[str] = None

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def health_check(self) -> bool:
        return await self.is_available()

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        is_coder = "coder" in model_name.lower() or "code" in model_name.lower()
        is_reasoner = "r1" in model_name.lower() or "reason" in model_name.lower()
        is_vision = "vision" in model_name.lower() or "vl" in model_name.lower() or "llava" in model_name.lower()
        return {
            "provider": "ollama",
            "model_name": model_name,
            "runtime": "local",
            "supports_tools": True,
            "supports_vision": is_vision,
            "context_limit": 16384 if is_coder else 8192,
            "is_coding": is_coder,
            "is_reasoning": is_reasoner,
        }

    def supports_vision(self) -> bool:
        return True

    async def get_installed_tags(self) -> List[str]:
        """Return cached list of locally installed model tags in Ollama (30s TTL)."""
        now = time.time()
        if self._cached_tags and (now - self._last_tags_check) < 30.0:
            return self._cached_tags

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = data.get("models", [])
                    self._cached_tags = [m.get("name") for m in models if "name" in m]
                    self._last_tags_check = now
                    return self._cached_tags
        except Exception as e:
            logger.debug(f"Ollama tags check notice: {e}")
        return self._cached_tags or []

    async def evict_idle_models(self, target_model: str) -> None:
        """Evicts previously loaded non-target models from memory to prevent RAM saturation and CPU thrashing."""
        if self._current_active_model and self._current_active_model != target_model:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    await client.post(
                        f"{self.base_url}/api/generate",
                        json={"model": self._current_active_model, "keep_alive": 0}
                    )
            except Exception:
                pass
        self._current_active_model = target_model

    async def pull_model(self, model_name: str) -> bool:
        """Trigger model download in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                res = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": False}
                )
                self._last_tags_check = 0.0 # Invalidate cache
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
                self._last_tags_check = 0.0 # Invalidate cache
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
        
        # 3. Normalized family / prefix match
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

    def _compute_adaptive_context_size(self, clean_messages: List[Dict[str, Any]], target_model: str) -> int:
        """Calculates optimal context window (num_ctx) to eliminate KV-cache pre-allocation latency on CPU."""
        total_chars = sum(len(m.get("content", "")) for m in clean_messages)
        est_tokens = max(32, total_chars // 4)
        
        # Scale context dynamically: for small conversations use 1024 / 2048, up to 4096 for long context
        if est_tokens <= 500:
            return 1024
        elif est_tokens <= 1500:
            return 2048
        return min(4096, est_tokens + 512)

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        has_images = any("images" in m and m["images"] for m in messages)
        target_model = await self.resolve_target_model(model_name, has_images=has_images)
        await self.evict_idle_models(target_model)
        
        clean_messages = []
        for m in messages:
            if m.get("content") or m.get("images"):
                entry = {"role": m["role"], "content": m.get("content", "")}
                if m.get("images"):
                    entry["images"] = m["images"]
                clean_messages.append(entry)

        num_ctx = self._compute_adaptive_context_size(clean_messages, target_model)
        timeout = httpx.Timeout(240.0, connect=15.0, read=240.0, write=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": target_model,
                    "messages": clean_messages,
                    "stream": False,
                    "keep_alive": "30m",  # Keep active model hot in memory
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        "num_ctx": num_ctx,
                        "num_thread": self._cpu_threads,
                    }
                }
            )
            if res.status_code == 200:
                data = res.json()
                return data.get("message", {}).get("content", "")
            raise RuntimeError(f"Ollama returned HTTP {res.status_code}: {res.text}")

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        has_images = any("images" in m and m["images"] for m in messages)
        target_model = await self.resolve_target_model(model_name, has_images=has_images)
        await self.evict_idle_models(target_model)

        clean_messages = []
        for m in messages:
            if m.get("content") or m.get("images"):
                entry = {"role": m["role"], "content": m.get("content", "")}
                if m.get("images"):
                    entry["images"] = m["images"]
                clean_messages.append(entry)

        num_ctx = self._compute_adaptive_context_size(clean_messages, target_model)
        timeout = httpx.Timeout(300.0, connect=15.0, read=300.0, write=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": target_model,
                    "messages": clean_messages,
                    "stream": True,
                    "keep_alive": "30m",  # Keep model hot in memory for instant next token response
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        "num_ctx": num_ctx,
                        "num_thread": self._cpu_threads,
                    }
                }
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise RuntimeError(f"Ollama streaming returned HTTP {response.status_code}: {error_body.decode('utf-8', 'ignore')}")

                async for line in response.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield token
                        except Exception:
                            pass

