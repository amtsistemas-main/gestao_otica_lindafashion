"""Commercial intelligence calculated from sales, items, lab orders and cash entries.

Revenue (faturamento) and effective profit (lucro efetivo) are kept separate:

    Faturamento líquido      = soma das vendas concluídas no período (já com descontos)
    CMV                      = soma de quantidade × custo congelado no item vendido
    Margem de contribuição   = faturamento − CMV − custos de laboratório das vendas
    Despesas operacionais    = saídas pagas no período, exceto compras de mercadoria
                               (já representadas no CMV) e estornos (vendas canceladas
                               já não entram no faturamento)
    Lucro efetivo            = margem de contribuição − despesas operacionais
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

INVENTORY_CATEGORIES = {"fornecedor", "produto", "produtos", "compra de mercadorias", "mercadorias", "estoque"}
EXCLUDED_EXPENSE_CATEGORIES = INVENTORY_CATEGORIES | {"estorno de venda"}
MONTH_NAMES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _day(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _f(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def pct(part: float, whole: float) -> float:
    return part / whole * 100 if whole else 0.0


@dataclass(slots=True)
class SellerRow:
    name: str
    sales: int = 0
    revenue: float = 0.0
    cost: float = 0.0

    @property
    def ticket(self) -> float:
        return self.revenue / self.sales if self.sales else 0.0

    @property
    def margin_percent(self) -> float:
        return pct(self.revenue - self.cost, self.revenue)


@dataclass(slots=True)
class ProductRow:
    name: str
    product_type: str = ""
    quantity: float = 0.0
    revenue: float = 0.0
    cost: float = 0.0

    @property
    def contribution(self) -> float:
        return self.revenue - self.cost

    @property
    def margin_percent(self) -> float:
        return pct(self.contribution, self.revenue)


@dataclass(slots=True)
class StagnantRow:
    name: str
    product_type: str
    stock: int
    stock_value: float
    last_sale: date | None


@dataclass(slots=True)
class MonthRow:
    label: str
    revenue: float = 0.0
    profit: float = 0.0


@dataclass(slots=True)
class Receivables:
    total: float = 0.0
    overdue: float = 0.0
    overdue_count: int = 0
    next_30_days: float = 0.0
    later: float = 0.0
    aging: dict[str, float] = field(default_factory=lambda: {"1–30 dias": 0.0, "31–60 dias": 0.0, "61–90 dias": 0.0, "+90 dias": 0.0})


@dataclass(slots=True)
class CommercialReport:
    start: date
    end: date
    revenue: float = 0.0
    discounts: float = 0.0
    sales_count: int = 0
    cogs: float = 0.0
    lab_costs: float = 0.0
    operating_expenses: float = 0.0
    quotes_created: int = 0
    quotes_converted: int = 0
    sellers: list[SellerRow] = field(default_factory=list)
    products: list[ProductRow] = field(default_factory=list)
    stagnant: list[StagnantRow] = field(default_factory=list)
    receivables: Receivables = field(default_factory=Receivables)
    monthly: list[MonthRow] = field(default_factory=list)

    @property
    def avg_ticket(self) -> float:
        return self.revenue / self.sales_count if self.sales_count else 0.0

    @property
    def contribution_margin(self) -> float:
        return self.revenue - self.cogs - self.lab_costs

    @property
    def contribution_percent(self) -> float:
        return pct(self.contribution_margin, self.revenue)

    @property
    def net_profit(self) -> float:
        return self.contribution_margin - self.operating_expenses

    @property
    def net_percent(self) -> float:
        return pct(self.net_profit, self.revenue)

    @property
    def conversion_percent(self) -> float:
        return pct(self.quotes_converted, self.quotes_created)

    @property
    def stagnant_value(self) -> float:
        return sum(row.stock_value for row in self.stagnant)


def is_operating_expense(entry: dict) -> bool:
    return (
        entry.get("direction") == "saida"
        and entry.get("status") == "pago"
        and str(entry.get("category") or "").strip().casefold() not in EXCLUDED_EXPENSE_CATEGORIES
    )


def build_report(
    *, start: date, end: date, orders: list[dict], items: list[dict], lab_orders: list[dict],
    entries: list[dict], products: list[dict], members: list[dict], stagnant_days: int = 90,
    today: date | None = None, months: int = 6,
) -> CommercialReport:
    today = today or date.today()
    report = CommercialReport(start=start, end=end)
    names = {str(m.get("user_id")): (m.get("display_name") or "").strip() for m in members}

    completed = {str(o["id"]): o for o in orders if o.get("status") == "completed"}
    in_period = {oid: o for oid, o in completed.items() if (d := _day(o.get("created_at"))) and start <= d <= end}

    items_by_order: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        items_by_order[str(item.get("sales_order_id"))].append(item)
    lab_by_order: dict[str, float] = defaultdict(float)
    for lab in lab_orders:
        if lab.get("sales_order_id") and lab.get("status") != "cancelado":
            lab_by_order[str(lab["sales_order_id"])] += _f(lab.get("lab_cost"))

    sellers: dict[str, SellerRow] = {}
    product_rows: dict[str, ProductRow] = {}
    for order_id, order in in_period.items():
        revenue = _f(order.get("total"))
        cost = sum(_f(i.get("quantity")) * _f(i.get("unit_cost")) for i in items_by_order.get(order_id, []))
        report.revenue += revenue
        report.discounts += _f(order.get("discount"))
        report.sales_count += 1
        report.cogs += cost
        report.lab_costs += lab_by_order.get(order_id, 0.0)
        seller_id = str(order.get("seller_id") or order.get("created_by") or "")
        seller_name = names.get(seller_id) or ("Sem vendedor identificado" if not seller_id else "Usuário sem nome cadastrado")
        row = sellers.setdefault(seller_name, SellerRow(seller_name))
        row.sales += 1
        row.revenue += revenue
        row.cost += cost
        for item in items_by_order.get(order_id, []):
            key = str(item.get("product_id") or item.get("product_name"))
            product = product_rows.setdefault(key, ProductRow(str(item.get("product_name") or "Produto"), str(item.get("product_type") or "")))
            product.quantity += _f(item.get("quantity"))
            product.revenue += _f(item.get("line_total"))
            product.cost += _f(item.get("quantity")) * _f(item.get("unit_cost"))

    report.operating_expenses = sum(
        _f(e.get("amount")) for e in entries
        if is_operating_expense(e) and (d := _day(e.get("paid_at") or e.get("due_date"))) and start <= d <= end
    )

    for order in orders:
        quoted = _day(order.get("quoted_at"))
        if quoted and start <= quoted <= end:
            report.quotes_created += 1
            if order.get("status") == "completed":
                report.quotes_converted += 1

    report.sellers = sorted(sellers.values(), key=lambda r: r.revenue, reverse=True)
    report.products = sorted(product_rows.values(), key=lambda r: r.contribution, reverse=True)

    # Stagnant stock: tracked items with balance and no sale in the window.
    last_sale: dict[str, date] = {}
    for item in items:
        order = completed.get(str(item.get("sales_order_id")))
        sold = _day((order or {}).get("created_at") or item.get("created_at"))
        if order and sold:
            key = str(item.get("product_id"))
            if key not in last_sale or sold > last_sale[key]:
                last_sale[key] = sold
    cutoff = end - timedelta(days=stagnant_days)
    for product in products:
        stock = int(product.get("stock_quantity") or 0)
        if not product.get("active", True) or not product.get("tracks_stock", True) or stock <= 0:
            continue
        sold = last_sale.get(str(product.get("id")))
        if sold is None or sold < cutoff:
            report.stagnant.append(StagnantRow(
                str(product.get("name") or "Produto"), str(product.get("product_type") or ""),
                stock, stock * _f(product.get("cost_price")), sold,
            ))
    report.stagnant.sort(key=lambda r: r.stock_value, reverse=True)

    # Receivables aging (open incoming entries).
    receivables = report.receivables
    for entry in entries:
        if entry.get("direction") != "entrada" or entry.get("status") != "pendente":
            continue
        amount = _f(entry.get("amount"))
        due = _day(entry.get("due_date")) or today
        receivables.total += amount
        days_late = (today - due).days
        if days_late > 0:
            receivables.overdue += amount
            receivables.overdue_count += 1
            bucket = "1–30 dias" if days_late <= 30 else "31–60 dias" if days_late <= 60 else "61–90 dias" if days_late <= 90 else "+90 dias"
            receivables.aging[bucket] += amount
        elif (due - today).days <= 30:
            receivables.next_30_days += amount
        else:
            receivables.later += amount

    # Monthly revenue × effective profit for the trend chart.
    first_month = date(end.year, end.month, 1)
    month_starts = []
    for offset in range(months - 1, -1, -1):
        year, month = first_month.year, first_month.month - offset
        while month <= 0:
            month += 12
            year -= 1
        month_starts.append(date(year, month, 1))
    rows = {(m.year, m.month): MonthRow(f"{MONTH_NAMES[m.month - 1]}/{str(m.year)[2:]}") for m in month_starts}
    for order_id, order in completed.items():
        d = _day(order.get("created_at"))
        if d and (d.year, d.month) in rows:
            cost = sum(_f(i.get("quantity")) * _f(i.get("unit_cost")) for i in items_by_order.get(order_id, []))
            row = rows[(d.year, d.month)]
            row.revenue += _f(order.get("total"))
            row.profit += _f(order.get("total")) - cost - lab_by_order.get(order_id, 0.0)
    for entry in entries:
        d = _day(entry.get("paid_at") or entry.get("due_date"))
        if d and (d.year, d.month) in rows and is_operating_expense(entry):
            rows[(d.year, d.month)].profit -= _f(entry.get("amount"))
    report.monthly = [rows[(m.year, m.month)] for m in month_starts]
    return report
