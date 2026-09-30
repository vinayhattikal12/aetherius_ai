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
    Engineered for sub-millisecond execution with zero blocking network overhead.
    """

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
            "trending market status recent events what happened launched announced 2024 2025 2026 search find lookup info"
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

    _centroid_embeddings: Dict[str, List[float]] = {
        intent: EmbeddingService._generate_semantic_vector(text)
        for intent, text in INTENT_CENTROIDS.items()
    }

    SEMANTIC_ANCHORS = {
        "stable_conceptual": (
            "definition define overview explanation meaning concept fundamentals syntax components "
            "variables functions recursion loops data structure algorithm programming tutorial useful "
            "purpose benefits why advantages principles theoretical virtual dom primitives build advice tips introduction philosophy"
        ),
        "volatile_temporal": (
            "latest current recently today yesterday upcoming breaking news update changelog "
            "changes new features status announcement release launched launch roadmap state of ecosystem "
            "catch me up diff new in version modern trends price who won election score weather live"
        ),
        "entity_fact": (
            "company organization business startup firm person biography founder ceo net worth "
            "headquarters revenue valuation website profile products services client employee location tell me about"
        ),
    }

    _anchor_embeddings: Dict[str, List[float]] = {
        k: EmbeddingService._generate_semantic_vector(v)
        for k, v in SEMANTIC_ANCHORS.items()
    }

    @classmethod
    def normalize_text(cls, raw: str) -> str:
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

        # 3. Extract named entities with typing
        extracted_entities_dict = ConversationStateService.extract_entities(user_message)
        extracted_entities = list(extracted_entities_dict.keys())
        has_real_world_entity = any(
            info.get("type") in ["organization", "person", "named_entity"]
            for info in extracted_entities_dict.values()
        )

        # 4. Instant Intent Centroids Cosine Proximity (<0.05ms)
        query_emb = EmbeddingService._generate_semantic_vector(canonical)

        scores: Dict[str, float] = {}
        for intent, c_emb in cls._centroid_embeddings.items():
            sim = EmbeddingService.cosine_similarity(query_emb, c_emb)
            scores[intent] = round(sim, 3)

        # 5. Detect Capabilities & Intents
        lower_c = canonical.lower().strip()
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

        # 6. Semantic Volatility & Knowledge Layer Proximity
        s_sim = EmbeddingService.cosine_similarity(query_emb, cls._anchor_embeddings["stable_conceptual"])
        v_sim = EmbeddingService.cosine_similarity(query_emb, cls._anchor_embeddings["volatile_temporal"])
        e_sim = EmbeddingService.cosine_similarity(query_emb, cls._anchor_embeddings["entity_fact"])

        # Knowledge Volatility & Freshness Signal (paraphrases, ecosystem shifts, live data)
        is_volatile = (v_sim > s_sim and v_sim > 0.05) or (v_sim > 0.18)

        # Entity Fact & Grounding Requirement (specific factual lookup for companies, persons, or real-world entities)
        has_org_or_person = any(
            info.get("type") in ["organization", "person", "named_entity"]
            for info in extracted_entities_dict.values()
        )
        is_entity_lookup = (
            (has_org_or_person or any(k in lower_c for k in ["solutions", "technologies", "inc", "ltd", "corp"]))
            and (
                any(k in lower_c for k in ["tell me about", "who is", "ceo", "founder", "net worth", "headquarters", "revenue", "overview of", "profile of", "services", "products of"])
                or (e_sim > s_sim and e_sim > 0.12)
            )
            and not any(k in lower_c for k in ["how to", "how do i", "how can i", "i want to", "steps to", "guide to", "advice on", "tips for"])
        )

        is_entity_query = is_entity_lookup
        is_definition_question = (
            lower_c.startswith("what is") or lower_c.startswith("explain") or lower_c.startswith("who is") or lower_c.startswith("define")
        )

        # Stable Conceptual / Advisory Filter (programming fundamentals, tutorials, conceptual architecture)
        is_conceptual_explanation = (
            (s_sim >= v_sim)
            and not is_volatile
            and not is_entity_lookup
        ) or (
            any(lower_c.startswith(k) for k in ["how to", "how can i", "how do i", "i want to", "steps to", "guide to", "why is", "what is a", "what are", "explain how"])
            and not is_volatile
            and not is_entity_lookup
        )

        # Final Search Determination: Provider-independent intelligent search decision
        is_search = (is_volatile or is_entity_lookup or scores.get("web_search", 0) > 0.65) and not is_conceptual_explanation

        is_fast = (
            scores.get("fast_lookup", 0) > 0.70 
            and len(normalized.split()) <= 3 
            and not is_code 
            and not is_search 
            and not is_reasoning
            and not is_definition_question
        )

        domain = cls.detect_domain(canonical, extracted_entities)

        # Composite Intents
        composite = []
        if is_entity_query:
            composite.append("entity_overview")
        if is_definition_question or scores.get("definition", 0) > 0.40:
            if not is_entity_query:
                composite.append("definition" if (lower_c.startswith("what is") or lower_c.startswith("define")) else "explanation")
        if is_search and not is_entity_query:
            composite.append("current_information" if any(k in lower_c for k in ["today", "yesterday", "latest", "2025", "2026"]) else "web_search")
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

        is_rag_required = any(
            k in lower_c for k in [
                "document", "documents", "file", "files", "pdf", "knowledge base",
                "in the doc", "in the file", "our policy", "guidelines", "handbook",
                "architecture spec", "system architecture", "according to", "in our knowledge",
                "uploaded"
            ]
        ) and not is_fast

        # Build Task Plan
        task_plan = TaskPlan(
            requires_direct_model=True,
            requires_web_search=is_search,
            requires_rag=is_rag_required,
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
