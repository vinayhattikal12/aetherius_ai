from fastapi import APIRouter
from backend.app.schemas.web_search import WebSearchRequest, WebSearchResponse
from backend.app.services.web_search_service import WebSearchService

router = APIRouter()


@router.post("/", response_model=WebSearchResponse)
async def perform_web_search(request: WebSearchRequest):
    """Perform real-time web search and return structured snippets and citations."""
    return await WebSearchService.search(request.query, max_results=request.max_results)
