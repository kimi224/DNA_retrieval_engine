import re
from pathlib import Path
from time import monotonic

from dna_retrieval_engine.desktop.api import DesktopApi
from dna_retrieval_engine.desktop.task_controller import TaskController

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "src" / "dna_retrieval_engine" / "resources" / "web"


def test_api_rejects_operations_without_required_data() -> None:
    api = DesktopApi()
    assert all(name.startswith("_") for name in vars(api))
    capabilities = api.get_state()["capabilities"]
    assert capabilities["can_configure"] is True
    assert capabilities["can_choose_input"] is True
    assert capabilities["can_run_search"] is False
    assert not hasattr(api, "start_build_index")
    assert capabilities["can_export"] is False
    assert api.start_search({"k": 6, "max_mismatches": 2}) == {
        "ok": False,
        "error": "请先生成或加载数据集",
    }
    assert api.start_export_results({"output_directory": str(ROOT)}) == {
        "ok": False,
        "error": "尚未完成检索，无法导出报告",
    }


def test_frontend_ready_probe_records_full_handshake(tmp_path: Path, monkeypatch) -> None:
    probe = tmp_path / "ready.json"
    monkeypatch.setenv("DNA_FRONTEND_READY_FILE", str(probe))
    api = DesktopApi()
    response = api.notify_frontend_ready({"views": 4, "protocol": "http:"})
    assert response == {"ok": True, "ready": True}
    assert '"ready": true' in probe.read_text(encoding="utf-8")


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
    ui_actions = (WEB / "ui-actions.js").read_text(encoding="utf-8")
    router = (WEB / "router.js").read_text(encoding="utf-8")

    assert 'max="3"' in html
    assert 'id="toggle-inspector"' in html and 'id="open-inspector-button"' in html
    assert "setInspectorCollapsed" in app and "inspector-collapsed" in styles
    assert "uiCapabilities" in app and "canConfigure" in app
    assert "nearest_hit" in app and "is-rejected" in app
    assert "错配" in app and "H=" not in app
    assert "distance-reject-label" in html
    assert "repeat(4" in styles and "0 个错配 · 0%" in report
    assert "table-layout: fixed" in (WEB / "pages.css").read_text(encoding="utf-8")
    assert "h4" not in pages.lower()
    assert "taskRunning()" in pages and "lockPageActions" in pages and "disabled" in pages
    assert "openHelp" in ui_actions and "openTrace" in ui_actions
    assert "history.replaceState" in router and "location.replace" not in router
    assert 'id="startup-overlay"' in html and "notify_frontend_ready" in ui_actions

    # Business buttons on secondary pages start disabled before the first
    # state snapshot; top-bar help remains a local, always-available action.
    for page_name in ("index-state.html", "reads.html", "report.html"):
        page_html = (WEB / "pages" / page_name).read_text(encoding="utf-8")
        page_actions = re.search(r'<div class="page-actions">(.*?)</div>', page_html)
        if page_name == "index-state.html":
            assert page_actions is None
            assert "rebuild-index-button" not in page_html
        elif page_name == "reads.html":
            assert page_actions
            assert 'data-local-action="navigate-import"' in page_actions.group(1)
        else:
            assert page_actions
            assert page_actions.group(1).count("disabled") == page_actions.group(1).count("<button")
        assert 'data-ui-action="help"' in page_html
        assert 'disabled data-ui-action="help"' not in page_html
    assert 'class="input-mode-tab is-active"' in html and 'class="stepper-button"' in html
    assert 'class="input-mode-tab is-active" disabled' not in html
