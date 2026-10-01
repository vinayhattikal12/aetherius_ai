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
    Frontier-grade source credibility, domain authority, freshness scoring,
    deep HTML reading, and table-to-markdown extraction engine.
    """

    # High-Authority Official Documentation & Primary Source Domains (0.90 - 1.00)
    TIER_1_DOMAINS = {
        "docs.python.org", "python.org", "github.com", "kernel.org", "postgresql.org",
        "rust-lang.org", "doc.rust-lang.org", "kubernetes.io", "fastapi.tiangolo.com",
        "huggingface.co", "arxiv.org", "w3.org", "developer.mozilla.org", "microsoft.com",
        "learn.microsoft.com", "apple.com", "developer.apple.com", "google.dev", "cloud.google.com",
        "aws.amazon.com", "docs.aws.amazon.com", "docker.com", "docs.docker.com", "golang.org",
        "pkg.go.dev", "nodejs.org", "react.dev", "vuejs.org", "typescriptlang.org", "sqlite.org",
        "en.wikipedia.org", "wikipedia.org", "india.gov.in", "gov.in", "whitehouse.gov", "un.org"
    }

    # Established Tech & Scientific Publications (0.75 - 0.89)
    TIER_2_DOMAINS = {
        "stackoverflow.com", "news.ycombinator.com", "techcrunch.com", "reuters.com",
        "theverge.com", "arstechnica.com", "nature.com", "ieee.org", "bloomberg.com",
        "wired.com", "zdnet.com", "infoworld.com", "medium.com", "bbc.com", "thehindu.com",
        "ndtv.com", "indianexpress.com", "timesofindia.indiatimes.com"
    }

    @classmethod
    def calculate_domain_authority(cls, url: str) -> float:
        """Assigns an authority weight based on domain reputation and primary source status."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname.lower() if parsed.hostname else ""
            if hostname.startswith("www."):
                hostname = hostname[4:]

            for d in cls.TIER_1_DOMAINS:
                if hostname == d or hostname.endswith(f".{d}"):
                    return 0.95

            for d in cls.TIER_2_DOMAINS:
                if hostname == d or hostname.endswith(f".{d}"):
                    return 0.80

            if hostname.endswith(".gov") or hostname.endswith(".edu") or hostname.endswith(".gov.in") or hostname.endswith(".ac.in"):
                return 0.95

            if hostname:
                return 0.60

            return 0.40
        except Exception:
            return 0.40

    @classmethod
    def calculate_freshness_score(cls, text: str, url: str) -> float:
        """Detects date cues and recency indicators dynamically in the source content."""
        from datetime import datetime, timezone
        curr_year = datetime.now(timezone.utc).year
        combined = f"{url} {text}".lower()

        if str(curr_year) in combined or "today" in combined or "hours ago" in combined or "just now" in combined:
            return 1.0
        if str(curr_year - 1) in combined or "yesterday" in combined or "days ago" in combined or "week ago" in combined:
            return 0.88
        if str(curr_year - 2) in combined or "month ago" in combined or "months ago" in combined:
            return 0.72

        return 0.50

    @classmethod
    def calculate_content_density(cls, text: str) -> float:
        """Measures the factual information density of the text snippet."""
        if not text:
            return 0.0
        words = text.split()
        if len(words) < 5:
            return 0.1

        has_code = 1.0 if any(char in text for char in ["{", "}", "(", ")", "def ", "class ", "import ", "const "]) else 0.0
        has_numbers = 1.0 if re.search(r"\b\d+(\.\d+)?%?\b", text) else 0.0
        has_table = 1.0 if "|" in text and "---" in text else 0.0

        length_score = min(1.0, len(words) / 50.0)
        return round(0.3 * length_score + 0.2 * has_code + 0.2 * has_numbers + 0.3 * has_table, 2)

    @classmethod
    async def score_and_rank_sources(
        cls,
        query: str,
        sources: List[WebSearchResultItem]
    ) -> List[Tuple[WebSearchResultItem, float]]:
        """
        Calculates composite evidence score for each source:
        Composite = 0.40 * Relevance + 0.30 * Domain Authority + 0.15 * Freshness + 0.15 * Density
        """
        if not sources:
            return []

        query_vec = EmbeddingService._generate_semantic_vector(query)
        scored_list: List[Tuple[WebSearchResultItem, float]] = []

        is_sports = any(k in query.lower() for k in ["match", "score", "scores", "who won", "won the", "vs", "versus", "cricket", "football", "tennis", "ipl", "game"])

        for item in sources:
            content_sample = f"{item.title} {item.snippet} {item.deep_content or ''}"
            item_vec = EmbeddingService._generate_semantic_vector(item.title + " " + item.snippet)
            relevance = max(0.0, EmbeddingService.cosine_similarity(query_vec, item_vec))

            authority = cls.calculate_domain_authority(item.url)
            if any(d in item.url for d in ["open-meteo.com", "open.er-api.com", "finance.yahoo.com"]):
                authority = 1.0
                relevance = max(relevance, 0.95)

            if is_sports:
                if any(d in item.url.lower() for d in ["sports.google.com", "news.google.com", "cricinfo", "cricbuzz", "yahoo", "espn", "foxsports", "bbc.com", "hindu"]):
                    authority = 1.0
                    relevance = max(relevance, 0.95)
                elif "wikipedia.org" in item.url:
                    authority = 0.20

            freshness = cls.calculate_freshness_score(content_sample, item.url)
            density = cls.calculate_content_density(content_sample)

            composite = round(
                (0.40 * relevance) + (0.30 * authority) + (0.15 * freshness) + (0.15 * density),
                3
            )
            scored_list.append((item, composite))

        # Rank descending
        scored_list.sort(key=lambda x: x[1], reverse=True)

        # Filter out dictionary definitions unless requested, and filter out wikipedia for sports queries
        is_dict_query = any(k in query.lower() for k in ["define", "definition", "meaning of", "dictionary"])
        filtered_list = []
        for item, comp in scored_list:
            if not is_dict_query and any(d in item.url.lower() for d in ["wiktionary.org", "merriam-webster.com", "oxfordlearnersdictionaries.com", "dictionary.cambridge.org", "dictionary.com"]):
                continue
            if is_sports and "wikipedia.org" in item.url and len(scored_list) > 1:
                continue
            filtered_list.append((item, comp))

        return filtered_list if filtered_list else scored_list

    @classmethod
    def extract_dense_factual_passages(
        cls,
        query: str,
        text: str,
        is_roster: bool = False,
        max_sentences: int = 3
    ) -> str:
        """
        Extracts high-signal, semantically relevant factual sentences for single-point queries
        while preserving structured data tables intact for roster queries.
        Reduces CPU prompt evaluation latency from ~15s to ~1s.
        """
        if not text:
            return ""

        # If text contains structured markdown table or query is a roster query, preserve table
        if "[Structured Table Data]:" in text or ("|" in text and "---" in text) or is_roster:
            return text[:2800]

        # Single-point query: Sentence slicing and semantic reranking
        clean_q = query.strip()
        q_words = set(re.findall(r"\w+", clean_q.lower())) - {"who", "is", "the", "of", "in", "a", "an", "what", "how", "when", "where", "why", "to", "for"}
        q_vec = EmbeddingService._generate_semantic_vector(clean_q)

        # Split text into candidate sentences
        raw_sentences = re.split(r"(?<=[.!?])\s+", text)
        ACTION_VERBS = {"sworn", "appointed", "incumbent", "current", "succeeded", "elected", "took", "assumed", "holds", "office", "is", "became", "born", "founded", "established"}
        YEAR_PAT = re.compile(r"\b(19\d{2}|20\d{2})\b")

        scored_sentences = []
        for s in raw_sentences:
            s_clean = s.strip()
            if len(s_clean) < 25 or len(s_clean) > 300:
                continue
            # Filter boilerplate
            if any(bp in s_clean.lower() for bp in ["wikipedia", "cookie", "privacy policy", "terms of use", "all rights reserved", "subscribe", "javascript"]):
                continue

            s_lower = s_clean.lower()
            s_words = set(re.findall(r"\w+", s_lower))
            overlap = len(q_words & s_words) / max(1, len(q_words)) if q_words else 0.0
            
            s_vec = EmbeddingService._generate_semantic_vector(s_clean)
            sim = EmbeddingService.cosine_similarity(q_vec, s_vec)
            
            action_boost = 0.25 if any(v in s_words for v in ACTION_VERBS) else 0.0
            year_boost = 0.20 if YEAR_PAT.search(s_clean) else 0.0

            total_score = (0.40 * sim) + (0.35 * overlap) + action_boost + year_boost
            scored_sentences.append((s_clean, total_score))

        if not scored_sentences:
            return text[:600]

        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        top_sentences = [s for s, _ in scored_sentences[:max_sentences]]
        return " ".join(top_sentences)

    @classmethod
    def _table_to_markdown(cls, table_elem, max_rows: int = 35) -> Tuple[str, int]:
        """Converts an HTML table element into a clean GitHub-flavored Markdown table with relevance weight."""
        if table_elem is None or not hasattr(table_elem, "attrs") or table_elem.attrs is None:
            return "", 0

        raw_classes = table_elem.attrs.get("class", [])
        if isinstance(raw_classes, list):
            classes = " ".join(raw_classes)
        elif isinstance(raw_classes, str):
            classes = raw_classes
        else:
            classes = ""

        if any(bad in classes.lower() for bad in ["infobox", "sidebar", "navbox", "ambox", "metadata", "ombox", "vertical-navbox"]):
            return "", 0

        rows = table_elem.find_all("tr")
        if not rows or len(rows) < 3:
            return "", 0

        header_row = rows[0]
        raw_headers = [c.get_text(" ", strip=True) for c in header_row.find_all(["th", "td"])]
        if not raw_headers:
            return "", 0

        unwanted = {"portrait", "image", "photo", "flag", "list", "ref", "reference", "coat of arms", "signature", "map", "constituency", "assembly", "governor", "cabinet"}
        scored_cols = []
        for idx, name in enumerate(raw_headers):
            clean_name = re.sub(r"\[.*?\]", "", name).strip().lower()
            if any(u in clean_name for u in unwanted):
                continue
            score = 1
            if any(k in clean_name for k in ["name", "officeholder", "chief minister", "prime minister", "incumbent", "leader", "person", "president", "state", "country"]):
                score += 10
            elif any(k in clean_name for k in ["term", "office", "took office", "dates", "period", "duration", "years"]):
                score += 8
            elif any(k in clean_name for k in ["party", "alliance"]):
                score += 6
            elif clean_name in ["no", "#", "no.", "rank", "s.no"]:
                score += 2
            scored_cols.append((idx, name, score))

        if len(scored_cols) < 2:
            # Fallback to non-empty columns
            for idx, name in enumerate(raw_headers):
                if name and not any(idx == sc[0] for sc in scored_cols):
                    scored_cols.append((idx, name, 1))

        if len(scored_cols) < 2:
            return "", 0

        # Pick top 3-4 scored columns, maintaining left-to-right table order
        scored_cols.sort(key=lambda x: x[2], reverse=True)
        chosen = sorted(scored_cols[:3], key=lambda x: x[0])
        chosen_indices = [c[0] for c in chosen]
        headers = [re.sub(r"\[.*?\]", "", c[1]).strip().replace("|", "/") for c in chosen]

        md_lines = []
        md_lines.append("| " + " | ".join(headers) + " |")
        md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Capture up to 60 rows; if table is longer, include head and tail to preserve both start and modern entries
        data_rows = rows[1:]
        if len(data_rows) > 60:
            selected_rows = data_rows[:20] + data_rows[-40:]
        else:
            selected_rows = data_rows[:60]

        row_count = 0
        for r in selected_rows:
            cols = r.find_all(["th", "td"])
            if not cols:
                continue
            vals = []
            for i in chosen_indices:
                if i < len(cols):
                    raw_c = cols[i].get_text(" ", strip=True)
                    clean_c = re.sub(r"\[.*?\]", "", raw_c).replace("|", "/").strip()
                    vals.append(clean_c[:60])
                else:
                    vals.append("")
            if any(vals) and len([v for v in vals if v]) >= 2:
                md_lines.append("| " + " | ".join(vals) + " |")
                row_count += 1

        if row_count < 2:
            return "", 0

        # Calculate relevance weight
        weight = row_count
        header_str = " ".join(headers).lower()
        if any(k in header_str for k in ["officeholder", "chief minister", "prime minister", "incumbent", "name", "leader", "president", "country", "state"]):
            weight += 100
        if "salary" in header_str:
            weight -= 50

        return "\n".join(md_lines), weight

    @classmethod
    async def deep_scrape_url(cls, url: str, timeout: float = 4.0) -> Optional[str]:
        """
        Deep reader: Fetches webpage, converts data tables into clean Markdown,
        and extracts structured factual body text.
        """
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
                    text_only = re.sub(r"<(script|style).*?>.*?</\1>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
                    text_only = re.sub(r"<[^>]+>", " ", text_only)
                    cleaned_text = re.sub(r"\s+", " ", text_only).strip()
                    return cleaned_text[:2000] if len(cleaned_text) > 80 else None

                soup = BeautifulSoup(resp.text, "html.parser")

                # Decompose non-content tags
                for element in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "svg", "form", "iframe", "figure"]):
                    element.decompose()

                content_container = (
                    soup.find("article")
                    or soup.find("main")
                    or soup.find("div", {"id": re.compile(r"(content|main|article|body|mw-content-text)", re.I)})
                    or soup.find("body")
                )

                if not content_container:
                    return None

                extracted_blocks = []

                # 1. Extract and rank all structured data tables
                tables = content_container.find_all("table")
                parsed_tables = []
                for table in tables:
                    md_table, weight = cls._table_to_markdown(table, max_rows=35)
                    if md_table:
                        parsed_tables.append((md_table, weight))
                    table.decompose()  # Avoid re-processing table text in paragraphs

                if parsed_tables:
                    parsed_tables.sort(key=lambda x: x[1], reverse=True)
                    for md_table, _ in parsed_tables[:2]:
                        extracted_blocks.append(f"\n[Structured Table Data]:\n{md_table}\n")

                # 2. Extract headings, lead paragraphs, and lists
                paragraphs = content_container.find_all(["h1", "h2", "h3", "p", "li", "pre", "code"])
                for p in paragraphs:
                    raw_text = p.get_text(separator=" ", strip=True)
                    clean_text = re.sub(r"\[(?:edit|\d+|[a-z]|note\s*\d+)\]", "", raw_text, flags=re.IGNORECASE)
                    clean_text = re.sub(r"\s+", " ", clean_text).strip()
                    if len(clean_text) > 25 and clean_text not in extracted_blocks:
                        if p.name in ["h1", "h2", "h3"]:
                            extracted_blocks.append(f"### {clean_text}")
                        elif p.name == "li":
                            extracted_blocks.append(f"- {clean_text}")
                        else:
                            extracted_blocks.append(clean_text)

                combined = "\n\n".join(extracted_blocks)
                if len(combined) > 80:
                    return combined[:3000]
                return None
        except Exception as e:
            logger.debug(f"Deep scraping notice for {url}: {e}")
            return None
