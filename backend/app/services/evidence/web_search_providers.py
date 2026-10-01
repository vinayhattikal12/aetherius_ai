import asyncio
import os
import re
import urllib.parse
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
from backend.app.schemas.web_search import WebSearchResultItem
from backend.app.core.logging import logger


class QueryCleaner:
    """Extracts high-signal search keywords from conversational user queries."""

    CONVERSATIONAL_PREFIXES = [
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:tell\s+me|show\s+me|find|search\s+for|search\s+the\s+web\s+for|look\s+up|what\s+is|what\s+are|what\'s|how\s+is|how\s+are|give\s+me|get\s+me|i\s+want\s+to\s+know|do\s+you\s+know|provide\s+me|who\s+won|who\s+has\s+won|what\s+was\s+the\s+result\s+of|result\s+of|score\s+of|latest\s+score\s+of)\s+",
        r"^(?:the\s+|a\s+)?list\s+of\s+",
        r"^(?:all\s+the\s+|all\s+)",
    ]

    TEMPORAL_NOISE = [
        r"\b(?:yesterday\'?s?\s+match|today\'?s?\s+match|last\s+night\'?s?\s+match|last\s+match)\b",
        r"\byesterday\'?s?\b",
        r"\btoday\'?s?\b",
        r"\bfrom\s+independence\s+till\s+(?:today|now|date)\b",
        r"\bfrom\s+independence\b",
        r"\bsince\s+(?:1947|1950|inception)\s+till\s+(?:today|now|date)\b",
        r"\bsince\s+(?:1947|1950|inception)\b",
        r"\bfrom\s+\d{4}\s+till\s+(?:today|now|date)\b",
        r"\bfrom\s+\d{4}\b",
        r"\btill\s+(?:today|now|date)\b",
        r"\bto\s+date\b",
        r"\bthroughout\s+history\b",
        r"\bover\s+the\s+years\b",
        r"\ball\s+time\b",
    ]

    CITY_ALIASES = {
        "bangalore": "Bengaluru",
        "bengaluru": "Bengaluru",
        "bombay": "Mumbai",
        "mumbai": "Mumbai",
        "calcutta": "Kolkata",
        "kolkata": "Kolkata",
        "madras": "Chennai",
        "chennai": "Chennai",
        "delhi": "New Delhi",
        "new york": "New York",
        "nyc": "New York",
        "sf": "San Francisco",
        "san francisco": "San Francisco",
        "la": "Los Angeles",
        "london": "London",
        "tokyo": "Tokyo",
        "singapore": "Singapore",
        "paris": "Paris",
        "berlin": "Berlin",
        "sydney": "Sydney",
        "toronto": "Toronto",
    }

    ACRONYM_EXPANSIONS = {
        r"\bcm's\b": "Chief Ministers",
        r"\bcms\b": "Chief Ministers",
        r"\bcm\b": "Chief Minister",
        r"\bpm's\b": "Prime Ministers",
        r"\bpms\b": "Prime Ministers",
        r"\bpm\b": "Prime Minister",
        r"\bceo\b": "CEO",
        r"\bcfo\b": "CFO",
        r"\bcto\b": "CTO",
        r"\bcji\b": "Chief Justice of India",
        r"\bpotus\b": "President of the United States",
        r"\bflotus\b": "First Lady of the United States",
        r"\brbi\b": "Reserve Bank of India",
        r"\bmla\b": "MLA",
        r"\bmp\b": "Member of Parliament",
        # International Sports Teams & Franchises
        r"\bind\b": "India",
        r"\bwi\b": "West Indies",
        r"\bwestindies\b": "West Indies",
        r"\bwindies\b": "West Indies",
        r"\baus\b": "Australia",
        r"\bpak\b": "Pakistan",
        r"\bnz\b": "New Zealand",
        r"\bsa\b": "South Africa",
        r"\beng\b": "England",
        r"\bsl\b": "Sri Lanka",
        r"\bban\b": "Bangladesh",
        r"\bafg\b": "Afghanistan",
        r"\bcsk\b": "Chennai Super Kings",
        r"\brcb\b": "Royal Challengers Bengaluru",
        r"\bmi\b": "Mumbai Indians",
        r"\bkkr\b": "Kolkata Knight Riders",
        r"\bdc\b": "Delhi Capitals",
        r"\bsrh\b": "Sunrisers Hyderabad",
        r"\bgt\b": "Gujarat Titans",
        r"\blsg\b": "Lucknow Super Giants",
        r"\bpbks\b": "Punjab Kings",
        r"\brr\b": "Rajasthan Royals",
        r"\bman utd\b": "Manchester United",
        r"\bmancity\b": "Manchester City",
        r"\breal madrid\b": "Real Madrid",
        r"\bbarca\b": "Barcelona",
    }

    @classmethod
    def clean_search_query(cls, raw_query: str, strip_temporal: bool = True) -> str:
        text = raw_query.strip()
        
        # 1. Expand acronyms first
        for pat, repl in cls.ACRONYM_EXPANSIONS.items():
            text = re.sub(pat, repl, text, flags=re.IGNORECASE).strip()

        # 2. Strip conversational fluff
        for pat in cls.CONVERSATIONAL_PREFIXES:
            text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()

        # 3. Strip temporal fluff for core entity lookup if requested
        if strip_temporal:
            for pat in cls.TEMPORAL_NOISE:
                text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()

        text = re.sub(r"[?!.,;]+$", "", text).strip()
        return re.sub(r"\s+", " ", text) if text else raw_query.strip()


