import io
import json
import os
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
    Preformatted,
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ─── Register Modern TrueType Fonts ───────────────────────────────────────────
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_MONO = "Courier"

try:
    windows_fonts = "C:/Windows/Fonts"
    segoe_reg = os.path.join(windows_fonts, "segoeui.ttf")
    segoe_bold = os.path.join(windows_fonts, "segoeuib.ttf")
    arial_reg = os.path.join(windows_fonts, "arial.ttf")
    arial_bold = os.path.join(windows_fonts, "arialbd.ttf")
    consolas_reg = os.path.join(windows_fonts, "consola.ttf")

    if os.path.exists(segoe_reg) and os.path.exists(segoe_bold):
        pdfmetrics.registerFont(TTFont("ModernAcademic", segoe_reg))
        pdfmetrics.registerFont(TTFont("ModernAcademic-Bold", segoe_bold))
        FONT_REGULAR = "ModernAcademic"
        FONT_BOLD = "ModernAcademic-Bold"
    elif os.path.exists(arial_reg) and os.path.exists(arial_bold):
        pdfmetrics.registerFont(TTFont("ModernAcademic", arial_reg))
        pdfmetrics.registerFont(TTFont("ModernAcademic-Bold", arial_bold))
        FONT_REGULAR = "ModernAcademic"
        FONT_BOLD = "ModernAcademic-Bold"

    if os.path.exists(consolas_reg):
        pdfmetrics.registerFont(TTFont("ModernMono", consolas_reg))
        FONT_MONO = "ModernMono"
except Exception as font_err:
    print(f"Warning: Fallback to default fonts: {font_err}")


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
        self.setFont(FONT_REGULAR, 8)
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


