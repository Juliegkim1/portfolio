"""Reusable iOS-style Kivy widgets."""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock

from ui.theme import (FONT, BG_PRIMARY, BG_SECONDARY, IOS_BLUE, IOS_RED,
                       LABEL_PRIMARY, LABEL_SECONDARY, BORDER, WHITE,
                       CARD_RADIUS, NAV_HEIGHT, BTN_HEIGHT, INPUT_HEIGHT,
                       PADDING, SMALL_PAD, SEPARATOR)


def with_bg(widget, color, radius=0):
    """Draw a background color on a widget's canvas.before."""
    with widget.canvas.before:
        c = Color(*color)
        if radius:
            rect = RoundedRectangle(radius=[radius], pos=widget.pos, size=widget.size)
        else:
            rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(pos=lambda *a: setattr(rect, 'pos', widget.pos),
                size=lambda *a: setattr(rect, 'size', widget.size))
    return widget


def ios_label(text, size=15, bold=False, color=None, halign="left", **kwargs):
    color = color or LABEL_PRIMARY
    lbl = Label(text=text, font_name=FONT, font_size=dp(size), bold=bold,
                color=color, halign=halign, valign="middle", **kwargs)
    lbl.bind(size=lbl.setter('text_size'))
    return lbl


def ios_button(text, color=None, text_color=WHITE, height=BTN_HEIGHT,
               radius=CARD_RADIUS, font_size=16, bold=False, **kwargs):
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


def ios_input(hint="", text="", height=INPUT_HEIGHT, **kwargs):
    ti = TextInput(hint_text=hint, text=text, multiline=False,
                   font_name=FONT, font_size=dp(15),
                   background_color=(0.95, 0.95, 0.97, 1),
                   foreground_color=(0, 0, 0, 1),
                   hint_text_color=(0.56, 0.56, 0.58, 1),
                   cursor_color=IOS_BLUE,
                   size_hint_y=None, height=height,
                   padding=[dp(12), dp(10)], **kwargs)
    with ti.canvas.before:
        Color(*BG_SECONDARY)
        rect = RoundedRectangle(radius=[dp(8)], pos=ti.pos, size=ti.size)
    ti.bind(pos=lambda *a: setattr(rect, 'pos', ti.pos),
            size=lambda *a: setattr(rect, 'size', ti.size))
    return ti


def nav_bar(title, back_label="Back", on_back=None, right_widget=None):
    """iOS-style navigation bar."""
    bar = BoxLayout(size_hint_y=None, height=NAV_HEIGHT,
                    padding=[PADDING, dp(8)], spacing=SMALL_PAD)
    with_bg(bar, BG_PRIMARY)

    if on_back:
        back_btn = Button(text=f"‹ {back_label}", font_name=FONT, font_size=dp(16),
                          color=IOS_BLUE, background_color=(0,0,0,0),
                          background_normal='', size_hint_x=None, width=dp(100))
        back_btn.bind(on_press=on_back)
        bar.add_widget(back_btn)

    title_lbl = Label(text=title, font_name=FONT, font_size=dp(17), bold=True,
                       color=LABEL_PRIMARY, halign="center")
    bar.add_widget(title_lbl)

    if right_widget:
        bar.add_widget(right_widget)
    elif on_back:
        bar.add_widget(Label(size_hint_x=None, width=dp(100)))  # spacer to center title

    return bar, title_lbl


def card(children=None, padding=PADDING, spacing=SMALL_PAD, radius=CARD_RADIUS,
         orientation="vertical", **kwargs):
    """White rounded card."""
    c = BoxLayout(orientation=orientation, padding=padding, spacing=spacing,
                  size_hint_y=None, **kwargs)
    with c.canvas.before:
        Color(*WHITE)
        rect = RoundedRectangle(radius=[radius], pos=c.pos, size=c.size)
    c.bind(pos=lambda *a: setattr(rect, 'pos', c.pos),
           size=lambda *a: setattr(rect, 'size', c.size),
           minimum_height=c.setter('height'))
    c.bind(minimum_height=c.setter('height'))
    if children:
        for w in children:
            c.add_widget(w)
    return c


