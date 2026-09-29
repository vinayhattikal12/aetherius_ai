import math
import hashlib
import httpx
import numpy as np
from typing import List, Optional
from backend.app.core.logging import logger

EMBEDDING_DIM = 384
_OLLAMA_AVAILABLE: Optional[bool] = None


class EmbeddingService:
    """Generates normalized dense embeddings for document chunks and user queries."""

    @classmethod
    async def _check_ollama(cls) -> bool:
        global _OLLAMA_AVAILABLE
        if _OLLAMA_AVAILABLE is not None:
            return _OLLAMA_AVAILABLE
        try:
            async with httpx.AsyncClient(timeout=0.3) as client:
                res = await client.get("http://127.0.0.1:11434/api/tags")
                _OLLAMA_AVAILABLE = res.status_code == 200
        except Exception:
            _OLLAMA_AVAILABLE = False
        return _OLLAMA_AVAILABLE

    @classmethod
    async def embed_text(cls, text: str, model_name: str = "nomic-embed-text") -> List[float]:
        # 1. Attempt local Ollama embedding if known to be running
        if await cls._check_ollama():
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.post(
                        "http://127.0.0.1:11434/api/embeddings",
                        json={"model": model_name, "prompt": text}
                    )
                    if res.status_code == 200:
                        emb = res.json().get("embedding", [])
                        if emb:
                            return cls._project_to_dim(emb, EMBEDDING_DIM)
            except Exception:
                pass

        # 2. Fast deterministic subword semantic embedding fallback (384-dimensional)
        return cls._generate_semantic_vector(text, EMBEDDING_DIM)

    @classmethod
    async def embed_batch(cls, texts: List[str], model_name: str = "nomic-embed-text") -> List[List[float]]:
        return [await cls.embed_text(t, model_name) for t in texts]

    @classmethod
    def _project_to_dim(cls, vec: List[float], target_dim: int = EMBEDDING_DIM) -> List[float]:
        arr = np.array(vec, dtype=np.float32)
        curr_dim = len(arr)
        if curr_dim == target_dim:
            return cls._normalize(arr.tolist())
        if curr_dim > target_dim:
            if curr_dim % target_dim == 0:
                factor = curr_dim // target_dim
                arr = arr.reshape(target_dim, factor).mean(axis=1)
            else:
                indices = np.linspace(0, curr_dim - 1, target_dim).astype(int)
                arr = arr[indices]
        else:
            arr = np.pad(arr, (0, target_dim - curr_dim))
        return cls._normalize(arr.tolist())

    @staticmethod
    def _normalize(vec: List[float]) -> List[float]:
        arr = np.array(vec, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()

    @classmethod
    def _generate_semantic_vector(cls, text: str, dim: int = 384) -> List[float]:
        words = text.lower().split()
        vec = np.zeros(dim, dtype=np.float32)

        for w in words:
            h_word = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            idx = h_word % dim
            sign = 1.0 if (h_word // dim) % 2 == 0 else -1.0
            vec[idx] += sign * 1.5

            for i in range(len(w) - 2):
                tri = w[i : i + 3]
                h_tri = int(hashlib.sha256(tri.encode("utf-8")).hexdigest(), 16)
                idx_tri = h_tri % dim
                sign_tri = 1.0 if (h_tri // dim) % 2 == 0 else -1.0
                vec[idx_tri] += sign_tri * 0.5

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2:
            return 0.0
        if len(v1) != len(v2):
            min_dim = min(len(v1), len(v2))
            v1 = v1[:min_dim]
            v2 = v2[:min_dim]
        a = np.array(v1, dtype=np.float32)
        b = np.array(v2, dtype=np.float32)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))
