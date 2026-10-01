import re
from typing import List, Dict, Any, Optional, Tuple
from backend.app.schemas.chat import SourceCitation
from backend.app.models.memory import Memory
from backend.app.models.knowledge import DocumentChunk
from backend.app.core.logging import logger


class ContextEngine:
    """
    10-Layer Production Context Engine:
    Assembles, priorities, and token-budgets multi-tier context across:
    1. User Context, 2. Conversation Context, 3. Turn Context,
    4. Task Context, 5. Project Context, 6. Workspace Context,
    7. Memory Context, 8. Knowledge (RAG) Context, 9. Tool Context, 10. Environment Context.
    """

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Fast robust token estimation (~3.8 chars per token average)."""
        if not text:
            return 0
        return max(1, int(len(text) / 3.8))

    @classmethod
    def assemble_context(
        cls,
        model_context_limit: int = 8192,
        max_output_tokens: int = 2048,
        system_instruction: Optional[str] = None,
        workspace_name: str = "General",
        workspace_instructions: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
        task_context: Optional[Dict[str, Any]] = None,
        project_context: Optional[Dict[str, Any]] = None,
        environment_context: Optional[Dict[str, Any]] = None,
        tool_definitions: Optional[List[Dict[str, Any]]] = None,
        memories: Optional[List[Memory]] = None,
        rag_chunks: Optional[List[Tuple[DocumentChunk, float]]] = None,
        web_results: Optional[List[Dict[str, Any]]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        current_user_message: str = "",
        accumulated_constraints: Optional[Dict[str, Any]] = None,
        conversation_state: Optional[Dict[str, Any]] = None,
        is_massive_scope: bool = False,
    ) -> Dict[str, Any]:
        """Assembles prioritized token-budgeted prompt payload."""
        available_prompt_tokens = max(1200, model_context_limit - max_output_tokens)

        # 1. Base System Directive & Workspace Context
        system_sections = []
        if system_instruction:
            system_sections.append(system_instruction)

        base_directive = (
            f"You are Aetherius AI, an accurate, fast, and helpful AI assistant in the '{workspace_name}' workspace.\n"
            "Guidelines:\n"
            "- Provide direct, clear, authoritative, and factual answers without template debug headers.\n"
            "- Strict Zero-Disclaimer Rule: Never say 'I do not have access to real-time information', 'I am an AI', or 'The live evidence does not provide...'. Answer directly and confidently using the verified facts.\n"
            "- When asked for lists of leaders, officials, states, or entities, format the response as a clean, concise Markdown table (| State/Entity | Current Incumbent |). Only list current incumbents (1 row each); never produce exhaustive historical lists of past leaders unless explicitly requested.\n"
            "- When live evidence is provided, strictly prioritize the named entities, leaders, numbers, and facts in that evidence.\n"
            "- STRICT FACTUAL GROUNDING & ZERO HALLUCINATION: Only state facts corroborated by verified evidence.\n"
            "- Built-in PDF & Document Generation: You have full native capability to generate professional downloadable PDF reports, Word documents (.docx), Excel spreadsheets (.xlsx), resumes, invoices, and attendance registers. NEVER say 'I cannot create or print PDFs' or 'I can only provide text'. When asked to generate, create, or export a PDF/document or 'create a pdf of it', immediately output the complete, beautifully structured document in Markdown with proper headings (#, ##), bullet points, and tables. The system automatically compiles your response into downloadable PDF and document files.\n"
            + ("- USER PROFILE MEMORY ISOLATION: Information in user memory represents personal context, not global world facts." if memories else "")
        )
        system_sections.append(base_directive)

        if workspace_instructions and workspace_instructions != "You are Aetherius AI.":
            system_sections.append(f"[WORKSPACE DIRECTIVES]:\n{workspace_instructions}")

        # 2. Dynamic Context (Move out of System Prompt to preserve KV Cache)
        dynamic_context_parts = []
        
        # Conversational State & Turn Intent Layer
        if conversation_state:
            topic = conversation_state.get("topic")
            turn_type = conversation_state.get("turn_type", "NEW_TOPIC")
            references = conversation_state.get("references", {})
            state_lines = []
            if topic:
                state_lines.append(f"Active Topic: {topic}")
            if turn_type and turn_type == "CORRECTION":
                state_lines.append("Note: User is revising/correcting a detail.")
            if references:
                ref_items = [f"'{k}' -> {v}" for k, v in list(references.items())[:3] if k != "subject"]
                if ref_items:
                    state_lines.append(f"Resolved References: {', '.join(ref_items)}")
            if state_lines:
                dynamic_context_parts.append("[CONVERSATION CONTEXT]:\n" + "\n".join(state_lines))

        # 3. User & Environment Context Layer
        if user_preferences:
            p_lines = [f"- {k}: {v}" for k, v in user_preferences.items()]
            dynamic_context_parts.append("[USER PREFERENCES]:\n" + "\n".join(p_lines))

        # 4. Memory Context Layer
        if memories and len(memories) > 0:
            mem_lines = [f"- {m.content if hasattr(m, 'content') else str(m)}" for m in memories[:3]]
            dynamic_context_parts.append("[USER PROFILE & PERSONAL MEMORY (ISOLATED)]:\n" + "\n".join(mem_lines))

        # 5. Tool Context Layer
        if tool_definitions and len(tool_definitions) > 0:
            tool_summaries = [f"- `{t.get('name')}`: {t.get('description')}" for t in tool_definitions]
            dynamic_context_parts.append("[AVAILABLE TOOLS]:\n" + "\n".join(tool_summaries))

        full_system_prompt = "\n\n".join(system_sections)
        system_tokens = cls.estimate_tokens(full_system_prompt)

        # 6. Accumulated Constraints Injection
        constraint_text = ""
        if accumulated_constraints:
            valid_c = {k: v for k, v in accumulated_constraints.items() if k != "location" or v != "US"}
            if valid_c:
                c_lines = [f"- {k}: {v}" for k, v in valid_c.items()]
                constraint_text = "[ACCUMULATED USER CONSTRAINTS]:\n" + "\n".join(c_lines)

        # 7. Knowledge Context (RAG) & Web Context Budgeting
        user_msg_tokens = cls.estimate_tokens(current_user_message)
        constraint_tokens = cls.estimate_tokens(constraint_text)
        mandatory_tokens = system_tokens + user_msg_tokens + constraint_tokens
        dynamic_budget = max(400, available_prompt_tokens - mandatory_tokens)

        # RAG Knowledge chunks
        active_rag_chunks = sorted(rag_chunks or [], key=lambda x: x[1], reverse=True)
        fitted_rag_parts = []
        rag_tokens = 0
        rag_budget = min(int(dynamic_budget * 0.40), 600)

        for chunk, score in active_rag_chunks:
            fn = chunk.chunk_metadata.get("filename", "Doc")
            part = f"[{fn}]: {chunk.content}"
            p_tokens = cls.estimate_tokens(part)
            if rag_tokens + p_tokens <= rag_budget:
                fitted_rag_parts.append(part)
                rag_tokens += p_tokens

        rag_text = ("[DOCUMENT KNOWLEDGE]:\n" + "\n\n".join(fitted_rag_parts)) if fitted_rag_parts else ""
        rag_tokens = cls.estimate_tokens(rag_text)

        # Web Evidence Context (High density, compact formatting for instant CPU prompt evaluation)
        fitted_web_parts = []
        web_tokens = 0
        web_budget = min(int(dynamic_budget * 0.65), 900)

        if web_results:
            for idx, w in enumerate(web_results[:4], 1):
                t = w.get("title", "")
                raw_fact = (w.get("deep_content") or w.get("snippet") or "").strip()
                if "|" in raw_fact and "---" in raw_fact:
                    clean_fact = raw_fact[:1400].strip()
                    part = f"- Source [{idx}] ({t}):\n{clean_fact}"
                else:
                    clean_fact = raw_fact[:650].strip()
                    part = f"- Source [{idx}] ({t}):\n{clean_fact}"
                    
                p_tokens = cls.estimate_tokens(part)
                if web_tokens + p_tokens <= web_budget:
                    fitted_web_parts.append(part)
                    web_tokens += p_tokens

        web_text = ("[VERIFIED LIVE EVIDENCE]:\n" + "\n\n".join(fitted_web_parts)) if fitted_web_parts else ""
        web_tokens = cls.estimate_tokens(web_text)

        # 8. Fit Conversation History within remaining token budget
        history_budget = max(200, available_prompt_tokens - (mandatory_tokens + rag_tokens + web_tokens))
        fitted_history: List[Dict[str, str]] = []
        current_history_tokens = 0

        if chat_history:
            for msg in reversed(chat_history):
                m_tokens = cls.estimate_tokens(msg.get("content", ""))
                if current_history_tokens + m_tokens <= history_budget:
                    fitted_history.insert(0, msg)
                    current_history_tokens += m_tokens

        # 9. Construct Final Turn Payload
        augmented_user_parts = []
        if dynamic_context_parts:
            augmented_user_parts.extend(dynamic_context_parts)
        if constraint_text:
            augmented_user_parts.append(constraint_text)
        if rag_text:
            augmented_user_parts.append(rag_text)
        if web_text:
            augmented_user_parts.append(web_text)
            augmented_user_parts.append(
                "Grounding & Accuracy Directives:\n"
                "1. Strict Identity & Telemetry Binding: For real-time queries (current leaders/officials, weather, market quotes, sports scores, currency rates), you MUST strictly use the exact names, values, and dates present in the [VERIFIED LIVE EVIDENCE] above. Never guess or substitute past leaders.\n"
                "2. Live Sports & Matches: For queries about match scores, match results, or 'who won yesterday/today', directly state the winner, final score/runs, margins, and key player performances (e.g. centuries, top scorers, key wickets/goals) from the verified live news evidence above. Never refuse or claim lack of real-time sports access when live evidence is provided.\n"
                "3. Multi-Entity Comparisons: When comparing multiple entities (e.g. GDP and PM of two countries), ensure both entities are addressed with their respective verified facts in structured sections or comparison tables.\n"
                "4. Roster & Table Inquiries: For roster/list queries across multiple entities/states, provide a complete Markdown table (| Entity | Current Incumbent | Dates |) using your knowledge enhanced by live evidence.\n"
                "5. Clean Direct Output: Do not reference internal citation markers like '[1]' or '[2]' in your prose. Answer naturally, directly, and factually.\n"
                "6. Institutional Precision: Accurately distinguish official government roles (e.g., USA President, German Chancellor, Indian Chief Minister / Prime Minister, UK Prime Minister)."
            )

        if is_massive_scope:
            augmented_user_parts.append(
                "Adaptive Scope & Capacity Directives:\n"
                "1. The user's query requests a broad multi-decade historical archive spanning multiple states/countries.\n"
                "2. To ensure a 100% complete, non-truncated response covering ALL entities within model token limits, format the response as a clean, concise Markdown table summarizing key historical milestones per entity:\n"
                "   | State/Entity | First Incumbent (Inception/1947) | Longest Serving / Notable Transition | Current Incumbent |\n"
                "3. Conclude with: 'If you would like the complete year-by-year chronological list for any specific state or entity, please let me know and I will provide the full breakdown.'"
            )

        augmented_user_parts.append(f"User Request: {current_user_message}")
        augmented_prompt = "\n\n".join(augmented_user_parts)

        total_estimated_tokens = (
            system_tokens + current_history_tokens + cls.estimate_tokens(augmented_prompt)
        )

        return {
            "system_prompt": full_system_prompt,
            "augmented_prompt": augmented_prompt,
            "fitted_history": fitted_history,
            "stats": {
                "system_tokens": system_tokens,
                "history_turns": len(fitted_history),
                "history_tokens": current_history_tokens,
                "rag_tokens": rag_tokens,
                "web_tokens": web_tokens,
                "total_estimated_tokens": total_estimated_tokens,
                "context_limit": model_context_limit,
            }
        }
