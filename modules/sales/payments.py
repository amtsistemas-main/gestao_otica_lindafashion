"""Point-of-sale arithmetic shared by the POS screen and the tests.

The database function ``finalize_sales_order_v2`` recalculates and enforces every
rule below; this module only lets the cashier see the same result before sending.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

PAYMENT_METHODS = {
    "dinheiro": "Dinheiro",
    "pix": "Pix",
    "debito": "Cartão de débito",
    "credito": "Cartão de crédito",
    "transferencia": "Transferência",
    "crediario": "Crediário (a receber)",
    "boleto": "Boleto (a receber)",
    "outro": "Outro",
}
RECEIVABLE_METHODS = {"crediario", "boleto"}
INSTALLMENT_METHODS = {"credito", "crediario", "boleto"}


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class CartLine:
    product_id: str
    name: str
    quantity: int
    unit_price: Decimal
    discount: Decimal = Decimal("0")
    product_type: str = ""
    tracks_stock: bool = True
    stock: int = 0

    @property
    def gross(self) -> Decimal:
        return money(self.unit_price * self.quantity)

    @property
    def total(self) -> Decimal:
        return money(self.gross - self.discount)

    def to_payload(self) -> dict:
        return {
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price": float(money(self.unit_price)),
            "discount": float(money(self.discount)),
        }


@dataclass(slots=True)
class PaymentLine:
    method: str
    amount: Decimal
    installments: int = 1
    is_down_payment: bool = False
    first_due_date: date | None = None

    @property
    def receivable(self) -> bool:
        return self.method in RECEIVABLE_METHODS

    @property
    def label(self) -> str:
        base = PAYMENT_METHODS.get(self.method, "Outro")
        suffix = f" {self.installments}x" if self.installments > 1 else ""
        tag = " (sinal)" if self.is_down_payment else ""
        return base + suffix + tag

    def to_payload(self) -> dict:
        payload = {
            "method": self.method,
            "amount": float(money(self.amount)),
            "installments": self.installments,
            "is_down_payment": self.is_down_payment,
        }
        if self.receivable and self.first_due_date:
            payload["first_due_date"] = self.first_due_date.isoformat()
        return payload


@dataclass(slots=True)
class CartTotals:
    subtotal: Decimal = Decimal("0.00")
    discount: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    discount_percent: Decimal = Decimal("0.00")
    items: int = field(default=0)


def cart_totals(lines: list[CartLine]) -> CartTotals:
    subtotal = money(sum((line.gross for line in lines), Decimal("0")))
    discount = money(sum((line.discount for line in lines), Decimal("0")))
    total = subtotal - discount
    percent = (discount / subtotal * 100).quantize(CENT, rounding=ROUND_HALF_UP) if subtotal > 0 else Decimal("0.00")
    return CartTotals(subtotal, discount, total, percent, sum(line.quantity for line in lines))


def paid_total(payments: list[PaymentLine]) -> Decimal:
    return money(sum((payment.amount for payment in payments), Decimal("0")))


def remaining_amount(total: Decimal, payments: list[PaymentLine]) -> Decimal:
    """Positive = still to collect; negative = overpaid."""
    return money(total - paid_total(payments))


def received_now(payments: list[PaymentLine]) -> Decimal:
    return money(sum((p.amount for p in payments if not p.receivable), Decimal("0")))


def add_months(start: date, months: int) -> date:
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(start.day, days[month - 1]))


def installment_schedule(amount: Decimal, installments: int, first_due: date) -> list[tuple[date, Decimal]]:
    """Same split used by the database: equal parts, the last one absorbs the cents."""
    amount = money(amount)
    part = money(amount / installments)
    schedule = []
    for index in range(installments):
        value = amount - part * (installments - 1) if index == installments - 1 else part
        schedule.append((add_months(first_due, index), money(value)))
    return schedule


def discount_check(percent: Decimal, max_percent: Decimal, is_manager: bool, reason: str) -> tuple[bool, str]:
    """Store-wide limit: sellers are blocked above it; owners/admins may exceed with a reason."""
    if percent <= max_percent:
        return True, ""
    if not is_manager:
        return False, (f"Desconto de {str(percent).replace('.', ',')}% acima do limite da loja "
                       f"({str(max_percent).replace('.', ',')}%). Somente administradores podem conceder.")
    if not reason.strip():
        return False, "Informe o motivo do desconto acima do limite da loja."
    return True, f"Desconto acima do limite autorizado por administrador ({str(percent).replace('.', ',')}%)."


def validate_sale(lines: list[CartLine], payments: list[PaymentLine], totals: CartTotals) -> list[str]:
    problems: list[str] = []
    if not lines:
        problems.append("Adicione ao menos um item.")
    for line in lines:
        if line.quantity <= 0:
            problems.append(f"{line.name}: quantidade inválida.")
        if line.discount < 0 or line.discount > line.gross:
            problems.append(f"{line.name}: desconto maior que o valor do item.")
        if line.tracks_stock and line.quantity > line.stock:
            problems.append(f"{line.name}: estoque insuficiente (disponível: {line.stock}).")
    for payment in payments:
        if payment.amount <= 0:
            problems.append("Há pagamento com valor zerado.")
        if payment.method not in PAYMENT_METHODS:
            problems.append("Forma de pagamento inválida.")
        if payment.installments > 1 and payment.method not in INSTALLMENT_METHODS:
            problems.append(f"{PAYMENT_METHODS.get(payment.method, payment.method)} não permite parcelamento.")
    remaining = remaining_amount(totals.total, payments)
    if totals.total > 0 and remaining > 0:
        problems.append(f"Faltam R$ {str(remaining).replace('.', ',')} para fechar os pagamentos.")
    if remaining < 0:
        problems.append(f"Pagamentos excedem o total em R$ {str(-remaining).replace('.', ',')}. Ajuste os valores.")
    return problems
