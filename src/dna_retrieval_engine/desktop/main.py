"""Compose the desktop window and enter the WebView2 event loop."""

import os

from dna_retrieval_engine.config import APP_NAME
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
        api = DesktopApi()
        window = webview.create_window(
            APP_NAME,
            url=html_path.as_uri(),
            js_api=api,
            width=1440,
            height=900,
            min_size=(1120, 720),
            resizable=True,
            text_select=True,
        )
        api.bind_window(window)
        debug = os.environ.get("DNA_RETRIEVAL_DEBUG") == "1"
        webview.start(gui="edgechromium", debug=debug)
    finally:
        guard.close()
