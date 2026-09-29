import pytest
from typing import List
from backend.app.schemas.web_search import WebSearchResultItem
from backend.app.services.evidence.web_search_providers import (
    DuckDuckGoSearchProvider,
    MultiProviderSearchOrchestrator
)
from backend.app.services.evidence.evidence_engine import SourceEvidenceEngine
from backend.app.services.evidence.answer_validator import AnswerValidationEngine
from backend.app.services.web_search_service import WebSearchService


@pytest.mark.asyncio
async def test_source_evidence_domain_authority_and_ranking():
    """Validates domain authority scoring, freshness detection, and composite evidence ranking."""
    # 1. Domain Authority
    assert SourceEvidenceEngine.calculate_domain_authority("https://docs.python.org/3/library/asyncio.html") == 0.95
    assert SourceEvidenceEngine.calculate_domain_authority("https://github.com/fastapi/fastapi") == 0.95
    assert SourceEvidenceEngine.calculate_domain_authority("https://www.postgresql.org/docs/current/index.html") == 0.95
    assert SourceEvidenceEngine.calculate_domain_authority("https://stackoverflow.com/questions/12345") == 0.80
    assert SourceEvidenceEngine.calculate_domain_authority("https://random-scraped-blog-123.com/article") == 0.60

    # 2. Freshness Score
    fresh_2026 = SourceEvidenceEngine.calculate_freshness_score("Released in February 2026 update", "https://example.com/2026-news")
    older_2024 = SourceEvidenceEngine.calculate_freshness_score("Published in 2024 archive", "https://example.com/2024")
    assert fresh_2026 > older_2024

    # 3. Content Density
    dense_code = SourceEvidenceEngine.calculate_content_density("def search(query: str) -> List[int]: return [1, 2, 3] # 99.5% accuracy")
    empty_snip = SourceEvidenceEngine.calculate_content_density("click here")
    assert dense_code > empty_snip

    # 4. Composite Ranking
    query = "FastAPI async database connection pooling"
    sources = [
        WebSearchResultItem(
            title="Random Forum Post",
            url="https://unknown-forum.net/thread/99",
            snippet="Someone asked about database stuff.",
            source_domain="unknown-forum.net"
        ),
        WebSearchResultItem(
            title="FastAPI Official Documentation on Async SQL Databases",
            url="https://fastapi.tiangolo.com/tutorial/sql-databases/",
            snippet="FastAPI supports async database connections using SQLAlchemy 2.0 and asyncpg connection pooling.",
            source_domain="fastapi.tiangolo.com"
        ),
    ]

    ranked = await SourceEvidenceEngine.score_and_rank_sources(query, sources)
    assert len(ranked) == 2
    # Official docs must rank #1
    assert ranked[0][0].source_domain == "fastapi.tiangolo.com"
    assert ranked[0][1] > ranked[1][1]


@pytest.mark.asyncio
async def test_answer_validation_and_grounding_audit():
    """Validates pre-generation answer validation, constraint verification, and anti-hallucination guardrails."""
    # 1. Constraint Validation - Table Format
    valid_table_resp = (
        "Here is the comparison table:\n\n"
        "| Feature | SQLite | PostgreSQL |\n"
        "|---|---|---|\n"
        "| Concurrency | File Lock | Multi-Version Concurrency Control (MVCC) |\n"
        "| Network | Local Embedded | Client-Server |\n"
    )
    ok, issues = AnswerValidationEngine.validate_constraints(valid_table_resp, {"format": "table"})
    assert ok is True
    assert len(issues) == 0

    invalid_table_resp = "SQLite is embedded and PostgreSQL is client-server."
    ok_bad, issues_bad = AnswerValidationEngine.validate_constraints(invalid_table_resp, {"format": "table"})
    assert ok_bad is False
    assert any("Markdown table" in i for i in issues_bad)

    # 2. Citation Footnote Verification
    cited_text = "PostgreSQL supports pgvector [1] and full-text search [2]."
    cit_ok, cit_issues = AnswerValidationEngine.validate_citations(cited_text, num_sources=2)
    assert cit_ok is True

    bad_cited_text = "PostgreSQL supports pgvector [1] and distributed clustering [5]."
    bad_cit_ok, bad_cit_issues = AnswerValidationEngine.validate_citations(bad_cited_text, num_sources=2)
    assert bad_cit_ok is False
    assert any("[5]" in i for i in bad_cit_issues)

    # 3. Grounding Score Calculation
    evidence_chunks = [
        "PostgreSQL pgvector extension enables efficient vector similarity search using HNSW and IVFFlat indexes."
    ]
    grounded_answer = "PostgreSQL pgvector supports vector similarity search with HNSW indexes."
    hallucinated_answer = "Quantum supercomputing uses superconducting qubits cooled to absolute zero."

    score_grounded = AnswerValidationEngine.calculate_grounding_score(grounded_answer, evidence_chunks)
    score_hallucinated = AnswerValidationEngine.calculate_grounding_score(hallucinated_answer, evidence_chunks)

    assert score_grounded > score_hallucinated


@pytest.mark.asyncio
async def test_web_search_service_retrieval_and_evidence():
    """Validates end-to-end multi-provider search, ranking, and citation creation."""
    res = await WebSearchService.search(
        query="Python asyncio high performance best practices",
        max_results=3,
        deep_scrape=False
    )
    assert res is not None
    assert len(res.results) > 0

    citations = WebSearchService.to_citations(res)
    assert len(citations) == len(res.results)
    assert all(c.source_type == "web" for c in citations)
    assert all(len(c.title) > 0 for c in citations)
