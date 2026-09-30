import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.app.schemas.chat import ChatCompletionRequest
from backend.app.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_streaming_sse_sequence():
    # Mock database session
    mock_db = AsyncMock()
    
    mock_exec_result = MagicMock()
    mock_exec_result.scalars.return_value.first.return_value = None
    mock_exec_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_exec_result)

    # Mock ModelManager stream_response
    async def mock_stream_tokens(*args, **kwargs):
        tokens = ["Hello", " world", "!"]
        for t in tokens:
            yield t

    with patch("backend.app.services.chat_service.model_manager.stream_response", side_effect=mock_stream_tokens):
        with patch("backend.app.services.chat_service.model_manager.ollama.get_model_info_async", return_value={"stable_num_ctx": 8192}):
            req = ChatCompletionRequest(
                message="Hello Aetherius",
                model_name="llama3.2:3b",
                workspace_slug="general",
                enable_web_search=False
            )
            
            events = []
            async for chunk in ChatService.stream_chat_completion(mock_db, req):
                if chunk.startswith("data: "):
                    data_str = chunk.replace("data: ", "").strip()
                    if data_str:
                        events.append(json.loads(data_str))

            assert len(events) >= 5
            # Event 0: init
            assert events[0]["type"] == "init"
            assert "conversation_id" in events[0]

            # Events 1..3: token
            token_events = [e for e in events if e["type"] == "token"]
            assert len(token_events) == 3
            assert "".join(e["token"] for e in token_events) == "Hello world!"

            # Last Event: done
            assert events[-1]["type"] == "done"
            assert "Hello world!" in events[-1]["content"]
