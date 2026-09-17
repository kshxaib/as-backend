"""
Compact Exam Cheatsheet PDF Generator (1-2 Page Printout).

Condenses solved question banks into an ultra-compact, high-density 2-column
exam-hall rehearsal cheatsheet containing:
- Question number, concise prompt & marks badge
- Core definitions, formulas & Quick Recall points (no long narrative text)
- Scaled Mermaid architecture/flow diagrams
"""

import base64
import io
import re

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Frame,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
    Image as RLImage,
)
from reportlab.pdfgen import canvas

from app.pdf import fonts
from app.pdf.mathrender import MathRenderer

fonts.register_pdf_fonts()

# ─── Color Palette ─────────────────────────────────────────────────────────────
INK = "#0f172a"          # slate 900
HEAD_DARK = "#0f172a"
ACCENT = "#0f766e"       # teal 700
ACCENT_BG = colors.HexColor("#f0fdfa")  # teal 50
BORDER_COLOR = colors.HexColor("#cbd5e1") # slate 300
MUTED = "#64748b"        # slate 500
CODE_INK = "#0f172a"
AMBER = "#d97706"        # amber 600
AMBER_BG = colors.HexColor("#fffbeb")

PAGE_W, PAGE_H = letter
MARGIN_X = 28.0
MARGIN_Y = 32.0
HEADER_H = 22.0
FOOTER_H = 22.0
USABLE_W = PAGE_W - 2 * MARGIN_X
COL_GAP = 14.0
COL_W = (USABLE_W - COL_GAP) / 2  # ~271 pt per column
BODY_H = PAGE_H - MARGIN_Y * 2 - HEADER_H

_BLACKLIST_RE = re.compile(
    r"^(step\s*\d+|given|total\s*outcomes?|favorable\s*outcomes?|outcomes?|total|sample\s*space|example|calculation|dice|coin|note|figure|table|proof|solution|assume|marks?|q\d+|case\s*\d+|where|let|using\s+the\s+formula)",
    re.IGNORECASE,
)

_INLINE_RE = re.compile(
    r"(?P<code>`[^`\n]+?`)"
    r"|(?P<dmath>\$\$[^\n]+?\$\$)"
    r"|(?P<imath>\$[^$\n]+?\$)"
    r"|(?P<pmath>\\\([^\n]+?\\\))"
)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_text(segment: str) -> str:
    s = _escape(segment)
    s = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(?=\S)([^*]+?)(?<=\S)\*", r"<i>\1</i>", s)
    return s


def _fmt_code(code: str) -> str:
    return f'<font face="{fonts.FONT_MONO}" size="7.5" color="{CODE_INK}">{_escape(code)}</font>'


def _img_tag(im, valign: float) -> str:
    src = im.path.replace("\\", "/")
    return f'<img src="{src}" width="{im.width_pt:.2f}" height="{im.height_pt:.2f}" valign="{valign:.2f}"/>'


def inline_markup(text: str, mr: MathRenderer, color_hex: str = INK, size: float = 7.5) -> str:
    """Turn inline Markdown + LaTeX into ReportLab paragraph markup."""
    out = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            out.append(_fmt_text(text[pos:m.start()]))

        if m.group("code"):
            out.append(_fmt_code(m.group("code")[1:-1]))
        else:
            raw = m.group("dmath") or m.group("imath") or m.group("pmath")
            latex = raw
            try:
                im = mr.render_inline(latex, color_hex=color_hex, fontsize=size)
                out.append(_img_tag(im, valign=-im.depth_pt))
            except Exception:
                inner = latex.strip("$")
                if inner.startswith("\\(") and inner.endswith("\\)"):
                    inner = inner[2:-2]
                out.append(_fmt_code(inner))
        pos = m.end()

    if pos < len(text):
        out.append(_fmt_text(text[pos:]))
    return "".join(out)


def _first_sentence(text: str, max_words: int = 18) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"^[:—–-]\s*", "", text).strip()
    match = re.match(r"^([^.?!]+[.?!])(?:\s|$)", cleaned)
    first = match.group(1).strip() if match else cleaned
    words = first.split()
    if len(words) > max_words:
        first = " ".join(words[:max_words]) + "..."
    return first


