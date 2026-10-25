"""Signed-in user chip for the top bar: initials, name and profile, opening an account menu."""
from __future__ import annotations

import re

import qtawesome as qta
from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget


def initials(name: str) -> str:
    parts = [part for part in re.split(r"[\s._-]+", name.strip()) if part]
    if not parts:
        return "?"
    letters = parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")
    return letters.upper()


class ProfileChip(QPushButton):
    """Whole chip is clickable; emits ``settings_requested`` or ``logout_requested`` from its menu."""

    settings_requested = Signal()
    logout_requested = Signal()

    def __init__(self, name: str, role: str, can_open_settings: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._name = name
        self._role = role
        self._can_open_settings = can_open_settings
        self.setObjectName("profileChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Conta: configurações e sair")
        self.setAccessibleName(f"Conta de {name}")
        self.setMinimumHeight(48)

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 10, 4)
        row.setSpacing(10)
        avatar = QLabel(initials(name))
        avatar.setObjectName("accountAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(36, 36)
        row.addWidget(avatar)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        name_label = QLabel(name)
        name_label.setObjectName("profileName")
        role_label = QLabel(role)
        role_label.setObjectName("profileRole")
        texts.addWidget(name_label)
        texts.addWidget(role_label)
        row.addLayout(texts)
        self._chevron = QLabel()
        self._chevron.setPixmap(qta.icon("fa5s.chevron-down", color="#64748B").pixmap(11, 11))
        row.addWidget(self._chevron)
        for child in (avatar, name_label, role_label, self._chevron):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedWidth(max(180, row.sizeHint().width()))
        self.clicked.connect(self._open_menu)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return self.layout().sizeHint()

    def _open_menu(self) -> None:
        menu = QMenu(self)
        menu.setObjectName("profileMenu")
        header = menu.addAction(qta.icon("fa5s.user-circle", color="#102957"), f"{self._name}\n{self._role}")
        header.setEnabled(False)
        menu.addSeparator()
        settings = menu.addAction(qta.icon("fa5s.cog", color="#2165F5"), "Configurações")
        settings.setEnabled(self._can_open_settings)
        settings.triggered.connect(self.settings_requested.emit)
        menu.addSeparator()
        logout = menu.addAction(qta.icon("fa5s.sign-out-alt", color="#C03030"), "Sair")
        logout.triggered.connect(self.logout_requested.emit)
        menu.setMinimumWidth(self.width())
        self._chevron.setPixmap(qta.icon("fa5s.chevron-up", color="#2165F5").pixmap(11, 11))
        position = self.mapToGlobal(QPoint(self.width() - max(menu.sizeHint().width(), self.width()), self.height() + 6))
        menu.exec(position)
        self._chevron.setPixmap(qta.icon("fa5s.chevron-down", color="#64748B").pixmap(11, 11))
