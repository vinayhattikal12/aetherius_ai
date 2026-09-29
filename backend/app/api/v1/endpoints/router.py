from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.schemas.router import RouterEvaluationRequest, RouterEvaluationResponse
from backend.app.services.router_service import ModelRouter

router = APIRouter()


@router.post("/evaluate", response_model=RouterEvaluationResponse)
async def evaluate_routing(
    request: RouterEvaluationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Evaluate optimal model, execution tier, and privacy compliance for a user request."""
    return await ModelRouter.evaluate_routing(db=db, request=request)
