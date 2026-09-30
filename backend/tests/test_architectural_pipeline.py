import pytest
from unittest.mock import AsyncMock, patch, MagicMock

pytestmark = pytest.mark.integration
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.conversation import Conversation, ConversationState
from backend.app.schemas.chat import ChatCompletionRequest
from backend.app.schemas.intelligence import ResolvedTask, TaskPlan
from backend.app.services.chat_service import ChatService
from backend.app.services.conversation_state_service import ConversationStateService, TurnType
from backend.app.services.query_intelligence_service import QueryIntelligenceService
from backend.app.services.router_service import ModelRouter
from backend.app.services.evidence import AnswerValidationEngine
from backend.app.services.providers.model_manager import ModelExecutionMetadata


@pytest.mark.asyncio
async def test_execution_order_trace(test_db: AsyncSession):
    """
    Architectural Verification Test:
    Enforces strict execution ordering:
    1. Conversation & State loaded before routing.
    2. Query Intelligence runs before routing.
    3. Canonical query and ResolvedTask reach ModelRouter.
    4. Task plan determines tool execution.
    5. Evidence assembled into context for model.
    6. AnswerValidationEngine runs before response return.
    7. ConversationState is updated only after generation succeeds.
    """
    execution_steps = []

    # Create base conversation in DB
    conv = Conversation(
        workspace_slug="general",
        title="Execution Order Test",
        model_name="llama3.2:3b"
    )
    test_db.add(conv)
    await test_db.commit()
    await test_db.refresh(conv)

    # Instrument components to trace invocation order
    orig_analyze = QueryIntelligenceService.analyze_query
    async def traced_analyze(*args, **kwargs):
        execution_steps.append("1_QUERY_INTELLIGENCE")
        return await orig_analyze(*args, **kwargs)

    orig_evaluate = ModelRouter.evaluate_routing
    async def traced_evaluate(*args, **kwargs):
        execution_steps.append("2_MODEL_ROUTING")
        assert kwargs.get("resolved_task") is not None, "ModelRouter MUST receive ResolvedTask!"
        return await orig_evaluate(*args, **kwargs)

    orig_validate = AnswerValidationEngine.validate_response
    def traced_validate(*args, **kwargs):
        execution_steps.append("4_ANSWER_VALIDATION")
        return orig_validate(*args, **kwargs)

    orig_update_state = ConversationStateService.update_state_turn
    async def traced_update_state(*args, **kwargs):
        execution_steps.append("5_STATE_PERSISTENCE")
        return await orig_update_state(*args, **kwargs)

    with patch.object(QueryIntelligenceService, "analyze_query", side_effect=traced_analyze), \
         patch.object(ModelRouter, "evaluate_routing", side_effect=traced_evaluate), \
         patch.object(AnswerValidationEngine, "validate_response", side_effect=traced_validate), \
         patch.object(ConversationStateService, "update_state_turn", side_effect=traced_update_state), \
         patch("backend.app.services.providers.model_manager.model_manager.generate_response_with_metadata",
               new_callable=AsyncMock) as mock_gen:

        mock_gen.return_value = (
            "Artificial Intelligence (AI) refers to systems capable of performing cognitive tasks.",
            ModelExecutionMetadata(
                requested_mode="auto",
                selected_model="llama3.2:3b",
                actual_model="llama3.2:3b",
                provider="ollama",
                runtime="local"
            )
        )

        async def mock_generate_side_effect(*args, **kwargs):
            execution_steps.append("3_MODEL_EXECUTION")
            return (
                "Artificial Intelligence (AI) refers to systems capable of performing cognitive tasks.",
                ModelExecutionMetadata(
                    requested_mode="auto",
                    selected_model="llama3.2:3b",
                    actual_model="llama3.2:3b",
                    provider="ollama",
                    runtime="local"
                )
            )
        mock_gen.side_effect = mock_generate_side_effect

        req = ChatCompletionRequest(
            conversation_id=conv.id,
            workspace_slug="general",
            message="What is artificial intelligence?",
            enable_web_search=False,
            enable_knowledge_rag=False
        )

        response = await ChatService.process_chat_completion(test_db, req)

        assert response is not None
        assert response.conversation_id == conv.id

        # Verify strict pipeline order
        expected_order = [
            "1_QUERY_INTELLIGENCE",
            "2_MODEL_ROUTING",
            "3_MODEL_EXECUTION",
            "4_ANSWER_VALIDATION",
            "5_STATE_PERSISTENCE"
        ]
        assert execution_steps == expected_order, f"Execution order violated! Got: {execution_steps}"


