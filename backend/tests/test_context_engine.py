import pytest
from backend.app.services.context_engine import ContextEngine
from backend.app.models.memory import Memory


def test_token_estimation():
    text = "Hello world! This is a test string for token estimation in Aetherius."
    tokens = ContextEngine.estimate_tokens(text)
    assert tokens > 0
    assert tokens < len(text)


def test_assemble_context_with_budget():
    memories = [
        Memory(
            workspace_slug="developer",
            memory_type="preference",
            content="User prefers FastAPI and PostgreSQL.",
            confidence_score=1.0,
            importance_weight=3.0,
            embedding_vector=[],
            memory_metadata={}
        )
    ]

    history = [
        {"role": "user", "content": "How do I setup database migrations?"},
        {"role": "assistant", "content": "You can use Alembic with PostgreSQL."},
        {"role": "user", "content": "Tell me more about async sessions."}
    ]

    web_results = [
        {"title": "SQLAlchemy Async", "url": "https://sqlalchemy.org", "snippet": "AsyncSession enables async DB queries."}
    ]

    assembled = ContextEngine.assemble_context(
        model_context_limit=4096,
        max_output_tokens=1024,
        system_instruction="You are a senior database architect.",
        workspace_name="Developer",
        workspace_instructions="Always write modular code.",
        memories=memories,
        web_results=web_results,
        chat_history=history,
        current_user_message="Provide an example of an async session context manager."
    )

    assert "FastAPI and PostgreSQL" in assembled["augmented_prompt"]
    assert "Always write modular code" in assembled["system_prompt"]
    assert "SQLAlchemy Async" in assembled["augmented_prompt"]
    assert len(assembled["fitted_history"]) >= 1
    assert assembled["stats"]["total_estimated_tokens"] < 4096
