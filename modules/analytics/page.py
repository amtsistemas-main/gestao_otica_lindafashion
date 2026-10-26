"""Commercial intelligence dashboard: revenue vs effective profit, margins, sellers and stock."""
from __future__ import annotations

import random
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QToolTip, QVBoxLayout, QWidget,
)

from core.organization import OrganizationContext, current_organization
from modules.analytics.metrics import CommercialReport, MonthRow, build_report
from modules.products.models import PRODUCT_TYPES
from ui.components.ui_kit import MetricTile, make_button, notice

REVENUE_COLOR = "#2165F5"
PROFIT_COLOR = "#0F9F8F"
INK_MUTED = "#64748B"
GRID = "#E8EDF4"


def brl(value: float, compact: bool = False) -> str:
    if compact and abs(value) >= 1000:
        return f"R$ {value / 1000:,.1f} mil".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def percent(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


class RevenueProfitChart(QWidget):
    """Grouped bars per month on one shared R$ axis; profit may go below the zero baseline."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._months: list[MonthRow] = []
        self._hit_boxes: list[tuple[QRectF, str]] = []
        self.setMinimumHeight(280)
        self.setMouseTracking(True)

    def set_data(self, months: list[MonthRow]) -> None:
        self._months = months
        self.update()

    @staticmethod
    def _nice_step(span: float) -> float:
        raw = span / 4 if span > 0 else 1
        magnitude = 10 ** len(str(int(raw))) / 10
        for factor in (1, 2, 2.5, 5, 10):
            if raw <= factor * magnitude:
                return factor * magnitude
        return raw

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._hit_boxes = []
        area = QRectF(self.rect()).adjusted(78, 16, -16, -34)
        if not self._months:
            painter.setPen(QColor(INK_MUTED))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "Sem dados no período.")
            return
        high = max([0.0] + [max(m.revenue, m.profit) for m in self._months])
        low = min([0.0] + [m.profit for m in self._months])
        step = self._nice_step(high - low)
        top = step * (int(high / step) + (1 if high % step else 0)) if high > 0 else step
        bottom = -step * (int(-low / step) + (1 if -low % step else 0)) if low < 0 else 0.0

        def y_of(value: float) -> float:
            return area.bottom() - (value - bottom) / (top - bottom) * area.height()

        small = QFont(self.font())
        small.setPointSizeF(8.5)
        painter.setFont(small)
        value = bottom
        while value <= top + 1e-6:
            y = y_of(value)
            painter.setPen(QPen(QColor("#B8C3D3" if abs(value) < 1e-6 else GRID), 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QColor(INK_MUTED))
            painter.drawText(QRectF(0, y - 9, area.left() - 8, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, brl(value, compact=True))
            value += step

        group = area.width() / len(self._months)
        bar = min(26.0, group * 0.28)
        gap = 2.0
        zero = y_of(0)
        for index, month in enumerate(self._months):
            center = area.left() + group * index + group / 2
            for offset, amount, color, caption in (
                (-bar - gap / 2, month.revenue, REVENUE_COLOR, "Faturamento"),
                (gap / 2, month.profit, PROFIT_COLOR, "Lucro efetivo"),
            ):
                y = y_of(amount)
                rect = QRectF(center + offset, min(y, zero), bar, max(abs(zero - y), 0.0))
                if rect.height() >= 1:
                    path = QPainterPath()
                    radius = min(4.0, rect.height(), bar / 2)
                    if amount >= 0:
                        path.moveTo(rect.left(), rect.bottom())
                        path.lineTo(rect.left(), rect.top() + radius)
                        path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
                        path.lineTo(rect.right() - radius, rect.top())
                        path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
                        path.lineTo(rect.right(), rect.bottom())
                    else:
                        path.moveTo(rect.left(), rect.top())
                        path.lineTo(rect.left(), rect.bottom() - radius)
                        path.quadTo(rect.left(), rect.bottom(), rect.left() + radius, rect.bottom())
                        path.lineTo(rect.right() - radius, rect.bottom())
                        path.quadTo(rect.right(), rect.bottom(), rect.right(), rect.bottom() - radius)
                        path.lineTo(rect.right(), rect.top())
                    path.closeSubpath()
                    painter.fillPath(path, QColor(color))
                hit = QRectF(center + offset - 4, area.top(), bar + 8, area.height())
                self._hit_boxes.append((hit, f"{month.label} — {caption}: {brl(amount)}"))
            painter.setPen(QColor(INK_MUTED))
            painter.drawText(QRectF(center - group / 2, area.bottom() + 8, group, 18), Qt.AlignmentFlag.AlignCenter, month.label)

        # Selective direct labels: only the latest month carries values.
        last = self._months[-1]
        center = area.left() + group * (len(self._months) - 1) + group / 2
        painter.setPen(QColor("#1E2F4D"))
        # Revenue label grows leftwards from its bar, profit label rightwards, so neither covers a bar.
        revenue_y = y_of(last.revenue)
        painter.drawText(QRectF(center - gap / 2 - 120, revenue_y - 18 if last.revenue >= 0 else revenue_y + 2, 120, 16),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, brl(last.revenue, compact=True))
        profit_y = y_of(last.profit)
        painter.drawText(QRectF(center + gap / 2, profit_y - 18 if last.profit >= 0 else profit_y + 2, 120, 16),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, brl(last.profit, compact=True))

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        position = event.position()
        for box, text in self._hit_boxes:
            if box.contains(position):
                QToolTip.showText(event.globalPosition().toPoint(), text, self)
                return
        QToolTip.hideText()


def _legend() -> QWidget:
    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(16)
    for color, caption in ((REVENUE_COLOR, "Faturamento"), (PROFIT_COLOR, "Lucro efetivo")):
        swatch = QLabel()
        swatch.setFixedSize(12, 12)
        swatch.setStyleSheet(f"background:{color}; border-radius:3px;")
        text = QLabel(caption)
        text.setObjectName("muted")
        row.addWidget(swatch)
        row.addWidget(text)
    row.addStretch(1)
    return host


def _table(headers: list[str], stretch: int = 0) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    header = table.horizontalHeader()
    for column in range(len(headers)):
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    return table


def _fill(table: QTableWidget, rows: list[list[str]], numeric_from: int = 1, colors: dict[tuple[int, int], str] | None = None) -> None:
    table.setRowCount(len(rows))
    for r, values in enumerate(rows):
        for c, value in enumerate(values):
            cell = QTableWidgetItem(value)
            if c >= numeric_from:
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if colors and (r, c) in colors:
                cell.setForeground(QColor(colors[(r, c)]))
            table.setItem(r, c, cell)


def _preview_dataset(today: date) -> dict:
    rng = random.Random(42)
    products = [
        {"id": "p1", "name": "Armação Ray-Ban RB2140", "product_type": "armacao", "cost_price": 220, "sale": 549.9, "stock_quantity": 6},
        {"id": "p2", "name": "Lente multifocal 1.67 AR (par)", "product_type": "lente_oftalmica", "cost_price": 480, "sale": 1290, "stock_quantity": 10},
        {"id": "p3", "name": "Lente monofocal 1.56 filtro azul", "product_type": "lente_oftalmica", "cost_price": 120, "sale": 390, "stock_quantity": 14},
        {"id": "p4", "name": "Óculos solar Oakley Holbrook", "product_type": "oculos_sol", "cost_price": 380, "sale": 799, "stock_quantity": 4},
        {"id": "p5", "name": "Armação Vogue VO5338 (coleção 2024)", "product_type": "armacao", "cost_price": 260, "sale": 590, "stock_quantity": 9},
        {"id": "p6", "name": "Estojo rígido premium", "product_type": "acessorio", "cost_price": 12, "sale": 49.9, "stock_quantity": 40},
    ]
    members = [{"user_id": "u1", "display_name": "Ana Silva"}, {"user_id": "u2", "display_name": "Carlos Lima"}]
    orders, items, labs, entries = [], [], [], []
    for day in range(180):
        when = today - timedelta(days=day)
        for _ in range(rng.choice([0, 1, 1, 2])):
            oid = f"o{len(orders)}"
            chosen = rng.sample(products[:4] + products[5:], k=rng.choice([1, 2]))
            total = 0.0
            for product in chosen:
                items.append({"sales_order_id": oid, "product_id": product["id"], "product_name": product["name"], "product_type": product["product_type"],
                              "quantity": 1, "unit_cost": product["cost_price"], "line_total": product["sale"], "created_at": when.isoformat()})
                total += product["sale"]
            status = "completed" if rng.random() > 0.05 else "cancelled"
            quoted = when.isoformat() if rng.random() < 0.35 else None
            orders.append({"id": oid, "status": status, "total": total, "discount": round(total * rng.choice([0, 0, 0.05]), 2),
                           "created_at": when.isoformat(), "seller_id": rng.choice(["u1", "u2"]), "quoted_at": quoted})
            if any(p["product_type"] == "lente_oftalmica" for p in chosen):
                labs.append({"sales_order_id": oid, "lab_cost": 90, "status": "entregue"})
        if day % 9 == 0:
            orders.append({"id": f"q{day}", "status": "draft", "total": 900, "created_at": when.isoformat(), "quoted_at": when.isoformat()})
        if when.day == 5:
            for category, amount in (("Aluguel", 3500), ("Salários", 6200), ("Energia", 480), ("Fornecedor", 5200)):
                entries.append({"direction": "saida", "category": category, "status": "pago", "amount": amount, "paid_at": when.isoformat(), "due_date": when.isoformat()})
    for offset in (-40, -12, -3, 6, 18, 45):
        entries.append({"direction": "entrada", "category": "Vendas", "status": "pendente", "amount": 350 + abs(offset) * 7, "due_date": (today + timedelta(days=offset)).isoformat()})
    for product in products:
        product["tracks_stock"] = True
        product["active"] = True
    return {"orders": orders, "items": [i for i in items if not i["product_id"] == "p5"], "lab_orders": labs,
            "entries": entries, "products": products, "members": members}


class AnalyticsPage(QDialog):
    """Faturamento × lucro efetivo, margens, conversão, vendedores, produtos, estoque parado e recebíveis."""

    PERIODS = ["Este mês", "Mês anterior", "Últimos 30 dias", "Últimos 90 dias", "Este ano"]

    def __init__(self, preview_mode: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx: OrganizationContext | None = None if preview_mode else current_organization("Os indicadores")
        self._data: dict = {}
        self.setWindowTitle("Indicadores — Ótica Linda Fashion")
        self.resize(1320, 860)
        self.setMinimumSize(1080, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(14)
        bar = QFrame()
        bar.setObjectName("windowTitleBar")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(18, 13, 18, 13)
        title = QLabel("Indicadores e rentabilidade")
        title.setObjectName("windowTitle")
        subtitle = QLabel("Faturamento separado do lucro efetivo: margem, ticket, conversão, vendedores, produtos, estoque parado e recebíveis.")
        subtitle.setObjectName("windowSubtitle")
        bar_layout.addWidget(title)
        bar_layout.addWidget(subtitle)
        root.addWidget(bar)
        if preview_mode:
            root.addWidget(notice("PRÉ-VISUALIZAÇÃO • dados demonstrativos gerados para ilustrar os indicadores."))

        toolbar = QHBoxLayout()
        label = QLabel("Período")
        label.setObjectName("filterLabel")
        self.period = QComboBox()
        self.period.addItems(self.PERIODS)
        self.period.setMinimumWidth(190)
        self.period.currentIndexChanged.connect(self._render)
        self.range_label = QLabel("")
        self.range_label.setObjectName("muted")
        refresh = make_button("Atualizar", "fa5s.sync-alt", "secondaryButton")
        refresh.clicked.connect(self._load)
        toolbar.addWidget(label)
        toolbar.addWidget(self.period)
        toolbar.addWidget(self.range_label)
        toolbar.addStretch(1)
        toolbar.addWidget(refresh)
        root.addLayout(toolbar)

        tiles = QGridLayout()
        tiles.setHorizontalSpacing(12)
        tiles.setVerticalSpacing(12)
        self.revenue_tile = MetricTile("Faturamento líquido", "—", "fa5s.coins", "primary")
        self.profit_tile = MetricTile("Lucro efetivo", "—", "fa5s.piggy-bank", "success")
        self.margin_tile = MetricTile("Margem de contribuição", "—", "fa5s.percentage", "navy")
        self.ticket_tile = MetricTile("Ticket médio", "—", "fa5s.receipt", "primary")
        self.sales_tile = MetricTile("Vendas concluídas", "—", "fa5s.shopping-bag", "navy")
        self.conversion_tile = MetricTile("Conversão de orçamentos", "—", "fa5s.exchange-alt", "primary")
        self.receivable_tile = MetricTile("Contas a receber", "—", "fa5s.hand-holding-usd", "warning")
        self.stagnant_tile = MetricTile("Estoque parado (+90 dias)", "—", "fa5s.box", "danger")
        for index, tile in enumerate((self.revenue_tile, self.profit_tile, self.margin_tile, self.ticket_tile,
                                      self.sales_tile, self.conversion_tile, self.receivable_tile, self.stagnant_tile)):
            tiles.addWidget(tile, index // 4, index % 4)
        root.addLayout(tiles)

        self.tabs = QTabWidget()
        evolution = QWidget()
        evolution_layout = QHBoxLayout(evolution)
        evolution_layout.setContentsMargins(0, 4, 0, 0)
        evolution_layout.setSpacing(14)
        chart_card = QFrame()
        chart_card.setObjectName("surfaceCard")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(16, 12, 16, 12)
        chart_title = QLabel("Faturamento × lucro efetivo — últimos 6 meses")
        chart_title.setObjectName("cardHeading")
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(_legend())
        self.chart = RevenueProfitChart()
        chart_layout.addWidget(self.chart, 1)
        evolution_layout.addWidget(chart_card, 3)
        self.dre = _table(["Demonstrativo do período", "Valor", "% do faturamento"])
        evolution_layout.addWidget(self.dre, 2)
        self.tabs.addTab(evolution, "Faturamento × lucro")
        self.sellers = _table(["Vendedor", "Vendas", "Faturamento", "Ticket médio", "Margem bruta"])
        self.tabs.addTab(self.sellers, "Vendedores")
        self.products = _table(["Produto", "Tipo", "Qtd.", "Faturamento", "Custo", "Contribuição", "Margem"])
        self.tabs.addTab(self.products, "Produtos mais rentáveis")
        self.stagnant = _table(["Produto", "Tipo", "Estoque", "Capital parado", "Última venda"])
        self.tabs.addTab(self.stagnant, "Estoque parado")
        self.receivables = _table(["Situação", "Valor"])
        self.tabs.addTab(self.receivables, "Contas a receber")
        root.addWidget(self.tabs, 1)

        explanation = QLabel(
            "Lucro efetivo = faturamento − custo das mercadorias vendidas (custo registrado na venda) − custos de laboratório "
            "− despesas pagas. Compras de mercadoria não entram como despesa, pois já estão no custo da venda."
        )
        explanation.setObjectName("muted")
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        self._load()

    # Data -----------------------------------------------------------------
    def _period_bounds(self) -> tuple[date, date]:
        today = date.today()
        choice = self.period.currentText()
        if choice == "Mês anterior":
            end = today.replace(day=1) - timedelta(days=1)
            return end.replace(day=1), end
        if choice == "Últimos 30 dias":
            return today - timedelta(days=29), today
        if choice == "Últimos 90 dias":
            return today - timedelta(days=89), today
        if choice == "Este ano":
            return today.replace(month=1, day=1), today
        return today.replace(day=1), today

    def _load(self) -> None:
        today = date.today()
        if self._ctx is None:
            self._data = _preview_dataset(today)
            self._render()
            return
        since = (today.replace(day=1) - timedelta(days=200)).replace(day=1)
        client, org = self._ctx.client, self._ctx.organization_id
        try:
            orders = client.table("sales_orders").select(
                "id,status,total,discount,created_at,seller_id,created_by,quoted_at"
            ).eq("organization_id", org).gte("created_at", since.isoformat()).limit(20000).execute().data or []
            items = client.table("sales_order_items").select(
                "sales_order_id,product_id,product_name,product_type,quantity,unit_cost,line_total,created_at"
            ).eq("organization_id", org).gte("created_at", since.isoformat()).limit(50000).execute().data or []
            lab_orders = client.table("customer_orders").select("sales_order_id,lab_cost,status").eq(
                "organization_id", org).gte("created_at", since.isoformat()).limit(20000).execute().data or []
            entries = client.table("financial_entries").select(
                "direction,category,status,amount,due_date,paid_at"
            ).eq("organization_id", org).limit(50000).execute().data or []
            products = client.table("products").select(
                "id,name,product_type,stock_quantity,cost_price,tracks_stock,active"
            ).eq("organization_id", org).execute().data or []
            try:
                members = client.table("organization_members").select("user_id,display_name").eq("organization_id", org).execute().data or []
            except Exception:
                members = []
        except Exception as exc:
            QMessageBox.critical(self, "Indicadores indisponíveis",
                                 f"{exc}\n\nConfirme se as migrations 202610250004 e 202610250005 foram aplicadas.")
            return
        self._data = {"orders": orders, "items": items, "lab_orders": lab_orders, "entries": entries, "products": products, "members": members}
        self._render()

    def _render(self, *_args: object) -> None:
        if not self._data:
            return
        start, end = self._period_bounds()
        self.range_label.setText(f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}")
        report: CommercialReport = build_report(start=start, end=end, **self._data)

        self.revenue_tile.set_value(brl(report.revenue))
        self.revenue_tile.set_hint(f"Descontos concedidos: {brl(report.discounts)}")
        self.profit_tile.set_value(brl(report.net_profit))
        self.profit_tile.set_hint(f"{percent(report.net_percent)} do faturamento")
        self.margin_tile.set_value(percent(report.contribution_percent))
        self.margin_tile.set_hint(brl(report.contribution_margin))
        self.ticket_tile.set_value(brl(report.avg_ticket))
        self.sales_tile.set_value(str(report.sales_count))
        self.conversion_tile.set_value(percent(report.conversion_percent) if report.quotes_created else "—")
        self.conversion_tile.set_hint(f"{report.quotes_converted} de {report.quotes_created} orçamentos" if report.quotes_created else "Nenhum orçamento no período")
        self.receivable_tile.set_value(brl(report.receivables.total))
        self.receivable_tile.set_hint(f"{brl(report.receivables.overdue)} vencidos ({report.receivables.overdue_count})")
        self.stagnant_tile.set_value(brl(report.stagnant_value))
        self.stagnant_tile.set_hint(f"{len(report.stagnant)} produto(s) sem venda há +90 dias")

        self.chart.set_data(report.monthly)
        gross = report.revenue + report.discounts
        dre_rows = [
            ("Faturamento bruto", gross), ("(−) Descontos", -report.discounts), ("= Faturamento líquido", report.revenue),
            ("(−) Custo das mercadorias vendidas", -report.cogs), ("(−) Custos de laboratório", -report.lab_costs),
            ("= Margem de contribuição", report.contribution_margin), ("(−) Despesas operacionais pagas", -report.operating_expenses),
            ("= Lucro efetivo", report.net_profit),
        ]
        colors = {}
        rows = []
        for index, (caption, value) in enumerate(dre_rows):
            rows.append([caption, brl(value), percent(value / report.revenue * 100) if report.revenue else "—"])
            if caption.startswith("= Lucro"):
                colors[(index, 1)] = "#0E8A5B" if value >= 0 else "#C03030"
        _fill(self.dre, rows, colors=colors)

        _fill(self.sellers, [[row.name, str(row.sales), brl(row.revenue), brl(row.ticket), percent(row.margin_percent)] for row in report.sellers])
        _fill(self.products, [
            [row.name, PRODUCT_TYPES.get(row.product_type, "—"), f"{row.quantity:g}", brl(row.revenue), brl(row.cost),
             brl(row.contribution), percent(row.margin_percent)] for row in report.products[:30]
        ], numeric_from=2)
        _fill(self.stagnant, [
            [row.name, PRODUCT_TYPES.get(row.product_type, "—"), str(row.stock), brl(row.stock_value),
             row.last_sale.strftime("%d/%m/%Y") if row.last_sale else "Nunca vendido"] for row in report.stagnant
        ], numeric_from=2)
        receivable_rows = [["A vencer em até 30 dias", brl(report.receivables.next_30_days)],
                           ["A vencer após 30 dias", brl(report.receivables.later)]]
        receivable_colors = {}
        for bucket, amount in report.receivables.aging.items():
            receivable_rows.append([f"Vencido há {bucket}", brl(amount)])
            if amount:
                receivable_colors[(len(receivable_rows) - 1, 1)] = "#C03030"
        receivable_rows.append(["Total em aberto", brl(report.receivables.total)])
        _fill(self.receivables, receivable_rows, colors=receivable_colors)
