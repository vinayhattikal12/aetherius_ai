from urllib.parse import urlparse
import asyncio
from typing import List, Dict, Any, Optional
from backend.app.schemas.web_search import WebSearchResultItem, WebSearchResponse
from backend.app.schemas.chat import SourceCitation
from backend.app.services.evidence.web_search_providers import MultiProviderSearchOrchestrator
from backend.app.services.evidence.evidence_engine import SourceEvidenceEngine
from backend.app.core.logging import logger


class WebSearchService:
    """
    Frontier-grade Multi-Provider Web Intelligence & Evidence Retrieval Service.
    Integrates:
    - Tiered failover search across Live Currency, Weather, Finance, Sports, DDG, Wikipedia, and Google News
    - Domain authority and publication freshness ranking
    - Parallel deep reading and dense fact extraction
    """

    _orchestrator = MultiProviderSearchOrchestrator()

    @classmethod
    async def scrape_page_content(cls, url: str, timeout: float = 3.5) -> Optional[str]:
        """Deep reader delegate using SourceEvidenceEngine."""
        return await SourceEvidenceEngine.deep_scrape_url(url, timeout=timeout)

    @classmethod
    async def search(
        cls,
        query: str,
        max_results: int = 5,
        deep_scrape: bool = True
    ) -> WebSearchResponse:
        """
        Executes multi-provider search, ranks candidate sources by evidence score,
        and deep scrapes the highest-authority pages in parallel.
        """
        clean_query = query.strip()
        raw_results = await cls._orchestrator.execute_search(clean_query, max_results=max_results + 2)

        if not raw_results:
            return WebSearchResponse(
                query=query,
                results=[],
                summary=f"No web sources found for '{query}'"
            )

        # 1. Score and Initial Rank candidates by domain authority and semantic relevance
        ranked_scored_pairs = await SourceEvidenceEngine.score_and_rank_sources(clean_query, raw_results)
        top_candidates = [item for item, _ in ranked_scored_pairs[:max_results]]

        # 2. Parallel Deep Scraping for top candidates to extract rich tables and full content
        is_roster = any(k in clean_query.lower() for k in ["chief minister", "prime minister", "governor", "president", "cabinet", "roster", "ministers", "states", "countries", "leaders", "list of"])

        if deep_scrape:
            scrape_candidates = [
                r for r in top_candidates
                if r.url and r.url.startswith("http") and "aetherius.ai" not in r.url and (not r.deep_content or "wikipedia.org" in r.url)
            ]
            if scrape_candidates:
                scrape_tasks = [cls.scrape_page_content(item.url) for item in scrape_candidates]
                scraped_contents = await asyncio.gather(*scrape_tasks, return_exceptions=True)
                for item, content in zip(scrape_candidates, scraped_contents):
                    if isinstance(content, str) and content:
                        dense_content = SourceEvidenceEngine.extract_dense_factual_passages(
                            query=clean_query,
                            text=content,
                            is_roster=is_roster
                        )
                        item.deep_content = dense_content

        final_results = top_candidates

        return WebSearchResponse(
            query=query,
            results=final_results,
            summary=f"Retrieved {len(final_results)} scored and verified web sources for '{query}'"
        )

    @classmethod
    def to_citations(cls, search_response: WebSearchResponse) -> List[SourceCitation]:
        citations = []
        for r in search_response.results:
            domain = r.source_domain
            if not domain and r.url:
                try:
                    domain = urlparse(r.url).hostname
                except Exception:
                    domain = "web"

            citations.append(SourceCitation(
                source_type="web",
                title=r.title,
                snippet=r.deep_content[:300] if r.deep_content else r.snippet,
                url=r.url,
                source_domain=domain
            ))
        return citations
