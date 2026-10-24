"""Premium home dashboard for Ótica Linda Fashion."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.components.module_card import ModuleCard


MODULES = [
    ("Produtos", "Catálogo, preços e códigos de barras", "PR"),
    ("Estoque", "Entradas, saídas e inventário", "ES"),
    ("Fornecedores", "Parceiros e compras", "FO"),
    ("Financeiro", "Receitas, despesas e caixa", "FI"),
    ("Relatórios", "Indicadores e análises", "RE"),
    ("Configurações", "Preferências e integrações", "CO"),
]


class MetricCard(QFrame):
    def __init__(
        self,
        title: str,
        value: str,
        detail: str,
        accent: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(126)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 15)
        layout.setSpacing(7)

        top = QHBoxLayout()
        marker = QLabel("●")
        marker.setStyleSheet(f"color:{accent}; font-size:11pt;")
        label = QLabel(title)
        label.setObjectName("metricLabel")
        top.addWidget(marker)
        top.addWidget(label)
        top.addStretch()
        layout.addLayout(top)

        amount = QLabel(value)
        amount.setObjectName("metricValue")
        layout.addWidget(amount)
        caption = QLabel(detail)
        caption.setObjectName("muted")
        caption.setWordWrap(True)
        layout.addWidget(caption)


class DashboardPage(QWidget):
    module_requested = Signal(str)

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setObjectName("dashboardPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 8)
        root.setSpacing(22)

        page_heading = QVBoxLayout()
        page_heading.setSpacing(5)
        eyebrow = QLabel("PAINEL DE CONTROLE")
        eyebrow.setObjectName("eyebrow")
        heading = QLabel("Visão geral")
        heading.setObjectName("dashboardTitle")
        intro = QLabel("Acompanhe a operação da sua ótica em um só lugar.")
        intro.setObjectName("muted")
        page_heading.addWidget(eyebrow)
        page_heading.addWidget(heading)
        page_heading.addWidget(intro)
        root.addLayout(page_heading)

        hero = QFrame()
        hero.setObjectName("welcomeBanner")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 22, 24, 22)
        hero_layout.setSpacing(20)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(8)
        badge = QLabel("ÓTICA LINDA FASHION  •  GESTÃO INTELIGENTE")
        badge.setObjectName("heroEyebrow")
        hero_title = QLabel("Sua gestão, mais clara.\nSeu negócio, mais forte.")
        hero_title.setObjectName("heroTitle")
        hero_title.setWordWrap(True)
        hero_description = QLabel(
            "Organize produtos, acompanhe o estoque e prepare sua operação "
            "para decisões melhores."
        )
        hero_description.setObjectName("heroDescription")
        hero_description.setWordWrap(True)
        hero_description.setMaximumWidth(560)
        hero_copy.addWidget(badge)
        hero_copy.addWidget(hero_title)
        hero_copy.addWidget(hero_description)
        hero_layout.addLayout(hero_copy, 1)

        hero_action = QVBoxLayout()
        hero_action.addStretch()
        self.primary_action = QPushButton("＋  Cadastrar produto")
        self.primary_action.setObjectName("heroButton")
        self.primary_action.setMinimumHeight(46)
        self.primary_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.primary_action.clicked.connect(lambda: self.module_requested.emit("Produtos"))
        hero_action.addWidget(self.primary_action)
        hero_action.addStretch()
        hero_layout.addLayout(hero_action)
        root.addWidget(hero)

        metrics_heading = QHBoxLayout()
        metrics_title = QLabel("Indicadores do negócio")
        metrics_title.setObjectName("sectionTitle")
        metrics_note = QLabel(
            "Prévia dos indicadores" if preview_mode else "Aguardando conexão dos dados"
        )
        metrics_note.setObjectName("muted")
        metrics_heading.addWidget(metrics_title)
        metrics_heading.addStretch()
        metrics_heading.addWidget(metrics_note)
        root.addLayout(metrics_heading)

        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(14)
        metrics.setVerticalSpacing(14)
        metric_data = [
            ("Produtos cadastrados", "—", "Total de itens no catálogo", "#315FE8"),
            ("Itens em estoque", "—", "Unidades disponíveis", "#0F9F83"),
            ("Contas a receber", "—", "Valores a receber", "#C18A28"),
            ("Contas a pagar", "—", "Compromissos financeiros", "#D45D64"),
        ]
        for index, data in enumerate(metric_data):
            metrics.addWidget(MetricCard(*data), 0, index)
        root.addLayout(metrics)

        section_heading = QHBoxLayout()
        modules_title = QLabel("Acesso rápido")
        modules_title.setObjectName("sectionTitle")
        modules_subtitle = QLabel("Entre diretamente nas áreas do sistema")
        modules_subtitle.setObjectName("muted")
        section_heading.addWidget(modules_title)
        section_heading.addStretch()
        section_heading.addWidget(modules_subtitle)
        root.addLayout(section_heading)

        modules_grid = QGridLayout()
        modules_grid.setContentsMargins(0, 0, 0, 0)
        modules_grid.setHorizontalSpacing(14)
        modules_grid.setVerticalSpacing(14)
        for index, (name, description, abbreviation) in enumerate(MODULES):
            card = ModuleCard(name, description, abbreviation)
            card.clicked.connect(
                lambda checked=False, module=name: self.module_requested.emit(module)
            )
            modules_grid.addWidget(card, index // 3, index % 3)
        root.addLayout(modules_grid)

        footer = QFrame()
        footer.setObjectName("dashboardFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.setSpacing(10)
        status_dot = QLabel("●")
        status_dot.setStyleSheet("color:#0F9F83; font-size:10pt;")
        status_text = QLabel(
            "Modo de visualização ativo — os dados de teste não são persistidos."
            if preview_mode
            else "Painel pronto para receber os dados da sua operação."
        )
        status_text.setObjectName("muted")
        footer_layout.addWidget(status_dot)
        footer_layout.addWidget(status_text)
        footer_layout.addStretch()
        footer_link = QLabel("AMT Sistemas")
        footer_link.setObjectName("footerBrand")
        footer_layout.addWidget(footer_link)
        root.addWidget(footer)
