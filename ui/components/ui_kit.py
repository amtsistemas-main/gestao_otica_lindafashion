"""Small reusable building blocks for the shared design system."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
import qtawesome as qta

PRIMARY = "#2165F5"
NAVY = "#102957"
DANGER = "#D64545"

_TONE_ICON_COLORS = {
    "primary": PRIMARY,
    "success": "#12A16B",
    "danger": DANGER,
    "warning": "#D9930D",
    "navy": NAVY,
}


def set_button_icon(button: QPushButton, icon_name: str, size: int = 15) -> QPushButton:
    """Attach a qtawesome icon whose colour matches the button variant."""
    variant = button.objectName()
    if variant in ("primaryButton", "actionButton"):
        color, active = "#FFFFFF", "#FFFFFF"
    elif variant == "dangerButton":
        color, active = DANGER, "#B42318"
    else:
        color, active = PRIMARY, "#1749C2"
    button.setIcon(qta.icon(icon_name, color=color, color_active=active, color_disabled="#A8B4C6"))
    button.setIconSize(QSize(size, size))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def make_button(text: str, icon_name: str | None = None, variant: str = "", parent: QWidget | None = None) -> QPushButton:
    button = QPushButton(text, parent)
    if variant:
        button.setObjectName(variant)
    if icon_name:
        set_button_icon(button, icon_name)
    else:
        button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class MetricTile(QFrame):
    """KPI card: icon badge, caption and a prominent value."""

    def __init__(self, title: str, value: str = "—", icon_name: str = "fa5s.chart-line",
                 tone: str = "primary", hint: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricTile")
        self.setProperty("tone", tone)
        self.setMinimumHeight(84)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(14)

        badge = QLabel()
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color = _TONE_ICON_COLORS.get(tone, PRIMARY)
        badge.setStyleSheet(f"background:{color}; border-radius:20px;")
        badge.setPixmap(qta.icon(icon_name, color="#FFFFFF").pixmap(18, 18))
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        self._title = QLabel(title)
        self._title.setObjectName("metricTileTitle")
        self._value = QLabel(value)
        self._value.setObjectName("metricTileValue")
        self._value.setProperty("tone", tone)
        texts.addWidget(self._title)
        texts.addWidget(self._value)
        self._hint = QLabel(hint)
        self._hint.setObjectName("metricTileHint")
        self._hint.setVisible(bool(hint))
        texts.addWidget(self._hint)
        row.addLayout(texts, 1)

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_hint(self, hint: str) -> None:
        self._hint.setText(hint)
        self._hint.setVisible(bool(hint))


def notice(text: str, kind: str = "preview") -> QLabel:
    """Inline banner for preview-mode warnings or contextual help."""
    label = QLabel(text)
    label.setObjectName("previewNotice" if kind == "preview" else "infoNotice")
    label.setWordWrap(True)
    return label
