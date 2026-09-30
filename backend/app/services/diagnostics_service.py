import time
from collections import deque
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.app.core.logging import logger


class RequestTimingRecord(BaseModel):
    request_id: str
    timestamp: float = Field(default_factory=time.time)
    model: str = "unknown"
    num_ctx: int = 2048
    stages_ms: Dict[str, float] = Field(default_factory=dict)
    prompt_tokens: Optional[int] = None
    gen_tokens: Optional[int] = None
    tok_s: Optional[float] = None
    load_s: Optional[float] = None
    first_token_ms: Optional[float] = None
    total_duration_ms: float = 0.0


class DiagnosticsService:
    """
    In-memory ring buffer tracking request latency, token throughput,
    and stage-by-stage timings for all conversational inference requests.
    """
    _records: deque = deque(maxlen=50)

    @classmethod
    def record_request(cls, record: RequestTimingRecord) -> None:
        cls._records.appendleft(record)
        stages_summary = ", ".join(f"{k}: {v:.1f}ms" for k, v in record.stages_ms.items())
        logger.info(
            f"[perf] request_id={record.request_id} model={record.model} num_ctx={record.num_ctx} "
            f"prompt_tokens={record.prompt_tokens} gen_tokens={record.gen_tokens} "
            f"tok/s={record.tok_s or 0.0:.1f} load_s={record.load_s or 0.0:.2f}s "
            f"first_token_ms={record.first_token_ms or 0.0:.1f}ms total_ms={record.total_duration_ms:.1f}ms | stages=[{stages_summary}]"
        )

    @classmethod
    def get_last_requests(cls, limit: int = 20) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(limit, 50))
        items = list(cls._records)[:safe_limit]
        return [item.model_dump() for item in items]

    @classmethod
    def clear(cls) -> None:
        cls._records.clear()


@contextmanager
def time_stage(stage_dict: Dict[str, float], stage_name: str):
    """Context manager helper to time an individual pipeline stage in milliseconds."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        stage_dict[stage_name] = round(elapsed_ms, 2)
