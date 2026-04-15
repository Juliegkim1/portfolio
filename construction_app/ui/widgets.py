"""Reusable iOS-style Kivy widgets."""
import calendar as _cal_mod
from datetime import date as _date, datetime as _datetime

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line
from kivy.metrics import dp
from kivy.clock import Clock

from ui.theme import (FONT, BG_PRIMARY, BG_SECONDARY, IOS_BLUE, IOS_RED,
                       LABEL_PRIMARY, LABEL_SECONDARY, BORDER, WHITE,
                       CARD_RADIUS, NAV_HEIGHT, BTN_HEIGHT, INPUT_HEIGHT,
                       PADDING, SMALL_PAD, SEPARATOR)


# ── Background helpers ────────────────────────────────────────────────────────

def with_bg(widget, color, radius=0):
    """Draw a flat background on a widget's canvas.before."""
    with widget.canvas.before:
        c = Color(*color)
        if radius:
            rect = RoundedRectangle(radius=[radius], pos=widget.pos, size=widget.size)
        else:
            rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda *a: setattr(rect, 'pos', widget.pos),
                size=lambda *a: setattr(rect, 'size', widget.size))
    return widget


def shadow_card(padding=PADDING, spacing=SMALL_PAD):
    """White rounded card with a subtle drop-shadow underneath."""
    c = BoxLayout(orientation="vertical", size_hint_y=None,
                  padding=padding, spacing=spacing)
    with c.canvas.before:
        Color(0.72, 0.72, 0.78, 0.20)
        _sh = RoundedRectangle(radius=[CARD_RADIUS])
        Color(1, 1, 1, 1)
        _bg = RoundedRectangle(radius=[CARD_RADIUS])

    def _upd(*a):
        _sh.pos = (c.x + dp(1), c.y - dp(3))
        _sh.size = c.size
        _bg.pos = c.pos
        _bg.size = c.size

    c.bind(pos=_upd, size=_upd, minimum_height=c.setter('height'))
    return c


# ── Typography ────────────────────────────────────────────────────────────────

def ios_label(text, size=15, bold=False, color=None, halign="left", **kwargs):
    color = color or LABEL_PRIMARY
    lbl = Label(text=text, font_name=FONT, font_size=dp(size), bold=bold,
                color=color, halign=halign, valign="middle", **kwargs)
    lbl.bind(size=lbl.setter('text_size'))
    return lbl


def section_header(text):
    """Gray uppercase section label (like iOS grouped list headers)."""
    return ios_label(text.upper(), size=11, bold=True, color=LABEL_SECONDARY,
                     size_hint_y=None, height=dp(24))


# ── Buttons ───────────────────────────────────────────────────────────────────

def ios_button(text, color=None, text_color=WHITE, height=BTN_HEIGHT,
               radius=CARD_RADIUS, font_size=16, bold=True, **kwargs):
    """Filled rounded button."""
    color = color or IOS_BLUE
    btn = Button(text=text, font_name=FONT, font_size=dp(font_size), bold=bold,
                 color=text_color, background_color=(0, 0, 0, 0),
                 background_normal='', size_hint_y=None, height=height, **kwargs)
    with btn.canvas.before:
        c = Color(*color)
        rect = RoundedRectangle(radius=[radius], pos=btn.pos, size=btn.size)
    btn.bind(pos=lambda *a: setattr(rect, 'pos', btn.pos),
             size=lambda *a: setattr(rect, 'size', btn.size))
    return btn


def outline_button(text, color=None, height=dp(40), radius=dp(8),
                   font_size=13, bold=False, **kwargs):
    """White button with colored border and text — secondary action style."""
    color = color or IOS_BLUE
    btn = Button(text=text, font_name=FONT, font_size=dp(font_size), bold=bold,
                 color=color, background_color=(0, 0, 0, 0),
                 background_normal='', size_hint_y=None, height=height, **kwargs)
    with btn.canvas.before:
        Color(1, 1, 1, 1)
        _bg = RoundedRectangle(radius=[radius], pos=btn.pos, size=btn.size)
        Color(*color)
        _line = Line(rounded_rectangle=(btn.x, btn.y, btn.width, btn.height, float(radius)),
                     width=dp(1.2))

    def _upd(*a):
        _bg.pos = btn.pos
        _bg.size = btn.size
        _line.rounded_rectangle = (btn.x, btn.y, btn.width, btn.height, float(radius))

    btn.bind(pos=_upd, size=_upd)
    return btn


# ── Inputs ────────────────────────────────────────────────────────────────────

