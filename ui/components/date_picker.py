"""Inline date picker: calendar, quick shortcuts and the chosen date written out."""
from __future__ import annotations

from collections import Counter
from datetime import date

import qtawesome as qta
from PySide6.QtCore import QDate, QLocale, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

SHORTCUTS = (("Hoje", 0), ("Amanhã", 1), ("Em 7 dias", 7), ("Em 30 dias", 30))


class DatePickerPanel(QWidget):
    """Calendar always visible; ``busy_dates`` highlights days that already have items."""

    dateChanged = Signal(QDate)

    def __init__(self, initial: QDate | None = None, busy_dates: list[date] | None = None,
                 minimum: QDate | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._locale = QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
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

        self.calendar = QCalendarWidget()
        self.calendar.setObjectName("datePickerCalendar")
        self.calendar.setLocale(self._locale)
        self.calendar.setFirstDayOfWeek(Qt.DayOfWeek.Sunday)
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.calendar.setMinimumSize(QSize(330, 270))
        if minimum is not None:
            self.calendar.setMinimumDate(minimum)
        for name, icon in (("qt_calendar_prevmonth", "fa5s.chevron-left"), ("qt_calendar_nextmonth", "fa5s.chevron-right")):
            arrow = self.calendar.findChild(QToolButton, name)
            if arrow is not None:
                arrow.setIcon(qta.icon(icon, color="#102957"))
                arrow.setIconSize(QSize(13, 13))
        self._style_days(busy_dates or [])
        self.calendar.selectionChanged.connect(self._on_selection)
        layout.addWidget(self.calendar)

        self.summary = QLabel("")
        self.summary.setObjectName("dateSummary")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.set_date(initial or QDate.currentDate())

    def _style_days(self, busy_dates: list[date]) -> None:
        weekend = QTextCharFormat()
        weekend.setForeground(QColor("#B42318"))
        self.calendar.setWeekdayTextFormat(Qt.DayOfWeek.Saturday, weekend)
        self.calendar.setWeekdayTextFormat(Qt.DayOfWeek.Sunday, weekend)
        today = QTextCharFormat()
        today.setFontWeight(QFont.Weight.Bold)
        today.setForeground(QColor("#2165F5"))
        today.setFontUnderline(True)
        self.calendar.setDateTextFormat(QDate.currentDate(), today)
        self._busy = Counter(busy_dates)
        for day, count in self._busy.items():
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.Bold)
            fmt.setBackground(QColor("#EAF0FC"))
            fmt.setForeground(QColor("#102957"))
            fmt.setToolTip(f"{count} tarefa(s) agendada(s)")
            self.calendar.setDateTextFormat(QDate(day.year, day.month, day.day), fmt)

    def set_date(self, value: QDate) -> None:
        self.calendar.setSelectedDate(value)
        self.calendar.setCurrentPage(value.year(), value.month())
        self._on_selection()

    def selected_date(self) -> QDate:
        return self.calendar.selectedDate()

    def _on_selection(self) -> None:
        value = self.calendar.selectedDate()
        text = self._locale.toString(value, "dddd, d 'de' MMMM 'de' yyyy")
        days = QDate.currentDate().daysTo(value)
        relative = {0: "hoje", 1: "amanhã", -1: "ontem"}.get(days)
        if relative is None:
            relative = f"daqui a {days} dias" if days > 0 else f"há {-days} dias"
        busy = self._busy.get(value.toPython(), 0)
        extra = f" • {busy} tarefa(s) já agendada(s) neste dia" if busy else ""
        self.summary.setText(f"<b>{text[:1].upper() + text[1:]}</b> ({relative}){extra}")
        self.dateChanged.emit(value)
