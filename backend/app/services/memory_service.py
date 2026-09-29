import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from backend.app.models.base import utc_now
from backend.app.models.memory import Memory
from backend.app.schemas.memory import MemoryCreate, MemoryResponse
from backend.app.services.embedding_service import EmbeddingService
from backend.app.core.logging import logger


class MemoryService:
    """Manages persistent episodic, semantic, and preference memories in PostgreSQL."""

    @staticmethod
    async def create_memory(
        db: AsyncSession,
        data: MemoryCreate
    ) -> Memory:
        vector = await EmbeddingService.embed_text(data.content)
        memory = Memory(
            user_id=data.user_id,
            workspace_slug=data.workspace_slug,
            memory_type=data.memory_type,
            content=data.content,
            source_conversation_id=data.source_conversation_id,
            confidence_score=data.confidence_score,
            importance_weight=data.importance_weight,
            embedding_vector=vector,
            memory_metadata=data.memory_metadata,
            access_count=0,
            last_accessed_at=utc_now()
        )
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        logger.info(f"Created {data.memory_type} memory: '{data.content[:40]}...'")
        return memory

    @staticmethod
    async def update_memory(
        db: AsyncSession,
        memory_id: str,
        data: MemoryUpdate
    ) -> Optional[Memory]:
        res = await db.execute(select(Memory).where(Memory.id == memory_id))
        mem = res.scalars().first()
        if not mem:
            return None

        if data.content is not None:
            mem.content = data.content
            mem.embedding_vector = await EmbeddingService.embed_text(data.content)
        if data.memory_type is not None:
            mem.memory_type = data.memory_type
        if data.confidence_score is not None:
            mem.confidence_score = data.confidence_score
        if data.importance_weight is not None:
            mem.importance_weight = data.importance_weight
        if data.memory_metadata is not None:
            mem.memory_metadata = data.memory_metadata

        mem.updated_at = utc_now()
        await db.commit()
        await db.refresh(mem)
        return mem

    @staticmethod
    async def delete_memory(
        db: AsyncSession,
        memory_id: str
    ) -> bool:
        res = await db.execute(select(Memory).where(Memory.id == memory_id))
        mem = res.scalars().first()
        if not mem:
            return False
        await db.delete(mem)
        await db.commit()
        return True

    @staticmethod
    async def clear_memories(
        db: AsyncSession,
        workspace_slug: Optional[str] = None
    ) -> int:
        stmt = delete(Memory)
        if workspace_slug and workspace_slug != "all":
            stmt = stmt.where(Memory.workspace_slug == workspace_slug)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    @staticmethod
    async def list_memories(
        db: AsyncSession,
        workspace_slug: Optional[str] = None,
        memory_type: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100
    ) -> List[Memory]:
        stmt = select(Memory).order_by(Memory.importance_weight.desc(), Memory.created_at.desc()).limit(limit)
        if workspace_slug and workspace_slug != "all":
            # Include both global 'general' memories and workspace specific
            stmt = stmt.where(Memory.workspace_slug.in_([workspace_slug, "general"]))
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)
        if search_query:
            stmt = stmt.where(Memory.content.ilike(f"%{search_query}%"))

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def retrieve_relevant_memories(
        db: AsyncSession,
        query: str,
        workspace_slug: Optional[str] = None,
        top_k: int = 6,
        min_similarity: float = 0.05
    ) -> List[Tuple[Memory, float]]:
        """Retrieves semantically similar memories from PostgreSQL using cosine similarity."""
        query_vector = await EmbeddingService.embed_text(query)

        # Include both global and workspace-scoped memories
        stmt = select(Memory)
        if workspace_slug:
            if workspace_slug == "general":
                stmt = stmt.where(Memory.workspace_slug == "general")
            else:
                stmt = stmt.where(Memory.workspace_slug.in_([workspace_slug, "general"]))

        result = await db.execute(stmt)
        memories = result.scalars().all()

        scored_memories: List[Tuple[Memory, float]] = []
        now = utc_now()

        for m in memories:
            if m.embedding_vector:
                sim = EmbeddingService.cosine_similarity(query_vector, m.embedding_vector)
                # Boost similarity by importance weight (1.0 - 5.0) and high-priority preferences
                boost = 1.0 + (m.importance_weight - 1.0) * 0.15
                if m.memory_type in ("preference", "instruction"):
                    boost += 0.1
                weighted_score = sim * boost
                if sim >= min_similarity:
                    m.access_count += 1
                    m.last_accessed_at = now
                    scored_memories.append((m, round(weighted_score, 4)))

        await db.commit()

        # Sort by weighted score descending
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        return scored_memories[:top_k]

    @classmethod
    async def handle_explicit_memory_commands(
        cls,
        db: AsyncSession,
        text: str,
        workspace_slug: str = "general"
    ) -> Optional[str]:
        """Handles explicit natural memory commands like 'Remember that...', 'What do you remember about me?', 'Forget...'."""
        lower = text.strip().lower()

        # 1. Ask what is in memory
        if re.search(r"(?:hi|hello|hey|please|can you tell me)?\s*(?:what (?:do you remember|is in my memory|have you learned)|show (?:my )?memories|list (?:my )?memories|what do you know about me)", lower):
            all_mems = await cls.list_memories(db=db, workspace_slug=workspace_slug, limit=50)
            if not all_mems:
                return "🧠 **Memory Profile:**\nI don't have any saved memories about you yet. You can tell me things like *'Remember that I prefer TypeScript and concise answers'* or *'I am a senior software engineer'*."
            
            lines = ["🧠 **Here is what I've learned and saved to memory:**\n"]
            for m in all_mems:
                lines.append(f"- **[{m.memory_type.upper()}]** {m.content}")
            lines.append("\n*You can ask me to remember new preferences or delete any obsolete items at any time.*")
            return "\n".join(lines)

        # 2. Explicit "Remember that ..." command
        rem_match = re.search(r"^(?:please )?(?:remember that|remember|keep in mind that|note that|save to memory:?)\s+(.+)$", text.strip(), re.IGNORECASE)
        if rem_match:
            raw_fact = rem_match.group(1).strip()
            if len(raw_fact) >= 3:
                # Determine type
                m_type = "preference" if any(w in raw_fact.lower() for w in ["prefer", "like", "always", "never", "format", "style"]) else "fact"
                
                # Check for existing duplicate to update
                existing = await cls.retrieve_relevant_memories(db=db, query=raw_fact, workspace_slug=workspace_slug, top_k=1, min_similarity=0.85)
                if existing:
                    target_mem = existing[0][0]
                    target_mem.content = raw_fact
                    target_mem.importance_weight = 5.0
                    target_mem.embedding_vector = await EmbeddingService.embed_text(raw_fact)
                    target_mem.updated_at = utc_now()
                    await db.commit()
                else:
                    await cls.create_memory(
                        db=db,
                        data=MemoryCreate(
                            workspace_slug=workspace_slug,
                            memory_type=m_type,
                            content=raw_fact,
                            confidence_score=1.0,
                            importance_weight=5.0,
                            memory_metadata={"source": "explicit_user_command"}
                        )
                    )
                return f"🧠 **Memory Updated:** I've saved to my long-term memory: *\"{raw_fact}\"*. I will apply this across your conversations."

        # 3. Explicit "Forget that ..." command
        forget_match = re.search(r"^(?:please )?(?:forget that|forget about|delete memory about|remove memory:?)\s+(.+)$", text.strip(), re.IGNORECASE)
        if forget_match:
            target_topic = forget_match.group(1).strip()
            existing = await cls.retrieve_relevant_memories(db=db, query=target_topic, workspace_slug=workspace_slug, top_k=1, min_similarity=0.70)
            if existing:
                deleted_items = []
                for m, _ in existing:
                    deleted_items.append(m.content)
                    await db.delete(m)
                await db.commit()
                return f"🧠 **Memory Cleared:** I have forgotten: *\"{', '.join(deleted_items)}\"*."
            else:
                return f"🧠 I couldn't find any memory matching *\"{target_topic}\"* to delete."

        return None

    @classmethod
    async def extract_and_store_from_text(
        cls,
        db: AsyncSession,
        text: str,
        workspace_slug: str = "general",
        conversation_id: Optional[str] = None
    ) -> List[Memory]:
        """Extracts facts, preferences, identity, and project guidelines using heuristic intelligence."""
        extracted: List[Memory] = []
        
        # Comprehensive Extraction Patterns
        patterns = [
            # User Identity & Role
            (r"(?:my name is|i am called|call me)\s+([A-Z][a-zA-Z\s]{1,30})", "identity", 4.5),
            (r"(?:i work as|i am an?|my role is|i work at|my job is)\s+([^.\n,]{3,60})", "work_context", 4.0),
            
            # Preferences & Style Directives
            (r"(?:i prefer|i always use|my preferred|please always|always format as|always reply with|prefer to use)\s+([^.\n]{4,100})", "preference", 4.0),
            (r"(?:never use|avoid using|do not include|don't give me)\s+([^.\n]{4,80})", "preference", 4.0),
            (r"(?:reply in|write all code in|output as)\s+([^.\n]{3,60})", "instruction", 4.0),
            
            # Technical Stack & Architecture
            (r"(?:our tech stack is|we use|our backend uses|our database is|the app is built with)\s+([^.\n]{3,100})", "fact", 3.5),
            (r"(?:our project is (?:named|called)|the project name is)\s+([^.\n]{2,50})", "fact", 3.5),
            (r"(?:i am learning|i am studying|currently studying)\s+([^.\n]{3,60})", "interest", 3.0),
        ]

        for regex, mem_type, base_weight in patterns:
            matches = re.finditer(regex, text, re.IGNORECASE)
            for m in matches:
                fact_content = m.group(0).strip()
                if len(fact_content) >= 8:
                    # Clean punctuation
                    fact_content = fact_content.rstrip(".,;!")
                    
                    # Deduplication check
                    existing = await cls.retrieve_relevant_memories(
                        db=db,
                        query=fact_content,
                        workspace_slug=workspace_slug,
                        top_k=1,
                        min_similarity=0.85
                    )
                    if not existing:
                        mem = await cls.create_memory(
                            db=db,
                            data=MemoryCreate(
                                workspace_slug=workspace_slug,
                                memory_type=mem_type,
                                content=fact_content,
                                confidence_score=0.95,
                                importance_weight=base_weight,
                                source_conversation_id=conversation_id,
                                memory_metadata={"extracted_automatically": True}
                            )
                        )
                        extracted.append(mem)

        return extracted
