"""Typed product model and validation helpers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


def _decimal(value: Any, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value if value is not None else "0").replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Informe um valor válido para {field_name}.") from exc
    if not parsed.is_finite():
        raise ValueError(f"Informe um valor válido para {field_name}.")
    return parsed


@dataclass(slots=True)
class Product:
    id: str | None = None
    organization_id: str | None = None
    barcode: str = ""
    sku: str = ""
    name: str = ""
    category: str = ""
    brand: str = ""
    supplier_id: str | None = None
    supplier_name: str = ""
    cost_price: Decimal = Decimal("0.00")
    sale_price: Decimal = Decimal("0.00")
    discount_percent: Decimal = Decimal("0.00")
    stock_quantity: int = 0
    minimum_stock: int = 0
    description: str = ""
    image_url: str = ""
    active: bool = True

    @property
    def final_price(self) -> Decimal:
        return (self.sale_price * (Decimal("1") - self.discount_percent / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def gross_margin_percent(self) -> Decimal:
        if self.sale_price <= 0:
            return Decimal("0.00")
        return (((self.final_price - self.cost_price) / self.sale_price) * Decimal("100")).quantize(Decimal("0.01"))

    def validate(self) -> None:
        self.name = self.name.strip()
        self.barcode = self.barcode.strip()
        self.sku = self.sku.strip()
        if not self.name:
            raise ValueError("Informe o nome do produto.")
        if self.cost_price < 0 or self.sale_price < 0:
            raise ValueError("Os preços não podem ser negativos.")
        if not Decimal("0") <= self.discount_percent <= Decimal("100"):
            raise ValueError("O desconto deve estar entre 0% e 100%.")
        if self.stock_quantity < 0 or self.minimum_stock < 0:
            raise ValueError("Estoque e estoque mínimo não podem ser negativos.")

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Product:
        return cls(
            id=str(data["id"]) if data.get("id") else None,
            organization_id=str(data["organization_id"]) if data.get("organization_id") else None,
            barcode=str(data.get("barcode") or ""),
            sku=str(data.get("sku") or ""),
            name=str(data.get("name") or ""),
            category=str(data.get("category") or ""),
            brand=str(data.get("brand") or ""),
            supplier_id=str(data["supplier_id"]) if data.get("supplier_id") else None,
            supplier_name=str(data.get("supplier_name") or ""),
            cost_price=_decimal(data.get("cost_price"), "preço de custo"),
            sale_price=_decimal(data.get("sale_price"), "preço de venda"),
            discount_percent=_decimal(data.get("discount_percent"), "desconto"),
            stock_quantity=int(data.get("stock_quantity") or 0),
            minimum_stock=int(data.get("minimum_stock") or 0),
            description=str(data.get("description") or ""),
            image_url=str(data.get("image_url") or ""),
            active=bool(data.get("active", True)),
        )

    def to_record(self, include_id: bool = False) -> dict[str, Any]:
        record = asdict(self)
        record["cost_price"] = str(self.cost_price.quantize(Decimal("0.01")))
        record["sale_price"] = str(self.sale_price.quantize(Decimal("0.01")))
        record["discount_percent"] = str(self.discount_percent.quantize(Decimal("0.01")))
        record.pop("id", None)
        record.pop("supplier_name", None)
        if not include_id:
            record.pop("organization_id", None)
        return record
