"""Dashboard inspirado na referência visual da Ótica Linda Fashion."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF, QLinearGradient
import qtawesome as qta
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget, QProgressBar, QComboBox,
)
 

def label(text: str, object_name: str, parent: QWidget | None = None) -> QLabel:
    item = QLabel(text, parent)
    item.setObjectName(object_name)
    return item


def icon_label(icon_name: str, color: str = "#2165F5", size: int = 18, object_name: str = "dashboardIcon") -> QLabel:
    """Renderiza ícones vetoriais consistentes via QtAwesome/Font Awesome."""
    item = QLabel()
    item.setObjectName(object_name)
    item.setAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setFixedSize(size + 12, size + 12)
    item.setPixmap(qta.icon(icon_name, color=color).pixmap(size, size))
    return item


def make_card(title: str, parent: QWidget | None = None) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame(parent)
    card.setObjectName("analyticsCard")
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)
    layout.addWidget(label(title, "cardTitle"))
    return card, layout


class GlassesArtwork(QWidget):
    """Ilustração vetorial de óculos para o banner de boas-vindas."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(220, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(220, 235, 250, 80))
        p.drawEllipse(int(w*.40), int(h*.04), int(h*.88), int(h*.88))
        p.setBrush(QColor(230, 240, 252, 55))
        p.drawEllipse(int(w*.61), int(h*.15), int(h*.75), int(h*.75))
        lw, lh = int(min(w*.28, h*.65)), int(h*.48)
        y, x1, x2 = int(h*.27), int(w*.20), int(w*.53)
        pen = QPen(QColor("#102957"), max(3, int(h*.035)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(QColor(180, 215, 246, 65))
        p.drawRoundedRect(x1, y, lw, lh, 17, 17)
        p.drawRoundedRect(x2, y, lw, lh, 17, 17)
        p.drawLine(x1+lw, y+int(lh*.25), x2, y+int(lh*.25))
        p.drawLine(x1, y+int(lh*.20), x1-int(w*.08), y+int(lh*.08))
        p.drawLine(x2+lw, y+int(lh*.20), x2+lw+int(w*.08), y+int(lh*.08))
        shine = QPen(QColor("#FFFFFF"), max(2, int(h*.018)))
        shine.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(shine)
        p.drawLine(x1+10, y+8, x1+int(lw*.38), y+8)


class TrendChart(QWidget):
    def __init__(self, preview_mode: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview_mode = preview_mode
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(38, 8, -8, -28)
        p.setPen(QPen(QColor("#E8EDF5"), 1))
        for i in range(4):
            y = area.top() + i * area.height()/3
            p.drawLine(area.left(), int(y), area.right(), int(y))
        p.setPen(QColor("#7186A8"))
        for i, value in enumerate(["R$ 6.000", "R$ 4.000", "R$ 2.000", "R$ 0"]):
            y = int(area.top() + i * area.height()/3)
            p.drawText(0, y-7, 34, 16, Qt.AlignmentFlag.AlignRight, value)
        if not self.preview_mode:
            p.drawText(area, Qt.AlignmentFlag.AlignCenter, "As vendas aparecerão após a integração do módulo.")
            return
        values = [.23, .43, .35, .54, .68, .61, .86]
        points = [QPointF(area.left()+i*area.width()/6, area.bottom()-v*area.height()) for i,v in enumerate(values)]
        grad = QLinearGradient(0, area.top(), 0, area.bottom())
        grad.setColorAt(0, QColor(49,95,232,70))
        grad.setColorAt(1, QColor(49,95,232,3))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPolygon(QPolygonF(points+[QPointF(area.right(),area.bottom()), QPointF(area.left(),area.bottom())]))
        p.setPen(QPen(QColor("#1764F5"), 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPolyline(QPolygonF(points))
        for point in points:
            p.setBrush(QColor("#FFFFFF")); p.drawEllipse(point, 4, 4)
            p.setBrush(QColor("#1764F5")); p.drawEllipse(point, 2, 2)
        p.setPen(QColor("#60779D"))
        for i, day in enumerate(["10/04","11/04","12/04","13/04","14/04","15/04","16/04"]):
            x = int(area.left()+i*area.width()/6-18)
            p.drawText(x, int(area.bottom())+19, 38, 16, Qt.AlignmentFlag.AlignHCenter, day)


class DonutChart(QWidget):
    def __init__(self, preview_mode: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview_mode = preview_mode
        self.setMinimumSize(145, 145)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = min(self.width(), self.height()) - 22
        rect_x = (self.width()-size)//2
        rect_y = (self.height()-size)//2
        rect = self.rect().adjusted(rect_x, rect_y, -rect_x, -rect_y)
        colors = ["#2165F5", "#41BFA5", "#F5B844", "#8B4CE3", "#7B91B9"]
        values = [39,24,18,11,8] if self.preview_mode else [1,1,1,1,1]
        start = 90*16
        total = sum(values)
        for val, color in zip(values, colors):
            span = -int(360*16*val/total)
            p.setPen(QPen(QColor(color), max(13, int(size*.16),), Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            p.drawArc(rect, start, span)
            start += span
        p.setPen(QColor("#102957"))
        p.setFont(p.font())
        p.drawText(self.rect().adjusted(0,-6,0,-2), Qt.AlignmentFlag.AlignCenter, "248" if self.preview_mode else "—")
        p.setPen(QColor("#637795"))
        p.drawText(self.rect().adjusted(0,22,0,0), Qt.AlignmentFlag.AlignCenter, "Produtos")


class MetricCard(QFrame):
    def __init__(self, icon: str, title: str, value: str, growth: str, color: str) -> None:
        super().__init__()
        self.setObjectName("metricCard")
        self.setMinimumHeight(142)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 15)
        layout.setSpacing(7)
        row = QHBoxLayout()
        badge = icon_label(icon, color, 16, "metricIcon")
        badge.setStyleSheet(f"background:{color}18; border-radius:20px;")
        row.addWidget(badge)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(label(title, "metricLabel"))
        layout.addWidget(label(value, "metricValue"))
        layout.addWidget(label(growth, "metricGrowth" if growth.startswith("↑") else "muted"))


class WelcomeBanner(QFrame):
    def __init__(self, preview_mode: bool) -> None:
        super().__init__()
        self.setObjectName("welcomeBanner")
        self.setMinimumHeight(150)
        self.setMaximumHeight(164)
        row = QHBoxLayout(self)
        row.setContentsMargins(20, 14, 22, 14)
        row.setSpacing(14)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        copy.addWidget(label("Olá, Ana Silva!" if preview_mode else "Olá!", "bannerGreeting"))
        copy.addWidget(label("Bem-vinda de volta!", "bannerTitle"))
        subtitle = label("Aqui você acompanha o desempenho da sua ótica e tem acesso rápido\nàs principais funcionalidades do sistema.", "bannerDescription")
        subtitle.setWordWrap(True)
        copy.addWidget(subtitle)
        row.addLayout(copy, 5)
        row.addWidget(GlassesArtwork(), 4)
        slogan = QVBoxLayout()
        slogan.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        slogan.addWidget(label("Mais que óculos,\né o seu olhar\npara o mundo.", "bannerSlogan"))
        slogan.addWidget(label("━━━━", "bannerAccent"))
        row.addLayout(slogan, 2)


class DashboardPage(QWidget):
    module_requested = Signal(str)

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview_mode = preview_mode
        self.setObjectName("dashboardPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        root.addWidget(WelcomeBanner(preview_mode))

        actions, action_layout = make_card("Ações rápidas")
        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        action_row.addWidget(label("Acesse os principais módulos com um clique.", "actionHint"), 1)
        for title, desc, icon, module, tint in [
            ("Produtos", "Cadastrar / consultar\nprodutos", "◇", "Produtos", "#3478F6"),
            ("Estoque", "Em evolução", "▤", "Estoque", "#16A889"),
            ("Financeiro", "Em evolução", "R$", "Financeiro", "#8955E8"),
        ]:
            tile = QPushButton()
            tile.setObjectName("quickTile")
            tile.setMinimumHeight(76)
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile_layout = QHBoxLayout(tile)
            tile_layout.setContentsMargins(12, 8, 10, 8)
            badge = icon_label({"Produtos":"fa5s.box-open","Estoque":"fa5s.warehouse","Financeiro":"fa5s.coins"}[title], tint, 19, "quickIcon")
            badge.setStyleSheet(f"background:{tint}18; border-radius:20px;")
            tile_layout.addWidget(badge)
            texts = QVBoxLayout()
            texts.addWidget(label(title, "quickTitle"))
            texts.addWidget(label(desc, "quickDescription"))
            tile_layout.addLayout(texts, 1)
            tile_layout.addWidget(label("→", "quickArrow"))
            tile.clicked.connect(lambda checked=False, target=module: self.module_requested.emit(target))
            action_row.addWidget(tile, 1)
        action_layout.addLayout(action_row)
        root.addWidget(actions)

        columns = QGridLayout()
        columns.setHorizontalSpacing(14)
        columns.setVerticalSpacing(12)
        columns.setColumnStretch(0, 7)
        columns.setColumnStretch(1, 4)
        main = QWidget()
        main.setObjectName("transparentHost")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(10)
        side = QWidget()
        side.setObjectName("transparentHost")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0,0,0,0)
        side_layout.setSpacing(10)

        metric_header = QHBoxLayout()
        metric_header.addWidget(label("Indicadores do negócio", "sectionTitle"))
        metric_header.addStretch()
        metric_header.addWidget(label("Prévia ilustrativa" if preview_mode else "Dados da operação", "muted"))
        main_layout.addLayout(metric_header)
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(10)
        cards = [
            ("fa5s.box","Produtos Cadastrados","248" if preview_mode else "—","↑ +12%   vs. mês anterior" if preview_mode else "Aguardando integração","#2165F5"),
            ("fa5s.shopping-cart","Vendas no Mês","R$ 18.742,90" if preview_mode else "—","↑ +8%   vs. mês anterior" if preview_mode else "Aguardando integração","#F0A52B"),
            ("fa5s.users","Clientes Ativos","132" if preview_mode else "—","↑ +15%   vs. mês anterior" if preview_mode else "Aguardando integração","#17A982"),
        ]
        for i, data in enumerate(cards):
            metrics.addWidget(MetricCard(*data),0,i)
        for i in range(3): metrics.setColumnStretch(i,1)
        main_layout.addLayout(metrics)

        trend, trend_layout = make_card("Vendas dos Últimos 7 Dias")
        period = QComboBox()
        period.addItems(["7 dias", "30 dias", "90 dias"])
        period.setObjectName("periodSelector")
        trend_layout.takeAt(0).widget().deleteLater()
        trend_header = QHBoxLayout()
        trend_header.addWidget(label("Vendas dos Últimos 7 Dias", "cardTitle"))
        trend_header.addStretch()
        trend_header.addWidget(period)
        trend_layout.insertLayout(0, trend_header)
        trend_layout.addWidget(TrendChart(preview_mode))
        category, category_layout = make_card("Categorias de Produtos")
        category_row = QHBoxLayout()
        category_row.addWidget(DonutChart(preview_mode), 1)
        legend = QVBoxLayout()
        for name, value, color in [("Armações","39%","#2165F5"),("Lentes","24%","#41BFA5"),("Óculos de Sol","18%","#F5B844"),("Acessórios","11%","#8B4CE3"),("Outros","8%","#7B91B9")]:
            line = QHBoxLayout()
            dot = label("●", "legendDot")
            dot.setStyleSheet(f"color:{color}; background:transparent;")
            line.addWidget(dot)
            line.addWidget(label(name, "legendLabel"),1)
            line.addWidget(label(value if preview_mode else "—", "legendValue"))
            legend.addLayout(line)
        category_row.addLayout(legend, 1)
        category_layout.addLayout(category_row)
        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)
        charts_row.addWidget(trend, 6)
        charts_row.addWidget(category, 5)
        main_layout.addLayout(charts_row, 1)

        bottom = QGridLayout()
        bottom.setHorizontalSpacing(12)
        products, products_layout = make_card("Produtos Mais Vendidos")
        if preview_mode:
            for name, code, trend_text in [("Armação Ray-Ban","RBS228","↑ 12%"),("Óculos de Sol Oakley","OO9186","↑ 6%"),("Lente Zeiss","ZEISS 1.60","↑ 9%"),("Armação Vogue","VO5338","↑ 5%")]:
                line = QHBoxLayout()
                line.addWidget(icon_label("fa5s.glasses", "#355E9B", 18, "productThumb"))
                item_text = QVBoxLayout()
                item_text.addWidget(label(name, "productName"))
                item_text.addWidget(label(code, "productCode"))
                line.addLayout(item_text,1)
                line.addWidget(label(trend_text, "metricGrowth"))
                products_layout.addLayout(line)
        else:
            products_layout.addWidget(label("Os produtos mais vendidos aparecerão após integração.", "emptyState"))
        bottom.addWidget(products,0,0)
        promo = QFrame()
        promo.setObjectName("promoCard")
        promo_layout = QVBoxLayout(promo)
        promo_layout.addStretch()
        promo_layout.addWidget(label("Qualidade, estilo\ne confiança em cada olhar.", "promoTitle"))
        promo_layout.addWidget(label("Ótica Linda Fashion", "promoCaption"))
        bottom.addWidget(promo,0,1)
        stock, stock_layout = make_card("Resumo do Estoque")
        for title, amount, tint in [("Total de Produtos","248" if preview_mode else "—","#2165F5"),("Em Estoque","224" if preview_mode else "—","#16A889"),("Estoque Baixo","12" if preview_mode else "—","#E64C5A")]:
            line=QHBoxLayout()
            line.addWidget(label("●", "legendDot"))
            line.addWidget(label(title, "stockLabel"),1)
            val=label(amount, "stockValue")
            if title=="Estoque Baixo": val.setStyleSheet("color:#E64C5A; background:transparent;")
            line.addWidget(val)
            stock_layout.addLayout(line)
        bottom.addWidget(stock,0,2)
        for i in range(3): bottom.setColumnStretch(i,1)
        main_layout.addLayout(bottom)

        activity, activity_layout = make_card("Atividades Recentes")
        view_all = QPushButton("Ver todas")
        view_all.setObjectName("textAction")
        activity_layout.takeAt(0).widget().deleteLater()
        header = QHBoxLayout()
        header.addWidget(label("Atividades Recentes","cardTitle"))
        header.addStretch()
        header.addWidget(view_all)
        activity_layout.insertLayout(0,header)
        activities = [
            ("fa5s.box","Novo produto cadastrado","Armação Ray-Ban","Hoje, 10:24","#EAF2FF","#2165F5"),
            ("fa5s.shopping-cart","Venda realizada","R$ 348,90","Hoje, 09:17","#E4F8F2","#14A887"),
            ("fa5s.user-plus","Cliente cadastrado","Mariana Costa","Hoje, 08:42","#FFF0F2","#F05B72"),
            ("fa5s.edit","Produto atualizado","Lente Zeiss","Hoje, 08:15","#EAF2FF","#3478F6"),
            ("fa5s.sign-in-alt","Usuário realizou login","Ana Silva","Hoje, 07:58","#F0ECFF","#7958D7"),
        ]
        if preview_mode:
            for ico, title, detail, time, bg, fg in activities:
                row=QHBoxLayout()
                ico_label=icon_label(ico, fg, 15, "activityIcon")
                ico_label.setStyleSheet(f"background:{bg}; border-radius:20px;")
                row.addWidget(ico_label)
                text_box=QVBoxLayout()
                text_box.addWidget(label(title,"activityTitle"))
                text_box.addWidget(label(detail,"activityDetail"))
                row.addLayout(text_box,1)
                row.addWidget(label(time,"activityTime"))
                activity_layout.addLayout(row)
        else:
            activity_layout.addWidget(label("As movimentações reais aparecerão aqui.", "emptyState"))
        side_layout.addWidget(activity)

        agenda, agenda_layout = make_card("Próximos Compromissos")
        agenda_header=QHBoxLayout()
        agenda_header.addWidget(label("Próximos Compromissos","cardTitle"))
        agenda_header.addStretch()
        agenda_action = QPushButton("Ver agenda")
        agenda_action.setObjectName("textAction")
        agenda_header.addWidget(agenda_action)
        agenda_layout.takeAt(0).widget().deleteLater()
        agenda_layout.insertLayout(0,agenda_header)
        if preview_mode:
            agenda_layout.addWidget(label("Hoje, 16 de Abril", "agendaDate"))
            for time, title, detail in [("09:00","Atendimento - João Santos","Consulta de armações"),("10:30","Consulta - Maria Oliveira","Revisão de grau"),("14:00","Venda - Carlos Lima","Lentes e armação"),("16:00","Atendimento - Ana Costa","Escolha de armação")]:
                row=QHBoxLayout()
                row.addWidget(icon_label("fa5s.calendar-alt", "#60799E", 12, "agendaTime"))
                row.addWidget(label(time,"agendaTime"))
                row.addWidget(icon_label("fa5s.circle", "#1764F5", 7, "agendaDot"))
                text_box=QVBoxLayout()
                text_box.addWidget(label(title,"activityTitle"))
                text_box.addWidget(label(detail,"activityDetail"))
                row.addLayout(text_box,1)
                agenda_layout.addLayout(row)
        else:
            agenda_layout.addWidget(label("Nenhum compromisso conectado.", "emptyState"))
        side_layout.addWidget(agenda)

        columns.addWidget(main,0,0)
        columns.addWidget(side,0,1)
        root.addLayout(columns)

        footer=QHBoxLayout()
        footer.addWidget(label("●", "statusDot"))
        footer.addWidget(label("Pré-visualização ativa — dados demonstrativos não são persistidos." if preview_mode else "Painel pronto para receber os dados da sua operação.", "muted"))
        footer.addStretch()
        footer.addWidget(label("ÓTICA LINDA FASHION", "footerBrand"))
        root.addLayout(footer)
