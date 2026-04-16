"""
Cabrera Construction App
Mobile (iOS) + Desktop application built with Kivy + MCP.

Set API_BASE_URL env var to connect to the Cloud Run backend instead of local DB:
  export API_BASE_URL=https://cabrera-construction-api-xxxxx-uc.a.run.app
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.core.window import Window

# iOS-friendly window size hint (use full screen on mobile)
if Window is not None:
    Window.size = (390, 844)  # iPhone 14 Pro dimensions in points

_api_url = os.getenv("API_BASE_URL", "").strip()
if _api_url:
    from mcp_client.client import HTTPClient as _Client
    _client_factory = lambda: _Client(_api_url)
else:
    from mcp_client.client import DirectClient as _Client
    _client_factory = _Client

from ui.screens import CoverScreen, HomeScreen, ProjectScreen, EstimateScreen, InvoiceScreen, FinanceScreen


class ConstructionApp(App):
    title = "Cabrera Construction"

    def build(self):
        client = _client_factory()
        sm = ScreenManager(transition=SlideTransition())

        sm.add_widget(CoverScreen(name="cover"))
        sm.add_widget(HomeScreen(client=client, name="home"))
        sm.add_widget(ProjectScreen(client=client, name="project"))
        sm.add_widget(EstimateScreen(client=client, name="estimate"))
        sm.add_widget(InvoiceScreen(client=client, name="invoice"))
        sm.add_widget(FinanceScreen(client=client, name="finance"))

        sm.current = "cover"
        return sm


if __name__ == "__main__":
    ConstructionApp().run()
