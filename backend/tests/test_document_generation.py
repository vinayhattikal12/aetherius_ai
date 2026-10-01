import pytest
import os
from httpx import AsyncClient
from backend.app.services.generators import (
    DocumentSynthesizer,
    DocumentArchetype,
    PDFGenerator,
    DocxGenerator,
    ExcelGenerator,
)
from backend.app.services.artifact_service import ArtifactService


def test_document_synthesizer_archetype_detection():
    # 1. Resume detection
    q_resume = "Draft a resume for a senior full-stack engineer"
    spec_resume = DocumentSynthesizer.synthesize_from_text(
        text="# Alex Mercer\n## Experience\n- Lead Developer at TechCorp\n## Education\n- B.S. in Computer Science",
        user_query=q_resume
    )
    assert spec_resume.archetype == DocumentArchetype.RESUME
    assert spec_resume.title == "Alex Mercer"
    assert len(spec_resume.sections) >= 2

    # 2. Attendance sheet detection
    q_att = "Make an attendance sheet for 20 students"
    text_att = """# Physics 101 Attendance Register
| Roll No | Student Name | Mon | Tue | Wed | Thu | Fri |
|---|---|---|---|---|---|---|
| 101 | Aarav Sharma | P | P | P | A | P |
| 102 | Priya Patel | P | P | P | P | P |
| 103 | Rahul Verma | A | P | P | P | P |
"""
    spec_att = DocumentSynthesizer.synthesize_from_text(text=text_att, user_query=q_att)
    assert spec_att.archetype == DocumentArchetype.ATTENDANCE
    assert spec_att.sections[0].table is not None
    assert len(spec_att.sections[0].table.headers) == 7
    assert len(spec_att.sections[0].table.rows) == 3

    # 3. Invoice detection
    q_inv = "Create an invoice for web development services"
    text_inv = """# Tax Invoice #INV-2026-001
## Bill To
Acme Corporation, New York

## Items
| Description | Qty | Unit Price | Total |
|---|---|---|---|
| Frontend Development | 40 | $100 | $4,000 |
| Backend API Design | 30 | $120 | $3,600 |
"""
    spec_inv = DocumentSynthesizer.synthesize_from_text(text=text_inv, user_query=q_inv)
    assert spec_inv.archetype == DocumentArchetype.INVOICE


def test_pdf_compilation():
    sample_text = """# Executive Strategic Report
## Executive Summary
This document provides quarterly strategic performance indicators and operational milestones.

## Performance Metrics
- **Revenue Growth**: +34% YoY
- **Customer Acquisition**: 12,400 new accounts
- **Uptime Reliability**: 99.98%

## Department Breakdown
| Department | Budget | Headcount | Status |
|---|---|---|---|
| Engineering | $1.2M | 45 | On Track |
| Product | $450K | 12 | Completed |
| Operations | $600K | 18 | On Track |
"""
    spec = DocumentSynthesizer.synthesize_from_text(sample_text, user_query="Generate quarterly executive report")
    pdf_bytes = PDFGenerator.generate_pdf_bytes(spec)

    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_docx_compilation():
    sample_text = """# Senior Flutter Developer Resume
## Professional Summary
Passionate mobile architect with 5+ years of experience in cross-platform Dart and Flutter.

## Technical Skills
- **Languages**: Dart, Kotlin, Swift, Python
- **Frameworks**: Flutter, Bloc, Riverpod, Firebase

## Experience
| Company | Role | Duration |
|---|---|---|
| Apex Labs | Lead Mobile Architect | 2023 - Present |
| ByteWave | Senior Flutter Engineer | 2021 - 2023 |
"""
    spec = DocumentSynthesizer.synthesize_from_text(sample_text, user_query="Create Flutter resume")
    docx_bytes = DocxGenerator.generate_docx_bytes(spec)

    assert len(docx_bytes) > 2000
    assert docx_bytes.startswith(b"PK")  # ZIP header for docx


