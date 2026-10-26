from datetime import date, timedelta
from decimal import Decimal

import pytest

from modules.analytics.metrics import build_report
from modules.crm.segments import segment_customers
from modules.lab_orders import statuses
from modules.lab_orders.page import order_alert
from modules.prescriptions.models import Prescription, format_diopter
from modules.products.models import Product
from modules.sales.payments import (
    CartLine, PaymentLine, cart_totals, discount_check, installment_schedule, remaining_amount, validate_sale,
)


# Fase 1 — produtos ópticos ---------------------------------------------------
def test_service_products_never_track_stock_and_lens_fields_are_cleared() -> None:
    product = Product(name="Montagem", product_type="servico", lens_index="1.67", stock_quantity=0)
    product.validate()
    assert product.tracks_stock is False
    assert product.lens_index == ""
    assert product.needs_reorder is False


def test_reorder_suggestion_prefers_registered_quantity() -> None:
    assert Product(name="A", stock_quantity=1, minimum_stock=3).suggested_reorder_quantity == 5
    assert Product(name="B", stock_quantity=1, minimum_stock=3, reorder_quantity=12).suggested_reorder_quantity == 12


def test_unknown_product_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="tipo"):
        Product(name="X", product_type="sapato").validate()


# Fase 2 — receitas -----------------------------------------------------------
def test_prescription_requires_axis_when_cylinder_is_present() -> None:
    item = Prescription(od_sphere=-1.25, od_cylinder=-0.75)
    assert any("eixo" in problem for problem in item.errors())
    item.od_axis = 180
    assert item.errors() == []


def test_prescription_normalizes_quarter_steps_and_drops_axis_without_cylinder() -> None:
    item = Prescription(od_sphere=-1.3, oe_sphere=-1.2, oe_axis=90)
    item.normalize()
    assert item.od_sphere == -1.25 and item.oe_sphere == -1.25
    assert item.oe_axis is None


def test_prescription_warns_about_likely_typing_mistakes() -> None:
    item = Prescription(prescribed_at=date.today(), od_sphere=-1.0, oe_sphere=-5.0, od_dnp=31, od_near_dnp=33)
    notes = " ".join(item.warnings())
    assert "Diferença" in notes
    assert "DNP de perto maior" in notes


def test_service_order_payload_computes_near_sphere_from_addition() -> None:
    item = Prescription(od_sphere=-1.0, od_addition=2.0, oe_sphere=0.0, oe_addition=2.0)
    payload = item.to_service_order_payload({"ponte": "18"})
    assert payload["perto"]["od"]["esf"] == "+1,00"
    assert payload["armacao"]["ponte"] == "18"
    assert format_diopter(0.0, plano=True) == "Plano"


# Fase 3 — pedidos e laboratório -------------------------------------------
def test_order_flow_and_quality_gate() -> None:
    assert statuses.next_status("aguardando_envio").code == "enviado_laboratorio"
    assert statuses.next_status("entregue") is None
    assert statuses.skips_quality_check("em_producao", "pronto_retirada") is True
    assert statuses.skips_quality_check("em_conferencia", "pronto_retirada") is False


def test_order_alert_flags_late_laboratory_and_customer_deadline() -> None:
    today = date(2026, 10, 25)
    lab_late = {"status": "em_producao", "lab_expected_at": "2026-10-20", "expected_at": "2026-10-30"}
    assert "Laboratório atrasado" in order_alert(lab_late, today)[0]
    customer_late = {"status": "em_producao", "expected_at": "2026-10-22"}
    assert "Prazo do cliente vencido" in order_alert(customer_late, today)[0]
    assert order_alert({"status": "entregue", "expected_at": "2026-01-01"}, today) is None


# Fase 4 — PDV -----------------------------------------------------------------
def _cart() -> list[CartLine]:
    return [
        CartLine("p1", "Armação", 1, Decimal("500.00"), Decimal("50.00"), stock=3),
        CartLine("p2", "Montagem", 1, Decimal("60.00"), tracks_stock=False),
    ]


def test_cart_totals_and_discount_percent() -> None:
    totals = cart_totals(_cart())
    assert totals.subtotal == Decimal("560.00")
    assert totals.total == Decimal("510.00")
    assert totals.discount_percent == Decimal("8.93")


def test_store_discount_limit_blocks_sellers_but_allows_admin_with_reason() -> None:
    assert discount_check(Decimal("12"), Decimal("10"), False, "")[0] is False
    assert discount_check(Decimal("12"), Decimal("10"), True, "")[0] is False
    assert discount_check(Decimal("12"), Decimal("10"), True, "Cliente fiel")[0] is True
    assert discount_check(Decimal("8"), Decimal("10"), False, "")[0] is True


def test_down_payment_plus_receivable_balance_closes_the_sale() -> None:
    totals = cart_totals(_cart())
    payments = [
        PaymentLine("pix", Decimal("210.00"), is_down_payment=True),
        PaymentLine("crediario", Decimal("300.00"), installments=3, first_due_date=date(2026, 1, 31)),
    ]
    assert remaining_amount(totals.total, payments) == Decimal("0.00")
    assert validate_sale(_cart(), payments, totals) == []
    schedule = installment_schedule(Decimal("100.00"), 3, date(2026, 1, 31))
    assert [value for _due, value in schedule] == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert schedule[1][0] == date(2026, 2, 28)