class MultiAngleQuerySynthesizer:
    """
    Synthesizes multiple search query angles (Direct, Structured Knowledge, Temporal)
    and decomposes multi-entity comparison queries into parallel sub-searches.
    """

    @classmethod
    def decompose_multi_hop(cls, raw_query: str) -> List[str]:
        """
        Decomposes complex multi-entity or comparative queries (e.g. 'Compare PM and GDP of India and Japan')
        into parallel atomic search queries for each individual entity.
        """
        clean = QueryCleaner.clean_search_query(raw_query, strip_temporal=False)
        lower = clean.lower()

        # Do NOT decompose head-to-head sports matches or games (they are single unified events)
        if any(k in lower for k in ["match", "score", "scores", "who won", "won the", "game", "tournament", "cup", "odi", "t20", "ipl", "premier league", "champions league", "series"]):
            return []

        # Pattern 1: Compare/attribute of Entity1 and Entity2 (e.g., 'Compare PM of India and Japan')
        m1 = re.search(r"^(?:compare|what\s+is|what\s+are|tell\s+me|give\s+me)?\s*(.*?)\s+of\s+([A-Za-z\s]{2,30}?)\s+(?:and|with|vs\.?)\s+([A-Za-z\s]{2,30})$", clean, re.IGNORECASE)
        if m1:
            attr, e1, e2 = m1.group(1).strip(), m1.group(2).strip(), m1.group(3).strip()
            if attr and len(e1) > 1 and len(e2) > 1:
                return [f"{attr} of {e1}", f"{attr} of {e2}"]
            elif len(e1) > 1 and len(e2) > 1:
                return [e1, e2]

        # Pattern 2: Compare Entity1 and Entity2 / Entity1 vs Entity2 (e.g. 'Compare iPhone 16 and Galaxy S24')
        m2 = re.search(r"^(?:compare|difference\s+between)\s+([^,]+?)\s+(?:and|with|vs\.?)\s+([^,]+)$", clean, re.IGNORECASE)
        if m2:
            e1, e2 = m2.group(1).strip(), m2.group(2).strip()
            if len(e1) > 1 and len(e2) > 1:
                return [e1, e2]

        # Pattern 3: Explicit dual entity 'X vs Y' (non-sports, e.g. 'PostgreSQL vs MySQL')
        m3 = re.search(r"^([A-Za-z0-9\s]{2,30})\s+vs\.?\s+([A-Za-z0-9\s]{2,30})$", clean, re.IGNORECASE)
        if m3:
            return [m3.group(1).strip(), m3.group(2).strip()]

        return []

    @classmethod
    def synthesize_queries(cls, raw_query: str) -> Dict[str, str]:
        clean_core = QueryCleaner.clean_search_query(raw_query, strip_temporal=True)
        lower_core = clean_core.lower()

        is_roster = any(k in lower_core for k in ["chief minister", "prime minister", "governor", "president", "cabinet", "roster", "ministers", "states", "countries", "leaders"])
        
        queries = {
            "primary": clean_core,
        }

        # Angle A: Structured / Wikipedia list & entity queries
        if is_roster:
            core_topic = re.sub(r"^(?:the\s+|a\s+)?(?:list\s+of\s+)?", "", clean_core, flags=re.IGNORECASE).strip()
            queries["wiki_list"] = f"List of {core_topic}"
            singular_topic = re.sub(r"Ministers", "Minister", core_topic, flags=re.IGNORECASE)
            queries["wiki_entity"] = singular_topic
        else:
            queries["wiki_list"] = f"{clean_core} wikipedia"
            queries["wiki_entity"] = clean_core

        # Angle B: Temporal live query
        if not any(k in lower_core for k in ["2024", "2025", "2026"]):
            queries["temporal"] = f"current {clean_core} 2025 2026"
        else:
            queries["temporal"] = clean_core

        return queries


