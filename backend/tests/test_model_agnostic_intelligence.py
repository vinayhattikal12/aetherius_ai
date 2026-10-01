import pytest
import os
from typing import Dict, Any, List
from backend.app.schemas.system import HardwareProfile, CpuInfo, RamInfo, GpuInfo, StorageInfo
from backend.app.schemas.model_registry import ModelBase, CompatibilityResult, ModelDescriptor, ModelCapabilities
from backend.app.services.compatibility_engine import ModelCompatibilityEngine
from backend.app.services.query_intelligence_service import QueryIntelligenceService
from backend.app.services.context_engine import ContextEngine
from backend.app.services.evidence.answer_validator import AnswerValidationEngine
from backend.app.services.conversation_state_service import ConversationStateService, TurnType
from backend.app.services.artifact_service import ArtifactService


# =========================================================================
# Category A: Basic Knowledge & Direct Model Reasoning
# =========================================================================
@pytest.mark.asyncio
async def test_category_a_basic_knowledge_planning():
    analysis = await QueryIntelligenceService.analyze_query("What is recursion in computer science?")
    assert analysis.resolved_task is not None
    assert analysis.resolved_task.plan.requires_direct_model is True
    assert analysis.resolved_task.plan.requires_web_search is False
    assert analysis.resolved_task.domain == "programming"


# =========================================================================
# Category B: Follow-up Questions & Anaphora Resolution
# =========================================================================
@pytest.mark.asyncio
async def test_category_b_follow_up_anaphora_resolution():
    history = [
        {"role": "user", "content": "Tell me about Qwen3."},
        {"role": "assistant", "content": "Qwen3 is a family of large language models developed by Alibaba Cloud."}
    ]
    analysis = await QueryIntelligenceService.analyze_query(
        user_message="What sizes are available?",
        conversation_history=history
    )
    assert analysis.resolved_task is not None
    # Must resolve follow-up reference to active entity (Qwen3)
    assert "qwen" in analysis.canonical_prompt.lower() or "qwen" in (analysis.base_topic or "").lower() or analysis.turn_type in [TurnType.CONTINUATION, TurnType.FOLLOW_UP, "FOLLOW_UP"]


# =========================================================================
# Category C: Entity Resolution (Distinguishing companies, models, tech)
# =========================================================================
@pytest.mark.asyncio
async def test_category_c_entity_resolution():
    # 1. Distinguish company
    analysis_org = await QueryIntelligenceService.analyze_query("Tell me about ERBrains It Solutions")
    assert any("erbrains" in e.lower() for e in analysis_org.extracted_entities) or "erbrains" in analysis_org.canonical_prompt.lower()

    # 2. Distinguish technology/database
    analysis_tech = await QueryIntelligenceService.analyze_query("Explain PostgreSQL database architecture")
    assert any("postgresql" in e.lower() for e in analysis_tech.extracted_entities) or "postgresql" in analysis_tech.canonical_prompt.lower()


# =========================================================================
# Category D: Context Retention & User Constraint Accumulation
# =========================================================================
def test_category_d_constraint_accumulation():
    t1 = "Explain sorting algorithms in Python."
    c1 = ConversationStateService.extract_constraints(t1)
    assert c1.get("language") == "python"

    t2 = "Give me the response in a markdown table with 3 columns."
    c2 = ConversationStateService.extract_constraints(t2)
    assert c2.get("format") == "table"


# =========================================================================
# Category E & F: Web Grounding, Search Planning & Claim Verification
# =========================================================================
@pytest.mark.asyncio
async def test_category_e_f_web_grounding_and_claims():
    # 1. Search trigger detection for temporal / news queries
    analysis = await QueryIntelligenceService.analyze_query("What is the latest release and pricing for NVIDIA RTX 5090 today?")
    assert analysis.resolved_task.plan.requires_web_search is True

    # 2. Claim-level evaluation
    evidence = ["NVIDIA announced RTX 5090 graphics card with 32GB GDDR7 VRAM in January 2025."]
    claims = ["RTX 5090 features 32GB GDDR7 VRAM.", "RTX 5090 has 128GB HBM3 memory released in 2019."]
    
    evals, issues = AnswerValidationEngine.evaluate_claims(claims, evidence)
    assert len(evals) == 2
    assert evals[0].verdict == "SUPPORTED"
    assert evals[1].verdict == "UNSUPPORTED"


# =========================================================================
# Category G: Private Document RAG Prioritization
# =========================================================================
@pytest.mark.asyncio
async def test_category_g_document_rag_planning():
    analysis = await QueryIntelligenceService.analyze_query("What does our internal architecture spec say about data storage?")
    assert analysis.resolved_task.plan.requires_rag is True


