import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.conversation import ConversationState
from backend.app.core.logging import logger


class TurnType:
    NEW_TOPIC = "NEW_TOPIC"
    FOLLOW_UP = "FOLLOW_UP"
    MODIFICATION = "MODIFICATION"
    CLARIFICATION = "CLARIFICATION"
    CORRECTION = "CORRECTION"
    EXPANSION = "EXPANSION"
    COMPARISON = "COMPARISON"
    CONTINUATION = "CONTINUATION"
    CONFIRMATION = "CONFIRMATION"
    TASK_CONTINUATION = "TASK_CONTINUATION"


class ConversationStateService:
    """
    Production-Grade Conversation Intelligence & Turn State Engine.
    Handles:
    - 10-class Turn Classification (ChatGPT/Claude/Gemini conversational state machine)
    - Generic multi-turn anaphora & semantic reference resolution (it, them, that, previous one, both, etc.)
    - Accumulated constraint tracking across arbitrary domains
    - Persistent PostgreSQL ConversationState lifecycle management
    """

    PRONOUNS = {"it", "its", "they", "them", "this", "that", "these", "those", "there", "here"}
    PRO_FORMS = {"previous one", "the former", "the latter", "the first one", "the second", "another one", "the same", "both", "all of them", "each"}

    CORRECTION_PATTERNS = [
        r"^(no|nope|not that|actually|i meant|i mean|that's wrong|thats wrong|incorrect|you misunderstood)\b",
        r"\b(instead of|rather than|not what i asked|i didn't ask)\b",
    ]

    MODIFICATION_PATTERNS = [
        r"^(now|instead|switch to|change to|convert to|make it|rewrite in|in|using|with)\b",
        r"\b(in python|in rust|in typescript|in go|in java|in cpp|in c\+\+|in c#|as async|using async|with error handling|with tests|as a class|as a function)\b",
        r"\b(faster|shorter|more concise|detailed|simpler|cleaner)\b",
    ]

    EXPANSION_PATTERNS = [
        r"^(give\s+(\d+|more|another)\s+examples?|show\s+more|elaborate|expand|tell\s+me\s+more|what\s+else|more\s+details|deep\s+dive)\b",
        r"\b(edge cases?|additional|more scenarios?|extra examples?)\b",
    ]

    COMPARISON_PATTERNS = [
        r"\b(compare|versus|vs\.?|difference between|pros and cons|trade-offs|which is better|how does (it|this) compare)\b",
    ]

    CLARIFICATION_PATTERNS = [
        r"^(why|how\s+so|what\s+does\s+that\s+mean|why\s+is\s+that|can\s+you\s+explain\s+why|how\s+come|what\s+do\s+you\s+mean)\b",
    ]

    CONTINUATION_PATTERNS = [
        r"^(continue|go\s+on|proceed|next\s+step|next|what\s+next|keep\s+going|and\s+then)\b",
    ]

    CONFIRMATION_PATTERNS = [
        r"^(ok|okay|got\s+it|understood|makes\s+sense|sounds\s+good|looks\s+good|perfect|thanks|thank\s+you|yes|cool|great|awesome)\b",
    ]

    @classmethod
    def classify_turn(
        cls,
        current_message: str,
        history: List[Dict[str, str]],
        current_topic: Optional[str] = None
    ) -> str:
        """
        Classifies the turn into one of the 10 standard conversation turn types.
        """
        clean_text = current_message.strip().lower()
        words = re.findall(r"\b\w+\b", clean_text)

        if not history:
            return TurnType.NEW_TOPIC

        # 1. Corrections (User is fixing misunderstanding)
        for pat in cls.CORRECTION_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return TurnType.CORRECTION

        # 2. Confirmations (User acknowledges or praises)
        for pat in cls.CONFIRMATION_PATTERNS:
            if re.match(pat, clean_text, re.IGNORECASE) and len(words) <= 5:
                return TurnType.CONFIRMATION

        # 3. Continuations (User asks to proceed / next step)
        for pat in cls.CONTINUATION_PATTERNS:
            if re.match(pat, clean_text, re.IGNORECASE) and len(words) <= 5:
                return TurnType.CONTINUATION

        # 4. Clarifications (User asks why / meaning of previous statement)
        for pat in cls.CLARIFICATION_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return TurnType.CLARIFICATION

        # 5. Comparisons (Comparing entities)
        for pat in cls.COMPARISON_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return TurnType.COMPARISON

        # 6. Expansions (Asking for more examples / deeper look)
        for pat in cls.EXPANSION_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return TurnType.EXPANSION

        # 7. Modifications (Refining implementation, language, or parameters)
        for pat in cls.MODIFICATION_PATTERNS:
            if re.search(pat, clean_text, re.IGNORECASE):
                return TurnType.MODIFICATION

        # 8. Follow-up vs New Topic
        # Deictic references or short qualifier messages indicate follow-up
        has_pronoun = any(p in words for p in cls.PRONOUNS)
        has_pro_form = any(pf in clean_text for pf in cls.PRO_FORMS)
        is_short_fragment = len(words) <= 6

        if (has_pronoun or has_pro_form or is_short_fragment) and current_topic:
            return TurnType.FOLLOW_UP

        # If length is substantial and has no relation to current topic, consider new topic
        if len(words) > 10 and not has_pronoun and not has_pro_form:
            return TurnType.NEW_TOPIC

        return TurnType.FOLLOW_UP if current_topic else TurnType.NEW_TOPIC

    @classmethod
    def extract_entities(cls, text: str) -> Dict[str, Dict[str, Any]]:
        """
        Domain-agnostic entity and technical concept extractor.
        Identifies libraries, languages, tools, frameworks, metrics, and capitalized entities.
        """
        entities: Dict[str, Dict[str, Any]] = {}
        if not text:
            return entities

        # Capitalized multi-word or single-word entities (excluding sentence start)
        raw_words = text.split()
        for idx, w in enumerate(raw_words):
            cleaned = re.sub(r"[^\w\-\.]", "", w)
            if cleaned and cleaned[0].isupper() and idx > 0 and len(cleaned) > 2:
                entities[cleaned] = {"type": "named_entity", "mentions": 1}

        # Known common programming languages, systems, and concepts
        known_tech = [
            "python", "typescript", "javascript", "rust", "golang", "go", "java", "c++", "c#", "scala",
            "postgresql", "postgres", "mysql", "sqlite", "redis", "mongodb", "cassandra", "clickhouse",
            "fastapi", "django", "flask", "express", "react", "nextjs", "vue", "angular", "node",
            "docker", "kubernetes", "linux", "windows", "macos", "aws", "gcp", "azure", "ollama",
            "pgvector", "faiss", "qdrant", "weaviate", "pinecone", "chroma"
        ]

        lower_text = text.lower()
        for tech in known_tech:
            if re.search(rf"\b{re.escape(tech)}\b", lower_text):
                formatted_name = tech.upper() if tech in ["aws", "gcp", "sql", "api"] else tech.capitalize()
                if tech in ["postgresql", "postgres"]:
                    formatted_name = "PostgreSQL"
                elif tech in ["typescript", "javascript"]:
                    formatted_name = "TypeScript" if tech == "typescript" else "JavaScript"
                elif tech == "pgvector":
                    formatted_name = "pgvector"
                entities[formatted_name] = {"type": "technology", "mentions": 1}

        return entities

    @classmethod
    def extract_constraints(cls, text: str) -> Dict[str, Any]:
        """
        Extracts domain-agnostic constraints (license, language, OS, hardware, format, etc.).
        """
        constraints: Dict[str, Any] = {}
        lower = text.lower()

        # License
        if "open source" in lower or "foss" in lower or "apache" in lower or "mit" in lower:
            constraints["license"] = "open_source"
        elif "proprietary" in lower or "commercial" in lower:
            constraints["license"] = "commercial"

        # Languages
        for lang in ["python", "rust", "typescript", "javascript", "go", "golang", "java", "c++", "c#", "sql"]:
            if re.search(rf"\b{re.escape(lang)}\b", lower):
                constraints["language"] = "golang" if lang == "go" else lang

        # Platforms / OS
        for platform in ["windows", "linux", "macos", "mac", "ios", "android", "docker", "kubernetes"]:
            if re.search(rf"\b{re.escape(platform)}\b", lower):
                constraints["platform"] = platform

        # Hardware / Memory limits
        ram_match = re.search(r"(\d+)\s*(gb|mb|tb)\s*(ram|vram|memory)?", lower)
        if ram_match:
            constraints["memory_limit"] = f"{ram_match.group(1)}{ram_match.group(2).upper()}"

        # Temporal
        if "today" in lower or "latest" in lower or "current" in lower:
            constraints["temporal"] = "latest"
        elif "yesterday" in lower:
            constraints["temporal"] = "yesterday"

        # Format constraints
        if "json" in lower:
            constraints["format"] = "json"
        elif "table" in lower or "markdown table" in lower:
            constraints["format"] = "table"
        elif "bullet" in lower or "bullet points" in lower:
            constraints["format"] = "bullet_points"
        elif "step by step" in lower:
            constraints["format"] = "step_by_step"

        return constraints

    @classmethod
    def resolve_references(
        cls,
        query: str,
        history: List[Dict[str, str]],
        state: Optional[ConversationState] = None
    ) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """
        Generic Semantic Anaphora Resolver:
        Resolves pronouns ('it', 'them', 'that', 'this', 'the previous one', 'both'),
        elliptical queries ('in python', 'why?', 'how to fix it?', 'make it faster'),
        and returns:
        (canonical_resolved_query, active_topic, updated_references, updated_constraints)
        """
        words = re.findall(r"\b\w+\b", query.lower())
        has_pronoun = any(w in cls.PRONOUNS for w in words)
        has_pro_form = any(pf in query.lower() for pf in cls.PRO_FORMS)
        is_short = len(words) <= 7

        # Start with state values if present
        active_topic = state.topic if state and state.topic else None
        accumulated_constraints = dict(state.constraints) if state and state.constraints else {}
        references = dict(state.references) if state and state.references else {}

        # Accumulate constraints from user turns in history
        if history:
            for turn in history:
                if turn.get("role") == "user":
                    turn_constraints = cls.extract_constraints(turn.get("content", ""))
                    accumulated_constraints.update(turn_constraints)

        # Update constraints from current query
        curr_constraints = cls.extract_constraints(query)
        accumulated_constraints.update(curr_constraints)

        # If we have no topic yet from state, inspect conversation history
        if not active_topic and history:
            # 1. First look for descriptive user queries (>3 words)
            for turn in reversed(history):
                if turn.get("role") == "user":
                    u_text = turn.get("content", "").strip()
                    if u_text and len(u_text.split()) > 3 and u_text.lower() != query.lower():
                        active_topic = u_text
                        break
            # 2. Fallback to any user query
            if not active_topic:
                for turn in reversed(history):
                    if turn.get("role") == "user":
                        u_text = turn.get("content", "").strip()
                        if u_text and len(u_text.split()) > 1 and u_text.lower() != query.lower():
                            active_topic = u_text
                            break
            # 3. Fallback to assistant headers
            if not active_topic:
                for turn in reversed(history):
                    if turn.get("role") == "assistant":
                        lines = [l.strip() for l in turn.get("content", "").split("\n") if l.strip()]
                        for line in lines:
                            cleaned = re.sub(r"[#*`_]", "", line).strip()
                            cleaned = re.sub(r"^(overview:|detailed analysis:|here is|regarding|solution:)\s*", "", cleaned, flags=re.IGNORECASE).strip()
                            if 3 < len(cleaned) < 120 and not cleaned.startswith("http"):
                                active_topic = cleaned
                                break
                        if active_topic:
                            break

        # Extract entities from history to populate reference pointers
        if history:
            for turn in reversed(history[-4:]):
                t_entities = cls.extract_entities(turn.get("content", ""))
                for ent in t_entities:
                    if "latest_entity" not in references:
                        references["latest_entity"] = ent
                    references[ent.lower()] = ent

        if active_topic:
            references["it"] = active_topic
            references["this"] = active_topic
            references["that"] = active_topic
            references["subject"] = active_topic

        # Build canonical prompt
        canonical = query
        if (has_pronoun or has_pro_form or is_short or curr_constraints) and active_topic:
            # Clean conversational wrappers
            clean_modifier = re.sub(
                r"\b(i\s+am\s+asking|asking\s+for|what\s+about|how\s+about|can\s+you|please|tell\s+me)\b",
                "",
                query,
                flags=re.IGNORECASE
            ).strip()
            clean_modifier = re.sub(r"^[,\s]+|[,\s]+$", "", clean_modifier)

            if clean_modifier and clean_modifier.lower() != active_topic.lower():
                canonical = f"{active_topic} — {clean_modifier}"
            else:
                canonical = active_topic

        return canonical, active_topic or query, references, accumulated_constraints

    @classmethod
    async def get_or_create_state(
        cls,
        db: AsyncSession,
        conversation_id: str
    ) -> ConversationState:
        """Loads existing ConversationState from database or creates an empty one."""
        result = await db.execute(
            select(ConversationState).where(ConversationState.conversation_id == conversation_id)
        )
        state = result.scalars().first()
        if not state:
            state = ConversationState(
                conversation_id=conversation_id,
                topic=None,
                subtopics=[],
                active_intent="general_question",
                turn_type=TurnType.NEW_TOPIC,
                entities={},
                references={},
                constraints={},
                previous_results=[],
                turn_count=0
            )
            db.add(state)
            await db.commit()
            await db.refresh(state)
        return state

    @classmethod
    async def update_state_turn(
        cls,
        db: AsyncSession,
        conversation_id: str,
        user_message: str,
        turn_type: str,
        resolved_topic: str,
        canonical_prompt: str,
        entities: Dict[str, Any],
        references: Dict[str, Any],
        constraints: Dict[str, Any],
        assistant_summary: Optional[str] = None
    ) -> ConversationState:
        """Persists the turn state back into PostgreSQL."""
        state = await cls.get_or_create_state(db, conversation_id)

        state.turn_count += 1
        state.turn_type = turn_type
        if not state.topic or turn_type == TurnType.NEW_TOPIC:
            state.topic = resolved_topic
        elif resolved_topic and resolved_topic != state.topic:
            if resolved_topic not in state.subtopics:
                sub = list(state.subtopics)
                sub.append(resolved_topic)
                state.subtopics = sub[-10:]

        # Merge entities
        merged_entities = dict(state.entities)
        for k, v in entities.items():
            if k in merged_entities:
                merged_entities[k]["mentions"] = merged_entities[k].get("mentions", 1) + 1
            else:
                merged_entities[k] = v
        state.entities = merged_entities

        # Update references & constraints
        merged_refs = dict(state.references)
        merged_refs.update(references)
        state.references = merged_refs

        merged_constraints = dict(state.constraints)
        merged_constraints.update(constraints)
        state.constraints = merged_constraints

        state.last_user_goal = canonical_prompt

        # Append assistant result summary if provided
        if assistant_summary:
            prev = list(state.previous_results)
            prev.append({
                "turn": state.turn_count,
                "topic": resolved_topic,
                "summary": assistant_summary[:300]
            })
            state.previous_results = prev[-8:]

        db.add(state)
        await db.commit()
        await db.refresh(state)
        return state
