"""Compose the desktop window and enter the WebView2 event loop."""

import os

from dna_retrieval_engine.config import APP_NAME, APP_VERSION
from dna_retrieval_engine.paths import resource_path

from .api import DesktopApi
from .single_instance import SingleInstance


def main() -> None:
    guard = SingleInstance("Local\\NEXUS_DNA_Retrieval_Engine_v1")
    if guard.already_running:
        guard.notify_existing()
        guard.close()
        return
    try:
        import webview

        html_path = resource_path("resources", "web", "index.html").resolve()
        if not html_path.is_file():
            raise RuntimeError(f"前端资源不存在：{html_path}")
        startup_probe_hidden = os.environ.get("DNA_STARTUP_PROBE_HIDDEN") == "1"
        api = DesktopApi()
        # Pass the absolute filesystem path, not a file:// URI.  pywebview
        # serves local paths through its built-in localhost server, which is
        # the supported origin for the JavaScript-Python bridge.
        window = webview.create_window(
            f"{APP_NAME} v{APP_VERSION}",
            url=str(html_path),
            js_api=api,
            width=1440,
            height=900,
            min_size=(1120, 720),
            resizable=True,
            text_select=True,
            hidden=startup_probe_hidden,
            maximized=not startup_probe_hidden,
        )
        api._bind_window(window)
        window.events.closing += api._close
        debug = os.environ.get("DNA_RETRIEVAL_DEBUG") == "1"
        webview.start(gui="edgechromium", debug=debug, http_server=True)
    finally:
        guard.close()
