import asyncio
import json
import uuid
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
from backend.app.schemas.intelligence import ResolvedTask
from backend.app.services.rag_service import RAGService
from backend.app.services.web_search_service import WebSearchService
from backend.app.services.memory_service import MemoryService
from backend.app.services.context_engine import ContextEngine
from backend.app.services.router_service import ModelRouter
from backend.app.services.tool_service import ToolExecutionEngine, ToolExecutionRequest
from backend.app.services.image_gen_service import ImageGenService, ImageGenerationRequest
from backend.app.services.conversation_state_service import ConversationStateService
from backend.app.services.query_intelligence_service import QueryIntelligenceService
from backend.app.services.evidence import AnswerValidationEngine
from backend.app.services.providers.model_manager import model_manager
from backend.app.core.logging import logger


class ChatService:
    """
    Authoritative 14-Step Intelligence Pipeline for Aetherius AI.
    Executes conversational understanding, generic entity/reference resolution,
    task planning, routing, tool & evidence grounding, model execution,
    closed-loop answer validation/repair, and atomic state persistence.
    """

    @staticmethod
    async def process_chat_completion(
        db: AsyncSession,
        request: ChatCompletionRequest,
    ) -> ChatCompletionResponse:
        request_id = str(uuid.uuid4())

        # =========================================================================
        # STEP 1 & 2: Load Conversation, Recent History, State, Workspace, Memory
        # =========================================================================
        conversation = None
        if request.conversation_id:
            result = await db.execute(select(Conversation).where(Conversation.id == request.conversation_id))
            conversation = result.scalars().first()

        recent_history: List[Dict[str, str]] = []
        if conversation:
            res_h = await db.execute(
                select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
            )
            recent_history = [{"role": h.role, "content": h.content} for h in res_h.scalars().all()[-10:]]

        # Load persistent state
        conv_state = None
        if conversation:
            conv_state = await ConversationStateService.get_or_create_state(db, conversation.id)

        # Check explicit memory command before full generation
        explicit_mem_reply = await MemoryService.handle_explicit_memory_commands(
            db=db,
            text=request.message,
            workspace_slug=request.workspace_slug
        )
        if explicit_mem_reply:
            if not conversation:
                conversation = Conversation(
                    workspace_slug=request.workspace_slug,
                    title="Memory Command",
                    model_name=request.model_name or "llama3.2:3b"
                )
                db.add(conversation)
                await db.commit()
                await db.refresh(conversation)

            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=request.message,
                model_name=request.model_name or "llama3.2:3b",
                token_count=len(request.message.split())
            )
            db.add(user_msg)
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=explicit_mem_reply,
                model_name=request.model_name or "llama3.2:3b",
                token_count=len(explicit_mem_reply.split()),
                extra_metadata={"memory_command": True}
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(user_msg)
            await db.refresh(assistant_msg)

            return ChatCompletionResponse(
                conversation_id=conversation.id,
                user_message=MessageResponse.model_validate(user_msg),
                assistant_message=MessageResponse.model_validate(assistant_msg),
                model_used=request.model_name or "llama3.2:3b",
                citations=[],
                web_searched=False,
                rag_applied=False
            )

        # =========================================================================
        # STEP 3, 4, 5 & 6: Conversation Understanding, Anaphora, Task Plan
        # =========================================================================
        q_analysis = await QueryIntelligenceService.analyze_query(
            user_message=request.message,
            conversation_history=recent_history,
            workspace_slug=request.workspace_slug,
            conversation_state=conv_state,
            request_id=request_id
        )
        resolved_task: ResolvedTask = q_analysis.resolved_task

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

        # Autonomous Visual Generation if requested
        generated_image_url: Optional[str] = None
        if resolved_task.is_visual:
            try:
                v_prompt = resolved_task.visual_prompt or request.message
                img_res = await ImageGenService.generate_image(
                    ImageGenerationRequest(
                        prompt=v_prompt,
                        workspace_slug=request.workspace_slug,
                        style_preset="diagram" if ("diagram" in v_prompt.lower() or "architecture" in v_prompt.lower() or "neural" in v_prompt.lower()) else "photorealistic"
                    )
                )
                generated_image_url = img_res.preview_url or img_res.image_url
            except Exception as e:
                logger.warning(f"Visual illustration notice: {e}")

        # =========================================================================
        # STEP 7: Model & Execution Routing based on authoritative ResolvedTask
        # =========================================================================
        routing_reason = "Manual model selection"
        execution_mode = "local"
        model_to_use = request.model_name

        if not model_to_use or model_to_use == "auto":
            route_plan = await ModelRouter.evaluate_routing(
                db=db,
                request=RouterEvaluationRequest(
                    prompt=resolved_task.canonical_query,
                    workspace_slug=request.workspace_slug,
                    privacy_mode=resolved_task.privacy_mode
                ),
                resolved_task=resolved_task
            )
            model_to_use = route_plan.selected_model_id
            routing_reason = route_plan.routing_reason
            execution_mode = route_plan.execution_mode

        # =========================================================================
        # STEP 8: Tool & Retrieval Execution based on TaskPlan
        # =========================================================================
        async def fetch_workspace():
            res = await db.execute(select(Workspace).where(Workspace.slug == request.workspace_slug))
            return res.scalars().first()

        async def fetch_memories():
            if len(request.message.split()) < 3 and not any(k in request.message.lower() for k in ["i am", "my", "prefer", "remember"]):
                return []
            try:
                scored = await MemoryService.retrieve_relevant_memories(
                    db=db, query=resolved_task.canonical_query, workspace_slug=request.workspace_slug, top_k=4, min_similarity=0.1
                )
                return [m for m, _ in scored]
            except Exception:
                return []

        async def fetch_rag():
            if not request.enable_knowledge_rag and not resolved_task.plan.requires_rag:
                return []
            lower_q = resolved_task.canonical_query.lower().strip()
            is_casual_or_greeting = (
                lower_q in ["hi", "hello", "hey", "hello aetherius", "hi aetherius", "hey aetherius", "good morning", "good evening", "how are you", "who are you", "what can you do", "help", "ping"]
                or (len(lower_q.split()) <= 2 and not any(k in lower_q for k in ["doc", "file", "spec", "pdf", "arch", "kb", "rag", "code", "table", "data"]))
            )
            if is_casual_or_greeting:
                return []
            try:
                return await RAGService.search_relevant_chunks(
                    db=db, query=resolved_task.canonical_query, knowledge_base_slugs=request.knowledge_base_slugs, workspace_slug=request.workspace_slug, top_k=4, min_similarity=0.65
                )
            except Exception:
                return []

        async def fetch_web():
            should_search = request.enable_web_search or resolved_task.plan.requires_web_search
            if should_search:
                try:
                    s_res = await WebSearchService.search(resolved_task.canonical_query, max_results=4)
                    return s_res.results if s_res else []
                except Exception:
                    pass
            return []

        # Execute pre-flight retrieval concurrently
        workspace_obj, retrieved_memories, rag_chunks, web_raw_results = await asyncio.gather(
            fetch_workspace(),
            fetch_memories(),
            fetch_rag(),
            fetch_web()
        )

        workspace_instructions = workspace_obj.instructions if workspace_obj else "You are Aetherius AI."
        workspace_name = workspace_obj.name if workspace_obj else "General"

        rag_applied = bool(rag_chunks)
        if rag_applied:
            citations.extend(RAGService.build_citations(rag_chunks))

        web_searched = bool(web_raw_results)
        web_results = []
        if web_searched:
            web_results = [{"title": r.title, "url": r.url, "snippet": r.snippet, "deep_content": getattr(r, "deep_content", None)} for r in web_raw_results]
            citations.extend([SourceCitation(source_type="web", title=r.title, url=r.url, snippet=r.deep_content[:300] if getattr(r, "deep_content", None) else r.snippet) for r in web_raw_results])

        # =========================================================================
        # STEP 9: Context Assembly
        # =========================================================================
        effective_user_message = request.message + attachment_text_context
        if generated_image_url:
            effective_user_message += f"\n\n[Visual Illustration Generated: {generated_image_url}]"

        state_payload = {
            "topic": resolved_task.active_subject or (conv_state.topic if conv_state else None),
            "turn_type": resolved_task.turn_type,
            "subtopics": conv_state.subtopics if conv_state else [],
            "references": resolved_task.resolved_references,
            "last_user_goal": resolved_task.canonical_query,
        }

        assembled = ContextEngine.assemble_context(
            model_context_limit=8192,
            max_output_tokens=request.max_tokens or 2048,
            workspace_name=workspace_name,
            workspace_instructions=workspace_instructions,
            memories=retrieved_memories,
            rag_chunks=rag_chunks,
            web_results=web_results,
            chat_history=recent_history,
            current_user_message=effective_user_message,
            accumulated_constraints=resolved_task.accumulated_constraints,
            conversation_state=state_payload
        )

        messages_payload: List[Dict[str, Any]] = [{"role": "system", "content": assembled["system_prompt"]}]
        messages_payload.extend(assembled["fitted_history"])
        user_turn_payload: Dict[str, Any] = {"role": "user", "content": assembled["augmented_prompt"]}
        if image_base64_list:
            user_turn_payload["images"] = image_base64_list
        messages_payload.append(user_turn_payload)

        # =========================================================================
        # STEP 10, 11 & 12: Model Execution with Closed-Loop Validation & Self-Repair
        # =========================================================================
        assistant_content = ""
        exec_meta_dict = {}
        val_report = None
        retries = 0
        max_retries = 2

        evidence_text_list = [w.get("snippet", "") + " " + (w.get("deep_content") or "") for w in web_results] + [c.content for c, _ in rag_chunks]

        while retries <= max_retries:
            try:
                assistant_content, exec_meta = await model_manager.generate_response_with_metadata(
                    messages=messages_payload,
                    model_name=model_to_use or "llama3.2:3b",
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    requested_mode="auto" if not request.model_name or request.model_name == "auto" else "manual"
                )
                exec_meta_dict = exec_meta.to_dict()
            except Exception as e:
                logger.error(f"Model execution error: {e}")
                assistant_content = (
                    f"I couldn't complete the request because the selected model ({model_to_use}) is unavailable "
                    f"and no reachable fallback provider was configured. Details: {str(e)}"
                )
                exec_meta_dict = {
                    "requested_mode": "auto" if not request.model_name or request.model_name == "auto" else "manual",
                    "selected_model": model_to_use,
                    "actual_model": "none",
                    "provider": "none",
                    "runtime": "offline",
                    "fallback_used": False,
                    "reason": str(e)
                }
                break

            # Validate response
            val_report = AnswerValidationEngine.validate_response(
                response_text=assistant_content,
                constraints=resolved_task.accumulated_constraints,
                available_sources=[c.model_dump() for c in citations],
                evidence_chunks=evidence_text_list
            )

            if val_report.is_valid or retries == max_retries:
                break

            # Attempt repair
            retries += 1
            logger.info(f"Self-repair attempt {retries}/{max_retries}: {val_report.issues}")
            messages_payload.append({"role": "assistant", "content": assistant_content})
            messages_payload.append({"role": "user", "content": val_report.repair_instruction})

        # =========================================================================
        # STEP 13 & 14: Atomic State Persistence
        # =========================================================================
        if not conversation:
            title = resolved_task.canonical_query[:30] + ("..." if len(resolved_task.canonical_query) > 30 else "")
            conversation = Conversation(
                workspace_slug=request.workspace_slug,
                title=title,
                model_name=model_to_use or "llama3.2:3b"
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        # Save User Message
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

        # Save Assistant Message
        assistant_metadata = {
            "rag_applied": rag_applied,
            "web_searched": web_searched,
            "routing_reason": routing_reason,
            "execution_mode": execution_mode,
            "image_url": generated_image_url,
            "context_stats": assembled["stats"],
            "constraints_applied": resolved_task.accumulated_constraints,
            "turn_type": resolved_task.turn_type,
            "canonical_prompt": resolved_task.canonical_query,
            "resolved_topic": resolved_task.active_subject,
            "execution_metadata": exec_meta_dict,
            "validation_report": val_report.model_dump() if val_report else {},
        }

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            model_name=exec_meta_dict.get("actual_model") or model_to_use,
            citations=[c.model_dump() for c in citations],
            token_count=len(assistant_content.split()),
            extra_metadata=assistant_metadata
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        # Update Conversation State only on successful turn
        try:
            await ConversationStateService.update_state_turn(
                db=db,
                conversation_id=conversation.id,
                user_message=request.message,
                turn_type=resolved_task.turn_type,
                resolved_topic=resolved_task.active_subject or request.message[:50],
                canonical_prompt=resolved_task.canonical_query,
                entities=ConversationStateService.extract_entities(request.message),
                references=resolved_task.resolved_references,
                constraints=resolved_task.accumulated_constraints,
                assistant_summary=assistant_content[:300]
            )
        except Exception as state_err:
            logger.warning(f"State update notice: {state_err}")

        # Inline fact extraction
        try:
            await MemoryService.extract_and_store_from_text(
                db=db,
                text=request.message,
                workspace_slug=request.workspace_slug,
                conversation_id=conversation.id
            )
        except Exception as e:
            logger.debug(f"Fact extraction notice: {e}")

        return ChatCompletionResponse(
            conversation_id=conversation.id,
            user_message=MessageResponse.model_validate(user_msg),
            assistant_message=MessageResponse.model_validate(assistant_msg),
            model_used=model_to_use,
            citations=citations,
            web_searched=web_searched,
            rag_applied=rag_applied,
            image_url=generated_image_url
        )

    @staticmethod
    async def stream_chat_completion(
        db: AsyncSession,
        request: ChatCompletionRequest,
    ) -> AsyncGenerator[str, None]:
        request_id = str(uuid.uuid4())

        # 1. Load Conversation, History & State
        conversation = None
        if request.conversation_id:
            result = await db.execute(select(Conversation).where(Conversation.id == request.conversation_id))
            conversation = result.scalars().first()

        recent_history: List[Dict[str, str]] = []
        if conversation:
            res_h = await db.execute(
                select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
            )
            recent_history = [{"role": h.role, "content": h.content} for h in res_h.scalars().all()[-10:]]

        conv_state = None
        if conversation:
            conv_state = await ConversationStateService.get_or_create_state(db, conversation.id)

        # Check explicit memory command
        explicit_mem_reply = await MemoryService.handle_explicit_memory_commands(
            db=db,
            text=request.message,
            workspace_slug=request.workspace_slug
        )
        if explicit_mem_reply:
            if not conversation:
                conversation = Conversation(
                    workspace_slug=request.workspace_slug,
                    title="Memory Command",
                    model_name=request.model_name or "llama3.2:3b"
                )
                db.add(conversation)
                await db.commit()
                await db.refresh(conversation)

            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=request.message,
                model_name=request.model_name or "llama3.2:3b",
                token_count=len(request.message.split())
            )
            db.add(user_msg)
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=explicit_mem_reply,
                model_name=request.model_name or "llama3.2:3b",
                token_count=len(explicit_mem_reply.split()),
                extra_metadata={"memory_command": True}
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)

            yield f"data: {json.dumps({'type': 'init', 'conversation_id': conversation.id, 'citations': [], 'model_used': request.model_name or 'llama3.2:3b', 'routing_reason': 'Explicit Memory Command'})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'token': explicit_mem_reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id, 'content': explicit_mem_reply, 'conversation_id': conversation.id, 'model_used': request.model_name or 'llama3.2:3b', 'citations': []})}\n\n"
            return

        # 2. Conversation Intelligence & Task Planning
        q_analysis = await QueryIntelligenceService.analyze_query(
            user_message=request.message,
            conversation_history=recent_history,
            workspace_slug=request.workspace_slug,
            conversation_state=conv_state,
            request_id=request_id
        )
        resolved_task: ResolvedTask = q_analysis.resolved_task

        citations: List[SourceCitation] = []

        # 3. Model Routing
        routing_reason = "Manual model selection"
        execution_mode = "local"
        model_to_use = request.model_name

        if not model_to_use or model_to_use == "auto":
            route_plan = await ModelRouter.evaluate_routing(
                db=db,
                request=RouterEvaluationRequest(
                    prompt=resolved_task.canonical_query,
                    workspace_slug=request.workspace_slug,
                    privacy_mode=resolved_task.privacy_mode
                ),
                resolved_task=resolved_task
            )
            model_to_use = route_plan.selected_model_id
            routing_reason = route_plan.routing_reason
            execution_mode = route_plan.execution_mode

        # 4. Tool & Evidence Retrieval
        async def fetch_workspace():
            res = await db.execute(select(Workspace).where(Workspace.slug == request.workspace_slug))
            return res.scalars().first()

        async def fetch_memories():
            if len(request.message.split()) < 3:
                return []
            try:
                scored = await MemoryService.retrieve_relevant_memories(
                    db=db, query=resolved_task.canonical_query, workspace_slug=request.workspace_slug, top_k=4, min_similarity=0.1
                )
                return [m for m, _ in scored]
            except Exception:
                return []

        async def fetch_rag():
            if not request.enable_knowledge_rag and not resolved_task.plan.requires_rag:
                return []
            lower_q = resolved_task.canonical_query.lower().strip()
            is_casual_or_greeting = (
                lower_q in ["hi", "hello", "hey", "hello aetherius", "hi aetherius", "hey aetherius", "good morning", "good evening", "how are you", "who are you", "what can you do", "help", "ping"]
                or (len(lower_q.split()) <= 2 and not any(k in lower_q for k in ["doc", "file", "spec", "pdf", "arch", "kb", "rag", "code", "table", "data"]))
            )
            if is_casual_or_greeting:
                return []
            try:
                return await RAGService.search_relevant_chunks(
                    db=db, query=resolved_task.canonical_query, knowledge_base_slugs=request.knowledge_base_slugs, workspace_slug=request.workspace_slug, top_k=4, min_similarity=0.65
                )
            except Exception:
                return []

        async def fetch_web():
            should_search = request.enable_web_search or resolved_task.plan.requires_web_search
            if should_search:
                try:
                    s_res = await WebSearchService.search(resolved_task.canonical_query, max_results=4)
                    return s_res.results if s_res else []
                except Exception:
                    pass
            return []

        workspace_obj, retrieved_memories, rag_chunks, web_raw_results = await asyncio.gather(
            fetch_workspace(),
            fetch_memories(),
            fetch_rag(),
            fetch_web()
        )

        workspace_instructions = workspace_obj.instructions if workspace_obj else "You are Aetherius AI."
        workspace_name = workspace_obj.name if workspace_obj else "General"

        rag_applied = bool(rag_chunks)
        if rag_applied:
            citations.extend(RAGService.build_citations(rag_chunks))

        web_searched = bool(web_raw_results)
        web_results = []
        if web_searched:
            web_results = [{"title": r.title, "url": r.url, "snippet": r.snippet, "deep_content": getattr(r, "deep_content", None)} for r in web_raw_results]
            citations.extend([SourceCitation(source_type="web", title=r.title, url=r.url, snippet=r.deep_content[:300] if getattr(r, "deep_content", None) else r.snippet) for r in web_raw_results])

        # 5. Context Assembly
        state_payload = {
            "topic": resolved_task.active_subject or (conv_state.topic if conv_state else None),
            "turn_type": resolved_task.turn_type,
            "subtopics": conv_state.subtopics if conv_state else [],
            "references": resolved_task.resolved_references,
            "last_user_goal": resolved_task.canonical_query,
        }

        assembled = ContextEngine.assemble_context(
            model_context_limit=8192,
            max_output_tokens=request.max_tokens or 2048,
            workspace_name=workspace_name,
            workspace_instructions=workspace_instructions,
            memories=retrieved_memories,
            rag_chunks=rag_chunks,
            web_results=web_results,
            chat_history=recent_history,
            current_user_message=request.message,
            accumulated_constraints=resolved_task.accumulated_constraints,
            conversation_state=state_payload
        )

        messages_payload: List[Dict[str, Any]] = [{"role": "system", "content": assembled["system_prompt"]}]
        messages_payload.extend(assembled["fitted_history"])
        messages_payload.append({"role": "user", "content": assembled["augmented_prompt"]})

        if not conversation:
            title = resolved_task.canonical_query[:30] + ("..." if len(resolved_task.canonical_query) > 30 else "")
            conversation = Conversation(
                workspace_slug=request.workspace_slug,
                title=title,
                model_name=model_to_use or "llama3.2:3b"
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        # Save User Message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            model_name=model_to_use,
            token_count=len(request.message.split())
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)

        # Send SSE init event
        yield f"data: {json.dumps({'type': 'init', 'conversation_id': conversation.id, 'citations': [c.model_dump() for c in citations], 'model_used': model_to_use, 'routing_reason': routing_reason})}\n\n"

        # Stream tokens
        full_response_text = ""
        actual_model_name = model_to_use
        provider_name = "ollama"

        try:
            async for token in model_manager.stream_response(
                messages=messages_payload,
                model_name=model_to_use or "llama3.2:3b",
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                full_response_text += token
                yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"
        except Exception as e:
            err_msg = f"\n[Model stream interrupted: {str(e)}]"
            full_response_text += err_msg
            yield f"data: {json.dumps({'type': 'token', 'token': err_msg})}\n\n"

        # Save Assistant Message
        assistant_metadata = {
            "rag_applied": rag_applied,
            "web_searched": web_searched,
            "routing_reason": routing_reason,
            "execution_mode": execution_mode,
            "constraints_applied": resolved_task.accumulated_constraints,
            "turn_type": resolved_task.turn_type,
            "canonical_prompt": resolved_task.canonical_query,
            "resolved_topic": resolved_task.active_subject,
        }

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=full_response_text,
            model_name=actual_model_name,
            citations=[c.model_dump() for c in citations],
            token_count=len(full_response_text.split()),
            extra_metadata=assistant_metadata
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        # Update Conversation State
        try:
            await ConversationStateService.update_state_turn(
                db=db,
                conversation_id=conversation.id,
                user_message=request.message,
                turn_type=resolved_task.turn_type,
                resolved_topic=resolved_task.active_subject or request.message[:50],
                canonical_prompt=resolved_task.canonical_query,
                entities=ConversationStateService.extract_entities(request.message),
                references=resolved_task.resolved_references,
                constraints=resolved_task.accumulated_constraints,
                assistant_summary=full_response_text[:300]
            )
        except Exception as state_err:
            logger.warning(f"State update notice: {state_err}")

        # Send SSE done event
        yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id, 'content': full_response_text, 'conversation_id': conversation.id, 'model_used': actual_model_name, 'citations': [c.model_dump() for c in citations]})}\n\n"
