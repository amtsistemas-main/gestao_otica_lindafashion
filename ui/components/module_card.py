"""Reusable module navigation card."""
from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class ModuleCard(QPushButton):
    def __init__(
        self,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("moduleCard")
        self.setCursor(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(7)
        title_label = __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel(title)
        title_label.setStyleSheet("font-size: 13pt; font-weight: 700; color: #172c52;")
        description_label = __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
