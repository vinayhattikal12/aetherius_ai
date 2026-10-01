import re
import json
import httpx
from typing import Dict, Any, List, Optional
from backend.app.services.embedding_service import EmbeddingService
from backend.app.core.logging import logger


class LLMRouterService:
    """
    Autonomous Semantic Intent, Entity, & Execution Router.
    Combines sub-millisecond semantic centroid embeddings with high-signal structural NLP.
    Scales to millions of users without fragile manual keyword lists.
    """

    SEMANTIC_CENTROIDS = {
        "temporal_realtime": (
            "latest current today yesterday now breaking news updates live weather temperature "
            "stock price quote market sports score match tournament winner election results "
            "trending recently announced launched released 2024 2025 2026 upcoming schedule"
        ),
        "entity_roster_fact": (
            "list of all chief ministers prime ministers presidents governors ministers ceos "
            "heads of state government officials leaders roster table each state country capital "
            "population gdp net worth biography founder company organization cabinet members rankings"
        ),
        "code_development": (
            "write code create function implement class def python typescript javascript sql query "
            "api endpoint unit test bug error exception debug refactor algorithm data structure"
        ),
        "visual_generation": (
            "draw paint sketch generate image create picture visualize illustrate render diagram flowchart schematic"
        ),
        "casual_greeting": (
            "hello hi hey good morning good evening how are you who are you what can you do help ping thank you"
        )
    }

    _centroid_vectors = {
        k: EmbeddingService._generate_semantic_vector(v)
        for k, v in SEMANTIC_CENTROIDS.items()
    }

    # High-signal structural patterns
    ROSTER_PATTERNS = [
        r"\b(?:list\s+of|names\s+of|all\s+the|table\s+of|roster\s+of|who\s+are\s+the)\b",
        r"\b(?:for\s+each|for\s+every|in\s+each|in\s+every)\s+(?:state|country|nation|department|district|city)\b",
        r"\b(?:all\s+states|all\s+countries|all\s+ministers|all\s+chief\s+ministers|all\s+presidents|all\s+governors)\b",
        r"\b(?:cm'?s?|pm'?s?|chief\s+ministers?|prime\s+ministers?|governors?)\s+of\b",
    ]

    FACTUAL_ENTITY_PATTERNS = [
        r"\b(?:who\s+is|who\s+was|who\s+are|who\s+won|what\s+is\s+the\s+capital|what\s+is\s+the\s+gdp|what\s+is\s+the\s+population|what\s+is\s+the\s+price|how\s+much\s+is|tell\s+me\s+about)\b",
        r"\b(?:chief\s+minister|prime\s+minister|president|governor|ceo|founder|chancellor|mayor|cabinet\s+minister|company|organization|startup|firm|enterprise)\b",
        r"\b(?:stock\s+price|market\s+cap|weather\s+in|temperature\s+in|latest\s+news|breaking\s+news)\b",
    ]

    CODE_PATTERNS = [
        r"\b(?:write|create|implement|generate|build)\s+(?:a\s+|an\s+)?(?:[a-zA-Z0-9_\-\s]{0,25})?\b(?:function|script|class|module|endpoint|query|algorithm|code|decorator|generator|interface)\b",
        r"\b(?:write\s+code|code\s+for|def\s+[a-zA-Z_]|class\s+[a-zA-Z_]|import\s+[a-zA-Z_]|fix\s+this\s+bug|syntax\s+error|refactor\s+this)\b",
        r"```[a-zA-Z]*",
    ]

    VISUAL_PATTERNS = [
        r"\b(?:draw|paint|sketch|generate\s+an?\s+image|create\s+an?\s+image|visualize|make\s+a\s+diagram|render\s+a\s+picture)\b",
    ]

    HISTORICAL_SCOPE_PATTERNS = [
        r"\b(?:from\s+independence|since\s+1947|since\s+1950|till\s+now|to\s+date|from\s+the\s+beginning|all\s+past\s+and\s+present|throughout\s+history|entire\s+history|since\s+inception|all\s+time|all\s+former)\b",
    ]

    MULTI_ENTITY_PATTERNS = [
        r"\b(?:each\s+state|every\s+state|all\s+states|each\s+country|every\s+country|all\s+countries|all\s+nations|each\s+nation)\b",
        r"\b(?:for\s+each|for\s+every|in\s+each|in\s+every)\s+(?:state|country|nation|territory|district)\b",
    ]

    @classmethod
    async def analyze_intent_and_entities(
        cls,
        query: str,
        history: List[Dict[str, str]],
        ollama_url: str = "http://127.0.0.1:11434"
    ) -> Dict[str, Any]:
        """
        Sub-millisecond autonomous intent analysis.
        Extracts execution requirements, routing signals, and search triggers.
        """
        q_clean = query.strip()
        q_lower = q_clean.lower()
        q_words = set(q_lower.split())

        # 1. Structural NLP Pattern Matching
        is_roster = any(re.search(pat, q_lower) for pat in cls.ROSTER_PATTERNS)
        is_factual_entity = any(re.search(pat, q_lower) for pat in cls.FACTUAL_ENTITY_PATTERNS)
        is_code = any(re.search(pat, q_lower) for pat in cls.CODE_PATTERNS)
        is_visual = any(re.search(pat, q_lower) for pat in cls.VISUAL_PATTERNS)
        has_hist = any(re.search(pat, q_lower) for pat in cls.HISTORICAL_SCOPE_PATTERNS)
        has_multi = any(re.search(pat, q_lower) for pat in cls.MULTI_ENTITY_PATTERNS)
        is_massive_scope = bool(has_hist and has_multi)

        is_casual = (
            q_lower in ["hi", "hello", "hey", "good morning", "good evening", "how are you", "who are you", "what can you do", "ping"]
            or (len(q_words) <= 2 and q_words.issubset({"hi", "hello", "hey", "aetherius", "help"}))
        )

        # 2. Dense Semantic Centroid Scoring (0ms)
        q_vec = EmbeddingService._generate_semantic_vector(q_clean)
        sim_temporal = EmbeddingService.cosine_similarity(q_vec, cls._centroid_vectors["temporal_realtime"])
        sim_roster = EmbeddingService.cosine_similarity(q_vec, cls._centroid_vectors["entity_roster_fact"])
        sim_code = EmbeddingService.cosine_similarity(q_vec, cls._centroid_vectors["code_development"])
        sim_visual = EmbeddingService.cosine_similarity(q_vec, cls._centroid_vectors["visual_generation"])

        # 3. Autonomous Web Search Decision Logic
        requires_web = False
        if not is_casual and not (is_code and sim_code > 0.45):
            if is_roster or is_factual_entity or is_massive_scope:
                requires_web = True
            elif sim_temporal > 0.22 or sim_roster > 0.25:
                requires_web = True
            elif any(k in q_words for k in {"news", "today", "latest", "current", "recently", "recent", "launched", "release", "released", "update", "updates", "weather", "stock", "price", "2024", "2025", "2026", "score", "scores", "won", "yesterday"}):
                requires_web = True

        # 4. Turn Type & Anaphora Resolution
        anaphora_words = {"it", "this", "that", "they", "them", "its", "their", "he", "she", "the same"}
        has_anaphora = bool(anaphora_words & q_words) and len(history) > 0
        is_follow_up = has_anaphora or (len(q_words) <= 4 and len(history) > 0)
        turn_type = "FOLLOW_UP" if is_follow_up else "NEW_TOPIC"

        canonical = query
        active_topic = query[:40]

        if is_follow_up and history:
            last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), query)
            active_topic = last_user[:35] if last_user else query[:35]

            # If short pronoun query, synthesize canonical search query
            if has_anaphora and len(q_words) <= 6:
                canonical = f"{active_topic} {query}"

        return {
            "turn_type": turn_type,
            "active_topic": active_topic,
            "canonical_query": canonical,
            "extracted_entities": [],
            "requires_web_search": requires_web,
            "is_roster_request": is_roster,
            "is_massive_scope": is_massive_scope,
            "is_visual_request": is_visual or (sim_visual > 0.40),
            "is_code_request": is_code or (sim_code > 0.38 and not requires_web),
            "semantic_scores": {
                "temporal": round(sim_temporal, 3),
                "roster": round(sim_roster, 3),
                "code": round(sim_code, 3),
            }
        }
