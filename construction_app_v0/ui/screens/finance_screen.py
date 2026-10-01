"""Finance / Quicken reconciliation screen with iOS styling."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp

from ui.theme import (BG_SECONDARY, IOS_BLUE, IOS_TEAL, LABEL_PRIMARY,
                       LABEL_SECONDARY, PADDING)
from ui.widgets import with_bg, ios_label, ios_button, ios_input, nav_bar


class FinanceScreen(Screen):
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BG_SECONDARY)

        bar, _ = nav_bar("Finance", back_label="Home",
                          on_back=lambda *a: setattr(self.manager, 'current', 'home'))
        root.add_widget(bar)

        scroll = ScrollView(do_scroll_x=False)
        form = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(12),
                          size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        form.add_widget(ios_label("Quicken Reconciliation", size=17, bold=True,
                                   color=LABEL_PRIMARY, size_hint_y=None, height=dp(36)))

        for lbl, attr, hint in [
            ("Project ID", "_pid_input", "e.g. 1"),
            ("QIF File Path", "_qif_input", "/path/to/export.qif"),
        ]:
            col = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(68), spacing=dp(4))
            col.add_widget(ios_label(lbl, size=12, color=LABEL_SECONDARY,
                                      size_hint_y=None, height=dp(18)))
            ti = ios_input(hint=hint)
            setattr(self, attr, ti)
            col.add_widget(ti)
            form.add_widget(col)

        btn = ios_button("Reconcile with Quicken", color=IOS_TEAL,
                          height=dp(50), font_size=15)
        btn.bind(on_press=self._reconcile)
        form.add_widget(btn)

        self._result = ios_label("", size=13, color=LABEL_SECONDARY,
                                  size_hint_y=None, height=dp(160), halign="left")
        form.add_widget(self._result)

        scroll.add_widget(form)
        root.add_widget(scroll)
        self.add_widget(root)

    def _reconcile(self, *args):
        pid = self._pid_input.text.strip()
        qif = self._qif_input.text.strip()
        if not pid or not qif:
            self._result.text = "Enter a project ID and QIF file path."
            return
        try:
            r = self.client.reconcile_with_quicken(int(pid), qif)
            balanced = r.get("balanced", False)
            self._result.text = (
                f"App total paid:    ${r.get('app_total_paid', 0):,.2f}\n"
                f"Quicken total:     ${r.get('quicken_total', 0):,.2f}\n"
                f"Difference:        ${r.get('difference', 0):,.2f}\n"
                f"Paid invoices:     {r.get('paid_invoices', 0)}\n"
                f"Quicken entries:   {r.get('quicken_transactions', 0)}\n"
                f"Status:            {'Balanced' if balanced else 'Discrepancy found'}"
            )
        except Exception as e:
            self._result.text = f"Error: {e}"
