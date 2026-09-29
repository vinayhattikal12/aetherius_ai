import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.services.conversation_state_service import ConversationStateService, TurnType
from backend.app.services.query_intelligence_service import QueryIntelligenceService
from backend.app.services.context_engine import ContextEngine
from backend.app.models.conversation import Conversation, ConversationState, Message


@pytest.mark.asyncio
async def test_turn_classification():
    """Validates 10-class turn relation classification across conversational scenarios."""
    # 1. New Topic
    assert ConversationStateService.classify_turn(
        current_message="Explain quantum computing principles",
        history=[],
        current_topic=None
    ) == TurnType.NEW_TOPIC

    history = [
        {"role": "user", "content": "How to implement a binary search tree in Rust?"},
        {"role": "assistant", "content": "Here is a complete binary search tree implementation in Rust with TreeNode struct."}
    ]
    topic = "Binary Search Tree in Rust"

    # 2. Modification
    assert ConversationStateService.classify_turn(
        current_message="now rewrite it in python",
        history=history,
        current_topic=topic
    ) == TurnType.MODIFICATION

    assert ConversationStateService.classify_turn(
        current_message="make it faster with async",
        history=history,
        current_topic=topic
    ) == TurnType.MODIFICATION

    # 3. Expansion
    assert ConversationStateService.classify_turn(
        current_message="give 3 more examples of edge cases",
        history=history,
        current_topic=topic
    ) == TurnType.EXPANSION

    # 4. Clarification
    assert ConversationStateService.classify_turn(
        current_message="why did you use Option<Box<Node>>?",
        history=history,
        current_topic=topic
    ) == TurnType.CLARIFICATION

    # 5. Correction
    assert ConversationStateService.classify_turn(
        current_message="No, I meant an AVL balanced tree instead",
        history=history,
        current_topic=topic
    ) == TurnType.CORRECTION

    # 6. Comparison
    assert ConversationStateService.classify_turn(
        current_message="compare it with a B-Tree",
        history=history,
        current_topic=topic
    ) == TurnType.COMPARISON

    # 7. Continuation
    assert ConversationStateService.classify_turn(
        current_message="continue with deletion logic",
        history=history,
        current_topic=topic
    ) == TurnType.CONTINUATION

    # 8. Confirmation
    assert ConversationStateService.classify_turn(
        current_message="got it, thanks!",
        history=history,
        current_topic=topic
    ) == TurnType.CONFIRMATION

    # 9. Follow-up
    assert ConversationStateService.classify_turn(
        current_message="what about its memory complexity?",
        history=history,
        current_topic=topic
    ) == TurnType.FOLLOW_UP


@pytest.mark.asyncio
async def test_generic_anaphora_and_reference_resolution():
    """Validates generic domain-agnostic pronoun and reference resolution."""
    history = [
        {"role": "user", "content": "How does PostgreSQL handle connection pooling with PgBouncer?"},
        {"role": "assistant", "content": "PostgreSQL utilizes PgBouncer in transaction pooling mode to manage persistent backend connections efficiently."}
    ]

    # Test pronoun 'it'
    canonical, topic, refs, constraints = ConversationStateService.resolve_references(
        query="how to optimize it for high throughput?",
        history=history,
        state=None
    )
    assert "PostgreSQL" in canonical or "connection pooling" in canonical.lower()
    assert "it" in refs
    assert "how to optimize it for high throughput" in canonical.lower() or "optimize" in canonical.lower()

    # Test elliptical query 'in Python?'
    canonical_py, topic_py, refs_py, constraints_py = ConversationStateService.resolve_references(
        query="in python?",
        history=history,
        state=None
    )
    assert "PostgreSQL" in canonical_py or "connection pooling" in canonical_py.lower()
    assert constraints_py.get("language") == "python"

    # Test comparative query
    canonical_comp, _, _, _ = ConversationStateService.resolve_references(
        query="compare it with redis cache",
        history=history,
        state=None
    )
    assert "PostgreSQL" in canonical_comp or "connection pooling" in canonical_comp.lower()


