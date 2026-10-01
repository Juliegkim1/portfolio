"""Estimate creation screen — section-grouped table layout for easy review."""
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
        self._edit_mode = False
        self._edit_id = None
        # Line items are held as plain data dicts (not widget refs) — the table
        # is a pure render of this list, so typing in a field just updates the
        # dict + a total label, while adding/removing/reassigning a section
        # triggers a full (cheap) re-render grouped by section.
        self._line_items = []
        self._section_subtotal_labels = {}
        self._item_total_labels = {}
        self._ps_rows = []
        self._source_pdf_path = None
        self._client_info_inputs = {}
        self._project_snapshot = None
        self._build()

    def set_project(self, project_id, prefill_line_items=None,
                     prefill_client_info=None, source_pdf_path=None):
        """Called when creating a new estimate. If prefill_line_items is given
        (best-effort scope parsed from an uploaded estimate PDF), the table is
        pre-populated, grouped by section, for review/editing instead of
        starting blank. If prefill_client_info is given, an editable Client
        Info card is shown too — on save its values are written back to the
        Project record."""
        self.project_id = project_id
        self._edit_mode = False
        self._edit_id = None
        self._source_pdf_path = source_pdf_path
        self._nav_title.text = "New Estimate"
        self._tax_input.text = ""
        self._permit_input.text = ""
        self._discount_input.text = ""
        for _, desc_w, amt_w, date_w in self._ps_rows:
            desc_w.text = ""
            amt_w.text = ""
            date_w.text = ""

        self._client_info_container.clear_widgets()
        self._client_info_inputs = {}
        self._project_snapshot = None
        if prefill_client_info is not None:
            self._project_snapshot = self.client.get_project(project_id)
            self._client_info_container.add_widget(
                self._build_client_info_card(prefill_client_info))

        self._line_items = []
        if prefill_line_items:
            for it in prefill_line_items:
                self._line_items.append({
                    "section": it.get("section") if it.get("section") in SECTIONS else SECTIONS[2],
                    "description": it.get("description", ""),
                    "qty": str(it.get("qty", 1)),
                    "unit": it.get("unit", "ea"),
                    "unit_price": str(it.get("unit_price", 0)),
                })
            show_toast(f"Parsed {len(prefill_line_items)} line item(s) — review before saving.")
        self._render_items_table()

    def set_estimate(self, estimate_id):
        """Called when editing an existing estimate — pre-fills all fields."""
        data = self.client.get_estimate(estimate_id)
        if not data or "error" in data:
            show_toast("Could not load estimate.")
            return
        self._edit_mode = True
        self._edit_id = estimate_id
        self._source_pdf_path = None
        self._client_info_container.clear_widgets()
        self._client_info_inputs = {}
        self._project_snapshot = None
        self._nav_title.text = f"Edit {data['estimate_number']}"

        # Pricing options
        self._tax_input.text    = str(round(data.get("tax_rate", 0) * 100, 4)).rstrip("0").rstrip(".")
        self._permit_input.text = str(data.get("permit_fees", 0) or "")
        self._discount_input.text = str(data.get("discount", 0) or "")

        # Line items
        self._line_items = [
            {
                "section": it.get("section") if it.get("section") in SECTIONS else SECTIONS[0],
                "description": it.get("description", ""),
                "qty": str(it.get("qty", 1)),
                "unit": it.get("unit", "ea"),
                "unit_price": str(it.get("unit_price", 0)),
            }
            for it in data.get("line_items", [])
        ]
        self._render_items_table()

        # Payment schedule (fill up to 3 rows)
        ps_list = data.get("payment_schedule", [])
        for idx, (lbl, desc_w, amt_w, date_w) in enumerate(self._ps_rows):
            if idx < len(ps_list):
                desc_w.text  = ps_list[idx].get("description", "")
                amt_w.text   = str(ps_list[idx].get("amount", ""))
                date_w.text  = ps_list[idx].get("due_date", "") or ""
            else:
                desc_w.text = ""
                amt_w.text  = ""
                date_w.text = ""

    def _build(self):
        root = BoxLayout(orientation="vertical")
        with_bg(root, BG_SECONDARY)

        bar, self._nav_title = nav_bar("New Estimate", back_label="Project",
                                        on_back=lambda *a: setattr(self.manager, 'current', 'project'))
        root.add_widget(bar)

        scroll = ScrollView(do_scroll_x=False)
        form = BoxLayout(orientation="vertical", padding=PADDING, spacing=dp(14),
                          size_hint_y=None)
        form.bind(minimum_height=form.setter('height'))

        # ── Client Info (only populated when created from an estimate upload) ──
        self._client_info_container = BoxLayout(orientation="vertical",
                                                  size_hint_y=None, spacing=dp(14))
        self._client_info_container.bind(
            minimum_height=self._client_info_container.setter('height'))
        form.add_widget(self._client_info_container)

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

        # ── Line Items (grouped by section, scrollable as part of the form) ──
        form.add_widget(ios_label("Line Items", size=15, bold=True,
                                   color=LABEL_PRIMARY, size_hint_y=None, height=dp(28)))

        self._sections_layout = BoxLayout(orientation="vertical", size_hint_y=None,
                                           spacing=dp(10))
        self._sections_layout.bind(minimum_height=self._sections_layout.setter('height'))
        form.add_widget(self._sections_layout)

        subtotal_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        subtotal_row.add_widget(ios_label("Estimate Subtotal", size=13, bold=True,
                                           color=LABEL_SECONDARY))
        self._grand_total_lbl = ios_label("$0.00", size=16, bold=True, color=IOS_BLUE,
                                           halign="right")
        subtotal_row.add_widget(self._grand_total_lbl)
        form.add_widget(subtotal_row)

        add_btn = ios_button("+ Add Line Item", color=IOS_GREEN,
                              height=dp(48), font_size=15, bold=True)
        add_btn.bind(on_press=lambda *a: self._add_line_item_row())
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
        self._save_btn = ios_button("Save Estimate", height=dp(54), font_size=16, bold=True)
        self._save_btn.bind(on_press=self._save_estimate)
        form.add_widget(self._save_btn)

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

    def _build_client_info_card(self, client_info):
        """Editable Owner/Client info, pre-filled from the uploaded estimate PDF
        (falling back to the project's current values). Saved back to the
        Project record on Save so it stays the single source of truth used by
        the contract and Adobe Sign."""
        card = self._white_card()
        card.add_widget(ios_label("Client Info (from uploaded estimate)", size=13,
                                   bold=True, color=LABEL_SECONDARY,
                                   size_hint_y=None, height=dp(24)))
        for label, key, hint in [
            ("Name", "name", "Owner name"),
            ("Address", "address", "Property address"),
            ("Phone", "phone", "(415) 000-0000"),
            ("Email", "email", "email@example.com"),
        ]:
            card.add_widget(_field_label(label))
            ti = _field_input(hint=hint, text=client_info.get(key, ""))
            self._client_info_inputs[key] = ti
            card.add_widget(ti)
        return card

    # ── Line-item table (grouped by section) ────────────────────────────────

    def _add_line_item_row(self, section=None, description="", qty="", unit="", unit_price=""):
        default_section = section if section in SECTIONS else SECTIONS[2]
        self._line_items.append({
            "section": default_section, "description": description,
            "qty": str(qty) if qty not in (None, "") else "",
            "unit": unit, "unit_price": str(unit_price) if unit_price not in (None, "") else "",
        })
        self._render_items_table()

    def _render_items_table(self):
        """Rebuilds the whole table grouped by section — cheap enough for a
        typical estimate's item count, and avoids fiddly incremental widget
        re-ordering when an item's section changes. Only called on structural
        changes (add/remove/reassign-section); typing in a field just mutates
        the underlying dict and updates a total label in place."""
        self._sections_layout.clear_widgets()
        self._section_subtotal_labels = {}
        self._item_total_labels = {}

        by_section = {}
        for idx, item in enumerate(self._line_items):
            by_section.setdefault(item["section"], []).append((idx, item))

        for section in SECTIONS:
            rows = by_section.get(section)
            if not rows:
                continue
            self._sections_layout.add_widget(self._build_section_block(section, rows))

        self._update_totals()

    def _build_section_block(self, section, rows):
        block = self._white_card()

        header = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(6))
        header.add_widget(ios_label(section, size=12, bold=True, color=IOS_BLUE,
                                     size_hint_x=0.7))
        subtotal_lbl = ios_label("$0.00", size=12, bold=True, color=LABEL_SECONDARY,
                                  halign="right", size_hint_x=0.3)
        header.add_widget(subtotal_lbl)
        block.add_widget(header)
        self._section_subtotal_labels[section] = subtotal_lbl

        for idx, item in rows:
            block.add_widget(self._build_item_row(idx, item))
        return block

    def _build_item_row(self, idx, item):
        row = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        row.bind(minimum_height=row.setter('height'))

        desc_ti = _field_input(hint="e.g. Demo existing tile flooring",
                                text=item["description"])

        def _on_desc(instance, value, i=idx):
            self._line_items[i]["description"] = value
        desc_ti.bind(text=_on_desc)
        row.add_widget(desc_ti)

        nums_row = BoxLayout(size_hint_y=None, height=INPUT_H, spacing=dp(6))

        qty_ti = _field_input(hint="Qty", text=item["qty"])
        unit_ti = _field_input(hint="Unit", text=item["unit"])
        price_ti = _field_input(hint="Price $", text=item["unit_price"])
        qty_ti.size_hint_x = 0.2
        unit_ti.size_hint_x = 0.2
        price_ti.size_hint_x = 0.3

        total_lbl = Label(text="$0.00", font_name=FONT, font_size=dp(14), bold=True,
                           color=IOS_BLUE, halign="center", valign="middle",
                           size_hint_x=0.3, size_hint_y=None, height=INPUT_H)
        total_lbl.bind(size=total_lbl.setter('text_size'))
        self._item_total_labels[idx] = total_lbl

        def _on_qty(instance, value, i=idx):
            self._line_items[i]["qty"] = value
            self._update_totals()

        def _on_unit(instance, value, i=idx):
            self._line_items[i]["unit"] = value

        def _on_price(instance, value, i=idx):
            self._line_items[i]["unit_price"] = value
            self._update_totals()

        qty_ti.bind(text=_on_qty)
        unit_ti.bind(text=_on_unit)
        price_ti.bind(text=_on_price)

        nums_row.add_widget(qty_ti)
        nums_row.add_widget(unit_ti)
        nums_row.add_widget(price_ti)
        nums_row.add_widget(total_lbl)
        row.add_widget(nums_row)

        ctrl_row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(6))
        section_spinner = Spinner(
            text=item["section"], values=SECTIONS,
            font_name=FONT, font_size=dp(11),
            background_color=(0.94, 0.94, 0.96, 1),
            background_normal='', color=(0, 0, 0, 1),
            size_hint_x=0.7,
        )

        def _on_section(instance, value, i=idx):
            self._line_items[i]["section"] = value
            self._render_items_table()
        section_spinner.bind(text=_on_section)
        ctrl_row.add_widget(section_spinner)

        del_btn = ios_button("✕ Remove", color=IOS_RED, height=dp(32),
                              font_size=12, radius=dp(8), size_hint_x=0.3)

        def _on_remove(*a, i=idx):
            del self._line_items[i]
            self._render_items_table()
        del_btn.bind(on_press=_on_remove)
        ctrl_row.add_widget(del_btn)
        row.add_widget(ctrl_row)

        return row

    def _update_totals(self):
        section_sums = {}
        grand_total = 0.0
        for idx, item in enumerate(self._line_items):
            try:
                t = float(item.get("qty") or 0) * float(item.get("unit_price") or 0)
            except ValueError:
                t = 0.0
            if idx in self._item_total_labels:
                self._item_total_labels[idx].text = f"${t:,.2f}"
            section_sums[item["section"]] = section_sums.get(item["section"], 0.0) + t
            grand_total += t

        for section, lbl in self._section_subtotal_labels.items():
            lbl.text = f"${section_sums.get(section, 0.0):,.2f}"

        self._grand_total_lbl.text = f"${grand_total:,.2f}"

    def _save_estimate(self, *args):
        if not self.project_id:
            show_toast("No project selected.")
            return

        line_items = []
        for item in self._line_items:
            desc = (item.get("description") or "").strip()
            if not desc:
                continue
            try:
                line_items.append({
                    "section": item.get("section", SECTIONS[2]),
                    "description": desc,
                    "qty": float(item.get("qty") or 1),
                    "unit": (item.get("unit") or "ea").strip() or "ea",
                    "unit_price": float(item.get("unit_price") or 0),
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

        tax_rate    = float(self._tax_input.text or 0) / 100
        permit_fees = float(self._permit_input.text or 0)
        discount    = float(self._discount_input.text or 0)

        try:
            if self._edit_mode and self._edit_id:
                result = self.client.update_estimate(
                    self._edit_id,
                    line_items=line_items,
                    payment_schedule=payment_schedule,
                    tax_rate=tax_rate,
                    permit_fees=permit_fees,
                    discount=discount,
                )
                show_toast(f"Estimate updated — ${result['total']:,.2f}")
            else:
                result = self.client.create_estimate(
                    project_id=self.project_id,
                    line_items=line_items,
                    payment_schedule=payment_schedule,
                    tax_rate=tax_rate,
                    permit_fees=permit_fees,
                    discount=discount,
                    source_pdf_path=self._source_pdf_path,
                )
                if self._client_info_inputs and self._project_snapshot:
                    snap = self._project_snapshot
                    self.client.update_project(
                        self.project_id,
                        name=snap.get("name", ""),
                        property_address=self._client_info_inputs["address"].text.strip()
                            or snap.get("property_address", ""),
                        customer_name=self._client_info_inputs["name"].text.strip()
                            or snap.get("customer_name", ""),
                        customer_phone=self._client_info_inputs["phone"].text.strip()
                            or snap.get("customer_phone", ""),
                        customer_email=self._client_info_inputs["email"].text.strip()
                            or snap.get("customer_email", ""),
                        project_type=snap.get("project_type", "General"),
                        notes=snap.get("notes", ""),
                        start_date=snap.get("start_date", ""),
                        duration_days=snap.get("duration_days", ""),
                    )
                show_toast(f"Estimate {result['estimate_number']} — ${result['total']:,.2f}")
            def _back(dt):
                ps = self.manager.get_screen("project")
                ps.load_project(self.project_id)
                self.manager.current = "project"
            Clock.schedule_once(_back, 1.5)
        except Exception as e:
            show_toast(f"Error: {e}")