def test_excel_compilation():
    sample_text = """# Student Attendance Sheet
| Roll No | Name | Present Days | Absent Days | Attendance % |
|---|---|---|---|---|
| 1 | Aarav Kumar | 24 | 1 | 96.0 |
| 2 | Neha Singh | 22 | 3 | 88.0 |
| 3 | Rohan Gupta | 25 | 0 | 100.0 |
"""
    spec = DocumentSynthesizer.synthesize_from_text(sample_text, user_query="Make attendance spreadsheet")
    xlsx_bytes = ExcelGenerator.generate_excel_bytes(spec)

    assert len(xlsx_bytes) > 2000
    assert xlsx_bytes.startswith(b"PK")  # ZIP header for xlsx


def test_artifact_service_end_to_end():
    sample_text = """# Class Attendance Register
| ID | Student | Status |
|---|---|---|
| 1 | Alice | Present |
| 2 | Bob | Present |
"""
    artifacts = ArtifactService.compile_document(
        text_content=sample_text,
        user_query="make an attendance register sheet"
    )

    assert len(artifacts) >= 2  # PDF + XLSX for attendance
    pdf_art = next((a for a in artifacts if a.file_type == "pdf"), None)
    xlsx_art = next((a for a in artifacts if a.file_type == "xlsx"), None)

    assert pdf_art is not None
    assert xlsx_art is not None
    assert os.path.exists(pdf_art.file_path)
    assert os.path.exists(xlsx_art.file_path)
    assert pdf_art.file_size_bytes > 0
    assert xlsx_art.file_size_bytes > 0


@pytest.mark.asyncio
async def test_artifacts_api_endpoints(async_client: AsyncClient):
    # Compile a test artifact
    sample_text = "# Project Requirements Document\n## Overview\nPRD for medical appointment booking."
    artifacts = ArtifactService.compile_document(sample_text, user_query="Create a PRD document")
    assert len(artifacts) > 0

    art = artifacts[0]

    # 1. Metadata endpoint
    meta_res = await async_client.get(f"/api/v1/artifacts/{art.artifact_id}/metadata")
    assert meta_res.status_code == 200
    meta_data = meta_res.json()
    assert meta_data["filename"] == art.filename
    assert meta_data["file_type"] == art.file_type

    # 2. Download endpoint
    dl_res = await async_client.get(f"/api/v1/artifacts/{art.artifact_id}/download")
    assert dl_res.status_code == 200
    assert len(dl_res.content) == art.file_size_bytes
    assert "attachment" in dl_res.headers.get("content-disposition", "")

    # 3. Preview endpoint
    prev_res = await async_client.get(f"/api/v1/artifacts/{art.artifact_id}/preview")
    assert prev_res.status_code == 200
    assert "inline" in prev_res.headers.get("content-disposition", "")


def test_multi_turn_refusal_recovery():
    # Simulate turn 1: User requested resume, assistant produced resume
    history = [
        {"role": "user", "content": "Create a resume template for a data scientist"},
        {
            "role": "assistant",
            "content": "# Sarah Jenkins - Senior Data Scientist\n## Summary\nExpert in NLP and predictive modeling.\n## Skills\n- Python, PyTorch, SQL\n## Experience\n- Lead Data Scientist at AI Corp (2020-Present)\n## Education\n- M.S. Data Science, Stanford",
        }
    ]

    # Turn 2: User says "create a pdf of it", assistant outputs canned refusal
    canned_refusal = "I'm sorry, but I can't assist with creating or printing PDFs directly. However, you can copy the text into a document editor."
    
    assert ArtifactService.is_refusal_or_sparse(canned_refusal) is True

    # ArtifactService should successfully recover the document from the history!
    artifacts = ArtifactService.compile_document(
        text_content=canned_refusal,
        user_query="create a pdf of it",
        chat_history=history
    )

    assert len(artifacts) >= 1
    pdf_art = artifacts[0]
    assert pdf_art.file_type == "pdf"
    assert "Sarah_Jenkins" in pdf_art.filename
    assert os.path.exists(pdf_art.file_path)
    assert pdf_art.file_size_bytes > 1000

