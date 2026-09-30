import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.conversation import ConversationState
from backend.app.schemas.intelligence import ResolvedEntity
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
    - Generic multi-turn anaphora & entity reference resolution (it -> entity, them -> entities)
    - Natural canonical query reconstruction (replacing awkward header strings)
    - Accumulated constraint tracking across arbitrary domains
    - Persistent PostgreSQL ConversationState lifecycle management
    """

    PRONOUNS = {"it", "its", "they", "them", "this", "that", "these", "those", "there", "here"}
    PRO_FORMS = {
        "previous one", "the former", "the latter", "the first one", "the second one",
        "the second", "the first", "another one", "the same", "both", "all of them", "each"
    }

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
        r"\b(compare|versus|vs\.?|difference between|pros and cons|trade-offs|which is (better|easier|faster|cheaper|simpler|more popular)|how does (it|this) compare)\b",
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
        has_pronoun = any(p in words for p in cls.PRONOUNS)
        has_pro_form = any(pf in clean_text for pf in cls.PRO_FORMS)
        
        # Check if the text is a greeting
        is_greeting = clean_text in ["hi", "hello", "hey", "heyy", "ping", "morning", "who are you"]

        if is_greeting:
            return TurnType.NEW_TOPIC

        # If it has pronouns or pro-forms, it's referring to the past
        if (has_pronoun or has_pro_form) and current_topic:
            return TurnType.FOLLOW_UP

        # If it's a very short fragment (<= 6 words) BUT it introduces a completely new standalone question (like "what is X"), it might be a new topic.
        # We check for generic standalone question starters
        is_standalone_question = re.match(r"^(what is|who is|explain|define|tell me about)\b", clean_text, re.IGNORECASE)

        if len(words) <= 6 and current_topic and not is_standalone_question:
            return TurnType.FOLLOW_UP

        return TurnType.NEW_TOPIC

    @classmethod
    def clean_subject_name(cls, raw: str) -> str:
        """Strips conversational wrappers like 'tell me about', 'what is', etc. to yield pure subject."""
        cleaned = raw.strip()
        patterns = [
            r"^(tell\s+me\s+about|what\s+is|who\s+is|explain|describe|show\s+me|overview\s+of|how\s+about|what\s+are)\s+",
            r"\s*\?+$"
        ]
        for pat in patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned

    @classmethod
    def extract_entities(cls, text: str) -> Dict[str, Dict[str, Any]]:
        """
        Domain-agnostic entity and technical concept extractor.
        Identifies organizations/companies, people, products, AI models, languages, tools, frameworks, and concepts.
        """
        entities: Dict[str, Dict[str, Any]] = {}
        if not text:
            return entities

        # 1. AI Models pattern (e.g., Qwen 3, Llama 3.2, DeepSeek R1, GPT-4o, Claude 3.5, Mistral, Phi)
        model_matches = re.findall(
            r"\b(qwen\s*[\d\.\-]+[a-z]*|llama\s*[\d\.\-]+[a-z]*|deepseek\s*[\w\.\-]+|gpt\-?[\w\.\-]+|claude\s*[\d\.\-]+|gemini\s*[\d\.\-]+|mistral\s*[\w\.\-]+|phi\s*[\d\.\-]+)\b",
            text,
            flags=re.IGNORECASE
        )
        for m in model_matches:
            name = m.strip()
            formatted = " ".join([part.capitalize() if not part.isdigit() else part for part in name.split()])
            entities[formatted] = {"type": "model", "mentions": 1}

        # 2. General concepts (AI, Machine Learning, Deep Learning, etc.)
        if re.search(r"\b(artificial intelligence|machine learning|deep learning|computer vision|nlp|natural language processing)\b", text, flags=re.IGNORECASE):
            entities["Artificial Intelligence"] = {"type": "concept", "mentions": 1}

        # 3. Known programming languages, systems, and tools
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

        # 4. Pattern-based & Known Global Organizations
        known_orgs = [
            "google", "microsoft", "apple", "openai", "anthropic",
            "meta", "nvidia", "amazon", "tesla", "oracle", "ibm", "intel", "salesforce", "adobe",
            "snowflake", "databricks", "stripe", "uber", "spacex", "deepmind", "alibaba", "bytedance",
            "github", "gitlab", "huggingface", "mistral ai", "stability ai"
        ]
        for org in known_orgs:
            if re.search(rf"\b{re.escape(org)}\b", lower_text):
                formatted_org = " ".join(w.capitalize() for w in org.split())
                entities[formatted_org] = {"type": "organization", "mentions": 1}

        # Match generic organization phrases worldwide (e.g. "Acme Corp", "Tata Technologies", "DeepMind Technologies", "Stripe Inc", "erbrains it solutions")
        clean_text_prefix = re.sub(r"^(tell\s+me\s+about|what\s+is|who\s+is|overview\s+of|profile\s+of)\s+", "", text, flags=re.IGNORECASE).strip()
        org_pattern = r"\b([a-zA-Z0-9_\-]+(?:\s+[a-zA-Z0-9_\-]+){0,3})\s+(Company|Technologies|Solutions|Technologies Pvt Ltd|Solutions Pvt Ltd|Inc\.?|Corp\.?|Corporation|Ltd\.?|Pvt Ltd|LLC|Labs|Enterprises|Firm|Consulting|Group)\b"
        org_stopwords = {"want", "build", "create", "start", "run", "make", "an", "a", "the", "our", "my", "your", "good", "new", "top", "best", "small", "big", "ai", "tech", "software", "product", "service"}
        for match in re.finditer(org_pattern, clean_text_prefix, flags=re.IGNORECASE):
            org_name = match.group(1).strip()
            org_words = [w.lower() for w in org_name.split()]
            if len(org_name) > 1 and not all(w in org_stopwords for w in org_words) and org_name.lower() not in ["the", "a", "an", "this", "that"]:
                entities[f"{org_name.title()} {match.group(2).title()}"] = {"type": "organization", "mentions": 1}

        # 5. Generic People names detection (titles, roles, attribution patterns, or capitalized full names)
        person_patterns = [
            r"\b(?:who\s+is|ceo\s+(?:of\s+)?|founder\s+(?:of\s+)?|created\s+by\s+|authored\s+by\s+|written\s+by\s+|architect\s+|director\s+|mr\.?\s+|ms\.?\s+|mrs\.?\s+|dr\.?\s+|prof\.?\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
        ]
        for p_pat in person_patterns:
            for match in re.finditer(p_pat, text):
                p_name = match.group(1).strip()
                if p_name and p_name not in entities:
                    entities[p_name] = {"type": "person", "mentions": 1}

        # 6. Capitalized multi-word or single-word entities (excluding common stopwords and hardware metrics)
        stopwords = {
            "The", "A", "An", "What", "How", "Why", "When", "Where", "Which", "Who", "Can", "Could",
            "Tell", "Give", "Explain", "RAM", "VRAM", "CPU", "GPU", "SSD", "HDD", "GB", "MB", "TB",
            "OS", "DB", "SQL", "API", "AI", "Is", "Are", "In", "On", "At", "For", "With", "About",
            "Here", "There", "Find", "Show", "Explain", "Tell", "Top", "Cloud", "Does", "Do", "Company"
        }
        raw_words = text.split()
        for idx, w in enumerate(raw_words):
            cleaned = re.sub(r"[^\w\-]", "", w)
            if cleaned and cleaned[0].isupper() and cleaned not in stopwords and len(cleaned) > 2:
                if cleaned not in entities:
                    # If followed by 'company' or 'solutions', categorize as organization
                    is_org = idx + 1 < len(raw_words) and re.sub(r"[^\w\-]", "", raw_words[idx+1]).lower() in ["company", "solutions", "technologies", "inc", "corp", "ltd"]
                    entities[cleaned] = {"type": "organization" if is_org else "named_entity", "mentions": 1}

        return entities

    @classmethod
    def extract_constraints(cls, text: str) -> Dict[str, Any]:
        """
        Extracts domain-agnostic constraints (license, language, OS, hardware, format, market, etc.).
        """
        constraints: Dict[str, Any] = {}
        lower = text.lower()

        # License
        if "open source" in lower or "open-source" in lower or "foss" in lower or "apache" in lower or "mit" in lower:
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

        # Execution mode
        if "local" in lower or "locally" in lower or "offline" in lower:
            constraints["execution_mode"] = "local"
        elif "cloud" in lower or "api" in lower:
            constraints["execution_mode"] = "cloud"

        # Hardware / Memory limits
        ram_match = re.search(r"(\d+)\s*(gb|mb|tb)\s*(ram|vram|memory)?", lower)
        if ram_match:
            constraints["memory_limit"] = f"{ram_match.group(1)}{ram_match.group(2).upper()}"

        # Temporal
        if "today" in lower or "latest" in lower or "current" in lower or "recently" in lower:
            constraints["temporal"] = "latest"
        elif "yesterday" in lower:
            constraints["temporal"] = "yesterday"

        # Market / Finance / Geographic Region
        if re.search(r"\b(india|indian)\b", lower):
            constraints["location"] = "India"
        elif re.search(r"\b(united states|u\.s\.a\.?|usa|nasdaq|nyse)\b", lower):
            constraints["location"] = "US"

        if "small cap" in lower or "small-cap" in lower:
            constraints["market_cap"] = "small_cap"
        elif "mid cap" in lower or "mid-cap" in lower:
            constraints["market_cap"] = "mid_cap"
        elif "large cap" in lower or "large-cap" in lower:
            constraints["market_cap"] = "large_cap"

        # Format constraints
        if "json" in lower:
            constraints["format"] = "json"
        elif "table" in lower or "markdown table" in lower:
            constraints["format"] = "table"
        elif "bullet" in lower or "bullet points" in lower:
            constraints["format"] = "bullet_points"
        elif "step by step" in lower or "step-by-step" in lower:
            constraints["format"] = "step_by_step"

        return constraints

    @classmethod
    def resolve_references(
        cls,
        query: str,
        history: List[Dict[str, str]],
        state: Optional[ConversationState] = None
    ) -> Tuple[str, str, Dict[str, str], Dict[str, Any], List[ResolvedEntity]]:
        """
        Generic Semantic Anaphora & Entity Reference Resolver:
        Resolves pronouns ('it', 'them', 'that', 'this', 'the previous one', 'both')
        to specific entity names rather than full question strings,
        builds clean, natural canonical queries, and tracks active entity recency.
        """
        words = re.findall(r"\b\w+\b", query.lower())
        has_pronoun = any(w in cls.PRONOUNS for w in words)
        has_pro_form = any(pf in query.lower() for pf in cls.PRO_FORMS)
        is_short = len(words) <= 7

        # Accumulate constraints
        accumulated_constraints = dict(state.constraints) if state and state.constraints else {}
        references: Dict[str, str] = dict(state.references) if state and state.references else {}
        entity_stack: List[str] = []
        prior_entity_stack: List[str] = []
        prior_user_entity_stack: List[str] = []
        user_entity_stack: List[str] = []
        entity_types: Dict[str, str] = {}

        if history:
            for turn in history:
                is_user = turn.get("role") == "user"
                if is_user:
                    accumulated_constraints.update(cls.extract_constraints(turn.get("content", "")))
                # Collect entities in chronological order
                t_entities = cls.extract_entities(turn.get("content", ""))
                for ent_name, ent_info in t_entities.items():
                    if ent_name in entity_stack:
                        entity_stack.remove(ent_name)
                    if ent_name in prior_entity_stack:
                        prior_entity_stack.remove(ent_name)
                    if is_user:
                        if ent_name in prior_user_entity_stack:
                            prior_user_entity_stack.remove(ent_name)
                        if ent_name in user_entity_stack:
                            user_entity_stack.remove(ent_name)

                    entity_stack.append(ent_name)
                    prior_entity_stack.append(ent_name)
                    if is_user:
                        prior_user_entity_stack.append(ent_name)
                        user_entity_stack.append(ent_name)
                    entity_types[ent_name] = ent_info.get("type", "named_entity")

        curr_constraints = cls.extract_constraints(query)
        accumulated_constraints.update(curr_constraints)

        # Also extract current query entities
        curr_entities = cls.extract_entities(query)
        for ent_name, ent_info in curr_entities.items():
            if ent_name in entity_stack:
                entity_stack.remove(ent_name)
            if ent_name in user_entity_stack:
                user_entity_stack.remove(ent_name)
            entity_stack.append(ent_name)
            user_entity_stack.append(ent_name)
            entity_types[ent_name] = ent_info.get("type", "named_entity")

        # Determine active topic and subject with model/technology priority
        active_topic = state.topic if state and state.topic else None
        active_subject = None

        # Priority resolution:
        # If the user is asking with a pronoun (it/its/this/that) or short follow-up, referent is the PRIOR entity from history
        priority_types = ["model", "technology", "organization", "person", "product", "concept"]
        prior_user_priority = [e for e in prior_user_entity_stack if entity_types.get(e) in priority_types]
        prior_all_priority = [e for e in prior_entity_stack if entity_types.get(e) in priority_types]
        user_priority = [e for e in user_entity_stack if entity_types.get(e) in priority_types]

        if has_pronoun or has_pro_form:
            if prior_user_priority:
                active_subject = prior_user_priority[-1]
            elif prior_all_priority:
                active_subject = prior_all_priority[-1]
            elif prior_entity_stack:
                active_subject = prior_entity_stack[-1]
            elif user_priority:
                active_subject = user_priority[-1]
        else:
            if user_priority:
                active_subject = user_priority[-1]
            elif prior_all_priority and is_short and not re.match(r"^(what is|who is|explain|define)\b", query, re.IGNORECASE):
                active_subject = prior_all_priority[-1]
            elif entity_stack:
                active_subject = entity_stack[-1]

        if not active_topic and history:
            for turn in reversed(history):
                if turn.get("role") == "user":
                    u_text = turn.get("content", "").strip()
                    if u_text and len(u_text.split()) > 1 and u_text.lower() != query.lower():
                        active_topic = cls.clean_subject_name(u_text)
                        break

        if not active_topic:
            active_topic = cls.clean_subject_name(query) if len(query.split()) > 1 else (active_subject or query)

        if not active_subject:
            active_subject = active_topic

        # Update reference mappings with true entity names
        if active_subject:
            references["it"] = active_subject
            references["this"] = active_subject
            references["that"] = active_subject
            references["subject"] = active_subject

        if len(entity_stack) >= 2:
            references["first_entity"] = entity_stack[-2]
            references["second_entity"] = entity_stack[-1]
            references["former"] = entity_stack[-2]
            references["latter"] = entity_stack[-1]
            references["them"] = f"{entity_stack[-2]} and {entity_stack[-1]}"
            references["both"] = f"{entity_stack[-2]} and {entity_stack[-1]}"
        elif len(entity_stack) == 1:
            references["them"] = entity_stack[0]

        # Build clean, natural canonical query
        canonical = query.strip()

        # 1. Pronoun replacement in query
        if has_pronoun and active_subject:
            # Replace 'it', 'its', 'this', 'that' with actual entity subject
            p_sub = active_subject
            canonical = re.sub(r"\b(how\s+does\s+)it(\s+help)\b", rf"\1{p_sub}\2", canonical, flags=re.IGNORECASE)
            canonical = re.sub(r"\b(how\s+much\s+ram\s+does\s+)it(\s+need)\b", rf"\1{p_sub}\2", canonical, flags=re.IGNORECASE)
            canonical = re.sub(r"\b(how\s+is\s+)it(\s+different\s+from)\b", rf"\1{p_sub}\2", canonical, flags=re.IGNORECASE)
            canonical = re.sub(r"\b(tell\s+me\s+more\s+about\s+)it\b", rf"\1{p_sub}", canonical, flags=re.IGNORECASE)
            canonical = re.sub(r"\b(run\s+)it\b", rf"\1{p_sub}", canonical, flags=re.IGNORECASE)
            canonical = re.sub(r"\b(install\s+)it\b", rf"\1{p_sub}", canonical, flags=re.IGNORECASE)
            canonical = re.sub(r"\b(what\s+about\s+)it\b", rf"\1{p_sub}", canonical, flags=re.IGNORECASE)

            # Plural pronouns
            if "them" in references and re.search(r"\b(compare|which|difference between)\s+them\b", canonical, re.IGNORECASE):
                canonical = re.sub(r"\bthem\b", references["them"], canonical, flags=re.IGNORECASE)

        # 2. Elliptical queries / continuation phrasing
        lower_q = query.strip().lower()
        if is_short or has_pro_form or curr_constraints:
            if lower_q in ["give examples", "give examples.", "give me some examples", "give me some examples.", "examples"]:
                canonical = f"Give examples of {active_subject or active_topic}."
            elif lower_q in ["which is easier?", "which is easier", "which is better?", "which is better"]:
                if len(entity_stack) >= 2:
                    canonical = f"Which is easier: {entity_stack[-2]} or {entity_stack[-1]}?"
                else:
                    canonical = f"Which is easier in {active_subject}?"
            elif lower_q in ["what about jobs?", "what about jobs", "jobs"]:
                canonical = f"What are the job opportunities for {active_subject or active_topic}?"
            elif re.match(r"^in\s+([\w\s]+)\??$", lower_q):
                target = re.sub(r"^in\s+", "", lower_q).replace("?", "").strip()
                # For "in X", the subject is the previous topic, not X itself
                prior_subj = prior_all_priority[-1] if prior_all_priority else active_topic
                canonical = f"{prior_subj} in {target.capitalize()}"
            elif lower_q in ["small cap", "small cap.", "small-cap"]:
                canonical = f"{active_topic or active_subject} (small cap)"
            elif lower_q in ["give details", "give details.", "details"]:
                canonical = f"Give details for {active_topic or active_subject}."
            elif re.match(r"^what\s+about\s+([\w\s]+)\??$", lower_q):
                target = re.sub(r"^what\s+about\s+", "", lower_q).replace("?", "").strip()
                canonical = f"How does {active_subject or active_topic} apply to {target}?"
            elif re.match(r"^which\s+ones?\s+run\s+locally\??$", lower_q):
                canonical = f"Which {active_subject or active_topic} models or tools run locally?"
            elif lower_q in ["do it", "do it.", "proceed"]:
                canonical = f"Proceed with {active_subject or active_topic}."
            elif (history or (state and state.topic)) and (curr_constraints or is_short) and (active_subject or active_topic) and (active_subject or active_topic).lower() not in canonical.lower():
                canonical = f"{active_topic or active_subject} ({query.strip()})"

        # Structured ResolvedEntity objects
        resolved_entities_list = [
            ResolvedEntity(name=name, entity_type="technology" if name.lower() in ["python", "rust", "postgresql"] else "concept", recency_index=idx)
            for idx, name in enumerate(reversed(entity_stack[-5:]))
        ]

        return canonical, active_topic or query, references, accumulated_constraints, resolved_entities_list

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
        """Persists the turn state back into PostgreSQL only after successful turn completion."""
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