def test_sale_validation_catches_stock_and_open_balance() -> None:
    lines = [CartLine("p1", "Armação", 5, Decimal("100.00"), stock=2)]
    problems = " ".join(validate_sale(lines, [PaymentLine("pix", Decimal("100.00"))], cart_totals(lines)))
    assert "estoque insuficiente" in problems
    assert "Faltam" in problems


# Fase 5 — indicadores ---------------------------------------------------------
def test_effective_profit_excludes_inventory_purchases_and_refunds() -> None:
    today = date(2026, 10, 25)
    report = build_report(
        start=date(2026, 10, 1), end=today, today=today,
        orders=[
            {"id": "o1", "status": "completed", "total": 1000, "discount": 0, "created_at": "2026-10-10", "seller_id": "u1", "quoted_at": "2026-10-09"},
            {"id": "o2", "status": "cancelled", "total": 999, "created_at": "2026-10-11"},
            {"id": "q1", "status": "draft", "total": 500, "created_at": "2026-10-12", "quoted_at": "2026-10-12"},
        ],
        items=[{"sales_order_id": "o1", "product_id": "p1", "product_name": "Armação", "quantity": 1, "unit_cost": 400, "line_total": 1000}],
        lab_orders=[{"sales_order_id": "o1", "lab_cost": 100, "status": "entregue"}],
        entries=[
            {"direction": "saida", "category": "Aluguel", "status": "pago", "amount": 200, "paid_at": "2026-10-05"},
            {"direction": "saida", "category": "Fornecedor", "status": "pago", "amount": 5000, "paid_at": "2026-10-05"},
            {"direction": "saida", "category": "Estorno de venda", "status": "pago", "amount": 999, "paid_at": "2026-10-11"},
            {"direction": "entrada", "category": "Vendas", "status": "pendente", "amount": 300, "due_date": "2026-10-01"},
        ],
        products=[{"id": "p9", "name": "Parado", "stock_quantity": 2, "cost_price": 50, "tracks_stock": True, "active": True}],
        members=[{"user_id": "u1", "display_name": "Ana"}],
    )
    assert report.revenue == 1000
    assert report.contribution_margin == 500
    assert report.operating_expenses == 200
    assert report.net_profit == 300
    assert report.conversion_percent == 50
    assert report.sellers[0].name == "Ana"
    assert report.stagnant[0].stock_value == 100
    assert report.receivables.overdue == 300


# Fase 6 — CRM -----------------------------------------------------------------
def test_segmentation_flags_risk_new_and_prescription_expiry() -> None:
    today = date(2026, 10, 25)
    customers = [{"id": c, "full_name": c, "active": True} for c in ("risk", "new", "rx", "none")]
    orders = [
        {"customer_id": "risk", "status": "completed", "total": 500, "created_at": (today - timedelta(days=300)).isoformat()},
        {"customer_id": "new", "status": "completed", "total": 800, "created_at": (today - timedelta(days=10)).isoformat()},
    ]
    prescriptions = [{"customer_id": "rx", "prescribed_at": (today - timedelta(days=355)).isoformat(), "active": True}]
    insights = segment_customers(customers, orders, prescriptions, today=today)
    assert "em_risco" in insights["risk"].segments
    assert "novos" in insights["new"].segments
    assert "receita_vencendo" in insights["rx"].segments
    assert "sem_compra" in insights["none"].segments


def test_module_access_respects_role_and_released_modules() -> None:
    from core.permissions import can_access, modules_summary, normalize_modules

    seller = normalize_modules(["vendas", "clientes", "desconhecido"])
    assert seller == frozenset({"vendas", "clientes"})
    assert can_access("member", seller, None)  # visão geral sempre visível
    assert can_access("member", seller, "Vendas") and can_access("member", seller, "Pedidos")
    assert not can_access("member", seller, "Financeiro")
    assert can_access("admin", frozenset(), "Financeiro")
    assert can_access("member", None, "Configurações")  # sem restrição cadastrada
    assert modules_summary("owner", ["vendas"]) == "Todos os módulos"
    assert modules_summary("member", []) == "Somente visão geral"


def test_sales_document_fits_one_page_even_with_many_items() -> None:
    from io import BytesIO

    from modules.sales.document_pdf import DENSITIES, SalesDocument, _render

    item = {"product_name": "Lente multifocal 1.67 antirreflexo (par)", "sku": "LEN-1", "product_type": "lente_oftalmica",
            "quantity": 1, "unit_price": 1000, "discount": 0, "line_total": 1000}
    document = SalesDocument(
        order={"order_number": "V-TESTE", "status": "completed", "created_at": "2026-10-25T12:00:00+00:00",
               "subtotal": 12000, "discount": 0, "total": 12000},
        customer={"full_name": "Cliente Teste"}, items=[item] * 12,
        payments=[{"method": "pix", "amount": 12000}],
        prescription=Prescription(od_sphere=-1.0, oe_sphere=-1.25), frame={"ponte": "18"},
        lab_order={"expected_at": "2026-11-01", "status": "aguardando_envio"}, notes="Observação",
    )
    pages = [_render(BytesIO(), document, k) for k in DENSITIES]
    assert min(pages) == 1
