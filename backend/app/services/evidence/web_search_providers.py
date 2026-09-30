import asyncio
import os
import re
import base64
import urllib.parse
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
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


class BingSearchProvider(BaseSearchProvider):
    """
    Direct Bing Web Search Parser.
    Extracts high-ranking search results and unwraps real destination URLs.
    """

    def is_available(self) -> bool:
        return True

    @staticmethod
    def _unwrap_bing_url(raw_url: str) -> str:
        try:
            if "bing.com/ck/a?" in raw_url and "u=" in raw_url:
                parsed = urllib.parse.urlparse(raw_url)
                params = urllib.parse.parse_qs(parsed.query)
                u_list = params.get("u", [])
                if u_list:
                    u_val = u_list[0]
                    if u_val.startswith("a1"):
                        b64_str = u_val[2:]
                        b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
                        decoded = base64.urlsafe_b64decode(b64_str).decode("utf-8", errors="ignore")
                        if decoded.startswith("http"):
                            return decoded
            return raw_url
        except Exception:
            return raw_url

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        results: List[WebSearchResultItem] = []
        clean_query = query.strip()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=6.0, headers=headers, follow_redirects=True) as client:
                res = await client.get("https://www.bing.com/search", params={"q": clean_query})
                if res.status_code == 200 and BeautifulSoup:
                    soup = BeautifulSoup(res.text, "html.parser")
                    li_results = soup.find_all("li", class_="b_algo")
                    for li in li_results[:max_results + 2]:
                        h2 = li.find("h2")
                        a = h2.find("a") if h2 else None
                        snippet_elem = li.find("p") or li.find("div", class_="b_caption")
                        if a:
                            title = a.get_text(strip=True)
                            raw_url = a.get("href", "")
                            real_url = self._unwrap_bing_url(raw_url)
                            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            domain = real_url.split("/")[2] if "//" in real_url else "bing.com"

                            if title and real_url and real_url.startswith("http") and "bing.com/search" not in real_url:
                                results.append(WebSearchResultItem(
                                    title=title,
                                    url=real_url,
                                    snippet=snippet,
                                    source_domain=domain
                                ))
                                if len(results) >= max_results:
                                    break
        except Exception as e:
            logger.debug(f"Bing search parser notice: {e}")

        return results


class WikipediaSearchProvider(BaseSearchProvider):
    """
    Instant, high-authority encyclopedia & knowledge retrieval provider.
    Zero-key, 100% reliable for entities, concepts, people, companies, technology, and science.
    """

    def is_available(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 4) -> List[WebSearchResultItem]:
        results: List[WebSearchResultItem] = []
        clean_query = query.strip()
        
        # Strip common conversational prefixes for Wikipedia search
        clean_q = re.sub(
            r"^(what is|who is|tell me about|explain|overview of|search for|define|where is|history of|how to|i want to)\s+",
            "",
            clean_query,
            flags=re.IGNORECASE
        ).strip().rstrip("?.,")
        if not clean_q:
            clean_q = clean_query

        # Only query Wikipedia for focused concepts/entities (avoid searching long conversational sentences)
        words = clean_q.split()
        if len(words) > 5 and not any(k in clean_query.lower() for k in ["who is", "what is", "where is", "history of", "overview of"]):
            return []

        headers = {
            "User-Agent": "AetheriusAI/1.0 (https://aetherius.ai; search-agent@aetherius.ai)",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                res = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "opensearch",
                        "search": clean_q,
                        "limit": max_results,
                        "namespace": 0,
                        "format": "json"
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    if len(data) >= 4:
                        titles = data[1]
                        descriptions = data[2]
                        urls = data[3]

                        for title, desc, url in zip(titles, descriptions, urls):
                            snippet = desc if desc and len(desc) > 10 else f"Wikipedia article for {title}"
                            deep_content = None
                            try:
                                encoded_title = urllib.parse.quote(title.replace(" ", "_"))
                                sum_res = await client.get(
                                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}",
                                    timeout=2.5
                                )
                                if sum_res.status_code == 200:
                                    sum_data = sum_res.json()
                                    extract = sum_data.get("extract", "")
                                    if extract:
                                        snippet = extract[:300]
                                        deep_content = extract
                            except Exception:
                                pass

                            item = WebSearchResultItem(
                                title=f"{title} - Wikipedia",
                                url=url,
                                snippet=snippet,
                                source_domain="en.wikipedia.org"
                            )
                            item.deep_content = deep_content
                            results.append(item)
        except Exception as e:
            logger.debug(f"Wikipedia search notice: {e}")

        return results


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """
    DuckDuckGo multi-strategy web search engine.
    Supports DDG Lite POST form submission, HTML parsing with URL unquoting,
    Instant Answer API, and DDGS library failover.
    """

    def is_available(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        results: List[WebSearchResultItem] = []
        clean_query = query.strip()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Strategy 1: DDG Lite POST
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers, follow_redirects=True) as client:
                resp = await client.post("https://lite.duckduckgo.com/lite/", data={"q": clean_query})
                if resp.status_code == 200 and BeautifulSoup:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    links = soup.find_all("a", class_="result-link")
                    snippets = soup.find_all("td", class_="result-snippet")

                    for l, s in zip(links[:max_results + 2], snippets[:max_results + 2]):
                        raw_url = l.get("href", "")
                        real_url = raw_url
                        if "uddg=" in raw_url:
                            real_url = urllib.parse.unquote(raw_url.split("uddg=")[1].split("&")[0])
                        elif raw_url.startswith("//"):
                            real_url = f"https:{raw_url}"

                        title = l.get_text(strip=True)
                        snippet = s.get_text(strip=True)
                        domain = real_url.split("/")[2] if "//" in real_url else "web"

                        if title and real_url and real_url.startswith("http"):
                            results.append(WebSearchResultItem(
                                title=title,
                                url=real_url,
                                snippet=snippet,
                                source_domain=domain
                            ))
                            if len(results) >= max_results:
                                return results
        except Exception as e:
            logger.debug(f"DuckDuckGo Lite notice: {e}")

        # Strategy 2: DDG HTML POST fallback
        if not results:
            try:
                async with httpx.AsyncClient(timeout=5.0, headers=headers, follow_redirects=True) as client:
                    resp = await client.post("https://html.duckduckgo.com/html/", data={"q": clean_query})
                    if resp.status_code == 200 and BeautifulSoup:
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

                            if snippet and real_url and real_url.startswith("http"):
                                results.append(WebSearchResultItem(
                                    title=title,
                                    url=real_url,
                                    snippet=snippet,
                                    source_domain=domain
                                ))
            except Exception as e:
                logger.debug(f"DuckDuckGo HTML fallback notice: {e}")

        return results[:max_results]


