import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from backend.app.services.model_installation_service import ModelInstallationManager


@pytest.mark.asyncio
async def test_install_ollama_not_running():
    """Verify that when Ollama is unreachable, install fails immediately with OLLAMA_NOT_RUNNING."""
    mgr = ModelInstallationManager()
    
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        res = await mgr.start_install(
            model_id_or_name="qwen2.5-coder:7b",
            display_name="Qwen 2.5 Coder 7B"
        )
        assert res.status in ("initializing", "downloading")
        
        # Wait for background task to complete
        await asyncio.sleep(0.1)
        
        progress = mgr.get_progress("qwen2.5-coder:7b")
        assert progress is not None
        assert progress.status == "failed"
        assert progress.error == "OLLAMA_NOT_RUNNING"
        assert "not running" in progress.status_message.lower()


@pytest.mark.asyncio
async def test_install_disk_insufficient():
    """Verify that when disk space is below 2.5 GB, install fails with INSUFFICIENT_DISK."""
    mgr = ModelInstallationManager()
    
    mock_usage = MagicMock()
    mock_usage.free = 1 * (1024 ** 3) # 1 GB free
    
    with patch("shutil.disk_usage", return_value=mock_usage):
        await mgr.start_install(
            model_id_or_name="llama3.2:3b",
            display_name="Llama 3.2 3B"
        )
        await asyncio.sleep(0.1)
        
        progress = mgr.get_progress("llama3.2:3b")
        assert progress is not None
        assert progress.status == "failed"
        assert progress.error == "INSUFFICIENT_DISK"


@pytest.mark.asyncio
async def test_install_mid_stream_error():
    """Verify that a stream error line from Ollama is caught and marks install as failed."""
    mgr = ModelInstallationManager()
    
    mock_tags = MagicMock(status_code=200)
    
    async def mock_aiter_lines():
        yield json.dumps({"status": "downloading manifest"})
        yield json.dumps({"error": "manifest for model not found"})

    mock_stream_resp = MagicMock(status_code=200)
    mock_stream_resp.aiter_lines = mock_aiter_lines
    
    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__.return_value = mock_stream_resp
    
    with patch("httpx.AsyncClient.get", return_value=mock_tags), \
         patch("httpx.AsyncClient.stream", return_value=mock_stream_cm), \
         patch("shutil.disk_usage", return_value=MagicMock(free=50 * (1024**3))):
        
        await mgr.start_install(
            model_id_or_name="invalid-model-name",
            display_name="Invalid Model"
        )
        await asyncio.sleep(0.1)
        
        progress = mgr.get_progress("invalid-model-name")
        assert progress is not None
        assert progress.status == "failed"
        assert "manifest for model not found" in progress.error


@pytest.mark.asyncio
async def test_install_cancellation():
    """Verify that cancel_install stops the installation and broadcasts status=cancelled."""
    mgr = ModelInstallationManager()
    
    mock_usage = MagicMock(free=50 * (1024 ** 3))
    with patch("shutil.disk_usage", return_value=mock_usage):
        await mgr.start_install("slow-model:14b", "Slow Model")
        
        cancelled = mgr.cancel_install("slow-model:14b")
        assert cancelled is True
        
        progress = mgr.get_progress("slow-model:14b")
        assert progress.status == "cancelled"
        assert progress.is_completed is True