def ios_input(hint="", text="", height=INPUT_HEIGHT, **kwargs):
    ti = TextInput(hint_text=hint, text=text, multiline=False,
                   font_name=FONT, font_size=dp(15),
                   background_color=(0.94, 0.94, 0.96, 1),
                   foreground_color=(0, 0, 0, 1),
                   hint_text_color=(0.56, 0.56, 0.58, 1),
                   cursor_color=IOS_BLUE,
                   size_hint_y=None, height=height,
                   padding=[dp(12), dp(10)], **kwargs)
    return ti


# ── Badges ────────────────────────────────────────────────────────────────────

def status_badge(text, color):
    """Small soft-colored pill badge."""
    badge = Label(text=text, font_name=FONT, font_size=dp(10), bold=True,
                   color=color, size_hint=(None, None), size=(dp(82), dp(22)),
                   halign="center", valign="middle")
    badge.bind(size=badge.setter('text_size'))
    with badge.canvas.before:
        Color(color[0], color[1], color[2], 0.13)
        _r = RoundedRectangle(radius=[dp(11)], pos=badge.pos, size=badge.size)
    badge.bind(pos=lambda *a: setattr(_r, 'pos', badge.pos),
               size=lambda *a: setattr(_r, 'size', badge.size))
    return badge


# ── Navigation bar ────────────────────────────────────────────────────────────

def nav_bar(title, back_label="Back", on_back=None, right_widget=None):
    """iOS-style navigation bar — white with title centered."""
    bar = BoxLayout(size_hint_y=None, height=NAV_HEIGHT,
                    padding=[PADDING, dp(8)], spacing=SMALL_PAD)
    with_bg(bar, WHITE)

    # Bottom separator
    sep = BoxLayout(size_hint=(1, None), height=dp(1))
    with_bg(sep, SEPARATOR)

    wrapper = BoxLayout(orientation="vertical", size_hint_y=None,
                        height=NAV_HEIGHT + dp(1))
    wrapper.add_widget(bar)
    wrapper.add_widget(sep)

    if on_back:
        back_btn = Button(text=f"‹ {back_label}", font_name=FONT, font_size=dp(16),
                          color=IOS_BLUE, background_color=(0, 0, 0, 0),
                          background_normal='', size_hint_x=None, width=dp(110))
        back_btn.bind(on_press=on_back)
        bar.add_widget(back_btn)

    title_lbl = Label(text=title, font_name=FONT, font_size=dp(17), bold=True,
                       color=LABEL_PRIMARY, halign="center")
    bar.add_widget(title_lbl)

    if right_widget:
        bar.add_widget(right_widget)
    elif on_back:
        bar.add_widget(Label(size_hint_x=None, width=dp(110)))  # balance spacer

    return wrapper, title_lbl


# ── Toast ─────────────────────────────────────────────────────────────────────

def show_toast(msg, duration=2.0):
    popup = Popup(
        title="", content=Label(text=msg, font_name=FONT, font_size=dp(14),
                                 color=WHITE, halign="center"),
        size_hint=(0.78, None), height=dp(72),
        background_color=(0.1, 0.1, 0.1, 0.88),
        separator_height=0, title_size=0,
    )
    popup.open()
    Clock.schedule_once(lambda dt: popup.dismiss(), duration)


# ── Calendar date picker ─────────────────────────────────────────────────────

