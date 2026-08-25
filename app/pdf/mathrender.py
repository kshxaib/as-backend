"""
LaTeX math → image rendering for the PDF pipeline.

Every formula is rendered to a real raster image via matplotlib's ``mathtext``
engine (no external LaTeX install, Linux-safe, deterministic) and embedded into
the PDF. This means ``\\frac{a}{b}`` renders as an actual stacked fraction,
``x^2`` as a true superscript, ``\\sum_{i=1}^{n}`` with proper limits — never as
lossy Unicode approximations like ``(a / b)``.

Two public entry points, both on :class:`MathRenderer` (which owns a scratch
directory and a render cache for one document build):

* ``render_inline(latex, ...)``  → ``InlineMath(path, width_pt, height_pt, depth_pt)``
  for embedding in a paragraph via ReportLab's ``<img>`` tag. ``depth_pt`` is the
  descent below the text baseline, used as a negative ``valign`` so the glyphs
  sit on the baseline exactly.

* ``render_display(latex, ...)`` → ``list[Flowable]`` — centered block equations.

``mathtext`` cannot parse the ``cases``/matrix/``align`` families, so those are
detected and composed from individually-rendered cells laid out in ReportLab
tables with vector brace/bracket delimiters.
"""

import io
import os
import re
import shutil
import tempfile
import threading
from collections import namedtuple

import numpy as np
from PIL import Image as PILImage

from matplotlib.mathtext import MathTextParser
from matplotlib.font_manager import FontProperties

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Flowable, Image, Table, TableStyle, Paragraph

from app.pdf import fonts

# Resolution for math rasters. High enough to stay crisp when the PDF is zoomed
# or printed; the display size is set separately in points so this only affects
# sharpness, not layout.
_DPI = 300

_PARSER = MathTextParser("agg")
# mathtext's parser holds mutable state; serialize access in case PDF builds run
# in a thread pool.
_PARSE_LOCK = threading.Lock()

InlineMath = namedtuple("InlineMath", ["path", "width_pt", "height_pt", "depth_pt"])
# A composed cell plus its measured natural size, so tables can be given
# explicit column widths (ReportLab's auto-sizing mis-handles narrow images).
_Cell = namedtuple("_Cell", ["flow", "w", "h"])

_ENV_RE = re.compile(r"\\begin\{(?P<env>[a-zA-Z*]+)\}(?P<body>.*?)\\end\{(?P=env)\}", re.DOTALL)

_MATRIX_DELIMS = {
    "matrix": (None, None),
    "bmatrix": ("[", "]"),
    "pmatrix": ("(", ")"),
    "Bmatrix": ("{", "}"),
    "vmatrix": ("|", "|"),
    "Vmatrix": ("|", "|"),
}
_MULTILINE_ENVS = {"align", "align*", "aligned", "gather", "gather*", "gathered", "multline", "multline*", "eqnarray", "eqnarray*", "split"}


def _px_to_pt(px: float) -> float:
    return px * 72.0 / _DPI


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def strip_delimiters(s: str) -> str:
    """Remove surrounding $$, $, \\[ \\], \\( \\) math delimiters."""
    s = s.strip()
    for open_d, close_d in (("$$", "$$"), ("\\[", "\\]"), ("\\(", "\\)"), ("$", "$")):
        if s.startswith(open_d) and s.endswith(close_d) and len(s) > len(open_d) + len(close_d) - 1:
            return s[len(open_d): len(s) - len(close_d)].strip()
    return s


def linearize_environments(s: str) -> str:
    """Rewrite matrix/cases environments into a compact single-line form that
    mathtext *can* parse (``\\left[ 1\\; 0 ;\\, 0\\; 1 \\right]``), for use in
    inline math where a true 2-D layout cannot be embedded. Display math uses
    the richer table builders instead."""
    def repl(m):
        env = m.group("env")
        rows = [r.strip() for r in re.split(r"\\{2,}", m.group("body")) if r.strip()]
        if env == "cases":
            body = " ;\\, ".join(" \\quad ".join(c.strip() for c in r.split("&")) for r in rows)
            return r"\left\{ " + body + r" \right."
        body = " ;\\, ".join(" \\; ".join(c.strip() for c in r.split("&")) for r in rows)
        if env == "bmatrix":
            return r"\left[ " + body + r" \right]"
        if env == "pmatrix":
            return r"\left( " + body + r" \right)"
        if env == "Bmatrix":
            return r"\left\{ " + body + r" \right\}"
        if env in ("vmatrix", "Vmatrix"):
            return r"\left| " + body + r" \right|"
        return body

    return _ENV_RE.sub(repl, s)


