"""Project detail screen — custom iOS-style tab bar, shadow cards, status badges."""
import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock

from ui.theme import (FONT, BG_SECONDARY, IOS_BLUE, IOS_GREEN, IOS_ORANGE,
                       IOS_RED, IOS_PURPLE, IOS_TEAL, IOS_INDIGO, LABEL_PRIMARY,
                       LABEL_SECONDARY, LABEL_TERTIARY, WHITE, CARD_RADIUS,
                       PADDING, SMALL_PAD, STATUS_COLOR, SEPARATOR)
from ui.widgets import (with_bg, ios_label, ios_button, outline_button,
                         shadow_card, status_badge, section_header,
                         nav_bar, show_toast, edit_form_popup)

TABS = [
    ("Overview",  "overview"),
    ("Estimates", "estimates"),
    ("Invoices",  "invoices"),
    ("Work Plan", "wbs"),
    ("Finance",   "finance"),
]

WBS_FIELDS = [
    ("Phase",            "phase",            "e.g. Phase 1 – Demo",  True),
    ("Task",             "task",             "Task description",      True),
    ("Assigned To",      "assigned_to",      "Name or team",          False),
    ("Estimated Hours",  "estimated_hours",  "0",                     False),
    ("Start Date",       "start_date",       "YYYY-MM-DD",            False),
    ("End Date",         "end_date",         "YYYY-MM-DD",            False),
]


