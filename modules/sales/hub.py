"""Vendas / PDV: sales, quotes, POS and the lab-order pipeline in a single module."""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QLabel, QTabWidget, QVBoxLayout, QWidget

from modules.lab_orders.page import LabOrdersPage
from modules.sales.page import SalesPage
from ui.components.module_host import embed_dialog, hide_title_bar


class SalesHubPage(QWidget):
    TAB_SALES, TAB_ORDERS = 0, 1

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None, tab: int = 0) -> None:
        super().__init__(parent)
        self.setObjectName("salesHub")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)

        bar = QFrame()
        bar.setObjectName("windowTitleBar")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(18, 13, 18, 13)
        bar_layout.setSpacing(4)
        title = QLabel("Vendas / PDV")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Ponto de venda, orçamentos, ordens de serviço em PDF e acompanhamento dos pedidos "
                          "no laboratório até a entrega.")
        subtitle.setObjectName("windowSubtitle")
        subtitle.setWordWrap(True)
        bar_layout.addWidget(title)
        bar_layout.addWidget(subtitle)
        root.addWidget(bar)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("moduleTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setIconSize(QSize(15, 15))
        self.sales = embed_dialog(SalesPage(preview_mode=preview_mode, parent=self.tabs))
        self.orders = embed_dialog(LabOrdersPage(preview_mode=preview_mode, parent=self.tabs))
        for page in (self.sales, self.orders):
            hide_title_bar(page)
            # The hub already provides the outer margins.
            page.layout().setContentsMargins(0, 14, 0, 0)
        self.tabs.addTab(self.sales, qta.icon("fa5s.cash-register", color="#2165F5"), "Vendas e orçamentos")
        self.tabs.addTab(self.orders, qta.icon("fa5s.clipboard-list", color="#2165F5"), "Pedidos e laboratório")
        self.tabs.setCurrentIndex(tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        root.addWidget(self.tabs, 1)

    def show_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)

    def _tab_changed(self, index: int) -> None:
        # Sales finished in the POS may have created lab orders (and vice versa).
        if index == self.TAB_ORDERS:
            self.orders._load()
        else:
            self.sales._load_orders()
