"""Cover / landing screen shown on app launch."""
import os

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp

from ui.theme import (FONT, LABEL_PRIMARY, LABEL_SECONDARY, WHITE, PADDING)
from ui.widgets import with_bg, ios_label, ios_button, shadow_card

_LOGO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "images", "Cabrera Construction logo.png"))

# ── Brand colors ──────────────────────────────────────────────────────────────
BRAND_DARK  = (0.10, 0.22, 0.36, 1)   # deep navy
BRAND_MID   = (0.14, 0.30, 0.50, 1)   # mid-blue
ACCENT      = (0.96, 0.61, 0.15, 1)   # warm gold

FEATURES = [
    ("📋", "Projects",
     "Track every job from first call to final sign-off — status, address, customer info, and timeline in one place."),
    ("📊", "Estimates",
     "Build detailed line-item estimates by section (Demo, Materials, Labor) with automatic totals, tax, permits, and discount."),
    ("💵", "Invoices & Payments",
     "Create professional invoices, push them to Stripe for online payment, and sync payment status back automatically."),
    ("📁", "Documents",
     "Generate polished PDF estimates, invoices, reconciliation reports, and project summaries — saved locally and synced to Google Cloud Storage."),
    ("📈", "Finance",
     "Full project reconciliation: total estimated vs. invoiced vs. paid, with a one-tap balance-due report."),
]


class CoverScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BRAND_DARK)

        # ── Hero header ───────────────────────────────────────────────────────
        hero = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(200),
                          padding=[dp(20), dp(24), dp(20), dp(16)], spacing=dp(8))
        with_bg(hero, BRAND_DARK)

        if os.path.exists(_LOGO_PATH):
            # White badge behind the logo — its wordmark is dark text meant
            # for a light background, illegible directly on the navy hero.
            logo_badge = BoxLayout(size_hint=(None, None), size=(dp(183), dp(66)),
                                    pos_hint={"center_x": 0.5}, padding=[dp(16), dp(10)])
            with logo_badge.canvas.before:
                Color(1, 1, 1, 1)
                _logo_bg = RoundedRectangle(radius=[dp(12)], pos=logo_badge.pos,
                                             size=logo_badge.size)
            logo_badge.bind(
                pos=lambda w, *a: setattr(_logo_bg, 'pos', w.pos),
                size=lambda w, *a: setattr(_logo_bg, 'size', w.size),
            )
            logo = Image(source=_LOGO_PATH, size_hint=(None, None),
                         size=(dp(151), dp(46)), fit_mode="contain",
                         pos_hint={"center_x": 0.5, "center_y": 0.5})
            logo_badge.add_widget(logo)
            hero.add_widget(logo_badge)
        else:
            hero.add_widget(Label(text="CABRERA CONSTRUCTION",
                                   font_name=FONT, font_size=dp(20), bold=True,
                                   color=WHITE, halign="center",
                                   size_hint_y=None, height=dp(34)))

        tagline = Label(
            text="Professional Construction Management",
            font_name=FONT, font_size=dp(13), color=(0.80, 0.88, 1.0, 1),
            halign="center", size_hint_y=None, height=dp(22))
        tagline.bind(size=tagline.setter("text_size"))
        hero.add_widget(tagline)

        root.add_widget(hero)

        # ── Divider ───────────────────────────────────────────────────────────
        div = BoxLayout(size_hint_y=None, height=dp(3))
        with_bg(div, ACCENT)
        root.add_widget(div)

        # ── Scrollable body ───────────────────────────────────────────────────
        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", size_hint_y=None,
                          padding=[dp(16), dp(18), dp(16), dp(24)], spacing=dp(12))
        body.bind(minimum_height=body.setter("height"))

        # About blurb
        blurb_card = shadow_card(padding=[dp(16), dp(14)], spacing=dp(6))
        blurb_title = Label(
            text="Built for Cabrera Construction",
            font_name=FONT, font_size=dp(15), bold=True,
            color=BRAND_DARK, halign="left", valign="middle",
            size_hint_y=None, height=dp(24))
        blurb_title.bind(size=blurb_title.setter("text_size"))
        blurb_card.add_widget(blurb_title)

        blurb_text = (
            "A mobile-first app that manages the full lifecycle of every "
            "construction project — from creating the first estimate to "
            "collecting the final payment. All project data, documents, and "
            "financials live in one place and are accessible from any device."
        )
        blurb = Label(
            text=blurb_text,
            font_name=FONT, font_size=dp(13), color=LABEL_PRIMARY,
            halign="left", valign="top",
            size_hint_y=None, text_size=(dp(330), None))
        blurb.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        blurb_card.add_widget(blurb)
        body.add_widget(blurb_card)

        # Feature cards
        feat_title = Label(
            text="WHAT YOU CAN DO",
            font_name=FONT, font_size=dp(11), bold=True,
            color=(0.75, 0.82, 0.95, 1), halign="left",
            size_hint_y=None, height=dp(22))
        feat_title.bind(size=feat_title.setter("text_size"))
        body.add_widget(feat_title)

        for icon, title, desc in FEATURES:
            body.add_widget(self._feature_card(icon, title, desc))

        # CTA button
        cta = ios_button("View Projects  →", color=ACCENT,
                          text_color=(0.10, 0.10, 0.10, 1),
                          height=dp(56), font_size=16, bold=True)
        cta.bind(on_press=lambda *a: setattr(self.manager, "current", "home"))
        body.add_widget(cta)

        # Version footer
        ver = Label(text="Cabrera Construction · v1.0",
                     font_name=FONT, font_size=dp(11),
                     color=(0.55, 0.65, 0.80, 1), halign="center",
                     size_hint_y=None, height=dp(30))
        ver.bind(size=ver.setter("text_size"))
        body.add_widget(ver)

        scroll.add_widget(body)
        root.add_widget(scroll)
        self.add_widget(root)

    def _feature_card(self, icon, title, desc):
        card = shadow_card(padding=[dp(14), dp(10)], spacing=dp(4))

        header = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(8))

        icon_lbl = Label(text=icon, font_size=dp(18),
                          size_hint_x=None, width=dp(28),
                          size_hint_y=None, height=dp(26))
        header.add_widget(icon_lbl)

        title_lbl = Label(text=title, font_name=FONT, font_size=dp(14),
                           bold=True, color=BRAND_DARK, halign="left",
                           valign="middle", size_hint_y=None, height=dp(26))
        title_lbl.bind(size=title_lbl.setter("text_size"))
        header.add_widget(title_lbl)
        card.add_widget(header)

        desc_lbl = Label(text=desc, font_name=FONT, font_size=dp(12),
                          color=LABEL_SECONDARY, halign="left", valign="top",
                          size_hint_y=None, text_size=(dp(320), None))
        desc_lbl.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        card.add_widget(desc_lbl)
        return card