class DatePickerPopup:
    """iOS-style month-grid date picker popup."""

    def __init__(self, on_date, initial_date=None):
        self._on_date = on_date
        today = _date.today()
        self._today = today
        self._selected = None
        if initial_date:
            try:
                d = _datetime.strptime(initial_date, "%Y-%m-%d").date()
                self._year, self._month = d.year, d.month
                self._selected = d
            except Exception:
                self._year, self._month = today.year, today.month
        else:
            self._year, self._month = today.year, today.month
        self._popup = None
        self._month_label = None
        self._grid_container = None

    def open(self):
        wrapper = BoxLayout(orientation="vertical", spacing=0)
        with_bg(wrapper, WHITE)

        # ── Month / year header ──────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=dp(52),
                           padding=[dp(8), dp(8)])
        with_bg(header, WHITE)

        prev_btn = Button(text="‹", font_name=FONT, font_size=dp(24),
                          color=IOS_BLUE, background_color=(0, 0, 0, 0),
                          background_normal="", size_hint_x=None, width=dp(44))
        next_btn = Button(text="›", font_name=FONT, font_size=dp(24),
                          color=IOS_BLUE, background_color=(0, 0, 0, 0),
                          background_normal="", size_hint_x=None, width=dp(44))
        self._month_label = Label(text="", font_name=FONT, font_size=dp(16),
                                   bold=True, color=LABEL_PRIMARY, halign="center")
        header.add_widget(prev_btn)
        header.add_widget(self._month_label)
        header.add_widget(next_btn)
        wrapper.add_widget(header)

        sep = BoxLayout(size_hint_y=None, height=dp(1))
        with_bg(sep, (0.88, 0.88, 0.88, 1))
        wrapper.add_widget(sep)

        # ── Day-of-week row ──────────────────────────────────────────────────
        dow_row = BoxLayout(size_hint_y=None, height=dp(28),
                            padding=[dp(4), 0])
        for d in ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]:
            dow_row.add_widget(Label(text=d, font_name=FONT, font_size=dp(11),
                                     bold=True, color=LABEL_SECONDARY,
                                     halign="center", valign="middle"))
        wrapper.add_widget(dow_row)

        # ── Calendar grid ────────────────────────────────────────────────────
        self._grid_container = BoxLayout(orientation="vertical",
                                          size_hint_y=None,
                                          padding=[dp(4), dp(4), dp(4), dp(4)],
                                          spacing=dp(2))
        wrapper.add_widget(self._grid_container)

        # ── Cancel button ────────────────────────────────────────────────────
        btn_row = BoxLayout(size_hint_y=None, height=dp(56),
                            padding=[dp(16), dp(6)])
        with_bg(btn_row, WHITE)
        cancel_btn = outline_button("Cancel", color=LABEL_SECONDARY, height=dp(44))

        self._popup = Popup(
            title="", content=wrapper,
            size_hint=(0.88, None), height=dp(430),
            background="", background_color=(0, 0, 0, 0),
            separator_height=0, title_size=0,
        )
        cancel_btn.bind(on_press=self._popup.dismiss)
        btn_row.add_widget(cancel_btn)
        wrapper.add_widget(btn_row)

        prev_btn.bind(on_press=lambda *a: self._nav(-1))
        next_btn.bind(on_press=lambda *a: self._nav(1))

        self._render_grid()
        self._popup.open()

    def _nav(self, delta):
        month = self._month + delta
        year = self._year
        if month > 12:
            month, year = 1, year + 1
        elif month < 1:
            month, year = 12, year - 1
        self._year, self._month = year, month
        self._render_grid()

    def _render_grid(self):
        self._month_label.text = _date(self._year, self._month, 1).strftime("%B %Y")
        self._grid_container.clear_widgets()

        weeks = _cal_mod.monthcalendar(self._year, self._month)
        self._grid_container.height = dp(42) * len(weeks) + dp(8)

        for week in weeks:
            row = BoxLayout(size_hint_y=None, height=dp(42))
            for day in week:
                if day == 0:
                    row.add_widget(Label(text=""))
                else:
                    d = _date(self._year, self._month, day)
                    is_sel = d == self._selected
                    is_today = d == self._today

                    cell = BoxLayout()
                    if is_sel:
                        with cell.canvas.before:
                            _c = Color(*IOS_BLUE)
                            _r = RoundedRectangle(radius=[dp(20)])
                        def _upd(w, *a, r=_r):
                            side = min(w.width, w.height) * 0.78
                            r.size = (side, side)
                            r.pos = (w.x + (w.width - side) / 2,
                                     w.y + (w.height - side) / 2)
                        cell.bind(pos=_upd, size=_upd)
                        txt_color = WHITE
                    elif is_today:
                        with cell.canvas.before:
                            _c = Color(0.82, 0.90, 1.0, 1)
                            _r = RoundedRectangle(radius=[dp(20)])
                        def _upd(w, *a, r=_r):
                            side = min(w.width, w.height) * 0.78
                            r.size = (side, side)
                            r.pos = (w.x + (w.width - side) / 2,
                                     w.y + (w.height - side) / 2)
                        cell.bind(pos=_upd, size=_upd)
                        txt_color = IOS_BLUE
                    else:
                        txt_color = LABEL_PRIMARY

                    btn = Button(
                        text=str(day), font_name=FONT, font_size=dp(14),
                        bold=is_sel, color=txt_color,
                        background_color=(0, 0, 0, 0),
                        background_normal="",
                    )
                    btn.bind(on_press=lambda b, d2=d: self._select(d2))
                    cell.add_widget(btn)
                    row.add_widget(cell)
            self._grid_container.add_widget(row)

    def _select(self, d):
        self._selected = d
        self._on_date(d.strftime("%Y-%m-%d"))
        if self._popup:
            self._popup.dismiss()


