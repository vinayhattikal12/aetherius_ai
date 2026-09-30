import pytest
import sys


def test_import_backend_main_integrity():
    """Verify backend.app.main imports cleanly on any Python 3.11+ without NameError."""
    import backend.app.main
    assert backend.app.main.app is not None


def test_memory_service_annotations():
    """Verify MemoryService and MemoryUpdate annotations evaluate without NameError."""
    from backend.app.services.memory_service import MemoryService
    from backend.app.schemas.memory import MemoryUpdate
    assert "data" in MemoryService.update_memory.__annotations__
    assert MemoryService.update_memory.__annotations__["data"] is MemoryUpdate
