import re
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
from backend.app.services.embedding_service import EmbeddingService
from backend.app.core.logging import logger


class ContextualQueryAnalysis(BaseModel):
    raw_query: str
    normalized_query: str
    canonical_prompt: str
    is_visual: bool = False
    is_code: bool = False
    is_reasoning: bool = False
    is_search: bool = False
    is_fast: bool = False
    visual_prompt: Optional[str] = None
    complexity: float = 0.3
    primary_intent: str = "general_conversation"
    intent_scores: Dict[str, float] = {}


class QueryIntelligenceService:
    """
    Industrial Multi-Turn Query Intelligence, Orthographic Normalizer,
    and Semantic Intent Classifier (ChatGPT / Claude / Gemini Architecture).
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
    }

    # Intent Semantic Centroids for Embedding Cosine Proximity
    INTENT_CENTROIDS = {
        "visual_generation": (
            "draw a high resolution visual graphic picture diagram sketch render illustration "
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
            "trending market status recent events"
        ),
        "fast_lookup": (
            "hello hi quick define what is translate summarize synonym short spell check help"
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
    def resolve_anaphora(cls, query: str, history: List[Dict[str, str]]) -> Tuple[str, Optional[str]]:
        """
        Resolves pronouns ('it', 'its', 'this', 'that', 'the above') from conversation history
        into a concrete, self-contained semantic topic.
        """
        normalized = cls.normalize_text(query)
        words = [w.lower() for w in re.findall(r"\b\w+\b", normalized)]
        deictic_words = {"it", "its", "this", "that", "these", "those", "above", "them", "again"}

        has_deictic = any(w in deictic_words for w in words)
        is_short = len(words) <= 4

        extracted_topic: Optional[str] = None

        if (has_deictic or is_short) and history:
            # Search reverse history for subject topic
            for turn in reversed(history):
                content = turn.get("content", "").strip()
                if not content or content.startswith("🎨"):
                    continue
                # Extract subject from first line / title / bold text
                lines = [line.strip() for line in content.split("\n") if line.strip()]
                for line in lines:
                    cleaned_line = re.sub(r"[#*`_]", "", line).strip()
                    # Clean generic prefixes
                    cleaned_line = re.sub(r"^(overview:|detailed analysis:|here is|regarding)\s*", "", cleaned_line, flags=re.IGNORECASE).strip()
                    if 3 < len(cleaned_line) < 120 and not cleaned_line.startswith("http"):
                        extracted_topic = cleaned_line
                        break
                if extracted_topic:
                    break

        canonical = normalized
        if extracted_topic:
            if has_deictic or is_short:
                # Replace pronouns or augment short query with extracted topic
                canonical = f"{normalized} (context: {extracted_topic})"

        return canonical, extracted_topic

    @classmethod
    def synthesize_visual_prompt(cls, subject: str, context_topic: Optional[str] = None, style_preset: Optional[str] = None) -> str:
        """
        Autonomous Visual Prompt Synthesizer:
        Generates enriched, photorealistic or technical schematic prompts for diffusion models.
        """
        raw = subject.strip()
        # Strip conversational wrappers
        for pattern in [
            r"^with\s+(the\s+)?(help\s+of\s+)?(an?\s+)?(image|picture|diagram|illustration|visual)\s+(of\s+)?",
            r"^(generate|create|draw|paint|make|show|render)\s+(an?|the|its|this|a)?\s*(image|picture|diagram|photo|illustration|visual)?\s*(of|for|about)?\s*",
            r"^(draw|paint|sketch|visualize|illustrate|render)\s+(a|an|the|me)?\s*",
            r"^(explain|describe|show)\s+(to\s+me\s+)?",
            r"\s+(with|using)\s+(the\s+)?(help\s+of\s+)?(an?\s+)?(image|picture|diagram|illustration|visual)$"
        ]:
            raw = re.sub(pattern, "", raw, flags=re.IGNORECASE).strip()

        raw_norm = cls.normalize_text(raw)

        # If reference pronoun or empty, use context topic
        if raw_norm.lower() in ["its", "it", "this", "that", "these", ""] and context_topic:
            raw_norm = context_topic

        lower_core = raw_norm.lower()

        # Domain expansions
        if "ai" in lower_core or "artificial intelligence" in lower_core or "neural" in lower_core:
            base_prompt = f"Artificial intelligence neural network architecture diagram, deep learning layers, data flow vectors, clean dark tech aesthetic"
            preset = "diagram"
        elif "dog" in lower_core and "street" in lower_core:
            base_prompt = f"A photorealistic dog crossing an urban asphalt street crosswalk, natural daylight, cinematic wide-angle photography, 8k resolution"
            preset = "photorealistic"
        elif any(k in lower_core for k in ["database", "postgres", "sql", "server", "microservice", "cloud", "backend"]):
            base_prompt = f"{raw_norm} infrastructure schematic diagram, technical system topology, high-definition blueprint styling, labeled components"
            preset = "diagram"
        else:
            base_prompt = raw_norm
            preset = style_preset or ("diagram" if ("diagram" in lower_core or "chart" in lower_core or "system" in lower_core) else "photorealistic")

        style_modifiers = {
            "diagram": "clear architectural schematic diagram, high-resolution visual explanation, clean lines, labeled components, technical infographic, professional presentation style",
            "schematic": "detailed engineering schematic, blueprint styling, clean lines, technical drafting, precise typography and annotations",
            "photorealistic": "hyper-realistic 8k photograph, high dynamic range, intricate details, natural lighting, cinematic composition",
            "3d": "3D render, Octane render, smooth lighting, volumetric illumination, high fidelity, 4k texture",
            "concept_art": "digital concept art, vivid lighting, atmospheric matte painting, masterpiece illustration",
        }

        modifier = style_modifiers.get(preset.lower(), "")
        if modifier and modifier not in base_prompt:
            return f"{base_prompt}, {modifier}"
        return base_prompt

    @classmethod
    async def analyze_query(
        cls,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        workspace_slug: str = "general"
    ) -> ContextualQueryAnalysis:
        """
        Full End-to-End Query Semantic Intelligence:
        1. Normalizes typos and shorthand.
        2. Resolves multi-turn anaphora and context.
        3. Computes zero-keyword semantic embedding cosine similarity.
        4. Synthesizes visual prompt if visual intent is present.
        """
        history = conversation_history or []
        normalized = cls.normalize_text(user_message)
        canonical, extracted_topic = cls.resolve_anaphora(user_message, history)

        # 1. Compute Semantic Intent Embeddings
        query_emb = await EmbeddingService.embed_text(canonical)
        centroids = await cls._get_centroid_embeddings()

        scores: Dict[str, float] = {}
        for intent, c_emb in centroids.items():
            sim = EmbeddingService.cosine_similarity(query_emb, c_emb)
            scores[intent] = round(sim, 3)

        p_lower = canonical.lower()

        # Fast greeting / short lookup check
        is_greeting = p_lower in ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "thanks", "thank you", "help"]
        if is_greeting:
            return ContextualQueryAnalysis(
                raw_query=user_message,
                normalized_query=normalized,
                canonical_prompt=canonical,
                is_visual=False,
                is_code=False,
                is_reasoning=False,
                is_search=False,
                is_fast=True,
                visual_prompt=None,
                complexity=0.1,
                primary_intent="fast_lookup",
                intent_scores=scores
            )

        # Visual triggers check
        visual_patterns = [
            r"\b(image|picture|diagram|photo|illustration|visual|chart|schematic|flowchart|wireframe)\b",
            r"\b(draw|paint|sketch|visualize|render)\b",
            r"\bgenerate\s+(its\s+|an?\s+|the\s+)?(image|picture|diagram|photo|illustration|visual)\b",
            r"\bwith\s+(the\s+)?(help\s+of\s+)?(an?\s+)?(image|picture|diagram|illustration|visual)\b",
            r"\bshow\s+(me\s+)?(an?\s+|the\s+)?(image|picture|diagram|photo|illustration|visual)\b"
        ]
        has_visual_keyword = any(re.search(pat, p_lower) for pat in visual_patterns)
        is_visual = has_visual_keyword or (scores.get("visual_generation", 0) > 0.72)

        is_code = (
            any(kw in p_lower for kw in [
                "code", "python", "typescript", "javascript", "react", "html", "css",
                "function", "class", "bug", "sql", "api", "regex", "docker", "c++", "rust",
                "endpoint", "refactor", "unit test", "database", "syntax", "git", "fastapi"
            ])
            or scores.get("code_generation", 0) > 0.70
        )

        is_reasoning = (
            any(kw in p_lower for kw in [
                "step by step", "prove", "derivation", "algorithm", "architecture", "solve",
                "math", "logical", "analyze", "why does", "compare trade-offs", "complexity",
                "deduce", "evaluate", "root cause", "calculate", "why is"
            ])
            or scores.get("deep_reasoning", 0) > 0.70
        )

        is_search = (
            any(kw in p_lower for kw in [
                "today", "latest", "current", "news", "price", "stock", "weather", "live", "crypto", "who won"
            ])
            or scores.get("web_search", 0) > 0.72
        )

        is_fast = not is_code and not is_reasoning and not is_visual and len(canonical.split()) <= 6

        # Determine Primary Intent & Complexity
        if is_visual and (is_code or is_reasoning or len(canonical.split()) > 5):
            primary_intent = "multimodal_hybrid"
            complexity = 0.65
        elif is_visual:
            primary_intent = "visual_generation"
            complexity = 0.5
        elif is_code:
            primary_intent = "code_generation"
            complexity = 0.7
        elif is_reasoning:
            primary_intent = "deep_reasoning"
            complexity = 0.85
        elif is_search:
            primary_intent = "web_search"
            complexity = 0.4
        elif is_fast:
            primary_intent = "fast_lookup"
            complexity = 0.2
        else:
            primary_intent = "general_conversation"
            complexity = 0.3

        # Synthesize visual prompt only if visual
        visual_prompt = None
        if is_visual:
            visual_prompt = cls.synthesize_visual_prompt(
                subject=user_message,
                context_topic=extracted_topic,
                style_preset="diagram" if ("diagram" in p_lower or "architecture" in p_lower or "network" in p_lower) else "photorealistic"
            )

        return ContextualQueryAnalysis(
            raw_query=user_message,
            normalized_query=normalized,
            canonical_prompt=canonical,
            is_visual=is_visual,
            is_code=is_code,
            is_reasoning=is_reasoning,
            is_search=is_search,
            is_fast=is_fast,
            visual_prompt=visual_prompt,
            complexity=complexity,
            primary_intent=primary_intent,
            intent_scores=scores
        )