# ─── LaTeX to Unicode Mathematical Conversion ─────────────────────────────────
def latex_to_unicode(latex_str: str) -> str:
    if not latex_str:
        return ""

    s = latex_str.strip()

    # Remove outer math delimiters
    if s.startswith("$$") and s.endswith("$$"):
        s = s[2:-2].strip()
    elif s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    elif s.startswith("\\[") and s.endswith("\\]"):
        s = s[2:-2].strip()
    elif s.startswith("\\(") and s.endswith("\\)"):
        s = s[2:-2].strip()

    # Handle piecewise / cases environment
    if "\\begin{cases}" in s:
        inner = re.search(r"\\begin\{cases\}(.*?)\\end\{cases\}", s, re.DOTALL)
        if inner:
            cases_content = inner.group(1).strip()
            lines = [l.strip() for l in re.split(r"\\\\|\\\\\\\\", cases_content) if l.strip()]
            formatted_lines = []
            for l in lines:
                parts = [p.strip() for p in l.split("&") if p.strip()]
                clean_parts = "   ".join(parts)
                formatted_lines.append(clean_parts)
            cases_str = "{\n  " + "\n  ".join(formatted_lines) + "\n}"
            s = s.replace(inner.group(0), cases_str)

    replacements = [
        # Sets & Logic
        (r"\\mu", "μ"),
        (r"\\cup", " ∪ "),
        (r"\\cap", " ∩ "),
        (r"\\land", " ∧ "),
        (r"\\lor", " ∨ "),
        (r"\\neg", "¬"),
        (r"\\sim", "∼"),
        (r"\\subset", " ⊂ "),
        (r"\\subseteq", " ⊆ "),
        (r"\\supset", " ⊃ "),
        (r"\\supseteq", " ⊇ "),
        (r"\\in", " ∈ "),
        (r"\\notin", " ∉ "),
        (r"\\emptyset", "∅"),
        (r"\\oplus", " ⊕ "),
        (r"\\odot", " ⊙ "),
        (r"\\setminus", " \\ "),
        # Relations & Operations
        (r"\\geq", " ≥ "),
        (r"\\ge", " ≥ "),
        (r"\\leq", " ≤ "),
        (r"\\le", " ≤ "),
        (r"\\neq", " ≠ "),
        (r"\\ne", " ≠ "),
        (r"\\equiv", " ≡ "),
        (r"\\times", " × "),
        (r"\\div", " ÷ "),
        (r"\\pm", " ± "),
        (r"\\mp", " ∓ "),
        (r"\\approx", " ≈ "),
        (r"\\propto", " ∝ "),
        (r"\\infty", "∞"),
        (r"\\rightarrow", " → "),
        (r"\\to", " → "),
        (r"\\leftarrow", " ← "),
        (r"\\Rightarrow", " ⇒ "),
        (r"\\Leftarrow", " ⇐ "),
        (r"\\Leftrightarrow", " ⇔ "),
        # Greek Letters
        (r"\\alpha", "α"),
        (r"\\beta", "β"),
        (r"\\gamma", "γ"),
        (r"\\Gamma", "Γ"),
        (r"\\delta", "δ"),
        (r"\\Delta", "Δ"),
        (r"\\epsilon", "ε"),
        (r"\\varepsilon", "ε"),
        (r"\\zeta", "ζ"),
        (r"\\eta", "η"),
        (r"\\theta", "θ"),
        (r"\\Theta", "Θ"),
        (r"\\iota", "ι"),
        (r"\\kappa", "κ"),
        (r"\\lambda", "λ"),
        (r"\\Lambda", "Λ"),
        (r"\\nu", "ν"),
        (r"\\xi", "ξ"),
        (r"\\pi", "π"),
        (r"\\rho", "ρ"),
        (r"\\sigma", "σ"),
        (r"\\Sigma", "Σ"),
        (r"\\tau", "τ"),
        (r"\\phi", "φ"),
        (r"\\Phi", "Φ"),
        (r"\\chi", "χ"),
        (r"\\psi", "ψ"),
        (r"\\omega", "ω"),
        (r"\\Omega", "Ω"),
        # Operators & Math Functions
        (r"\\sum", "Σ"),
        (r"\\prod", "Π"),
        (r"\\int", "∫"),
        (r"\\partial", "∂"),
        (r"\\nabla", "∇"),
        (r"\\max", "max"),
        (r"\\min", "min"),
        (r"\\log", "log"),
        (r"\\ln", "ln"),
        (r"\\exp", "exp"),
        (r"\\sin", "sin"),
        (r"\\cos", "cos"),
        (r"\\tan", "tan"),
        (r"\\lim", "lim"),
        # Formatting & Macros
        (r"\\mathcal\{([A-Za-z])\}", r"\1"),
        (r"\\mathbb\{([A-Za-z])\}", r"\1"),
        (r"\\text\{([^}]+)\}", r"\1"),
        (r"\\textbf\{([^}]+)\}", r"<b>\1</b>"),
        (r"\\textit\{([^}]+)\}", r"<i>\1</i>"),
        (r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1 / \2)"),
        (r"\\sqrt\[([^]]+)\]\{([^}]+)\}", r"\1√(\2)"),
        (r"\\sqrt\{([^}]+)\}", r"√(\1)"),
        (r"\\bar\{([^}]+)\}", r"\1̄"),
        (r"\\hat\{([^}]+)\}", r"\1̂"),
        (r"\\vec\{([^}]+)\}", r"\1⃗"),
        (r"\\overline\{([^}]+)\}", r"\1̄"),
        (r"\\underline\{([^}]+)\}", r"\1"),
        # Superscript & Subscript Cleanup
        (r"\^\{c\}|\^c", "ᶜ"),
        (r"\^\{2\}|\^2", "²"),
        (r"\^\{3\}|\^3", "³"),
        (r"\^\{n\}|\^n", "ⁿ"),
        (r"\^\{([^}]+)\}", r"^(\1)"),
        (r"_\{([^}]+)\}", r"_(\1)"),
        (r"\\cdot", "·"),
        (r"\\quad", " "),
        (r"\\qquad", "   "),
        (r"\\left", ""),
        (r"\\right", ""),
        (r"\\{", "{"),
        (r"\\}", "}"),
        (r"\\\\", "\n"),
        (r"\\", ""),
    ]

    for pat, rep in replacements:
        s = re.sub(pat, rep, s)

    # Clean up multiple spaces
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


# ─── XML Safe Text Cleaner for ReportLab ──────────────────────────────────────
ALLOWED_TAG_PATTERN = re.compile(
    r"(</?(?:b|i|u|sub|sup|font|color)(?:\s+[^>]+)?>|<br/>)",
    re.IGNORECASE,
)


