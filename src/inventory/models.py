import re
from dataclasses import dataclass
from decimal import Decimal

from .errors import ValidationError

SKU_PATTERN = re.compile(r"[A-Za-z0-9-]+")
MAX_SKU_LENGTH = 32
MAX_NAME_LENGTH = 100
MAX_PRICE_DECIMALS = 2


@dataclass(frozen=True)
class Product:
    id: int
    sku: str
    name: str
    price: Decimal
    stock: int


def validate_sku(sku: object) -> None:
    if not isinstance(sku, str):
        raise ValidationError("sku must be a string")
    if not 1 <= len(sku) <= MAX_SKU_LENGTH:
        raise ValidationError(f"sku must have between 1 and {MAX_SKU_LENGTH} characters")
    if not SKU_PATTERN.fullmatch(sku):
        raise ValidationError("sku may only contain letters, digits and dashes")


def validate_name(name: object) -> None:
    if not isinstance(name, str):
        raise ValidationError("name must be a string")
    if not name.strip():
        raise ValidationError("name must not be blank")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"name must have at most {MAX_NAME_LENGTH} characters")


def validate_price(price: object) -> None:
    # Floats are rejected on purpose: money is handled with Decimal only.
    if not isinstance(price, Decimal):
        raise ValidationError("price must be a Decimal")
    if not price.is_finite():
        raise ValidationError("price must be a finite number")
    if price < 0:
        raise ValidationError("price must not be negative")
    if price.normalize().as_tuple().exponent < -MAX_PRICE_DECIMALS:
        raise ValidationError(f"price must have at most {MAX_PRICE_DECIMALS} decimals")


def validate_stock(stock: object) -> None:
    # bool is a subclass of int, but True/False are not quantities.
    if isinstance(stock, bool) or not isinstance(stock, int):
        raise ValidationError("stock must be an integer")
    if stock < 0:
        raise ValidationError("stock must not be negative")


VALIDATORS = {
    "sku": validate_sku,
    "name": validate_name,
    "price": validate_price,
    "stock": validate_stock,
}
