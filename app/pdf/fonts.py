"""
Project-owned font registration for PDF generation.

Fonts are bundled under ``app/pdf/assets/fonts`` (DejaVu family — free, fully
redistributable, and Unicode-complete) so rendering is byte-for-byte identical
in development (Windows) and production (Linux/Docker). We deliberately do NOT
probe ``C:/Windows/Fonts`` or any OS font directory: those paths do not exist on
the deployment target and produce a different-looking PDF than the developer sees.

Three families are registered, each with normal / bold / italic / bold-italic
members wired through ``registerFontFamily`` so that ``<b>`` and ``<i>`` markup
inside ReportLab paragraphs resolves to the correct physical font:

    ASSerif  — body text (DejaVu Serif)
    ASSans   — titles, headings, metadata (DejaVu Sans)
    ASMono   — code blocks and ASCII diagrams (DejaVu Sans Mono)

If the bundled TTFs are somehow unavailable, we fall back to the PDF standard
14 fonts (Times / Helvetica / Courier) so PDF generation never hard-fails —
though those lack full Unicode coverage.
"""

import os
import threading

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ─── Registered family + face names ──────────────────────────────────────────
# These names are what the rest of the codebase references. On success they map
# to the bundled DejaVu faces; on fallback they are rebound to the built-in
# standard fonts (which ReportLab already knows how to bold/italicise).
SERIF_FAMILY = "ASSerif"
FONT_SERIF = "ASSerif"
FONT_SERIF_BOLD = "ASSerif-Bold"
FONT_SERIF_ITALIC = "ASSerif-Italic"
FONT_SERIF_BOLDITALIC = "ASSerif-BoldItalic"

SANS_FAMILY = "ASSans"
FONT_SANS = "ASSans"
FONT_SANS_BOLD = "ASSans-Bold"
FONT_SANS_ITALIC = "ASSans-Italic"
FONT_SANS_BOLDITALIC = "ASSans-BoldItalic"

MONO_FAMILY = "ASMono"
FONT_MONO = "ASMono"
FONT_MONO_BOLD = "ASMono-Bold"
FONT_MONO_ITALIC = "ASMono-Italic"
FONT_MONO_BOLDITALIC = "ASMono-BoldItalic"

# True once the bundled TrueType faces are loaded (full Unicode available).
FONTS_READY = False

_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

# Each tuple: (registered name, family, member, ttf filename)
_FONT_SPECS = [
    (FONT_SERIF, SERIF_FAMILY, "normal", "DejaVuSerif.ttf"),
    (FONT_SERIF_BOLD, SERIF_FAMILY, "bold", "DejaVuSerif-Bold.ttf"),
    (FONT_SERIF_ITALIC, SERIF_FAMILY, "italic", "DejaVuSerif-Italic.ttf"),
    (FONT_SERIF_BOLDITALIC, SERIF_FAMILY, "boldItalic", "DejaVuSerif-BoldItalic.ttf"),
    (FONT_SANS, SANS_FAMILY, "normal", "DejaVuSans.ttf"),
    (FONT_SANS_BOLD, SANS_FAMILY, "bold", "DejaVuSans-Bold.ttf"),
    (FONT_SANS_ITALIC, SANS_FAMILY, "italic", "DejaVuSans-Oblique.ttf"),
    (FONT_SANS_BOLDITALIC, SANS_FAMILY, "boldItalic", "DejaVuSans-BoldOblique.ttf"),
    (FONT_MONO, MONO_FAMILY, "normal", "DejaVuSansMono.ttf"),
    (FONT_MONO_BOLD, MONO_FAMILY, "bold", "DejaVuSansMono-Bold.ttf"),
    (FONT_MONO_ITALIC, MONO_FAMILY, "italic", "DejaVuSansMono-Oblique.ttf"),
    (FONT_MONO_BOLDITALIC, MONO_FAMILY, "boldItalic", "DejaVuSansMono-BoldOblique.ttf"),
]

_FAMILY_MEMBERS = {
    SERIF_FAMILY: (FONT_SERIF, FONT_SERIF_BOLD, FONT_SERIF_ITALIC, FONT_SERIF_BOLDITALIC),
    SANS_FAMILY: (FONT_SANS, FONT_SANS_BOLD, FONT_SANS_ITALIC, FONT_SANS_BOLDITALIC),
    MONO_FAMILY: (FONT_MONO, FONT_MONO_BOLD, FONT_MONO_ITALIC, FONT_MONO_BOLDITALIC),
}

_registered = False
_lock = threading.Lock()


def _bind_standard_fallback() -> None:
    """Rebind the exported names to the built-in standard-14 fonts."""
    global SERIF_FAMILY, FONT_SERIF, FONT_SERIF_BOLD, FONT_SERIF_ITALIC, FONT_SERIF_BOLDITALIC
    global SANS_FAMILY, FONT_SANS, FONT_SANS_BOLD, FONT_SANS_ITALIC, FONT_SANS_BOLDITALIC
    global MONO_FAMILY, FONT_MONO, FONT_MONO_BOLD, FONT_MONO_ITALIC, FONT_MONO_BOLDITALIC

    SERIF_FAMILY = "Times-Roman"
    FONT_SERIF, FONT_SERIF_BOLD = "Times-Roman", "Times-Bold"
    FONT_SERIF_ITALIC, FONT_SERIF_BOLDITALIC = "Times-Italic", "Times-BoldItalic"

    SANS_FAMILY = "Helvetica"
    FONT_SANS, FONT_SANS_BOLD = "Helvetica", "Helvetica-Bold"
    FONT_SANS_ITALIC, FONT_SANS_BOLDITALIC = "Helvetica-Oblique", "Helvetica-BoldOblique"

    MONO_FAMILY = "Courier"
    FONT_MONO, FONT_MONO_BOLD = "Courier", "Courier-Bold"
    FONT_MONO_ITALIC, FONT_MONO_BOLDITALIC = "Courier-Oblique", "Courier-BoldOblique"


def register_pdf_fonts() -> bool:
    """
    Register the bundled TrueType fonts with ReportLab. Idempotent and
    thread-safe. Returns True if the Unicode-complete DejaVu faces loaded,
    False if we fell back to the standard-14 fonts.
    """
    global _registered, FONTS_READY

    if _registered:
        return FONTS_READY

    with _lock:
        if _registered:
            return FONTS_READY

        try:
            for name, _family, _member, filename in _FONT_SPECS:
                path = os.path.join(_FONTS_DIR, filename)
                if not os.path.exists(path):
                    raise FileNotFoundError(path)
                pdfmetrics.registerFont(TTFont(name, path))

            for family, (normal, bold, italic, bold_italic) in _FAMILY_MEMBERS.items():
                pdfmetrics.registerFontFamily(
                    family,
                    normal=normal,
                    bold=bold,
                    italic=italic,
                    boldItalic=bold_italic,
                )

            FONTS_READY = True
        except Exception as exc:  # pragma: no cover - defensive fallback
            print(f"[pdf.fonts] Bundled fonts unavailable, using standard fonts: {exc}")
            _bind_standard_fallback()
            FONTS_READY = False

        _registered = True
        return FONTS_READY