@pytest.mark.asyncio
async def test_multi_turn_constraint_accumulation():
    """Validates continuous accumulation of constraints over multiple conversation turns."""
    # Turn 1
    c1 = ConversationStateService.extract_constraints("Recommend high performance vector databases")
    assert c1 == {}

    # Turn 2: license constraint
    c2 = ConversationStateService.extract_constraints("only open source options")
    assert c2.get("license") == "open_source"

    # Turn 3: platform & hardware constraint
    c3 = ConversationStateService.extract_constraints("that can run locally on windows with 16gb ram")
    assert c3.get("platform") == "windows"
    assert c3.get("memory_limit") == "16GB"

    # Turn 4: format constraint
    c4 = ConversationStateService.extract_constraints("output as a markdown table")
    assert c4.get("format") == "table"

    # Merged accumulation
    accumulated = {}
    for c in [c1, c2, c3, c4]:
        accumulated.update(c)

    assert accumulated["license"] == "open_source"
    assert accumulated["platform"] == "windows"
    assert accumulated["memory_limit"] == "16GB"
    assert accumulated["format"] == "table"


@pytest.mark.asyncio
async def test_conversation_state_postgres_roundtrip(test_db: AsyncSession):
    """Tests saving, updating, and reloading ConversationState in PostgreSQL."""
    # 1. Create Conversation
    conv = Conversation(
        workspace_slug="general",
        title="PostgreSQL State Tracking Test",
        model_name="llama3.2:3b"
    )
    test_db.add(conv)
    await test_db.commit()
    await test_db.refresh(conv)

    # 2. Get or create state
    state = await ConversationStateService.get_or_create_state(test_db, conv.id)
    assert state.conversation_id == conv.id
    assert state.turn_count == 0

    # 3. Update Turn 1
    state = await ConversationStateService.update_state_turn(
        db=test_db,
        conversation_id=conv.id,
        user_message="Explain FastAPI background tasks",
        turn_type=TurnType.NEW_TOPIC,
        resolved_topic="FastAPI background tasks",
        canonical_prompt="Explain FastAPI background tasks",
        entities={"FastAPI": {"type": "framework", "mentions": 1}},
        references={"subject": "FastAPI background tasks"},
        constraints={"language": "python"},
        assistant_summary="FastAPI background tasks allow running long-running operations in the background."
    )
    assert state.turn_count == 1
    assert state.topic == "FastAPI background tasks"
    assert state.constraints.get("language") == "python"
    assert len(state.previous_results) == 1

    # 4. Update Turn 2 (Follow-up)
    state = await ConversationStateService.update_state_turn(
        db=test_db,
        conversation_id=conv.id,
        user_message="how to handle error logging in them?",
        turn_type=TurnType.FOLLOW_UP,
        resolved_topic="FastAPI background tasks - error logging",
        canonical_prompt="FastAPI background tasks: how to handle error logging",
        entities={"Logging": {"type": "module", "mentions": 1}},
        references={"them": "FastAPI background tasks"},
        constraints={"language": "python", "format": "step_by_step"},
        assistant_summary="Wrap task logic in a try-except block and use python logging."
    )
    assert state.turn_count == 2
    assert state.turn_type == TurnType.FOLLOW_UP
    assert state.constraints.get("format") == "step_by_step"
    assert len(state.previous_results) == 2


@pytest.mark.asyncio
async def test_context_engine_with_conversation_state():
    """Validates that ContextEngine incorporates ConversationState directives into assembled prompt."""
    conv_state = {
        "topic": "PostgreSQL Query Optimization",
        "turn_type": "CORRECTION",
        "subtopics": ["B-Tree Indexes", "EXPLAIN ANALYZE"],
        "references": {"it": "PostgreSQL Query Optimization"},
        "last_user_goal": "Optimize slow join query"
    }
    accumulated_constraints = {
        "license": "open_source",
        "platform": "linux",
        "memory_limit": "32GB"
    }

    assembled = ContextEngine.assemble_context(
        model_context_limit=4096,
        max_output_tokens=1024,
        workspace_name="Database Architecture",
        workspace_instructions="Provide enterprise DB guidance.",
        chat_history=[
            {"role": "user", "content": "How to optimize queries?"},
            {"role": "assistant", "content": "Use indexes and query planners."}
        ],
        current_user_message="No, I meant optimizing partitioned table joins",
        accumulated_constraints=accumulated_constraints,
        conversation_state=conv_state
    )

    sys_prompt = assembled["system_prompt"]
    augmented = assembled["augmented_prompt"]

    # Verify Conversation State layer in system prompt
    assert "CONVERSATION STATE & TURN INTELLIGENCE" in sys_prompt
    assert "PostgreSQL Query Optimization" in sys_prompt
    assert "CORRECTION" in sys_prompt

    # Verify Accumulated Constraints layer
    assert "ACCUMULATED MULTI-TURN CONSTRAINTS" in augmented
    assert "License: `open_source`" in augmented or "open_source" in augmented
    assert "32GB" in augmented
