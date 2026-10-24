"""Product catalog use cases and business rules."""
from __future__ import annotations

from modules.products.models import Product
from modules.products.repository import ProductRepository


class ProductService:
    def __init__(self, repository: ProductRepository) -> None:
        self._repository = repository

    def list_products(self, search: str = "", include_inactive: bool = False) -> list[Product]:
        return self._repository.list_products(search, include_inactive)

    def save_product(self, product: Product) -> Product:
        product.validate()
        existing = self._repository.list_products("", include_inactive=True)
        for item in existing:
            if item.id == product.id:
                continue
            if product.barcode and item.barcode == product.barcode:
                raise ValueError("Já existe um produto com este código de barras.")
            if product.sku and item.sku == product.sku:
                raise ValueError("Já existe um produto com este código interno.")
        return self._repository.save_product(product)

    def archive_product(self, product_id: str) -> None:
        self._repository.archive_product(product_id)
