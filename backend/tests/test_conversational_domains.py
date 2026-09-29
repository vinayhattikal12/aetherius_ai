import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.conversation import Conversation, ConversationState
from backend.app.schemas.chat import ChatCompletionRequest
from backend.app.services.chat_service import ChatService
from backend.app.services.conversation_state_service import ConversationStateService, TurnType
from backend.app.services.query_intelligence_service import QueryIntelligenceService
from backend.app.services.providers.model_manager import ModelExecutionMetadata


@pytest.mark.asyncio
async def test_simple_and_general_conversation_chain(test_db: AsyncSession):
    """
    Verifies Requirement 17 & 18:
    Multi-turn chain across general concepts:
    Turn 1: 'What is Python?'
    Turn 2: 'How is it different from Java?' -> it resolves to Python
    Turn 3: 'Which is easier?' -> comparison of Python vs Java
    Turn 4: 'What about jobs?' -> job opportunities for Python / Java
    Turn 5: 'In India?' -> in India context
    Turn 6: 'Give me some examples.' -> examples in India
    """
    history = []

    # Turn 1
    t1 = "What is Python?"
    c1, topic1, refs1, const1, ent1 = ConversationStateService.resolve_references(t1, history)
    assert "Python" in c1
    history.append({"role": "user", "content": t1})
    history.append({"role": "assistant", "content": "Python is a high-level, interpreted programming language known for readability."})

    # Turn 2: 'How is it different from Java?'
    t2 = "How is it different from Java?"
    c2, topic2, refs2, const2, ent2 = ConversationStateService.resolve_references(t2, history)
    assert refs2.get("it") == "Python", f"Expected refs['it'] == 'Python', got {refs2.get('it')}"
    assert "Python" in c2
    history.append({"role": "user", "content": t2})
    history.append({"role": "assistant", "content": "Python is dynamically typed while Java is statically typed."})

    # Turn 3: 'Which is easier?'
    t3 = "Which is easier?"
    c3, topic3, refs3, const3, ent3 = ConversationStateService.resolve_references(t3, history)
    assert "Python" in c3 or "Java" in c3
    assert TurnType.COMPARISON == ConversationStateService.classify_turn(t3, history, topic2)
    history.append({"role": "user", "content": t3})
    history.append({"role": "assistant", "content": "Python has simpler syntax and is generally easier for beginners."})

    # Turn 4: 'What about jobs?'
    t4 = "What about jobs?"
    c4, topic4, refs4, const4, ent4 = ConversationStateService.resolve_references(t4, history)
    assert "job" in c4.lower()
    assert "Python" in c4 or "Java" in c4

    # Turn 5: 'In India?'
    t5 = "In India?"
    c5, topic5, refs5, const5, ent5 = ConversationStateService.resolve_references(t5, history)
    assert "India" in c5
    assert const5.get("location") == "India"


@pytest.mark.asyncio
async def test_research_hardware_constraint_accumulation():
    """
    Verifies Requirement 19:
    Progressive constraint accumulation for AI model research:
    Turn 1: 'What are the latest open-source AI coding models?'
    Turn 2: 'Which ones run locally?'
    Turn 3: 'I have 16GB RAM.'
    Turn 4: 'Compare the best two.'
    """
    history = []

    # Turn 1
    t1 = "What are the latest open-source AI coding models?"
    c1, topic1, refs1, const1, ent1 = ConversationStateService.resolve_references(t1, history)
    assert const1.get("license") == "open_source"
    assert const1.get("temporal") == "latest"

    history.append({"role": "user", "content": t1})
    history.append({"role": "assistant", "content": "Top open-source coding models include Qwen 2.5 Coder and DeepSeek Coder."})

    # Turn 2: 'Which ones run locally?'
    t2 = "Which ones run locally?"
    c2, topic2, refs2, const2, ent2 = ConversationStateService.resolve_references(t2, history)
    assert const2.get("execution_mode") == "local"
    assert const2.get("license") == "open_source"

    history.append({"role": "user", "content": t2})
    history.append({"role": "assistant", "content": "Both Qwen 2.5 Coder 7B and DeepSeek Coder 6.7B run locally via Ollama."})

    # Turn 3: 'I have 16GB RAM.'
    t3 = "I have 16GB RAM."
    c3, topic3, refs3, const3, ent3 = ConversationStateService.resolve_references(t3, history)
    assert const3.get("memory_limit") == "16GB"
    assert const3.get("execution_mode") == "local"

    history.append({"role": "user", "content": t3})
    history.append({"role": "assistant", "content": "With 16GB RAM, 7B quantized (Q4_K_M) models fit comfortably with room for context."})

    # Turn 4: 'Compare the best two.'
    t4 = "Compare the best two."
    c4, topic4, refs4, const4, ent4 = ConversationStateService.resolve_references(t4, history)
    turn_type = ConversationStateService.classify_turn(t4, history, topic3)
    assert turn_type == TurnType.COMPARISON


