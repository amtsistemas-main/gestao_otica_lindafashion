"""Compact summary cards for the main dashboard."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        cards = [
            ("Produtos cadastrados", "—", "Resumo após configurar o banco"),
            ("Itens em estoque", "—", "Controle de inventário"),
            ("Contas a receber", "—", "Resumo financeiro"),
            ("Contas a pagar", "—", "Compromissos financeiros"),
        ]
        for index, (title, value, caption) in enumerate(cards):
            frame = QFrame()
            frame.setObjectName("panel")
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(18, 16, 18, 16)
            title_label = QLabel(title)
            title_label.setObjectName("muted")
            value_label = QLabel(value)
            value_label.setStyleSheet("font-size:24pt; font-weight:800; color:#172c52;")
            caption_label = QLabel(caption)
            caption_label.setObjectName("muted")
            caption_label.setWordWrap(True)
            layout.addWidget(title_label)
            layout.addWidget(value_label)
            layout.addWidget(caption_label)
            grid.addWidget(frame, 0, index)
