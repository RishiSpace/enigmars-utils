from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class Work(QThread):
    """Run a callable off the GUI thread and emit the return value or exception."""

    result = Signal(object)

    def __init__(self, fn: Callable[[], Any], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.result.emit(self._fn())
        except Exception as exc:  # noqa: BLE001 — surfaced to the UI slot
            self.result.emit(exc)