def status_badge(text, color):
    """Small colored status pill."""
    badge = Label(text=text, font_name=FONT, font_size=dp(11), bold=True,
                   color=color, size_hint=(None, None),
                   size=(dp(80), dp(22)), halign="center")
    with badge.canvas.before:
        Color(color[0], color[1], color[2], 0.15)
        RoundedRectangle(radius=[dp(11)], pos=badge.pos, size=badge.size)
    badge.bind(pos=lambda *a: None, size=lambda *a: None)
    return badge


def show_toast(msg, duration=2.0):
    """Brief overlay toast message."""
    popup = Popup(
        title="", content=Label(text=msg, font_name=FONT, font_size=dp(14),
                                 color=WHITE, halign="center"),
        size_hint=(0.75, None), height=dp(80),
        background_color=(0.1, 0.1, 0.1, 0.85),
        separator_height=0, title_size=0,
    )
    popup.open()
    Clock.schedule_once(lambda dt: popup.dismiss(), duration)


def edit_form_popup(title, fields_config, on_save, prefill=None):
    """
    Generic edit popup.
    fields_config: list of (label, key, hint, required)
    prefill: dict of key->value to pre-populate
    on_save: callable(data_dict)
    """
    # Outer wrapper with explicit white background
    wrapper = BoxLayout(orientation="vertical", spacing=0, padding=0)
    with_bg(wrapper, WHITE)

    # Title bar
    title_bar = BoxLayout(size_hint_y=None, height=dp(52),
                           padding=[dp(16), dp(8)], spacing=dp(8))
    with_bg(title_bar, WHITE)
    title_bar.add_widget(Label(text=title, font_name=FONT, font_size=dp(17),
                                bold=True, color=(0, 0, 0, 1),
                                halign="center", valign="middle"))
    wrapper.add_widget(title_bar)

    # Thin separator
    sep = BoxLayout(size_hint_y=None, height=dp(1))
    with_bg(sep, (0.9, 0.9, 0.9, 1))
    wrapper.add_widget(sep)

    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))
    with_bg(content, WHITE)
    fields = {}

    scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
    inner = BoxLayout(orientation="vertical", spacing=dp(8),
                      size_hint_y=None, padding=[0, 0, 0, dp(8)])
    inner.bind(minimum_height=inner.setter('height'))

    for lbl, key, hint, _ in fields_config:
        row = BoxLayout(orientation="vertical", size_hint_y=None,
                        height=dp(68), spacing=dp(4))
        with_bg(row, WHITE)
        # Label in dark gray
        lbl_widget = Label(text=lbl, font_name=FONT, font_size=dp(12),
                            color=(0.4, 0.4, 0.4, 1),
                            halign="left", valign="middle",
                            size_hint_y=None, height=dp(20))
        lbl_widget.bind(size=lbl_widget.setter('text_size'))
        row.add_widget(lbl_widget)

        # Input with solid light-gray background and black text
        ti = TextInput(
            hint_text=hint,
            text=str(prefill.get(key, "") if prefill else ""),
            multiline=False,
            font_name=FONT, font_size=dp(15),
            foreground_color=(0, 0, 0, 1),
            hint_text_color=(0.6, 0.6, 0.6, 1),
            background_color=(0.94, 0.94, 0.96, 1),
            cursor_color=IOS_BLUE,
            size_hint_y=None, height=dp(40),
            padding=[dp(10), dp(10)],
        )
        fields[key] = ti
        row.add_widget(ti)
        inner.add_widget(row)

    scroll.add_widget(inner)
    content.add_widget(scroll)

    btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10),
                         padding=[dp(16), dp(4)])
    with_bg(btn_row, WHITE)

    # Use transparent Popup — wrapper carries all the visual styling
    popup = Popup(title="", content=wrapper,
                   size_hint=(0.92, 0.88),
                   background="",
                   background_color=(0, 0, 0, 0),
                   separator_height=0,
                   title_size=0)

    cancel_btn = ios_button("Cancel", color=(0.88, 0.88, 0.88, 1),
                             text_color=(0, 0, 0, 1), height=dp(44))
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