# ─── Vector delimiter flowables ──────────────────────────────────────────────
class _Delimiter(Flowable):
    """A single vector delimiter (brace / bracket / paren / bar) of a given height."""

    def __init__(self, kind: str, height: float, color, width: float = 6.0, thickness: float = 0.9):
        super().__init__()
        self.kind = kind
        self.height = height
        self.color = color
        self.width = width
        self.thickness = thickness

    def wrap(self, avail_w, avail_h):
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness)
        c.setLineJoin(1)
        c.setLineCap(1)
        k = self.kind

        if k in ("[", "]"):
            serif = w * 0.7
            p = c.beginPath()
            if k == "[":
                p.moveTo(w, h); p.lineTo(w - serif, h)
                p.lineTo(w - serif, 0); p.lineTo(w, 0)
            else:
                p.moveTo(0, h); p.lineTo(serif, h)
                p.lineTo(serif, 0); p.lineTo(0, 0)
            c.drawPath(p, stroke=1, fill=0)
        elif k == "|":
            x = w / 2.0
            c.line(x, 0, x, h)
        elif k in ("(", ")"):
            p = c.beginPath()
            if k == "(":
                p.moveTo(w, h)
                p.curveTo(w - w * 1.4, h * 0.72, w - w * 1.4, h * 0.28, w, 0)
            else:
                p.moveTo(0, h)
                p.curveTo(w * 1.4, h * 0.72, w * 1.4, h * 0.28, 0, 0)
            c.drawPath(p, stroke=1, fill=0)
        elif k in ("{", "}"):
            self._draw_brace(c, w, h, opening_right=(k == "{"))

    def _draw_brace(self, c, w, h, opening_right: bool):
        # A curly brace with a central cusp and two symmetric arms.
        mid = h / 2.0
        bump = w * 0.9
        p = c.beginPath()
        if opening_right:
            # tips on the right, cusp points left at mid-height
            p.moveTo(w, h)
            p.curveTo(w - bump, h, w - bump * 0.6, mid + mid * 0.18, 0, mid)
            p.curveTo(w - bump * 0.6, mid - mid * 0.18, w - bump, 0, w, 0)
        else:
            p.moveTo(0, h)
            p.curveTo(bump, h, bump * 0.6, mid + mid * 0.18, w, mid)
            p.curveTo(bump * 0.6, mid - mid * 0.18, bump, 0, 0, 0)
        c.drawPath(p, stroke=1, fill=0)


