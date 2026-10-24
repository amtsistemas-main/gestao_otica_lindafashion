"""Premium home dashboard for Ótica Linda Fashion."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QProgressBar,
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



class SalesTrendChart(QWidget):
    """Native Qt line chart with clearly labeled illustrative preview data."""

    def __init__(self, preview_mode: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(18, 14, -12, -24)
        painter.setPen(QPen(QColor("#E7ECF5"), 1))
        for i in range(4):
            y = area.top() + i * area.height() / 3
            painter.drawLine(int(area.left()), int(y), int(area.right()), int(y))
        if not self._preview_mode:
            painter.setPen(QColor("#718099"))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter,
                             "Gráfico disponível após integrar os dados de vendas.")
            return
        values = [0.28, 0.42, 0.36, 0.58, 0.51, 0.73, 0.86]
        points = [QPointF(area.left() + i * area.width() / 6,
                          area.bottom() - value * area.height())
                  for i, value in enumerate(values)]
        painter.setPen(QPen(QColor("#315FE8"), 3, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPolyline(QPolygonF(points))
        painter.setBrush(QColor("#FFFFFF"))
        for point in points:
            painter.drawEllipse(point, 4, 4)
        painter.setPen(QColor("#315FE8"))
        for point in points:
            painter.drawEllipse(point, 2, 2)
        painter.setPen(QColor("#718099"))
        for i, label in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
            x = int(area.left() + i * area.width() / 6 - 12)
            painter.drawText(x, int(area.bottom()) + 19, 28, 18,
                             Qt.AlignmentFlag.AlignHCenter, label)


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

        analytics_heading = QHBoxLayout()
        analytics_title = QLabel("Visão analítica")
        analytics_title.setObjectName("sectionTitle")
        analytics_caption = QLabel("Exemplo visual" if preview_mode else "Aguardando dados reais")
        analytics_caption.setObjectName("muted")
        analytics_heading.addWidget(analytics_title)
        analytics_heading.addStretch()
        analytics_heading.addWidget(analytics_caption)
        root.addLayout(analytics_heading)

        analytics_grid = QGridLayout()
        analytics_grid.setContentsMargins(0, 0, 0, 0)
        analytics_grid.setHorizontalSpacing(14)
        analytics_grid.setVerticalSpacing(14)

        trend_card = QFrame()
        trend_card.setObjectName("analyticsCard")
        trend_layout = QVBoxLayout(trend_card)
        trend_layout.setContentsMargins(18, 16, 18, 12)
        trend_layout.setSpacing(8)
        trend_title = QLabel("Tendência de vendas")
        trend_title.setObjectName("chartTitle")
        trend_subtitle = QLabel(
            "Dados ilustrativos para demonstração" if preview_mode
            else "Nenhuma série de vendas conectada ainda"
        )
        trend_subtitle.setObjectName("muted")
        trend_layout.addWidget(trend_title)
        trend_layout.addWidget(trend_subtitle)
        trend_layout.addWidget(SalesTrendChart(preview_mode))
        analytics_grid.addWidget(trend_card, 0, 0)

        category_card = QFrame()
        category_card.setObjectName("analyticsCard")
        category_layout = QVBoxLayout(category_card)
        category_layout.setContentsMargins(18, 16, 18, 16)
        category_layout.setSpacing(12)
        category_title = QLabel("Distribuição do catálogo")
        category_title.setObjectName("chartTitle")
        category_subtitle = QLabel(
            "Exemplo ilustrativo de categorias" if preview_mode
            else "A distribuição aparecerá após integrar o catálogo"
        )
        category_subtitle.setObjectName("muted")
        category_layout.addWidget(category_title)
        category_layout.addWidget(category_subtitle)
        for category, amount, color in [
            ("Armações", 78, "#315FE8"),
            ("Lentes", 61, "#0F9F83"),
            ("Óculos de sol", 46, "#C18A28"),
            ("Acessórios", 29, "#8B6CE0"),
        ]:
            labels = QHBoxLayout()
            name_label = QLabel(category)
            name_label.setObjectName("chartCategoryLabel")
            value_label = QLabel(str(amount) if preview_mode else "—")
            value_label.setObjectName("chartValue")
            labels.addWidget(name_label)
            labels.addStretch()
            labels.addWidget(value_label)
            bar = QProgressBar()
            bar.setObjectName("categoryProgress")
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.setValue(amount if preview_mode else 0)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                f"QProgressBar#categoryProgress {{ background:#EAF0F8; border:none; "
                f"border-radius:4px; }} QProgressBar#categoryProgress::chunk "
                f"{{ background:{color}; border-radius:4px; }}"
            )
            category_layout.addLayout(labels)
            category_layout.addWidget(bar)
        if not preview_mode:
            note = QLabel("Os valores reais serão exibidos quando o catálogo for conectado.")
            note.setObjectName("muted")
            note.setWordWrap(True)
            category_layout.addWidget(note)
        analytics_grid.addWidget(category_card, 0, 1)
        analytics_grid.setColumnStretch(0, 3)
        analytics_grid.setColumnStretch(1, 2)
        root.addLayout(analytics_grid)

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
