"""
ReportLab PDF generator for authentic university-format predicted examination papers.
Produces a clean, professional, printable exam paper with instructions, sections,
sub-questions, and marks allocation.
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.pdfgen import canvas

from app.pdf import fonts

fonts.register_pdf_fonts()

INK = "#0f172a"
HEAD_DARK = "#020617"
ACCENT = "#0f766e"
MUTED = "#64748b"
BORDER_COLOR = "#cbd5e1"
ALT_ROW_BG = "#f8fafc"
CONTENT_WIDTH = 504.0


def _escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class PredictedPaperNumberedCanvas(canvas.Canvas):
    """Two-pass canvas for authentic exam paper numbering and running header/footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_decorations(self, page_count):
        self.saveState()
        self.setFont(fonts.FONT_SANS, 8)
        self.setFillColor(colors.HexColor(MUTED))

        # Running header (page 2 onwards)
        if self._pageNumber > 1:
            self.drawString(54, 750, "AcademicStack • Predicted Examination Paper")
            self.setStrokeColor(colors.HexColor(BORDER_COLOR))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        # Running footer
        self.setStrokeColor(colors.HexColor(BORDER_COLOR))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
        self.drawString(54, 32, "AcademicStack AI Multi-Year Model Exam Paper • Strictly for Preparation")
        self.restoreState()


