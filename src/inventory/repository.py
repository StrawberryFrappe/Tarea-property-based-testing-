from dataclasses import replace
from decimal import Decimal

from .errors import DuplicateSkuError, NotFoundError
from .models import VALIDATORS, Product


class ProductRepository:
    """In-memory storage for products.

    Ids are assigned by the repository, start at 1 and are never reused,
    not even after a product is deleted.
    """

    def __init__(self) -> None:
        self._products: dict[int, Product] = {}
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._products)

    def __repr__(self) -> str:
        return f"ProductRepository({self.list_all()!r})"

    def create(self, sku: str, name: str, price: Decimal, stock: int) -> Product:
        fields = {"sku": sku, "name": name, "price": price, "stock": stock}
        self._validate(fields)
        self._ensure_sku_is_free(sku)

        product = Product(id=self._next_id, **fields)
        self._products[product.id] = product
        self._next_id += 1
        return product

    def get(self, product_id: int) -> Product:
        try:
            return self._products[product_id]
        except (KeyError, TypeError):
            raise NotFoundError(f"product {product_id!r} does not exist") from None

    def list_all(self) -> list[Product]:
        return sorted(self._products.values(), key=lambda product: product.id)

    def update(
        self,
        product_id: int,
        *,
        sku: str | None = None,
        name: str | None = None,
        price: Decimal | None = None,
        stock: int | None = None,
    ) -> Product:
        """Partial update: only the fields that are not None are changed."""
        current = self.get(product_id)
        changes = {
            field: value
            for field, value in {"sku": sku, "name": name, "price": price, "stock": stock}.items()
            if value is not None
        }
        self._validate(changes)
        if "sku" in changes:
            self._ensure_sku_is_free(changes["sku"], ignore_id=product_id)

        updated = replace(current, **changes)
        self._products[product_id] = updated
        return updated

    def delete(self, product_id: int) -> Product:
        product = self.get(product_id)
        del self._products[product_id]
        return product

    @staticmethod
    def _validate(fields: dict[str, object]) -> None:
        for field, value in fields.items():
            VALIDATORS[field](value)

    def _ensure_sku_is_free(self, sku: str, ignore_id: int | None = None) -> None:
        for product in self._products.values():
            if product.sku == sku and product.id != ignore_id:
                raise DuplicateSkuError(f"sku {sku!r} is already used by product {product.id}")
