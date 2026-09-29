import re
import uuid
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel
from backend.app.schemas.intelligence import (
    ResolvedTask,
    ExecutionContext,
    TaskPlan,
    ResolvedEntity,
    InformationRequirement,
)
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
    resolved_task: Optional[ResolvedTask] = None


class QueryIntelligenceService:
    """
    Production-Grade Multi-Turn Query Intelligence, Generic Anaphora Resolver,
    Constraint Extractor, Composite Intent Classifier, and Task Plan Generator.
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
            "trending market status recent events what happened launched announced"
        ),
        "definition": (
            "what is define meaning explain concept overview definition introduction describe"
        ),
        "fast_lookup": (
            "hello hi quick translate short spell check ping help"
        ),
        "comparison": (
            "compare differences versus trade-offs pros and cons which is better versus benchmark"
        ),
        "data_analysis": (
            "calculate compute financial stats metrics growth interest rate aggregate average table compound"
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
    def detect_domain(cls, query: str, entities: List[str]) -> str:
        """Detects domain for semantic context (AI, finance, programming, research, general)."""
        lower = query.lower()
        if any(k in lower for k in ["stock", "market", "ticker", "mover", "finance", "compound interest", "growth rate", "revenue", "financials", "small cap"]):
            return "finance"
        if any(k in lower for k in ["python", "rust", "typescript", "javascript", "code", "sql", "api", "function", "class", "debug", "endpoint", "database"]):
            return "programming"
        if any(k in lower for k in ["model", "llm", "qwen", "llama", "deepseek", "gpt", "claude", "gemini", "neural", "transformer", "artificial intelligence", "ai"]):
            return "artificial_intelligence"
        if any(k in lower for k in ["paper", "research", "arxiv", "theorem", "hypothesis"]):
            return "research"
        return "general"

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
        conversation_state: Optional[Any] = None,
        request_id: Optional[str] = None
    ) -> ContextualQueryAnalysis:
        """
        Generic End-to-End Query Semantic Intelligence:
        1. Normalizes typos and shorthand.
        2. Resolves multi-turn anaphora and accumulated constraints with Entity Recency Stack.
        3. Classifies conversational turn type.
        4. Computes semantic intent embeddings.
        5. Builds authoritative TaskPlan and ResolvedTask.
        """
        history = conversation_history or []
        normalized = cls.normalize_text(user_message)

        # 1. Resolve anaphora, references, constraints, and active entities
        canonical, base_topic, references, constraints, resolved_entities = ConversationStateService.resolve_references(
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

        # 3. Extract named entities
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
            or any(k in lower_c for k in ["code", "function", "class", "python", "typescript", "javascript", "sql", "api", "bug", "refactor", "unit test"])
        )
        is_reasoning = (
            scores.get("deep_reasoning", 0) > 0.60
            or any(k in lower_c for k in ["step by step", "proof", "derive", "algorithm", "trade-off", "why", "root cause"])
        )
        # Search is triggered only for genuinely real-time / current inquiries
        is_search = (
            (scores.get("web_search", 0) > 0.60 or any(k in lower_c for k in ["latest", "current", "today", "yesterday", "news", "recent", "who won", "weather", "released", "launch"]))
            and not (lower_c.startswith("what is") and not any(t in lower_c for t in ["latest", "today", "yesterday", "current", "new"]))
        )
        is_fast = scores.get("fast_lookup", 0) > 0.70 and len(normalized.split()) <= 3 and not is_code and not is_search and not is_reasoning

        domain = cls.detect_domain(canonical, extracted_entities)

        # Composite Intents
        composite = []
        if is_search:
            composite.append("current_information" if "today" in lower_c or "yesterday" in lower_c or "latest" in lower_c else "web_search")
        if is_code:
            composite.append("code_generation")
        if is_reasoning:
            composite.append("deep_reasoning")
        if is_visual:
            composite.append("visual_generation")
        if "compare" in lower_c or "versus" in lower_c or turn_type == TurnType.COMPARISON:
            composite.append("comparison")
        if scores.get("definition", 0) > 0.55 or lower_c.startswith("what is") or lower_c.startswith("explain"):
            composite.append("definition" if lower_c.startswith("what is") else "explanation")
        if not composite:
            composite.append("general_question")

        primary = composite[0] if composite else "general_question"
        complexity = round(min(0.95, max(0.15, (len(normalized.split()) * 0.03) + (0.3 if is_reasoning or is_code else 0.0))), 2)

        visual_prompt = cls.synthesize_visual_prompt(user_message, base_topic) if is_visual else None

        # Build Task Plan
        task_plan = TaskPlan(
            requires_direct_model=True,
            requires_web_search=is_search,
            requires_rag=False,  # Set dynamically in pipeline if enabled
            requires_tools=[],
            requires_code_execution=is_code and ("run" in lower_c or "test" in lower_c or "execute" in lower_c),
            requires_agent_react=False,
            search_queries=[canonical] if is_search else []
        )

        if any(k in lower_c for k in ["calculate", "compound interest", "math", "+", "*", "/"]):
            task_plan.requires_tools.append("calculate_expression")

        resolved_task = ResolvedTask(
            request_id=request_id or str(uuid.uuid4()),
            raw_message=user_message,
            canonical_query=canonical,
            turn_type=turn_type,
            intent=primary,
            domain=domain,
            complexity=complexity,
            confidence=0.92,
            is_visual=is_visual,
            visual_prompt=visual_prompt,
            active_subject=base_topic,
            entities=resolved_entities,
            resolved_references=references,
            accumulated_constraints=constraints,
            temporal_context=constraints.get("temporal"),
            location_context=constraints.get("location"),
            plan=task_plan,
            workspace_slug=workspace_slug
        )

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
            intent_scores=scores,
            resolved_task=resolved_task
        )
