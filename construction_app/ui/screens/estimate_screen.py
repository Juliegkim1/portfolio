"""Estimate creation screen — vertical card layout for easy mobile input."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock

from ui.theme import (FONT, BG_SECONDARY, IOS_BLUE, IOS_GREEN, IOS_RED,
                       LABEL_PRIMARY, LABEL_SECONDARY, WHITE,
                       CARD_RADIUS, PADDING, SMALL_PAD)
from ui.widgets import with_bg, ios_label, ios_button, nav_bar, show_toast, date_input

SECTIONS = ["DEMOLITION/PREPARATION", "MATERIALS", "LABOR", "ADDITIONAL WORK"]

INPUT_H = dp(44)
LABEL_H = dp(20)


def _field_input(hint="", text=""):
    """Full-width black-text input."""
    ti = TextInput(
        hint_text=hint, text=text, multiline=False,
        font_name=FONT, font_size=dp(15),
        foreground_color=(0, 0, 0, 1),
        hint_text_color=(0.6, 0.6, 0.6, 1),
        background_color=(0.94, 0.94, 0.96, 1),
        cursor_color=IOS_BLUE,
        size_hint_y=None, height=INPUT_H,
        padding=[dp(12), dp(10)],
    )
    return ti


def _field_label(text):
    lbl = Label(text=text, font_name=FONT, font_size=dp(12),
                 color=(0.4, 0.4, 0.4, 1), halign="left", valign="middle",
                 size_hint_y=None, height=LABEL_H)
    lbl.bind(size=lbl.setter('text_size'))
    return lbl


class EstimateScreen(Screen):
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.project_id = None
        self._line_items = []
        self._ps_rows = []
        self._build()

    def set_project(self, project_id):
        self.project_id = project_id
        self._line_items = []
        self._items_layout.clear_widgets()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BG_SECONDARY)

        bar, _ = nav_bar("New Estimate", back_label="Project",
                          on_back=lambda *a: setattr(self.manager, 'current', 'project'))
        root.add_widget(bar)

        scroll = ScrollView(do_scroll_x=False)
        form = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(14),
                          size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # ── Tax / Permit / Discount ──────────────────────────────────────────
        opts_card = self._white_card()
        opts_card.add_widget(ios_label("Pricing Options", size=13, bold=True,
                                        color=LABEL_SECONDARY,
                                        size_hint_y=None, height=dp(24)))
        opts_row = BoxLayout(size_hint_y=None, height=INPUT_H + LABEL_H + dp(4),
                              spacing=dp(10))
        for label, attr in [("Tax %", "_tax_input"),
                              ("Permit Fees $", "_permit_input"),
                              ("Discount $", "_discount_input")]:
            col = BoxLayout(orientation="vertical", spacing=dp(4))
            col.add_widget(_field_label(label))
            ti = _field_input(hint="0")
            setattr(self, attr, ti)
            col.add_widget(ti)
            opts_row.add_widget(col)
        opts_card.add_widget(opts_row)
        form.add_widget(opts_card)

        # ── Line Items ───────────────────────────────────────────────────────
        form.add_widget(ios_label("Line Items", size=15, bold=True,
                                   color=LABEL_PRIMARY, size_hint_y=None, height=dp(28)))

        self._items_layout = BoxLayout(orientation="vertical", size_hint_y=None,
                                        spacing=dp(10))
        self._items_layout.bind(minimum_height=self._items_layout.setter('height'))
        form.add_widget(self._items_layout)

        add_btn = ios_button("+ Add Line Item", color=IOS_GREEN,
                              height=dp(48), font_size=15, bold=True)
        add_btn.bind(on_press=lambda *a: self._add_line_item())
        form.add_widget(add_btn)

        # ── Payment Schedule ─────────────────────────────────────────────────
        form.add_widget(ios_label("Payment Schedule", size=15, bold=True,
                                   color=LABEL_PRIMARY, size_hint_y=None, height=dp(28)))
        self._ps_rows = []
        for lbl, desc_default in [("1st Payment", "Deposit – Project Start"),
                                    ("2nd Payment", "Mid-Project Milestone"),
                                    ("3rd Payment", "Final Payment – Completion")]:
            ps_card = self._white_card()
            ps_card.add_widget(ios_label(lbl, size=13, bold=True, color=IOS_BLUE,
                                          size_hint_y=None, height=dp(22)))
            row1 = BoxLayout(size_hint_y=None,
                              height=INPUT_H + LABEL_H + dp(4), spacing=dp(10))
            desc_col = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=0.55)
            desc_col.add_widget(_field_label("Description"))
            desc_ti = _field_input(hint="Description", text=desc_default)
            desc_col.add_widget(desc_ti)
            row1.add_widget(desc_col)

            amt_col = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=0.25)
            amt_col.add_widget(_field_label("Amount $"))
            amt_ti = _field_input(hint="0.00")
            amt_col.add_widget(amt_ti)
            row1.add_widget(amt_col)

            date_col = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=0.25)
            date_col.add_widget(_field_label("Due Date"))
            date_container, date_ti = date_input(hint="YYYY-MM-DD", height=INPUT_H)
            date_col.add_widget(date_container)
            row1.add_widget(date_col)

            ps_card.add_widget(row1)
            self._ps_rows.append((lbl, desc_ti, amt_ti, date_ti))
            form.add_widget(ps_card)

        # ── Save ─────────────────────────────────────────────────────────────
        save_btn = ios_button("Save Estimate", height=dp(54), font_size=16, bold=True)
        save_btn.bind(on_press=self._save_estimate)
        form.add_widget(save_btn)

        scroll.add_widget(form)
        root.add_widget(scroll)
        self.add_widget(root)

    def _white_card(self):
        """Returns a white rounded card that auto-sizes to its children."""
        card = BoxLayout(orientation="vertical", size_hint_y=None,
                          padding=dp(14), spacing=dp(8))
        with card.canvas.before:
            Color(*WHITE)
            rect = RoundedRectangle(radius=[CARD_RADIUS], pos=card.pos, size=card.size)
        card.bind(pos=lambda *a: setattr(rect, 'pos', card.pos),
                  size=lambda *a: setattr(rect, 'size', card.size),
                  minimum_height=card.setter('height'))
        return card

    def _add_line_item(self):
        item_num = len(self._line_items) + 1
        card = self._white_card()
        row_data = {"card": card}

        # Header row: item number + section spinner + delete
        header = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        header.add_widget(ios_label(f"Item {item_num}", size=13, bold=True,
                                     color=LABEL_PRIMARY, size_hint_x=None, width=dp(55)))

        spinner = Spinner(
            text=SECTIONS[2], values=SECTIONS,
            font_name=FONT, font_size=dp(12),
            background_color=(0.94, 0.94, 0.96, 1),
            background_normal='', color=(0, 0, 0, 1),
            size_hint_y=None, height=dp(34),
        )
        row_data["section"] = spinner
        header.add_widget(spinner)

        del_btn = ios_button("✕ Remove", color=IOS_RED, height=dp(32),
                              font_size=12, radius=dp(8),
                              size_hint_x=None, width=dp(90))
        del_btn.bind(on_press=lambda *a: self._remove_item(card, row_data))
        header.add_widget(del_btn)
        card.add_widget(header)

        # Description — full width
        card.add_widget(_field_label("Description"))
        desc_ti = _field_input(hint="e.g. Demo existing tile flooring")
        row_data["description"] = desc_ti
        card.add_widget(desc_ti)

        # Qty / Unit / Unit Price / Total — in a row
        nums_row = BoxLayout(size_hint_y=None,
                              height=INPUT_H + LABEL_H + dp(4), spacing=dp(8))

        total_lbl_ref = [None]

        for label, key, hint, flex in [("Qty", "qty", "1", 0.2),
                                        ("Unit", "unit", "ea", 0.2),
                                        ("Unit Price $", "unit_price", "0.00", 0.35)]:
            col = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=flex)
            col.add_widget(_field_label(label))
            ti = _field_input(hint=hint)
            row_data[key] = ti
            col.add_widget(ti)
            nums_row.add_widget(col)

        # Total display
        total_col = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_x=0.25)
        total_col.add_widget(_field_label("Total $"))
        total_lbl = Label(text="$0.00", font_name=FONT, font_size=dp(15),
                           bold=True, color=IOS_BLUE, halign="center",
                           size_hint_y=None, height=INPUT_H)
        total_lbl_ref[0] = total_lbl
        row_data["total_lbl"] = total_lbl
        total_col.add_widget(total_lbl)
        nums_row.add_widget(total_col)

        card.add_widget(nums_row)

        def _update(*a):
            try:
                t = float(row_data["qty"].text or 0) * float(row_data["unit_price"].text or 0)
                total_lbl.text = f"${t:,.2f}"
            except ValueError:
                pass
        row_data["qty"].bind(text=_update)
        row_data["unit_price"].bind(text=_update)

        self._line_items.append(row_data)
        self._items_layout.add_widget(card)

    def _remove_item(self, card, row_data):
        self._items_layout.remove_widget(card)
        if row_data in self._line_items:
            self._line_items.remove(row_data)

    def _save_estimate(self, *args):
        if not self.project_id:
            show_toast("No project selected.")
            return

        line_items = []
        for rd in self._line_items:
            desc = rd["description"].text.strip()
            if not desc:
                continue
            try:
                line_items.append({
                    "section": rd["section"].text,
                    "description": desc,
                    "qty": float(rd["qty"].text or 1),
                    "unit": rd["unit"].text.strip() or "ea",
                    "unit_price": float(rd["unit_price"].text or 0),
                })
            except ValueError:
                continue

        payment_schedule = []
        for lbl, desc_w, amt_w, date_w in self._ps_rows:
            try:
                amt = float(amt_w.text or 0)
                if amt > 0:
                    payment_schedule.append({
                        "label": lbl, "description": desc_w.text.strip(),
                        "amount": amt, "due_date": date_w.text.strip() or None,
                    })
            except ValueError:
                continue

        try:
            result = self.client.create_estimate(
                project_id=self.project_id,
                line_items=line_items,
                payment_schedule=payment_schedule,
                tax_rate=float(self._tax_input.text or 0) / 100,
                permit_fees=float(self._permit_input.text or 0),
                discount=float(self._discount_input.text or 0),
            )
            show_toast(f"Estimate {result['estimate_number']} — ${result['total']:,.2f}")
            def _back(dt):
                ps = self.manager.get_screen("project")
                ps.load_project(self.project_id)
                self.manager.current = "project"
            Clock.schedule_once(_back, 1.5)
        except Exception as e:
            show_toast(f"Error: {e}")
