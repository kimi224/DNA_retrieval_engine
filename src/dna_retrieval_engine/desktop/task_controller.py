"""Single background task controller with thread-safe state and UI push."""

import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from threading import RLock, Thread
from typing import Any
from uuid import uuid4


class TaskCancelledError(Exception):
    pass


@dataclass(slots=True)
class TaskContext:
    controller: "TaskController"
    task_id: str

    def update(self, progress: int, message: str) -> None:
        self.controller.update(self.task_id, progress=progress, message=message)

    def check_cancelled(self) -> None:
        if self.controller.is_cancel_requested(self.task_id):
            raise TaskCancelledError("任务已由用户取消")


class TaskController:
    def __init__(self, push_callback: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._lock = RLock()
        self._push_callback = push_callback
        self._closed = False
        self._state: dict[str, Any] = {
            "task_id": None,
            "type": None,
            "status": "idle",
            "progress": 0,
            "message": "本地服务已就绪",
            "error": None,
            "result": None,
            "cancel_requested": False,
            "started_at": None,
            "finished_at": None,
        }

    def set_push_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._push_callback = callback

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)

    def _emit(self) -> None:
        callback = self._push_callback
        if callback is not None:
            try:
                callback(self.snapshot())
            except Exception:
                # Polling get_state() remains the recovery path when event injection fails.
                pass

    def is_running(self) -> bool:
        with self._lock:
            return self._state["status"] == "running"

    def close(self) -> None:
        """Stop accepting new work after the native window begins closing."""
        with self._lock:
            self._closed = True
            if self._state["status"] == "running":
                self._state["cancel_requested"] = True

    def is_cancel_requested(self, task_id: str) -> bool:
        with self._lock:
            return self._state["task_id"] == task_id and self._state["cancel_requested"]

    def update(self, task_id: str, **changes: Any) -> None:
        with self._lock:
            if self._state["task_id"] != task_id:
                return
            self._state.update(changes)
        self._emit()

    def start(self, task_type: str, worker: Callable[[TaskContext], Any]) -> dict[str, Any]:
        with self._lock:
            if self._closed:
                return {"ok": False, "error": "窗口正在关闭，无法启动新任务"}
            if self._state["status"] == "running":
                return {
                    "ok": False,
                    "error": "已有任务正在运行，请等待完成或先取消",
                    "task_id": self._state["task_id"],
                }
            task_id = uuid4().hex
            self._state = {
                "task_id": task_id,
                "type": task_type,
                "status": "running",
                "progress": 0,
                "message": "正在准备任务",
                "error": None,
                "result": None,
                "cancel_requested": False,
                "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "finished_at": None,
            }
        self._emit()

        def run_worker() -> None:
            context = TaskContext(self, task_id)
            try:
                result = worker(context)
                context.check_cancelled()
                self.update(
                    task_id,
                    status="completed",
                    progress=100,
                    message="任务已完成",
                    result=result,
                    finished_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                )
            except TaskCancelledError as exc:
                self.update(
                    task_id,
                    status="cancelled",
                    message=str(exc),
                    finished_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                )
            except Exception as exc:
                self.update(
                    task_id,
                    status="error",
                    message="任务执行失败",
                    error=str(exc),
                    finished_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                )

        Thread(target=run_worker, daemon=True, name=f"dna-{task_type}-{task_id[:8]}").start()
        return {"ok": True, "task_id": task_id}

    def cancel(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            if self._state["task_id"] != task_id or self._state["status"] != "running":
                return {"ok": False, "error": "该任务不存在或已经结束"}
            self._state["cancel_requested"] = True
            self._state["message"] = "正在安全取消任务"
        self._emit()
        return {"ok": True, "task_id": task_id}


def task_event_script(state: dict[str, Any]) -> str:
    payload = json.dumps(state, ensure_ascii=False).replace("</", "<\\/")
    return f"window.dispatchAppEvent && window.dispatchAppEvent('onTaskProgress', {payload});"
