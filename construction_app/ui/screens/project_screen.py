from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line
from kivy.metrics import dp
from kivy.clock import Clock

from ui.theme import (FONT, BG_PRIMARY, BG_SECONDARY, IOS_BLUE, IOS_GREEN,
                       IOS_ORANGE, IOS_RED, IOS_PURPLE, IOS_TEAL, LABEL_PRIMARY,
                       LABEL_SECONDARY, WHITE, CARD_RADIUS, NAV_HEIGHT,
                       PADDING, SMALL_PAD, STATUS_COLOR, SEPARATOR)
from ui.widgets import (with_bg, ios_label, ios_button, ios_input,
                         nav_bar, show_toast, edit_form_popup)

WBS_FIELDS = [
    ("Phase", "phase", "e.g. Phase 1 – Demo", True),
    ("Task", "task", "Task description", True),
    ("Assigned To", "assigned_to", "Name or team", False),
    ("Estimated Hours", "estimated_hours", "0", False),
    ("Start Date", "start_date", "YYYY-MM-DD", False),
    ("End Date", "end_date", "YYYY-MM-DD", False),
]


class ProjectScreen(Screen):
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.project_id = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BG_SECONDARY)

        # Nav bar
        back_btn_ref = []
        bar, self._title_label = nav_bar(
            "Project",
            back_label="Projects",
            on_back=lambda *a: setattr(self.manager, 'current', 'home'),
        )
        root.add_widget(bar)

        # Tabbed panel
        self._tabs = TabbedPanel(do_default_tab=False,
                                  tab_height=dp(40), tab_width=dp(88))
        self._tabs.background_color = (0, 0, 0, 0)

        self._tab_overview  = TabbedPanelItem(text="Overview",  font_name=FONT, font_size=dp(12))
        self._tab_estimates = TabbedPanelItem(text="Estimates", font_name=FONT, font_size=dp(12))
        self._tab_invoices  = TabbedPanelItem(text="Invoices",  font_name=FONT, font_size=dp(12))
        self._tab_wbs       = TabbedPanelItem(text="Work Plan", font_name=FONT, font_size=dp(12))
        self._tab_finance   = TabbedPanelItem(text="Finance",   font_name=FONT, font_size=dp(12))

        for t in [self._tab_overview, self._tab_estimates, self._tab_invoices,
                  self._tab_wbs, self._tab_finance]:
            self._tabs.add_widget(t)

        root.add_widget(self._tabs)
        self.add_widget(root)

    def load_project(self, project_id):
        self.project_id = project_id
        Clock.schedule_once(lambda dt: self._refresh())

    def _refresh(self):
        p = self.client.get_project(self.project_id)
        if not p or "error" in p:
            return
        self._title_label.text = p["name"]
        self._load_overview(p)
        self._load_estimates_tab()
        self._load_invoices_tab()
        self._load_wbs_tab()
        self._load_finance_tab()

    # ── Overview ──────────────────────────────────────────────────────────────

    def _load_overview(self, p):
        self._tab_overview.clear_widgets()
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(12),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        # Info card
        info_card = self._info_card(p)
        layout.add_widget(info_card)

        # Status buttons
        layout.add_widget(ios_label("Change Status", size=13, bold=True,
                                     color=LABEL_SECONDARY, size_hint_y=None, height=dp(24)))
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=SMALL_PAD)
        for status, color in [("active", IOS_GREEN), ("on_hold", IOS_ORANGE),
                                ("completed", LABEL_SECONDARY)]:
            b = ios_button(status.replace("_", " ").title(), color=color,
                            height=dp(40), font_size=13)
            b.bind(on_press=lambda _, s=status: self._set_status(s))
            btn_row.add_widget(b)
        layout.add_widget(btn_row)

        sv.add_widget(layout)
        self._tab_overview.add_widget(sv)

    def _info_card(self, p):
        card = BoxLayout(orientation="vertical", size_hint_y=None,
                          padding=PADDING, spacing=dp(10))
        with card.canvas.before:
            Color(*WHITE)
            rect = RoundedRectangle(radius=[CARD_RADIUS], pos=card.pos, size=card.size)
        card.bind(pos=lambda *a: setattr(rect, 'pos', card.pos),
                  size=lambda *a: setattr(rect, 'size', card.size),
                  minimum_height=card.setter('height'))

        rows = [
            ("Customer", p["customer_name"]),
            ("Email", p["customer_email"]),
            ("Phone", p["customer_phone"] or "—"),
            ("Address", p["property_address"]),
            ("Type", p["project_type"] or "—"),
            ("Status", p["status"].replace("_", " ").title()),
            ("Start Date", p.get("start_date") or "—"),
        ]
        if p.get("notes"):
            rows.append(("Notes", p["notes"]))

        for label, val in rows:
            row = BoxLayout(size_hint_y=None, height=dp(28), spacing=SMALL_PAD)
            row.add_widget(ios_label(label, size=13, bold=True, color=LABEL_SECONDARY,
                                      size_hint_x=0.35))
            color = STATUS_COLOR.get(p["status"], LABEL_PRIMARY) if label == "Status" else LABEL_PRIMARY
            row.add_widget(ios_label(str(val), size=13, color=color))
            card.add_widget(row)

        # Edit button
        edit_btn = ios_button("Edit Project", color=IOS_BLUE, height=dp(40), font_size=14)
        edit_btn.bind(on_press=lambda *a: self._show_edit_project())
        card.add_widget(edit_btn)
        return card

    def _set_status(self, status):
        self.client.update_project_status(self.project_id, status)
        show_toast(f"Status set to {status.replace('_',' ')}")
        Clock.schedule_once(lambda dt: self._refresh(), 0.2)

    def _show_edit_project(self):
        from ui.screens.home_screen import PROJECT_FIELDS
        p = self.client.get_project(self.project_id)
        def _save(data):
            self.client.update_project(self.project_id, **{
                k: data.get(k, p.get(k, "")) for k in
                ["name","property_address","customer_name","customer_phone",
                 "customer_email","project_type","notes"]
            })
            show_toast("Project updated.")
            Clock.schedule_once(lambda dt: self._refresh(), 0.2)
        edit_form_popup("Edit Project", PROJECT_FIELDS, _save, prefill=p).open()

    # ── Estimates ─────────────────────────────────────────────────────────────

    def _load_estimates_tab(self):
        self._tab_estimates.clear_widgets()
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(8),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        new_btn = ios_button("+ New Estimate", height=dp(50), font_size=15, bold=True)
        new_btn.bind(on_press=lambda *a: self._go_to("estimate"))
        layout.add_widget(new_btn)

        estimates = self.client.list_estimates(self.project_id)
        if not estimates:
            layout.add_widget(ios_label("No estimates yet.", size=14,
                                         color=LABEL_SECONDARY, size_hint_y=None,
                                         height=dp(40), halign="center"))
        for est in estimates:
            layout.add_widget(self._estimate_row(est))

        sv.add_widget(layout)
        self._tab_estimates.add_widget(sv)

    def _estimate_row(self, est):
        row = BoxLayout(size_hint_y=None, height=dp(70), padding=PADDING,
                         spacing=SMALL_PAD)
        with_bg(row, WHITE)

        info = BoxLayout(orientation="vertical", spacing=dp(3))
        info.add_widget(ios_label(est["estimate_number"], size=15, bold=True))
        info.add_widget(ios_label(f"${est['total']:,.2f}", size=14, color=IOS_BLUE))
        info.add_widget(ios_label(est["date_issued"], size=11, color=LABEL_SECONDARY))
        row.add_widget(info)

        right = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(90),
                           spacing=dp(4))
        sc = STATUS_COLOR.get(est["status"], LABEL_SECONDARY)
        right.add_widget(ios_label(est["status"].title(), size=11, color=sc,
                                    bold=True, halign="right"))
        pdf_btn = ios_button("PDF", height=dp(30), font_size=12, radius=dp(15),
                              color=IOS_BLUE, size_hint_x=None, width=dp(70))
        pdf_btn.bind(on_press=lambda _, eid=est["id"]: self._gen_estimate_pdf(eid))
        right.add_widget(pdf_btn)
        row.add_widget(right)
        return row

    # ── Invoices ──────────────────────────────────────────────────────────────

    def _load_invoices_tab(self):
        self._tab_invoices.clear_widgets()
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(8),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        new_btn = ios_button("+ New Invoice", height=dp(50), font_size=15, bold=True)
        new_btn.bind(on_press=lambda *a: self._go_to("invoice"))
        layout.add_widget(new_btn)

        invoices = self.client.list_invoices(self.project_id)
        if not invoices:
            layout.add_widget(ios_label("No invoices yet.", size=14,
                                         color=LABEL_SECONDARY, size_hint_y=None,
                                         height=dp(40), halign="center"))
        for inv in invoices:
            layout.add_widget(self._invoice_row(inv))

        sv.add_widget(layout)
        self._tab_invoices.add_widget(sv)

    def _invoice_row(self, inv):
        row = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(90),
                         padding=[PADDING, dp(8)], spacing=dp(4))
        with_bg(row, WHITE)

        top = BoxLayout(spacing=SMALL_PAD)
        top.add_widget(ios_label(inv["invoice_number"], size=15, bold=True))
        sc = STATUS_COLOR.get(inv["status"], LABEL_SECONDARY)
        top.add_widget(ios_label(inv["status"].upper(), size=11, bold=True,
                                  color=sc, halign="right"))
        row.add_widget(top)

        row.add_widget(ios_label(f"${inv['total']:,.2f}  ·  Due: {inv['due_date'] or '—'}",
                                   size=13, color=IOS_BLUE))

        btn_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))
        edit_btn = ios_button("Edit", height=dp(28), font_size=12, radius=dp(14),
                               color=IOS_BLUE, size_hint_x=None, width=dp(60))
        edit_btn.bind(on_press=lambda _, iid=inv["id"]: self._show_edit_invoice(iid))

        stripe_btn = ios_button("Stripe", height=dp(28), font_size=12, radius=dp(14),
                                 color=IOS_PURPLE, size_hint_x=None, width=dp(70))
        stripe_btn.bind(on_press=lambda _, iid=inv["id"]: self._push_to_stripe(iid))

        sync_btn = ios_button("Sync", height=dp(28), font_size=12, radius=dp(14),
                               color=IOS_GREEN, size_hint_x=None, width=dp(60))
        sync_btn.bind(on_press=lambda _, iid=inv["id"]: self._sync_stripe(iid))

        pdf_btn = ios_button("PDF", height=dp(28), font_size=12, radius=dp(14),
                              color=LABEL_SECONDARY, size_hint_x=None, width=dp(55))
        pdf_btn.bind(on_press=lambda _, iid=inv["id"]: self._gen_invoice_pdf(iid))

        for b in [edit_btn, stripe_btn, sync_btn, pdf_btn]:
            btn_row.add_widget(b)
        row.add_widget(btn_row)
        return row

    def _show_edit_invoice(self, invoice_id):
        inv = self.client.get_invoice(invoice_id)
        if not inv or "error" in inv:
            return
        fields = [
            ("Description", "description", "Invoice description", True),
            ("Amount ($)", "amount", "0.00", True),
            ("Tax Amount ($)", "tax_amount", "0.00", False),
            ("Due Date", "due_date", "YYYY-MM-DD", False),
            ("Notes", "notes", "Optional notes", False),
        ]
        prefill = {
            "description": inv["description"],
            "amount": str(inv["amount"]),
            "tax_amount": str(inv["tax_amount"]),
            "due_date": inv["due_date"],
            "notes": inv["notes"],
        }
        def _save(data):
            try:
                self.client.update_invoice(
                    invoice_id,
                    description=data["description"],
                    amount=float(data["amount"] or 0),
                    tax_amount=float(data["tax_amount"] or 0),
                    due_date=data["due_date"],
                    notes=data["notes"],
                )
                show_toast("Invoice updated.")
                Clock.schedule_once(lambda dt: self._load_invoices_tab(), 0.2)
            except Exception as e:
                show_toast(f"Error: {e}")
        edit_form_popup("Edit Invoice", fields, _save, prefill=prefill).open()

    # ── Work Plan (WBS) ───────────────────────────────────────────────────────

    def _load_wbs_tab(self):
        self._tab_wbs.clear_widgets()
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(8),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        add_btn = ios_button("+ Add Task", height=dp(50), font_size=15, bold=True)
        add_btn.bind(on_press=lambda *a: self._show_add_wbs())
        layout.add_widget(add_btn)

        items = self.client.list_wbs(self.project_id)
        current_phase = None
        for item in items:
            if item["phase"] != current_phase:
                current_phase = item["phase"]
                layout.add_widget(ios_label(current_phase, size=13, bold=True,
                                             color=LABEL_SECONDARY,
                                             size_hint_y=None, height=dp(28)))
            layout.add_widget(self._wbs_row(item))

        sv.add_widget(layout)
        self._tab_wbs.add_widget(sv)

    def _wbs_row(self, item):
        row = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(82),
                         padding=[PADDING, dp(6)], spacing=dp(4))
        with_bg(row, WHITE)

        top = BoxLayout(spacing=SMALL_PAD)
        top.add_widget(ios_label(item["task"], size=14, bold=True))
        sc = STATUS_COLOR.get(item["status"], LABEL_SECONDARY)
        top.add_widget(ios_label(item["status"].replace("_", " ").title(),
                                  size=11, color=sc, bold=True, halign="right",
                                  size_hint_x=None, width=dp(90)))
        row.add_widget(top)

        sub = f"{item['assigned_to'] or 'Unassigned'}  ·  Est: {item['estimated_hours']}h"
        row.add_widget(ios_label(sub, size=12, color=LABEL_SECONDARY))

        btn_row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
        for label, status, color in [("Start", "in_progress", IOS_ORANGE),
                                      ("Done", "completed", IOS_GREEN)]:
            b = ios_button(label, height=dp(26), font_size=12, radius=dp(13),
                            color=color, size_hint_x=None, width=dp(60))
            b.bind(on_press=lambda _, iid=item["id"], s=status:
                   self._update_wbs_status(iid, s))
            btn_row.add_widget(b)

        edit_btn = ios_button("Edit", height=dp(26), font_size=12, radius=dp(13),
                               color=IOS_BLUE, size_hint_x=None, width=dp(55))
        edit_btn.bind(on_press=lambda _, iid=item["id"]: self._show_edit_wbs(iid, item))

        del_btn = ios_button("Delete", height=dp(26), font_size=12, radius=dp(13),
                              color=IOS_RED, size_hint_x=None, width=dp(65))
        del_btn.bind(on_press=lambda _, iid=item["id"]: self._delete_wbs(iid))

        for b in [edit_btn, del_btn]:
            btn_row.add_widget(b)
        row.add_widget(btn_row)
        return row

    def _show_add_wbs(self):
        def _save(data):
            if not data.get("task"):
                show_toast("Task description is required.")
                return
            self.client.add_wbs_item(
                project_id=self.project_id,
                phase=data.get("phase") or "Phase 1",
                task=data["task"],
                assigned_to=data.get("assigned_to", ""),
                estimated_hours=float(data.get("estimated_hours") or 0),
                start_date=data.get("start_date", ""),
                end_date=data.get("end_date", ""),
            )
            show_toast("Task added.")
            Clock.schedule_once(lambda dt: self._load_wbs_tab(), 0.2)
        edit_form_popup("Add Task", WBS_FIELDS, _save).open()

    def _show_edit_wbs(self, item_id, item):
        prefill = {k: str(item.get(k, "") or "") for k in
                   ["phase", "task", "assigned_to", "estimated_hours", "start_date", "end_date"]}
        def _save(data):
            self.client.update_wbs_item(
                item_id,
                phase=data.get("phase") or "Phase 1",
                task=data.get("task", item["task"]),
                assigned_to=data.get("assigned_to", ""),
                estimated_hours=float(data.get("estimated_hours") or 0),
                start_date=data.get("start_date", ""),
                end_date=data.get("end_date", ""),
            )
            show_toast("Task updated.")
            Clock.schedule_once(lambda dt: self._load_wbs_tab(), 0.2)
        edit_form_popup("Edit Task", WBS_FIELDS, _save, prefill=prefill).open()

    def _update_wbs_status(self, item_id, status):
        self.client.update_wbs_status(item_id, status)
        Clock.schedule_once(lambda dt: self._load_wbs_tab(), 0.1)

    def _delete_wbs(self, item_id):
        self.client.delete_wbs_item(item_id)
        show_toast("Task deleted.")
        Clock.schedule_once(lambda dt: self._load_wbs_tab(), 0.2)

    # ── Finance ───────────────────────────────────────────────────────────────

    def _load_finance_tab(self):
        self._tab_finance.clear_widgets()
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(10),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))

        layout.add_widget(ios_label("Quicken / Finance", size=17, bold=True,
                                     color=LABEL_PRIMARY, size_hint_y=None, height=dp(32)))

        qif_btn = ios_button("Export to Quicken (QIF)", color=IOS_TEAL,
                              height=dp(50), font_size=15)
        qif_btn.bind(on_press=lambda *a: self._export_quicken())
        layout.add_widget(qif_btn)

        rec_btn = ios_button("Generate Reconciliation PDF", color=IOS_BLUE,
                              height=dp(50), font_size=15)
        rec_btn.bind(on_press=lambda *a: self._gen_reconciliation())
        layout.add_widget(rec_btn)

        drive_btn = ios_button("View Google Drive Folder", color=(0.24, 0.55, 0.87, 1),
                                height=dp(50), font_size=15)
        drive_btn.bind(on_press=lambda *a: self._show_drive_info())
        layout.add_widget(drive_btn)

        self._finance_label = ios_label("", size=13, color=LABEL_SECONDARY,
                                         size_hint_y=None, height=dp(80),
                                         halign="center")
        layout.add_widget(self._finance_label)
        sv.add_widget(layout)
        self._tab_finance.add_widget(sv)

    def _export_quicken(self):
        try:
            result = self.client.export_to_quicken(self.project_id)
            self._finance_label.text = f"QIF saved:\n{result.get('qif_file', '')}"
        except Exception as e:
            self._finance_label.text = f"Error: {e}"

    def _gen_reconciliation(self):
        try:
            result = self.client.generate_reconciliation_report(self.project_id)
            link = result.get("drive_link") or result.get("pdf_path", "")
            self._finance_label.text = f"Report ready:\n{link}"
        except Exception as e:
            self._finance_label.text = f"Error: {e}"

    def _show_drive_info(self):
        try:
            info = self.client.get_drive_info(self.project_id)
            link = info.get("project_folder_link") or "Drive not configured"
            self._finance_label.text = f"Drive:\n{link}"
        except Exception as e:
            self._finance_label.text = f"Error: {e}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _go_to(self, screen):
        self.manager.get_screen(screen).set_project(self.project_id)
        self.manager.current = screen

    def _gen_estimate_pdf(self, estimate_id):
        try:
            result = self.client.generate_estimate_pdf(estimate_id)
            show_toast(f"PDF saved.")
        except Exception as e:
            show_toast(f"Error: {e}")

    def _gen_invoice_pdf(self, invoice_id):
        try:
            self.client.generate_invoice_pdf(invoice_id)
            show_toast("PDF saved.")
        except Exception as e:
            show_toast(f"Error: {e}")

    def _push_to_stripe(self, invoice_id):
        try:
            result = self.client.push_invoice_to_stripe(invoice_id)
            show_toast(f"Stripe: {result.get('status', 'created')}")
            Clock.schedule_once(lambda dt: self._load_invoices_tab(), 0.2)
        except Exception as e:
            show_toast(f"Stripe error: {e}")

    def _sync_stripe(self, invoice_id):
        try:
            result = self.client.sync_invoice_status(invoice_id)
            show_toast(f"Status: {result.get('status')}")
            Clock.schedule_once(lambda dt: self._load_invoices_tab(), 0.2)
        except Exception as e:
            show_toast(f"Sync error: {e}")
