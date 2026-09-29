from typing import List, Optional
from pydantic import BaseModel, Field


class WebSearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str
    source_domain: Optional[str] = None
    deep_content: Optional[str] = None


class WebSearchRequest(BaseModel):
    query: str
    max_results: int = 5


class WebSearchResponse(BaseModel):
    query: str
    results: List[WebSearchResultItem] = Field(default_factory=list)
    summary: str = ""
    status: str = "success"
