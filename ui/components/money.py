"""Money field typed like a card machine: digits enter through the cents (1, 2, 5, 0 -> R$ 12,50).

A value filled by the system (or present when the field gets focus) is selected and replaced by
the first digit typed, so a suggested amount is never prefixed to what the user types.
"""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget


def format_brl(cents: int) -> str:
    value = f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {value}"


class MoneyEdit(QLineEdit):
    """``value()``/``setValue()`` in reais, like QDoubleSpinBox; the caret always stays at the end."""

    valueChanged = Signal(float)

    def __init__(self, value: float = 0.0, maximum: float = 999_999_999.99, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("moneyEdit")
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setToolTip("Digite só os números: os dois últimos são os centavos")
        self._max_cents = int(round(maximum * 100))
        self._cents = 0
        self._replace_next = True
        self.setValue(value)

    def value(self) -> float:
        return self._cents / 100

    def setValue(self, value: float) -> None:  # noqa: N802 - mirrors QDoubleSpinBox
        cents = int((Decimal(str(value or 0)) * 100).quantize(Decimal("1")))
        self._set_cents(cents)
        self._replace_next = True
        if self.hasFocus():
            self.selectAll()

    def _set_cents(self, cents: int) -> None:
        cents = max(0, min(cents, self._max_cents))
        changed = cents != self._cents
        self._cents = cents
        self.setText(format_brl(cents))
        self.setCursorPosition(len(self.text()))
        if changed:
            self.valueChanged.emit(self.value())

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self.isReadOnly():
            super().keyPressEvent(event)
            return
        key, text = event.key(), event.text()
        if len(text) == 1 and text.isdigit():
            base = 0 if self._replace_next else self._cents
            candidate = base * 10 + int(text)
            if candidate <= self._max_cents:
                self._replace_next = False
                self._set_cents(candidate)
        elif key == Qt.Key.Key_Backspace:
            self._replace_next = False
            self._set_cents(self._cents // 10)
        elif key == Qt.Key.Key_Delete:
            self._replace_next = False
            self._set_cents(0)
        elif event.matches(QKeySequence.StandardKey.Paste):
            self._replace_next = False
            self._paste(QApplication.clipboard().text())
        elif key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            super().keyPressEvent(event)

    def _paste(self, text: str) -> None:
        """Accepts "1.234,56", "1234,5", "1234.56" or plain digits (as cents)."""
        cleaned = "".join(ch for ch in text if ch.isdigit() or ch in ",.")
        if not cleaned:
            return
        separator = max(cleaned.rfind(","), cleaned.rfind("."))
        if separator >= 0 and len(cleaned) - separator - 1 in (1, 2):
            whole = "".join(ch for ch in cleaned[:separator] if ch.isdigit()) or "0"
            fraction = cleaned[separator + 1:].ljust(2, "0")
            self._set_cents(int(whole) * 100 + int(fraction))
        else:
            self._set_cents(int("".join(ch for ch in cleaned if ch.isdigit())) * 100)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().mouseReleaseEvent(event)
        if self._replace_next:
            self.selectAll()
        else:
            self.setCursorPosition(len(self.text()))

    def focusInEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().focusInEvent(event)
        self._replace_next = True
        QTimer.singleShot(0, self.selectAll)  # after the click that gave focus
