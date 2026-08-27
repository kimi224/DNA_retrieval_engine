"""Small Windows named-mutex guard for repeated double-click launches."""

import ctypes
import sys
from typing import Any


class SingleInstance:
    def __init__(self, name: str) -> None:
        self._handle: Any = None
        self.already_running = False
        if sys.platform != "win32":
            return
        kernel32 = ctypes.windll.kernel32
        self._handle = kernel32.CreateMutexW(None, False, name)
        self.already_running = kernel32.GetLastError() == 183

    def notify_existing(self) -> None:
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(
                None,
                "DNA Retrieval Engine 已经在运行。",
                "NEXUS DNA Retrieval Engine",
                0x40,
            )

    def close(self) -> None:
        if self._handle is not None and sys.platform == "win32":
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
