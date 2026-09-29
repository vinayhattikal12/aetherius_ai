from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from backend.app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from backend.app.schemas.knowledge import DocumentChunkResponse, RAGSearchResult
from backend.app.schemas.chat import SourceCitation
from backend.app.services.document_processor import DocumentProcessor
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.storage_service import storage
from backend.app.core.logging import logger


class RAGService:
    @staticmethod
    async def create_or_get_knowledge_base(
        db: AsyncSession,
        name: str,
        slug: str,
        collection_type: str = "General",
        workspace_slug: str = "general",
        description: Optional[str] = None
    ) -> KnowledgeBase:
        result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.slug == slug))
        kb = result.scalars().first()
        if not kb:
            kb = KnowledgeBase(
                name=name,
                slug=slug,
                collection_type=collection_type,
                workspace_slug=workspace_slug,
                description=description
            )
            db.add(kb)
            await db.commit()
            await db.refresh(kb)
        return kb

    @staticmethod
    async def ingest_document(
        db: AsyncSession,
        knowledge_base_id: str,
        filename: str,
        file_bytes: bytes,
        file_type: str
    ) -> Document:
        """Saves file to storage, extracts text, chunks, computes embeddings, and stores in PostgreSQL."""
        # 1. Save file to disk
        storage_path = storage.save_file(file_bytes, filename)

        # 2. Create document record
        doc = Document(
            knowledge_base_id=knowledge_base_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=len(file_bytes),
            storage_path=storage_path,
            status="parsing"
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        try:
            # 3. Extract text
            text, meta = DocumentProcessor.extract_text(file_bytes, file_type)
            doc.doc_metadata = meta

            # 4. Chunk text
            chunks_data = DocumentProcessor.chunk_text(text)
            doc.chunk_count = len(chunks_data)
            doc.status = "chunked"
            await db.commit()

            # 5. Generate embeddings and persist chunks
            for c_info in chunks_data:
                emb = await EmbeddingService.embed_text(c_info["content"])
                chunk_record = DocumentChunk(
                    document_id=doc.id,
                    knowledge_base_id=knowledge_base_id,
                    chunk_index=c_info["chunk_index"],
                    content=c_info["content"],
                    embedding_vector=emb,
                    token_count=len(c_info["content"].split()),
                    chunk_metadata={
                        "filename": filename,
                        "char_length": c_info["char_length"]
                    }
                )
                db.add(chunk_record)

            doc.status = "ready"
            await db.commit()
            await db.refresh(doc)
            logger.info(f"Document {filename} ingested into PostgreSQL with {len(chunks_data)} chunks.")
            return doc

        except Exception as e:
            logger.error(f"Failed to ingest document {filename}: {e}")
            doc.status = "error"
            doc.error_message = str(e)
            await db.commit()
            raise

    @staticmethod
    async def search_relevant_chunks(
        db: AsyncSession,
        query: str,
        knowledge_base_slugs: Optional[List[str]] = None,
        workspace_slug: Optional[str] = None,
        top_k: int = 4,
        min_similarity: float = 0.05
    ) -> List[Tuple[DocumentChunk, float]]:
        """Performs vector similarity search across document chunks stored in PostgreSQL."""
        # 1. Compute query vector
        query_vector = await EmbeddingService.embed_text(query)

        # 2. Build query
        stmt = select(DocumentChunk).join(KnowledgeBase)
        if knowledge_base_slugs:
            stmt = stmt.where(KnowledgeBase.slug.in_(knowledge_base_slugs))
        elif workspace_slug:
            stmt = stmt.where(KnowledgeBase.workspace_slug == workspace_slug)

        result = await db.execute(stmt)
        chunks = result.scalars().all()

        scored_chunks: List[Tuple[DocumentChunk, float]] = []
        for chunk in chunks:
            if chunk.embedding_vector:
                sim = EmbeddingService.cosine_similarity(query_vector, chunk.embedding_vector)
                if sim >= min_similarity:
                    scored_chunks.append((chunk, round(sim, 4)))

        # Sort by similarity descending
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]

    @classmethod
    def build_citations(cls, scored_chunks: List[Tuple[DocumentChunk, float]]) -> List[SourceCitation]:
        citations = []
        for chunk, score in scored_chunks:
            fn = chunk.chunk_metadata.get("filename", "Uploaded Document")
            citations.append(SourceCitation(
                source_type="document",
                title=fn,
                snippet=chunk.content[:200] + ("..." if len(chunk.content) > 200 else ""),
                chunk_index=chunk.chunk_index,
                similarity_score=score
            ))
        return citations
