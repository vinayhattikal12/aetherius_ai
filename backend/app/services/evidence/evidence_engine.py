import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from backend.app.schemas.web_search import WebSearchResultItem
from backend.app.services.embedding_service import EmbeddingService
from backend.app.core.logging import logger


class SourceEvidenceEngine:
    """
     frontier-grade source credibility, domain authority, freshness scoring,
    and evidence ranking engine.
    """

    # High-Authority Official Documentation & Primary Source Domains (0.90 - 1.00)
    TIER_1_DOMAINS = {
        "docs.python.org", "python.org", "github.com", "kernel.org", "postgresql.org",
        "rust-lang.org", "doc.rust-lang.org", "kubernetes.io", "fastapi.tiangolo.com",
        "huggingface.co", "arxiv.org", "w3.org", "developer.mozilla.org", "microsoft.com",
        "learn.microsoft.com", "apple.com", "developer.apple.com", "google.dev", "cloud.google.com",
        "aws.amazon.com", "docs.aws.amazon.com", "docker.com", "docs.docker.com", "golang.org",
        "pkg.go.dev", "nodejs.org", "react.dev", "vuejs.org", "typescriptlang.org", "sqlite.org"
    }

    # Established Tech & Scientific Publications (0.75 - 0.89)
    TIER_2_DOMAINS = {
        "stackoverflow.com", "news.ycombinator.com", "techcrunch.com", "reuters.com",
        "theverge.com", "arstechnica.com", "nature.com", "ieee.org", "bloomberg.com",
        "wired.com", "zdnet.com", "infoworld.com", "medium.com"
    }

    @classmethod
    def calculate_domain_authority(cls, url: str) -> float:
        """Assigns an authority weight based on domain reputation and documentation primary status."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname.lower() if parsed.hostname else ""
            if hostname.startswith("www."):
                hostname = hostname[4:]

            # Exact or subdomain check for Tier 1
            for d in cls.TIER_1_DOMAINS:
                if hostname == d or hostname.endswith(f".{d}"):
                    return 0.95

            # Tier 2 check
            for d in cls.TIER_2_DOMAINS:
                if hostname == d or hostname.endswith(f".{d}"):
                    return 0.80

            # Government / Academic TLDs
            if hostname.endswith(".gov") or hostname.endswith(".edu"):
                return 0.92

            # General web
            if hostname:
                return 0.60

            return 0.40
        except Exception:
            return 0.40

    @classmethod
    def calculate_freshness_score(cls, text: str, url: str) -> float:
        """Detects date cues and recency indicators in the source content."""
        combined = f"{url} {text}".lower()

        # Check for current/recent year mentions (e.g. 2026, 2025)
        if "2026" in combined:
            return 0.95
        if "2025" in combined:
            return 0.85
        if "2024" in combined:
            return 0.70
        if "yesterday" in combined or "today" in combined or "hours ago" in combined:
            return 1.0
        if "days ago" in combined or "week ago" in combined:
            return 0.90
        if "month ago" in combined:
            return 0.75

        return 0.50

    @classmethod
    def calculate_content_density(cls, text: str) -> float:
        """Measures the factual information density of the text snippet."""
        if not text:
            return 0.0
        words = text.split()
        if len(words) < 5:
            return 0.1

        # Check for code blocks, numbers, technical terms
        has_code = 1.0 if any(char in text for char in ["{", "}", "(", ")", "def ", "class ", "import ", "const "]) else 0.0
        has_numbers = 1.0 if re.search(r"\b\d+(\.\d+)?%?\b", text) else 0.0

        length_score = min(1.0, len(words) / 50.0)
        return round(0.4 * length_score + 0.3 * has_code + 0.3 * has_numbers, 2)

    @classmethod
    async def score_and_rank_sources(
        cls,
        query: str,
        sources: List[WebSearchResultItem]
    ) -> List[Tuple[WebSearchResultItem, float]]:
        """
        Calculates composite evidence score for each source:
        Composite = 0.35 * Relevance + 0.35 * Domain Authority + 0.15 * Freshness + 0.15 * Density
        """
        if not sources:
            return []

        query_emb = await EmbeddingService.embed_text(query)

        scored_list: List[Tuple[WebSearchResultItem, float]] = []

        for item in sources:
            content_sample = f"{item.title} {item.snippet} {item.deep_content or ''}"
            
            # 1. Semantic relevance
            item_emb = await EmbeddingService.embed_text(item.title + " " + item.snippet)
            relevance = max(0.0, EmbeddingService.cosine_similarity(query_emb, item_emb))

            # 2. Domain Authority
            authority = cls.calculate_domain_authority(item.url)

            # 3. Freshness
            freshness = cls.calculate_freshness_score(content_sample, item.url)

            # 4. Density
            density = cls.calculate_content_density(content_sample)

            composite = round(
                (0.35 * relevance) + (0.35 * authority) + (0.15 * freshness) + (0.15 * density),
                3
            )
            scored_list.append((item, composite))

        # Rank descending by composite score
        scored_list.sort(key=lambda x: x[1], reverse=True)
        return scored_list

    @classmethod
    async def deep_scrape_url(cls, url: str, timeout: float = 3.5) -> Optional[str]:
        """Deep reader: Asynchronously fetches a webpage, strips boilerplate/ads, and extracts readable text."""
        if not url or not url.startswith("http") or "search.aetherius.ai" in url:
            return None

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200 or not resp.text:
                    return None

                if BeautifulSoup is None:
                    # Clean regex fallback
                    text_only = re.sub(r"<(script|style).*?>.*?</\1>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
                    text_only = re.sub(r"<[^>]+>", " ", text_only)
                    cleaned_text = re.sub(r"\s+", " ", text_only).strip()
                    return cleaned_text[:2000] if len(cleaned_text) > 80 else None

                soup = BeautifulSoup(resp.text, "html.parser")

                # Remove non-content elements
                for element in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "svg", "form", "iframe"]):
                    element.decompose()

                # Prioritize main article/content containers if present
                content_container = (
                    soup.find("article")
                    or soup.find("main")
                    or soup.find("div", {"id": re.compile(r"(content|main|article|body)", re.I)})
                    or soup.find("body")
                )

                if not content_container:
                    return None

                paragraphs = content_container.find_all(["p", "h1", "h2", "h3", "li", "pre", "code"])
                extracted_lines = []
                for p in paragraphs:
                    text = p.get_text(separator=" ", strip=True)
                    if len(text) > 30 and text not in extracted_lines:
                        extracted_lines.append(text)

                combined_text = "\n".join(extracted_lines)
                cleaned_text = re.sub(r"\s+", " ", combined_text).strip()

                if len(cleaned_text) > 80:
                    return cleaned_text[:2000] # Return up to 2000 chars of dense factual data
                return None
        except Exception as e:
            logger.debug(f"Deep scraping notice for {url}: {e}")
            return None
