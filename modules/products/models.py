"""Typed product model and validation helpers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

PRODUCT_TYPES = {
    "armacao": "Armação",
    "lente_oftalmica": "Lente oftálmica",
    "lente_contato": "Lente de contato",
    "oculos_sol": "Óculos de sol",
    "acessorio": "Acessório",
    "servico": "Serviço",
    "outro": "Outro",
}
GENDERS = {"": "Não informado", "feminino": "Feminino", "masculino": "Masculino", "unissex": "Unissex", "infantil": "Infantil"}
LENS_TYPES = {"": "Não se aplica", "monofocal": "Monofocal", "bifocal": "Bifocal", "multifocal": "Multifocal", "ocupacional": "Ocupacional"}
LENS_INDEXES = ["", "1.50", "1.53", "1.56", "1.59", "1.60", "1.67", "1.74"]
CONTACT_REPLACEMENTS = ["", "Diária", "Quinzenal", "Mensal", "Trimestral", "Anual"]
FRAME_TYPES = {"armacao", "oculos_sol"}
LENS_PRODUCT_TYPES = {"lente_oftalmica", "lente_contato"}


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
    product_type: str = "outro"
    category: str = ""
    brand: str = ""
    model: str = ""
    color: str = ""
    size: str = ""
    material: str = ""
    gender: str = ""
    lens_type: str = ""
    lens_index: str = ""
    lens_treatment: str = ""
    contact_replacement: str = ""
    supplier_id: str | None = None
    supplier_name: str = ""
    cost_price: Decimal = Decimal("0.00")
    sale_price: Decimal = Decimal("0.00")
    discount_percent: Decimal = Decimal("0.00")
    stock_quantity: int = 0
    minimum_stock: int = 0
    reorder_quantity: int = 0
    tracks_stock: bool = True
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

    @property
    def type_label(self) -> str:
        return PRODUCT_TYPES.get(self.product_type, "Outro")

    @property
    def needs_reorder(self) -> bool:
        """True when a stock-tracked product reached its reorder point."""
        return self.tracks_stock and self.stock_quantity <= self.minimum_stock

    @property
    def suggested_reorder_quantity(self) -> int:
        if self.reorder_quantity > 0:
            return self.reorder_quantity
        return max(1, self.minimum_stock * 2 - self.stock_quantity)

    @property
    def characteristics(self) -> str:
        """Compact optical description, e.g. 'RB2140 · Preto · 52□18 · Acetato'."""
        parts = [self.model, self.color, self.size, self.material]
        if self.product_type == "lente_oftalmica":
            parts += [LENS_TYPES.get(self.lens_type, "") if self.lens_type else "", self.lens_index, self.lens_treatment]
        elif self.product_type == "lente_contato":
            parts.append(self.contact_replacement)
        return " · ".join(part for part in parts if part)

    def validate(self) -> None:
        self.name = self.name.strip()
        self.barcode = self.barcode.strip()
        self.sku = self.sku.strip()
        if not self.name:
            raise ValueError("Informe o nome do produto.")
        if self.product_type not in PRODUCT_TYPES:
            raise ValueError("Selecione um tipo de produto válido.")
        if self.gender not in GENDERS:
            raise ValueError("Selecione um público válido.")
        if self.lens_type not in LENS_TYPES:
            raise ValueError("Selecione um tipo de lente válido.")
        if self.cost_price < 0 or self.sale_price < 0:
            raise ValueError("Os preços não podem ser negativos.")
        if not Decimal("0") <= self.discount_percent <= Decimal("100"):
            raise ValueError("O desconto deve estar entre 0% e 100%.")
        if self.stock_quantity < 0 or self.minimum_stock < 0 or self.reorder_quantity < 0:
            raise ValueError("Estoque, ponto de reposição e quantidade de reposição não podem ser negativos.")
        # Attributes that do not apply to the product type are cleared so reports stay consistent.
        if self.product_type == "servico":
            self.tracks_stock = False
        if self.product_type != "lente_oftalmica":
            self.lens_type = self.lens_index = self.lens_treatment = ""
        if self.product_type != "lente_contato":
            self.contact_replacement = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Product:
        return cls(
            id=str(data["id"]) if data.get("id") else None,
            organization_id=str(data["organization_id"]) if data.get("organization_id") else None,
            barcode=str(data.get("barcode") or ""),
            sku=str(data.get("sku") or ""),
            name=str(data.get("name") or ""),
            product_type=str(data.get("product_type") or "outro"),
            category=str(data.get("category") or ""),
            brand=str(data.get("brand") or ""),
            model=str(data.get("model") or ""),
            color=str(data.get("color") or ""),
            size=str(data.get("size") or ""),
            material=str(data.get("material") or ""),
            gender=str(data.get("gender") or ""),
            lens_type=str(data.get("lens_type") or ""),
            lens_index=str(data.get("lens_index") or ""),
            lens_treatment=str(data.get("lens_treatment") or ""),
            contact_replacement=str(data.get("contact_replacement") or ""),
            supplier_id=str(data["supplier_id"]) if data.get("supplier_id") else None,
            supplier_name=str(data.get("supplier_name") or ""),
            cost_price=_decimal(data.get("cost_price"), "preço de custo"),
            sale_price=_decimal(data.get("sale_price"), "preço de venda"),
            discount_percent=_decimal(data.get("discount_percent"), "desconto"),
            stock_quantity=int(data.get("stock_quantity") or 0),
            minimum_stock=int(data.get("minimum_stock") or 0),
            reorder_quantity=int(data.get("reorder_quantity") or 0),
            tracks_stock=bool(data.get("tracks_stock", True)),
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