def extract_quick_recall(raw_content: str, question_text: str = "") -> list[str]:
    if not raw_content:
        return []

    # 1. Explicit Quick Recall block: > **⚡ 2-Min Quick Recall...**
    match = re.search(
        r"(?:^|\n)\s*(?:>\s*)?(?:\*{0,2}|#{1,4}\s*)⚡?\s*(?:2-Min\s+)?Quick\s+Recall[^\n]*\n([\s\S]*?)(?=\n\s*(?:#{1,4}\s+|[A-Z][A-Za-z0-9\s]{2,40}\n={2,}|\n(?![>*-]))|$)",
        raw_content,
        re.IGNORECASE,
    )
    if match and match.group(1):
        lines = []
        for ln in match.group(1).split("\n"):
            cleaned = re.sub(r"^>\s*", "", ln).strip()
            if cleaned and (cleaned.startswith(("-", "*", "•")) or re.match(r"^\d+\.", cleaned)):
                lines.append(re.sub(r"^(?:[-*•]|\d+\.)\s*", "", cleaned).strip())
        if lines:
            return lines

    bq_match = re.search(
        r">\s*\*{0,2}⚡?\s*(?:2-Min\s+)?Quick\s+Recall[^\n]*\*{0,2}\s*\n((?:>\s*[-*•\d].*\n?)+)",
        raw_content,
        re.IGNORECASE,
    )
    if bq_match and bq_match.group(1):
        lines = []
        for ln in bq_match.group(1).split("\n"):
            cleaned = re.sub(r"^>\s*[-*•\d.]*\s*", "", ln).strip()
            if cleaned:
                lines.append(cleaned)
        if lines:
            return lines

    # 2. Fallback: Core Concept + Tables + Key terms
    points = []
    lines = [ln.strip() for ln in raw_content.split("\n") if ln.strip()]

    # 2a. Core concept sentence
    for ln in lines:
        if (
            not ln.startswith(("#", "```", ">", "|", "*", "-"))
            and not re.match(r"^\d+\.", ln)
            and len(ln) > 30
            and re.search(r"\b(is a|is an|is the|refers to|deals with|defined as|measures|models|describes|difference between|two ways to|captures)\b", ln, re.IGNORECASE)
        ):
            first_sent = _first_sentence(ln, 22)
            points.append(f"**Core Concept** — {first_sent}")
            break

    # 2b. Comparison table
    table_rows = [ln for ln in lines if ln.startswith("|") and ln.endswith("|") and "---" not in ln]
    if len(table_rows) >= 2:
        header_cells = [c.strip() for c in table_rows[0].split("|") if c.strip()]
        col_a = header_cells[1] if len(header_cells) > 1 else "Concept A"
        col_b = header_cells[2] if len(header_cells) > 2 else "Concept B"
        for r in table_rows[1:]:
            cells = [c.strip() for c in r.split("|") if c.strip()]
            if len(cells) >= 3:
                aspect = cells[0].strip("*").strip()
                val_a = _first_sentence(cells[1], 10)
                val_b = _first_sentence(cells[2], 10)
                if aspect and val_a and val_b and not _BLACKLIST_RE.match(aspect):
                    points.append(f"**{aspect}** — {col_a}: {val_a} | {col_b}: {val_b}")

    # 2c. Component lines
    term_re = re.compile(r"^(?:[-*•]|\d+\.)?\s*(?:\*\*)?([A-Za-z0-9\s/()_–—\\]{2,35})(?:\*\*)?\s*[:—–-]\s*(.+)$")
    for ln in lines:
        if ln.startswith(("#", "```", "|")):
            continue
        m = term_re.match(ln)
        if m:
            term = m.group(1).strip("*").strip()
            exp = m.group(2).strip()
            if not _BLACKLIST_RE.match(term) and len(term) >= 2 and len(exp) > 5:
                if not any(term.lower() in p.lower() for p in points):
                    points.append(f"**{term}** — {_first_sentence(exp, 15)}")

    if len(points) < 2:
        for ln in lines:
            if re.match(r"^[-*•]\s+", ln):
                clean = re.sub(r"^[-*•]\s+", "", ln).strip()
                bold_m = re.match(r"^\*\*([^*]+)\*\*[:—–-]?\s*(.*)$", clean)
                if bold_m:
                    term = bold_m.group(1).strip()
                    if not _BLACKLIST_RE.match(term) and not any(term.lower() in p.lower() for p in points):
                        points.append(f"**{term}** — {_first_sentence(bold_m.group(2), 15)}")
                elif not _BLACKLIST_RE.match(clean):
                    points.append(_first_sentence(clean, 16))
            if len(points) >= 5:
                break

    return points[:7] if points else ["Key concept reviewed and grounded in study material."]


