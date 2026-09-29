import pytest
from backend.app.services.embedding_service import EmbeddingService


@pytest.mark.asyncio
async def test_embedding_generation_and_cosine_similarity():
    text1 = "FastAPI backend with PostgreSQL database"
    text2 = "FastAPI backend and PostgreSQL storage"
    text3 = "Tropical rainforest wildlife and flora"

    vec1 = await EmbeddingService.embed_text(text1)
    vec2 = await EmbeddingService.embed_text(text2)
    vec3 = await EmbeddingService.embed_text(text3)

    assert len(vec1) == 384
    assert len(vec2) == 384

    # Related texts should have significantly higher similarity than unrelated text
    sim_related = EmbeddingService.cosine_similarity(vec1, vec2)
    sim_unrelated = EmbeddingService.cosine_similarity(vec1, vec3)

    assert sim_related > sim_unrelated
    assert sim_related > 0.0