def xml_escape(text: str) -> str:
    """Sanitizes raw HTML/Markdown into safe ReportLab-compliant XML."""
    if not text:
        return ""

    # Normalize br tags
    text = re.sub(r"<\s*/?\s*br\s*/?\s*>", "<br/>", text, flags=re.IGNORECASE)

    # Strip disallowed HTML tags
    disallowed = ["div", "span", "p", "ul", "ol", "li", "table", "tr", "td", "th", "tbody", "thead", "hr", "pre", "code"]
    for tag in disallowed:
        text = re.sub(rf"<\s*/?\s*{tag}[^>]*>", "", text, flags=re.IGNORECASE)

    # Escape XML entities safely
    parts = ALLOWED_TAG_PATTERN.split(text)
    escaped_parts = []
    for p in parts:
        if ALLOWED_TAG_PATTERN.match(p):
            if p.lower() in ("<br>", "<br/>", "</br>"):
                escaped_parts.append("<br/>")
            else:
                escaped_parts.append(p)
        else:
            p = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+);)", "&amp;", p)
            p = p.replace("<", "&lt;").replace(">", "&gt;")
            escaped_parts.append(p)

    return "".join(escaped_parts)


# ─── Markdown Table Parser ───────────────────────────────────────────────────
def parse_markdown_table(
    table_text: str,
    cell_style: ParagraphStyle,
    header_style: ParagraphStyle,
) -> Table | None:
    lines = [l.strip() for l in table_text.strip().split("\n") if l.strip()]
    if len(lines) < 2:
        return None

    rows = []
    header_found = False

    for line in lines:
        if re.match(r"^\|?[\s\-:|]+\|?$", line) and "-" in line:
            header_found = True
            continue

        raw_cells = [c.strip() for c in line.strip("|").split("|")]
        if not any(raw_cells):
            continue

        cell_paras = []
        for c in raw_cells:
            # Inline math and bold formatting in table cells
            c = re.sub(r"\$([^$\n]+)\$", lambda m: f"<b>{latex_to_unicode(m.group(1))}</b>", c)
            c = re.sub(r"\\\((.+?)\\\)", lambda m: f"<b>{latex_to_unicode(m.group(1))}</b>", c)
            c = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", c)
            c = re.sub(r"\*(.+?)\*", r"<i>\1</i>", c)
            clean_c = xml_escape(c)

            current_style = header_style if (len(rows) == 0 and not header_found) else cell_style
            cell_paras.append(Paragraph(clean_c, current_style))

        if cell_paras:
            rows.append(cell_paras)

    if not rows:
        return None

    num_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < num_cols:
            r.append(Paragraph("", cell_style))

    total_width = 504.0
    if num_cols == 2:
        col_widths = [150.0, 354.0]
    elif num_cols == 3:
        col_widths = [120.0, 192.0, 192.0]
    elif num_cols == 4:
        col_widths = [90.0, 138.0, 138.0, 138.0]
    else:
        col_widths = [total_width / num_cols] * num_cols

    table = Table(rows, colWidths=col_widths)
    table_style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e293b")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]

    for row_idx in range(1, len(rows)):
        bg = colors.HexColor("#ffffff") if row_idx % 2 == 1 else colors.HexColor("#f8fafc")
        table_style_commands.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg))

    table.setStyle(TableStyle(table_style_commands))
    return table


