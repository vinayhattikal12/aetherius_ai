import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.services.router_service import ModelRouter
from backend.app.services.providers.ollama_provider import OllamaProvider
from backend.app.schemas.router import RouterEvaluationRequest
from backend.app.models.model_registry import ModelRegistry
from backend.app.models.system_profile import SystemProfile
from backend.app.models.settings import UserSettings


@pytest.mark.asyncio
async def test_model_router_caching():
    """Verify ModelRouter caches DB inputs across repeat requests for sub-millisecond routing."""
    ModelRouter.invalidate_cache()
    
    mock_db = AsyncMock()
    
    # Mock settings, profile, and registry models
    mock_settings_res = MagicMock()
    mock_settings_res.scalars.return_value.first.return_value = UserSettings(user_id="u1", privacy_mode="HYBRID")
    
    mock_sys_res = MagicMock()
    mock_sys_res.scalars.return_value.first.return_value = SystemProfile(compute_tier="High")
    
    mock_models_res = MagicMock()
    mock_models_res.scalars.return_value.all.return_value = [
        ModelRegistry(name="llama3.2:3b", display_name="Llama 3.2 3B", provider="ollama", model_family="llama", is_installed=True, is_active=True)
    ]
    
    mock_db.execute.side_effect = [mock_settings_res, mock_sys_res, mock_models_res]
    
    req = RouterEvaluationRequest(prompt="Hello", workspace_slug="general")
    
    # Call 1: Populates cache (3 db queries)
    res1 = await ModelRouter.evaluate_routing(mock_db, req)
    assert res1.selected_model_id is not None
    assert mock_db.execute.call_count == 3
    
    # Call 2: Must hit cache with 0 additional DB queries
    res2 = await ModelRouter.evaluate_routing(mock_db, req)
    assert res2.selected_model_id == res1.selected_model_id
    assert mock_db.execute.call_count == 3
    
    # Invalidate cache -> next call hits DB
    ModelRouter.invalidate_cache()
    mock_db.execute.side_effect = [mock_settings_res, mock_sys_res, mock_models_res]
    await ModelRouter.evaluate_routing(mock_db, req)
    assert mock_db.execute.call_count == 6


@pytest.mark.asyncio
async def test_ollama_no_per_request_eviction_when_memory_sufficient():
    """Verify OllamaProvider skips /api/ps eviction when system free RAM >= 2.0GB."""
    provider = OllamaProvider()
    
    with patch("psutil.virtual_memory") as mock_mem, patch("httpx.AsyncClient.get") as mock_get:
        # Mock 8 GB free RAM
        mock_mem.return_value.available = 8 * (1024 ** 3)
        
        await provider.evict_idle_models("llama3.2:3b")
        
        # /api/ps should not even be called when memory is abundant
        mock_get.assert_not_called()
        assert provider._current_active_model == "llama3.2:3b"
