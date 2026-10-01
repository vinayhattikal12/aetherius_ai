import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.app.services.generators.document_models import (
    DocumentSpec,
    DocumentSection,
    DocumentArchetype,
    TableData,
    CalloutBlock,
)


class DocumentSynthesizer:
    """
    Parses unstructured text, Markdown, or raw LLM output into a strongly-typed DocumentSpec.
    Determines visual archetype, extracts tabular data, callouts, and metric key-values.
    """

    @classmethod
    def detect_archetype(cls, query: str, content: str = "") -> DocumentArchetype:
        combined = f"{query} {content[:500]}".lower()

        if any(k in combined for k in ["resume", "curriculum vitae", " cv ", "work experience", "education background", "skills & abilities"]):
            return DocumentArchetype.RESUME
        if any(k in combined for k in ["invoice", "quotation", "receipt", "bill to", "payment terms", "due date", "subtotal"]):
            return DocumentArchetype.INVOICE
        if any(k in combined for k in ["attendance", "roster sheet", "roll number", "present/absent", "student attendance"]):
            return DocumentArchetype.ATTENDANCE
        if any(k in combined for k in ["prd", "product requirements", "user stories", "functional specs", "system specification"]):
            return DocumentArchetype.PRD
        if any(k in combined for k in ["formal letter", "appointment letter", "resignation letter", "official email", "apology letter", "dear "]):
            return DocumentArchetype.FORMAL_LETTER
        if any(k in combined for k in ["spreadsheet", "excel sheet", "data table", "budget sheet", "expense sheet"]):
            return DocumentArchetype.SPREADSHEET
        if any(k in combined for k in ["report", "whitepaper", "executive summary", "overview", "analysis"]):
            return DocumentArchetype.REPORT

        return DocumentArchetype.GENERAL

    @classmethod
    def parse_markdown_table(cls, table_lines: List[str]) -> Optional[TableData]:
        if len(table_lines) < 2:
            return None

        clean_rows = []
        for line in table_lines:
            line = line.strip()
            if not line.startswith("|") or not line.endswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            # Skip delimiter line
            if all(re.match(r"^:?-+:?$", c) for c in cells if c):
                continue
            clean_rows.append(cells)

        if not clean_rows:
            return None

        headers = clean_rows[0]
        data_rows = clean_rows[1:] if len(clean_rows) > 1 else []

        return TableData(
            headers=headers,
            rows=data_rows
        )

    @classmethod
    def synthesize_from_text(
        cls,
        text: str,
        user_query: Optional[str] = None,
        forced_title: Optional[str] = None
    ) -> DocumentSpec:
        q = user_query or ""
        archetype = cls.detect_archetype(q, text)

        lines = text.split("\n")
        title = forced_title or ""
        subtitle = None
        author = "Aetherius AI"
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

        sections: List[DocumentSection] = []
        current_section = DocumentSection(heading="Overview")
        summary_box = None
        key_metrics: Dict[str, str] = {}
        contact_info: Dict[str, str] = {}

        # Colors by Archetype
        accent_palette = {
            DocumentArchetype.RESUME: "#1E3A8A",       # Deep Professional Navy
            DocumentArchetype.REPORT: "#0F766E",       # Emerald Teal
            DocumentArchetype.INVOICE: "#0369A1",      # Blue Sky Business
            DocumentArchetype.ATTENDANCE: "#4338CA",   # Indigo Academic
            DocumentArchetype.PRD: "#334155",          # Slate Modern
            DocumentArchetype.FORMAL_LETTER: "#1F2937",# Charcoal
            DocumentArchetype.SPREADSHEET: "#15803D",  # Excel Forest Green
            DocumentArchetype.GENERAL: "#1E293B",      # Slate
        }

        in_table = False
        table_buffer: List[str] = []

        def flush_table():
            nonlocal in_table, table_buffer, current_section
            if table_buffer:
                td = cls.parse_markdown_table(table_buffer)
                if td:
                    current_section.table = td
                table_buffer = []
            in_table = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if in_table:
                    flush_table()
                continue

            # Check Markdown table line
            if line.startswith("|") and line.endswith("|"):
                in_table = True
                table_buffer.append(line)
                continue
            elif in_table:
                flush_table()

            # Heading 1 (Document Title if not already set)
            if line.startswith("# ") and not line.startswith("##"):
                h_text = line.lstrip("#").strip()
                if not title:
                    title = h_text
                else:
                    if current_section.content_paragraphs or current_section.bullet_points or current_section.table:
                        sections.append(current_section)
                    current_section = DocumentSection(heading=h_text)
                continue

            # Heading 2 or Heading 3 (Section Heading)
            if line.startswith("## ") or line.startswith("### "):
                if in_table:
                    flush_table()
                if current_section.content_paragraphs or current_section.bullet_points or current_section.table:
                    sections.append(current_section)
                current_section = DocumentSection(heading=line.lstrip("#").strip())
                continue

            # Bullet points
            if re.match(r"^[\*\-\+]\s+", line):
                item_text = re.sub(r"^[\*\-\+]\s+", "", line).strip()
                # Check for key metric (e.g., "**GPA:** 3.9/4.0")
                m_metric = re.match(r"^\*\*([^\*]+)\*\*:\s*(.*)$", item_text)
                if m_metric:
                    k, v = m_metric.group(1).strip(), m_metric.group(2).strip()
                    if len(k) < 30 and len(v) < 50:
                        key_metrics[k] = v
                current_section.bullet_points.append(item_text)
                continue

            # Callout quotes (e.g., "> Note: ...")
            if line.startswith(">"):
                quote_text = line.lstrip(">").strip()
                current_section.callouts.append(CalloutBlock(content=quote_text, style="info"))
                continue

            # Standard paragraph text
            clean_p = re.sub(r"\[.*?\]\(.*?\)", lambda m: m.group(0).split("]")[0].lstrip("["), line)
            current_section.content_paragraphs.append(clean_p)

        if in_table:
            flush_table()

        if current_section.content_paragraphs or current_section.bullet_points or current_section.table:
            sections.append(current_section)

        # Intelligent Title extraction and conversational query filtering
        is_conversational_cmd = bool(re.search(r"^(make|create|generate|download|export|print|save)?\s*(a\s+)?(pdf|docx|excel|word|spreadsheet|doc|file)?\s*(of\s+it|it|this|that|now|please)?$", q.strip(), flags=re.IGNORECASE))
        
        # Check if title is generic or missing from text
        if not title or title.lower().strip() in ["overview", "references", "notes", "pdf of it", "it", "document", "template", "untitled"]:
            # Check for candidate section heading
            valid_heading = next((s.heading for s in sections if s.heading and s.heading.lower() not in ["overview", "references", "notes"]), None)
            if valid_heading:
                title = valid_heading
            elif archetype == DocumentArchetype.RESUME:
                title = "Professional Resume"
            elif archetype == DocumentArchetype.ATTENDANCE:
                title = "Attendance Register"
            elif archetype == DocumentArchetype.INVOICE:
                title = "Commercial Invoice"
            elif archetype == DocumentArchetype.PRD:
                title = "Product Requirement Document"
            elif archetype == DocumentArchetype.FORMAL_LETTER:
                title = "Formal Letter"
            elif archetype == DocumentArchetype.SPREADSHEET:
                title = "Data Spreadsheet"
            elif q and not is_conversational_cmd:
                clean_q = re.sub(r"^(make|create|generate|write|draft|build)\s+(an?|the)?\s*", "", q, flags=re.IGNORECASE).strip()
                title = clean_q.title()[:60]
            else:
                title = "Aetherius Document Report"

        return DocumentSpec(
            title=title,
            subtitle=subtitle,
            archetype=archetype,
            author=author,
            date_str=date_str,
            summary_box=summary_box,
            key_metrics=key_metrics,
            contact_info=contact_info,
            sections=sections,
            accent_color=accent_palette.get(archetype, "#1E3A8A")
        )
