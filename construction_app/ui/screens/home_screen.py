from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp
from kivy.clock import Clock
import os

from ui.theme import (FONT, BG_PRIMARY, BG_SECONDARY, IOS_BLUE, IOS_GREEN,
                       IOS_ORANGE, IOS_RED, LABEL_PRIMARY, LABEL_SECONDARY,
                       WHITE, CARD_RADIUS, NAV_HEIGHT, PADDING, SMALL_PAD,
                       STATUS_COLOR, SEPARATOR)
from ui.widgets import (with_bg, ios_label, ios_button, ios_input,
                         nav_bar, show_toast, edit_form_popup)

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "images", "logo.png")

PROJECT_FIELDS = [
    ("Project Name", "name", "e.g. Kitchen Remodel", True),
    ("Property Address", "property_address", "123 Main St, City, CA", True),
    ("Customer Name", "customer_name", "Full name", True),
    ("Customer Email", "customer_email", "email@example.com", True),
    ("Customer Phone", "customer_phone", "(415) 000-0000", False),
    ("Project Type", "project_type", "e.g. Bathroom Remodel", False),
    ("Notes", "notes", "Optional notes", False),
]


class HomeScreen(Screen):
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)
        self.client = client
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", spacing=0)
        with_bg(root, BG_SECONDARY)

        # ── Brand header with logo ───────────────────────────────────────────
        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(90),
                            padding=[dp(12), dp(8)])
        with_bg(header, WHITE)
        if os.path.exists(_LOGO_PATH):
            logo = Image(source=_LOGO_PATH, size_hint=(None, None),
                         size=(dp(160), dp(74)), fit_mode="contain",
                         pos_hint={"center_x": 0.5})
            header.add_widget(logo)
        else:
            # Fallback text if logo file not found
            header.add_widget(ios_label("CABRERA CONSTRUCTION", size=17, bold=True,
                                         color=IOS_BLUE, halign="center",
                                         size_hint_y=None, height=dp(74)))
        root.add_widget(header)

        # Thin separator
        sep = BoxLayout(size_hint_y=None, height=dp(1))
        with_bg(sep, (0.88, 0.88, 0.90, 1))
        root.add_widget(sep)

        # Navigation bar
        add_btn = ios_button("+ New", height=dp(34), font_size=14,
                              radius=dp(17), size_hint_x=None, width=dp(80))
        add_btn.bind(on_press=self._show_new_project_form)
        bar, _ = nav_bar("Projects", right_widget=add_btn)
        root.add_widget(bar)

        # Project list
        scroll = ScrollView(do_scroll_x=False)
        self._grid = GridLayout(cols=1, spacing=dp(1), padding=[0, dp(8), 0, dp(20)],
                                 size_hint_y=None)
        self._grid.bind(minimum_height=self._grid.setter('height'))
        scroll.add_widget(self._grid)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_enter(self):
        Clock.schedule_once(lambda dt: self._refresh())

    def _refresh(self):
        self._grid.clear_widgets()
        try:
            projects = self.client.list_projects()
        except Exception as e:
            self._grid.add_widget(
                ios_label(f"Error loading projects: {e}", color=IOS_RED,
                           size_hint_y=None, height=dp(50)))
            return

        if not projects:
            empty = BoxLayout(size_hint_y=None, height=dp(120),
                               padding=PADDING, orientation="vertical")
            empty.add_widget(ios_label("No projects yet.", size=17, bold=True,
                                        color=LABEL_PRIMARY, halign="center"))
            empty.add_widget(ios_label("Tap '+ New' to create your first project.",
                                        size=14, color=LABEL_SECONDARY, halign="center"))
            self._grid.add_widget(empty)
            return

        for p in projects:
            self._grid.add_widget(self._project_row(p))

    def _project_row(self, p: dict):
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(72),
                         padding=[PADDING, dp(10)], spacing=SMALL_PAD)
        with_bg(row, WHITE)

        info = BoxLayout(orientation="vertical", spacing=dp(3))
        info.add_widget(ios_label(p["name"], size=16, bold=True, color=LABEL_PRIMARY))
        info.add_widget(ios_label(p["customer"], size=13, color=LABEL_SECONDARY))
        info.add_widget(ios_label(p["address"], size=12, color=LABEL_SECONDARY))
        row.add_widget(info)

        right = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(100),
                           spacing=dp(6))
        status_c = STATUS_COLOR.get(p["status"], LABEL_SECONDARY)
        right.add_widget(ios_label(p["status"].replace("_", " ").title(),
                                    size=11, bold=True, color=status_c, halign="right"))
        open_btn = ios_button("Open  ›", height=dp(30), font_size=13, radius=dp(15),
                               size_hint_x=None, width=dp(80))
        open_btn.bind(on_press=lambda *a: self._open_project(p["id"]))
        right.add_widget(open_btn)

        edit_btn = Button(text="Edit", font_name=FONT, font_size=dp(12),
                           color=IOS_BLUE, background_color=(0,0,0,0),
                           background_normal='', size_hint_x=None, width=dp(30))
        edit_btn.bind(on_press=lambda *a: self._show_edit_form(p["id"]))
        right.add_widget(edit_btn)
        row.add_widget(right)

        # Separator line
        sep = BoxLayout(size_hint_y=None, height=dp(0.5))
        with_bg(sep, SEPARATOR)

        wrapper = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(72))
        wrapper.add_widget(row)
        return wrapper

    def _open_project(self, project_id):
        self.manager.get_screen("project").load_project(project_id)
        self.manager.current = "project"

    def _show_new_project_form(self, *args):
        def _save(data):
            if not all(data.get(k) for k in ["name", "property_address",
                                               "customer_name", "customer_email"]):
                show_toast("Name, address, customer name & email are required.")
                return
            try:
                self.client.create_project(**data)
                show_toast(f"Project '{data['name']}' created!")
                Clock.schedule_once(lambda dt: self._refresh(), 0.3)
            except Exception as e:
                show_toast(f"Error: {e}")

        popup = edit_form_popup("New Project", PROJECT_FIELDS, _save)
        popup.open()

    def _show_edit_form(self, project_id):
        project = self.client.get_project(project_id)
        if not project or "error" in project:
            return

        def _save(data):
            try:
                self.client.update_project(
                    project_id,
                    name=data.get("name", project["name"]),
                    property_address=data.get("property_address", project["property_address"]),
                    customer_name=data.get("customer_name", project["customer_name"]),
                    customer_phone=data.get("customer_phone", project["customer_phone"]),
                    customer_email=data.get("customer_email", project["customer_email"]),
                    project_type=data.get("project_type", project["project_type"]),
                    notes=data.get("notes", project["notes"]),
                )
                show_toast("Project updated.")
                Clock.schedule_once(lambda dt: self._refresh(), 0.3)
            except Exception as e:
                show_toast(f"Error: {e}")

        popup = edit_form_popup("Edit Project", PROJECT_FIELDS, _save, prefill=project)
        popup.open()
