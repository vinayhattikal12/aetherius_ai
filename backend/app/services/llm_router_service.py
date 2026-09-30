import json
import time
import httpx
from typing import Dict, Any, List, Optional
from backend.app.core.logging import logger


# These signals do NOT require an LLM call - they are unambiguous by text alone
_WEB_TRIGGERS = frozenset([
    "today", "latest", "current", "news", "live", "now", "weather",
    "stock", "price", "yesterday", "recent", "2024", "2025", "2026",
    "trending", "just announced", "just released", "right now",
    "who won", "what happened", "score", "sensex", "nifty"
])
_CODE_TRIGGERS = frozenset([
    "write code", "write a", "code for", "function", "def ", "class ",
    "import ", "debug", "error", "exception", "fix this", "refactor",
    "implement", "algorithm", "script", "program", "sql query", "api endpoint"
])
_VISUAL_TRIGGERS = frozenset([
    "draw", "paint", "sketch", "generate image", "create image",
    "visualize", "illustrate", "render", "show me a picture", "make a diagram"
])


class LLMRouterService:
    """
    Ultra-fast query intent classifier.
    
    Strategy:
    - For MOST queries: instant sub-millisecond classification via keyword signals.
      This fires BEFORE streaming so the right context is assembled.
    - For AMBIGUOUS multi-turn queries: use async Ollama LLM router in parallel,
      but do NOT block streaming on it (not yet implemented - placeholder).
    """

    @classmethod
    async def analyze_intent_and_entities(
        cls,
        query: str,
        history: List[Dict[str, str]],
        ollama_url: str = "http://127.0.0.1:11434"
    ) -> Dict[str, Any]:
        """
        Returns intent classification as fast as possible.
        For simple queries: returns instantly using text signals (0ms).
        For complex anaphoric follow-ups: calls a local LLM with a strict timeout.
        """
        q_lower = query.lower().strip()
        q_words = set(q_lower.split())

        # --- Instant classification (0ms) ---
        requires_web = bool(_WEB_TRIGGERS & q_words) or any(t in q_lower for t in _WEB_TRIGGERS)
        is_visual = any(t in q_lower for t in _VISUAL_TRIGGERS)
        is_code = any(t in q_lower for t in _CODE_TRIGGERS)

        # --- Turn type: check if query has an anaphoric pronoun referencing history ---
        anaphora_words = {"it", "this", "that", "they", "them", "its", "their", "he", "she", "the same"}
        has_anaphora = bool(anaphora_words & q_words) and len(history) > 0
        is_follow_up = has_anaphora or (len(q_lower.split()) <= 4 and len(history) > 0)
        turn_type = "FOLLOW_UP" if is_follow_up else "NEW_TOPIC"

        # --- Canonical query: resolve pronouns if short follow-up ---
        canonical = query
        if is_follow_up and history:
            # Get last assistant turn to resolve pronouns
            last_assistant = next((m["content"][:60] for m in reversed(history) if m["role"] == "assistant"), None)
            last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), query)
            if has_anaphora and last_user and last_user != query:
                canonical = query  # We'll resolve it contextually via history in context engine
            # Use previous topic as active topic context
            active_topic = last_user[:30] if last_user else query[:30]
        else:
            active_topic = query[:40]

        # --- For complex anaphoric queries, try LLM router with SHORT timeout ---
        # Only call if query is short + has pronouns (genuinely ambiguous)
        if has_anaphora and len(q_lower.split()) <= 6 and len(history) > 0:
            try:
                result = await cls._call_llm_router(query, history, ollama_url)
                if result:
                    return result
            except Exception:
                pass  # Fall through to instant result

        return {
            "turn_type": turn_type,
            "active_topic": active_topic,
            "canonical_query": canonical,
            "extracted_entities": [],
            "requires_web_search": requires_web,
            "is_visual_request": is_visual,
            "is_code_request": is_code,
        }

    @classmethod
    async def _call_llm_router(
        cls,
        query: str,
        history: List[Dict[str, str]],
        ollama_url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Calls Ollama LLM for anaphora resolution. Only used for genuinely ambiguous short follow-ups.
        Hard timeout: 3 seconds. If LLM is slow or busy, we skip it and use instant defaults.
        """
        history_text = "\n".join([f"{m['role']}: {m['content'][:100]}" for m in history[-3:]])
        system_prompt = (
            'You are a minimal NLP classifier. Return ONLY valid JSON, no explanation:\n'
            '{"turn_type":"FOLLOW_UP","active_topic":"short topic","canonical_query":"standalone query","extracted_entities":[],'
            '"requires_web_search":false,"is_visual_request":false,"is_code_request":false}'
        )
        prompt = f"History:\n{history_text}\n\nQuery: {query}"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                res = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": "qwen2.5-coder:1.5b",
                        "system": system_prompt,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 100}
                    }
                )
                if res.status_code == 200:
                    text = res.json().get("response", "{}")
                    return json.loads(text)
        except Exception as e:
            logger.debug(f"LLM router skipped (timeout/error): {e}")
        return None

