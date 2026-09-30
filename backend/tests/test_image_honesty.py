import pytest
from unittest.mock import patch, AsyncMock
from backend.app.services.image_gen_service import ImageGenService, ImageGenerationRequest
from backend.app.core.config import settings


@pytest.mark.asyncio
async def test_image_gen_local_only_mode_blocked():
    settings.LOCAL_ONLY = True
    try:
        req = ImageGenerationRequest(prompt="A beautiful sunset")
        with pytest.raises(RuntimeError, match="disabled in LOCAL_ONLY mode"):
            await ImageGenService.generate_image(req)
    finally:
        settings.LOCAL_ONLY = False


@pytest.mark.asyncio
async def test_image_gen_provider_failure_raises_honestly():
    settings.LOCAL_ONLY = False
    req = ImageGenerationRequest(prompt="A futuristic city")
    
    # Mock httpx failure
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = Exception("Connection refused to diffusion server")
        with pytest.raises(RuntimeError, match="Image generation failed"):
            await ImageGenService.generate_image(req)


def test_prompt_enhancement_clean():
    clean1 = ImageGenService._enhance_prompt("generate an image of a red sports car", "photorealistic")
    assert "generate an image of" not in clean1.lower()
    assert "red sports car" in clean1.lower()
    assert "photograph" in clean1.lower()
