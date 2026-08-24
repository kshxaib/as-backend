"""
PDF generation for solved question banks.

Produces a professionally typeset academic solved-paper PDF from AI-generated
Markdown + LaTeX answer content. The pipeline is:

    Markdown/LaTeX  →  structured block tokens  →  ReportLab flowables

Design goals (see also :mod:`app.pdf.fonts` and :mod:`app.pdf.mathrender`):

* Coherent typography — a small, deliberate font hierarchy built on bundled
  DejaVu faces (identical in dev and prod), with controlled spacing driven by
  paragraph-style ``spaceBefore``/``spaceAfter``/``leading`` rather than a
  scattering of manual ``Spacer`` calls.
* Real math — LaTeX is rasterized by matplotlib mathtext (``\\frac`` is a true
  fraction, ``x^2`` a real superscript), inline glyphs sit on the text baseline.
* Structured Markdown — headings, paragraphs, bold/italic, ordered/unordered
  lists, GFM tables, fenced code, block/inline math, blockquotes. LaTeX is
  extracted *before* any Markdown/XML processing so it is never corrupted.
* Standalone horizontal rules (``---`` / ``***`` / ``___``) are ignored, never
  rendered as lines.

Public API (unchanged): :func:`generate_solved_question_bank_pdf`.
"""

import io
import json
import re
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
    Preformatted,
    KeepTogether,
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

from app.pdf import fonts
from app.pdf.mathrender import MathRenderer

fonts.register_pdf_fonts()


# ─── Palette ──────────────────────────────────────────────────────────────────
INK = "#1e293b"          # body text
HEAD_DARK = "#0f172a"    # titles / strong headings
ACCENT = "#0f766e"       # teal accent (section headings, rules)
MUTED = "#64748b"        # metadata
LINK = "#0284c7"         # sources
CODE_INK = "#0f172a"
CODE_BG = colors.HexColor("#f8fafc")
CODE_BORDER = colors.HexColor("#e2e8f0")
TABLE_HEAD_BG = colors.HexColor("#f1f5f9")
TABLE_GRID = colors.HexColor("#cbd5e1")
TABLE_ALT_BG = colors.HexColor("#f8fafc")

# Deliberate, reused vertical-rhythm steps (points). No ad-hoc spacers elsewhere.
GAP_SM = 4
GAP_MD = 7
GAP_LG = 11

