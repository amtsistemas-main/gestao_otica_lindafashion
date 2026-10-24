"""Reusable module card with consistent symbolic icons."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
import qtawesome as qta


MODULE_ICONS = {
    "Produtos": ("fa5s.glasses", "#2165F5"),
    "Estoque": ("fa5s.warehouse", "#17A982"),
    "Fornecedores": ("fa5s.truck", "#E7A22B"),
    "Financeiro": ("fa5s.wallet", "#8955E8"),
    "Relatórios": ("fa5s.chart-bar", "#2165F5"),
    "Configurações": ("fa5s.cog", "#60799E"),
}


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
        self.setAccessibleName(f"Abrir módulo {title}")
        self.setToolTip(f"{title}: {description}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(14)

        icon = QLabel()
        icon_name, icon_color = MODULE_ICONS.get(title, ("fa5s.layer-group", "#2165F5"))
        icon.setObjectName("moduleIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(qta.icon(icon_name, color=icon_color).pixmap(21, 21))
        icon.setFixedSize(46, 46)
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        copy = QVBoxLayout()
        copy.setSpacing(6)
        copy.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        title_label = QLabel(title)
        title_label.setObjectName("moduleTitle")
        description_label = QLabel(description)
        description_label.setObjectName("moduleDescription")
        description_label.setWordWrap(True)
        description_label.setMinimumWidth(0)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        description_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        copy.addWidget(title_label)
        copy.addWidget(description_label)

        arrow = QLabel("›")
        arrow.setObjectName("moduleArrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(18)
        arrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(copy, 1)
        layout.addWidget(arrow, 0, Qt.AlignmentFlag.AlignVCenter)
