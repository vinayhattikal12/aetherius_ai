from typing import List, Dict, Any, Optional, Tuple
from backend.app.schemas.chat import SourceCitation
from backend.app.models.memory import Memory
from backend.app.models.knowledge import DocumentChunk


class ContextEngine:
    """Assembles and optimizes hierarchical context within model token budget constraints."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Fast robust token estimation (average ~4 chars per token)."""
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
        memories: Optional[List[Memory]] = None,
        rag_chunks: Optional[List[Tuple[DocumentChunk, float]]] = None,
        web_results: Optional[List[Dict[str, Any]]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        current_user_message: str = ""
    ) -> Dict[str, Any]:
        """Assembles a prioritized, token-budgeted prompt payload."""
        # 1. Calculate available budget for prompt
        available_prompt_tokens = max(1000, model_context_limit - max_output_tokens)

        # 2. Build Base System Prompt
        system_sections = []
        if system_instruction:
            system_sections.append(system_instruction)

        system_sections.append(
            f"You are Aetherius AI, an elite AI operating environment running in the '{workspace_name}' workspace.\n"
            "CORE BEHAVIOR & INTELLIGENCE DIRECTIVES:\n"
            "- DYNAMIC BREVITY & DEPTH: Calibrate your response length to the user's intent. For direct, simple, or quick queries, provide punchy, crisp, fluff-free answers. For complex concepts, how-to guides, architectural questions, or multi-step tasks, provide structured deep-dives with headers and bullet points.\n"
            "- PRACTICAL EXAMPLES: Whenever explaining a concept, mechanism, algorithm, or methodology, ALWAYS illustrate with a concrete, realistic real-world example, analogy, or runnable code snippet.\n"
            "- CODE & VISUAL FORMATTING: Use clean markdown with precise language tags (e.g. ```python, ```typescript, ```sql). When visual diagrams or flowcharts are helpful, include structured ASCII or Mermaid diagrams.\n"
            "- FACTUAL ACCURACY: When [Live Web Search Results] or [Document Knowledge] are provided, use those live facts, numbers, and data points directly in your response.\n"
            "- At the end of your response, provide a '### Sources & References' section with links when external sources are cited."
        )
        if workspace_instructions:
            system_sections.append(f"### [WORKSPACE ROLE & COGNITIVE GUIDELINES]:\n{workspace_instructions}")

        # 3. Add Personalized Long-Term Memory Section
        if memories and len(memories) > 0:
            mem_lines = []
            for m in memories:
                m_type = m.memory_type.upper() if hasattr(m, 'memory_type') else 'FACT'
                m_content = m.content if hasattr(m, 'content') else str(m)
                mem_lines.append(f"- [{m_type}] {m_content}")
            
            mem_text = "\n".join(mem_lines)
            system_sections.append(
                f"### [USER PROFILE & LONG-TERM MEMORY]:\n"
                f"{mem_text}\n"
                f"ADAPTATION DIRECTIVE: Seamlessly adapt your answers, tone, language, and formatting to reflect these user preferences and facts naturally without explicitly announcing 'According to my memory' unless directly asked."
            )

        full_system_prompt = "\n\n".join(system_sections)
        system_tokens = cls.estimate_tokens(full_system_prompt)

        # 4. Assemble Knowledge Base (RAG) Context
        rag_text = ""
        rag_tokens = 0
        if rag_chunks and len(rag_chunks) > 0:
            rag_parts = []
            for chunk, score in rag_chunks:
                fn = chunk.chunk_metadata.get("filename", "Doc")
                rag_parts.append(f"[Source: {fn} (similarity: {score})]:\n{chunk.content}")
            rag_text = "Retrieved Document Knowledge:\n" + "\n\n".join(rag_parts)
            rag_tokens = cls.estimate_tokens(rag_text)

        # 5. Assemble Web Search Context
        web_text = ""
        web_tokens = 0
        if web_results and len(web_results) > 0:
            web_parts = [f"- **{w.get('title')}**\n  Snippet: {w.get('snippet')}\n  URL: {w.get('url')}" for w in web_results]
            web_text = "### [LIVE REAL-TIME WEB SEARCH RESULTS]:\n" + "\n\n".join(web_parts)
            web_tokens = cls.estimate_tokens(web_text)

        # 6. Fit Conversation History within remaining budget
        user_msg_tokens = cls.estimate_tokens(current_user_message)
        consumed_so_far = system_tokens + rag_tokens + web_tokens + user_msg_tokens
        history_budget = max(500, available_prompt_tokens - consumed_so_far)

        fitted_history: List[Dict[str, str]] = []
        current_history_tokens = 0

        if chat_history:
            # Add from newest to oldest until budget is exhausted
            for msg in reversed(chat_history):
                m_tokens = cls.estimate_tokens(msg.get("content", ""))
                if current_history_tokens + m_tokens <= history_budget:
                    fitted_history.insert(0, msg)
                    current_history_tokens += m_tokens
                else:
                    break

        # 7. Construct Final Augmented User Prompt
        augmented_user_parts = []
        if rag_text:
            augmented_user_parts.append(rag_text)
        if web_text:
            augmented_user_parts.append(web_text)
            augmented_user_parts.append("DIRECTIVE: Use the live web search results above to answer the user query in detail. Cite numbers, indices, and top movers, and list sources at the end.")

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
                "context_limit": model_context_limit
            }
        }