def extract_mermaid_code(raw_content: str) -> str | None:
    if not raw_content:
        return None
    match = re.search(r"```mermaid\s*\n([\s\S]*?)\n```", raw_content, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _render_mermaid_figure(code: str, st) -> list:
    if not code:
        return []
    try:
        b64 = base64.urlsafe_b64encode(code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{b64}?type=png"
        req = urllib.request.Request(url, headers={"User-Agent": "AcademicStack-Cheatsheet/1.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        png_bytes = resp.read()
        if len(png_bytes) < 200:
            return []
        img_buf = io.BytesIO(png_bytes)
        img = RLImage(img_buf)

        max_w = COL_W - 8
        max_h = 130.0
        iw, ih = img.drawWidth, img.drawHeight
        scale = min(max_w / iw, max_h / ih, 1.0)
        img.drawWidth = iw * scale
        img.drawHeight = ih * scale
        img.hAlign = "CENTER"

        caption = Paragraph("Figure: Flow / Architecture", st.caption)
        return [Spacer(1, 2), img, Spacer(1, 1), caption, Spacer(1, 2)]
    except Exception:
        return []


# ─── Two-Pass Canvas for Header & Footer ──────────────────────────────────────
class CheatsheetCanvas(canvas.Canvas):
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

    def _draw_decorations(self, total_pages):
        self.saveState()

        # Running Top Header
        self.setFont(fonts.FONT_SANS_BOLD, 7.5)
        self.setFillColor(colors.HexColor(ACCENT))
        self.drawString(MARGIN_X, PAGE_H - 20, "AcademicStack • Exam Cheatsheet Companion")

        self.setFont(fonts.FONT_SANS, 7)
        self.setFillColor(colors.HexColor(MUTED))
        self.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 20, f"Page {self._pageNumber} of {total_pages}")

        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(MARGIN_X, PAGE_H - 24, PAGE_W - MARGIN_X, PAGE_H - 24)

        # Running Bottom Footer
        self.line(MARGIN_X, 22, PAGE_W - MARGIN_X, 22)
        self.setFont(fonts.FONT_SANS, 6.5)
        self.drawString(MARGIN_X, 12, "Rapid Recall Printout • Grounded in Syllabus Notes")
        self.drawRightString(PAGE_W - MARGIN_X, 12, "2-Column Compact Edition")

        self.restoreState()


class _Styles:
    def __init__(self):
        self.q_title = ParagraphStyle(
            "QTitle", fontName=fonts.FONT_SANS_BOLD, fontSize=8.2, leading=10.5,
            textColor=colors.HexColor(HEAD_DARK),
        )
        self.q_marks = ParagraphStyle(
            "QMarks", fontName=fonts.FONT_MONO_BOLD, fontSize=7.2, leading=9.0,
            textColor=colors.HexColor(ACCENT), alignment=2,
        )
        self.body_bullet = ParagraphStyle(
            "CheatsheetBullet", fontName=fonts.FONT_SANS, fontSize=7.2, leading=9.5,
            textColor=colors.HexColor(INK), spaceAfter=2,
        )
        self.caption = ParagraphStyle(
            "Caption", fontName=fonts.FONT_SANS, fontSize=6.2, leading=7.5,
            textColor=colors.HexColor(MUTED), alignment=1,
        )


def generate_exam_cheatsheet_pdf(question_bank_name: str, subject: str, answers: list[dict]) -> bytes:
    """Generate a dense 2-column compact formula & diagram cheatsheet PDF."""
    buf = io.BytesIO()
    mr = MathRenderer()
    st = _Styles()

    # Left & Right Column Frames
    frame_left = Frame(
        MARGIN_X, MARGIN_Y, COL_W, BODY_H,
        id="col1", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    frame_right = Frame(
        MARGIN_X + COL_W + COL_GAP, MARGIN_Y, COL_W, BODY_H,
        id="col2", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )

    template = PageTemplate(id="TwoCol", frames=[frame_left, frame_right])
    doc = BaseDocTemplate(
        buf, pagesize=letter, pageTemplates=[template],
        leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=MARGIN_Y, bottomMargin=MARGIN_Y,
    )

    story = []

    # Document Header Card (placed in first column flow)
    header_title = Paragraph(f"<b>{_escape(subject)}</b> • Formula & Concept Cheatsheet", st.q_title)
    header_sub = Paragraph(
        f'<font color="{MUTED}" size="6.8">Bank: {_escape(question_bank_name)} • {len(answers)} Questions Solved</font>',
        st.body_bullet,
    )
    hdr_box = Table([[header_title], [header_sub]], colWidths=[COL_W])
    hdr_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_BG),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(ACCENT)),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr_box)
    story.append(Spacer(1, 6))

    for idx, ans in enumerate(answers, start=1):
        if ans.get("status") != "completed":
            continue

        q_num = ans.get("question_number") or idx
        q_text = ans.get("question_text") or ""
        marks = ans.get("marks") or 0
        raw_content = ans.get("content") or ""

        points = extract_quick_recall(raw_content, q_text)
        mermaid_code = extract_mermaid_code(raw_content)

        card_elements = []

        # Question Title Row
        q_label = f"<b>Q{q_num:02d}.</b> {_escape(q_text[:95])}{'...' if len(q_text) > 95 else ''}"
        left_p = Paragraph(q_label, st.q_title)
        right_p = Paragraph(f"[{marks}M]", st.q_marks)
        q_head_table = Table([[left_p, right_p]], colWidths=[COL_W - 36, 36])
        q_head_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        card_elements.append(q_head_table)

        # Quick Recall Bullet Points
        for pt in points:
            formatted_pt = inline_markup(f"• {pt}", mr, color_hex=INK, size=st.body_bullet.fontSize)
            card_elements.append(Paragraph(formatted_pt, st.body_bullet))

        # Optional Mermaid Diagram
        if mermaid_code:
            diag_flowables = _render_mermaid_figure(mermaid_code, st)
            card_elements.extend(diag_flowables)

        # Divider between question items
        card_elements.append(Spacer(1, 3))
        card_elements.append(HRFlowable(width="100%", thickness=0.4, color=BORDER_COLOR, spaceBefore=2, spaceAfter=4))

        # Use KeepTogether on tightly grouped elements
        story.append(KeepTogether(card_elements))

    doc.build(story, canvasmaker=CheatsheetCanvas)
    mr.cleanup()
    return buf.getvalue()
