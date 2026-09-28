class InventoryError(Exception):
    """Base class for every error raised by the inventory."""


class ValidationError(InventoryError, ValueError):
    """A field does not satisfy the domain rules."""


class DuplicateSkuError(InventoryError):
    """Another product already uses the given SKU."""


class NotFoundError(InventoryError, LookupError):
    """There is no product with the given id."""
