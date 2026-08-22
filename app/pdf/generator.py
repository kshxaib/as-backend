import io
import json
import re
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 750, "AcademicStack • Solved Question Bank")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        # Footer
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)

        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.drawString(
            54,
            32,
            "AcademicStack AI-Assisted Solved Paper • Strictly for Educational Reference",
        )
        self.restoreState()


def clean_markdown_for_pdf(text: str) -> str:
    if not text:
        return ""

    # Convert markdown headers ## to bold text
    text = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    # Convert **bold** to <b>bold</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Convert *italic* to <i>italic</i>
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # Replace newlines with <br/>
    text = text.replace("\n\n", "<br/><br/>").replace("\n", "<br/>")

    return text


def generate_solved_question_bank_pdf(
    question_bank_name: str,
    subject: str,
    answers: list[dict],
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=60,
        bottomMargin=55,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    brand_style = ParagraphStyle(
        "BrandStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#4f46e5"),
    )

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
    )

    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
    )

    disclaimer_style = ParagraphStyle(
        "DisclaimerStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#dc2626"),
    )

    question_title_style = ParagraphStyle(
        "QuestionTitleStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1e1b4b"),
    )

    answer_body_style = ParagraphStyle(
        "AnswerBodyStyle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
    )

    source_style = ParagraphStyle(
        "SourceStyle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0284c7"),
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("ACADEMICSTACK SOLUTIONS", brand_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"{subject} — {question_bank_name}", title_style))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            f"Generated on {datetime.utcnow().strftime('%B %d, %Y')} • RAG Grounded Answer Set",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 8))

    # 2. Disclaimer Callout Box
    disclaimer_html = (
        "<b>Notice:</b> This document contains AI-generated examination solutions grounded in verified study "
        "materials. It is designed to assist exam preparation and conceptual understanding."
    )
    disclaimer_table = Table(
        [[Paragraph(disclaimer_html, disclaimer_style)]],
        colWidths=[504],
    )
    disclaimer_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(disclaimer_table)
    story.append(Spacer(1, 14))

    # 3. Stats Strip
    total_q = len(answers)
    total_marks = sum(int(a.get("marks") or 0) for a in answers)
    stats_data = [[
        Paragraph(f"<b>Total Questions:</b> {total_q}", subtitle_style),
        Paragraph(f"<b>Total Marks:</b> {total_marks}", subtitle_style),
        Paragraph(f"<b>Subject:</b> {subject}", subtitle_style),
    ]]
    stats_table = Table(stats_data, colWidths=[168, 168, 168])
    stats_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ])
    )
    story.append(stats_table)
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    # 4. Answers List
    for index, ans in enumerate(answers, start=1):
        q_num = ans.get("question_number", index)
        q_text = ans.get("question_text", "Untitled Question")
        marks = ans.get("marks", 0)
        content = ans.get("content") or "<i>Answer not generated.</i>"
        raw_sources = ans.get("sources") or []

        if isinstance(raw_sources, str):
            try:
                sources_list = json.loads(raw_sources)
            except Exception:
                sources_list = []
        else:
            sources_list = raw_sources

        # Question Header Box
        q_header_text = f"<b>Q{q_num}. {q_text}</b>"
        q_marks_text = f"<b>[{marks} Marks]</b>"

        q_table = Table(
            [[
                Paragraph(q_header_text, question_title_style),
                Paragraph(q_marks_text, ParagraphStyle("MarkRight", parent=question_title_style, alignment=2, textColor=colors.HexColor("#4f46e5"))),
            ]],
            colWidths=[420, 84],
        )
        q_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef2ff")),
                ("PADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d2fe")),
            ])
        )

        formatted_content = clean_markdown_for_pdf(content)
        answer_paragraph = Paragraph(formatted_content, answer_body_style)

        # Sources footer
        source_items = []
        if sources_list:
            source_labels = []
            for s in sources_list:
                res = s.get("resource_name", "Material")
                p = s.get("page", "")
                ch = s.get("chapter", "")
                source_labels.append(f"{res} (Pg {p})" if p and p != "N/A" else res)
            source_text = f"<b>Sources Cited:</b> {', '.join(source_labels)}"
            source_items.append(Paragraph(source_text, source_style))

        answer_elements = [
            q_table,
            Spacer(1, 8),
            answer_paragraph,
            Spacer(1, 6),
        ]
        if source_items:
            answer_elements.extend(source_items)
        answer_elements.append(Spacer(1, 14))
        answer_elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=14))

        story.append(KeepTogether(answer_elements))

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
