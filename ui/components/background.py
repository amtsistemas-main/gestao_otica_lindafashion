"""Runs blocking network calls off the UI thread (QR Code polling, sending documents)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal


class _Task(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.succeeded.emit(self._fn())
        except Exception as exc:  # reported to the UI as a message
            self.failed.emit(str(exc))


def run_in_background(owner: QObject, fn: Callable[[], object], on_success: Callable[[object], None],
                      on_error: Callable[[str], None] | None = None) -> _Task:
    """Starts ``fn`` in a worker thread; callbacks run back on the UI thread.

    The task is parented to ``owner`` so it is kept alive while running.
    """
    task = _Task(fn, owner)
    task.succeeded.connect(on_success)
    if on_error is not None:
        task.failed.connect(on_error)
    task.finished.connect(task.deleteLater)
    task.start()
    return task
