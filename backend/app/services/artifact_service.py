import os
import uuid
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.core.logging import logger
from backend.app.services.storage_service import storage
from backend.app.services.generators import (
    DocumentSpec,
    DocumentSynthesizer,
    DocumentArchetype,
    PDFGenerator,
    DocxGenerator,
    ExcelGenerator,
)


class GeneratedArtifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_type: str  # "pdf", "docx", "xlsx", "png", "svg"
    mime_type: str
    file_size_bytes: int
    title: str
    archetype: str
    download_url: str
    preview_url: Optional[str] = None
    file_path: str


class ArtifactService:
    """
    Coordinates multi-format artifact creation (PDF, DOCX, XLSX),
    local disk persistence, metadata management, and delivery to chat UI.
    """

    _registry: Dict[str, GeneratedArtifact] = {}

    @classmethod
    def is_document_intent(cls, query: str, assistant_response: str = "") -> bool:
        """
        Detects if query or assistant response warrants automatic artifact generation
        (explicit document request, resume, attendance, invoice, PRD, formal letter, or large table).
        """
        combined = f"{query} {assistant_response[:300]}".lower()

        # Direct document triggers
        if any(k in combined for k in [
            "generate pdf", "make a pdf", "download pdf", "export pdf", "create a pdf",
            "generate docx", "make a word doc", "export docx", "generate excel", "make a spreadsheet",
            "resume", "curriculum vitae", " cv ",
            "attendance sheet", "attendance register", "attendance report",
            "invoice", "quotation", "receipt", "bill to",
            "prd", "product requirement", "project specification",
            "formal letter", "appointment letter", "resignation letter",
            "minutes of meeting", "mom report"
        ]):
            return True

        # Has Markdown table with > 3 rows
        if assistant_response and assistant_response.count("|") >= 12 and "---" in assistant_response:
            return True

        return False

    @classmethod
    def is_refusal_or_sparse(cls, text: str) -> bool:
        """
        Detects if the text is an AI refusal to create documents or too sparse to compile a standalone document.
        """
        t = (text or "").lower()
        refusal_triggers = [
            "can't assist with creating",
            "cannot assist with creating",
            "can't create or print",
            "cannot create or print",
            "cannot generate pdf",
            "can't generate pdf",
            "unable to create pdf",
            "unable to generate pdf",
            "cannot create file",
            "can't create file",
            "don't have the ability to create",
            "i cannot directly generate",
            "i am unable to create",
            "as an ai, i cannot",
        ]
        if any(r in t for r in refusal_triggers):
            return True
        return len(t.strip()) < 80

    @classmethod
    def compile_document(
        cls,
        text_content: str,
        user_query: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        preferred_format: Optional[str] = None,
        custom_title: Optional[str] = None
    ) -> List[GeneratedArtifact]:
        """
        Synthesizes a DocumentSpec and compiles the corresponding PDF, DOCX, and/or XLSX artifacts.
        Supports multi-turn context recovery if the current assistant turn is a refusal or brief acknowledgment.
        """
        target_text = text_content

        # If current turn text is a refusal or sparse, recover from chat history
        if cls.is_refusal_or_sparse(target_text) and chat_history:
            for turn in reversed(chat_history):
                if turn.get("role") == "assistant" and len(turn.get("content", "").strip()) > 80:
                    if not cls.is_refusal_or_sparse(turn["content"]):
                        target_text = turn["content"]
                        break

        # If still empty or refusal, fallback to user query or minimal text
        if not target_text or cls.is_refusal_or_sparse(target_text):
            if user_query and len(user_query.strip()) > 10:
                target_text = f"# Document\n\nGenerated for: {user_query}\n\n"
            else:
                target_text = text_content

        spec = DocumentSynthesizer.synthesize_from_text(
            text=target_text,
            user_query=user_query,
            forced_title=custom_title
        )

        artifacts: List[GeneratedArtifact] = []
        safe_base = re.sub(r"[^\w\-]", "_", spec.title).strip("_") or "Document"

        q_lower = (user_query or "").lower()
        
        # Determine target formats
        formats_to_build = []
        if preferred_format:
            formats_to_build.append(preferred_format.lower())
        else:
            if "excel" in q_lower or "spreadsheet" in q_lower or "xlsx" in q_lower or "csv" in q_lower:
                formats_to_build.append("xlsx")
            elif "docx" in q_lower or "word" in q_lower or "doc" in q_lower:
                formats_to_build.append("docx")
            elif spec.archetype in [DocumentArchetype.ATTENDANCE, DocumentArchetype.SPREADSHEET]:
                formats_to_build.extend(["pdf", "xlsx"])
            else:
                formats_to_build.append("pdf")

        # 1. Compile PDF
        if "pdf" in formats_to_build or not formats_to_build:
            try:
                pdf_bytes = PDFGenerator.generate_pdf_bytes(spec)
                pdf_filename = f"{safe_base}.pdf"
                saved_path = storage.save_file(pdf_bytes, pdf_filename, subfolder="artifacts")
                
                art_id = str(uuid.uuid4())
                artifact = GeneratedArtifact(
                    artifact_id=art_id,
                    filename=pdf_filename,
                    file_type="pdf",
                    mime_type="application/pdf",
                    file_size_bytes=len(pdf_bytes),
                    title=spec.title,
                    archetype=spec.archetype.value,
                    download_url=f"/api/v1/artifacts/{art_id}/download",
                    preview_url=f"/api/v1/artifacts/{art_id}/preview",
                    file_path=saved_path
                )
                cls._registry[art_id] = artifact
                artifacts.append(artifact)
            except Exception as e:
                logger.error(f"Failed to generate PDF artifact: {e}")

        # 2. Compile DOCX
        if "docx" in formats_to_build:
            try:
                docx_bytes = DocxGenerator.generate_docx_bytes(spec)
                docx_filename = f"{safe_base}.docx"
                saved_path = storage.save_file(docx_bytes, docx_filename, subfolder="artifacts")
                
                art_id = str(uuid.uuid4())
                artifact = GeneratedArtifact(
                    artifact_id=art_id,
                    filename=docx_filename,
                    file_type="docx",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    file_size_bytes=len(docx_bytes),
                    title=spec.title,
                    archetype=spec.archetype.value,
                    download_url=f"/api/v1/artifacts/{art_id}/download",
                    file_path=saved_path
                )
                cls._registry[art_id] = artifact
                artifacts.append(artifact)
            except Exception as e:
                logger.error(f"Failed to generate DOCX artifact: {e}")

        # 3. Compile XLSX
        if "xlsx" in formats_to_build:
            try:
                xlsx_bytes = ExcelGenerator.generate_excel_bytes(spec)
                xlsx_filename = f"{safe_base}.xlsx"
                saved_path = storage.save_file(xlsx_bytes, xlsx_filename, subfolder="artifacts")
                
                art_id = str(uuid.uuid4())
                artifact = GeneratedArtifact(
                    artifact_id=art_id,
                    filename=xlsx_filename,
                    file_type="xlsx",
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    file_size_bytes=len(xlsx_bytes),
                    title=spec.title,
                    archetype=spec.archetype.value,
                    download_url=f"/api/v1/artifacts/{art_id}/download",
                    file_path=saved_path
                )
                cls._registry[art_id] = artifact
                artifacts.append(artifact)
            except Exception as e:
                logger.error(f"Failed to generate XLSX artifact: {e}")

        return artifacts

    @classmethod
    def get_artifact(cls, artifact_id: str) -> Optional[GeneratedArtifact]:
        return cls._registry.get(artifact_id)
