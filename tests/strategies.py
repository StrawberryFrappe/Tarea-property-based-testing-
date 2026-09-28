"""Hypothesis strategies that generate valid and invalid product data."""

import string
from decimal import Decimal

from hypothesis import strategies as st

from inventory import ProductRepository
from inventory.models import MAX_NAME_LENGTH, MAX_SKU_LENGTH, SKU_PATTERN

SKU_ALPHABET = string.ascii_letters + string.digits + "-"

# --- valid values -----------------------------------------------------------

skus = st.text(alphabet=SKU_ALPHABET, min_size=1, max_size=MAX_SKU_LENGTH)
names = st.text(min_size=1, max_size=MAX_NAME_LENGTH).filter(lambda s: s.strip())
prices = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
stocks = st.integers(min_value=0, max_value=1_000_000)

VALID_VALUES = {"sku": skus, "name": names, "price": prices, "stock": stocks}


def product_data(sku_strategy=skus):
    """Keyword arguments accepted by ProductRepository.create."""
    return st.fixed_dictionaries(
        {"sku": sku_strategy, "name": names, "price": prices, "stock": stocks}
    )


# Any non-empty subset of the fields, used for partial updates.
product_changes = st.fixed_dictionaries({}, optional=VALID_VALUES).filter(bool)

# --- invalid values ---------------------------------------------------------

invalid_skus = st.one_of(
    st.just(""),
    st.text(alphabet=SKU_ALPHABET, min_size=MAX_SKU_LENGTH + 1, max_size=MAX_SKU_LENGTH + 20),
    st.text(min_size=1, max_size=MAX_SKU_LENGTH).filter(lambda s: not SKU_PATTERN.fullmatch(s)),
    st.integers(),
)
invalid_names = st.one_of(
    st.text(alphabet=" \t\n\r", max_size=10),
    st.text(min_size=MAX_NAME_LENGTH + 1, max_size=MAX_NAME_LENGTH + 50),
    st.integers(),
)
invalid_prices = st.one_of(
    st.decimals(max_value=Decimal("-0.01"), places=2, allow_nan=False, allow_infinity=False),
    st.decimals(min_value=Decimal("0"), max_value=Decimal("1000"), places=3).filter(
        lambda d: d.normalize().as_tuple().exponent < -2
    ),
    st.sampled_from([Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")]),
    st.floats(allow_nan=False),
)
invalid_stocks = st.one_of(
    st.integers(max_value=-1),
    st.booleans(),
    st.floats(),
    st.text(),
)

INVALID_VALUES = {
    "sku": invalid_skus,
    "name": invalid_names,
    "price": invalid_prices,
    "stock": invalid_stocks,
}


@st.composite
def invalid_field(draw):
    """A (field, value) pair where the value breaks exactly that field's rules."""
    field = draw(st.sampled_from(sorted(INVALID_VALUES)))
    return field, draw(INVALID_VALUES[field])


@st.composite
def invalid_product_data(draw):
    """Valid product data with exactly one field replaced by an invalid value."""
    data = draw(product_data())
    field, value = draw(invalid_field())
    data[field] = value
    return data


# --- repositories -----------------------------------------------------------


@st.composite
def repositories(draw, min_size=0, max_size=10):
    """A repository filled with random products, some of them already deleted."""
    repo = ProductRepository()
    items = draw(
        st.lists(product_data(), min_size=min_size, max_size=max_size, unique_by=lambda d: d["sku"])
    )
    created = [repo.create(**data) for data in items]

    # Deleting a few products makes sure the properties also hold when the
    # ids stored in the repository are no longer contiguous.
    if len(created) > min_size:
        to_delete = draw(
            st.lists(st.sampled_from(created), max_size=len(created) - min_size, unique=True)
        )
        for product in to_delete:
            repo.delete(product.id)
    return repo
