"""Invoice creation screen."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock

from ui.theme import (FONT, BG_SECONDARY, IOS_BLUE, LABEL_PRIMARY,
                       LABEL_SECONDARY, WHITE, CARD_RADIUS, PADDING)
from ui.widgets import with_bg, ios_label, ios_button, nav_bar, show_toast, date_input


def _label(text):
    lbl = Label(text=text, font_name=FONT, font_size=dp(12),
                 color=(0.4, 0.4, 0.4, 1), halign="left", valign="middle",
                 size_hint_y=None, height=dp(20))
    lbl.bind(size=lbl.setter('text_size'))
    return lbl


def _input(hint="", text=""):
    return TextInput(
        hint_text=hint, text=text, multiline=False,
        font_name=FONT, font_size=dp(15),
        foreground_color=(0, 0, 0, 1),
        hint_text_color=(0.6, 0.6, 0.6, 1),
        background_color=(0.94, 0.94, 0.96, 1),
        cursor_color=IOS_BLUE,
        size_hint_y=None, height=dp(44),
        padding=[dp(12), dp(10)],
    )


class InvoiceScreen(Screen):
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.project_id = None
        self._fields = {}
        self._build()

    def set_project(self, project_id):
        self.project_id = project_id
        for ti in self._fields.values():
            ti.text = ""

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BG_SECONDARY)

        bar, _ = nav_bar("New Invoice", back_label="Project",
                          on_back=lambda *a: setattr(self.manager, 'current', 'project'))
        root.add_widget(bar)

        scroll = ScrollView(do_scroll_x=False)
        form = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(14),
                          size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # White card containing all fields
        card = BoxLayout(orientation="vertical", size_hint_y=None,
                          padding=dp(14), spacing=dp(12))
        with card.canvas.before:
            Color(*WHITE)
            rect = RoundedRectangle(radius=[CARD_RADIUS], pos=card.pos, size=card.size)
        card.bind(pos=lambda *a: setattr(rect, 'pos', card.pos),
                  size=lambda *a: setattr(rect, 'size', card.size),
                  minimum_height=card.setter('height'))

        fields_config = [
            ("Description *", "description", "e.g. Deposit – Kitchen Remodel"),
            ("Amount ($) *",  "amount",      "e.g. 5000.00"),
            ("Tax Amount ($)", "tax_amount", "e.g. 412.50"),
            ("Due Date",       "due_date",   "YYYY-MM-DD"),
            ("Linked Estimate ID", "estimate_id", "optional"),
            ("Notes",          "notes",      "optional"),
        ]

        for lbl_text, key, hint in fields_config:
            is_date = "date" in key.lower()
            col_h = dp(74) if is_date else dp(70)
            col = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=col_h, spacing=dp(4))
            col.add_widget(_label(lbl_text))
            if is_date:
                container, ti = date_input(hint=hint, height=dp(44))
                col.add_widget(container)
            else:
                ti = _input(hint=hint)
                col.add_widget(ti)
            self._fields[key] = ti
            card.add_widget(col)

        form.add_widget(card)

        save_btn = ios_button("Create Invoice", height=dp(54), font_size=16, bold=True)
        save_btn.bind(on_press=self._save)
        form.add_widget(save_btn)

        scroll.add_widget(form)
        root.add_widget(scroll)
        self.add_widget(root)

    def _save(self, *args):
        if not self.project_id:
            show_toast("No project selected.")
            return

        desc = self._fields["description"].text.strip()
        amt_text = self._fields["amount"].text.strip()
        if not desc or not amt_text:
            show_toast("Description and Amount are required.")
            return

        try:
            estimate_id_text = self._fields["estimate_id"].text.strip()
            result = self.client.create_invoice(
                project_id=self.project_id,
                description=desc,
                amount=float(amt_text),
                tax_amount=float(self._fields["tax_amount"].text or 0),
                estimate_id=int(estimate_id_text) if estimate_id_text else None,
                due_date=self._fields["due_date"].text.strip(),
                notes=self._fields["notes"].text.strip(),
            )
            show_toast(f"Invoice {result['invoice_number']} — ${result['total']:,.2f}")
            def _back(dt):
                ps = self.manager.get_screen("project")
                ps.load_project(self.project_id)
                self.manager.current = "project"
            Clock.schedule_once(_back, 1.5)
        except Exception as e:
            show_toast(f"Error: {e}")
