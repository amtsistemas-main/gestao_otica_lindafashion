"""Keeps the Enter of barcode readers (and of typing) from pressing dialog buttons.

USB barcode readers type the code and send Enter. In a QDialog an Enter that a field does
not consume presses the default button (save, add, refresh...). Two rules:

- a line edit with its own Enter action (``returnPressed`` connected: POS search, product
  search, barcode field) keeps the Enter to itself;
- module pages and the POS are not forms: an Enter that reaches them presses no button.
"""
from __future__ import annotations

from PySide6.QtCore import SIGNAL, QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit

_ENTER_KEYS = (Qt.Key.Key_Return, Qt.Key.Key_Enter)


def _is_enter(event: QEvent) -> bool:
    return event.type() == QEvent.Type.KeyPress and event.key() in _ENTER_KEYS


class EnterKeyGuard(QObject):
    """Application-wide: Enter in a field with its own Enter action stays in that field."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if (_is_enter(event) and isinstance(watched, QLineEdit) and not isinstance(watched.parent(), QComboBox)
                and isinstance(watched.window(), QDialog)
                and watched.receivers(SIGNAL("returnPressed()")) > 0):
            watched.keyPressEvent(event)  # emits returnPressed / editingFinished as usual
            # QLineEdit ignores Enter on purpose (so dialogs see it); Qt propagates ignored
            # key events to the parents even when a filter consumed them, so accept it here.
            event.accept()
            return True
        return False


class _PageEnterBlocker(QObject):
    """Swallows an Enter that bubbled up to the page, so no default button is pressed."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        return _is_enter(event) and watched is not None and isinstance(watched, QDialog)


_PAGE_ENTER_BLOCKER = _PageEnterBlocker()


def install_enter_guard(app: QApplication) -> None:
    guard = EnterKeyGuard(app)
    app.installEventFilter(guard)
    app.setProperty("_enter_key_guard", guard)


def without_default_button(dialog: QDialog) -> QDialog:
    """For pages that are not forms (module screens, POS): Enter never presses a button.

    A button that has keyboard focus still reacts to Enter/Space itself.
    """
    dialog.installEventFilter(_PAGE_ENTER_BLOCKER)
    return dialog