# ─── Parse Markdown into ReportLab Flowable Elements ─────────────────────────
def parse_markdown_to_flowables(
    text: str,
    body_style: ParagraphStyle,
    heading_style: ParagraphStyle,
    formula_style: ParagraphStyle,
    code_style: ParagraphStyle,
) -> list:
    flowables = []
    if not text:
        return flowables

    raw = text.replace("\r\n", "\n").strip()

    # 1. Clean rubric / scoring feedback if any
    raw = re.sub(
        r"(?:^|\n)(?:Mark Allocation|Grading Rubric|Scoring Breakdown|Reviewer Assessment):\s*[\s\S]*?(?=\n\n|\n[A-Z]|$)",
        "\n",
        raw,
        flags=re.IGNORECASE,
    )

    # 2. Split into Code Blocks vs Regular Text chunks
    parts = re.split(r"(```[\s\S]*?```)", raw)

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=body_style,
        fontSize=8.5,
        leading=11.5,
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=heading_style,
        fontSize=9,
        leading=12,
        fontName=FONT_BOLD,
        textColor=colors.HexColor("#0f172a"),
    )

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Case A: Fenced Code Block / ASCII Diagram
        if part.startswith("```") and part.endswith("```"):
            code_lines = part[3:-3].strip().split("\n")
            # If first line has a language tag like ```python or ```text, strip it
            if code_lines and re.match(r"^[a-zA-Z0-9_\-]+$", code_lines[0].strip()):
                code_lines = code_lines[1:]

            code_text = "\n".join(code_lines)
            if not code_text.strip():
                continue

            # Render ASCII diagram / code inside a dedicated monospace container
            pre_element = Preformatted(code_text, code_style)
            code_table = Table([[pre_element]], colWidths=[504])
            code_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            flowables.append(Spacer(1, 4))
            flowables.append(code_table)
            flowables.append(Spacer(1, 6))
            continue

        # Case B: Regular text with formulas, headings, tables
        block_pattern = re.compile(
            r"(\$\$(?:[^\$]+?)\$\$|\\\[(?:[\s\S]+?)\\\]|\[\s*\\(?:mu|max|min|begin|neg|text|sum|frac|sigma)[^\]]+?\])",
            re.DOTALL,
        )

        chunks = block_pattern.split(part)

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            # Display Math Formula
            if (
                chunk.startswith("$$")
                or chunk.startswith("\\[")
                or (chunk.startswith("[") and ("\\mu" in chunk or "\\begin" in chunk or "\\max" in chunk))
            ):
                unicode_math = latex_to_unicode(chunk)
                formatted_math = xml_escape(unicode_math).replace("\n", "<br/>")

                math_p = Paragraph(f"<b>{formatted_math}</b>", formula_style)
                formula_table = Table(
                    [[math_p]],
                    colWidths=[504],
                )
                formula_table.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
                        ("LINELEFT", (0, 0), (-1, -1), 3, colors.HexColor("#0f766e")),
                        ("PADDING", (0, 0), (-1, -1), 6),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ])
                )
                flowables.append(Spacer(1, 4))
                flowables.append(formula_table)
                flowables.append(Spacer(1, 6))
                continue

            # Split regular paragraphs
            paragraphs = chunk.split("\n\n")

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Horizontal Rule e.g. --- or --
                if re.match(r"^[-*_]{2,}$", para):
                    flowables.append(Spacer(1, 4))
                    flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=6))
                    continue

                # Markdown Table
                lines = [l.strip() for l in para.split("\n") if l.strip()]
                if len(lines) >= 2 and any("|" in l for l in lines) and any(re.match(r"^\|?[\s\-:|]+\|?$", l) for l in lines):
                    rendered_table = parse_markdown_table(
                        table_text=para,
                        cell_style=table_cell_style,
                        header_style=table_header_style,
                    )
                    if rendered_table:
                        flowables.append(Spacer(1, 4))
                        flowables.append(rendered_table)
                        flowables.append(Spacer(1, 6))
                        continue

                # Inline math `$ ... $` or `\( ... \)`
                para = re.sub(
                    r"\$([^$\n]+)\$",
                    lambda m: f"<b>{latex_to_unicode(m.group(1))}</b>",
                    para,
                )
                para = re.sub(
                    r"\\\((.+?)\\\)",
                    lambda m: f"<b>{latex_to_unicode(m.group(1))}</b>",
                    para,
                )

                # Markdown Heading (### 1. Title)
                if re.match(r"^#{1,6}\s+", para):
                    heading_text = re.sub(r"^#{1,6}\s*", "", para).strip()
                    heading_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", heading_text)
                    heading_text = xml_escape(heading_text)
                    flowables.append(Spacer(1, 6))
                    flowables.append(Paragraph(heading_text, heading_style))
                    flowables.append(Spacer(1, 2))
                    continue

                # Subtopic Numbering "1. Perception and Sensory Input"
                if re.match(r"^\d+\.\s+[A-Za-z]", para) and len(para) < 90 and not ("." in para[4:-1]):
                    item_title = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", para)
                    item_title = xml_escape(item_title)
                    flowables.append(Spacer(1, 5))
                    flowables.append(Paragraph(f"<b>{item_title}</b>", heading_style))
                    flowables.append(Spacer(1, 2))
                    continue

                # Standard Paragraph
                para = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", para)
                para = re.sub(r"\*(.+?)\*", r"<i>\1</i>", para)
                para = re.sub(r"^\s*[-*•]\s+(.+)$", r"• \1", para, flags=re.MULTILINE)

                para_html = xml_escape(para).replace("\n", "<br/>")
                flowables.append(Paragraph(para_html, body_style))
                flowables.append(Spacer(1, 3))

    return flowables