class ProjectScreen(Screen):
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self.project_id = None
        self._project_data = None
        self._active_tab = "overview"
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BG_SECONDARY)

        bar, self._title_label = nav_bar(
            "Project",
            back_label="Projects",
            on_back=lambda *a: setattr(self.manager, "current", "home"),
        )
        root.add_widget(bar)
        root.add_widget(self._build_tab_bar())

        self._content = BoxLayout(orientation="vertical")
        root.add_widget(self._content)
        self.add_widget(root)

    def _build_tab_bar(self):
        outer = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(45))
        with_bg(outer, WHITE)

        scroll = ScrollView(do_scroll_y=False, do_scroll_x=True,
                            bar_width=0, size_hint=(1, None), height=dp(43))
        inner = BoxLayout(size_hint=(None, 1))
        inner.bind(minimum_width=inner.setter("width"))

        self._tab_btns = {}
        self._tab_indicators = {}

        for label, key in TABS:
            w = max(dp(84), len(label) * dp(10) + dp(24))
            cell = BoxLayout(orientation="vertical", size_hint=(None, 1), width=w)

            btn = Button(
                text=label, font_name=FONT, font_size=dp(12),
                background_normal="", background_color=(0, 0, 0, 0),
                color=LABEL_SECONDARY, bold=False,
                size_hint=(None, None), width=w, height=dp(41),
            )
            btn.bind(on_press=lambda b, k=key: self._switch_tab(k))
            self._tab_btns[key] = btn

            ind = BoxLayout(size_hint=(None, None), width=w, height=dp(2))
            with ind.canvas.before:
                ind._ind_color = Color(0, 0, 0, 0)
                ind._ind_rect = Rectangle(pos=ind.pos, size=ind.size)
            ind.bind(
                pos=lambda w, *a: setattr(w._ind_rect, "pos", w.pos),
                size=lambda w, *a: setattr(w._ind_rect, "size", w.size),
            )
            self._tab_indicators[key] = ind

            cell.add_widget(btn)
            cell.add_widget(ind)
            inner.add_widget(cell)

        scroll.add_widget(inner)
        outer.add_widget(scroll)

        sep = BoxLayout(size_hint_y=None, height=dp(1))
        with_bg(sep, SEPARATOR)
        outer.add_widget(sep)
        return outer

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _switch_tab(self, key):
        self._active_tab = key
        for k, btn in self._tab_btns.items():
            ind = self._tab_indicators[k]
            if k == key:
                btn.color = IOS_BLUE
                btn.bold = True
                ind._ind_color.rgba = IOS_BLUE
            else:
                btn.color = LABEL_SECONDARY
                btn.bold = False
                ind._ind_color.rgba = (0, 0, 0, 0)

        if not self._project_data:
            return

        self._content.clear_widgets()
        {
            "overview":  lambda: self._load_overview(self._project_data),
            "estimates": self._load_estimates_tab,
            "invoices":  self._load_invoices_tab,
            "wbs":       self._load_wbs_tab,
            "finance":   self._load_finance_tab,
        }[key]()

    def load_project(self, project_id):
        self.project_id = project_id
        Clock.schedule_once(lambda dt: self._refresh())

    def _refresh(self):
        p = self.client.get_project(self.project_id)
        if not p or "error" in p:
            return
        self._project_data = p
        self._title_label.text = p["name"]
        self._switch_tab(self._active_tab)

    # ── Overview ──────────────────────────────────────────────────────────────

    def _load_overview(self, p):
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(14),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        layout.add_widget(self._info_card(p))

        layout.add_widget(section_header("Update Status"))
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=SMALL_PAD)
        for label, status, color in [
            ("Active",    "active",    IOS_GREEN),
            ("On Hold",   "on_hold",   IOS_ORANGE),
            ("Completed", "completed", LABEL_SECONDARY),
        ]:
            b = ios_button(label, color=color, height=dp(42), font_size=13)
            b.bind(on_press=lambda _, s=status: self._set_status(s))
            btn_row.add_widget(b)
        layout.add_widget(btn_row)

        sv.add_widget(layout)
        self._content.add_widget(sv)

    def _info_card(self, p):
        c = shadow_card(padding=PADDING, spacing=dp(10))
        dur = p.get("duration_days")
        dur_str = f"{dur} days" if dur else "—"
        rows = [
            ("Customer", p["customer_name"]),
            ("Email",    p["customer_email"]),
            ("Phone",    p["customer_phone"] or "—"),
            ("Address",  p["property_address"]),
            ("Type",     p["project_type"] or "—"),
            ("Est. Start",    p.get("start_date") or "—"),
            ("Est. Duration", dur_str),
        ]
        if p.get("notes"):
            rows.append(("Notes", p["notes"]))

        for label, val in rows:
            row = BoxLayout(size_hint_y=None, height=dp(28), spacing=SMALL_PAD)
            row.add_widget(ios_label(label, size=11, bold=True, color=LABEL_SECONDARY,
                                      size_hint_x=0.28))
            row.add_widget(ios_label(str(val), size=13, color=LABEL_PRIMARY))
            c.add_widget(row)

        # Status badge row
        sc = STATUS_COLOR.get(p["status"], LABEL_SECONDARY)
        badge_row = BoxLayout(size_hint_y=None, height=dp(26))
        badge_row.add_widget(ios_label("Status", size=11, bold=True,
                                        color=LABEL_SECONDARY, size_hint_x=0.28))
        badge_row.add_widget(status_badge(p["status"].replace("_", " ").title(), sc))
        c.add_widget(badge_row)

        edit_btn = ios_button("Edit Project", color=IOS_BLUE, height=dp(46), font_size=14)
        edit_btn.bind(on_press=lambda *a: self._show_edit_project())
        c.add_widget(edit_btn)

        del_btn = outline_button("Delete Project", color=IOS_RED, height=dp(40), font_size=13)
        del_btn.bind(on_press=lambda *a: self._confirm_delete_project())
        c.add_widget(del_btn)
        return c

    def _set_status(self, status):
        self.client.update_project_status(self.project_id, status)
        show_toast(f"Status → {status.replace('_', ' ')}")
        Clock.schedule_once(lambda dt: self._refresh(), 0.2)

    def _confirm_delete_project(self):
        from kivy.uix.popup import Popup

        wrapper = BoxLayout(orientation="vertical", spacing=0)
        from ui.widgets import with_bg
        with_bg(wrapper, (1, 1, 1, 1))

        # Warning message
        msg_box = BoxLayout(orientation="vertical", padding=[dp(20), dp(20)],
                             spacing=dp(10), size_hint_y=None, height=dp(120))
        with_bg(msg_box, (1, 1, 1, 1))
        msg_box.add_widget(ios_label("Delete Project?", size=17, bold=True,
                                      color=IOS_RED, halign="center",
                                      size_hint_y=None, height=dp(26)))
        name = self._project_data.get("name", "this project") if self._project_data else "this project"
        msg_box.add_widget(ios_label(
            f"'{name}' and all its estimates,\ninvoices, and tasks will be permanently deleted.",
            size=13, color=LABEL_PRIMARY, halign="center",
            size_hint_y=None, height=dp(60)))
        wrapper.add_widget(msg_box)

        btn_row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12),
                             padding=[dp(16), dp(6)])
        with_bg(btn_row, (1, 1, 1, 1))

        popup = Popup(title="", content=wrapper,
                       size_hint=(0.82, None), height=dp(176),
                       background="", background_color=(0, 0, 0, 0),
                       separator_height=0, title_size=0)

        cancel_btn = outline_button("Cancel", color=LABEL_SECONDARY, height=dp(44))
        cancel_btn.bind(on_press=popup.dismiss)

        confirm_btn = ios_button("Delete", color=IOS_RED, height=dp(44))
        def _do_delete(*a):
            popup.dismiss()
            self._delete_project()
        confirm_btn.bind(on_press=_do_delete)

        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        wrapper.add_widget(btn_row)
        popup.open()

    def _delete_project(self):
        try:
            self.client.delete_project(self.project_id)
            show_toast("Project deleted.")
            Clock.schedule_once(lambda dt: setattr(self.manager, "current", "home"), 0.5)
            Clock.schedule_once(lambda dt: self.manager.get_screen("home")._refresh(), 0.6)
        except Exception as e:
            show_toast(f"Error: {e}")

    def _show_edit_project(self):
        from ui.screens.home_screen import PROJECT_FIELDS
        p = self.client.get_project(self.project_id)
        def _save(data):
            self.client.update_project(self.project_id, **{
                k: data.get(k, p.get(k, "")) for k in
                ["name", "property_address", "customer_name", "customer_phone",
                 "customer_email", "project_type", "notes",
                 "start_date", "duration_days"]
            })
            show_toast("Project updated.")
            Clock.schedule_once(lambda dt: self._refresh(), 0.2)
        edit_form_popup("Edit Project", PROJECT_FIELDS, _save, prefill=p).open()

    # ── Estimates ─────────────────────────────────────────────────────────────

    def _load_estimates_tab(self):
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(10),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        new_btn = ios_button("+ New Estimate", height=dp(50), font_size=15)
        new_btn.bind(on_press=lambda *a: self._go_to("estimate"))
        layout.add_widget(new_btn)

        estimates = self.client.list_estimates(self.project_id)
        if not estimates:
            layout.add_widget(self._empty_state(
                "No estimates yet", "Tap '+ New Estimate' to get started"))
        for est in estimates:
            layout.add_widget(self._estimate_card(est))

        sv.add_widget(layout)
        self._content.add_widget(sv)

    def _estimate_card(self, est):
        c = shadow_card(padding=[PADDING, dp(14)], spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(ios_label(est["estimate_number"], size=14, bold=True))
        sc = STATUS_COLOR.get(est["status"], LABEL_SECONDARY)
        top.add_widget(status_badge(est["status"].title(), sc))
        c.add_widget(top)

        c.add_widget(ios_label(f"${est['total']:,.2f}", size=22, bold=True,
                                color=IOS_BLUE, size_hint_y=None, height=dp(30)))
        c.add_widget(ios_label(f"Issued {est['date_issued']}", size=12,
                                color=LABEL_SECONDARY, size_hint_y=None, height=dp(18)))

        btn_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        pdf_btn = outline_button("Generate PDF", color=IOS_BLUE,
                                  height=dp(34), font_size=12, radius=dp(8))
        pdf_btn.bind(on_press=lambda _, eid=est["id"]: self._gen_estimate_pdf(eid))
        btn_row.add_widget(pdf_btn)
        del_btn = outline_button("Delete", color=IOS_RED,
                                  height=dp(34), font_size=12, radius=dp(8))
        del_btn.bind(on_press=lambda _, eid=est["id"]: self._delete_estimate(eid))
        btn_row.add_widget(del_btn)
        c.add_widget(btn_row)
        return c

    # ── Invoices ──────────────────────────────────────────────────────────────

    def _load_invoices_tab(self):
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(10),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        new_btn = ios_button("+ New Invoice", height=dp(50), font_size=15)
        new_btn.bind(on_press=lambda *a: self._go_to("invoice"))
        layout.add_widget(new_btn)

        invoices = self.client.list_invoices(self.project_id)
        if not invoices:
            layout.add_widget(self._empty_state(
                "No invoices yet", "Tap '+ New Invoice' to get started"))
        for inv in invoices:
            layout.add_widget(self._invoice_card(inv))

        sv.add_widget(layout)
        self._content.add_widget(sv)

    def _invoice_card(self, inv):
        sc = STATUS_COLOR.get(inv["status"], LABEL_SECONDARY)
        c = shadow_card(padding=[PADDING, dp(14)], spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(ios_label(inv["invoice_number"], size=14, bold=True))
        top.add_widget(status_badge(inv["status"].upper(), sc))
        c.add_widget(top)

        c.add_widget(ios_label(f"${inv['total']:,.2f}", size=22, bold=True,
                                color=sc, size_hint_y=None, height=dp(30)))
        c.add_widget(ios_label(f"Due: {inv['due_date'] or '—'}",
                                size=12, color=LABEL_SECONDARY,
                                size_hint_y=None, height=dp(18)))

        btn_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        actions = [
            ("Edit",   IOS_BLUE,   lambda iid=inv["id"]: self._show_edit_invoice(iid)),
            ("Stripe", IOS_PURPLE, lambda iid=inv["id"]: self._push_to_stripe(iid)),
            ("Sync",   IOS_GREEN,  lambda iid=inv["id"]: self._sync_stripe(iid)),
            ("PDF",    LABEL_SECONDARY, lambda iid=inv["id"]: self._gen_invoice_pdf(iid)),
            ("Delete", IOS_RED,    lambda iid=inv["id"]: self._delete_invoice(iid)),
        ]
        for label, color, fn in actions:
            b = outline_button(label, color=color, height=dp(32),
                                font_size=12, radius=dp(7))
            b.bind(on_press=lambda _, f=fn: f())
            btn_row.add_widget(b)
        c.add_widget(btn_row)
        return c

    def _show_edit_invoice(self, invoice_id):
        inv = self.client.get_invoice(invoice_id)
        if not inv or "error" in inv:
            return
        fields = [
            ("Description",    "description", "Invoice description", True),
            ("Amount ($)",     "amount",      "0.00",                True),
            ("Tax Amount ($)", "tax_amount",  "0.00",                False),
            ("Due Date",       "due_date",    "YYYY-MM-DD",          False),
            ("Notes",          "notes",       "Optional notes",      False),
        ]
        prefill = {
            "description": inv["description"],
            "amount":      str(inv["amount"]),
            "tax_amount":  str(inv["tax_amount"]),
            "due_date":    inv["due_date"],
            "notes":       inv["notes"],
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
                Clock.schedule_once(lambda dt: self._switch_tab("invoices"), 0.2)
            except Exception as e:
                show_toast(f"Error: {e}")
        edit_form_popup("Edit Invoice", fields, _save, prefill=prefill).open()

    # ── Work Plan ─────────────────────────────────────────────────────────────

    def _load_wbs_tab(self):
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(10),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        add_btn = ios_button("+ Add Task", height=dp(50), font_size=15)
        add_btn.bind(on_press=lambda *a: self._show_add_wbs())
        layout.add_widget(add_btn)

        items = self.client.list_wbs(self.project_id)
        if not items:
            layout.add_widget(self._empty_state(
                "No tasks yet", "Tap '+ Add Task' to plan the work"))

        current_phase = None
        for item in items:
            if item["phase"] != current_phase:
                current_phase = item["phase"]
                layout.add_widget(section_header(current_phase))
            layout.add_widget(self._wbs_card(item))

        sv.add_widget(layout)
        self._content.add_widget(sv)

    def _wbs_card(self, item):
        sc = STATUS_COLOR.get(item["status"], LABEL_SECONDARY)
        c = shadow_card(padding=[PADDING, dp(12)], spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(ios_label(item["task"], size=14, bold=True))
        top.add_widget(status_badge(item["status"].replace("_", " ").title(), sc))
        c.add_widget(top)

        c.add_widget(ios_label(
            f"{item['assigned_to'] or 'Unassigned'}  ·  Est: {item['estimated_hours']}h",
            size=12, color=LABEL_SECONDARY, size_hint_y=None, height=dp(18)))

        btn_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        for label, status, color in [("▶ Start", "in_progress", IOS_ORANGE),
                                      ("✓ Done",  "completed",   IOS_GREEN)]:
            b = ios_button(label, color=color, height=dp(32), font_size=11,
                            radius=dp(7), bold=False)
            b.bind(on_press=lambda _, iid=item["id"], s=status:
                   self._update_wbs_status(iid, s))
            btn_row.add_widget(b)

        edit_btn = outline_button("Edit", color=IOS_BLUE, height=dp(32),
                                   font_size=11, radius=dp(7))
        edit_btn.bind(on_press=lambda _, iid=item["id"]: self._show_edit_wbs(iid, item))
        btn_row.add_widget(edit_btn)

        del_btn = outline_button("Delete", color=IOS_RED, height=dp(32),
                                  font_size=11, radius=dp(7))
        del_btn.bind(on_press=lambda _, iid=item["id"]: self._delete_wbs(iid))
        btn_row.add_widget(del_btn)

        c.add_widget(btn_row)
        return c

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
            Clock.schedule_once(lambda dt: self._switch_tab("wbs"), 0.2)
        edit_form_popup("Add Task", WBS_FIELDS, _save).open()

    def _show_edit_wbs(self, item_id, item):
        prefill = {k: str(item.get(k, "") or "")
                   for k in ["phase", "task", "assigned_to",
                              "estimated_hours", "start_date", "end_date"]}
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
            Clock.schedule_once(lambda dt: self._switch_tab("wbs"), 0.2)
        edit_form_popup("Edit Task", WBS_FIELDS, _save, prefill=prefill).open()

    def _update_wbs_status(self, item_id, status):
        self.client.update_wbs_status(item_id, status)
        Clock.schedule_once(lambda dt: self._switch_tab("wbs"), 0.1)

    def _delete_wbs(self, item_id):
        self.client.delete_wbs_item(item_id)
        show_toast("Task deleted.")
        Clock.schedule_once(lambda dt: self._switch_tab("wbs"), 0.2)

    # ── Finance ───────────────────────────────────────────────────────────────

    def _load_finance_tab(self):
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(12),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        layout.add_widget(section_header("Documents & Integrations"))

        actions = [
            ("Generate Project Summary PDF",  IOS_BLUE,             self._gen_project_summary),
            ("Setup Cloud Storage Bucket",    IOS_TEAL,             self._setup_drive),
            ("View Files in Cloud Storage",   (0.24, 0.55, 0.87, 1), self._show_drive_info),
            ("Export to Quicken (QIF)",       IOS_BLUE,             self._export_quicken),
            ("Generate Reconciliation PDF",   IOS_INDIGO,           self._gen_reconciliation),
        ]
        for label, color, fn in actions:
            btn = ios_button(label, color=color, height=dp(50), font_size=14, bold=False)
            btn.bind(on_press=lambda _, f=fn: f())
            layout.add_widget(btn)

        self._finance_label = ios_label("", size=13, color=LABEL_SECONDARY,
                                         size_hint_y=None, height=dp(80),
                                         halign="center")
        layout.add_widget(self._finance_label)
        sv.add_widget(layout)
        self._content.add_widget(sv)

    def _setup_drive(self):
        self._finance_label.text = "Connecting to Cloud Storage…"

        def _run():
            try:
                self.client.setup_drive_folders(self.project_id)
                info = self.client.get_drive_info(self.project_id)
                link = info.get("project_folder_link", "")
                def _ok(dt):
                    self._finance_label.text = f"Drive ready!\n{link}"
                    show_toast("Cloud Storage bucket ready.")
                Clock.schedule_once(_ok, 0)
            except Exception as e:
                msg = str(e)
                def _err(dt, m=msg):
                    self._finance_label.text = (
                        f"Drive error: {m}\n\n"
                        "Tip: Set GCS_BUCKET_NAME in your .env file.\n"
                        "For auth, set GCS_CREDENTIALS_FILE to a service-account key,\n"
                        "or run: gcloud auth application-default login"
                    )
                Clock.schedule_once(_err, 0)

        threading.Thread(target=_run, daemon=True).start()

    def _show_drive_info(self):
        try:
            info = self.client.get_drive_info(self.project_id)
            link = info.get("project_folder_link")
            self._finance_label.text = (f"Drive:\n{link}" if link else
                "Drive not configured.\nTap 'Setup Google Drive Folders' first.")
        except Exception as e:
            self._finance_label.text = f"Error: {e}"

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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _go_to(self, screen):
        self.manager.get_screen(screen).set_project(self.project_id)
        self.manager.current = screen

    def _delete_estimate(self, estimate_id):
        try:
            self.client.delete_estimate(estimate_id)
            show_toast("Estimate deleted.")
            Clock.schedule_once(lambda dt: self._switch_tab("estimates"), 0.2)
        except Exception as e:
            show_toast(f"Error: {e}")

    def _delete_invoice(self, invoice_id):
        try:
            self.client.delete_invoice(invoice_id)
            show_toast("Invoice deleted.")
            Clock.schedule_once(lambda dt: self._switch_tab("invoices"), 0.2)
        except Exception as e:
            show_toast(f"Error: {e}")

    def _gen_project_summary(self):
        try:
            self._finance_label.text = "Generating project summary…"
            result = self.client.generate_project_summary(self.project_id)
            link = result.get("drive_link") or result.get("pdf_path", "")
            self._finance_label.text = f"Summary saved:\n{link}"
            show_toast("Project summary PDF ready.")
        except Exception as e:
            self._finance_label.text = f"Error: {e}"

    def _gen_estimate_pdf(self, estimate_id):
        try:
            self.client.generate_estimate_pdf(estimate_id)
            show_toast("PDF saved.")
        except Exception as e:
            show_toast(f"PDF error: {e}")

    def _gen_invoice_pdf(self, invoice_id):
        try:
            self.client.generate_invoice_pdf(invoice_id)
            show_toast("PDF saved.")
        except Exception as e:
            show_toast(f"PDF error: {e}")

    def _push_to_stripe(self, invoice_id):
        try:
            result = self.client.push_invoice_to_stripe(invoice_id)
            show_toast(f"Stripe: {result.get('status', 'created')}")
            Clock.schedule_once(lambda dt: self._switch_tab("invoices"), 0.2)
        except Exception as e:
            show_toast(f"Stripe error: {e}")

    def _sync_stripe(self, invoice_id):
        try:
            result = self.client.sync_invoice_status(invoice_id)
            show_toast(f"Status: {result.get('status')}")
            Clock.schedule_once(lambda dt: self._switch_tab("invoices"), 0.2)
        except Exception as e:
            show_toast(f"Sync error: {e}")

    def _empty_state(self, title, subtitle=""):
        box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(90),
                         padding=[PADDING, dp(16)])
        box.add_widget(ios_label(title, size=16, bold=True, color=LABEL_SECONDARY,
                                  halign="center", size_hint_y=None, height=dp(28)))
        if subtitle:
            box.add_widget(ios_label(subtitle, size=13, color=LABEL_TERTIARY,
                                      halign="center", size_hint_y=None, height=dp(22)))
        return box
