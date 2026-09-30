import json
import httpx
from typing import Dict, Any, List, Optional
from backend.app.core.logging import logger
from backend.app.services.providers.ollama_provider import OllamaProvider

class LLMRouterService:
    @classmethod
    async def analyze_intent_and_entities(
        cls, 
        query: str, 
        history: List[Dict[str, str]], 
        ollama_url: str = "http://127.0.0.1:11434"
    ) -> Dict[str, Any]:
        """
        Uses a lightweight local LLM to perform dynamic NLP tasks:
        - Turn Classification (NEW_TOPIC, FOLLOW_UP, etc.)
        - Entity Extraction (Without hardcoded lists)
        - Intent Detection (Requires Web Search, Requires Code, etc.)
        """
        provider = OllamaProvider(base_url=ollama_url)
        # Fallback to the fastest available model on the system
        target_model = await provider.resolve_target_model("llama3.2:3b")
        
        system_prompt = """You are an internal NLP router for Aetherius AI. Analyze the user's latest query in the context of the history.
Return ONLY a valid JSON object matching this schema, nothing else:
{
  "turn_type": "NEW_TOPIC" | "FOLLOW_UP" | "MODIFICATION" | "CORRECTION" | "CLARIFICATION",
  "active_topic": "A short 1-3 word description of the main subject",
  "canonical_query": "The user's query rewritten to be standalone (e.g. replacing 'it' with the active topic)",
  "extracted_entities": [{"name": "Entity Name", "type": "person|organization|technology|concept"}],
  "requires_web_search": true/false,
  "is_visual_request": true/false,
  "is_code_request": true/false
}

Guidelines:
- canonical_query: If the user says "what about it?", rewrite it as "what about [topic]?". If it's already clear, leave it as is.
- requires_web_search: True ONLY if the query asks for live news, real-time weather, stock prices, or recent events. False for general programming or definitions.
- is_visual_request: True if asking to draw, paint, generate image, or visualize.
- is_code_request: True if asking to write code, debug, or explain algorithms."""
        
        # Prepare context
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-3:]])
        prompt = f"History:\n{history_text}\n\nLatest Query: {query}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": target_model,
                        "system": system_prompt,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {
                            "temperature": 0.0,
                            "num_predict": 150
                        }
                    }
                )
                if res.status_code == 200:
                    text = res.json().get("response", "{}")
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        logger.error(f"LLM Router returned invalid JSON: {text}")
        except Exception as e:
            logger.error(f"LLM Router failed: {e}")
            
        # Fallback if LLM fails
        return {
            "turn_type": "NEW_TOPIC",
            "active_topic": query[:20],
            "extracted_entities": [],
            "requires_web_search": False,
            "is_visual_request": False,
            "is_code_request": False
        }
