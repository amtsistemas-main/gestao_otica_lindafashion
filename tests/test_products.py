from decimal import Decimal

import pytest

from modules.products.models import Product
from modules.products.repository import MemoryProductRepository
from modules.products.service import ProductService


def test_discounted_price_is_calculated_to_cents() -> None:
    product = Product(sale_price=Decimal("199.90"), discount_percent=Decimal("15"))
    assert product.final_price == Decimal("169.92")


def test_product_requires_name_and_nonnegative_prices() -> None:
    with pytest.raises(ValueError, match="nome"):
        Product(name=" ").validate()
    with pytest.raises(ValueError, match="negativos"):
        Product(name="Armação", sale_price=Decimal("-1")).validate()


def test_service_rejects_duplicate_barcode() -> None:
    service = ProductService(MemoryProductRepository())
    service.save_product(Product(name="Óculos A", barcode="7891234567890"))
    with pytest.raises(ValueError, match="código de barras"):
        service.save_product(Product(name="Óculos B", barcode="7891234567890"))


def test_archive_keeps_product_but_hides_from_default_list() -> None:
    service = ProductService(MemoryProductRepository())
    product = service.save_product(Product(name="Óculos", barcode="ABC123"))
    service.archive_product(product.id or "")
    assert service.list_products() == []
    archived = service.list_products(include_inactive=True)
    assert len(archived) == 1
    assert archived[0].active is False