class MathRenderer:
    """Renders LaTeX to images for a single PDF build. Call :meth:`cleanup` after."""

    def __init__(self):
        self._dir = tempfile.mkdtemp(prefix="asmath_")
        self._counter = 0
        self._cache: dict[tuple, InlineMath] = {}
        self._fallback_style = ParagraphStyle(
            "MathFallback",
            fontName=fonts.FONT_MONO,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0f172a"),
        )

    # -- lifecycle -------------------------------------------------------------
    def cleanup(self):
        shutil.rmtree(self._dir, ignore_errors=True)

    def _next_path(self) -> str:
        self._counter += 1
        return os.path.join(self._dir, f"m{self._counter}.png")

    # -- core raster -----------------------------------------------------------
    def _render_mathtext(self, latex: str, color_hex: str, fontsize: float) -> InlineMath:
        """Rasterize a single mathtext-parseable expression. Raises on parse error."""
        # In (La)TeX/mathtext ``%`` starts a comment, which would silently drop
        # the rest of the line. In academic formulas ``%`` almost always means
        # "percent" (e.g. ``\times 100%``), so escape any unescaped ``%``.
        latex = re.sub(r"(?<!\\)%", r"\\%", latex)
        key = ("mt", latex, color_hex, round(fontsize, 2))
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        prop = FontProperties(size=fontsize)
        with _PARSE_LOCK:
            res = _PARSER.parse(f"${latex}$", dpi=_DPI, prop=prop)

        alpha = np.asarray(res.image)
        if alpha.ndim != 2:
            raise ValueError("unexpected mathtext raster shape")
        h_px, w_px = alpha.shape

        r, g, b = _hex_to_rgb(color_hex)
        rgba = np.empty((h_px, w_px, 4), dtype=np.uint8)
        rgba[..., 0] = r
        rgba[..., 1] = g
        rgba[..., 2] = b
        rgba[..., 3] = alpha

        path = self._next_path()
        PILImage.fromarray(rgba, mode="RGBA").save(path, format="PNG")

        result = InlineMath(
            path=path,
            width_pt=_px_to_pt(w_px),
            height_pt=_px_to_pt(h_px),
            depth_pt=_px_to_pt(res.depth),
        )
        self._cache[key] = result
        return result

    # -- public: inline --------------------------------------------------------
    def render_inline(self, latex: str, color_hex: str = "#1e293b", fontsize: float = 10.0) -> InlineMath:
        """Render inline math. Raises if the expression is not mathtext-parseable.

        A matrix/cases environment inside inline math cannot be laid out 2-D
        within a paragraph, so it is first collapsed to a compact bracketed row
        form (``[1 0; 0 1]``) that mathtext renders as a single image.
        """
        body = strip_delimiters(latex)
        if "\\begin{" in body:
            body = linearize_environments(body)
        return self._render_mathtext(body, color_hex, fontsize)

    def _image_flowable(self, im: InlineMath, align: str = "CENTER") -> Image:
        img = Image(im.path, width=im.width_pt, height=im.height_pt)
        img.hAlign = align
        return img

    # -- public: display -------------------------------------------------------
    def render_display(self, latex: str, color_hex: str = "#0f172a", fontsize: float = 12.5) -> list:
        """Render block/display math, returning a list of centered flowables.

        Handles the ``cases`` / matrix / multi-line environments that mathtext
        cannot parse on its own; falls back to monospace text only if a cell is
        itself unparseable.
        """
        body = strip_delimiters(latex)
        env_match = _ENV_RE.search(body)

        try:
            if env_match:
                env = env_match.group("env")
                if env == "cases":
                    return [self._build_cases(body, env_match, color_hex, fontsize)]
                if env in _MATRIX_DELIMS:
                    return [self._build_matrix(body, env_match, env, color_hex, fontsize)]
                if env in _MULTILINE_ENVS:
                    return self._build_multiline(env_match.group("body"), color_hex, fontsize)
            # Plain display expression. It may have been soft-wrapped across
            # lines by the model, or hold several formula lines separated by
            # ``\\``; mathtext handles neither, so normalise here: split on
            # explicit ``\\`` breaks and collapse stray whitespace/newlines
            # within each line into single spaces.
            flowables = []
            for row in self._split_rows(body) or [body]:
                line = " ".join(row.split())
                if not line:
                    continue
                flowables.append(self._image_flowable(self._render_mathtext(line, color_hex, fontsize)))
            if not flowables:
                raise ValueError("empty display math")
            return flowables
        except Exception:
            return [self._fallback_flowable(body)]

    def _fallback_flowable(self, text: str):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, self._fallback_style)

    def _cell(self, latex: str, color_hex: str, fontsize: float, align: str = "LEFT") -> _Cell:
        """Render one math sub-expression as a measured cell (image, or text fallback)."""
        latex = latex.strip()
        if not latex:
            return _Cell(Paragraph("", self._fallback_style), 0.0, 12.0)
        try:
            im = self._render_mathtext(latex, color_hex, fontsize)
            return _Cell(self._image_flowable(im, align=align), im.width_pt, im.height_pt)
        except Exception:
            safe = latex.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            w = pdfmetrics.stringWidth(latex, self._fallback_style.fontName, self._fallback_style.fontSize)
            return _Cell(Paragraph(safe, self._fallback_style), w, self._fallback_style.leading)

    def _split_rows(self, body: str) -> list[str]:
        return [r.strip() for r in re.split(r"\\{2,}", body) if r.strip()]

    def _assemble(self, grid: list[list[_Cell]], col_gaps: list[float], align: str, row_pad: float = 3.0):
        """Build a table from measured cells using explicit column widths.

        Padding is baked into the column widths (cell padding is zero) so the
        table never derives a width smaller than its image content. Returns
        ``(table, total_width, total_height)``.
        """
        ncols = max(len(r) for r in grid)
        col_w = [0.0] * ncols
        for row in grid:
            for ci, cell in enumerate(row):
                col_w[ci] = max(col_w[ci], cell.w)
        col_widths = [col_w[ci] + (col_gaps[ci] if ci < len(col_gaps) else 0.0) + 1.0 for ci in range(ncols)]

        data = []
        for row in grid:
            cells = [c.flow for c in row]
            while len(cells) < ncols:
                cells.append(Paragraph("", self._fallback_style))
            data.append(cells)

        table = Table(data, colWidths=col_widths, hAlign="CENTER")
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), align),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), row_pad),
            ("BOTTOMPADDING", (0, 0), (-1, -1), row_pad),
        ]))
        total_w = sum(col_widths)
        total_h = table.wrap(total_w, 100_000)[1]
        return table, total_w, total_h

    def _wrap_outer(self, cells: list[_Cell], align_row: str = "CENTER"):
        """Lay out prefix / delimiter / structure / suffix cells side by side."""
        col_widths = [c.w + 3.0 for c in cells]
        table = Table([[c.flow for c in cells]], colWidths=col_widths, hAlign=align_row)
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return table

    # -- cases -----------------------------------------------------------------
    def _build_cases(self, body: str, env_match, color_hex: str, fontsize: float):
        prefix = body[: env_match.start()].strip()
        suffix = body[env_match.end():].strip()
        rows = self._split_rows(env_match.group("body"))

        grid = []
        for row in rows:
            parts = row.split("&", 1)
            expr = self._cell(parts[0], color_hex, fontsize, align="LEFT")
            cond = self._cell(parts[1], color_hex, fontsize, align="LEFT") if len(parts) > 1 else _Cell(Paragraph("", self._fallback_style), 0.0, 12.0)
            grid.append([expr, cond])
        if not grid:
            grid = [[_Cell(Paragraph("", self._fallback_style), 0.0, 12.0)] * 2]

        inner, inner_w, inner_h = self._assemble(grid, col_gaps=[16.0, 0.0], align="LEFT")
        color = colors.HexColor(color_hex)
        brace = _Delimiter("{", inner_h, color, width=7.0)

        cells = []
        if prefix:
            cells.append(self._cell(prefix, color_hex, fontsize, align="LEFT"))
        cells.append(_Cell(brace, brace.width, inner_h))
        cells.append(_Cell(inner, inner_w, inner_h))
        if suffix:
            cells.append(self._cell(suffix, color_hex, fontsize, align="LEFT"))
        return self._wrap_outer(cells)

    # -- matrices --------------------------------------------------------------
    def _build_matrix(self, body: str, env_match, env: str, color_hex: str, fontsize: float):
        prefix = body[: env_match.start()].strip()
        suffix = body[env_match.end():].strip()
        rows = self._split_rows(env_match.group("body"))

        grid = []
        for row in rows:
            grid.append([self._cell(c, color_hex, fontsize, align="CENTER") for c in row.split("&")])
        if not grid:
            grid = [[_Cell(Paragraph("", self._fallback_style), 0.0, 12.0)]]
        ncols = max(len(r) for r in grid)

        inner, inner_w, inner_h = self._assemble(grid, col_gaps=[12.0] * ncols, align="CENTER")
        color = colors.HexColor(color_hex)
        left_kind, right_kind = _MATRIX_DELIMS.get(env, (None, None))

        cells = []
        if prefix:
            cells.append(self._cell(prefix, color_hex, fontsize, align="LEFT"))
        if left_kind:
            d = _Delimiter(left_kind, inner_h, color, width=5.0)
            cells.append(_Cell(d, d.width, inner_h))
        cells.append(_Cell(inner, inner_w, inner_h))
        if right_kind:
            d = _Delimiter(right_kind, inner_h, color, width=5.0)
            cells.append(_Cell(d, d.width, inner_h))
        if suffix:
            cells.append(self._cell(suffix, color_hex, fontsize, align="LEFT"))
        return self._wrap_outer(cells)

    # -- multi-line (align / gather / ...) ------------------------------------
    def _build_multiline(self, env_body: str, color_hex: str, fontsize: float) -> list:
        flowables = []
        for row in self._split_rows(env_body):
            line = row.replace("&", " ").strip()
            if not line:
                continue
            try:
                flowables.append(self._image_flowable(self._render_mathtext(line, color_hex, fontsize)))
            except Exception:
                flowables.append(self._fallback_flowable(line))
        if not flowables:
            flowables.append(self._fallback_flowable(env_body))
        return flowables