CONTENT_WIDTH = 504.0  # letter (612) minus 54pt margins each side


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas that stamps a running header/footer and page N of M."""

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
        self.setFont(fonts.FONT_SANS, 8)
        self.setFillColor(colors.HexColor(MUTED))

        if self._pageNumber > 1:
            self.drawString(54, 750, "AcademicStack • Solved Question Bank")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)

        self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
        self.drawString(
            54, 32,
            "AcademicStack AI-Assisted Solved Paper • Strictly for Educational Reference",
        )
        self.restoreState()


# ─── Inline text → ReportLab paragraph markup ─────────────────────────────────
# Extract inline code and math BEFORE any Markdown/XML handling so their
# contents are never escaped or mangled.
_INLINE_RE = re.compile(
    r"(?P<code>`[^`\n]+?`)"
    r"|(?P<dmath>\$\$[^\n]+?\$\$)"
    r"|(?P<imath>\$[^$\n]+?\$)"
    r"|(?P<pmath>\\\([^\n]+?\\\))"
)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_text(segment: str) -> str:
    """Escape prose then apply bold/italic. Underscores are left alone so that
    identifiers like ``my_var`` are not turned into emphasis."""
    s = _escape(segment)
    s = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(?=\S)([^*]+?)(?<=\S)\*", r"<i>\1</i>", s)
    return s


def _fmt_code(code: str) -> str:
    return f'<font face="{fonts.FONT_MONO}" size="9" color="{CODE_INK}">{_escape(code)}</font>'


def _img_tag(im, valign: float) -> str:
    src = im.path.replace("\\", "/")
    return f'<img src="{src}" width="{im.width_pt:.2f}" height="{im.height_pt:.2f}" valign="{valign:.2f}"/>'


def inline_markup(text: str, mr: MathRenderer, color_hex: str = INK, size: float = 10.0) -> str:
    """Turn a run of inline Markdown+LaTeX into ReportLab paragraph markup."""
    out: list[str] = []
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


# ─── Block tokenizer ──────────────────────────────────────────────────────────
_HR_RE = re.compile(r"^([-*_])\1{2,}$")           # 3+ of the same rule char
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_ULIST_RE = re.compile(r"^([-*+•])\s+(.*)$")
_OLIST_RE = re.compile(r"^(\d+)[.)]\s+(.*)$")
_BOLD_LINE_RE = re.compile(r"^\*\*(.+)\*\*$")


def _is_table_sep(line: str) -> bool:
    s = line.strip()
    return bool(re.match(r"^\|?[\s:|-]+\|?$", s)) and "-" in s and "|" in s


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def tokenize_blocks(text: str) -> list[tuple]:
    """Parse answer Markdown into a flat list of ``(kind, payload...)`` blocks.

    Kinds: ``heading`` (level, text), ``subheading`` (text), ``para`` (text),
    ``list`` (items[(ordered, level, text)]), ``table`` (raw_text),
    ``code`` (lang, code), ``mathblock`` (latex), ``quote`` (text).
    """
    lines = text.replace("\r\n", "\n").split("\n")
    blocks: list[tuple] = []
    i, n = 0, len(lines)

    while i < n:
        raw = lines[i]
        line = raw.strip()

        if not line:
            i += 1
            continue

        # Fenced code / diagram
        if line.startswith("```") or line.startswith("~~~"):
            fence = line[:3]
            lang = line[3:].strip().lower()
            buf, j = [], i + 1
            while j < n and not lines[j].strip().startswith(fence):
                buf.append(lines[j])
                j += 1
            blocks.append(("code", lang, "\n".join(buf)))
            i = j + 1
            continue

        # Display math: $$ ... $$  or  \[ ... \]  (single or multi-line)
        for open_d, close_d in (("$$", "$$"), ("\\[", "\\]")):
            if line.startswith(open_d):
                if line.endswith(close_d) and len(line) > len(open_d) + len(close_d) - 1:
                    inner = line[len(open_d):len(line) - len(close_d)]
                    blocks.append(("mathblock", inner.strip()))
                    i += 1
                else:
                    buf, j = [line[len(open_d):]], i + 1
                    while j < n and close_d not in lines[j]:
                        buf.append(lines[j])
                        j += 1
                    if j < n:
                        tail = lines[j]
                        buf.append(tail[:tail.find(close_d)])
                        j += 1
                    blocks.append(("mathblock", "\n".join(buf).strip()))
                    i = j
                break
        else:
            # Standalone horizontal rule → ignore entirely
            if _HR_RE.match(line):
                i += 1
                continue

            # Heading
            h = _HEADING_RE.match(line)
            if h:
                blocks.append(("heading", len(h.group(1)), h.group(2).strip()))
                i += 1
                continue

            # Table (needs a separator row directly under the header row)
            if "|" in raw and i + 1 < n and _is_table_sep(lines[i + 1]):
                buf, j = [raw], i + 1
                while j < n and "|" in lines[j] and lines[j].strip():
                    buf.append(lines[j])
                    j += 1
                blocks.append(("table", "\n".join(buf)))
                i = j
                continue

            # Blockquote
            if line.startswith(">"):
                buf, j = [], i
                while j < n and lines[j].strip().startswith(">"):
                    buf.append(re.sub(r"^\s*>\s?", "", lines[j]))
                    j += 1
                blocks.append(("quote", " ".join(s.strip() for s in buf if s.strip())))
                i = j
                continue

            # List (unordered / ordered, with simple nesting by indent)
            if _ULIST_RE.match(line) or _OLIST_RE.match(line):
                items, j = [], i
                while j < n:
                    cur = lines[j]
                    cs = cur.strip()
                    if not cs:
                        # allow a single blank line only if the next line continues the list
                        if j + 1 < n and (_ULIST_RE.match(lines[j + 1].strip()) or _OLIST_RE.match(lines[j + 1].strip())):
                            j += 1
                            continue
                        break
                    mu = _ULIST_RE.match(cs)
                    mo = _OLIST_RE.match(cs)
                    if not mu and not mo:
                        break
                    level = min(_leading_spaces(cur) // 2, 3)
                    if mu:
                        items.append((None, level, mu.group(2).strip()))
                    else:
                        items.append((mo.group(1), level, mo.group(2).strip()))
                    j += 1
                blocks.append(("list", items))
                i = j
                continue

            # Paragraph: gather consecutive lines until a blank line or a line
            # that begins a different block.
            buf, j = [line], i + 1
            while j < n:
                nxt = lines[j]
                ns = nxt.strip()
                if not ns:
                    break
                if (ns.startswith("```") or ns.startswith("~~~") or ns.startswith("$$")
                        or ns.startswith("\\[") or _HEADING_RE.match(ns) or _HR_RE.match(ns)
                        or _ULIST_RE.match(ns) or _OLIST_RE.match(ns) or ns.startswith(">")
                        or ("|" in nxt and j + 1 < n and _is_table_sep(lines[j + 1]))):
                    break
                buf.append(ns)
                j += 1
            para = " ".join(buf).strip()
            bl = _BOLD_LINE_RE.match(para)
            if bl:
                blocks.append(("subheading", bl.group(1).strip()))
            else:
                blocks.append(("para", para))
            i = j

    return blocks


# ─── Block renderers ──────────────────────────────────────────────────────────
def _render_code(lang: str, code: str, st) -> list:
    code = code.rstrip("\n")
    if not code.strip():
        return []

    lines = code.split("\n")
    flowables = []

    # Diagram DSLs (mermaid / graphviz) can't be rendered as pictures here, so
    # show them clearly as labeled source, per product decision.
    if lang in ("mermaid", "dot", "graphviz"):
        flowables.append(Paragraph(f"Diagram source ({lang})", st.caption))

    # Fit the monospace font so the widest line does not clip (preserves ASCII
    # diagram alignment without wrapping).
    base = 8.5
    longest = max((pdfmetrics.stringWidth(ln, fonts.FONT_MONO, base) for ln in lines), default=0.0)
    avail = CONTENT_WIDTH - 16  # cell padding
    size = base
    if longest > avail and longest > 0:
        size = max(6.0, base * (avail / longest))
    code_style = ParagraphStyle(
        "CodeBlock", fontName=fonts.FONT_MONO, fontSize=size,
        leading=size * 1.25, textColor=colors.HexColor(CODE_INK),
    )

    box = Table([[Preformatted(code, code_style)]], colWidths=[CONTENT_WIDTH])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, CODE_BORDER),
        ("LINELEFT", (0, 0), (-1, -1), 2.5, colors.HexColor(ACCENT)),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    flowables.append(box)
    return [Spacer(1, GAP_SM), KeepTogether(flowables), Spacer(1, GAP_MD)]


def _render_table(raw: str, mr: MathRenderer, st) -> list:
    rows_txt = [l for l in raw.split("\n") if l.strip()]
    parsed: list[list[str]] = []
    for line in rows_txt:
        if _is_table_sep(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        parsed.append(cells)
    if len(parsed) < 1:
        return []

    ncols = max(len(r) for r in parsed)
    data = []
    for r_idx, cells in enumerate(parsed):
        while len(cells) < ncols:
            cells.append("")
        style = st.table_head if r_idx == 0 else st.table_cell
        data.append([Paragraph(inline_markup(c, mr, color_hex=INK, size=style.fontSize), style) for c in cells])

    if ncols == 2:
        col_widths = [CONTENT_WIDTH * 0.3, CONTENT_WIDTH * 0.7]
    elif ncols == 3:
        col_widths = [CONTENT_WIDTH * 0.24, CONTENT_WIDTH * 0.38, CONTENT_WIDTH * 0.38]
    elif ncols == 4:
        col_widths = [CONTENT_WIDTH * 0.18] + [CONTENT_WIDTH * 0.82 / 3] * 3
    else:
        col_widths = [CONTENT_WIDTH / ncols] * ncols

    table = Table(data, colWidths=col_widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEAD_BG),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(INK)),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for r_idx in range(1, len(data)):
        if r_idx % 2 == 0:
            cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), TABLE_ALT_BG))
    table.setStyle(TableStyle(cmds))
    return [Spacer(1, GAP_SM), table, Spacer(1, GAP_MD)]


def _render_mathblock(latex: str, mr: MathRenderer, st) -> list:
    disp = mr.render_display(latex, color_hex=HEAD_DARK, fontsize=12.5)
    inner: list = []
    for k, f in enumerate(disp):
        if k > 0:
            inner.append(Spacer(1, 2))
        inner.append(f)
    return [Spacer(1, GAP_SM), KeepTogether(inner), Spacer(1, GAP_MD)]


def _render_list(items: list, mr: MathRenderer, st) -> list:
    flowables = []
    for marker, level, text in items:
        ordered = marker is not None
        style = st.list_ordered if ordered else st.list_item
        base_indent = 14 + level * 14
        istyle = ParagraphStyle(
            f"li{level}{'o' if ordered else 'u'}", parent=style,
            leftIndent=base_indent, bulletIndent=base_indent - 12,
        )
        markup = inline_markup(text, mr, color_hex=INK, size=style.fontSize)
        bullet = f"{marker}." if ordered else "•"
        flowables.append(Paragraph(markup, istyle, bulletText=bullet))
    return flowables


def render_blocks(blocks: list[tuple], mr: MathRenderer, st) -> list:
    out: list = []
    for block in blocks:
        kind = block[0]
        if kind == "heading":
            _, level, text = block
            if level <= 3:
                style, color = st.h_section, ACCENT
            else:
                style, color = st.h_sub, HEAD_DARK
            out.append(Paragraph(inline_markup(text, mr, color_hex=color, size=style.fontSize), style))
        elif kind == "subheading":
            out.append(Paragraph(inline_markup(block[1], mr, color_hex=HEAD_DARK, size=st.h_sub.fontSize), st.h_sub))
        elif kind == "para":
            out.append(Paragraph(inline_markup(block[1], mr, color_hex=INK, size=st.body.fontSize), st.body))
        elif kind == "list":
            out.extend(_render_list(block[1], mr, st))
        elif kind == "table":
            out.extend(_render_table(block[1], mr, st))
        elif kind == "code":
            out.extend(_render_code(block[1], block[2], st))
        elif kind == "mathblock":
            out.extend(_render_mathblock(block[1], mr, st))
        elif kind == "quote":
            out.append(_render_quote(block[1], mr, st))
    return out


def _render_quote(text: str, mr: MathRenderer, st):
    para = Paragraph(inline_markup(text, mr, color_hex=MUTED, size=st.quote.fontSize), st.quote)
    box = Table([[para]], colWidths=[CONTENT_WIDTH])
    box.setStyle(TableStyle([
        ("LINELEFT", (0, 0), (-1, -1), 2.5, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return box


# ─── Style sheet ────────────────────────────────────────────────────────────
class _Styles:
    def __init__(self):
        self.brand = ParagraphStyle(
            "Brand", fontName=fonts.FONT_SANS_BOLD, fontSize=10.5, leading=13,
            textColor=colors.HexColor(ACCENT), spaceAfter=2,
        )
        self.title = ParagraphStyle(
            "Title", fontName=fonts.FONT_SANS_BOLD, fontSize=18, leading=22,
            textColor=colors.HexColor(HEAD_DARK), spaceAfter=2,
        )
        self.subtitle = ParagraphStyle(
            "Subtitle", fontName=fonts.FONT_SANS, fontSize=9, leading=12.5,
            textColor=colors.HexColor(MUTED),
        )
        self.disclaimer = ParagraphStyle(
            "Disclaimer", fontName=fonts.FONT_SANS, fontSize=8, leading=11,
            textColor=colors.HexColor("#b91c1c"),
        )
        self.q_title = ParagraphStyle(
            "QTitle", fontName=fonts.FONT_SANS_BOLD, fontSize=11.5, leading=15,
            textColor=colors.HexColor(HEAD_DARK),
        )
        self.q_marks = ParagraphStyle(
            "QMarks", fontName=fonts.FONT_SANS_BOLD, fontSize=10, leading=15,
            textColor=colors.HexColor(ACCENT), alignment=2,
        )
        self.h_section = ParagraphStyle(
            "HSection", fontName=fonts.FONT_SANS_BOLD, fontSize=11.5, leading=15,
            textColor=colors.HexColor(ACCENT), spaceBefore=GAP_LG, spaceAfter=GAP_SM,
            keepWithNext=True,
        )
        self.h_sub = ParagraphStyle(
            "HSub", fontName=fonts.FONT_SANS_BOLD, fontSize=10.5, leading=14,
            textColor=colors.HexColor(HEAD_DARK), spaceBefore=GAP_MD, spaceAfter=3,
            keepWithNext=True,
        )
        self.body = ParagraphStyle(
            "Body", fontName=fonts.FONT_SERIF, fontSize=10, leading=15,
            textColor=colors.HexColor(INK), spaceAfter=GAP_MD, alignment=0,
        )
        self.list_item = ParagraphStyle(
            "ListItem", fontName=fonts.FONT_SERIF, fontSize=10, leading=14.5,
            textColor=colors.HexColor(INK), spaceAfter=3,
        )
        self.list_ordered = ParagraphStyle(
            "ListOrdered", parent=self.list_item,
        )
        self.quote = ParagraphStyle(
            "Quote", fontName=fonts.FONT_SERIF_ITALIC, fontSize=10, leading=14.5,
            textColor=colors.HexColor(MUTED),
        )
        self.caption = ParagraphStyle(
            "Caption", fontName=fonts.FONT_SANS, fontSize=8, leading=11,
            textColor=colors.HexColor(MUTED), spaceAfter=2,
        )
        self.table_cell = ParagraphStyle(
            "TableCell", fontName=fonts.FONT_SERIF, fontSize=8.5, leading=12,
            textColor=colors.HexColor(INK),
        )
        self.table_head = ParagraphStyle(
            "TableHead", fontName=fonts.FONT_SANS_BOLD, fontSize=9, leading=12,
            textColor=colors.HexColor(HEAD_DARK),
        )
        self.source = ParagraphStyle(
            "Source", fontName=fonts.FONT_SANS, fontSize=8.5, leading=11.5,
            textColor=colors.HexColor(LINK),
        )


# ─── Main entry point ─────────────────────────────────────────────────────────
def generate_solved_question_bank_pdf(
    question_bank_name: str,
    subject: str,
    answers: list[dict],
) -> bytes:
    fonts.register_pdf_fonts()
    st = _Styles()
    mr = MathRenderer()

    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            leftMargin=54, rightMargin=54, topMargin=60, bottomMargin=55,
            title=f"{subject} - {question_bank_name}", author="AcademicStack",
        )

        story: list = []

        # 1. Brand header
        story.append(Paragraph("ACADEMICSTACK SOLUTIONS", st.brand))
        story.append(Paragraph(f"{_escape(subject)} — {_escape(question_bank_name)}", st.title))
        story.append(Paragraph(
            f"Generated on {datetime.utcnow().strftime('%B %d, %Y')} • RAG Grounded & AI Verified Answer Set",
            st.subtitle,
        ))
        story.append(Spacer(1, GAP_MD))

        # 2. Disclaimer callout
        disclaimer = (
            "<b>Notice:</b> This document contains AI-generated examination solutions grounded in verified "
            "study materials. It is designed to assist exam preparation, conceptual clarity, and revision."
        )
        disc_box = Table([[Paragraph(disclaimer, st.disclaimer)]], colWidths=[CONTENT_WIDTH])
        disc_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fca5a5")),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(disc_box)
        story.append(Spacer(1, GAP_MD))

        # 3. Stats strip
        total_q = len(answers)
        total_marks = sum(int(a.get("marks") or 0) for a in answers)
        stats = [[
            Paragraph(f"<b>Total Questions:</b> {total_q}", st.subtitle),
            Paragraph(f"<b>Total Marks:</b> {total_marks}", st.subtitle),
            Paragraph(f"<b>Subject:</b> {_escape(subject)}", st.subtitle),
        ]]
        stats_table = Table(stats, colWidths=[CONTENT_WIDTH / 3] * 3)
        stats_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, CODE_BORDER),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, GAP_MD))
        story.append(HRFlowable(width="100%", thickness=1, color=TABLE_GRID, spaceAfter=GAP_MD))

        # 4. Per-question sections
        for index, ans in enumerate(answers, start=1):
            q_num = ans.get("question_number", index)
            q_text = ans.get("question_text", "Untitled Question")
            marks = ans.get("marks", 0)
            content = ans.get("content") or "*Answer not generated.*"

            raw_sources = ans.get("sources") or []
            if isinstance(raw_sources, str):
                try:
                    sources_list = json.loads(raw_sources)
                except Exception:
                    sources_list = []
            else:
                sources_list = raw_sources

            # Question header box
            q_box = Table(
                [[
                    Paragraph(f"Q{q_num}. {inline_markup(str(q_text), mr, color_hex=HEAD_DARK, size=st.q_title.fontSize)}", st.q_title),
                    Paragraph(f"[{marks} Marks]", st.q_marks),
                ]],
                colWidths=[CONTENT_WIDTH - 84, 84],
            )
            q_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),
                ("PADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#99f6e4")),
            ]))
            story.append(KeepTogether([q_box, Spacer(1, GAP_SM)]))

            # Answer body
            blocks = tokenize_blocks(content)
            story.extend(render_blocks(blocks, mr, st))

            # Sources footer
            if sources_list:
                labels = []
                for s in sources_list:
                    res = s.get("resource_name", "Material")
                    p = s.get("page", "")
                    ch = s.get("chapter", "")
                    label = f"{res} (Pg {p})" if p and p != "N/A" else res
                    if ch and ch != "General":
                        label += f" • {ch}"
                    labels.append(label)
                story.append(Spacer(1, GAP_SM))
                story.append(Paragraph(f"<b>Verified Sources:</b> {_escape(', '.join(labels))}", st.source))

            story.append(Spacer(1, GAP_MD))
            story.append(HRFlowable(width="100%", thickness=0.5, color=CODE_BORDER, spaceAfter=GAP_MD))

        doc.build(story, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer.getvalue()
    finally:
        mr.cleanup()
