"""Brand calendar used by every date field popup and by the inline date picker.

Cells are painted by hand: selected day as a solid circle, today as a ring, a soft
hover, muted days from other months, and a dot on days that already have items.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

import qtawesome as qta
from PySide6.QtCore import QDate, QEvent, QLocale, QObject, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPalette, QPen, QTextCharFormat
from PySide6.QtWidgets import (QApplication, QCalendarWidget, QDateEdit, QFrame, QHBoxLayout, QItemDelegate,
                               QLineEdit, QPushButton, QStyle, QTableView, QToolButton, QVBoxLayout, QWidget)

PRIMARY = "#2165F5"
NAVY = "#102957"
INK = "#1E2B42"
SOFT = "#EAF0FC"
WEEKEND = "#C2410C"
OTHER_MONTH = "#B6C0CF"
DISABLED = "#D3DAE5"
LOCALE = QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
EMPTY_DATE_TEXT = "DD/MM/AAAA"


class _PlainCellDelegate(QItemDelegate):
    """Calendar cells without the focus rectangle (QCalendarWidget still calls paintCell)."""

    def __init__(self, view: QTableView) -> None:
        super().__init__(view)
        self._original = view.itemDelegate()

    def paint(self, painter, option, index) -> None:
        option.state &= ~QStyle.StateFlag.State_HasFocus
        self._original.paint(painter, option, index)


class BrandCalendar(QCalendarWidget):
    """``footer`` adds Hoje/Limpar (popups); ``clearable`` treats the minimum date as "no date"."""

    def __init__(self, footer: bool = False, clearable: bool = False, empty_page: QDate | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("brandCalendar")
        self._clearable = clearable
        self._empty_page = empty_page
        self._busy: Counter[date] = Counter()
        self._hover_rect = QRect()
        self.setLocale(LOCALE)
        self.setFirstDayOfWeek(Qt.DayOfWeek.Sunday)
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setMinimumSize(QSize(316, 300 if footer else 270))
        self._style_header()
        for name, icon in (("qt_calendar_prevmonth", "fa5s.chevron-left"), ("qt_calendar_nextmonth", "fa5s.chevron-right")):
            arrow = self.findChild(QToolButton, name)
            if arrow is not None:
                arrow.setIcon(qta.icon(icon, color=NAVY, color_active=PRIMARY))
                arrow.setIconSize(QSize(12, 12))
                arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self._view = self.findChild(QTableView, "qt_calendar_calendarview")
        # Kept as a Python reference: eventFilter must not touch C++ objects during teardown.
        self._viewport = self._view.viewport() if self._view is not None else None
        if self._view is not None:
            # The selection circle replaces Qt's focus/selection frame around the current cell.
            palette = self._view.palette()
            for role in (QPalette.ColorRole.Highlight, QPalette.ColorRole.HighlightedText):
                palette.setColor(role, QColor("#FFFFFF"))
            self._view.setPalette(palette)
            self._view.setItemDelegate(_PlainCellDelegate(self._view))
        if self._viewport is not None:
            self._viewport.setMouseTracking(True)
            self._viewport.installEventFilter(self)
            self._viewport.setCursor(Qt.CursorShape.PointingHandCursor)
        if footer:
            self._add_footer()

    # ------------------------------------------------------------------ setup
    def _style_header(self) -> None:
        header = QTextCharFormat()
        header.setForeground(QColor("#7A889E"))
        header.setBackground(QColor("#FFFFFF"))
        header.setFontWeight(QFont.Weight.Bold)
        header.setFontPointSize(8.5)
        self.setHeaderTextFormat(header)
        weekend = QTextCharFormat()
        weekend.setForeground(QColor(WEEKEND))
        for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
            self.setWeekdayTextFormat(day, weekend)

    def _add_footer(self) -> None:
        footer = QWidget()
        footer.setObjectName("calendarFooter")
        row = QHBoxLayout(footer)
        row.setContentsMargins(10, 4, 10, 8)
        today = QPushButton("Hoje")
        today.setObjectName("calendarFooterButton")
        today.setCursor(Qt.CursorShape.PointingHandCursor)
        today.clicked.connect(lambda: self._choose(QDate.currentDate()))
        row.addWidget(today)
        row.addStretch(1)
        if self._clearable:
            clear = QPushButton("Limpar")
            clear.setObjectName("calendarFooterButton")
            clear.setCursor(Qt.CursorShape.PointingHandCursor)
            clear.clicked.connect(lambda: self._choose(self.minimumDate()))
            row.addWidget(clear)
        self.layout().addWidget(footer)

    def _choose(self, value: QDate) -> None:
        """Selects and confirms, closing the popup of a date field like a click on a day."""
        value = max(self.minimumDate(), min(self.maximumDate(), value))
        self.setSelectedDate(value)
        self.activated.emit(value)

    def set_busy_dates(self, days: list[date]) -> None:
        self._busy = Counter(days)
        self.updateCells()

    def busy_count(self, value: QDate) -> int:
        return self._busy.get(value.toPython(), 0)

    # ------------------------------------------------------------------ behaviour
    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().showEvent(event)
        if self._is_empty() and self._empty_page is not None:
            self.setCurrentPage(self._empty_page.year(), self._empty_page.month())

    def _is_empty(self) -> bool:
        return self._clearable and self.selectedDate() == self.minimumDate()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if self._viewport is not None and watched is self._viewport:
            if event.type() == QEvent.Type.MouseMove:
                index = self._view.indexAt(event.position().toPoint())
                rect = self._view.visualRect(index) if index.isValid() and index.row() > 0 else QRect()
                if rect != self._hover_rect:
                    self._hover_rect = rect
                    self._viewport.update()
            elif event.type() == QEvent.Type.Leave and not self._hover_rect.isNull():
                self._hover_rect = QRect()
                self._viewport.update()
        return super().eventFilter(watched, event)

    def paintCell(self, painter: QPainter, rect: QRect, value: QDate) -> None:  # noqa: N802 - Qt override
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(rect, QColor("#FFFFFF"))
        enabled = self.minimumDate() <= value <= self.maximumDate()
        in_month = value.month() == self.monthShown() and value.year() == self.yearShown()
        selected = value == self.selectedDate() and not self._is_empty()
        today = value == QDate.currentDate()
        size = max(min(rect.width(), rect.height()) - 8, 16)
        circle = QRectF(rect.center().x() - size / 2 + 0.5, rect.center().y() - size / 2 + 0.5, size, size)

        if selected and enabled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(PRIMARY))
            painter.drawEllipse(circle)
        elif enabled and rect == self._hover_rect:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(SOFT))
            painter.drawEllipse(circle)
        if today and not selected:
            painter.setPen(QPen(QColor(PRIMARY), 1.6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle.adjusted(1, 1, -1, -1))

        if selected and enabled:
            color = QColor("#FFFFFF")
        elif not enabled:
            color = QColor(DISABLED)
        elif not in_month:
            color = QColor(OTHER_MONTH)
        elif today:
            color = QColor(PRIMARY)
        elif value.dayOfWeek() in (6, 7):
            color = QColor(WEEKEND)
        else:
            color = QColor(INK)
        font = QFont(painter.font())
        font.setPointSizeF(9.5)
        font.setBold(selected or today)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(value.day()))

        if self.busy_count(value) and enabled:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#FFFFFF") if selected else QColor(PRIMARY))
            painter.drawEllipse(QRectF(circle.center().x() - 2, circle.bottom() - 7, 4, 4))
        painter.restore()


def make_date_edit(value: QDate | date | None = None, *, minimum: QDate | None = None,
                   maximum: QDate | None = None, parent: QWidget | None = None) -> QDateEdit:
    """Required date field (dd/MM/yyyy) with the brand calendar popup; empty means today."""
    field = QDateEdit(parent)
    field.setLocale(LOCALE)
    field.setDisplayFormat("dd/MM/yyyy")
    field.setCalendarPopup(True)
    if minimum is not None:
        field.setMinimumDate(minimum)
    if maximum is not None:
        field.setMaximumDate(maximum)
    field.setCalendarWidget(BrandCalendar(footer=True))
    if isinstance(value, date):
        value = QDate(value.year, value.month, value.day)
    field.setDate(value if value is not None and value.isValid() else QDate.currentDate())
    return field


class MaskedDateEdit(QLineEdit):
    """Optional date typed over the mask DD/MM/AAAA, with a calendar button.

    Each digit replaces the next letter of the mask; Backspace removes the last one.
    ``date()`` returns ``minimumDate()`` while empty (same contract as a clearable QDateEdit).
    """

    POSITIONS = (0, 1, 3, 4, 6, 7, 8, 9)

    def __init__(self, value: date | None = None, minimum: QDate | None = None, maximum: QDate | None = None,
                 empty_page: QDate | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("maskedDateEdit")
        self._minimum = minimum or QDate(1900, 1, 1)
        self._maximum = maximum or QDate(7999, 12, 31)
        self._empty_page = empty_page
        self._digits = ""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setToolTip("Digite somente os números (DD/MM/AAAA) ou escolha no calendário")
        self._calendar_action = self.addAction(qta.icon("fa5s.calendar-alt", color=PRIMARY),
                                               QLineEdit.ActionPosition.TrailingPosition)
        self._calendar_action.setToolTip("Escolher no calendário")
        self._calendar_action.triggered.connect(self._open_calendar)
        self.setDate(QDate(value.year, value.month, value.day) if value else None)

    # ------------------------------------------------------------------ value
    def minimumDate(self) -> QDate:  # noqa: N802 - mirrors QDateEdit
        return self._minimum

    def date(self) -> QDate:
        parsed = self._parsed()
        return parsed if parsed is not None else self._minimum

    def setDate(self, value: QDate | None) -> None:  # noqa: N802 - mirrors QDateEdit
        valid = value is not None and value.isValid() and value > self._minimum
        self._digits = value.toString("ddMMyyyy") if valid else ""
        self._render()

    def is_empty(self) -> bool:
        return not self._digits

    def is_valid(self) -> bool:
        """Empty or a complete real date inside the allowed range."""
        return self.is_empty() or self._parsed() is not None

    def _parsed(self) -> QDate | None:
        if len(self._digits) != 8:
            return None
        value = QDate.fromString(self._digits, "ddMMyyyy")
        return value if value.isValid() and self._minimum < value <= self._maximum else None

    def _render(self) -> None:
        text = list(EMPTY_DATE_TEXT)
        for position, digit in zip(self.POSITIONS, self._digits):
            text[position] = digit
        self.setText("".join(text))
        self.setCursorPosition(self.POSITIONS[len(self._digits)] if len(self._digits) < 8 else len(text))
        self.setProperty("empty", not self._digits)
        self.style().unpolish(self)
        self.style().polish(self)

    # ------------------------------------------------------------------ typing
    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self.isReadOnly():
            super().keyPressEvent(event)
            return
        key, text = event.key(), event.text()
        if len(text) == 1 and text.isdigit():
            if len(self._digits) < 8:
                self._digits += text
                self._render()
        elif key == Qt.Key.Key_Backspace:
            self._digits = self._digits[:-1]
            self._render()
        elif key == Qt.Key.Key_Delete:
            self._digits = ""
            self._render()
        elif event.matches(QKeySequence.StandardKey.Paste):
            pasted = "".join(character for character in QApplication.clipboard().text() if character.isdigit())
            self._digits = (self._digits + pasted)[:8]
            self._render()
        elif key in (Qt.Key.Key_F4, Qt.Key.Key_Space) or (
                key == Qt.Key.Key_Down and event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self._open_calendar()
        elif key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            super().keyPressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().mouseReleaseEvent(event)
        self._render()  # the caret always sits on the next position to type

    # ------------------------------------------------------------------ calendar
    def _open_calendar(self) -> None:
        if not self.isEnabled() or self.isReadOnly():
            return
        popup = QFrame(self, Qt.WindowType.Popup)
        popup.setObjectName("calendarPopup")
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(0, 0, 0, 0)
        calendar = BrandCalendar(footer=True, clearable=True, empty_page=self._empty_page)
        calendar.setMinimumDate(self._minimum)
        calendar.setMaximumDate(self._maximum)
        calendar.setSelectedDate(self.date())
        layout.addWidget(calendar)

        def chosen(value: QDate) -> None:
            self.setDate(None if value == self._minimum else value)
            popup.close()
            self.setFocus()

        calendar.activated.connect(chosen)
        calendar.clicked.connect(chosen)
        popup.adjustSize()
        position = self.mapToGlobal(QPoint(0, self.height() + 4))
        screen = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        position.setX(max(screen.left(), min(position.x(), screen.right() - popup.width())))
        if position.y() + popup.height() > screen.bottom():
            position.setY(self.mapToGlobal(QPoint(0, 0)).y() - popup.height() - 4)
        popup.move(position)
        popup.show()
        calendar.setFocus()
