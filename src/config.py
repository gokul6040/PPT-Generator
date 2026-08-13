import os
from pathlib import Path

from dotenv import load_dotenv
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

# Load .env from app folder or parent PPT-Working folder
_APP_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_APP_DIR / ".env")
load_dotenv(_APP_DIR.parent / ".env")

# Paths (logs only — PPT files live in Azure Blob)
TOKEN_USAGE_XLSX = "logs/token_usage.xlsx"

# Azure Blob Storage (required)
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "turnb-ppt").strip()
AZURE_STORAGE_TEMPLATE_BLOB = os.getenv(
    "AZURE_STORAGE_TEMPLATE_BLOB", "templates/sample_template.pptx"
).strip()
BLOB_PREFIX_GENERATED = "generated"
BLOB_PREFIX_UPLOADS = "uploads"

# ── TurnB brand colors (do not introduce other colors) ──────────────────────
TEAL_PRIMARY = RGBColor(0x02, 0x84, 0x82)   # #028482
TEAL_ACCENT = RGBColor(0x05, 0xA3, 0x9B)      # #05A39B
TEAL_BRIGHT = RGBColor(0x0A, 0xC9, 0xBB)      # #0AC9BB
TEAL_DARK = RGBColor(0x01, 0x83, 0x81)        # #018381
BLACK = RGBColor(0x00, 0x00, 0x00)            # #000000
LIGHT_GREY = RGBColor(0xEC, 0xEC, 0xEC)       # #ECECEC

# Slide text placement — tune these to match your template's grey heading bar
# Widescreen slide: 13.33" x 7.5"
# Title zone: spans the full grey banner (diamond edge → before TurnB logo)
SLIDE_WIDTH = Inches(13.333)
TITLE_X = Inches(1.15)           # inner edge of grey banner after diamond
TITLE_RIGHT_END = Inches(10.85)  # hard stop before TurnB logo
TITLE_Y = Inches(0.31)           # top of grey banner
TITLE_BAR_H = Inches(0.58)       # fixed — matches grey strip height exactly
TITLE_W = TITLE_RIGHT_END - TITLE_X

HEADING_X = Inches(0.6)
HEADING_Y = Inches(1.2)
HEADING_W = Inches(12.0)
HEADING_H = Inches(0.5)

BODY_X = Inches(0.7)
BODY_Y = Inches(1.85)
BODY_W = Inches(12.0)
BODY_H = Inches(4.9)

# Two-section slide layout — top half (first section)
TWO_SEC_TOP_HEADING_X = Inches(0.60)
TWO_SEC_TOP_HEADING_Y = Inches(1.10)
TWO_SEC_TOP_HEADING_W = Inches(12.0)
TWO_SEC_TOP_HEADING_H = Inches(0.40)
TWO_SEC_TOP_BODY_X = Inches(0.70)
TWO_SEC_TOP_BODY_Y = Inches(1.55)
TWO_SEC_TOP_BODY_W = Inches(12.0)
TWO_SEC_TOP_BODY_H = Inches(2.00)

# Two-section slide layout — bottom half (second section)
TWO_SEC_BOT_HEADING_X = Inches(0.60)
TWO_SEC_BOT_HEADING_Y = Inches(3.85)
TWO_SEC_BOT_HEADING_W = Inches(12.0)
TWO_SEC_BOT_HEADING_H = Inches(0.40)
TWO_SEC_BOT_BODY_X = Inches(0.70)
TWO_SEC_BOT_BODY_Y = Inches(4.30)
TWO_SEC_BOT_BODY_W = Inches(12.0)
TWO_SEC_BOT_BODY_H = Inches(2.10)

# Legacy layout constants (tests / docs); slide_fit.py uses height-based packing
MAX_BULLETS_PER_SINGLE_SECTION_SLIDE = 6
MAX_BULLETS_PER_TWO_SECTION_HALF = 3
MAX_WORDS_PER_BULLET = 18
CHARS_PER_BODY_LINE = 95
MAX_LINES_PER_SINGLE_SECTION_SLIDE = 14
MAX_WORDS_PER_SINGLE_SECTION_SLIDE = 120
MAX_LINES_PER_TWO_SECTION_HALF = 6
MAX_WORDS_PER_TWO_SECTION_HALF = 65
ORPHAN_CONTINUATION_MAX_BULLETS = 3
ORPHAN_CONTINUATION_MAX_WORDS = 60

# Fonts — match template typography
TITLE_FONT = "Segoe UI"
HEADING_FONT = "Segoe UI"
BODY_FONT = "Segoe UI"
QUOTE_FONT = "Segoe UI"

TITLE_FONT_SIZE = Pt(24)
HEADING_FONT_SIZE = Pt(14)
BODY_FONT_SIZE = Pt(12)
MIN_BODY_FONT_SIZE = Pt(9)

# Visual gap between body blocks (Label: text rows) — rendered as space_after in PPT
BODY_PARAGRAPH_SPACE_AFTER = Pt(10)


def _estimate_slide_text_capacity() -> tuple[int, int]:
    """
    Estimate per-slide body budget.

    Returns (max_chars, gap_char_cost):
    - max_chars: total vertical budget in character-equivalents
    - gap_char_cost: how much each inter-block gap consumes from that budget
    """
    width_in = BODY_W.inches
    height_in = BODY_H.inches
    font_pt = BODY_FONT_SIZE.pt
    char_width_in = (font_pt / 72.0) * 0.52
    chars_per_line = max(50, int(width_in / char_width_in))
    line_height_pt = font_pt * 1.2
    line_height_in = line_height_pt / 72.0
    max_lines = max(10, int(height_in / line_height_in))

    max_chars = int(chars_per_line * max_lines * 0.82)
    gap_char_cost = int(chars_per_line * (BODY_PARAGRAPH_SPACE_AFTER.pt / line_height_pt))
    return max_chars, gap_char_cost


# max_chars = total slide budget; text_fitter subtracts gap_char_cost per block boundary
MAX_CHARS_PER_SLIDE, BODY_GAP_CHAR_COST = _estimate_slide_text_capacity()

# LLM provider selection
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()

# Azure Anthropic / Claude Messages API
AZURE_ANTHROPIC_ENDPOINT = os.getenv("AZURE_ANTHROPIC_ENDPOINT", "").strip()
AZURE_ANTHROPIC_API_KEY = os.getenv("AZURE_ANTHROPIC_API_KEY", "").strip()
AZURE_ANTHROPIC_MODEL = os.getenv(
    "AZURE_ANTHROPIC_MODEL", "claude-sonnet-4-6"
).strip()
AZURE_ANTHROPIC_API_VERSION = os.getenv(
    "AZURE_ANTHROPIC_API_VERSION", "2023-06-01"
).strip()
AZURE_ANTHROPIC_MAX_TOKENS = int(
    os.getenv("AZURE_ANTHROPIC_MAX_TOKENS", "4096")
)

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT_NAME = (
    os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    or os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
)
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# OpenAI fallback
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
