import pytest
import pytest_asyncio
from backend.app.services.conversation_state_service import ConversationStateService, TurnType
from backend.app.services.query_intelligence_service import QueryIntelligenceService
from backend.app.services.context_engine import ContextEngine
from backend.app.services.web_search_service import WebSearchService
from backend.app.services.evidence.answer_validator import AnswerValidationEngine
from backend.app.models.memory import Memory


@pytest.mark.asyncio
async def test_entity_detection_and_typing():
    # 1. Company / Organization query
    query_company = "Tell me about ERBrains company"
    entities = ConversationStateService.extract_entities(query_company)
    assert "ERBrains" in entities
    assert entities["ERBrains"]["type"] == "organization"

    analysis = await QueryIntelligenceService.analyze_query(query_company)
    assert "entity_overview" in analysis.composite_intents
    assert analysis.resolved_task.plan.requires_web_search is True

    # 2. Standard CS Concept query (No search, direct model)
    query_concept = "What is a loop in Java?"
    entities_concept = ConversationStateService.extract_entities(query_concept)
    assert "Java" in entities_concept
    assert entities_concept["Java"]["type"] == "technology"

    analysis_concept = await QueryIntelligenceService.analyze_query(query_concept)
    assert analysis_concept.resolved_task.plan.requires_web_search is False
    assert analysis_concept.primary_intent in ["definition", "explanation"]


@pytest.mark.asyncio
async def test_multi_turn_entity_reference_resolution():
    history = [
        {"role": "user", "content": "Tell me about ERBrains company"},
        {"role": "assistant", "content": "ERBrains IT Solutions is an enterprise digital transformation company."}
    ]

    query_followup = "What services do they offer?"
    canonical, base_topic, references, constraints, resolved_entities = ConversationStateService.resolve_references(
        query=query_followup,
        history=history
    )

    assert "ERBrains" in base_topic or "ERBrains" in references.get("them", "") or "ERBrains" in canonical
    assert references.get("it") == "ERBrains" or references.get("them") == "ERBrains" or "ERBrains" in canonical


@pytest.mark.asyncio
async def test_memory_isolation_in_context_engine():
    dummy_memory = Memory(
        workspace_slug="general",
        memory_type="fact",
        content="Vinay is a Lead Architect at ERBrains."
    )

    assembled = ContextEngine.assemble_context(
        workspace_name="General",
        memories=[dummy_memory],
        current_user_message="Tell me about ERBrains company"
    )

    sys_prompt = assembled["system_prompt"]
    # Check that system prompt explicitly contains isolation directives
    assert "USER PROFILE MEMORY ISOLATION" in sys_prompt
    assert "STRICT FACTUAL GROUNDING & ZERO HALLUCINATION" in sys_prompt
    assert "[USER PROFILE & PERSONAL MEMORY" in sys_prompt


@pytest.mark.asyncio
async def test_web_search_clean_fallback():
    # If search returns no results, results list must be empty (no fake search.aetherius.ai fallback)
    response = await WebSearchService.search("completely_non_existent_fake_query_1234567890", max_results=3)
    for res in response.results:
        assert "search.aetherius.ai" not in res.url


def test_answer_validator_anti_leakage():
    # 1. Clean response
    clean_text = "ERBrains IT Solutions provides enterprise ERP consulting and technology solutions."
    report_clean = AnswerValidationEngine.validate_response(clean_text)
    assert report_clean.is_valid is True

    # 2. Leaked internal header
    bad_text = "Active Conversation Topic: ERBrains\nResponse:\nERBrains provides solutions."
    report_bad = AnswerValidationEngine.validate_response(bad_text)
    assert report_bad.is_valid is False
    assert any("diagnostic marker" in issue for issue in report_bad.issues)

    # 3. Phantom citations without external sources
    phantom_text = "ERBrains was founded in 2018 [1] and has major clients [2]."
    report_phantom = AnswerValidationEngine.validate_response(phantom_text, available_sources=[])
    assert report_phantom.is_valid is False
    assert any("citation footnotes" in issue for issue in report_phantom.issues)
