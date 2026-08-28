from pathlib import Path
from time import monotonic

from dna_retrieval_engine.desktop.api import DesktopApi
from dna_retrieval_engine.desktop.task_controller import TaskController

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "src" / "dna_retrieval_engine" / "resources" / "web"


def test_api_rejects_operations_without_required_data() -> None:
    api = DesktopApi()
    assert api.start_build_index(6) == {"ok": False, "error": "请先生成或加载数据集"}
    assert api.start_search({"k": 6, "max_mismatches": 2}) == {
        "ok": False,
        "error": "请先生成或加载数据集",
    }
    assert api.start_export_results({"output_directory": str(ROOT)}) == {
        "ok": False,
        "error": "尚未完成检索，无法导出报告",
    }


def test_task_controller_locks_duplicate_starts_without_waiting() -> None:
    controller = TaskController()
    accepted = controller.start("slow-test", lambda context: __import__("time").sleep(0.2))
    started_at = monotonic()
    rejected = controller.start("duplicate", lambda context: None)
    assert monotonic() - started_at < 0.05
    assert accepted["ok"] is True
    assert rejected["ok"] is False


def test_frontend_guardrails_are_wired_without_browser_automation() -> None:
    app = (WEB / "app.js").read_text(encoding="utf-8")
    pages = (WEB / "pages.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    report = (WEB / "pages" / "report.html").read_text(encoding="utf-8")
    styles = (WEB / "styles.css").read_text(encoding="utf-8")

    assert 'max="3"' in html
    assert 'id="toggle-inspector"' in html and 'id="open-inspector-button"' in html
    assert "setInspectorCollapsed" in app and "inspector-collapsed" in styles
    assert 'nodes("button")' in app and "only the local Inspector toggle" in app
    assert "nearest_hit" in app and "is-rejected" in app
    assert "错配" in app and "H=" not in app
    assert "distance-reject-label" in html
    assert "repeat(4" in styles and "0 个错配 · 0%" in report
    assert "table-layout: fixed" in (WEB / "pages.css").read_text(encoding="utf-8")
    assert "h4" not in pages.lower()
    assert "taskRunning()" in pages and "lockPageActions" in pages and "disabled" in pages
