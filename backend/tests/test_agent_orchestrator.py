import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agent_definitions_listing_and_seeding(async_client: AsyncClient):
    # 1. Fetch available agents (auto-seeds defaults)
    res = await async_client.get("/api/v1/agents/")
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) >= 4

    slugs = [a["slug"] for a in agents]
    assert "coder-agent" in slugs
    assert "research-agent" in slugs
    assert "analyst-agent" in slugs
    assert "executive-agent" in slugs


@pytest.mark.asyncio
async def test_agent_coder_task_execution(async_client: AsyncClient):
    # 1. Create a Coder task
    payload = {
        "agent_slug": "coder-agent",
        "goal_prompt": "Write a Python script to format JSON config and calculate buffer size for 64 clients.",
        "workspace_slug": "developer"
    }
    task_res = await async_client.post("/api/v1/agents/tasks", json=payload)
    assert task_res.status_code == 200
    task_data = task_res.json()

    assert task_data["status"] == "completed"
    assert task_data["agent_slug"] == "coder-agent"
    assert len(task_data["steps"]) >= 4

    # Verify step sequence: plan -> tool_call -> observation -> reflection -> final_output
    step_types = [s["step_type"] for s in task_data["steps"]]
    assert "plan" in step_types
    assert "tool_call" in step_types
    assert "observation" in step_types
    assert "final_output" in step_types
    assert task_data["result_output"] is not None
    assert "Aetherius Coder" in task_data["result_output"]


@pytest.mark.asyncio
async def test_agent_analyst_task_execution(async_client: AsyncClient):
    # 1. Create a Finance task
    payload = {
        "agent_slug": "analyst-agent",
        "goal_prompt": "Calculate 10-year compound interest growth for an initial investment of 50000 at 8.5% annual rate.",
        "workspace_slug": "finance"
    }
    task_res = await async_client.post("/api/v1/agents/tasks", json=payload)
    assert task_res.status_code == 200
    task_data = task_res.json()

    assert task_data["status"] == "completed"
    assert task_data["agent_slug"] == "analyst-agent"
    assert len(task_data["steps"]) >= 4

    # Fetch task by ID to verify persistence
    get_res = await async_client.get(f"/api/v1/agents/tasks/{task_data['id']}")
    assert get_res.status_code == 200
    fetched_data = get_res.json()
    assert fetched_data["id"] == task_data["id"]
    assert fetched_data["status"] == "completed"