@pytest.mark.asyncio
async def test_finance_domain_reconstruction():
    """
    Verifies Requirement 20:
    Multi-turn financial query reconstruction:
    Turn 1: 'Which stock was the top mover yesterday?'
    Turn 2: 'In India.'
    Turn 3: 'Small cap.'
    Turn 4: 'Give details.'
    """
    history = []

    # Turn 1
    t1 = "Which stock was the top mover yesterday?"
    a1 = await QueryIntelligenceService.analyze_query(t1, history)
    assert a1.resolved_task.domain == "finance"
    assert a1.extracted_constraints.get("temporal") == "yesterday"

    history.append({"role": "user", "content": t1})
    history.append({"role": "assistant", "content": "Here are top gainers across global exchanges."})

    # Turn 2: 'In India.'
    t2 = "In India."
    a2 = await QueryIntelligenceService.analyze_query(t2, history)
    assert a2.extracted_constraints.get("location") == "India"
    assert a2.extracted_constraints.get("temporal") == "yesterday"

    history.append({"role": "user", "content": t2})
    history.append({"role": "assistant", "content": "Top Indian market movers yesterday included NSE gainers."})

    # Turn 3: 'Small cap.'
    t3 = "Small cap."
    a3 = await QueryIntelligenceService.analyze_query(t3, history)
    assert a3.extracted_constraints.get("market_cap") == "small_cap"
    assert a3.extracted_constraints.get("location") == "India"
    assert a3.extracted_constraints.get("temporal") == "yesterday"


@pytest.mark.asyncio
async def test_current_information_web_requirement():
    """
    Verifies Requirement 21:
    'Which AI model was launched recently?' accurately detects web search / current info requirement.
    """
    analysis = await QueryIntelligenceService.analyze_query(
        user_message="Which AI model was launched recently?"
    )
    assert analysis.resolved_task.plan.requires_web_search is True
    assert analysis.resolved_task.intent in ["current_information", "web_search"]


@pytest.mark.asyncio
async def test_state_persistence_across_turns(test_db: AsyncSession):
    """
    Verifies Requirement 24:
    ConversationState is reliably stored and retrieved in PostgreSQL across sequential turns.
    """
    conv = Conversation(workspace_slug="general", title="Persistence Verification", model_name="llama3.2:3b")
    test_db.add(conv)
    await test_db.commit()
    await test_db.refresh(conv)

    # Update Turn 1
    await ConversationStateService.update_state_turn(
        db=test_db,
        conversation_id=conv.id,
        user_message="Tell me about Qwen 3.",
        turn_type=TurnType.NEW_TOPIC,
        resolved_topic="Qwen 3",
        canonical_prompt="Tell me about Qwen 3.",
        entities={"Qwen 3": {"type": "model", "mentions": 1}},
        references={"it": "Qwen 3"},
        constraints={"license": "open_source"},
        assistant_summary="Qwen 3 overview."
    )

    # Retrieve from DB to verify persistence
    state = await ConversationStateService.get_or_create_state(test_db, conv.id)
    assert state.topic == "Qwen 3"
    assert state.turn_count == 1
    assert state.references.get("it") == "Qwen 3"
    assert state.constraints.get("license") == "open_source"

    # Turn 2: Apply hardware limit
    await ConversationStateService.update_state_turn(
        db=test_db,
        conversation_id=conv.id,
        user_message="I have 16GB RAM.",
        turn_type=TurnType.FOLLOW_UP,
        resolved_topic="Qwen 3",
        canonical_prompt="Qwen 3 with 16GB RAM.",
        entities={},
        references={},
        constraints={"memory_limit": "16GB"},
        assistant_summary="RAM compatibility check."
    )

    state2 = await ConversationStateService.get_or_create_state(test_db, conv.id)
    assert state2.turn_count == 2
    assert state2.constraints.get("license") == "open_source"
    assert state2.constraints.get("memory_limit") == "16GB"