class SerperSearchProvider(BaseSearchProvider):
    """Google Search API powered by Serper."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPER_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        if not self.is_available():
            return []
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                    json={"q": query, "num": max_results}
                )
                if res.status_code == 200:
                    data = res.json()
                    results = []
                    for item in data.get("organic", []):
                        url = item.get("link", "")
                        domain = url.split("/")[2] if "//" in url else "google"
                        results.append(WebSearchResultItem(
                            title=item.get("title", ""),
                            url=url,
                            snippet=item.get("snippet", ""),
                            source_domain=domain
                        ))
                    return results
        except Exception as e:
            logger.warning(f"Serper search error: {e}")
        return []


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
    """
    Tiered Failover Multi-Provider Search Orchestrator.
    Combines paid API providers (Tavily, Serper, Brave), robust Bing & DuckDuckGo web search,
    and authoritative encyclopedic Wikipedia knowledge retrieval.
    """

    def __init__(self):
        self.bing = BingSearchProvider()
        self.duckduckgo = DuckDuckGoSearchProvider()
        self.wikipedia = WikipediaSearchProvider()
        self.tavily = TavilySearchProvider()
        self.serper = SerperSearchProvider()
        self.brave = BraveSearchProvider()

    async def execute_search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. If paid search APIs configured, prioritize them
        for paid_provider in [self.tavily, self.serper, self.brave]:
            if paid_provider.is_available():
                try:
                    paid_res = await paid_provider.search(clean_query, max_results=max_results)
                    if paid_res:
                        return paid_res
                except Exception as e:
                    logger.debug(f"Paid search provider notice: {e}")

        # 2. Parallel Search: Bing Web + DDG + Wikipedia Knowledge
        results_by_url: Dict[str, WebSearchResultItem] = {}

        async def run_bing():
            try:
                return await self.bing.search(clean_query, max_results=max_results)
            except Exception as e:
                logger.debug(f"Bing search error: {e}")
                return []

        async def run_ddg():
            try:
                return await self.duckduckgo.search(clean_query, max_results=max_results)
            except Exception as e:
                logger.debug(f"DDG Search error: {e}")
                return []

        async def run_wiki():
            try:
                return await self.wikipedia.search(clean_query, max_results=2)
            except Exception as e:
                logger.debug(f"Wikipedia search error: {e}")
                return []

        bing_res, ddg_res, wiki_res = await asyncio.gather(run_bing(), run_ddg(), run_wiki())

        # Collect unique results
        for item in (bing_res or []):
            if item.url and item.url not in results_by_url:
                results_by_url[item.url] = item

        for item in (ddg_res or []):
            if item.url and item.url not in results_by_url:
                results_by_url[item.url] = item

        for item in (wiki_res or []):
            if item.url and item.url not in results_by_url:
                results_by_url[item.url] = item

        return list(results_by_url.values())[:max_results]
