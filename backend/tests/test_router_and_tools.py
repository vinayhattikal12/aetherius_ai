import pytest
from httpx import AsyncClient
from backend.app.services.tool_service import ToolExecutionEngine, ToolExecutionRequest


def test_tool_safe_math_calculation():
    req = ToolExecutionRequest(
        tool_name="calculate_expression",
        arguments={"expression": "(50 * 4) + (2 ** 6) - 14"}
    )
    res = ToolExecutionEngine.execute_tool(req)
    assert res.status == "success"
    assert res.result["result"] == 250


def test_tool_json_formatter():
    req = ToolExecutionRequest(
        tool_name="format_json",
        arguments={"raw_json": '{"name":"Aetherius","phase":3,"active":true}', "indent": 2}
    )
    res = ToolExecutionEngine.execute_tool(req)
    assert res.status == "success"
    assert res.result["valid"] is True
    assert "Aetherius" in res.result["formatted_json"]


def test_tool_hash_calculator():
    req = ToolExecutionRequest(
        tool_name="calculate_hash",
        arguments={"data": "Aetherius AI Operating Environment", "algorithm": "sha256"}
    )
    res = ToolExecutionEngine.execute_tool(req)
    assert res.status == "success"
    assert len(res.result["hash"]) == 64


def test_tool_compound_interest():
    req = ToolExecutionRequest(
        tool_name="finance_compound_interest",
        arguments={"principal": 10000, "annual_rate_percent": 8, "years": 5, "compounding_frequency": 12}
    )
    res = ToolExecutionEngine.execute_tool(req)
    assert res.status == "success"
    assert res.result["final_balance"] > 14000
    assert res.result["total_interest_earned"] > 4000


@pytest.mark.integration
@pytest.mark.asyncio
async def test_router_evaluation_endpoint(async_client: AsyncClient):
    # Test coding intent routing with local privacy mode
    req_payload = {
        "prompt": "Write a Python async generator function to stream binary chunks from PostgreSQL.",
        "workspace_slug": "developer",
        "privacy_mode": "LOCAL_ONLY"
    }
    res = await async_client.post("/api/v1/router/evaluate", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["execution_mode"] == "local"
    assert data["privacy_compliant"] is True
    assert data["detected_intent"] == "code_generation"
    assert len(data["selected_model_id"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tools_listing_and_execution_endpoints(async_client: AsyncClient):
    # 1. List tools
    list_res = await async_client.get("/api/v1/tools/?workspace_slug=developer")
    assert list_res.status_code == 200
    tools = list_res.json()
    assert len(tools) >= 4

    # 2. Execute tool via API
    exec_payload = {
        "tool_name": "calculate_expression",
        "arguments": {"expression": "1024 * 8"},
        "workspace_slug": "developer"
    }
    exec_res = await async_client.post("/api/v1/tools/execute", json=exec_payload)
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["status"] == "success"
    assert exec_data["result"]["result"] == 8192