class BaseSearchProvider(ABC):
    """Abstract interface for pluggable web search providers."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class LiveWeatherProvider(BaseSearchProvider):
    """
    Zero-key, instantaneous live meteorological provider powered by Open-Meteo.
    Provides sub-second real-time temperature, condition, humidity, wind, and forecast.
    """

    WEATHER_CODES = {
        0: "Clear sky (Sunny)",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }

    def is_available(self) -> bool:
        return True

    def is_weather_query(self, query: str) -> bool:
        lower = query.lower()
        triggers = ["temp", "temperature", "weather", "forecast", "climate", "rain", "sunny", "humidity", "hot", "cold", "degrees"]
        return any(t in lower for t in triggers)

    def extract_city(self, query: str) -> Optional[str]:
        lower = query.lower()
        # Direct alias check
        for alias, canonical in QueryCleaner.CITY_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", lower):
                return canonical

        # Regex location extraction
        patterns = [
            r"(?:in|at|for|around)\s+([A-Za-z\s]{2,30})",
            r"(?:weather|temp|temperature)\s+([A-Za-z\s]{2,30})",
            r"([A-Za-z\s]{2,30})\s+(?:weather|temp|temperature|forecast)",
        ]
        for pat in patterns:
            m = re.search(pat, query, re.IGNORECASE)
            if m:
                extracted = m.group(1).strip()
                cleaned = re.sub(r"\b(today|now|current|tomorrow|weekly|hourly|right now)\b", "", extracted, flags=re.IGNORECASE).strip()
                if cleaned and len(cleaned) >= 2:
                    return QueryCleaner.CITY_ALIASES.get(cleaned.lower(), cleaned.title())

        return None

    async def search(self, query: str, max_results: int = 1) -> List[WebSearchResultItem]:
        if not self.is_weather_query(query):
            return []

        city = self.extract_city(query)
        if not city:
            return []

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                # 1. Geocode city name to Coordinates
                geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=5&language=en&format=json"
                geo_res = await client.get(geo_url)
                if geo_res.status_code != 200:
                    return []

                results = geo_res.json().get("results", [])
                if not results:
                    return []

                # Pick location with highest population or best match
                results.sort(key=lambda x: x.get("population") or 0, reverse=True)
                loc = results[0]
                lat, lon = loc["latitude"], loc["longitude"]
                loc_name = loc.get("name", city)
                admin1 = loc.get("admin1", "")
                country = loc.get("country", "")
                loc_label = f"{loc_name}, {admin1}, {country}".replace(", ,", ",").strip(", ")

                # 2. Query Live Meteorological Telemetry
                forecast_url = (
                    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                    "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
                    "&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
                )
                w_res = await client.get(forecast_url)
                if w_res.status_code != 200:
                    return []

                w_data = w_res.json()
                cur = w_data.get("current", {})
                daily = w_data.get("daily", {})

                temp_c = cur.get("temperature_2m")
                temp_f = round((temp_c * 9 / 5) + 32, 1) if temp_c is not None else None
                feels_c = cur.get("apparent_temperature")
                humidity = cur.get("relative_humidity_2m")
                wind_kph = cur.get("wind_speed_10m")
                w_code = cur.get("weather_code", 0)
                condition = self.WEATHER_CODES.get(w_code, "Clear / Variable")
                t_max = daily.get("temperature_2m_max", [None])[0]
                t_min = daily.get("temperature_2m_min", [None])[0]

                snippet = (
                    f"Live Weather for {loc_label}: Current Temperature: {temp_c}°C ({temp_f}°F), "
                    f"Feels like: {feels_c}°C. Condition: {condition}. Humidity: {humidity}%, Wind: {wind_kph} km/h. "
                    f"Today's High: {t_max}°C, Low: {t_min}°C."
                )

                deep_content = (
                    f"### [Verified Real-Time Meteorological Telemetry: {loc_label}]\n"
                    f"- **Current Temperature:** {temp_c}°C / {temp_f}°F\n"
                    f"- **Feels Like:** {feels_c}°C\n"
                    f"- **Weather Condition:** {condition}\n"
                    f"- **Relative Humidity:** {humidity}%\n"
                    f"- **Wind Speed:** {wind_kph} km/h\n"
                    f"- **Today High / Low:** High {t_max}°C / Low {t_min}°C\n"
                    f"- **Observation Coordinates:** {lat:.4f}°N, {lon:.4f}°E\n"
                )

                return [
                    WebSearchResultItem(
                        title=f"Live Weather & Temperature in {loc_label}",
                        url=f"https://open-meteo.com/en/docs?latitude={lat}&longitude={lon}",
                        snippet=snippet,
                        source_domain="open-meteo.com",
                        deep_content=deep_content
                    )
                ]
        except Exception as e:
            logger.debug(f"LiveWeatherProvider notice: {e}")
            return []


class LiveCurrencyExchangeProvider(BaseSearchProvider):
    """
    Zero-key, instantaneous real-time foreign exchange and cryptocurrency converter.
    Powered by open.er-api.com API.
    Provides sub-second conversion across 160+ world currencies and major crypto pairs.
    """

    CURRENCY_MAP = {
        "usd": "USD", "dollar": "USD", "dollars": "USD", "bucks": "USD", "us dollar": "USD", "us dollars": "USD",
        "inr": "INR", "rupee": "INR", "rupees": "INR", "rs": "INR", "indian rupee": "INR", "indian rupees": "INR",
        "eur": "EUR", "euro": "EUR", "euros": "EUR",
        "gbp": "GBP", "pound": "GBP", "pounds": "GBP", "sterling": "GBP", "british pound": "GBP",
        "jpy": "JPY", "yen": "JPY", "japanese yen": "JPY",
        "cad": "CAD", "canadian dollar": "CAD", "canadian dollars": "CAD",
        "aud": "AUD", "australian dollar": "AUD", "australian dollars": "AUD",
        "chf": "CHF", "swiss franc": "CHF", "franc": "CHF",
        "cny": "CNY", "yuan": "CNY", "rmb": "CNY", "chinese yuan": "CNY",
        "sgd": "SGD", "singapore dollar": "SGD",
        "aed": "AED", "dirham": "AED", "dirhams": "AED", "uae dirham": "AED",
        "sar": "SAR", "riyal": "SAR", "riyals": "SAR", "saudi riyal": "SAR",
        "kwd": "KWD", "kuwaiti dinar": "KWD", "dinar": "KWD",
        "qar": "QAR", "qatari riyal": "QAR",
        "nzd": "NZD", "new zealand dollar": "NZD",
        "krw": "KRW", "won": "KRW", "korean won": "KRW",
        "rub": "RUB", "ruble": "RUB", "rubles": "RUB",
        "brl": "BRL", "real": "BRL", "brazilian real": "BRL",
        "zar": "ZAR", "rand": "ZAR", "south african rand": "ZAR",
        "btc": "BTC", "bitcoin": "BTC",
        "eth": "ETH", "ethereum": "ETH",
        "sol": "SOL", "solana": "SOL",
    }

    def is_available(self) -> bool:
        return True

    def extract_conversion_params(self, query: str) -> Optional[Tuple[float, str, str]]:
        lower = query.lower().strip()

        # Pattern 1: e.g. '100 USD in INR', 'convert 50 euros to dollars', '2.5 btc to inr'
        p1 = re.search(
            r"(?:convert\s+)?([\d,]+(?:\.\d+)?)\s*([a-zA-Z\s]{2,20}?)\s+(?:in|to|into|equal(?:s)?(?:\s+to)?)\s+([a-zA-Z\s]{2,20})",
            lower
        )
        if p1:
            raw_amt, raw_from, raw_to = p1.group(1), p1.group(2).strip(), p1.group(3).strip()
            raw_to = re.sub(r"\b(today|now|currently|rate|conversion)\b", "", raw_to).strip()
            raw_from = re.sub(r"\b(today|now|currently)\b", "", raw_from).strip()
            
            from_code = self.CURRENCY_MAP.get(raw_from)
            to_code = self.CURRENCY_MAP.get(raw_to)
            if from_code and to_code and from_code != to_code:
                try:
                    amount = float(raw_amt.replace(",", ""))
                    return amount, from_code, to_code
                except ValueError:
                    pass

        # Pattern 2: e.g. 'USD to INR', 'EUR/USD', 'exchange rate of EUR to INR'
        p2 = re.search(r"\b([a-zA-Z]{3,15})\s*(?:to|\/|in)\s*([a-zA-Z]{3,15})\b", lower)
        if p2:
            raw_from, raw_to = p2.group(1).strip(), p2.group(2).strip()
            from_code = self.CURRENCY_MAP.get(raw_from)
            to_code = self.CURRENCY_MAP.get(raw_to)
            if from_code and to_code and from_code != to_code:
                return 1.0, from_code, to_code

        return None

    async def search(self, query: str, max_results: int = 1) -> List[WebSearchResultItem]:
        params = self.extract_conversion_params(query)
        if not params:
            return []

        amount, from_curr, to_curr = params
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"https://open.er-api.com/v6/latest/{from_curr}")
                if res.status_code != 200:
                    return []

                data = res.json()
                if data.get("result") != "success":
                    return []

                rates = data.get("rates", {})
                rate = rates.get(to_curr)
                if not rate:
                    return []

                converted = amount * rate
                time_utc = data.get("time_last_update_utc", "Live")

                snippet = (
                    f"Live Exchange Rate: {amount:,.2f} {from_curr} = {converted:,.2f} {to_curr} "
                    f"(1 {from_curr} = {rate:,.4f} {to_curr}, 1 {to_curr} = {(1/rate):,.4f} {from_curr}). "
                    f"Last updated: {time_utc}."
                )

                deep_content = (
                    f"### [Verified Real-Time Currency Exchange Telemetry]\n"
                    f"- **Conversion:** {amount:,.2f} {from_curr} = {converted:,.2f} {to_curr}\n"
                    f"- **Exchange Rate:** 1 {from_curr} = {rate:,.4f} {to_curr}\n"
                    f"- **Inverse Rate:** 1 {to_curr} = {(1/rate):,.4f} {from_curr}\n"
                    f"- **Source Base:** {from_curr} | **Target:** {to_curr}\n"
                    f"- **Observation Timestamp (UTC):** {time_utc}\n"
                )

                return [
                    WebSearchResultItem(
                        title=f"Live Currency Exchange: {amount:,.2f} {from_curr} to {to_curr}",
                        url=f"https://open.er-api.com/v6/latest/{from_curr}",
                        snippet=snippet,
                        source_domain="open.er-api.com",
                        deep_content=deep_content
                    )
                ]
        except Exception as e:
            logger.debug(f"LiveCurrencyExchangeProvider notice: {e}")
            return []


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """
    DuckDuckGo multi-strategy web search engine.
    Supports DDG HTML & Lite with query sanitization and unquoted direct URLs.
    """

    def is_available(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        results: List[WebSearchResultItem] = []
        clean_query = QueryCleaner.clean_search_query(query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Strategy 1: DDG HTML POST
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers, follow_redirects=True) as client:
                resp = await client.post("https://html.duckduckgo.com/html/", data={"q": clean_query})
                if resp.status_code == 200 and BeautifulSoup:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    result_divs = soup.find_all("div", class_="result")
                    for r in result_divs[:max_results + 2]:
                        h2 = r.find("h2", class_="result__title")
                        link = h2.find("a") if h2 else None
                        title = link.get_text(strip=True) if link else ""
                        raw_url = link["href"] if link and "href" in link.attrs else ""

                        real_url = raw_url
                        if "uddg=" in raw_url:
                            real_url = urllib.parse.unquote(raw_url.split("uddg=")[1].split("&")[0])
                        elif raw_url.startswith("//"):
                            real_url = f"https:{raw_url}"

                        domain = real_url.split("/")[2] if "//" in real_url else "web"
                        snippet_elem = r.find("a", class_="result__snippet")
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                        if snippet and real_url and real_url.startswith("http") and "duckduckgo.com" not in real_url:
                            results.append(WebSearchResultItem(
                                title=title,
                                url=real_url,
                                snippet=snippet,
                                source_domain=domain
                            ))
                            if len(results) >= max_results:
                                return results
        except Exception as e:
            logger.debug(f"DuckDuckGo HTML search notice: {e}")

        # Strategy 2: DDG Lite POST fallback
        if not results:
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

                            if title and real_url and real_url.startswith("http") and "duckduckgo.com" not in real_url:
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

        return results[:max_results]


class WikipediaSearchProvider(BaseSearchProvider):
    """
    Instant, high-authority encyclopedia & knowledge retrieval provider.
    Zero-key, 100% reliable for entities, concepts, science, math, technology, history, and culture.
    Fetches full introductory summaries and definitions in a single high-speed batch.
    """

    def is_available(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 3) -> List[WebSearchResultItem]:
        clean_q = QueryCleaner.clean_search_query(query)
        headers = {
            "User-Agent": "AetheriusAI/1.0 (https://aetherius.ai; search-agent@aetherius.ai)",
            "Accept": "application/json",
        }

        results: List[WebSearchResultItem] = []
        try:
            async with httpx.AsyncClient(timeout=3.5, headers=headers) as client:
                res = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": clean_q,
                        "format": "json",
                        "srlimit": max_results
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    search_items = data.get("query", {}).get("search", [])
                    titles = [it.get("title", "") for it in search_items if it.get("title")]

                    # Fetch page extracts in one batch for rich factual grounding
                    extracts_by_title = {}
                    if titles:
                        try:
                            ext_res = await client.get(
                                "https://en.wikipedia.org/w/api.php",
                                params={
                                    "action": "query",
                                    "prop": "extracts",
                                    "exintro": 1,
                                    "explaintext": 1,
                                    "redirects": 1,
                                    "titles": "|".join(titles),
                                    "format": "json"
                                }
                            )
                            if ext_res.status_code == 200:
                                pages = ext_res.json().get("query", {}).get("pages", {})
                                for pid, pdata in pages.items():
                                    t = pdata.get("title", "")
                                    ext = pdata.get("extract", "").strip()
                                    if t and ext:
                                        extracts_by_title[t] = ext
                        except Exception:
                            pass

                    for it in search_items:
                        title = it.get("title", "")
                        raw_snip = it.get("snippet", "")
                        clean_snip = re.sub(r"<[^>]+>", "", raw_snip).strip()
                        url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                        
                        rich_extract = extracts_by_title.get(title)
                        display_snippet = rich_extract[:300] if rich_extract else clean_snip
                        deep_content = rich_extract if rich_extract else clean_snip

                        results.append(WebSearchResultItem(
                            title=f"{title} - Wikipedia",
                            url=url,
                            snippet=display_snippet,
                            source_domain="en.wikipedia.org",
                            deep_content=deep_content
                        ))
        except Exception as e:
            logger.debug(f"Wikipedia search notice: {e}")

        return results


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
            async with httpx.AsyncClient(timeout=5.0) as client:
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
            async with httpx.AsyncClient(timeout=6.0) as client:
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
            async with httpx.AsyncClient(timeout=5.0) as client:
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


class LiveFinanceProvider(BaseSearchProvider):
    """
    Zero-key real-time stock and cryptocurrency quote provider.
    Powered by Yahoo Finance Chart API.
    """

    FINANCE_SYMBOLS = {
        "apple": "AAPL",
        "microsoft": "MSFT",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "nvidia": "NVDA",
        "tesla": "TSLA",
        "meta": "META",
        "facebook": "META",
        "bitcoin": "BTC-USD",
        "btc": "BTC-USD",
        "ethereum": "ETH-USD",
        "eth": "ETH-USD",
        "solana": "SOL-USD",
        "sol": "SOL-USD",
        "sensex": "^BSESN",
        "nifty": "^NSEI",
        "s&p 500": "^GSPC",
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "gold": "GC=F",
        "silver": "SI=F",
        "crude oil": "CL=F",
    }

    def is_available(self) -> bool:
        return True

    async def extract_symbol(self, query: str, client: httpx.AsyncClient) -> Optional[Tuple[str, str]]:
        lower = query.lower()
        # 1. Fast local dictionary lookup for instant hits
        for name, sym in self.FINANCE_SYMBOLS.items():
            if re.search(rf"\b{re.escape(name)}\b", lower):
                return name.title(), sym

        # 2. Direct ticker check (e.g. AAPL, NVDA, BTC-USD)
        m = re.search(r"\b([A-Z]{2,5}(?:-USD)?)\b", query)
        if m and m.group(1).upper() not in ["AND", "THE", "FOR", "WHAT", "WHO", "HOW", "WHY"]:
            t = m.group(1)
            return t, t

        # 3. Dynamic Global Ticker Resolution via Yahoo Finance Search API
        cleaned = re.sub(r"\b(share\s+price|stock\s+price|market\s+cap|price\s+today|shares|quote|ticker|stock|share|price|what\s+is|what\s+are|tell\s+me|show\s+me|the|of|in|for|today|current)\b", "", query, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) >= 2:
            try:
                res = await client.get(f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(cleaned)}&quotesCount=1")
                if res.status_code == 200:
                    quotes = res.json().get("quotes", [])
                    if quotes:
                        shortname = quotes[0].get("shortname") or quotes[0].get("longname") or cleaned.title()
                        symbol = quotes[0].get("symbol")
                        if symbol:
                            return shortname, symbol
            except Exception as e:
                logger.debug(f"Dynamic ticker resolution notice: {e}")

        return None

    async def search(self, query: str, max_results: int = 1) -> List[WebSearchResultItem]:
        lower = query.lower()
        if not any(k in lower for k in ["price", "stock", "shares", "crypto", "trading", "quote", "market cap", "worth", "ticker", "sensex", "nifty"]):
            return []

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                extracted = await self.extract_symbol(query, client)
                if not extracted:
                    return []

                name, symbol = extracted
                res = await client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1d")
                if res.status_code != 200:
                    # Fallback to search if direct ticker failed (e.g. TCS -> TCS.NS)
                    s_res = await client.get(f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(symbol)}&quotesCount=1")
                    if s_res.status_code == 200:
                        quotes = s_res.json().get("quotes", [])
                        if quotes and quotes[0].get("symbol"):
                            symbol = quotes[0]["symbol"]
                            name = quotes[0].get("shortname") or quotes[0].get("longname") or name
                            res = await client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=1d")
                    if res.status_code != 200:
                        return []

                chart_res = res.json().get("chart", {}).get("result", [])
                if not chart_res:
                    return []

                meta = chart_res[0].get("meta", {})
                price = meta.get("regularMarketPrice")
                currency = meta.get("currency", "USD")
                prev_close = meta.get("chartPreviousClose")
                change = round(price - prev_close, 2) if price and prev_close else 0.0
                pct_change = round((change / prev_close) * 100, 2) if prev_close else 0.0
                direction = "📈 +" if change >= 0 else "📉 "

                snippet = (
                    f"Live Market Quote for {name} ({symbol}): Current Price: {price} {currency} "
                    f"({direction}{change} / {pct_change}%). Previous Close: {prev_close} {currency}."
                )

                deep_content = (
                    f"### [Verified Real-Time Financial Quote: {name} ({symbol})]\n"
                    f"- **Company / Asset:** {name} ({symbol})\n"
                    f"- **Current Trading Price:** {price} {currency}\n"
                    f"- **Day Change:** {direction}{change} {currency} ({pct_change}%)\n"
                    f"- **Previous Market Close:** {prev_close} {currency}\n"
                    f"- **Exchange Market Timezone:** {meta.get('exchangeTimezoneName', 'UTC')}\n"
                )

                return [
                    WebSearchResultItem(
                        title=f"Live {name} ({symbol}) Stock / Asset Price Quote",
                        url=f"https://finance.yahoo.com/quote/{symbol}",
                        snippet=snippet,
                        source_domain="finance.yahoo.com",
                        deep_content=deep_content
                    )
                ]
        except Exception as e:
            logger.debug(f"LiveFinanceProvider notice: {e}")
            return []


class LiveSportsProvider(BaseSearchProvider):
    """
    Zero-key real-time sports telemetry & live match score provider.
    Powered by live news and sports feeds.
    Provides verified match scores, fixture status, and tournament standings.
    """

    SPORTS_PATTERN = re.compile(
        r"\b(?:ipl|cricket|match|matches|score|scores|scorecard|test\s+match|odi|t20|world\s+cup|premier\s+league|epl|champions\s+league|la\s+liga|serie\s+a|bundesliga|nba|nfl|formula\s+1|f1|tennis|wimbledon|who\s+won|won\s+the|game|games|versus|vs\.?|fixture|fixtures|football|soccer|badminton|hockey|isl|wpl|csk|rcb|mi|srh|kkr|dc|gt|lsg|pbks|rr)\b",
        re.IGNORECASE
    )

    def is_available(self) -> bool:
        return True

    def is_sports_query(self, query: str) -> bool:
        return bool(self.SPORTS_PATTERN.search(query))

    async def search(self, query: str, max_results: int = 4) -> List[WebSearchResultItem]:
        if not self.is_sports_query(query):
            return []

        clean_core = QueryCleaner.clean_search_query(query, strip_temporal=True)
        raw_full = QueryCleaner.clean_search_query(query, strip_temporal=False)
        target_query = f"{clean_core} match result score" if clean_core else f"{raw_full} match score"
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(target_query)}&hl=en-US&gl=US&ceid=US:en"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        }

        results: List[WebSearchResultItem] = []
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code == 200 and res.content:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(res.content)
                    channel = root.find("channel")
                    if channel is not None:
                        items = channel.findall("item")
                        for item in items[:max_results]:
                            title_elem = item.find("title")
                            link_elem = item.find("link")
                            pub_elem = item.find("pubDate")
                            desc_elem = item.find("description")
                            source_elem = item.find("source")

                            title = title_elem.text if title_elem is not None and title_elem.text else "Live Match Score"
                            link = link_elem.text if link_elem is not None and link_elem.text else ""
                            pub_date = pub_elem.text if pub_elem is not None and pub_elem.text else ""
                            source_name = source_elem.text if source_elem is not None and source_elem.text else "Live Sports"

                            desc_raw = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                            clean_desc = re.sub(r"<[^>]+>", " ", desc_raw)
                            clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                            match_summary = f"{title}. {clean_desc}" if (clean_desc and clean_desc != title) else title

                            deep_content = (
                                f"### [Live Sports Score & Match Telemetry: {title}]\n"
                                f"- **Match / Event:** {title}\n"
                                f"- **Source:** {source_name}\n"
                                f"- **Reported Time:** {pub_date}\n"
                                f"- **Match Details & Outcome:** {match_summary}\n"
                            )

                            if title and link:
                                results.append(WebSearchResultItem(
                                    title=title,
                                    url=link,
                                    snippet=f"[{source_name}] {match_summary[:250]}",
                                    source_domain="sports.google.com",
                                    deep_content=deep_content
                                ))
        except Exception as e:
            logger.debug(f"LiveSportsProvider notice: {e}")

        return results


class GoogleNewsRSSProvider(BaseSearchProvider):
    """
    Zero-key, 100% reliable real-time Google News RSS provider.
    Delivers breaking news, global current events, and live updates without captchas or IP bans.
    """

    def is_available(self) -> bool:
        return True

    def is_news_query(self, query: str) -> bool:
        lower = query.lower()
        triggers = [
            "news", "latest", "breaking", "today", "yesterday", "current", "update",
            "election", "war", "announced", "launched", "release", "president", "minister",
            "score", "match", "tournament", "championship", "stock", "market", "crisis"
        ]
        return any(t in lower for t in triggers)

    async def search(self, query: str, max_results: int = 4) -> List[WebSearchResultItem]:
        clean_q = QueryCleaner.clean_search_query(query)
        if not clean_q:
            return []

        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(clean_q)}&hl=en-US&gl=US&ceid=US:en"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        }

        results: List[WebSearchResultItem] = []
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code == 200 and res.content:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(res.content)
                    channel = root.find("channel")
                    if channel is not None:
                        items = channel.findall("item")
                        for item in items[:max_results]:
                            title_elem = item.find("title")
                            link_elem = item.find("link")
                            pub_elem = item.find("pubDate")
                            desc_elem = item.find("description")
                            source_elem = item.find("source")

                            title = title_elem.text if title_elem is not None and title_elem.text else "News Update"
                            link = link_elem.text if link_elem is not None and link_elem.text else ""
                            pub_date = pub_elem.text if pub_elem is not None and pub_elem.text else ""
                            source_name = source_elem.text if source_elem is not None and source_elem.text else "Google News"
                            
                            # Clean HTML tags out of description
                            desc_raw = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                            clean_desc = re.sub(r"<[^>]+>", " ", desc_raw)
                            clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                            if not clean_desc or clean_desc == title:
                                clean_desc = f"Reported by {source_name} on {pub_date}."

                            domain = "news.google.com"
                            if source_elem is not None and "url" in source_elem.attrib:
                                try:
                                    domain = urllib.parse.urlparse(source_elem.attrib["url"]).hostname or domain
                                except Exception:
                                    pass

                            deep_content = (
                                f"### [Breaking News Report: {title}]\n"
                                f"- **Source:** {source_name}\n"
                                f"- **Published:** {pub_date}\n"
                                f"- **Summary:** {clean_desc}\n"
                            )

                            if title and link:
                                results.append(WebSearchResultItem(
                                    title=title,
                                    url=link,
                                    snippet=f"[{source_name}] {clean_desc}",
                                    source_domain=domain,
                                    deep_content=deep_content
                                ))
        except Exception as e:
            logger.debug(f"GoogleNewsRSSProvider notice: {e}")

        return results


class RedditSearchProvider(BaseSearchProvider):
    """
    Zero-key Reddit Community Intelligence and Discussion Search Provider.
    Extracts real-time community experiences, developer solutions, benchmark reviews, and unfiltered feedback.
    """

    def is_available(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 3) -> List[WebSearchResultItem]:
        clean_q = QueryCleaner.clean_search_query(query)
        if not clean_q:
            return []

        url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(clean_q)}&limit={max_results}&sort=relevance"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

        results: List[WebSearchResultItem] = []
        try:
            async with httpx.AsyncClient(timeout=4.0, headers=headers, follow_redirects=True) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    children = data.get("data", {}).get("children", [])
                    for post_wrapper in children[:max_results]:
                        post = post_wrapper.get("data", {})
                        title = post.get("title", "")
                        selftext = post.get("selftext", "").strip()
                        subreddit = post.get("subreddit_name_prefixed", "r/reddit")
                        score = post.get("score", 0)
                        num_comments = post.get("num_comments", 0)
                        permalink = post.get("permalink", "")
                        post_url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")

                        preview_snippet = selftext[:250].replace("\n", " ") if selftext else f"Community discussion with {num_comments} comments."
                        snippet = f"[{subreddit} | {score} upvotes | {num_comments} comments] {preview_snippet}"

                        deep_content = (
                            f"### [Reddit Community Discussion: {title}]\n"
                            f"- **Subreddit:** {subreddit}\n"
                            f"- **Upvotes:** {score} | **Comments:** {num_comments}\n"
                            f"- **Discussion Post:** {selftext[:800]}\n"
                        )

                        if title and post_url:
                            results.append(WebSearchResultItem(
                                title=f"{title} ({subreddit})",
                                url=post_url,
                                snippet=snippet,
                                source_domain="reddit.com",
                                deep_content=deep_content
                            ))
        except Exception as e:
            logger.debug(f"RedditSearchProvider notice: {e}")

        return results


class MultiProviderSearchOrchestrator:
    """
    Tiered Failover Multi-Provider Search Orchestrator.
    Combines live currency conversions, meteorological weather telemetry, real-time financial quotes,
    live sports match scores, Google News RSS feeds, Reddit community intelligence, zero-key DuckDuckGo web search,
    authoritative Wikipedia knowledge, and multi-hop query decomposition.
    """

    def __init__(self):
        self.currency = LiveCurrencyExchangeProvider()
        self.weather = LiveWeatherProvider()
        self.finance = LiveFinanceProvider()
        self.sports = LiveSportsProvider()
        self.google_news = GoogleNewsRSSProvider()
        self.reddit = RedditSearchProvider()
        self.duckduckgo = DuckDuckGoSearchProvider()
        self.wikipedia = WikipediaSearchProvider()
        self.tavily = TavilySearchProvider()
        self.serper = SerperSearchProvider()
        self.brave = BraveSearchProvider()

    async def _execute_atomic_search(self, clean_query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        """Executes a single-query multi-angle retrieval across all active search providers."""
        results_by_url: Dict[str, WebSearchResultItem] = {}

        # 1. Specialized Live Currency Converter
        try:
            curr_results = await self.currency.search(clean_query)
            for c in curr_results:
                results_by_url[c.url] = c
        except Exception as e:
            logger.debug(f"Live currency lookup notice: {e}")

        # 2. Specialized Live Weather Telemetry Check
        if self.weather.is_weather_query(clean_query):
            try:
                weather_results = await self.weather.search(clean_query)
                for w in weather_results:
                    results_by_url[w.url] = w
            except Exception as e:
                logger.debug(f"Live weather lookup notice: {e}")

        # 3. Specialized Live Financial Market Check
        try:
            fin_results = await self.finance.search(clean_query)
            for f in fin_results:
                results_by_url[f.url] = f
        except Exception as e:
            logger.debug(f"Live finance lookup notice: {e}")

        # 4. Specialized Live Sports Score Check
        is_sports = self.sports.is_sports_query(clean_query)
        if is_sports:
            try:
                sports_results = await self.sports.search(clean_query, max_results=max_results)
                for s in sports_results:
                    results_by_url[s.url] = s
            except Exception as e:
                logger.debug(f"Live sports lookup notice: {e}")

        # 5. Paid Search APIs (Tavily, Serper, Brave) if configured
        for paid_provider in [self.tavily, self.serper, self.brave]:
            if paid_provider.is_available():
                try:
                    paid_res = await paid_provider.search(clean_query, max_results=max_results)
                    for item in paid_res:
                        if item.url not in results_by_url:
                            results_by_url[item.url] = item
                    if len(results_by_url) >= max_results:
                        return list(results_by_url.values())[:max_results]
                except Exception as e:
                    logger.debug(f"Paid search provider notice: {e}")

        # 6. Multi-Engine Parallel Python In-Process Fetcher with Multi-Angle Queries
        synth = MultiAngleQuerySynthesizer.synthesize_queries(clean_query)
        primary_q = synth.get("primary", clean_query)
        wiki_q = synth.get("wiki_list", primary_q)
        wiki_entity_q = synth.get("wiki_entity", primary_q)
        temporal_q = synth.get("temporal", primary_q)

        async def run_ddg():
            try:
                return await self.duckduckgo.search(primary_q, max_results=max_results)
            except Exception as e:
                logger.debug(f"DDG Search error: {e}")
                return []

        async def run_wiki():
            # Skip Wikipedia for live match scores since Wikipedia does not track yesterday's scorecards
            if is_sports:
                return []
            try:
                if wiki_q != wiki_entity_q:
                    res_list, res_entity = await asyncio.gather(
                        self.wikipedia.search(wiki_q, max_results=2),
                        self.wikipedia.search(wiki_entity_q, max_results=2)
                    )
                    combined_w = []
                    seen_urls = set()
                    for r in (res_list or []) + (res_entity or []):
                        if r.url not in seen_urls:
                            seen_urls.add(r.url)
                            combined_w.append(r)
                    return combined_w[:3]
                else:
                    return await self.wikipedia.search(wiki_q, max_results=3)
            except Exception as e:
                logger.debug(f"Wikipedia search error: {e}")
                return []

        async def run_news():
            try:
                target_q = temporal_q if self.google_news.is_news_query(clean_query) else primary_q
                return await self.google_news.search(target_q, max_results=4)
            except Exception as e:
                logger.debug(f"Google News RSS error: {e}")
                return []

        async def run_reddit():
            try:
                return await self.reddit.search(primary_q, max_results=2)
            except Exception as e:
                logger.debug(f"Reddit search error: {e}")
                return []

        ddg_res, wiki_res, news_res, reddit_res = await asyncio.gather(
            run_ddg(), run_wiki(), run_news(), run_reddit()
        )

        is_news = self.google_news.is_news_query(clean_query)
        if (is_news or is_sports) and news_res:
            for item in news_res:
                if item.url and item.url not in results_by_url:
                    results_by_url[item.url] = item

        for item in (wiki_res or []):
            if item.url and item.url not in results_by_url:
                results_by_url[item.url] = item

        for item in (ddg_res or []):
            if item.url and item.url not in results_by_url:
                results_by_url[item.url] = item

        for item in (news_res or []):
            if item.url and item.url not in results_by_url:
                results_by_url[item.url] = item

        for item in (reddit_res or []):
            if item.url and item.url not in results_by_url:
                results_by_url[item.url] = item

        return list(results_by_url.values())[:max_results]

    async def execute_search(self, query: str, max_results: int = 5) -> List[WebSearchResultItem]:
        clean_query = query.strip()
        if not clean_query:
            return []

        # Multi-Hop Query Decomposition Check (e.g. 'Compare GDP and PM of India and Japan')
        decomposed_subqueries = MultiAngleQuerySynthesizer.decompose_multi_hop(clean_query)
        if len(decomposed_subqueries) >= 2:
            logger.info(f"Executing Multi-Hop parallel decomposed searches for: {decomposed_subqueries}")
            sub_tasks = [self._execute_atomic_search(sub_q, max_results=3) for sub_q in decomposed_subqueries]
            sub_results_lists = await asyncio.gather(*sub_tasks, return_exceptions=True)
            
            merged_results: List[WebSearchResultItem] = []
            seen_urls = set()
            
            # Interleave results from each decomposed entity sub-query
            max_len = max((len(res) for res in sub_results_lists if isinstance(res, list)), default=0)
            for i in range(max_len):
                for res_list in sub_results_lists:
                    if isinstance(res_list, list) and i < len(res_list):
                        item = res_list[i]
                        if item.url not in seen_urls:
                            seen_urls.add(item.url)
                            merged_results.append(item)

            if merged_results:
                return merged_results[:max_results + 2]

        return await self._execute_atomic_search(clean_query, max_results=max_results)

