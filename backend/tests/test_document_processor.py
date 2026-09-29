import pytest
from backend.app.services.document_processor import DocumentProcessor


def test_extract_text_plain():
    content = b"Hello Aetherius AI. This is a plain text test document."
    text, meta = DocumentProcessor.extract_text(content, "txt")
    assert "Hello Aetherius AI" in text
    assert meta["format"] == "txt"


def test_chunk_text_boundaries():
    long_text = "\n\n".join([f"Paragraph {i}: " + ("word " * 50) for i in range(10)])
    chunks = DocumentProcessor.chunk_text(long_text, chunk_size=300, chunk_overlap=50)
    
    assert len(chunks) > 1
    assert all("chunk_index" in c for c in chunks)
    assert all("content" in c for c in chunks)
    assert chunks[0]["chunk_index"] == 0
    assert chunks[1]["chunk_index"] == 1
