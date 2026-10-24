"""Product persistence adapters: local preview and Supabase."""
from __future__ import annotations

from typing import Protocol
from pathlib import Path
from uuid import uuid4

from core.exceptions import ConfigurationError
from core.supabase_client import get_supabase_client
from modules.products.models import Product


class ProductRepository(Protocol):
    def list_products(self, search: str = "", include_inactive: bool = False) -> list[Product]: ...
    def save_product(self, product: Product) -> Product: ...
    def archive_product(self, product_id: str) -> None: ...


class MemoryProductRepository:
    """In-memory storage used only for UI preview; data is not persisted."""

    def __init__(self) -> None:
        self._products: dict[str, Product] = {}

    def list_products(self, search: str = "", include_inactive: bool = False) -> list[Product]:
        needle = search.casefold().strip()
        products = list(self._products.values())
        if not include_inactive:
            products = [item for item in products if item.active]
        if needle:
            products = [
                item for item in products
                if needle in item.name.casefold()
                or needle in item.barcode.casefold()
                or needle in item.sku.casefold()
                or needle in item.category.casefold()
                or needle in item.brand.casefold()
            ]
        return sorted(products, key=lambda item: item.name.casefold())

    def save_product(self, product: Product) -> Product:
        product.validate()
        for current in self._products.values():
            if current.id != product.id and product.barcode and current.barcode == product.barcode:
                raise ValueError("Já existe um produto com este código de barras.")
            if current.id != product.id and product.sku and current.sku == product.sku:
                raise ValueError("Já existe um produto com este código interno.")
        if not product.id:
            product.id = str(uuid4())
        self._products[product.id] = product
        return product

    def archive_product(self, product_id: str) -> None:
        product = self._products.get(product_id)
        if product is not None:
            product.active = False


class SupabaseProductRepository:
    """Tenant-scoped persistence; database RLS remains the security boundary."""

    def __init__(self, organization_id: str) -> None:
        if not organization_id:
            raise ConfigurationError("A conta não possui uma organização vinculada.")
        self._client = get_supabase_client()
        self._organization_id = organization_id

    @classmethod
    def for_current_user(cls) -> SupabaseProductRepository:
        from core.session_manager import session_manager

        session = session_manager.current
        if session is None:
            raise ConfigurationError("Entre no sistema para acessar os produtos online.")
        try:
            response = (
                get_supabase_client()
                .table("organization_members")
                .select("organization_id")
                .eq("user_id", session.user_id)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            if not rows or not rows[0].get("organization_id"):
                raise ConfigurationError(
                    "Seu usuário ainda não está vinculado a uma organização. "
                    "Configure o vínculo no Supabase antes de usar os dados online."
                )
            return cls(str(rows[0]["organization_id"]))
        except ConfigurationError:
            raise
        except Exception as exc:
            raise ConfigurationError(
                "Não foi possível identificar a organização deste usuário. "
                "Confira se as migrations do módulo Produtos foram aplicadas."
            ) from exc

    def list_products(self, search: str = "", include_inactive: bool = False) -> list[Product]:
        query = (
            self._client.table("products")
            .select("*")
            .eq("organization_id", self._organization_id)
            .order("name")
        )
        if not include_inactive:
            query = query.eq("active", True)
        response = query.execute()
        products = [Product.from_mapping(row) for row in (response.data or [])]
        needle = search.casefold().strip()
        if needle:
            products = [
                item for item in products
                if needle in item.name.casefold()
                or needle in item.barcode.casefold()
                or needle in item.sku.casefold()
                or needle in item.category.casefold()
                or needle in item.brand.casefold()
            ]
        return products

    def save_product(self, product: Product) -> Product:
        product.validate()
        record = product.to_record()
        record["organization_id"] = self._organization_id
        if product.id:
            response = (
                self._client.table("products")
                .update(record)
                .eq("id", product.id)
                .eq("organization_id", self._organization_id)
                .select("*")
                .execute()
            )
        else:
            response = self._client.table("products").insert(record).select("*").execute()
        rows = response.data or []
        if not rows:
            raise RuntimeError(
                "O produto não foi retornado após salvar. Verifique as permissões RLS "
                "e se o registro existe na organização atual."
            )
        return Product.from_mapping(rows[0])

    @property
    def organization_id(self) -> str:
        return self._organization_id

    def upload_product_image(self, image_path: str) -> str:
        """Upload an image into the organization-scoped public product image bucket."""
        path = Path(image_path)
        suffix = path.suffix.lower()
        allowed = {".png", ".jpg", ".jpeg", ".webp"}
        if suffix not in allowed:
            raise ValueError("Formato de imagem não suportado. Use PNG, JPG ou WEBP.")
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("A imagem deve ter no máximo 8 MB.")
        content_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        object_path = f"{self._organization_id}/{uuid4().hex}{suffix}"
        with path.open("rb") as image_file:
            self._client.storage.from_("product-images").upload(
                object_path,
                image_file.read(),
                file_options={"content-type": content_types[suffix], "upsert": "false"},
            )
        return self._client.storage.from_("product-images").get_public_url(object_path)

    def archive_product(self, product_id: str) -> None:
        (
            self._client.table("products")
            .update({"active": False})
            .eq("id", product_id)
            .eq("organization_id", self._organization_id)
            .execute()
        )
