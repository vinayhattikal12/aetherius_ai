import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.conversation import Conversation, Message
from backend.app.models.workspace import Workspace
from backend.app.models.model_registry import ModelRegistry
from backend.app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    MessageResponse,
    SourceCitation,
)
from backend.app.schemas.router import RouterEvaluationRequest
from backend.app.services.rag_service import RAGService
from backend.app.services.web_search_service import WebSearchService
from backend.app.services.memory_service import MemoryService
from backend.app.services.context_engine import ContextEngine
from backend.app.services.router_service import ModelRouter
from backend.app.services.tool_service import ToolExecutionEngine, ToolExecutionRequest
from backend.app.services.image_gen_service import ImageGenService, ImageGenerationRequest
from backend.app.services.providers.model_manager import model_manager
from backend.app.core.logging import logger


class ChatService:
    @staticmethod
    async def process_chat_completion(
        db: AsyncSession,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        # 1. Fetch or create Conversation
        conversation = None
        if request.conversation_id:
            result = await db.execute(select(Conversation).where(Conversation.id == request.conversation_id))
            conversation = result.scalars().first()

        # 2. Sub-Millisecond Intelligent Model Routing
        routing_reason = "Manual model selection"
        execution_mode = "local"
        model_to_use = request.model_name

        if not model_to_use or model_to_use == "auto":
            route_plan = await ModelRouter.evaluate_routing(
                db=db,
                request=RouterEvaluationRequest(
                    prompt=request.message,
                    workspace_slug=request.workspace_slug
                )
            )
            model_to_use = route_plan.selected_model_id
            routing_reason = route_plan.routing_reason
            execution_mode = route_plan.execution_mode

        if not conversation:
            title = request.message[:30] + ("..." if len(request.message) > 30 else "")
            conversation = Conversation(
                workspace_slug=request.workspace_slug,
                title=title,
                model_name=model_to_use or "llama3.2:3b"
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        # 3. Save User Message
        user_metadata = {}
        if request.attachments:
            user_metadata["attachments"] = [a.model_dump() for a in request.attachments]

        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            model_name=model_to_use,
            token_count=len(request.message.split()),
            extra_metadata=user_metadata
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        # Process attachments
        attachment_text_context = ""
        image_base64_list = []
        citations: List[SourceCitation] = []

        if request.attachments:
            for att in request.attachments:
                if att.is_image and att.preview_url:
                    if "base64," in att.preview_url:
                        b64 = att.preview_url.split("base64,")[1]
                        image_base64_list.append(b64)
                    citations.append(SourceCitation(
                        source_type="document",
                        title=f"Attached Image: {att.filename}",
                        snippet=f"Visual upload: {att.filename} ({round(att.file_size_bytes / 1024, 1)} KB)"
                    ))
                elif att.extracted_text:
                    attachment_text_context += f"\n\n--- [Attached Document: {att.filename}] ---\n{att.extracted_text[:6000]}\n--- [End of {att.filename}] ---"
                    citations.append(SourceCitation(
                        source_type="document",
                        title=f"Attached File: {att.filename}",
                        snippet=f"Extracted content from {att.filename} ({round(att.file_size_bytes / 1024, 1)} KB)"
                    ))

        # Check explicit memory command
        explicit_mem_reply = await MemoryService.handle_explicit_memory_commands(
            db=db,
            text=request.message,
            workspace_slug=request.workspace_slug
        )
        if explicit_mem_reply:
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=explicit_mem_reply,
                model_name=model_to_use,
                token_count=len(explicit_mem_reply.split()),
                extra_metadata={"memory_command": True}
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)
            return ChatCompletionResponse(
                conversation_id=conversation.id,
                user_message=MessageResponse.model_validate(user_msg),
                assistant_message=MessageResponse.model_validate(assistant_msg),
                model_used=model_to_use,
                citations=[],
                web_searched=False,
                rag_applied=False
            )

        # Fetch recent history first
        res_h = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
        )
        recent_history = [{"role": h.role, "content": h.content} for h in res_h.scalars().all()[-8:]]

        # Multi-Turn Semantic Query Intelligence Analysis
        from backend.app.services.query_intelligence_service import QueryIntelligenceService
        q_analysis = await QueryIntelligenceService.analyze_query(
            user_message=request.message,
            conversation_history=recent_history,
            workspace_slug=request.workspace_slug
        )

        is_visual = q_analysis.is_visual
        generated_image_url: Optional[str] = None

        if is_visual:
            try:
                v_prompt = q_analysis.visual_prompt or request.message
                img_res = await ImageGenService.generate_image(
                    ImageGenerationRequest(
                        prompt=v_prompt,
                        workspace_slug=request.workspace_slug,
                        style_preset="diagram" if ("diagram" in v_prompt.lower() or "architecture" in v_prompt.lower() or "neural" in v_prompt.lower()) else "photorealistic"
                    )
                )
                generated_image_url = img_res.preview_url or img_res.image_url
            except Exception as e:
                logger.warn(f"Autonomous image generation notice: {e}")

        # Parallel retrieval tasks
        async def fetch_workspace():
            res = await db.execute(select(Workspace).where(Workspace.slug == request.workspace_slug))
            return res.scalars().first()

        async def fetch_memories():
            if len(request.message.split()) < 3 and not any(k in request.message.lower() for k in ["i am", "my", "prefer", "remember"]):
                return []
            try:
                scored = await MemoryService.retrieve_relevant_memories(
                    db=db, query=q_analysis.canonical_prompt, workspace_slug=request.workspace_slug, top_k=4, min_similarity=0.1
                )
                return [m for m, _ in scored]
            except Exception:
                return []

        async def fetch_rag():
            if not request.enable_knowledge_rag:
                return []
            try:
                return await RAGService.search_relevant_chunks(
                    db=db, query=q_analysis.canonical_prompt, knowledge_base_slugs=request.knowledge_base_slugs, workspace_slug=request.workspace_slug, top_k=4
                )
            except Exception:
                return []

        async def fetch_web():
            should_search = request.enable_web_search or q_analysis.is_search
            if should_search:
                try:
                    s_res = await WebSearchService.search(q_analysis.canonical_prompt, max_results=4)
                    return s_res.results if s_res else []
                except Exception:
                    pass
            return []

        async def fetch_history():
            res = await db.execute(
                select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
            )
            return [{"role": h.role, "content": h.content} for h in res.scalars().all()[-8:]]

        # Execute pre-flight tasks concurrently in parallel (<20ms)
        workspace_obj, retrieved_memories, rag_chunks, web_raw_results, recent_history = await asyncio.gather(
            fetch_workspace(),
            fetch_memories(),
            fetch_rag(),
            fetch_web(),
            fetch_history()
        )

        workspace_instructions = workspace_obj.instructions if workspace_obj else "You are Aetherius AI."
        workspace_name = workspace_obj.name if workspace_obj else "General"

        rag_applied = bool(rag_chunks)
        if rag_applied:
            citations.extend(RAGService.build_citations(rag_chunks))

        web_searched = bool(web_raw_results)
        web_results = []
        if web_searched:
            web_results = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in web_raw_results]
            citations.extend([SourceCitation(source_type="web", title=r.title, url=r.url, snippet=r.snippet) for r in web_raw_results])

        # Assemble Context
        effective_user_message = request.message + attachment_text_context
        if generated_image_url:
            effective_user_message += f"\n\n[Visual Illustration Generated: {generated_image_url}]"

        assembled = ContextEngine.assemble_context(
            model_context_limit=8192,
            max_output_tokens=request.max_tokens or 2048,
            workspace_name=workspace_name,
            workspace_instructions=workspace_instructions,
            memories=retrieved_memories,
            rag_chunks=rag_chunks,
            web_results=web_results,
            chat_history=recent_history,
            current_user_message=effective_user_message
        )

        messages_payload: List[Dict[str, Any]] = [{"role": "system", "content": assembled["system_prompt"]}]
        messages_payload.extend(assembled["fitted_history"])
        user_turn_payload: Dict[str, Any] = {"role": "user", "content": assembled["augmented_prompt"]}
        if image_base64_list:
            user_turn_payload["images"] = image_base64_list
        messages_payload.append(user_turn_payload)

        # Generate LLM response
        assistant_content = await model_manager.generate_response(
            messages=messages_payload,
            model_name=model_to_use or "llama3.2:3b",
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        assistant_metadata = {
            "rag_applied": rag_applied,
            "web_searched": web_searched,
            "routing_reason": routing_reason,
            "execution_mode": execution_mode,
            "image_url": generated_image_url,
        }

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            model_name=model_to_use,
            citations=[c.model_dump() for c in citations],
            token_count=len(assistant_content.split()),
            extra_metadata=assistant_metadata
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        parsed_citations = [SourceCitation(**c) if isinstance(c, dict) else c for c in assistant_msg.citations]

        return ChatCompletionResponse(
            conversation_id=conversation.id,
            user_message=MessageResponse.model_validate(user_msg),
            assistant_message=MessageResponse.model_validate(assistant_msg),
            model_used=model_to_use,
            citations=parsed_citations,
            web_searched=web_searched,
            rag_applied=rag_applied
        )

    @staticmethod
    async def stream_chat_completion(
        db: AsyncSession,
        request: ChatCompletionRequest,
    ) -> AsyncGenerator[str, None]:
        # 1. Fetch or create Conversation
        conversation = None
        if request.conversation_id:
            result = await db.execute(select(Conversation).where(Conversation.id == request.conversation_id))
            conversation = result.scalars().first()

        # 2. Sub-Millisecond Intelligent Dynamic Model Routing
        routing_reason = "Manual model selection"
        execution_mode = "local"
        model_to_use = request.model_name

        if not model_to_use or model_to_use == "auto":
            route_plan = await ModelRouter.evaluate_routing(
                db=db,
                request=RouterEvaluationRequest(
                    prompt=request.message,
                    workspace_slug=request.workspace_slug
                )
            )
            model_to_use = route_plan.selected_model_id
            routing_reason = route_plan.routing_reason
            execution_mode = route_plan.execution_mode

        if not conversation:
            title = request.message[:30] + ("..." if len(request.message) > 30 else "")
            conversation = Conversation(
                workspace_slug=request.workspace_slug,
                title=title,
                model_name=model_to_use or "llama3.2:3b"
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        # 3. Save User Message
        user_metadata = {}
        if request.attachments:
            user_metadata["attachments"] = [a.model_dump() for a in request.attachments]

        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            model_name=model_to_use,
            token_count=len(request.message.split()),
            extra_metadata=user_metadata
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        # Process attachments
        attachment_text_context = ""
        image_base64_list = []
        citations: List[SourceCitation] = []

        if request.attachments:
            for att in request.attachments:
                if att.is_image and att.preview_url:
                    if "base64," in att.preview_url:
                        b64 = att.preview_url.split("base64,")[1]
                        image_base64_list.append(b64)
                    citations.append(SourceCitation(
                        source_type="document",
                        title=f"Attached Image: {att.filename}",
                        snippet=f"Visual upload: {att.filename} ({round(att.file_size_bytes / 1024, 1)} KB)"
                    ))
                elif att.extracted_text:
                    attachment_text_context += f"\n\n--- [Attached Document: {att.filename}] ---\n{att.extracted_text[:6000]}\n--- [End of {att.filename}] ---"
                    citations.append(SourceCitation(
                        source_type="document",
                        title=f"Attached File: {att.filename}",
                        snippet=f"Extracted content from {att.filename} ({round(att.file_size_bytes / 1024, 1)} KB)"
                    ))

        # Check explicit memory command
        explicit_mem_reply = await MemoryService.handle_explicit_memory_commands(
            db=db,
            text=request.message,
            workspace_slug=request.workspace_slug
        )
        if explicit_mem_reply:
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=explicit_mem_reply,
                model_name=model_to_use,
                token_count=len(explicit_mem_reply.split()),
                extra_metadata={"memory_command": True}
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)

            yield f"data: {json.dumps({'type': 'init', 'conversation_id': conversation.id, 'citations': [], 'model_used': model_to_use, 'routing_reason': routing_reason})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'token': explicit_mem_reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id, 'content': explicit_mem_reply, 'conversation_id': conversation.id, 'model_used': model_to_use, 'citations': []})}\n\n"
            return

        # Fetch recent history first to enable deep multi-turn query intelligence
        res_h = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
        )
        recent_history = [{"role": h.role, "content": h.content} for h in res_h.scalars().all()[-8:]]

        # Multi-Turn Semantic Query Intelligence Analysis
        from backend.app.services.query_intelligence_service import QueryIntelligenceService
        q_analysis = await QueryIntelligenceService.analyze_query(
            user_message=request.message,
            conversation_history=recent_history,
            workspace_slug=request.workspace_slug
        )

        is_visual = q_analysis.is_visual

        async def fetch_workspace():
            res = await db.execute(select(Workspace).where(Workspace.slug == request.workspace_slug))
            return res.scalars().first()

        async def fetch_memories():
            if len(request.message.split()) < 3:
                return []
            try:
                scored = await MemoryService.retrieve_relevant_memories(
                    db=db, query=q_analysis.canonical_prompt, workspace_slug=request.workspace_slug, top_k=4, min_similarity=0.1
                )
                return [m for m, _ in scored]
            except Exception:
                return []

        async def fetch_rag():
            if not request.enable_knowledge_rag:
                return []
            try:
                return await RAGService.search_relevant_chunks(
                    db=db, query=q_analysis.canonical_prompt, knowledge_base_slugs=request.knowledge_base_slugs, workspace_slug=request.workspace_slug, top_k=4
                )
            except Exception:
                return []

        async def fetch_web():
            should_search = request.enable_web_search or q_analysis.is_search
            if should_search:
                try:
                    s_res = await WebSearchService.search(q_analysis.canonical_prompt, max_results=4)
                    return s_res.results if s_res else []
                except Exception:
                    pass
            return []

        async def generate_visual():
            if not is_visual:
                return None
            try:
                v_prompt = q_analysis.visual_prompt or request.message
                res = await ImageGenService.generate_image(
                    ImageGenerationRequest(
                        prompt=v_prompt,
                        workspace_slug=request.workspace_slug,
                        style_preset="diagram" if ("diagram" in v_prompt.lower() or "architecture" in v_prompt.lower() or "neural" in v_prompt.lower()) else "photorealistic"
                    )
                )
                return res.preview_url or res.image_url
            except Exception as e:
                logger.warn(f"Visual gen warning: {e}")
                return None

        # Run all remaining pre-flight operations concurrently (<15ms)
        workspace_obj, retrieved_memories, rag_chunks, web_raw_results, generated_image_url = await asyncio.gather(
            fetch_workspace(),
            fetch_memories(),
            fetch_rag(),
            fetch_web(),
            generate_visual()
        )

        workspace_instructions = workspace_obj.instructions if workspace_obj else "You are Aetherius AI."
        workspace_name = workspace_obj.name if workspace_obj else "General"

        rag_applied = bool(rag_chunks)
        if rag_applied:
            citations.extend(RAGService.build_citations(rag_chunks))

        web_searched = bool(web_raw_results)
        web_results = []
        if web_searched:
            web_results = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in web_raw_results]
            citations.extend([SourceCitation(source_type="web", title=r.title, url=r.url, snippet=r.snippet) for r in web_raw_results])

        # Immediate init SSE event with auto-routing badge and conversation ID
        yield f"data: {json.dumps({'type': 'init', 'conversation_id': conversation.id, 'citations': [c.model_dump() for c in citations], 'model_used': model_to_use, 'routing_reason': routing_reason, 'image_url': generated_image_url})}\n\n"

        # If visual image was generated, emit visual event immediately
        if generated_image_url:
            yield f"data: {json.dumps({'type': 'image', 'image_url': generated_image_url, 'prompt': request.message})}\n\n"

        # Assemble Context with Adaptive Intelligence Directives
        effective_user_message = request.message + attachment_text_context
        assembled = ContextEngine.assemble_context(
            model_context_limit=8192,
            max_output_tokens=request.max_tokens or 2048,
            workspace_name=workspace_name,
            workspace_instructions=workspace_instructions,
            memories=retrieved_memories,
            rag_chunks=rag_chunks,
            web_results=web_results,
            chat_history=recent_history,
            current_user_message=effective_user_message
        )

        messages_payload: List[Dict[str, Any]] = [{"role": "system", "content": assembled["system_prompt"]}]
        messages_payload.extend(assembled["fitted_history"])
        user_turn_payload: Dict[str, Any] = {"role": "user", "content": assembled["augmented_prompt"]}
        if image_base64_list:
            user_turn_payload["images"] = image_base64_list
        messages_payload.append(user_turn_payload)

        # Stream LLM tokens directly to client
        accumulated_tokens: List[str] = []
        async for token in model_manager.generate_stream(
            messages=messages_payload,
            model_name=model_to_use or "llama3.2:3b",
            temperature=request.temperature,
            max_tokens=request.max_tokens
        ):
            accumulated_tokens.append(token)
            yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

        assistant_content = "".join(accumulated_tokens)

        # Save Assistant Message
        assistant_metadata = {
            "rag_applied": rag_applied,
            "web_searched": web_searched,
            "routing_reason": routing_reason,
            "execution_mode": execution_mode,
            "image_url": generated_image_url,
            "context_stats": assembled["stats"]
        }

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            model_name=model_to_use,
            citations=[c.model_dump() for c in citations],
            token_count=len(assistant_content.split()),
            extra_metadata=assistant_metadata
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        # Background fact extraction (non-blocking)
        try:
            asyncio.create_task(
                MemoryService.extract_and_store_from_text(
                    db=db,
                    text=request.message,
                    workspace_slug=request.workspace_slug,
                    conversation_id=conversation.id
                )
            )
        except Exception:
            pass

        # Final done SSE event
        yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id, 'content': assistant_content, 'conversation_id': conversation.id, 'model_used': model_to_use, 'citations': [c.model_dump() for c in citations], 'image_url': generated_image_url})}\n\n"
