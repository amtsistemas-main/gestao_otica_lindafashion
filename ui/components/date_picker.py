"""Inline date picker: calendar, quick shortcuts and the chosen date written out."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.components.calendar import LOCALE, BrandCalendar

SHORTCUTS = (("Hoje", 0), ("Amanhã", 1), ("Em 7 dias", 7), ("Em 30 dias", 30))


class DatePickerPanel(QWidget):
    """Calendar always visible; ``busy_dates`` marks days that already have items."""

    dateChanged = Signal(QDate)

    def __init__(self, initial: QDate | None = None, busy_dates: list[date] | None = None,
                 minimum: QDate | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(6)
        for caption, days in SHORTCUTS:
            button = QPushButton(caption)
            button.setObjectName("dateShortcut")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, offset=days: self.set_date(QDate.currentDate().addDays(offset)))
            shortcuts.addWidget(button)
        next_month = QPushButton("Próximo mês")
        next_month.setObjectName("dateShortcut")
        next_month.setCursor(Qt.CursorShape.PointingHandCursor)
        next_month.clicked.connect(lambda: self.set_date(QDate.currentDate().addMonths(1)))
        shortcuts.addWidget(next_month)
        shortcuts.addStretch(1)
        layout.addLayout(shortcuts)

        self.calendar = BrandCalendar()
        self.calendar.setMinimumSize(330, 270)
        if minimum is not None:
            self.calendar.setMinimumDate(minimum)
        self.calendar.set_busy_dates(busy_dates or [])
        self.calendar.selectionChanged.connect(self._on_selection)
        layout.addWidget(self.calendar)

        self.summary = QLabel("")
        self.summary.setObjectName("dateSummary")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.set_date(initial or QDate.currentDate())

    def set_date(self, value: QDate) -> None:
        self.calendar.setSelectedDate(value)
        self.calendar.setCurrentPage(value.year(), value.month())
        self._on_selection()

    def selected_date(self) -> QDate:
        return self.calendar.selectedDate()

    def _on_selection(self) -> None:
        value = self.calendar.selectedDate()
        text = LOCALE.toString(value, "dddd, d 'de' MMMM 'de' yyyy")
        days = QDate.currentDate().daysTo(value)
        relative = {0: "hoje", 1: "amanhã", -1: "ontem"}.get(days)
        if relative is None:
            relative = f"daqui a {days} dias" if days > 0 else f"há {-days} dias"
        busy = self.calendar.busy_count(value)
        extra = f" • {busy} tarefa(s) já agendada(s) neste dia" if busy else ""
        self.summary.setText(f"<b>{text[:1].upper() + text[1:]}</b> ({relative}){extra}")
        self.dateChanged.emit(value)
