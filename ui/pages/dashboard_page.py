"""Premium home dashboard for Ótica Linda Fashion."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QLinearGradient
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget, QProgressBar,
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


class WelcomeBanner(QFrame):
    """Brand-led welcome banner with native vector eyeglasses artwork."""
    def __init__(self, preview_mode: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomeBanner")
        self.setMinimumHeight(150)
        self.setMaximumHeight(174)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 18, 22, 18)
        layout.setSpacing(10)

        copy = QVBoxLayout()
        copy.setSpacing(5)
        eyebrow = QLabel("ÓTICA LINDA FASHION")
        eyebrow.setObjectName("bannerEyebrow")
        title = QLabel("Bem-vinda à sua visão geral")
        title.setObjectName("bannerTitle")
        subtitle = QLabel(
            "Ambiente de demonstração: explore os recursos do sistema."
            if preview_mode
            else "Acompanhe a operação da sua ótica em um só lugar."
        )
        subtitle.setObjectName("bannerDescription")
        subtitle.setWordWrap(True)
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(subtitle)
        copy.addStretch()
        layout.addLayout(copy, 3)
        artwork = GlassesArtwork()
        artwork.setMinimumWidth(180)
        layout.addWidget(artwork, 2)


class GlassesArtwork(QWidget):
    """Lightweight vector illustration, so the dashboard does not depend on remote assets."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(105)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Soft decorative circles
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 24))
        painter.drawEllipse(int(w * .58), int(h * .02), int(h * .8), int(h * .8))
        painter.setBrush(QColor(255, 255, 255, 15))
        painter.drawEllipse(int(w * .72), int(h * .24), int(h * .65), int(h * .65))
        # Eyeglasses, drawn in a crisp navy/ice-blue line
        lens_w, lens_h = int(min(w * .25, h * .54)), int(h * .48)
        y = int(h * .27)
        x1 = int(w * .15)
        x2 = int(w * .53)
        pen = QPen(QColor("#E9F1FF"), max(3, int(h * .025)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QColor(206, 226, 255, 24))
        painter.drawRoundedRect(x1, y, lens_w, lens_h, 17, 17)
        painter.drawRoundedRect(x2, y, lens_w, lens_h, 17, 17)
        painter.drawLine(x1 + lens_w, y + int(lens_h * .24),
                         x2, y + int(lens_h * .24))
        painter.drawLine(x1, y + int(lens_h * .2), x1 - int(w * .08), y + int(lens_h * .1))
        painter.drawLine(x2 + lens_w, y + int(lens_h * .2),
                         x2 + lens_w + int(w * .08), y + int(lens_h * .1))


class SalesTrendChart(QWidget):
    """Native Qt trend chart. Preview data is explicitly marked as illustrative."""
    def __init__(self, preview_mode: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setMinimumHeight(166)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(18, 12, -12, -24)
        painter.setPen(QPen(QColor("#E8EDF6"), 1))
        for i in range(4):
            y = area.top() + i * area.height() / 3
            painter.drawLine(int(area.left()), int(y), int(area.right()), int(y))
        if not self._preview_mode:
            painter.setPen(QColor("#7A879C"))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter,
                             "O gráfico será exibido quando as vendas forem integradas.")
            return
        values = [0.28, 0.42, 0.36, 0.58, 0.51, 0.73, 0.86]
        points = [QPointF(area.left() + i * area.width() / 6,
                          area.bottom() - value * area.height())
                  for i, value in enumerate(values)]
        fill = QLinearGradient(0, area.top(), 0, area.bottom())
        fill.setColorAt(0, QColor(49, 95, 232, 65))
        fill.setColorAt(1, QColor(49, 95, 232, 3))
        polygon = QPolygonF(points + [QPointF(area.right(), area.bottom()),
                                      QPointF(area.left(), area.bottom())])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawPolygon(polygon)
        painter.setPen(QPen(QColor("#315FE8"), 2.5, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPolyline(QPolygonF(points))
        painter.setBrush(QColor("#FFFFFF"))
        for point in points:
            painter.drawEllipse(point, 4, 4)
        painter.setBrush(QColor("#315FE8"))
        for point in points:
            painter.drawEllipse(point, 2, 2)
        painter.setPen(QColor("#7A879C"))
        for i, label in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
            x = int(area.left() + i * area.width() / 6 - 12)
            painter.drawText(x, int(area.bottom()) + 19, 28, 18,
                             Qt.AlignmentFlag.AlignHCenter, label)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, detail: str, accent: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        row = QHBoxLayout()
        marker = QLabel("●")
        marker.setStyleSheet(f"color:{accent}; font-size:10pt; background:transparent;")
        name = QLabel(title)
        name.setObjectName("metricLabel")
        row.addWidget(marker)
        row.addWidget(name)
        row.addStretch()
        layout.addLayout(row)
        amount = QLabel(value)
        amount.setObjectName("metricValue")
        layout.addWidget(amount)
        caption = QLabel(detail)
        caption.setObjectName("muted")
        caption.setWordWrap(True)
        layout.addWidget(caption)


def section_card(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("analyticsCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 15, 16, 15)
    layout.setSpacing(9)
    heading = QLabel(title)
    heading.setObjectName("chartTitle")
    layout.addWidget(heading)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return card, layout


class DashboardPage(QWidget):
    module_requested = Signal(str)

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_mode = preview_mode
        self.setObjectName("dashboardPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 8)
        root.setSpacing(16)

        heading = QHBoxLayout()
        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(3)
        eyebrow = QLabel("PAINEL DE CONTROLE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Visão geral")
        title.setObjectName("dashboardTitle")
        heading_copy.addWidget(eyebrow)
        heading_copy.addWidget(title)
        heading.addLayout(heading_copy)
        heading.addStretch()
        root.addLayout(heading)

        root.addWidget(WelcomeBanner(preview_mode))

        actions_card, actions_layout = section_card(
            "Ações rápidas", "Acesse os principais módulos com um clique."
        )
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        for label, module, style in [
            ("＋  Produtos", "Produtos", "primaryQuickAction"),
            ("▤  Estoque", "Estoque", "secondaryQuickAction"),
            ("R$  Financeiro", "Financeiro", "secondaryQuickAction"),
        ]:
            button = QPushButton(label)
            button.setObjectName(style)
            button.setMinimumHeight(42)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, target=module: self.module_requested.emit(target))
            actions_row.addWidget(button, 1)
        actions_layout.addLayout(actions_row)
        root.addWidget(actions_card)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        main_column = QVBoxLayout()
        main_column.setSpacing(14)
        side_column = QVBoxLayout()
        side_column.setSpacing(14)

        metric_heading = QHBoxLayout()
        metric_title = QLabel("Indicadores do negócio")
        metric_title.setObjectName("sectionTitle")
        metric_hint = QLabel("Prévia ilustrativa" if preview_mode else "Aguardando dados reais")
        metric_hint.setObjectName("muted")
        metric_heading.addWidget(metric_title)
        metric_heading.addStretch()
        metric_heading.addWidget(metric_hint)
        main_column.addLayout(metric_heading)

        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(10)
        metrics_grid.setVerticalSpacing(10)
        for index, data in enumerate([
            ("Produtos cadastrados", "—", "Itens no catálogo", "#315FE8"),
            ("Itens em estoque", "—", "Unidades disponíveis", "#0F9F83"),
            ("Contas a receber", "—", "Valores pendentes", "#C18A28"),
            ("Contas a pagar", "—", "Compromissos financeiros", "#D45D64"),
        ]):
            metrics_grid.addWidget(MetricCard(*data), index // 2, index % 2)
        main_column.addLayout(metrics_grid)

        trend, trend_layout = section_card(
            "Vendas dos últimos 7 dias",
            "Exemplo visual, sem representar vendas reais." if preview_mode
            else "Os dados serão exibidos após a integração do módulo de vendas."
        )
        trend_layout.addWidget(SalesTrendChart(preview_mode))
        main_column.addWidget(trend)

        categories, category_layout = section_card(
            "Categorias de produtos",
            "Distribuição ilustrativa." if preview_mode
            else "A distribuição será calculada a partir do catálogo."
        )
        for name, value, color in [
            ("Armações", 78, "#315FE8"), ("Lentes", 61, "#37BFA4"),
            ("Óculos de sol", 46, "#F0B544"), ("Acessórios", 29, "#8B6CE0"),
        ]:
            labels = QHBoxLayout()
            category_label = QLabel(name)
            category_label.setObjectName("chartCategoryLabel")
            number = QLabel(str(value) if preview_mode else "—")
            number.setObjectName("chartValue")
            labels.addWidget(category_label)
            labels.addStretch()
            labels.addWidget(number)
            category_layout.addLayout(labels)
            bar = QProgressBar()
            bar.setObjectName("categoryProgress")
            bar.setTextVisible(False)
            bar.setRange(0, 100)
            bar.setValue(value if preview_mode else 0)
            bar.setFixedHeight(7)
            bar.setStyleSheet(
                f"QProgressBar#categoryProgress {{ background:#EAF0F8; border:none; border-radius:3px; }}"
                f"QProgressBar#categoryProgress::chunk {{ background:{color}; border-radius:3px; }}"
            )
            category_layout.addWidget(bar)
        main_column.addWidget(categories)

        activity, activity_layout = section_card(
            "Atividades recentes",
            "As movimentações aparecerão aqui quando os módulos estiverem conectados."
        )
        activity_empty = QLabel("Ainda não há atividades para exibir.")
        activity_empty.setObjectName("emptyState")
        activity_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        activity_empty.setMinimumHeight(74)
        activity_layout.addWidget(activity_empty)
        side_column.addWidget(activity)

        agenda, agenda_layout = section_card(
            "Próximos compromissos",
            "A agenda ficará disponível nesta área em uma próxima evolução."
        )
        agenda_empty = QLabel("Nenhum compromisso conectado.")
        agenda_empty.setObjectName("emptyState")
        agenda_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        agenda_empty.setMinimumHeight(74)
        agenda_layout.addWidget(agenda_empty)
        side_column.addWidget(agenda)

        stock, stock_layout = section_card("Resumo do estoque")
        for label, detail, color in [
            ("Total de produtos", "Catálogo cadastrado", "#315FE8"),
            ("Disponibilidade", "Unidades em estoque", "#0F9F83"),
            ("Estoque baixo", "Itens que exigem atenção", "#D45D64"),
        ]:
            line = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; background:transparent;")
            text_box = QVBoxLayout()
            text_box.setSpacing(2)
            title_label = QLabel(label)
            title_label.setObjectName("chartCategoryLabel")
            detail_label = QLabel(detail)
            detail_label.setObjectName("muted")
            text_box.addWidget(title_label)
            text_box.addWidget(detail_label)
            value = QLabel("—")
            value.setObjectName("chartValue")
            line.addWidget(dot)
            line.addLayout(text_box, 1)
            line.addWidget(value)
            stock_layout.addLayout(line)
        side_column.addWidget(stock)

        columns.addLayout(main_column, 7)
        columns.addLayout(side_column, 4)
        root.addLayout(columns)

        modules_heading = QHBoxLayout()
        modules_title = QLabel("Todos os módulos")
        modules_title.setObjectName("sectionTitle")
        modules_note = QLabel("Acesso às áreas do sistema")
        modules_note.setObjectName("muted")
        modules_heading.addWidget(modules_title)
        modules_heading.addStretch()
        modules_heading.addWidget(modules_note)
        root.addLayout(modules_heading)

        modules_grid = QGridLayout()
        modules_grid.setHorizontalSpacing(12)
        modules_grid.setVerticalSpacing(12)
        for index, (name, description, abbreviation) in enumerate(MODULES):
            card = ModuleCard(name, description, abbreviation)
            card.clicked.connect(lambda checked=False, module=name: self.module_requested.emit(module))
            modules_grid.addWidget(card, index // 3, index % 3)
        root.addLayout(modules_grid)

        footer = QFrame()
        footer.setObjectName("dashboardFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 10, 14, 10)
        status_dot = QLabel("●")
        status_dot.setStyleSheet("color:#0F9F83; background:transparent;")
        status_text = QLabel(
            "Pré-visualização ativa — dados demonstrativos não são persistidos."
            if preview_mode else "Painel pronto para receber os dados da sua operação."
        )
        status_text.setObjectName("muted")
        footer_layout.addWidget(status_dot)
        footer_layout.addWidget(status_text)
        footer_layout.addStretch()
        brand = QLabel("AMT SISTEMAS")
        brand.setObjectName("footerBrand")
        footer_layout.addWidget(brand)
        root.addWidget(footer)
