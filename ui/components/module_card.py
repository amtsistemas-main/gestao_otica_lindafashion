"""Reusable premium module navigation card."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class ModuleCard(QPushButton):
    def __init__(
        self,
        title: str,
        description: str,
        abbreviation: str = "AP",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("moduleCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(112)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        icon = QLabel(abbreviation)
        icon.setObjectName("moduleIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(42, 42)

        copy = QVBoxLayout()
        copy.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("moduleTitle")
        description_label = QLabel(description)
        description_label.setObjectName("moduleDescription")
        description_label.setWordWrap(True)
        description_label.setMinimumWidth(0)
        copy.addWidget(title_label)
        copy.addWidget(description_label)
        copy.addStretch()

        arrow = QLabel("›")
        arrow.setObjectName("moduleDescription")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(12)

        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(copy, 1)
        layout.addWidget(arrow, 0, Qt.AlignmentFlag.AlignCenter)
