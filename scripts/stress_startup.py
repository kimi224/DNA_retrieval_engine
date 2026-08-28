"""Repeatedly verify that a packaged build completes its full frontend handshake."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from time import monotonic, sleep

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "dist" / "DNA_Retrieval_Engine_onedir" / "DNA_Retrieval_Engine_onedir.exe"


def stop_process_tree(pid: int) -> None:
    creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        check=False,
        capture_output=True,
        creationflags=creation_flags,
    )


def run_once(executable: Path, timeout: float, run_number: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="dna-startup-probe-") as temporary:
        ready_file = Path(temporary) / "frontend-ready.json"
        environment = os.environ.copy()
        environment["DNA_FRONTEND_READY_FILE"] = str(ready_file)
        environment["DNA_STARTUP_PROBE_HIDDEN"] = "1"
        started = monotonic()
        process = subprocess.Popen([str(executable)], env=environment)
        try:
            deadline = started + timeout
            while monotonic() < deadline:
                if ready_file.is_file():
                    payload = json.loads(ready_file.read_text(encoding="utf-8"))
                    return {
                        "run": run_number,
                        "ok": payload.get("ready") is True,
                        "elapsed_ms": round((monotonic() - started) * 1000, 1),
                        "details": payload.get("details", {}),
                    }
                if process.poll() is not None:
                    return {
                        "run": run_number,
                        "ok": False,
                        "elapsed_ms": round((monotonic() - started) * 1000, 1),
                        "error": f"程序提前退出，exit={process.returncode}",
                    }
                sleep(0.05)
            return {
                "run": run_number,
                "ok": False,
                "elapsed_ms": round((monotonic() - started) * 1000, 1),
                "error": "加载遮罩未在超时前完成前端握手",
            }
        finally:
            stop_process_tree(process.pid)
            sleep(0.25)


def main() -> None:
    parser = argparse.ArgumentParser(description="重复冷启动 EXE 并等待前端加载遮罩完成")
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--runs", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"EXE 不存在：{executable}")
    results = [run_once(executable, args.timeout, index + 1) for index in range(args.runs)]
    success = all(bool(item["ok"]) for item in results)
    print(json.dumps({"ok": success, "runs": results}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
