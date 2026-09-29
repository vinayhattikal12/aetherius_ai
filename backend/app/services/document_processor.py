import os
import io
import csv
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader
from docx import Document as DocxDocument
from backend.app.core.logging import logger


class DocumentProcessor:
    """Extracts text from various file formats and chunks it for pgvector RAG."""

    @classmethod
    def extract_text(cls, file_bytes: bytes, file_type: str) -> Tuple[str, Dict[str, Any]]:
        file_type = file_type.lower().replace(".", "")
        metadata: Dict[str, Any] = {"format": file_type}

        try:
            if file_type == "pdf":
                reader = PdfReader(io.BytesIO(file_bytes))
                num_pages = len(reader.pages)
                metadata["pages"] = num_pages
                text_parts = []
                for idx, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    text_parts.append(f"--- Page {idx + 1} ---\n{page_text}")
                return "\n\n".join(text_parts), metadata

            elif file_type in ["docx", "doc"]:
                doc = DocxDocument(io.BytesIO(file_bytes))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                metadata["paragraphs"] = len(paragraphs)
                return "\n\n".join(paragraphs), metadata

            elif file_type in ["csv"]:
                stream = io.StringIO(file_bytes.decode("utf-8", errors="ignore"))
                reader = csv.reader(stream)
                rows = list(reader)
                metadata["rows"] = len(rows)
                formatted_rows = [", ".join(row) for row in rows if row]
                return "\n".join(formatted_rows), metadata

            elif file_type in ["txt", "md", "markdown", "json", "py", "ts", "tsx", "js"]:
                text = file_bytes.decode("utf-8", errors="ignore")
                return text, metadata

            else:
                text = file_bytes.decode("utf-8", errors="ignore")
                return text, metadata

        except Exception as e:
            logger.error(f"Error parsing {file_type} document: {e}")
            raise

    @classmethod
    def chunk_text(
        cls,
        text: str,
        chunk_size: int = 800,
        chunk_overlap: int = 120
    ) -> List[Dict[str, Any]]:
        """
        Recursive character chunker respecting paragraph boundaries where possible.
        """
        if not text or not text.strip():
            return []

        paragraphs = text.split("\n\n")
        chunks: List[Dict[str, Any]] = []
        current_chunk = ""
        chunk_idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph exceeds chunk size, save current and start new with overlap
            if len(current_chunk) + len(para) > chunk_size:
                if current_chunk:
                    chunks.append({
                        "chunk_index": chunk_idx,
                        "content": current_chunk.strip(),
                        "char_length": len(current_chunk),
                    })
                    chunk_idx += 1
                    # Retain trailing overlap
                    overlap_start = max(0, len(current_chunk) - chunk_overlap)
                    current_chunk = current_chunk[overlap_start:] + "\n" + para
                else:
                    # Single paragraph exceeds chunk size -> split into slices
                    for i in range(0, len(para), chunk_size - chunk_overlap):
                        slice_text = para[i : i + chunk_size]
                        chunks.append({
                            "chunk_index": chunk_idx,
                            "content": slice_text.strip(),
                            "char_length": len(slice_text),
                        })
                        chunk_idx += 1
                    current_chunk = ""
            else:
                current_chunk = (current_chunk + "\n\n" + para).strip()

        if current_chunk.strip():
            chunks.append({
                "chunk_index": chunk_idx,
                "content": current_chunk.strip(),
                "char_length": len(current_chunk),
            })

        return chunks