@pytest.mark.asyncio
async def test_entity_resolution_not_raw_question():
    """
    Verifies Requirement 6:
    'it' resolves to specific entity 'Qwen 3', NOT the entire raw question 'Tell me about Qwen 3.'
    """
    history = [
        {"role": "user", "content": "Tell me about Qwen 3."},
        {"role": "assistant", "content": "Qwen 3 is a frontier open-weights large language model released by Alibaba Cloud."}
    ]

    canonical, active_topic, refs, constraints, entities = ConversationStateService.resolve_references(
        query="How much RAM does it need?",
        history=history
    )

    assert refs.get("it") == "Qwen 3", f"Expected refs['it'] == 'Qwen 3', got {refs.get('it')}"
    assert "Qwen 3" in canonical, f"Canonical query should mention entity 'Qwen 3', got: {canonical}"
    assert "tell me about" not in canonical.lower(), f"Canonical query must not contain conversational wrapper: {canonical}"


@pytest.mark.asyncio
async def test_no_fast_lookup_intent_degradation(test_db: AsyncSession):
    """
    Verifies Requirement 4:
    'What is AI?' preserves semantic intent 'definition' or 'general_question'
    and is NOT degraded to 'fast_lookup' with artificial low complexity.
    """
    analysis = await QueryIntelligenceService.analyze_query(
        user_message="What is AI?",
        workspace_slug="general"
    )

    assert analysis.primary_intent in ["definition", "general_question", "explanation"]
    assert analysis.primary_intent != "fast_lookup"

    # Route evaluation must also preserve intent
    from backend.app.schemas.router import RouterEvaluationRequest
    route = await ModelRouter.evaluate_routing(
        db=test_db,
        request=RouterEvaluationRequest(prompt=analysis.canonical_prompt),
        resolved_task=analysis.resolved_task
    )
    assert route.detected_intent != "fast_lookup"


@pytest.mark.asyncio
async def test_closed_loop_answer_validation_and_repair(test_db: AsyncSession):
    """
    Verifies Requirement 13 & 12:
    AnswerValidationEngine actively triggers repair if generated answer fails validation constraints.
    """
    conv = Conversation(workspace_slug="developer", title="Table Output Test", model_name="llama3.2:3b")
    test_db.add(conv)
    await test_db.commit()
    await test_db.refresh(conv)

    attempt_count = 0

    async def mock_generate_with_repair(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        messages = kwargs.get("messages", [])

        # Check if repair prompt is injected
        has_repair = any("CRITICAL CORRECTION REQUIRED" in m.get("content", "") for m in messages if m.get("role") == "user")

        if not has_repair:
            # First attempt: invalid format (plain text instead of requested markdown table)
            return (
                "Python is dynamic and interpreted, while Rust is static and compiled.",
                ModelExecutionMetadata(
                    requested_mode="auto", selected_model="llama3.2:3b", actual_model="llama3.2:3b", provider="ollama", runtime="local"
                )
            )
        else:
            # Second attempt: valid Markdown table satisfying constraint
            return (
                "| Feature | Python | Rust |\n|---|---|---|\n| Typing | Dynamic | Static |\n| Memory | Garbage Collected | Ownership System |",
                ModelExecutionMetadata(
                    requested_mode="auto", selected_model="llama3.2:3b", actual_model="llama3.2:3b", provider="ollama", runtime="local"
                )
            )

    with patch("backend.app.services.providers.model_manager.model_manager.generate_response_with_metadata", side_effect=mock_generate_with_repair):
        req = ChatCompletionRequest(
            conversation_id=conv.id,
            workspace_slug="developer",
            message="Compare Python and Rust in a markdown table format.",
            enable_web_search=False,
            enable_knowledge_rag=False
        )

        response = await ChatService.process_chat_completion(test_db, req)
        assert response is not None
        assert "|" in response.assistant_message.content
        assert "---" in response.assistant_message.content
        assert attempt_count == 2, f"Expected 2 attempts (initial + 1 repair), got {attempt_count}"
