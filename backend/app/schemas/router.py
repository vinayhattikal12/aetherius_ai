from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class RouterEvaluationRequest(BaseModel):
    prompt: str
    workspace_slug: str = "general"
    privacy_mode: str = "HYBRID"  # LOCAL_ONLY, HYBRID, CLOUD
    requires_coding: Optional[bool] = None
    requires_vision: Optional[bool] = None
    requires_reasoning: Optional[bool] = None
    requires_tools: Optional[bool] = None
    requires_rag: Optional[bool] = None
    explicit_model_id: Optional[str] = None


class RouterEvaluationResponse(BaseModel):
    selected_model_id: str
    selected_model_name: str
    execution_mode: str  # local, cloud, hybrid
    privacy_compliant: bool
    confidence_score: float
    routing_reason: str
    complexity_score: float  # 0.0 to 1.0
    detected_intent: str
    fallback_model_id: Optional[str] = None