def date_input(hint="YYYY-MM-DD", text="", height=INPUT_HEIGHT):
    """Returns (container BoxLayout, TextInput).  Container = TextInput + calendar icon."""
    container = BoxLayout(size_hint_y=None, height=height, spacing=dp(6))
    ti = ios_input(hint=hint, text=text, height=height)

    cal_btn = Button(
        text="▦", font_name=FONT, font_size=dp(18),
        color=IOS_BLUE, background_color=(0, 0, 0, 0),
        background_normal="", size_hint_x=None, width=height,
    )

    def _open_picker(*a):
        DatePickerPopup(
            on_date=lambda s: setattr(ti, "text", s),
            initial_date=ti.text.strip() or None,
        ).open()

    cal_btn.bind(on_press=_open_picker)
    container.add_widget(ti)
    container.add_widget(cal_btn)
    return container, ti


# ── Edit popup ────────────────────────────────────────────────────────────────

def edit_form_popup(title, fields_config, on_save, prefill=None):
    """Generic edit popup with white background, black text inputs."""
    wrapper = BoxLayout(orientation="vertical", spacing=0, padding=0)
    with_bg(wrapper, WHITE)

    # Title bar
    title_bar = BoxLayout(size_hint_y=None, height=dp(52),
                           padding=[dp(16), dp(8)])
    with_bg(title_bar, WHITE)
    title_bar.add_widget(Label(text=title, font_name=FONT, font_size=dp(17),
                                bold=True, color=(0, 0, 0, 1),
                                halign="center", valign="middle"))
    wrapper.add_widget(title_bar)

    sep = BoxLayout(size_hint_y=None, height=dp(1))
    with_bg(sep, (0.88, 0.88, 0.88, 1))
    wrapper.add_widget(sep)

    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))
    with_bg(content, WHITE)
    fields = {}

    scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
    inner = BoxLayout(orientation="vertical", spacing=dp(8),
                      size_hint_y=None, padding=[0, 0, 0, dp(8)])
    inner.bind(minimum_height=inner.setter('height'))

    for lbl, key, hint, _ in fields_config:
        is_date = "date" in key.lower()
        row_h = dp(72) if is_date else dp(68)
        row = BoxLayout(orientation="vertical", size_hint_y=None,
                        height=row_h, spacing=dp(4))
        with_bg(row, WHITE)
        lbl_w = Label(text=lbl, font_name=FONT, font_size=dp(12),
                       color=(0.4, 0.4, 0.4, 1), halign="left", valign="middle",
                       size_hint_y=None, height=dp(20))
        lbl_w.bind(size=lbl_w.setter('text_size'))
        row.add_widget(lbl_w)

        prefill_val = str(prefill.get(key, "") if prefill else "")
        if is_date:
            container, ti = date_input(hint=hint, text=prefill_val, height=dp(44))
            row.add_widget(container)
        else:
            ti = TextInput(
                hint_text=hint,
                text=prefill_val,
                multiline=False, font_name=FONT, font_size=dp(15),
                foreground_color=(0, 0, 0, 1),
                hint_text_color=(0.6, 0.6, 0.6, 1),
                background_color=(0.94, 0.94, 0.96, 1),
                cursor_color=IOS_BLUE,
                size_hint_y=None, height=dp(40),
                padding=[dp(10), dp(10)],
            )
            row.add_widget(ti)
        fields[key] = ti
        inner.add_widget(row)

    scroll.add_widget(inner)
    content.add_widget(scroll)

    btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10),
                         padding=[dp(16), dp(4)])
    with_bg(btn_row, WHITE)

    popup = Popup(title="", content=wrapper,
                   size_hint=(0.92, 0.88),
                   background="", background_color=(0, 0, 0, 0),
                   separator_height=0, title_size=0)

    cancel_btn = outline_button("Cancel", color=LABEL_SECONDARY, height=dp(44))
    cancel_btn.bind(on_press=popup.dismiss)

    save_btn = ios_button("Save", color=IOS_BLUE, height=dp(44))

    def _save(*a):
        data = {k: v.text.strip() for k, v in fields.items()}
        on_save(data)
        popup.dismiss()

    save_btn.bind(on_press=_save)
    btn_row.add_widget(cancel_btn)
    btn_row.add_widget(save_btn)

    wrapper.add_widget(content)
    wrapper.add_widget(btn_row)
    return popup