# ─── Main PDF Generation Function ─────────────────────────────────────────────
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

    brand_style = ParagraphStyle(
        "BrandStyle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor("#0f766e"),
    )

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
    )

    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor("#475569"),
    )

    disclaimer_style = ParagraphStyle(
        "DisclaimerStyle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#b91c1c"),
    )

    question_title_style = ParagraphStyle(
        "QuestionTitleStyle",
        parent=styles["Heading2"],
        fontName=FONT_BOLD,
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
    )

    answer_heading_style = ParagraphStyle(
        "AnswerHeadingStyle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#0f766e"),
    )

    answer_body_style = ParagraphStyle(
        "AnswerBodyStyle",
        parent=styles["BodyText"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
    )

    formula_style = ParagraphStyle(
        "FormulaStyle",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,
    )

    code_style = ParagraphStyle(
        "CodeStyle",
        parent=styles["Normal"],
        fontName=FONT_MONO,
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0f766e"),
    )

    source_style = ParagraphStyle(
        "SourceStyle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0284c7"),
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("ACADEMICSTACK SOLUTIONS", brand_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph(f"{subject} — {question_bank_name}", title_style))
    story.append(Spacer(1, 3))
    story.append(
        Paragraph(
            f"Generated on {datetime.utcnow().strftime('%B %d, %Y')} • RAG Grounded & AI Verified Answer Set",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 8))

    # 2. Disclaimer Callout Box
    disclaimer_html = (
        "<b>Notice:</b> This document contains AI-generated examination solutions grounded in verified study "
        "materials. It is designed to assist exam preparation, conceptual clarity, and revision."
    )
    disclaimer_table = Table(
        [[Paragraph(disclaimer_html, disclaimer_style)]],
        colWidths=[504],
    )
    disclaimer_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(disclaimer_table)
    story.append(Spacer(1, 8))

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
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ])
    )
    story.append(stats_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=10))

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
        q_header_text = f"<b>Q{q_num}. {xml_escape(q_text)}</b>"
        q_marks_text = f"<b>[{marks} Marks]</b>"

        q_table = Table(
            [[
                Paragraph(q_header_text, question_title_style),
                Paragraph(
                    q_marks_text,
                    ParagraphStyle(
                        "MarkRight",
                        parent=question_title_style,
                        alignment=2,
                        textColor=colors.HexColor("#0f766e"),
                    ),
                ),
            ]],
            colWidths=[420, 84],
        )
        q_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#99f6e4")),
            ])
        )

        story.append(q_table)
        story.append(Spacer(1, 6))

        # Parse structured answer content and formula boxes
        answer_flowables = parse_markdown_to_flowables(
            content,
            body_style=answer_body_style,
            heading_style=answer_heading_style,
            formula_style=formula_style,
            code_style=code_style,
        )
        story.extend(answer_flowables)

        # Sources footer
        if sources_list:
            source_labels = []
            for s in sources_list:
                res = s.get("resource_name", "Material")
                p = s.get("page", "")
                ch = s.get("chapter", "")
                label = f"{res} (Pg {p})" if p and p != "N/A" else res
                if ch and ch != "General":
                    label += f" • {ch}"
                source_labels.append(label)
            source_text = f"<b>Verified Sources:</b> {', '.join(source_labels)}"
            story.append(Paragraph(xml_escape(source_text), source_style))
            story.append(Spacer(1, 4))

        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=10))

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
