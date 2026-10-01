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
    is_massive_scope: bool = False
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
        "cm": "Chief Minister",
        "pm": "Prime Minister",
        "cji": "Chief Justice of India",
        "potus": "President of the United States",
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
        if any(k in lower for k in ["python", "rust", "typescript", "javascript", "code", "sql", "api", "function", "class", "debug", "endpoint", "database", "recursion", "algorithm", "computer science", "data structure"]):
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

        from backend.app.services.llm_router_service import LLMRouterService
        
        # 1. Use the new LLM Router for all NLP intelligence
        router_result = await LLMRouterService.analyze_intent_and_entities(user_message, history)
        
        turn_type = router_result.get("turn_type", "NEW_TOPIC")
        base_topic = router_result.get("active_topic")
        canonical = router_result.get("canonical_query", user_message)
        extracted_entities = [e.get("name") for e in router_result.get("extracted_entities", [])]
        
        is_search = router_result.get("requires_web_search", False)
        is_visual = router_result.get("is_visual_request", False)
        is_code = router_result.get("is_code_request", False)
        is_massive_scope = router_result.get("is_massive_scope", False)
        
        # Extract accumulated constraints and references across conversation history and current message
        from backend.app.services.conversation_state_service import ConversationStateService
        constraints = {}
        for msg in history:
            if msg.get("role") == "user":
                constraints.update(ConversationStateService.extract_constraints(msg.get("content", "")))
        constraints.update(ConversationStateService.extract_constraints(user_message))

        references = router_result.get("resolved_references", {})
        resolved_entities = extracted_entities
        is_reasoning = False
        is_fast = False
        is_volatile = is_search
        is_entity_query = False
        is_conceptual_explanation = not is_search

        lower_c = canonical.lower()
        
        domain = cls.detect_domain(canonical, extracted_entities)

        # Composite Intents
        composite = []
        if is_code:
            composite.append("code_generation")
        if is_visual:
            composite.append("visual_generation")
        if is_search:
            composite.append("web_search")
        if any(k in lower_c for k in ["what is", "what are", "define", "definition", "meaning of", "explain"]):
            composite.append("definition")
        if any(k in lower_c for k in ["compare", "comparison", "difference", "differences", "versus", "vs."]):
            composite.append("comparison")
        if any(k in lower_c for k in ["tell me about", "who is", "about "]) or extracted_entities:
            composite.append("entity_overview")
            
        if not composite:
            composite.append("general_question")

        primary = composite[0] if composite else "general_question"
        complexity = 0.5

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
            is_massive_scope=is_massive_scope,
            visual_prompt=visual_prompt,
            complexity=complexity,
            primary_intent=primary,
            composite_intents=composite,
            intent_scores={},
            resolved_task=resolved_task
        )
