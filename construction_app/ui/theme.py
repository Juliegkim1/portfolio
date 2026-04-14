"""
iOS-style design system for the construction app.
Colors follow iOS 17 Human Interface Guidelines.
Fonts use Open Sans (variable font).
"""
import os
from pathlib import Path
from kivy.core.text import LabelBase
from kivy.metrics import dp

FONTS_DIR = Path(__file__).parent / "fonts"

# Register Open Sans variable font
_FONT_REGULAR = str(FONTS_DIR / "OpenSans-Variable.ttf")
_FONT_ITALIC = str(FONTS_DIR / "OpenSans-Italic-Variable.ttf")

if os.path.exists(_FONT_REGULAR):
    LabelBase.register(
        name="OpenSans",
        fn_regular=_FONT_REGULAR,
        fn_italic=_FONT_ITALIC if os.path.exists(_FONT_ITALIC) else _FONT_REGULAR,
    )
    FONT = "OpenSans"
else:
    FONT = "Roboto"  # Kivy built-in fallback

# ── iOS Color Palette ─────────────────────────────────────────────────────────

# Backgrounds
BG_PRIMARY      = (1,    1,    1,    1)      # #FFFFFF — main screen background
BG_SECONDARY    = (0.949, 0.949, 0.969, 1)  # #F2F2F7 — grouped list bg / card bg
BG_TERTIARY     = (1,    1,    1,    1)      # #FFFFFF — inset cards

# Labels
LABEL_PRIMARY   = (0,    0,    0,    1)      # #000000
LABEL_SECONDARY = (0.557, 0.557, 0.576, 1)  # #8E8E93
LABEL_TERTIARY  = (0.776, 0.776, 0.784, 1)  # #C6C6C8

# iOS system colors
IOS_BLUE        = (0,    0.478, 1,    1)     # #007AFF — primary action
IOS_GREEN       = (0.204, 0.78, 0.349, 1)   # #34C759 — success / paid
IOS_ORANGE      = (1,    0.584, 0,    1)     # #FF9500 — warning / pending
IOS_RED         = (1,    0.231, 0.188, 1)   # #FF3B30 — destructive / overdue
IOS_PURPLE      = (0.686, 0.322, 0.871, 1)  # #AF52DE — Stripe
IOS_TEAL        = (0.188, 0.690, 0.780, 1)  # #30B0C7 — finance / quicken
IOS_INDIGO      = (0.345, 0.337, 0.839, 1)  # #5856D6

# Separators / borders
SEPARATOR       = (0.776, 0.776, 0.784, 0.5) # subtle line
BORDER          = (0.776, 0.776, 0.784, 1)

WHITE           = (1, 1, 1, 1)
TRANSPARENT     = (0, 0, 0, 0)

# Status → color mapping
STATUS_COLOR = {
    "active":      IOS_GREEN,
    "completed":   LABEL_SECONDARY,
    "on_hold":     IOS_ORANGE,
    "draft":       LABEL_SECONDARY,
    "sent":        IOS_BLUE,
    "accepted":    IOS_GREEN,
    "rejected":    IOS_RED,
    "paid":        IOS_GREEN,
    "open":        IOS_ORANGE,
    "void":        IOS_RED,
    "uncollectible": IOS_RED,
    "not_started": LABEL_SECONDARY,
    "in_progress": IOS_ORANGE,
    "Pending":     IOS_ORANGE,
    "Paid":        IOS_GREEN,
    "Overdue":     IOS_RED,
}

# ── Layout constants ──────────────────────────────────────────────────────────
NAV_HEIGHT   = dp(56)
TAB_HEIGHT   = dp(49)   # iOS tab bar standard
CARD_RADIUS  = dp(12)
BTN_HEIGHT   = dp(50)
ROW_HEIGHT   = dp(60)
INPUT_HEIGHT = dp(44)
PADDING      = dp(16)
SMALL_PAD    = dp(8)
