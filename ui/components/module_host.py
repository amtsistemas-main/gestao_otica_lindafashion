"""Hosting module pages inside the main window instead of separate windows."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QDialog, QFrame, QScrollArea, QWidget

from ui.components.enter_guard import without_default_button


class _EscapeBlocker(QObject):
    """An embedded QDialog would hide itself on Esc; inside the main window that is never wanted."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            return True
        return False


_ESCAPE_BLOCKER = _EscapeBlocker()


def embed_dialog(page: QDialog, on_finished: Callable[[], None] | None = None) -> QDialog:
    """Turns a module QDialog into a plain child widget.

    Window-only settings (size, minimum size, Esc to close) are dropped. If the page
    closes itself (accept/reject, e.g. after saving settings) it is shown again for the
    next visit and ``on_finished`` runs, typically returning to the overview.
    """
    page.setWindowFlags(Qt.WindowType.Widget)
    page.setMinimumSize(0, 0)
    page.setSizeGripEnabled(False)
    page.installEventFilter(_ESCAPE_BLOCKER)
    without_default_button(page)

    def finished(_result: int) -> None:
        page.setVisible(True)
        if on_finished is not None:
            on_finished()

    page.finished.connect(finished)
    return page


def hide_title_bar(page: QWidget) -> None:
    """Hides the page's own title bar when a host already shows one."""
    bar = page.findChild(QFrame, "windowTitleBar")
    if bar is not None:
        bar.setVisible(False)


class _FitScrollArea(QScrollArea):
    """Gives the page the whole viewport and scrolls only below the page's real minimum.

    QScrollArea.setWidgetResizable sizes pages with word-wrapped labels by their
    height-for-width (preferred heights), which made pages taller than the screen.
    """

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        page = self.widget()
        if page is None:
            return
        viewport = self.viewport().size()
        minimum = page.minimumSizeHint().expandedTo(page.minimumSize())
        page.resize(max(viewport.width(), minimum.width()), max(viewport.height(), minimum.height()))


def scroll_container(page: QWidget) -> QScrollArea:
    """Workspace container: the page scrolls only when the window is smaller than its content."""
    area = _FitScrollArea()
    area.setObjectName("moduleScroll")
    area.setWidgetResizable(False)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(page)
    return area