def generate_predicted_question_paper_pdf(paper_data: dict) -> bytes:
    """
    Generates a university-standard printable examination question paper PDF.
    Expects paper_data dictionary with 'exam_meta', 'pattern_insights', and 'sections'.
    """
    fonts.register_pdf_fonts()

    meta = paper_data.get("exam_meta", {})
    sections = paper_data.get("sections", [])
    subject = meta.get("subject", "Academic Subject")
    title = meta.get("paper_title", "Predicted Examination Paper")
    duration = meta.get("time_allowed", "3 Hours")
    max_marks = meta.get("maximum_marks", 70)
    instructions = meta.get("general_instructions", [
        "All questions are compulsory subject to internal choices.",
        "Figures to the right indicate full marks assigned.",
        "Assume suitable data wherever necessary.",
    ])

    brand_style = ParagraphStyle(
        "Brand", fontName=fonts.FONT_SANS_BOLD, fontSize=10, leading=13,
        textColor=colors.HexColor(ACCENT), alignment=1, spaceAfter=2,
    )
    univ_style = ParagraphStyle(
        "UnivTitle", fontName=fonts.FONT_SANS_BOLD, fontSize=15, leading=19,
        textColor=colors.HexColor(HEAD_DARK), alignment=1, spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "SubjectTitle", fontName=fonts.FONT_SANS_BOLD, fontSize=12, leading=16,
        textColor=colors.HexColor(INK), alignment=1, spaceAfter=4,
    )
    meta_bar_style = ParagraphStyle(
        "MetaBar", fontName=fonts.FONT_SANS, fontSize=9, leading=12,
        textColor=colors.HexColor(INK),
    )
    inst_head_style = ParagraphStyle(
        "InstHead", fontName=fonts.FONT_SANS_BOLD, fontSize=8.5, leading=11,
        textColor=colors.HexColor(HEAD_DARK), spaceAfter=2,
    )
    inst_item_style = ParagraphStyle(
        "InstItem", fontName=fonts.FONT_SERIF, fontSize=8, leading=11,
        textColor=colors.HexColor(MUTED),
    )
    sec_title_style = ParagraphStyle(
        "SecTitle", fontName=fonts.FONT_SANS_BOLD, fontSize=10.5, leading=14,
        textColor=colors.HexColor(HEAD_DARK),
    )
    sec_inst_style = ParagraphStyle(
        "SecInst", fontName=fonts.FONT_SANS, fontSize=8.5, leading=12,
        textColor=colors.HexColor(ACCENT), alignment=2,
    )
    q_num_style = ParagraphStyle(
        "QNum", fontName=fonts.FONT_SANS_BOLD, fontSize=9.5, leading=13.5,
        textColor=colors.HexColor(HEAD_DARK),
    )
    q_text_style = ParagraphStyle(
        "QText", fontName=fonts.FONT_SERIF, fontSize=9.5, leading=13.5,
        textColor=colors.HexColor(INK),
    )
    q_marks_style = ParagraphStyle(
        "QMarks", fontName=fonts.FONT_SANS_BOLD, fontSize=9, leading=13.5,
        textColor=colors.HexColor(ACCENT), alignment=2,
    )
    or_style = ParagraphStyle(
        "OrDivider", fontName=fonts.FONT_SANS_BOLD, fontSize=8.5, leading=12,
        textColor=colors.HexColor(MUTED), alignment=1,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=54, rightMargin=54, topMargin=55, bottomMargin=55,
        title=f"{subject} - {title}", author="AcademicStack AI Exam Predictor",
    )

    story = []

    # 1. Exam Masthead
    story.append(Paragraph("ACADEMICSTACK PREDICTED MODEL EXAMINATION", brand_style))
    story.append(Paragraph(_escape(title), univ_style))
    story.append(Paragraph(f"Course / Subject: <b>{_escape(subject)}</b>", sub_style))
    story.append(Spacer(1, 4))

    # 2. Time & Max Marks Strip
    meta_table_data = [[
        Paragraph(f"<b>Time Allowed:</b> {_escape(duration)}", meta_bar_style),
        Paragraph(f"<b>Session:</b> Model Exam {datetime.utcnow().year}", meta_bar_style),
        Paragraph(f"<b>Maximum Marks:</b> {max_marks}", ParagraphStyle("MBRight", parent=meta_bar_style, alignment=2)),
    ]]
    meta_table = Table(meta_table_data, colWidths=[CONTENT_WIDTH / 3] * 3)
    meta_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("PADDING", (0, 0), (-1, -1), 4.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6))

    # 3. General Instructions Box
    inst_flowables = [Paragraph("<b>General Instructions to Candidates:</b>", inst_head_style)]
    for i, inst in enumerate(instructions, 1):
        inst_flowables.append(Paragraph(f"({i}) {_escape(inst)}", inst_item_style))
    
    inst_box = Table([[inst_flowables]], colWidths=[CONTENT_WIDTH])
    inst_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(inst_box)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(BORDER_COLOR), spaceAfter=10))

    # 4. Sections & Questions
    for sec_idx, sec in enumerate(sections, 1):
        sec_name = sec.get("section_name", f"SECTION {chr(64 + sec_idx)}")
        sec_inst = sec.get("section_instruction", "")
        sec_total = sec.get("total_marks")
        if sec_total and not sec_inst.endswith("Marks"):
            sec_inst += f" [{sec_total} Marks]"

        # Section Header Strip
        sec_header = Table([[
            Paragraph(_escape(sec_name), sec_title_style),
            Paragraph(_escape(sec_inst), sec_inst_style),
        ]], colWidths=[CONTENT_WIDTH * 0.45, CONTENT_WIDTH * 0.55])
        sec_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(BORDER_COLOR)),
        ]))
        story.append(KeepTogether([sec_header, Spacer(1, 4)]))

        # Questions in this section
        q_list = sec.get("questions", [])
        q_rows = []

        for q in q_list:
            is_or = q.get("is_or_choice", False)
            if is_or:
                q_rows.append([
                    Paragraph("", q_num_style),
                    Paragraph("<b>— OR —</b>", or_style),
                    Paragraph("", q_marks_style),
                ])

            q_num = q.get("question_number", "")
            q_text = q.get("question_text", "")
            marks = q.get("marks", "")
            likelihood = q.get("prediction_likelihood", "")
            
            q_text_p = f"{_escape(q_text)}"
            if likelihood:
                q_text_p += f' <font color="#0f766e" size="7"><b>[{_escape(likelihood)} Probability]</b></font>'

            q_rows.append([
                Paragraph(f"<b>{_escape(q_num)}</b>", q_num_style),
                Paragraph(q_text_p, q_text_style),
                Paragraph(f"[{marks}]", q_marks_style),
            ])

        if q_rows:
            q_table = Table(
                q_rows,
                colWidths=[38, CONTENT_WIDTH - 38 - 50, 50],
            )
            q_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
            ]))
            story.append(q_table)

        story.append(Spacer(1, 10))

    # Paper End Note
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>*** END OF QUESTION PAPER ***</b>", or_style))

    doc.build(story, canvasmaker=PredictedPaperNumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
