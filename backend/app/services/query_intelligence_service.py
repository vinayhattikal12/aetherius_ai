import re
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.conversation_state_service import ConversationStateService, TurnType
from backend.app.core.logging import logger


class ContextualQueryAnalysis(BaseModel):
    raw_query: str
    normalized_query: str
    canonical_prompt: str
    base_topic: Optional[str] = None
    turn_type: str = TurnType.NEW_TOPIC
    extracted_entities: List[str] = []
    references: Dict[str, Any] = {}
    extracted_constraints: Dict[str, Any] = {}
    is_visual: bool = False
    is_code: bool = False
    is_reasoning: bool = False
    is_search: bool = False
    is_fast: bool = False
    visual_prompt: Optional[str] = None
    complexity: float = 0.3
    primary_intent: str = "general_question"
    composite_intents: List[str] = []
    intent_scores: Dict[str, float] = {}


class QueryIntelligenceService:
    """
    Production-Grade Multi-Turn Query Intelligence, Generic Anaphora Resolver,
    Constraint Extractor, and Composite Intent Classifier (ChatGPT/Claude/Gemini architecture).
    """

    # Common Developer / General Orthographic Corrections & Shorthand
    NORMALIZATION_MAP = {
        "expalin": "explain",
        "strret": "street",
        "stret": "street",
        "diag": "diagram",
        "diagarm": "diagram",
        "diaram": "diagram",
        "img": "image",
        "imgs": "images",
        "pic": "picture",
        "pics": "pictures",
        "vis": "visual",
        "arch": "architecture",
        "architechture": "architecture",
        "auth": "authentication",
        "pg": "PostgreSQL",
        "postgres": "PostgreSQL",
        "db": "database",
        "py": "python",
        "pytn": "python",
        "ts": "TypeScript",
        "js": "JavaScript",
        "func": "function",
        "impl": "implementation",
        "alg": "algorithm",
        "algo": "algorithm",
        "peopel": "people",
        "computr": "computer",
        "artifical": "artificial",
        "artifitial": "artificial",
        "inteligence": "intelligence",
        "pls": "please",
        "plz": "please",
        "yestarday": "yesterday",
        "yestardays": "yesterday's",
    }

    INTENT_CENTROIDS = {
        "visual_generation": (
            "draw visual graphic picture diagram sketch render illustration "
            "visualize schematic flowchart wireframe architecture visual scene photo depiction"
        ),
        "code_generation": (
            "write implementation code function class python typescript javascript sql api "
            "database endpoint unit test bug error exception syntax refactor docker backend frontend"
        ),
        "deep_reasoning": (
            "step by step mathematical proof logical derivation algorithm analysis compare trade-offs "
            "solve optimize complexity root cause calculate deduce investigate architecture principles"
        ),
        "web_search": (
            "latest current today news stock price weather live release update who won sports "
            "trending market status recent events what happened"
        ),
        "fast_lookup": (
            "hello hi quick define what is translate summarize synonym short spell check help"
        ),
        "comparison": (
            "compare differences versus trade-offs pros and cons which is better versus benchmark"
        ),
        "data_analysis": (
            "calculate compute financial stats metrics growth interest rate aggregate average table"
        ),
    }

    _centroid_embeddings: Dict[str, List[float]] = {}

    @classmethod
    async def _get_centroid_embeddings(cls) -> Dict[str, List[float]]:
        if not cls._centroid_embeddings:
            for intent, text in cls.INTENT_CENTROIDS.items():
                cls._centroid_embeddings[intent] = await EmbeddingService.embed_text(text)
        return cls._centroid_embeddings

    @classmethod
    def normalize_text(cls, raw: str) -> str:
        """Correct typos, normalize shorthand, and standardize phrasing."""
        if not raw:
            return ""
        tokens = raw.strip().split()
        normalized_tokens = []
        for t in tokens:
            cleaned = re.sub(r"[^\w\-\./:]", "", t.lower())
            replacement = cls.NORMALIZATION_MAP.get(cleaned, t)
            normalized_tokens.append(replacement)
        return " ".join(normalized_tokens)

    @classmethod
    def extract_constraints(cls, text: str) -> Dict[str, Any]:
        """Extracts domain-agnostic user constraints (e.g. platform, license, temporal, budget)."""
        constraints: Dict[str, Any] = {}
        lower = text.lower()

        # License constraints
        if "open source" in lower or "foss" in lower:
            constraints["license"] = "open_source"
        elif "proprietary" in lower or "commercial" in lower:
            constraints["license"] = "commercial"

        # Platform / OS constraints
        for os_name in ["windows", "linux", "macos", "mac", "ios", "android", "docker"]:
            if re.search(rf"\b{os_name}\b", lower):
                constraints["platform"] = os_name

        # Memory / Hardware constraints
        ram_match = re.search(r"(\d+)\s*(gb|mb|tb)\s*(ram|vram|memory)?", lower)
        if ram_match:
            constraints["hardware_ram"] = f"{ram_match.group(1)}{ram_match.group(2).upper()}"

        # Temporal constraints
        if "yesterday" in lower:
            constraints["temporal"] = "yesterday"
        elif "today" in lower:
            constraints["temporal"] = "today"
        elif "recently" in lower or "latest" in lower:
            constraints["temporal"] = "latest"

        # Execution mode constraints
        if "local" in lower or "locally" in lower or "offline" in lower:
            constraints["execution_mode"] = "local"
        elif "cloud" in lower or "api" in lower:
            constraints["execution_mode"] = "cloud"

        return constraints

    @classmethod
    def resolve_anaphora(
        cls,
        query: str,
        history: List[Dict[str, str]]
    ) -> Tuple[str, Optional[str], Dict[str, Any]]:
        """
        Domain-Agnostic Multi-Turn Context & Anaphora Resolver:
        Resolves pronouns ('it', 'them', 'that', 'this', 'the previous one', 'both'),
        continuation queries ('compare them', 'which is faster', 'only open source', 'which support windows'),
        and accumulates conversation constraints.
        """
        normalized = cls.normalize_text(query)
        words = [w.lower() for w in re.findall(r"\b\w+\b", normalized)]
        deictic_words = {
            "it", "its", "this", "that", "these", "those", "above", "them", "again",
            "there", "same", "here", "both", "one", "two", "fastest", "cheapest", "better", "compare"
        }

        has_deictic = any(w in deictic_words for w in words)
        is_short = len(words) <= 7

        # Extract accumulated constraints from current and previous user turns
        accumulated_constraints = {}
        for turn in history:
            if turn.get("role") == "user":
                turn_constraints = cls.extract_constraints(turn.get("content", ""))
                accumulated_constraints.update(turn_constraints)

        current_constraints = cls.extract_constraints(normalized)
        accumulated_constraints.update(current_constraints)

        extracted_topic: Optional[str] = None
        extracted_user_query: Optional[str] = None

        if (has_deictic or is_short or bool(current_constraints)) and history:
            # 1. Search recent user queries for anchor subject
            for turn in reversed(history):
                if turn.get("role") == "user":
                    u_text = turn.get("content", "").strip()
                    if u_text and len(u_text) > 3 and u_text.lower() != normalized.lower():
                        # Don't pick short qualifier queries as the root topic
                        if len(u_text.split()) > 3:
                            extracted_user_query = u_text
                            break

            # 2. Search assistant responses for topic headers
            if not extracted_user_query:
                for turn in reversed(history):
                    if turn.get("role") == "assistant":
                        content = turn.get("content", "").strip()
                        if not content or content.startswith("🎨"):
                            continue
                        lines = [line.strip() for line in content.split("\n") if line.strip()]
                        for line in lines:
                            cleaned = re.sub(r"[#*`_]", "", line).strip()
                            cleaned = re.sub(r"^(overview:|detailed analysis:|here is|regarding|real-time intelligence:)\s*", "", cleaned, flags=re.IGNORECASE).strip()
                            if 3 < len(cleaned) < 120 and not cleaned.startswith("http") and not cleaned.startswith("["):
                                extracted_topic = cleaned
                                break
                        if extracted_topic:
                            break

        base_topic = extracted_user_query or extracted_topic
        canonical = normalized

        if base_topic:
            # Clean conversational conversational filler
            clean_modifier = re.sub(
                r"\b(i\s+am\s+asking|asking\s+for|what\s+about|how\s+about|can\s+you|please|tell\s+me)\b",
                "",
                normalized,
                flags=re.IGNORECASE
            ).strip()
            clean_modifier = re.sub(r"^[,\s]+|[,\s]+$", "", clean_modifier)

            if has_deictic or is_short or bool(current_constraints):
                canonical = f"{base_topic} ({clean_modifier if clean_modifier else normalized})".strip()

        return canonical, base_topic, accumulated_constraints

    @classmethod
    def synthesize_visual_prompt(cls, subject: str, context_topic: Optional[str] = None, style_preset: Optional[str] = None) -> str:
        """Domain-agnostic visual prompt synthesizer for image/diagram diffusion models."""
        raw = subject.strip()
        for pattern in [
            r"^with\s+(the\s+)?(help\s+of\s+)?(an?\s+)?(image|picture|diagram|illustration|visual)\s+(of\s+)?",
            r"^(generate|create|draw|paint|make|show|render)\s+(an?|the|its|this|a)?\s*(image|picture|diagram|photo|illustration|visual)?\s*(of|for|about)?\s*",
            r"^(draw|paint|sketch|visualize|illustrate|render)\s+(a|an|the|me)?\s*",
            r"^(explain|describe|show)\s+(to\s+me\s+)?",
            r"\s+(with|using)\s+(the\s+)?(help\s+of\s+)?(an?\s+)?(image|picture|diagram|illustration|visual)$"
        ]:
            raw = re.sub(pattern, "", raw, flags=re.IGNORECASE).strip()

        raw_norm = cls.normalize_text(raw)
        if raw_norm.lower() in ["its", "it", "this", "that", "these", ""] and context_topic:
            raw_norm = context_topic

        lower_core = raw_norm.lower()
        preset = style_preset or ("diagram" if any(k in lower_core for k in ["diagram", "architecture", "flowchart", "schematic", "system", "chart"]) else "photorealistic")

        style_modifiers = {
            "diagram": "clear architectural schematic diagram, high-resolution visual explanation, clean lines, labeled components, technical infographic, professional presentation style",
            "schematic": "detailed engineering schematic, blueprint styling, clean lines, technical drafting, precise typography and annotations",
            "photorealistic": "hyper-realistic 8k photograph, high dynamic range, intricate details, natural lighting, cinematic composition",
            "3d": "3D render, Octane render, smooth lighting, volumetric illumination, high fidelity, 4k texture",
            "concept_art": "digital concept art, vivid lighting, atmospheric matte painting, masterpiece illustration",
        }

        modifier = style_modifiers.get(preset.lower(), "")
        if modifier and modifier not in raw_norm:
            return f"{raw_norm}, {modifier}"
        return raw_norm

    @classmethod
    async def analyze_query(
        cls,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        workspace_slug: str = "general",
        conversation_state: Optional[Any] = None
    ) -> ContextualQueryAnalysis:
        """
        Generic End-to-End Query Semantic Intelligence:
        1. Normalizes typos and shorthand.
        2. Resolves multi-turn anaphora and accumulated constraints across ANY domain using ConversationStateService.
        3. Classifies conversational turn type (NEW_TOPIC, FOLLOW_UP, MODIFICATION, CLARIFICATION, CORRECTION, etc.).
        4. Computes semantic intent embeddings.
        5. Identifies composite intents.
        """
        history = conversation_history or []
        normalized = cls.normalize_text(user_message)

        # 1. Resolve anaphora, references, constraints and active topic
        canonical, base_topic, references, constraints = ConversationStateService.resolve_references(
            query=user_message,
            history=history,
            state=conversation_state
        )

        # 2. Classify conversational turn relation
        turn_type = ConversationStateService.classify_turn(
            current_message=user_message,
            history=history,
            current_topic=base_topic
        )

        # 3. Extract named entities and technologies
        extracted_entities_dict = ConversationStateService.extract_entities(user_message)
        extracted_entities = list(extracted_entities_dict.keys())

        # 4. Intent Centroids Cosine Proximity
        query_emb = await EmbeddingService.embed_text(canonical)
        centroids = await cls._get_centroid_embeddings()

        scores: Dict[str, float] = {}
        for intent, c_emb in centroids.items():
            sim = EmbeddingService.cosine_similarity(query_emb, c_emb)
            scores[intent] = round(sim, 3)

        # 5. Detect Capabilities & Intents
        lower_c = canonical.lower()
        is_visual = (
            scores.get("visual_generation", 0) > 0.65
            or any(k in lower_c for k in ["draw", "paint", "sketch", "visualize", "diagram", "picture", "generate image"])
        )
        is_code = (
            scores.get("code_generation", 0) > 0.60
            or any(k in lower_c for k in ["code", "function", "class", "python", "typescript", "javascript", "sql", "api", "bug", "refactor"])
        )
        is_reasoning = (
            scores.get("deep_reasoning", 0) > 0.60
            or any(k in lower_c for k in ["step by step", "proof", "derive", "algorithm", "trade-off", "why", "root cause"])
        )
        is_search = (
            scores.get("web_search", 0) > 0.58
            or any(k in lower_c for k in ["latest", "current", "today", "news", "recent", "who won", "weather", "released", "launch"])
        )
        is_fast = scores.get("fast_lookup", 0) > 0.65 and len(normalized.split()) <= 4

        # Composite Intents
        composite = []
        if is_search:
            composite.append("web_search")
        if is_code:
            composite.append("code_generation")
        if is_reasoning:
            composite.append("deep_reasoning")
        if is_visual:
            composite.append("visual_generation")
        if "compare" in lower_c or "versus" in lower_c or turn_type == TurnType.COMPARISON:
            composite.append("comparison")
        if not composite:
            composite.append("general_question")

        primary = composite[0] if composite else "general_question"
        complexity = round(min(0.95, max(0.15, (len(normalized.split()) * 0.03) + (0.3 if is_reasoning or is_code else 0.0))), 2)

        visual_prompt = cls.synthesize_visual_prompt(user_message, base_topic) if is_visual else None

        return ContextualQueryAnalysis(
            raw_query=user_message,
            normalized_query=normalized,
            canonical_prompt=canonical,
            base_topic=base_topic,
            turn_type=turn_type,
            extracted_entities=extracted_entities,
            references=references,
            extracted_constraints=constraints,
            is_visual=is_visual,
            is_code=is_code,
            is_reasoning=is_reasoning,
            is_search=is_search,
            is_fast=is_fast,
            visual_prompt=visual_prompt,
            complexity=complexity,
            primary_intent=primary,
            composite_intents=composite,
            intent_scores=scores
        )
