import io
import re
from typing import Optional
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from backend.app.services.generators.document_models import DocumentSpec, DocumentArchetype


class DocxGenerator:
    """
    Microsoft Word (.docx) document generator.
    Produces enterprise-grade Word documents with corporate heading styles,
    tables with shaded headers, callout boxes, and bullet lists.
    """

    @classmethod
    def set_cell_background(cls, cell, hex_color: str):
        shading_xml = f'<w:shd {nsdecls("w")} w:fill="{hex_color.lstrip("#")}"/>'
        cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))

    @classmethod
    def set_cell_margins(cls, cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for margin_name, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
            node = OxmlElement(margin_name)
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    @classmethod
    def generate_docx_bytes(cls, spec: DocumentSpec) -> bytes:
        doc = Document()

        # Set 1-inch margins
        for section in doc.sections:
            section.top_margin = Inches(0.8)
            section.bottom_margin = Inches(0.8)
            section.left_margin = Inches(0.8)
            section.right_margin = Inches(0.8)

        # 1. Document Title
        title_p = doc.add_paragraph()
        title_run = title_p.add_run(spec.title)
        title_run.bold = True
        title_run.font.size = Pt(22)
        title_run.font.name = "Calibri"
        title_run.font.color.rgb = RGBColor(15, 23, 42)
        title_p.paragraph_format.space_after = Pt(2)

        # 2. Subtitle / Metadata
        if spec.subtitle:
            sub_p = doc.add_paragraph()
            sub_run = sub_p.add_run(spec.subtitle)
            sub_run.font.size = Pt(11)
            sub_run.font.color.rgb = RGBColor(71, 85, 105)
            sub_p.paragraph_format.space_after = Pt(4)

        meta_p = doc.add_paragraph()
        meta_items = []
        if spec.date_str:
            meta_items.append(f"Date: {spec.date_str}")
        if spec.author:
            meta_items.append(f"Prepared By: {spec.author}")
        if spec.archetype:
            meta_items.append(f"Type: {spec.archetype.value.replace('_', ' ').title()}")
        
        meta_run = meta_p.add_run("  |  ".join(meta_items))
        meta_run.font.size = Pt(9.5)
        meta_run.font.color.rgb = RGBColor(100, 116, 139)
        meta_p.paragraph_format.space_after = Pt(14)

        # 3. Document Sections
        for s in spec.sections:
            if s.heading:
                h_p = doc.add_paragraph()
                h_run = h_p.add_run(s.heading)
                h_run.bold = True
                h_run.font.size = Pt(13)
                h_run.font.name = "Calibri"
                h_run.font.color.rgb = RGBColor(30, 58, 138)  # Deep Navy
                h_p.paragraph_format.space_before = Pt(12)
                h_p.paragraph_format.space_after = Pt(4)

            # Paragraphs
            for p_text in s.content_paragraphs:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(4)
                p.paragraph_format.line_spacing = 1.15

                # Parse markdown bold / italic
                parts = re.split(r"(\*\*.*?\*\*)", p_text)
                for part in parts:
                    if part.startswith("**") and part.endswith("**"):
                        r = p.add_run(part[2:-2])
                        r.bold = True
                    else:
                        r = p.add_run(part)
                    r.font.size = Pt(10)
                    r.font.name = "Calibri"
                    r.font.color.rgb = RGBColor(15, 23, 42)

            # Bullets
            for b_text in s.bullet_points:
                bp = doc.add_paragraph(style="List Bullet")
                bp.paragraph_format.space_after = Pt(2)
                parts = re.split(r"(\*\*.*?\*\*)", b_text)
                for part in parts:
                    if part.startswith("**") and part.endswith("**"):
                        r = bp.add_run(part[2:-2])
                        r.bold = True
                    else:
                        r = bp.add_run(part)
                    r.font.size = Pt(10)
                    r.font.name = "Calibri"
                    r.font.color.rgb = RGBColor(15, 23, 42)

            # Callouts
            for callout in s.callouts:
                cp = doc.add_paragraph()
                cp.paragraph_format.left_indent = Inches(0.3)
                cp.paragraph_format.space_before = Pt(4)
                cp.paragraph_format.space_after = Pt(6)
                c_run = cp.add_run(f"[{callout.title}]: {callout.content}")
                c_run.italic = True
                c_run.font.size = Pt(9.5)
                c_run.font.color.rgb = RGBColor(51, 65, 85)

            # Tables
            if s.table and s.table.headers:
                table = doc.add_table(rows=len(s.table.rows) + 1, cols=len(s.table.headers))
                table.alignment = WD_TABLE_ALIGNMENT.CENTER
                table.autofit = True

                # Format Header
                hdr_cells = table.rows[0].cells
                for i, header_text in enumerate(s.table.headers):
                    hdr_cells[i].text = header_text
                    cls.set_cell_background(hdr_cells[i], "1E3A8A")
                    cls.set_cell_margins(hdr_cells[i], top=120, bottom=120, left=150, right=150)
                    for paragraph in hdr_cells[i].paragraphs:
                        for run in paragraph.runs:
                            run.font.bold = True
                            run.font.color.rgb = RGBColor(255, 255, 255)
                            run.font.size = Pt(9)

                # Format Data Rows
                for r_idx, row_data in enumerate(s.table.rows):
                    row_cells = table.rows[r_idx + 1].cells
                    bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
                    for c_idx, cell_value in enumerate(row_data):
                        if c_idx < len(row_cells):
                            row_cells[c_idx].text = str(cell_value).replace("**", "")
                            cls.set_cell_background(row_cells[c_idx], bg_color)
                            cls.set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=150, right=150)
                            for paragraph in row_cells[c_idx].paragraphs:
                                for run in paragraph.runs:
                                    run.font.size = Pt(9)
                                    run.font.color.rgb = RGBColor(15, 23, 42)

                doc.add_paragraph().paragraph_format.space_after = Pt(6)

        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()
