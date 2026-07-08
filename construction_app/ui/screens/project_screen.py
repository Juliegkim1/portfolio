"""Project detail screen — custom iOS-style tab bar, shadow cards, status badges."""
import subprocess
import sys
import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
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
    ("Contract",  "contract"),
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
        """Single-row bar: current section label on left, ☰ menu button on right."""
        bar = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(46))
        with_bg(bar, WHITE)

        row = BoxLayout(size_hint_y=None, height=dp(44),
                         padding=[dp(14), dp(4), dp(10), dp(4)], spacing=dp(8))

        # Current section label
        self._section_label = Label(
            text="Overview", font_name=FONT, font_size=dp(13),
            color=IOS_BLUE, bold=True,
            halign="left", valign="middle",
        )
        self._section_label.bind(size=self._section_label.setter("text_size"))
        row.add_widget(self._section_label)

        # ☰ Menu button
        menu_btn = Button(
            text="☰  Menu", font_name=FONT, font_size=dp(13),
            background_normal="", background_color=(0, 0, 0, 0),
            color=IOS_BLUE, bold=False,
            size_hint=(None, None), width=dp(96), height=dp(36),
        )
        with menu_btn.canvas.before:
            Color(*IOS_BLUE[:3], 0.12)
            _r = RoundedRectangle(radius=[dp(8)], pos=menu_btn.pos, size=menu_btn.size)
        menu_btn.bind(
            pos=lambda w, *a: setattr(_r, "pos", w.pos),
            size=lambda w, *a: setattr(_r, "size", w.size),
        )
        menu_btn.bind(on_release=self._open_menu)
        self._menu_btn = menu_btn
        row.add_widget(menu_btn)

        bar.add_widget(row)

        sep = BoxLayout(size_hint_y=None, height=dp(1))
        with_bg(sep, SEPARATOR)
        bar.add_widget(sep)
        return bar

    def _open_menu(self, widget):
        """Build and open the dropdown menu with a solid white background."""
        dd = DropDown(auto_width=False, width=dp(230))

        # White background + subtle shadow border on the container
        with dd.canvas.before:
            Color(1, 1, 1, 1)
            dd._bg_rect = Rectangle(pos=dd.pos, size=dd.size)
            Color(0.82, 0.82, 0.82, 1)
            dd._border = Rectangle(pos=dd.pos, size=dd.size)
        dd.bind(
            pos=lambda w, *a: (
                setattr(w._bg_rect, "pos", w.pos),
                setattr(w._border,  "pos", w.pos),
            ),
            size=lambda w, *a: (
                setattr(w._bg_rect, "size", w.size),
                setattr(w._border,  "size", w.size),
            ),
        )

        TAB_ICONS = {
            "overview":  "🏠",
            "estimates": "📋",
            "invoices":  "💵",
            "wbs":       "🗓️",
            "contract":  "📄",
            "finance":   "📈",
        }

        for i, (label, key) in enumerate(TABS):
            is_active = (key == self._active_tab)
            icon = TAB_ICONS.get(key, "•")
            is_last = (i == len(TABS) - 1)

            # Outer wrapper so we can draw a bottom separator
            row = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(52) if is_last else dp(53),
            )
            with row.canvas.before:
                Color(*(IOS_BLUE[:3] + (0.08,)) if is_active else (1, 1, 1, 1))
                row._bg = Rectangle(pos=row.pos, size=row.size)
            row.bind(
                pos=lambda w, *a: setattr(w._bg, "pos", w.pos),
                size=lambda w, *a: setattr(w._bg, "size", w.size),
            )

            item_btn = Button(
                text=f"   {icon}   {label}",
                font_name=FONT, font_size=dp(14),
                halign="left",
                background_normal="", background_color=(0, 0, 0, 0),
                color=IOS_BLUE if is_active else LABEL_PRIMARY,
                bold=is_active,
                size_hint_y=None, height=dp(52),
            )
            item_btn.bind(on_release=lambda b, k=key: (dd.dismiss(), self._switch_tab(k)))
            row.add_widget(item_btn)

            # Separator line (skip on last item)
            if not is_last:
                sep = BoxLayout(size_hint_y=None, height=dp(1))
                with sep.canvas.before:
                    Color(0.88, 0.88, 0.88, 1)
                    Rectangle(pos=sep.pos, size=sep.size)
                sep.bind(
                    pos=lambda w, *a: None,
                    size=lambda w, *a: None,
                )
                with_bg(sep, (0.88, 0.88, 0.88, 1))
                row.add_widget(sep)

            dd.add_widget(row)

        dd.open(widget)

    # ── Tab switching ─────────────────────────────────────────────────────────

    def _switch_tab(self, key):
        self._active_tab = key
        label = next(lbl for lbl, k in TABS if k == key)
        self._section_label.text = label

        if not self._project_data:
            return

        self._content.clear_widgets()
        {
            "overview":  lambda: self._load_overview(self._project_data),
            "estimates": self._load_estimates_tab,
            "invoices":  self._load_invoices_tab,
            "wbs":       self._load_wbs_tab,
            "contract":  self._load_contract_tab,
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

        layout.add_widget(self._upload_card())

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

    def _upload_card(self):
        """Approved-estimate gate + upload. QuickBooks estimates are built
        outside the app; this turns an approved upload into a scope-of-work
        review (EstimateScreen) rather than the app authoring scope itself."""
        c = shadow_card()
        c.add_widget(ios_label("Approved Estimate Upload", size=14, bold=True,
                                size_hint_y=None, height=dp(22)))

        approved = getattr(self, "_estimate_upload_approved", False)

        if not approved:
            c.add_widget(ios_label(
                "Do you have an approved estimate for this project?",
                size=13, color=LABEL_SECONDARY, size_hint_y=None, height=dp(36)))
            row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
            yes_btn = ios_button("Yes", color=IOS_GREEN, height=dp(40), font_size=13)
            yes_btn.bind(on_press=lambda *a: self._set_estimate_upload_approved(True))
            no_btn = outline_button("No", color=LABEL_SECONDARY, height=dp(40), font_size=13)
            no_btn.bind(on_press=lambda *a: self._set_estimate_upload_approved(False))
            row.add_widget(yes_btn)
            row.add_widget(no_btn)
            c.add_widget(row)
            c.add_widget(ios_label(
                "Waiting for an approved estimate — upload it here once it's approved.",
                size=12, color=LABEL_TERTIARY, size_hint_y=None, height=dp(32)))
        else:
            upload_btn = ios_button("Upload Estimate PDF", color=IOS_INDIGO,
                                     height=dp(46), font_size=14)
            upload_btn.bind(on_press=lambda *a: self._pick_estimate_pdf())
            c.add_widget(upload_btn)
            self._upload_status_label = ios_label("", size=12, color=LABEL_SECONDARY,
                                                    size_hint_y=None, height=dp(20))
            c.add_widget(self._upload_status_label)
            back_btn = outline_button("Not approved yet", color=LABEL_SECONDARY,
                                       height=dp(32), font_size=11)
            back_btn.bind(on_press=lambda *a: self._set_estimate_upload_approved(False))
            c.add_widget(back_btn)

        return c

    def _set_estimate_upload_approved(self, val):
        self._estimate_upload_approved = val
        self._switch_tab("estimates")

    def _pick_estimate_pdf(self):
        try:
            from plyer import filechooser
            filechooser.open_file(
                title="Select approved estimate PDF",
                filters=[("PDF files", "*.pdf")],
                on_selection=self._on_estimate_pdf_selected,
            )
        except (ImportError, NotImplementedError):
            # plyer has no native file-chooser backend registered for this
            # platform/build — surface that clearly rather than crashing.
            show_toast("File picker unavailable on this platform/build.")

    def _on_estimate_pdf_selected(self, selection):
        if not selection:
            return
        path = selection[0]
        self._upload_status_label.text = "Parsing estimate…"

        def _run():
            try:
                parsed = self.client.parse_estimate_pdf(path)
                line_items = parsed.get("line_items", [])
                client_info = parsed.get("client_info", {})
                stored = self.client.save_estimate_upload(self.project_id, path)
                stored_path = stored.get("stored_path") or path
            except Exception as e:
                def _err(dt, m=str(e)):
                    self._upload_status_label.text = f"Error: {m}"
                Clock.schedule_once(_err, 0)
                return

            def _ok(dt):
                self._go_to_estimate_with_prefill(line_items, client_info, stored_path)
            Clock.schedule_once(_ok, 0)

        threading.Thread(target=_run, daemon=True).start()

    def _go_to_estimate_with_prefill(self, line_items, client_info, source_pdf_path):
        # Fill any field the parser didn't find with the project's current value,
        # so the review card never shows blanks the project already has answers for.
        current = self.client.get_project(self.project_id) or {}
        merged_client_info = {
            "name": client_info.get("name") or current.get("customer_name", ""),
            "address": client_info.get("address") or current.get("property_address", ""),
            "phone": client_info.get("phone") or current.get("customer_phone", ""),
            "email": client_info.get("email") or current.get("customer_email", ""),
        }
        screen = self.manager.get_screen("estimate")
        screen.set_project(self.project_id, prefill_line_items=line_items,
                            prefill_client_info=merged_client_info,
                            source_pdf_path=source_pdf_path)
        self.manager.current = "estimate"

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
        edit_btn = outline_button("Edit", color=IOS_BLUE,
                                   height=dp(34), font_size=12, radius=dp(8))
        edit_btn.bind(on_press=lambda _, eid=est["id"]: self._show_edit_estimate(eid))
        btn_row.add_widget(edit_btn)
        pdf_btn = outline_button("PDF", color=IOS_INDIGO,
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

        # Auto-sync any open Stripe invoices in background
        open_ids = [
            inv["id"] for inv in invoices
            if inv.get("stripe_invoice_id") and inv.get("status") == "open"
        ]
        if open_ids:
            import threading
            def _bg_sync():
                changed = False
                for iid in open_ids:
                    try:
                        self.client.sync_invoice_status(iid)
                        changed = True
                    except Exception:
                        pass
                if changed:
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self._switch_tab("invoices"), 0)
            threading.Thread(target=_bg_sync, daemon=True).start()

    def _invoice_card(self, inv):
        sc = STATUS_COLOR.get(inv["status"], LABEL_SECONDARY)
        c = shadow_card(padding=[PADDING, dp(14)], spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(ios_label(inv["invoice_number"], size=14, bold=True))
        top.add_widget(status_badge(inv["status"].upper(), sc))
        c.add_widget(top)

        # Show Stripe invoice number if available
        stripe_num = inv.get("stripe_invoice_number", "")
        if stripe_num:
            c.add_widget(ios_label(f"Stripe: {stripe_num}", size=11,
                                    color=IOS_PURPLE, size_hint_y=None, height=dp(16)))

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

        # "Open in Chrome" button — only shown when a Stripe URL exists
        stripe_url = inv.get("stripe_invoice_url", "")
        if stripe_url:
            open_btn = ios_button("Open Stripe Invoice in Chrome →",
                                   color=IOS_PURPLE, height=dp(38), font_size=12)
            open_btn.bind(on_press=lambda _, u=stripe_url: self._open_in_chrome(u))
            c.add_widget(open_btn)

        return c

    def _show_edit_invoice(self, invoice_id):
        from kivy.uix.popup import Popup
        from kivy.uix.textinput import TextInput
        from kivy.uix.spinner import Spinner as KvSpinner

        inv = self.client.get_invoice(invoice_id)
        if not inv or "error" in inv:
            return

        # Build estimate options for this project
        estimates = []
        estimate_map = {"None (no linked estimate)": None}
        try:
            estimates = self.client.list_estimates(self.project_id)
            for e in estimates:
                key = f"{e['estimate_number']}  ${e['total']:,.2f}"
                estimate_map[key] = e["id"]
        except Exception:
            pass

        spinner_options = list(estimate_map.keys())
        # Pre-select the currently linked estimate
        current_est_id = inv.get("estimate_id")
        current_sel = "None (no linked estimate)"
        for k, v in estimate_map.items():
            if v == current_est_id:
                current_sel = k
                break

        # ── Popup layout ──────────────────────────────────────────────────────
        wrapper = BoxLayout(orientation="vertical", spacing=0)
        with_bg(wrapper, (1, 1, 1, 1))

        # Title bar
        title_bar = BoxLayout(size_hint_y=None, height=dp(50),
                               padding=[dp(16), dp(8)])
        with_bg(title_bar, (0.12, 0.29, 0.53, 1))
        title_bar.add_widget(ios_label("Edit Invoice", size=16, bold=True,
                                        color=(1, 1, 1, 1), halign="center"))
        wrapper.add_widget(title_bar)

        scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
        form = BoxLayout(orientation="vertical", size_hint_y=None,
                          padding=[dp(16), dp(12)], spacing=dp(10))
        form.bind(minimum_height=form.setter("height"))

        def _ti(hint="", text="", required=False):
            return TextInput(
                hint_text=hint, text=text, multiline=False,
                font_name=FONT, font_size=dp(14),
                foreground_color=(0, 0, 0, 1),
                hint_text_color=(0.6, 0.6, 0.6, 1),
                background_color=(0.94, 0.94, 0.96, 1),
                cursor_color=IOS_BLUE,
                size_hint_y=None, height=dp(44),
                padding=[dp(10), dp(10)],
            )

        def _row(label_text, widget):
            col = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(68), spacing=dp(4))
            col.add_widget(ios_label(label_text, size=12, bold=True,
                                      color=LABEL_SECONDARY,
                                      size_hint_y=None, height=dp(20)))
            col.add_widget(widget)
            return col

        desc_ti   = _ti(hint="Invoice description", text=inv["description"])
        amt_ti    = _ti(hint="0.00", text=str(inv["amount"]))
        tax_ti    = _ti(hint="0.00", text=str(inv["tax_amount"]))
        notes_ti  = _ti(hint="Optional notes", text=inv["notes"] or "")

        from ui.widgets import date_input as _date_input
        due_container, due_ti = _date_input(hint="YYYY-MM-DD",
                                             text=inv["due_date"] or "",
                                             height=dp(44))

        est_spinner = KvSpinner(
            text=current_sel,
            values=spinner_options,
            font_name=FONT, font_size=dp(13),
            background_color=(0.94, 0.94, 0.96, 1),
            background_normal="", color=(0, 0, 0, 1),
            size_hint_y=None, height=dp(44),
        )

        form.add_widget(_row("Description *", desc_ti))
        form.add_widget(_row("Amount ($) *",   amt_ti))
        form.add_widget(_row("Tax Amount ($)", tax_ti))

        due_col = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(68), spacing=dp(4))
        due_col.add_widget(ios_label("Due Date", size=12, bold=True,
                                      color=LABEL_SECONDARY,
                                      size_hint_y=None, height=dp(20)))
        due_col.add_widget(due_container)
        form.add_widget(due_col)

        form.add_widget(_row("Linked Estimate", est_spinner))
        form.add_widget(_row("Notes",           notes_ti))

        scroll.add_widget(form)
        wrapper.add_widget(scroll)

        # Button row
        btn_row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12),
                             padding=[dp(16), dp(6)])
        with_bg(btn_row, (1, 1, 1, 1))

        popup = Popup(title="", content=wrapper,
                       size_hint=(0.92, 0.82),
                       background="", background_color=(0, 0, 0, 0),
                       separator_height=0, title_size=0)

        cancel_btn = outline_button("Cancel", color=LABEL_SECONDARY, height=dp(44))
        cancel_btn.bind(on_press=popup.dismiss)

        def _save(*a):
            try:
                selected_est = est_spinner.text
                eid = estimate_map.get(selected_est)
                self.client.update_invoice(
                    invoice_id,
                    description=desc_ti.text.strip(),
                    amount=float(amt_ti.text or 0),
                    tax_amount=float(tax_ti.text or 0),
                    due_date=due_ti.text.strip(),
                    notes=notes_ti.text.strip(),
                    estimate_id=eid,
                )
                popup.dismiss()
                show_toast("Invoice updated.")
                Clock.schedule_once(lambda dt: self._switch_tab("invoices"), 0.2)
            except Exception as e:
                show_toast(f"Error: {e}")

        save_btn = ios_button("Save", color=IOS_BLUE, height=dp(44))
        save_btn.bind(on_press=_save)

        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(save_btn)
        wrapper.add_widget(btn_row)
        popup.open()

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

    # ── Contract ──────────────────────────────────────────────────────────────

    def _load_contract_tab(self):
        from kivy.uix.textinput import TextInput
        from kivy.uix.spinner import Spinner as KvSpinner

        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(10),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        # ── Current contract status (persisted — shows "Not available" until
        # one has been generated below) ──────────────────────────────────────
        try:
            self._contract_data = self.client.get_contract(self.project_id)
        except Exception:
            self._contract_data = None
        layout.add_widget(self._contract_status_card())

        layout.add_widget(section_header("Generate / Update Contract"))

        # ── Estimate picker ───────────────────────────────────────────────────
        layout.add_widget(ios_label("Linked Estimate (sets contract price & scope):",
                                     size=12, color=LABEL_SECONDARY,
                                     size_hint_y=None, height=dp(20)))
        estimates = []
        self._contract_estimate_map = {"None": None}
        try:
            estimates = self.client.list_estimates(self.project_id)
            for e in estimates:
                key = f"{e['estimate_number']}  ${e['total']:,.2f}"
                self._contract_estimate_map[key] = e["id"]
        except Exception:
            pass

        spinner_vals = list(self._contract_estimate_map.keys())
        self._contract_estimate_spinner = KvSpinner(
            text=spinner_vals[0] if spinner_vals else "None",
            values=spinner_vals,
            size_hint_y=None, height=dp(40),
            font_name=FONT, font_size=dp(13),
        )
        layout.add_widget(self._contract_estimate_spinner)

        # ── Project Site ──────────────────────────────────────────────────────
        layout.add_widget(ios_label("Project Site Address:", size=12,
                                     color=LABEL_SECONDARY, size_hint_y=None, height=dp(20)))
        self._contract_site = TextInput(
            hint_text="Leave blank to use project property address",
            font_name=FONT, font_size=dp(13),
            size_hint_y=None, height=dp(40),
            multiline=False,
        )
        layout.add_widget(self._contract_site)

        # ── Dates ─────────────────────────────────────────────────────────────
        date_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self._contract_start = TextInput(
            hint_text="Start Date (YYYY-MM-DD)",
            font_name=FONT, font_size=dp(12),
            multiline=False,
        )
        self._contract_end = TextInput(
            hint_text="Completion Date (YYYY-MM-DD)",
            font_name=FONT, font_size=dp(12),
            multiline=False,
        )
        date_row.add_widget(self._contract_start)
        date_row.add_widget(self._contract_end)
        layout.add_widget(ios_label("Approximate Start / Completion Dates:", size=12,
                                     color=LABEL_SECONDARY, size_hint_y=None, height=dp(20)))
        layout.add_widget(date_row)

        # ── Subcontractors ────────────────────────────────────────────────────
        layout.add_widget(section_header("Subcontractors  (AB 1327)"))
        self._contract_sub_rows = []   # list of (name_ti, lic_ti, class_ti, scope_ti)
        self._contract_subs_layout = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(6))
        self._contract_subs_layout.bind(
            minimum_height=self._contract_subs_layout.setter("height"))
        layout.add_widget(self._contract_subs_layout)

        add_sub_btn = outline_button("+ Add Subcontractor", color=IOS_TEAL,
                                      height=dp(36), font_size=12)
        add_sub_btn.bind(on_press=lambda *a: self._add_sub_row())
        layout.add_widget(add_sub_btn)

        # ── Generate button ───────────────────────────────────────────────────
        layout.add_widget(ios_label("", size_hint_y=None, height=dp(6)))  # spacer
        gen_btn = ios_button("Generate Contract PDF", color=IOS_INDIGO,
                              height=dp(50), font_size=15)
        gen_btn.bind(on_press=lambda *a: self._gen_contract_from_form())
        layout.add_widget(gen_btn)

        self._contract_status_label = ios_label("", size=12, color=LABEL_SECONDARY,
                                                  size_hint_y=None, height=dp(40),
                                                  halign="center")
        layout.add_widget(self._contract_status_label)

        sv.add_widget(layout)
        self._content.add_widget(sv)

    def _add_sub_row(self, name="", license="", classification="", scope=""):
        from kivy.uix.textinput import TextInput
        row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        name_ti  = TextInput(hint_text="Name",           text=name,           font_name=FONT, font_size=dp(11), multiline=False)
        lic_ti   = TextInput(hint_text="License #",      text=license,        font_name=FONT, font_size=dp(11), multiline=False, size_hint_x=0.35)
        class_ti = TextInput(hint_text="Classification", text=classification, font_name=FONT, font_size=dp(11), multiline=False, size_hint_x=0.4)
        scope_ti = TextInput(hint_text="Scope",          text=scope,          font_name=FONT, font_size=dp(11), multiline=False)
        for ti in (name_ti, lic_ti, class_ti, scope_ti):
            row.add_widget(ti)
        del_btn = outline_button("✕", color=IOS_RED, height=dp(34), font_size=12, size_hint_x=None, width=dp(32))
        del_btn.bind(on_press=lambda _, r=row: self._remove_sub_row(r))
        row.add_widget(del_btn)
        self._contract_sub_rows.append((name_ti, lic_ti, class_ti, scope_ti, row))
        self._contract_subs_layout.add_widget(row)

    def _remove_sub_row(self, row_widget):
        self._contract_sub_rows = [t for t in self._contract_sub_rows if t[4] is not row_widget]
        self._contract_subs_layout.remove_widget(row_widget)

    def _gen_contract_from_form(self):
        self._contract_status_label.text = "Generating contract PDF…"
        estimate_key = self._contract_estimate_spinner.text
        estimate_id  = self._contract_estimate_map.get(estimate_key)
        start_date   = self._contract_start.text.strip() or None
        end_date     = self._contract_end.text.strip() or None
        site         = self._contract_site.text.strip() or None
        subcontractors = [
            {"name": t[0].text.strip(), "license": t[1].text.strip(),
             "classification": t[2].text.strip(), "scope": t[3].text.strip()}
            for t in self._contract_sub_rows
            if t[0].text.strip()  # only rows with a name filled in
        ]

        def _run():
            try:
                result = self.client.generate_contract(
                    self.project_id,
                    estimate_id=estimate_id,
                    start_date=start_date,
                    completion_date=end_date,
                    subcontractors=subcontractors or None,
                    project_site=site,
                )
                pdf_path = result.get("pdf_path", "")
                def _ok(dt, p=pdf_path):
                    show_toast("Contract PDF ready.")
                    if p:
                        Clock.schedule_once(lambda dt2, _p=p: self._open_pdf(_p), 0.3)
                    self._switch_tab("contract")
                Clock.schedule_once(_ok, 0)
            except Exception as e:
                err = str(e)
                Clock.schedule_once(lambda dt, m=err: setattr(
                    self._contract_status_label, "text", f"Error: {m}"), 0)

        threading.Thread(target=_run, daemon=True).start()

    def _contract_status_card(self):
        """Shows 'Not available' until a contract has been generated below,
        otherwise the persisted contract's status, Adobe Sign actions, and
        its change orders."""
        c = shadow_card()
        contract = self._contract_data

        if not contract:
            c.add_widget(ios_label("Contract", size=14, bold=True,
                                    size_hint_y=None, height=dp(22)))
            c.add_widget(ios_label(
                "Not available — generate one below from an approved estimate.",
                size=13, color=LABEL_SECONDARY, size_hint_y=None, height=dp(36)))
            return c

        top = BoxLayout(size_hint_y=None, height=dp(24))
        top.add_widget(ios_label(contract["contract_number"], size=14, bold=True))
        sc = STATUS_COLOR.get(contract["status"], LABEL_SECONDARY)
        top.add_widget(status_badge(contract["status"].replace("_", " ").title(), sc))
        c.add_widget(top)

        if contract.get("adobe_agreement_status"):
            c.add_widget(ios_label(f"Adobe: {contract['adobe_agreement_status']}",
                                    size=11, color=IOS_PURPLE,
                                    size_hint_y=None, height=dp(16)))

        btn_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        pdf_btn = outline_button("Open PDF", color=IOS_BLUE,
                                  height=dp(34), font_size=12, radius=dp(8))
        pdf_btn.bind(on_press=lambda *a, p=contract["pdf_path"]: self._open_pdf(p))
        btn_row.add_widget(pdf_btn)

        if contract["status"] == "draft":
            send_btn = outline_button("Send for Signature", color=IOS_TEAL,
                                       height=dp(34), font_size=12, radius=dp(8))
            send_btn.bind(on_press=lambda *a, cid=contract["id"]:
                          self._send_contract_for_signature(cid))
            btn_row.add_widget(send_btn)
        else:
            sync_btn = outline_button("Refresh Status", color=IOS_TEAL,
                                       height=dp(34), font_size=12, radius=dp(8))
            sync_btn.bind(on_press=lambda *a, cid=contract["id"]:
                          self._sync_contract_status(cid))
            btn_row.add_widget(sync_btn)
        c.add_widget(btn_row)

        self._contract_adobe_status_label = ios_label(
            "", size=11, color=LABEL_SECONDARY, size_hint_y=None, height=dp(18))
        c.add_widget(self._contract_adobe_status_label)

        c.add_widget(section_header("Change Orders"))
        try:
            change_orders = self.client.list_change_orders(contract["id"])
        except Exception:
            change_orders = []
        if not change_orders:
            c.add_widget(ios_label("No change orders yet.", size=12,
                                    color=LABEL_TERTIARY, size_hint_y=None, height=dp(20)))
        for co in change_orders:
            c.add_widget(self._change_order_row(co))

        new_co_btn = outline_button("+ New Change Order", color=IOS_ORANGE,
                                     height=dp(36), font_size=12)
        new_co_btn.bind(on_press=lambda *a, cid=contract["id"]:
                        self._show_change_order_form(cid))
        c.add_widget(new_co_btn)

        return c

    def _change_order_row(self, co):
        row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        sign = "+" if co["price_delta"] >= 0 else "-"
        row.add_widget(ios_label(
            f"{co['change_order_number']}   {sign}${abs(co['price_delta']):,.2f}   "
            f"{co['days_delta']:+d}d",
            size=12, size_hint_x=0.7))
        open_btn = outline_button("Open", color=IOS_BLUE, height=dp(32), font_size=11,
                                   size_hint_x=None, width=dp(70))
        open_btn.bind(on_press=lambda *a, p=co["pdf_path"]: self._open_pdf(p))
        row.add_widget(open_btn)
        return row

    def _send_contract_for_signature(self, contract_id):
        self._contract_adobe_status_label.text = "Checking Adobe authorization…"

        def _run():
            try:
                status = self.client.get_adobe_status()
            except Exception as e:
                Clock.schedule_once(lambda dt, m=str(e): setattr(
                    self._contract_adobe_status_label, "text", f"Error: {m}"), 0)
                return

            if not status.get("authorized"):
                try:
                    auth = self.client.get_adobe_auth_url()
                except Exception as e:
                    Clock.schedule_once(lambda dt, m=str(e): setattr(
                        self._contract_adobe_status_label, "text", f"Error: {m}"), 0)
                    return

                def _open_browser(dt, url=auth["url"]):
                    import webbrowser
                    webbrowser.open(url)
                    self._contract_adobe_status_label.text = (
                        "Complete sign-in on the Adobe page that just opened, "
                        "then tap 'Send for Signature' again.")
                Clock.schedule_once(_open_browser, 0)
                return

            try:
                self.client.send_contract_for_signature(contract_id)
            except Exception as e:
                Clock.schedule_once(lambda dt, m=str(e): setattr(
                    self._contract_adobe_status_label, "text", f"Error: {m}"), 0)
                return

            def _ok(dt):
                show_toast("Contract sent for signature via Adobe.")
                self._switch_tab("contract")
            Clock.schedule_once(_ok, 0)

        threading.Thread(target=_run, daemon=True).start()

    def _sync_contract_status(self, contract_id):
        def _run():
            try:
                self.client.sync_contract_status(contract_id)
            except Exception as e:
                Clock.schedule_once(lambda dt, m=str(e): setattr(
                    self._contract_adobe_status_label, "text", f"Error: {m}"), 0)
                return
            Clock.schedule_once(lambda dt: self._switch_tab("contract"), 0)

        threading.Thread(target=_run, daemon=True).start()

    def _show_change_order_form(self, contract_id):
        from kivy.uix.popup import Popup
        from kivy.uix.textinput import TextInput
        from ui.widgets import line_item_row

        wrapper = BoxLayout(orientation="vertical")
        with_bg(wrapper, WHITE)
        wrapper.add_widget(ios_label("New Change Order", size=16, bold=True,
                                      halign="center", size_hint_y=None, height=dp(48)))

        sv2 = ScrollView(do_scroll_x=False)
        form = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(10),
                          size_hint_y=None)
        form.bind(minimum_height=form.setter("height"))

        form.add_widget(ios_label("Description", size=12, color=LABEL_SECONDARY,
                                   size_hint_y=None, height=dp(18)))
        desc_input = TextInput(hint_text="Description of the change", font_name=FONT,
                                font_size=dp(13), size_hint_y=None, height=dp(60),
                                multiline=True)
        form.add_widget(desc_input)

        items_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        items_layout.bind(minimum_height=items_layout.setter("height"))
        form.add_widget(items_layout)
        co_items = []

        def _remove_item(card, row_data):
            items_layout.remove_widget(card)
            if row_data in co_items:
                co_items.remove(row_data)

        def _add_item(*a):
            card, row_data = line_item_row(len(co_items) + 1, on_remove=_remove_item)
            co_items.append(row_data)
            items_layout.add_widget(card)

        add_btn = outline_button("+ Add Item", color=IOS_GREEN, height=dp(36), font_size=12)
        add_btn.bind(on_press=_add_item)
        form.add_widget(add_btn)
        _add_item()

        form.add_widget(ios_label("Change in Contract Time (days)", size=12,
                                   color=LABEL_SECONDARY, size_hint_y=None, height=dp(18)))
        days_input = TextInput(hint_text="0", font_name=FONT, font_size=dp(13),
                                size_hint_y=None, height=dp(40), multiline=False)
        form.add_widget(days_input)

        sv2.add_widget(form)
        wrapper.add_widget(sv2)

        btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10),
                             padding=[PADDING, dp(4)])
        popup = Popup(title="", content=wrapper, size_hint=(0.92, 0.88),
                      background="", background_color=(0, 0, 0, 0),
                      separator_height=0, title_size=0)
        cancel_btn = outline_button("Cancel", color=LABEL_SECONDARY, height=dp(44))
        cancel_btn.bind(on_press=popup.dismiss)
        save_btn = ios_button("Create", color=IOS_ORANGE, height=dp(44))

        def _save(*a):
            line_items = []
            for rd in co_items:
                desc = rd["description"].text.strip()
                if not desc:
                    continue
                try:
                    line_items.append({
                        "description": desc,
                        "qty": float(rd["qty"].text or 1),
                        "unit": rd["unit"].text.strip() or "ea",
                        "unit_price": float(rd["unit_price"].text or 0),
                    })
                except ValueError:
                    continue
            try:
                days_delta = int(days_input.text.strip() or 0)
            except ValueError:
                days_delta = 0
            try:
                self.client.create_change_order(
                    contract_id, description=desc_input.text.strip(),
                    line_items=line_items, days_delta=days_delta)
                popup.dismiss()
                show_toast("Change order created.")
                self._switch_tab("contract")
            except Exception as e:
                show_toast(f"Error: {e}")

        save_btn.bind(on_press=_save)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(save_btn)
        wrapper.add_widget(btn_row)
        popup.open()

    # ── Finance ───────────────────────────────────────────────────────────────

    def _load_finance_tab(self):
        sv = ScrollView(do_scroll_x=False)
        layout = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(12),
                            size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        # ── Generate / Cloud Storage actions ─────────────────────────────────
        layout.add_widget(section_header("Documents & Integrations"))

        actions = [
            ("Generate Project Summary PDF",  IOS_BLUE,   self._gen_project_summary),
            ("Generate Reconciliation PDF",   IOS_INDIGO, self._gen_reconciliation),
            ("Export to Quicken (QIF)",       IOS_BLUE,   self._export_quicken),
            ("Setup Cloud Storage Bucket",    IOS_TEAL,   self._setup_drive),
        ]
        for label, color, fn in actions:
            btn = ios_button(label, color=color, height=dp(48), font_size=13, bold=False)
            btn.bind(on_press=lambda _, f=fn: f())
            layout.add_widget(btn)

        self._finance_label = ios_label("", size=12, color=LABEL_SECONDARY,
                                         size_hint_y=None, height=dp(52),
                                         halign="center")
        layout.add_widget(self._finance_label)

        # ── Generated Files ───────────────────────────────────────────────────
        layout.add_widget(section_header("Generated Files"))
        self._files_layout = BoxLayout(orientation="vertical", size_hint_y=None,
                                        spacing=dp(6))
        self._files_layout.bind(minimum_height=self._files_layout.setter("height"))
        layout.add_widget(self._files_layout)
        self._refresh_file_list()

        sv.add_widget(layout)
        self._content.add_widget(sv)

    def _refresh_file_list(self):
        self._files_layout.clear_widgets()
        try:
            files = self.client.list_project_pdfs(self.project_id)
        except Exception:
            files = []

        if not files:
            self._files_layout.add_widget(
                ios_label("No PDFs generated yet.", size=12, color=LABEL_SECONDARY,
                           halign="center", size_hint_y=None, height=dp(32)))
            return

        for f in files:
            self._files_layout.add_widget(self._file_row(f["name"], f["path"]))

    def _file_row(self, name, path):
        from ui.widgets import shadow_card, outline_button, ios_label
        card = shadow_card(padding=[dp(10), dp(8)], spacing=dp(6))
        card.height = dp(68)

        inner = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52),
                          spacing=dp(8))

        # File icon + name
        info = BoxLayout(orientation="vertical", spacing=dp(2))
        # Shorten name for display
        display = name.replace("_", " ").replace(".pdf", "")
        if len(display) > 32:
            display = display[:30] + "…"
        info.add_widget(ios_label("📄 " + display, size=12, bold=True,
                                   color=LABEL_PRIMARY, size_hint_y=None, height=dp(20)))
        import os as _os
        try:
            size_kb = _os.path.getsize(path) // 1024
            info.add_widget(ios_label(f"{size_kb} KB  ·  PDF",
                                       size=11, color=LABEL_SECONDARY,
                                       size_hint_y=None, height=dp(16)))
        except Exception:
            pass
        inner.add_widget(info)

        open_btn = ios_button("Open", height=dp(36), font_size=12,
                               radius=dp(8), size_hint_x=None, width=dp(64))
        open_btn.bind(on_press=lambda _, p=path: self._open_pdf(p))
        inner.add_widget(open_btn)

        card.add_widget(inner)
        return card

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
        pass  # replaced by inline file list — no longer needed

    def _open_pdf(self, path):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", path])
            else:
                subprocess.Popen(["start", path], shell=True)
        except Exception as e:
            show_toast(f"Cannot open: {e}")

    def _open_in_chrome(self, url):
        if not url:
            show_toast("No Stripe URL — push to Stripe first.")
            return
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Google Chrome", url])
            elif sys.platform.startswith("linux"):
                subprocess.Popen(["google-chrome", url])
            else:
                subprocess.Popen(["start", "chrome", url], shell=True)
        except Exception as e:
            # Fallback: open with default browser
            try:
                subprocess.Popen(["open", url])
            except Exception:
                show_toast(f"Cannot open browser: {e}")

    def _export_quicken(self):
        try:
            result = self.client.export_to_quicken(self.project_id)
            self._finance_label.text = f"QIF saved:\n{result.get('qif_file', '')}"
        except Exception as e:
            self._finance_label.text = f"Error: {e}"

    def _gen_reconciliation(self):
        self._finance_label.text = "Generating reconciliation report…"

        def _run():
            try:
                result = self.client.generate_reconciliation_report(self.project_id)
                sheet_url = result.get("sheet_url") or ""
                msg = "Reconciliation PDF ready."
                if sheet_url:
                    msg += f"\n\nGoogle Sheet:\n{sheet_url}"
                def _ok(dt, m=msg):
                    self._finance_label.text = m
                    show_toast("Reconciliation complete.")
                    Clock.schedule_once(lambda dt2: self._refresh_file_list(), 0.3)
                Clock.schedule_once(_ok, 0)
            except Exception as e:
                err = str(e)
                def _err(dt, m=err):
                    self._finance_label.text = f"Error: {m}"
                Clock.schedule_once(_err, 0)

        threading.Thread(target=_run, daemon=True).start()

    def _gen_contract(self):
        self._finance_label.text = "Generating contract PDF…"

        def _run():
            try:
                result = self.client.generate_contract(self.project_id)
                pdf_path = result.get("pdf_path", "")
                def _ok(dt, p=pdf_path):
                    self._finance_label.text = ""
                    show_toast("Contract PDF ready.")
                    Clock.schedule_once(lambda dt2: self._refresh_file_list(), 0.3)
                    if p:
                        Clock.schedule_once(lambda dt2, _p=p: self._open_pdf(_p), 0.5)
                Clock.schedule_once(_ok, 0)
            except Exception as e:
                err = str(e)
                def _err(dt, m=err):
                    self._finance_label.text = f"Error: {m}"
                Clock.schedule_once(_err, 0)

        threading.Thread(target=_run, daemon=True).start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _go_to(self, screen):
        self.manager.get_screen(screen).set_project(self.project_id)
        self.manager.current = screen

    def _show_edit_estimate(self, estimate_id):
        screen = self.manager.get_screen("estimate")
        screen.project_id = self.project_id
        screen.set_estimate(estimate_id)
        self.manager.current = "estimate"

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
            self._finance_label.text = ""
            show_toast("Project summary PDF ready.")
            Clock.schedule_once(lambda dt: self._refresh_file_list(), 0.3)
        except Exception as e:
            self._finance_label.text = f"Error: {e}"

    def _gen_estimate_pdf(self, estimate_id):
        try:
            result = self.client.generate_estimate_pdf(estimate_id)
            path = result.get("pdf_path", "")
            show_toast("PDF saved.")
            self._open_pdf(path)
        except Exception as e:
            show_toast(f"PDF error: {e}")

    def _gen_invoice_pdf(self, invoice_id):
        try:
            result = self.client.generate_invoice_pdf(invoice_id)
            path = result.get("pdf_path", "")
            show_toast("PDF saved.")
            self._open_pdf(path)
        except Exception as e:
            show_toast(f"PDF error: {e}")

    def _push_to_stripe(self, invoice_id):
        try:
            result = self.client.push_invoice_to_stripe(invoice_id)
            show_toast(f"Stripe: {result.get('status', 'created')}")
            url = result.get("stripe_invoice_url", "")
            # Refresh invoices tab so "Open in Chrome" button appears
            Clock.schedule_once(lambda dt: self._switch_tab("invoices"), 0.2)
            if url:
                Clock.schedule_once(lambda dt, u=url: self._open_in_chrome(u), 0.5)
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
