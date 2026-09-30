import pytest
from backend.app.services.diagnostics_service import DiagnosticsService, RequestTimingRecord, time_stage


def test_time_stage_context_manager():
    stages = {}
    with time_stage(stages, "router"):
        import time
        time.sleep(0.01)

    assert "router" in stages
    assert stages["router"] >= 8.0  # at least ~10ms


def test_diagnostics_service_ring_buffer():
    DiagnosticsService.clear()
    for i in range(25):
        DiagnosticsService.record_request(
            RequestTimingRecord(
                request_id=f"req-{i}",
                model="llama3.2:3b",
                num_ctx=4096,
                stages_ms={"query_analysis": 1.5, "router": 2.0},
                prompt_tokens=100 + i,
                gen_tokens=50 + i,
                tok_s=12.5,
                load_s=0.01,
                total_duration_ms=150.0
            )
        )

    records = DiagnosticsService.get_last_requests(limit=10)
    assert len(records) == 10
    # Most recent first
    assert records[0]["request_id"] == "req-24"
    assert records[0]["model"] == "llama3.2:3b"
    assert records[0]["num_ctx"] == 4096
    assert records[0]["stages_ms"]["router"] == 2.0