# =========================================================================
# Category H: Coding & Markdown Validation
# =========================================================================
def test_category_h_coding_constraint_validation():
    # Valid Python code matching constraint
    code_resp = "Here is the code:\n```python\ndef solve():\n    return 42\n```"
    report_valid = AnswerValidationEngine.validate_response(
        response_text=code_resp,
        constraints={"language": "python"}
    )
    assert report_valid.constraints_satisfied is True
    assert report_valid.is_valid is True

    # Invalid code (Rust provided instead of Python)
    bad_code = "```rust\nfn main() {}\n```"
    report_bad = AnswerValidationEngine.validate_response(
        response_text=bad_code,
        constraints={"language": "python"}
    )
    assert report_bad.constraints_satisfied is False
    assert report_bad.is_valid is False


# =========================================================================
# Category I: Multi-Step Tool Planning
# =========================================================================
@pytest.mark.asyncio
async def test_category_i_tool_planning():
    analysis = await QueryIntelligenceService.analyze_query("Calculate compound interest on $10,000 at 5% over 10 years.")
    assert "calculate_expression" in analysis.resolved_task.plan.requires_tools or analysis.resolved_task.intent in ["data_analysis", "general_question"]


# =========================================================================
# Category J: Unknown Hardware Safety & Compatibility
# =========================================================================
def test_category_j_hardware_unknown_safety():
    # 1. Unknown Hardware Profile (0 RAM / Missing specs)
    unknown_profile = HardwareProfile(
        ram_gb=0.0,
        ram=RamInfo(total_gb=0.0),
        vram_gb=0.0,
        storage_free_gb=0.0
    )
    local_model = ModelBase(
        name="qwen2.5:7b",
        display_name="Qwen 2.5 7B",
        provider="ollama",
        model_family="qwen",
        parameters_b=7.0,
        is_local=True
    )
    compat = ModelCompatibilityEngine.evaluate(unknown_profile, local_model)
    assert compat.compatibility == "UNKNOWN"
    assert "I need your hardware details before determining compatibility." in compat.reasons[0]

    # 2. Known 16GB RAM hardware profile
    known_profile = HardwareProfile(
        ram_gb=16.0,
        ram=RamInfo(total_gb=16.0, available_gb=10.0),
        vram_gb=6.0,
        storage_free_gb=80.0,
        gpu=[GpuInfo(name="NVIDIA RTX 3060", vendor="NVIDIA", vram_total_gb=6.0, cuda_supported=True)]
    )
    compat_known = ModelCompatibilityEngine.evaluate(known_profile, local_model)
    assert compat_known.compatibility in ["SUPPORTED", "POSSIBLE"]


# =========================================================================
# Category K & N: Hallucination Resistance & Internal Leakage Protection
# =========================================================================
def test_category_k_n_leakage_and_guardrails():
    leaked_resp = "Here is your answer.\n[CONVERSATION CONTEXT]: Active Topic: AI\nTurn Relation Mode: FOLLOW_UP"
    report = AnswerValidationEngine.validate_response(response_text=leaked_resp)
    assert report.is_valid is False
    assert any("diagnostic marker" in i.lower() for i in report.issues)


# =========================================================================
# Category L: Model Switching Context Preservation
# =========================================================================
def test_category_l_context_assembly_across_models():
    # Test that changing the target model context limit from 2048 to 16384 preserves the same task & system contract
    task_msg = "Create a summary of our discussion"
    history = [
        {"role": "user", "content": "We decided on a microservices architecture with PostgreSQL and Redis."},
        {"role": "assistant", "content": "Acknowledged. Microservices with PostgreSQL and Redis documented."}
    ]

    # Model A: Small local model (2048 context)
    ctx_small = ContextEngine.assemble_context(
        model_context_limit=2048,
        chat_history=history,
        current_user_message=task_msg
    )

    # Model B: Large cloud model (16384 context)
    ctx_large = ContextEngine.assemble_context(
        model_context_limit=16384,
        chat_history=history,
        current_user_message=task_msg
    )

    assert "Authoritative Operating Principles" in ctx_small["system_prompt"]
    assert "Authoritative Operating Principles" in ctx_large["system_prompt"]
    assert len(ctx_small["fitted_history"]) > 0
    assert len(ctx_large["fitted_history"]) > 0


# =========================================================================
# Category O: Long Conversation Token Budgeting
# =========================================================================
def test_category_o_token_budgeting():
    # Long chat history (50 turns)
    long_history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}: Information content about topic {i}."} for i in range(50)]
    
    ctx = ContextEngine.assemble_context(
        model_context_limit=4096,
        max_output_tokens=1024,
        chat_history=long_history,
        current_user_message="Summarize the key milestones."
    )
    
    # Must fit strictly within available budget without crashing or overflowing
    assert ctx["stats"]["total_estimated_tokens"] <= 4096
    assert ctx["stats"]["history_turns"] > 0
