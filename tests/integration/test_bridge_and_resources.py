from pathlib import Path
from time import monotonic, sleep

from dna_retrieval_engine.desktop.api import DesktopApi
from dna_retrieval_engine.paths import resource_path


def wait_for_task(api: DesktopApi, timeout: float = 5.0) -> dict:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        task = api.get_state()["task"]
        if task["status"] != "running":
            return task
        sleep(0.02)
    raise AssertionError("background task did not finish")


def test_bridge_start_methods_return_immediately_and_share_state(tmp_path: Path) -> None:
    api = DesktopApi()
    started_at = monotonic()
    accepted = api.start_generate_dataset(
        {"output_directory": str(tmp_path), "seed": 11, "reference_length": 2000}
    )
    assert accepted["ok"] is True
    assert monotonic() - started_at < 0.2
    assert wait_for_task(api)["status"] == "completed"
    state = api.get_state()
    assert state["dataset"]["read_count"] == 50
    assert state["index"]["integrity_ok"] is True

    assert api.start_search({"k": 6, "max_mismatches": 2, "early_prune": True})["ok"]
    assert wait_for_task(api)["status"] == "completed"
    result = api.get_last_result()
    assert result["ok"]
    assert 0 <= result["result"]["summary"]["matched_read_count"] <= 50
    assert len(result["result"]["summary"]["mismatch_distribution"]) == 4


def test_frontend_resources_are_offline_and_bridge_aware() -> None:
    web = resource_path("resources", "web")
    expected = [
        web / "index.html",
        web / "app.js",
        web / "bridge-client.js",
        web / "state-store.js",
        web / "pages" / "index-state.html",
        web / "pages" / "reads.html",
        web / "pages" / "report.html",
        web / "vendor" / "lucide.min.js",
    ]
    assert all(path.is_file() for path in expected)
    bridge = (web / "bridge-client.js").read_text(encoding="utf-8")
    assert 'addEventListener("pywebviewready"' in bridge
    assert "get_state" in bridge and "setInterval" in bridge
    assert "refreshInFlight" in bridge and "pollState" in bridge
    for path in [web / "index.html", *(web / "pages").glob("*.html")]:
        html = path.read_text(encoding="utf-8")
        assert "https://" not in html
        assert "bridge-client.js" in html


def test_prd_baseline_remains_untouched() -> None:
    root = Path(__file__).resolve().parents[2]
    assert "unpkg.com/lucide@0.468.0" in (root / "prd" / "index.html").read_text(encoding="utf-8")
