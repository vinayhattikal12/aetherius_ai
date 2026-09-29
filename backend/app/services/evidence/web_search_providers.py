import asyncio
import os
import re
import urllib.parse
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from backend.app.schemas.web_search import WebSearchResultItem
from backend.app.core.logging import logger


class BaseSearchProvider(ABC):
    """Abstract interface for pluggable web search providers."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """DuckDuckGo provider with dual API and HTML scraping resilience."""

    def is_available(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        results: List[WebSearchResultItem] = []
        clean_query = query.strip()

        # 1. Try DDGS API
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(clean_query, max_results=max_results))
                for item in raw_results:
                    url = item.get("href") or item.get("link") or ""
                    domain = url.split("/")[2] if "//" in url else "web"
                    results.append(WebSearchResultItem(
                        title=item.get("title", "Web Source"),
                        url=url,
                        snippet=item.get("body", ""),
                        source_domain=domain
                    ))
        except Exception as e:
            logger.debug(f"DuckDuckGo API notice: {e}")

        # 2. Fallback to HTML interface if API was empty/rate-limited
        if not results:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        "https://html.duckduckgo.com/html/",
                        params={"q": clean_query},
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    )
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        result_divs = soup.find_all("div", class_="result")
                        for r in result_divs[:max_results]:
                            h2 = r.find("h2", class_="result__title")
                            link = h2.find("a") if h2 else None
                            title = link.get_text(strip=True) if link else clean_query
                            raw_url = link["href"] if link and "href" in link.attrs else ""

                            real_url = raw_url
                            if "uddg=" in raw_url:
                                real_url = urllib.parse.unquote(raw_url.split("uddg=")[1].split("&")[0])
                            elif raw_url.startswith("//"):
                                real_url = f"https:{raw_url}"

                            domain = real_url.split("/")[2] if "//" in real_url else "web"
                            snippet_elem = r.find("a", class_="result__snippet")
                            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                            if snippet and real_url:
                                results.append(WebSearchResultItem(
                                    title=title,
                                    url=real_url,
                                    snippet=snippet,
                                    source_domain=domain
                                ))
            except Exception as e2:
                logger.debug(f"DuckDuckGo HTML fallback notice: {e2}")

        return results


class TavilySearchProvider(BaseSearchProvider):
    """Tavily search provider for optimized LLM-tailored web search."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        if not self.is_available():
            return []
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "advanced"
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    results = []
                    for item in data.get("results", []):
                        url = item.get("url", "")
                        domain = url.split("/")[2] if "//" in url else "web"
                        results.append(WebSearchResultItem(
                            title=item.get("title", ""),
                            url=url,
                            snippet=item.get("content", ""),
                            source_domain=domain
                        ))
                    return results
        except Exception as e:
            logger.warning(f"Tavily search error: {e}")
        return []


class BraveSearchProvider(BaseSearchProvider):
    """Brave Search API provider for independent privacy-first search."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("BRAVE_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        if not self.is_available():
            return []
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"X-Subscription-Token": self.api_key},
                    params={"q": query, "count": max_results}
                )
                if res.status_code == 200:
                    data = res.json()
                    web = data.get("web", {})
                    results = []
                    for item in web.get("results", []):
                        url = item.get("url", "")
                        domain = url.split("/")[2] if "//" in url else "web"
                        results.append(WebSearchResultItem(
                            title=item.get("title", ""),
                            url=url,
                            snippet=item.get("description", ""),
                            source_domain=domain
                        ))
                    return results
        except Exception as e:
            logger.warning(f"Brave search error: {e}")
        return []


class MultiProviderSearchOrchestrator:
    """Orchestrates search execution across available providers with tiered failover."""

    def __init__(self):
        self.providers: List[BaseSearchProvider] = [
            TavilySearchProvider(),
            BraveSearchProvider(),
            DuckDuckGoSearchProvider(),
        ]

    async def execute_search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        for provider in self.providers:
            if provider.is_available():
                try:
                    res = await provider.search(query, max_results=max_results)
                    if res:
                        return res
                except Exception as e:
                    logger.warning(f"Search provider failover notice: {e}")
                    continue

        return []
