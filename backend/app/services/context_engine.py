from typing import List, Dict, Any, Optional, Tuple
from backend.app.schemas.chat import SourceCitation
from backend.app.models.memory import Memory
from backend.app.models.knowledge import DocumentChunk


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
    ) -> Dict[str, Any]:
        """Assembles prioritized token-budgeted prompt payload."""
        available_prompt_tokens = max(1200, model_context_limit - max_output_tokens)

        # 1. Base System Directive & Workspace Context
        system_sections = []
        if system_instruction:
            system_sections.append(system_instruction)

        base_directive = (
            f"You are Aetherius AI, an advanced AI Operating Environment in the '{workspace_name}' workspace.\n"
            "CORE OPERATIONAL DIRECTIVES:\n"
            "- CONTINUOUS REASONING: Maintain complete conversational awareness. When the user refines, filters, or follows up on previous turns, directly continue from the active discussion without requesting restatements.\n"
            "- DYNAMIC CALIBRATION: Match answer depth to the query's complexity. Deliver crisp, concise answers for quick questions and thorough, structured, header-organized deep dives for complex topics.\n"
            "- EVIDENCE-BACKED FACTUALITY: Strictly base assertions on provided document excerpts, verified web search results, or validated tool observations. Never hallucinate data.\n"
            "- CONCRETE EXAMPLES: Illustrate concepts with clear, runnable code snippets or structured analogies whenever applicable.\n"
            "- CITATIONS: When external knowledge or live search results are provided, cite sources accurately."
        )
        system_sections.append(base_directive)

        if workspace_instructions:
            system_sections.append(f"### [WORKSPACE ROLE DIRECTIVES]:\n{workspace_instructions}")

        # 2. User & Environment Context Layer
        env_lines = []
        if environment_context:
            for k, v in environment_context.items():
                env_lines.append(f"- {k.replace('_', ' ').title()}: {v}")
        if user_preferences:
            for k, v in user_preferences.items():
                env_lines.append(f"- Preference ({k}): {v}")

        if env_lines:
            system_sections.append(f"### [ENVIRONMENT & USER CONTEXT]:\n" + "\n".join(env_lines))

        # 3. Active Task & Project Context Layer
        if task_context:
            task_desc = f"Objective: {task_context.get('objective', 'Active Task')}\nStatus: {task_context.get('status', 'running')}\nCurrent Step: {task_context.get('current_step', 'in progress')}"
            system_sections.append(f"### [ACTIVE TASK CONTEXT]:\n{task_desc}")

        if project_context:
            proj_desc = f"Project: {project_context.get('name', 'Active Workspace')}\nActive Files: {project_context.get('files', [])}"
            system_sections.append(f"### [PROJECT CONTEXT]:\n{proj_desc}")

        # 4. Memory Context Layer (Semantic & Episodic)
        if memories and len(memories) > 0:
            mem_lines = []
            for m in memories:
                m_type = m.memory_type.upper() if hasattr(m, "memory_type") else "FACT"
                m_content = m.content if hasattr(m, "content") else str(m)
                mem_lines.append(f"- [{m_type}] {m_content}")
            system_sections.append(
                f"### [USER PROFILE & MEMORY RECALL]:\n"
                + "\n".join(mem_lines)
                + "\n(Seamlessly adapt tone, constraints, and preferences without explicitly announcing recall unless asked.)"
            )

        # 5. Tool Context Layer
        if tool_definitions and len(tool_definitions) > 0:
            tool_summaries = [f"- `{t.get('name')}`: {t.get('description')}" for t in tool_definitions]
            system_sections.append(f"### [AVAILABLE SANDBOX TOOLS]:\n" + "\n".join(tool_summaries))

        full_system_prompt = "\n\n".join(system_sections)
        system_tokens = cls.estimate_tokens(full_system_prompt)

        # 6. Knowledge Context (RAG)
        rag_text = ""
        rag_tokens = 0
        if rag_chunks and len(rag_chunks) > 0:
            rag_parts = []
            for chunk, score in rag_chunks:
                fn = chunk.chunk_metadata.get("filename", "Document")
                rag_parts.append(f"[Source: {fn} (similarity: {score})]:\n{chunk.content}")
            rag_text = "Retrieved Document Knowledge:\n" + "\n\n".join(rag_parts)
            rag_tokens = cls.estimate_tokens(rag_text)

        # 7. Web Intelligence Context
        web_text = ""
        web_tokens = 0
        if web_results and len(web_results) > 0:
            web_parts = []
            for idx, w in enumerate(web_results, 1):
                part = f"[{idx}] Title: {w.get('title')}\n    URL: {w.get('url')}\n    Summary: {w.get('snippet')}"
                if w.get("deep_content"):
                    part += f"\n    Full Article Excerpt: {w.get('deep_content')}"
                web_parts.append(part)
            web_text = "### [LIVE REAL-TIME WEB SEARCH & DEEP RETRIEVAL DATA]:\n" + "\n\n".join(web_parts)
            web_tokens = cls.estimate_tokens(web_text)

        # 8. Accumulated Constraints Injection
        constraint_text = ""
        if accumulated_constraints:
            c_lines = [f"- {k.replace('_', ' ').title()}: `{v}`" for k, v in accumulated_constraints.items()]
            constraint_text = "### [ACCUMULATED MULTI-TURN CONSTRAINTS]:\n" + "\n".join(c_lines)

        # 9. Fit Conversation History within remaining token budget
        user_msg_tokens = cls.estimate_tokens(current_user_message)
        consumed_so_far = system_tokens + rag_tokens + web_tokens + user_msg_tokens + cls.estimate_tokens(constraint_text)
        history_budget = max(400, available_prompt_tokens - consumed_so_far)

        fitted_history: List[Dict[str, str]] = []
        current_history_tokens = 0

        if chat_history:
            for msg in reversed(chat_history):
                m_tokens = cls.estimate_tokens(msg.get("content", ""))
                if current_history_tokens + m_tokens <= history_budget:
                    fitted_history.insert(0, msg)
                    current_history_tokens += m_tokens
                else:
                    break

        # 10. Construct Final Turn Payload
        augmented_user_parts = []
        if constraint_text:
            augmented_user_parts.append(constraint_text)
        if rag_text:
            augmented_user_parts.append(rag_text)
        if web_text:
            augmented_user_parts.append(web_text)
            augmented_user_parts.append(
                "STRICT GROUNDING DIRECTIVE:\n"
                "1. Answer using the live web search data and full article excerpts provided above.\n"
                "2. When stating facts or conclusions, add inline footnotes corresponding to the source index, e.g. [1], [2].\n"
                "3. Conclude with a clean '### Sources & Evidence' section listing the source titles and markdown hyperlinks."
            )

        augmented_user_parts.append(f"User Request:\n{current_user_message}")
        augmented_prompt = "\n\n---\n\n".join(augmented_user_parts)

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
