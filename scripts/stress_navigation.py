"""Manual WebView2 navigation/memory stress test without browser automation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from time import sleep

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from dna_retrieval_engine.config import APP_NAME  # noqa: E402
from dna_retrieval_engine.desktop.api import DesktopApi  # noqa: E402
from dna_retrieval_engine.paths import resource_path  # noqa: E402


def process_tree_memory_mb(root_pid: int) -> float:
    script = rf"""
$all = Get-CimInstance Win32_Process
$ids = @({root_pid})
for ($round = 0; $round -lt 6; $round++) {{
  $children = @($all | Where-Object {{ $ids -contains $_.ParentProcessId }} |
    Select-Object -ExpandProperty ProcessId)
  $ids += @($children | Where-Object {{ $ids -notcontains $_ }})
}}
$bytes = 0
foreach ($processId in ($ids | Sort-Object -Unique)) {{
  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
  if ($process) {{ $bytes += $process.WorkingSet64 }}
}}
[math]::Round($bytes / 1MB, 1)
"""
    creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
        capture_output=True,
        text=True,
        creationflags=creation_flags,
    )
    return float(completed.stdout.strip())


def cycle_pages(window, rounds: int) -> None:
    # The product has four real views.  Use an eight-step non-linear route so
    # each stress cycle also covers repeated back-and-forth transitions.
    targets = ("workspace", "index", "reads", "report", "reads", "index", "workspace", "report")
    samples: list[dict[str, float | int]] = []
    try:
        if not window.events._pywebviewready.wait(15):
            raise RuntimeError("初始 pywebview Bridge 未在 15 秒内就绪")
        for _ in range(100):
            if window.evaluate_js("Boolean(window.DnaRouter && window.DnaRouter.isReady())"):
                break
            sleep(0.05)
        else:
            raise RuntimeError("单页视图路由未在 5 秒内就绪")
        sleep(1)
        samples.append({"navigation": 0, "working_set_mb": process_tree_memory_mb(os.getpid())})
        for index in range(rounds):
            target = targets[index % len(targets)]
            if not window.evaluate_js(f"window.DnaRouter.navigate({json.dumps(target)})"):
                raise RuntimeError(f"视图切换失败：{target}")
            sleep(0.04)
            if (index + 1) % 20 == 0:
                samples.append(
                    {
                        "navigation": index + 1,
                        "working_set_mb": process_tree_memory_mb(os.getpid()),
                    }
                )
        sleep(3)
        samples.append(
            {"navigation": rounds, "working_set_mb": process_tree_memory_mb(os.getpid())}
        )
        warm_samples = samples[1:] if len(samples) > 1 else samples
        growth = round(warm_samples[-1]["working_set_mb"] - warm_samples[0]["working_set_mb"], 1)
        stable = growth <= 100
        print(
            json.dumps(
                {"ok": stable, "growth_after_warmup_mb": growth, "samples": samples},
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "samples": samples}, ensure_ascii=False))
    finally:
        window.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="连续切换四个页面并采样 WebView2 进程树内存")
    parser.add_argument("--rounds", type=int, default=160)
    args = parser.parse_args()
    import webview

    api = DesktopApi()
    html_path = resource_path("resources", "web", "index.html").resolve()
    window = webview.create_window(
        f"{APP_NAME} - navigation stress",
        url=str(html_path),
        js_api=api,
        width=1280,
        height=780,
        min_size=(1120, 720),
    )
    api._bind_window(window)
    window.events.closing += api._close
    webview.start(cycle_pages, args=(window, args.rounds), gui="edgechromium", http_server=True)


if __name__ == "__main__":
    main()
