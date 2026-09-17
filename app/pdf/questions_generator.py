"""
PDF generator for extracted question banks (questions only, no answers).
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfgen import canvas

from app.pdf import fonts

fonts.register_pdf_fonts()

INK = "#1e293b"
HEAD_DARK = "#0f172a"
ACCENT = "#0f766e"
MUTED = "#64748b"
REPEAT_COLOR = "#e11d48"
CODE_BG = colors.HexColor("#f8fafc")
CODE_BORDER = colors.HexColor("#e2e8f0")
CONTENT_WIDTH = 504.0


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class NumberedCanvas(canvas.Canvas):
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
        if self._pageNumber > 1:
            self.drawString(54, 750, "AcademicStack • Question Bank")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
        self.drawString(54, 32, "AcademicStack • Extracted Question Paper")
        self.restoreState()


def generate_questions_pdf(question_bank_name: str, subject: str, questions: list[dict]) -> bytes:
    fonts.register_pdf_fonts()

    brand_style = ParagraphStyle(
        "Brand", fontName=fonts.FONT_SANS_BOLD, fontSize=10.5, leading=13,
        textColor=colors.HexColor(ACCENT), spaceAfter=2,
    )
    title_style = ParagraphStyle(
        "Title", fontName=fonts.FONT_SANS_BOLD, fontSize=18, leading=22,
        textColor=colors.HexColor(HEAD_DARK), spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", fontName=fonts.FONT_SANS, fontSize=9, leading=12.5,
        textColor=colors.HexColor(MUTED),
    )
    q_text_style = ParagraphStyle(
        "QText", fontName=fonts.FONT_SERIF, fontSize=10.5, leading=15,
        textColor=colors.HexColor(INK),
    )
    q_num_style = ParagraphStyle(
        "QNum", fontName=fonts.FONT_SANS_BOLD, fontSize=10.5, leading=15,
        textColor=colors.HexColor(HEAD_DARK),
    )
    q_marks_style = ParagraphStyle(
        "QMarks", fontName=fonts.FONT_SANS_BOLD, fontSize=10, leading=15,
        textColor=colors.HexColor(ACCENT), alignment=2,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=54, rightMargin=54, topMargin=60, bottomMargin=55,
        title=f"{subject} - {question_bank_name}",
        author="AcademicStack",
    )

    story = []

    # Header
    story.append(Paragraph("ACADEMICSTACK", brand_style))
    story.append(Paragraph(f"{_escape(subject)} — {_escape(question_bank_name)}", title_style))
    story.append(Paragraph(
        f"Generated on {datetime.utcnow().strftime('%B %d, %Y')} • {len(questions)} Questions",
        subtitle_style,
    ))
    story.append(Spacer(1, 8))

    # Stats strip
    total_marks = sum(int(q.get("marks") or 0) for q in questions)
    repeated_count = sum(1 for q in questions if q.get("repeat_count", 1) > 1)
    stats_style = ParagraphStyle("Stats", fontName=fonts.FONT_SANS, fontSize=8.5, leading=12, textColor=colors.HexColor(MUTED))
    stats_data = [[
        Paragraph(f"<b>Total Questions:</b> {len(questions)}", stats_style),
        Paragraph(f"<b>Total Marks:</b> {total_marks}", stats_style),
        Paragraph(f"<b>🔥 High-Yield:</b> {repeated_count}", stats_style),
        Paragraph(f"<b>Subject:</b> {_escape(subject)}", stats_style),
    ]]
    stats_table = Table(stats_data, colWidths=[CONTENT_WIDTH / 4] * 4)
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, CODE_BORDER),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=8))

    # Questions
    for q in questions:
        q_num = q.get("question_number", "?")
        q_text = q.get("question_text", "")
        marks = q.get("marks", 0)
        repeat_count = q.get("repeat_count", 1)

        repeat_badge = ""
        if repeat_count > 1:
            repeat_badge = f' <font color="{REPEAT_COLOR}"><b>[★ Repeated {repeat_count}x]</b></font>'

        q_row = Table(
            [[
                Paragraph(
                    f"<b>Q{q_num}.</b>  {_escape(str(q_text))}{repeat_badge}",
                    q_text_style
                ),
                Paragraph(f"[{marks} Marks]", q_marks_style),
            ]],
            colWidths=[CONTENT_WIDTH - 84, 84],
        )
        q_row.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#99f6e4")),
        ]))
        story.append(q_row)
        story.append(Spacer(1, 6))

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
