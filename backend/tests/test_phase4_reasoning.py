import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.schemas.agent import AgentTaskCreate
from backend.app.schemas.tool import ToolExecutionRequest
from backend.app.services.tool_service import ToolExecutionEngine, SandboxedCodeExecutor
from backend.app.services.agent_orchestrator import AgentOrchestrator
from backend.app.models.agent import AgentTask, AgentTaskStep


from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_sandboxed_python_and_security_guards():
    """Validates pure Python execution and verifies security guardrails block malicious constructs."""
    settings.ENABLE_PYTHON_SANDBOX = True
    try:
        # 1. Safe Python execution
        code_safe = "result = sum([x * 2 for x in range(1, 6)])"
        ok, res, err = SandboxedCodeExecutor.execute_safe_python(code_safe)
        assert ok is True
        assert res == 30
        assert err is None

        # 2. Blocked import statement
        code_import = "import os\nresult = os.listdir('.')"
        ok_imp, res_imp, err_imp = SandboxedCodeExecutor.execute_safe_python(code_import)
        assert ok_imp is False
        assert "Security Violation" in err_imp or "forbidden" in err_imp.lower()

        # 3. Blocked file open
        code_open = "f = open('test.txt', 'w')"
        ok_open, _, err_open = SandboxedCodeExecutor.execute_safe_python(code_open)
        assert ok_open is False
        assert "Security Violation" in err_open or "forbidden" in err_open.lower()

        # 4. Blocked dunder escape
        code_dunder = "result = ().__class__.__bases__"
        ok_dunder, _, err_dunder = SandboxedCodeExecutor.execute_safe_python(code_dunder)
        assert ok_dunder is False
        assert "Security Violation" in err_dunder or "forbidden" in err_dunder.lower()
    finally:
        settings.ENABLE_PYTHON_SANDBOX = False


@pytest.mark.asyncio
async def test_safe_math_ast_evaluator():
    """Validates mathematical expression parsing and execution without eval()."""
    t_res = ToolExecutionEngine.execute_tool(
        ToolExecutionRequest(
            tool_name="calculate_expression",
            arguments={"expression": "(50 * 4) + (2 ** 6) - sqrt(144)"}
        )
    )
    assert t_res.status == "success"
    assert t_res.result["result"] == 252.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_task_state_machine_and_react_loop(test_db: AsyncSession):
    """Validates PostgreSQL-backed task state machine transitions across Plan -> Act -> Observe -> Reflect -> Synthesize."""
    # 1. Create and execute Autonomous Coder Task
    task = await AgentOrchestrator.create_task(
        db=test_db,
        data=AgentTaskCreate(
            agent_slug="coder-agent",
            workspace_slug="developer",
            title="Algorithm Optimization Task",
            goal_prompt="Optimize memory buffer calculation for 1024 * 64 units",
            use_rag=False,
            use_web_search=False
        )
    )

    assert task.status == "completed"
    assert task.result_output is not None
    assert len(task.result_output) > 50
    assert task.completed_at is not None

    # Verify all ReAct steps logged in PostgreSQL
    steps_res = await test_db.execute(
        select(AgentTaskStep).where(AgentTaskStep.task_id == task.id).order_by(AgentTaskStep.step_index.asc())
    )
    steps = steps_res.scalars().all()
    assert len(steps) >= 4
    step_types = [s.step_type for s in steps]
    assert "plan" in step_types
    assert "tool_call" in step_types
    assert "observation" in step_types
    assert "reflection" in step_types
    assert "final_output" in step_types
