import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["app"] == "Aetherius AI"


@pytest.mark.asyncio
async def test_system_detect_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/system/detect")
    assert response.status_code == 200
    data = response.json()
    assert "cpu" in data
    assert "ram" in data
    assert "compute_tier" in data
    assert data["ram_gb"] > 0
    assert len(data["accelerators"]) >= 1


@pytest.mark.asyncio
async def test_save_hardware_profile_endpoint(async_client: AsyncClient):
    response = await async_client.post("/api/v1/system/save-profile")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"
    assert "profile" in data
    assert "id" in data


@pytest.mark.asyncio
async def test_models_listing_with_compatibility(async_client: AsyncClient):
    response = await async_client.get("/api/v1/models/?evaluate_compatibility=true")
    assert response.status_code == 200
    models = response.json()
    assert len(models) >= 1
    
    first = models[0]
    assert "name" in first
    assert "display_name" in first
    assert "compatibility" in first
    assert first["compatibility"]["compatibility"] in ["Compatible", "Maybe Compatible", "Not Recommended"]


@pytest.mark.asyncio
async def test_model_packages_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/models/packages")
    assert response.status_code == 200
    packages = response.json()
    assert len(packages) >= 1
    assert any(p["slug"] == "developer-package" for p in packages)


@pytest.mark.asyncio
async def test_evaluate_compatibility_endpoint(async_client: AsyncClient):
    payload = {
        "name": "qwen2.5-coder:7b",
        "display_name": "Qwen 2.5 Coder 7B",
        "provider": "ollama",
        "model_family": "qwen",
        "parameters_b": 7.6,
        "quantization": "Q4_K_M",
        "context_size": 16384,
        "is_local": True
    }
    response = await async_client.post("/api/v1/models/evaluate-compatibility", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "qwen2.5-coder:7b"
    assert data["compatibility"] in ["Compatible", "Maybe Compatible", "Not Recommended"]
    assert "score" in data
    assert data["estimated_memory_gb"] > 0


@pytest.mark.asyncio
async def test_workspaces_endpoints(async_client: AsyncClient):
    # 1. List workspaces
    response = await async_client.get("/api/v1/workspaces/")
    assert response.status_code == 200
    workspaces = response.json()
    assert len(workspaces) >= 5
    
    slugs = [w["slug"] for w in workspaces]
    assert "general" in slugs
    assert "developer" in slugs
    assert "student" in slugs

    # 2. Get specific workspace
    ws_resp = await async_client.get("/api/v1/workspaces/developer")
    assert ws_resp.status_code == 200
    ws_data = ws_resp.json()
    assert ws_data["slug"] == "developer"
    assert "editor" in ws_data["ui_capabilities"]


@pytest.mark.asyncio
async def test_settings_endpoints(async_client: AsyncClient):
    # 1. Get settings
    get_res = await async_client.get("/api/v1/settings/")
    assert get_res.status_code == 200
    settings = get_res.json()
    assert "theme" in settings
    assert "privacy_mode" in settings

    # 2. Patch settings
    patch_res = await async_client.patch("/api/v1/settings/", json={
        "theme": "dark",
        "privacy_mode": "LOCAL_ONLY",
        "onboarding_completed": True
    })
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["theme"] == "dark"
    assert updated["privacy_mode"] == "LOCAL_ONLY"
    assert updated["onboarding_completed"] is True


@pytest.mark.asyncio
async def test_auth_flow(async_client: AsyncClient):
    email = "tester@aetherius.ai"
    password = "SuperSecretPassword123!"

    # 1. Register
    reg_res = await async_client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Test Engineer",
        "role": "developer"
    })
    if reg_res.status_code != 400: # If already registered in previous run
        assert reg_res.status_code == 200
        user_data = reg_res.json()
        assert user_data["email"] == email

    # 2. Login
    login_res = await async_client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["email"] == email
