"""Property-based tests for the CRUD operations of ProductRepository.

Each test states a rule that must hold for *any* generated input, instead of
checking a single hand-picked example.
"""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from inventory import DuplicateSkuError, NotFoundError, ProductRepository, ValidationError
from strategies import (
    invalid_field,
    invalid_product_data,
    product_changes,
    product_data,
    repositories,
)

FIELDS = ("sku", "name", "price", "stock")


def used_skus(repo):
    return {product.sku for product in repo.list_all()}


def unknown_id(repo):
    """Ids that the repository does not contain (never created or deleted)."""
    ids = {product.id for product in repo.list_all()}
    return st.integers().filter(lambda i: i not in ids)


# --- Create -----------------------------------------------------------------


@given(repo=repositories(), data=product_data())
def test_create_adds_exactly_one_product_with_the_given_data(repo, data):
    assume(data["sku"] not in used_skus(repo))
    before = repo.list_all()

    product = repo.create(**data)

    assert {field: getattr(product, field) for field in FIELDS} == data
    assert product.id not in {p.id for p in before}
    assert repo.get(product.id) == product
    assert repo.list_all() == before + [product]


@given(items=st.lists(product_data(), max_size=20, unique_by=lambda d: d["sku"]))
def test_created_products_always_get_distinct_ids(items):
    repo = ProductRepository()
    ids = [repo.create(**data).id for data in items]

    assert len(set(ids)) == len(ids)


@given(repo=repositories(), data=invalid_product_data())
def test_create_with_invalid_data_is_rejected_and_changes_nothing(repo, data):
    before = repo.list_all()

    with pytest.raises(ValidationError):
        repo.create(**data)

    assert repo.list_all() == before


@given(repo=repositories(min_size=1), data=product_data(), choice=st.data())
def test_create_with_a_sku_already_in_use_is_rejected(repo, data, choice):
    existing = choice.draw(st.sampled_from(repo.list_all()))
    before = repo.list_all()

    with pytest.raises(DuplicateSkuError):
        repo.create(**{**data, "sku": existing.sku})

    assert repo.list_all() == before


# --- Read -------------------------------------------------------------------


@given(items=st.lists(product_data(), max_size=20, unique_by=lambda d: d["sku"]))
def test_get_returns_exactly_what_was_created(items):
    repo = ProductRepository()
    created = [repo.create(**data) for data in items]

    for product in created:
        assert repo.get(product.id) == product


@given(items=st.lists(product_data(), max_size=20, unique_by=lambda d: d["sku"]))
def test_list_contains_every_created_product_and_nothing_else(items):
    repo = ProductRepository()
    created = [repo.create(**data) for data in items]

    listed = repo.list_all()
    assert listed == sorted(created, key=lambda p: p.id)
    assert len(listed) == len(repo)


@given(repo=repositories(), choice=st.data())
def test_get_of_an_unknown_id_always_fails(repo, choice):
    missing = choice.draw(unknown_id(repo))

    with pytest.raises(NotFoundError):
        repo.get(missing)


@given(repo=repositories())
def test_reading_never_changes_the_repository(repo):
    before = repo.list_all()

    for product in before:
        repo.get(product.id)
    repo.list_all()

    assert repo.list_all() == before


# --- Update -----------------------------------------------------------------


@given(repo=repositories(min_size=1), changes=product_changes, choice=st.data())
def test_update_changes_only_the_given_fields_of_the_target(repo, changes, choice):
    target = choice.draw(st.sampled_from(repo.list_all()))
    others = [p for p in repo.list_all() if p.id != target.id]
    assume("sku" not in changes or changes["sku"] not in {p.sku for p in others})

    updated = repo.update(target.id, **changes)

    for field in FIELDS:
        assert getattr(updated, field) == changes.get(field, getattr(target, field))
    assert updated.id == target.id
    assert repo.get(target.id) == updated
    assert [p for p in repo.list_all() if p.id != target.id] == others


@given(repo=repositories(min_size=1), changes=product_changes, choice=st.data())
def test_update_is_idempotent(repo, changes, choice):
    target = choice.draw(st.sampled_from(repo.list_all()))
    assume("sku" not in changes or changes["sku"] not in used_skus(repo) - {target.sku})

    first = repo.update(target.id, **changes)
    state_after_first = repo.list_all()
    second = repo.update(target.id, **changes)

    assert first == second
    assert repo.list_all() == state_after_first


@given(repo=repositories(min_size=1), bad=invalid_field(), choice=st.data())
def test_update_with_invalid_data_is_rejected_and_changes_nothing(repo, bad, choice):
    target = choice.draw(st.sampled_from(repo.list_all()))
    field, value = bad
    before = repo.list_all()

    with pytest.raises(ValidationError):
        repo.update(target.id, **{field: value})

    assert repo.list_all() == before


@given(repo=repositories(min_size=2), choice=st.data())
def test_update_to_the_sku_of_another_product_is_rejected(repo, choice):
    target, other = choice.draw(st.permutations(repo.list_all()))[:2]
    before = repo.list_all()

    with pytest.raises(DuplicateSkuError):
        repo.update(target.id, sku=other.sku)

    assert repo.list_all() == before


@given(repo=repositories(), changes=product_changes, choice=st.data())
def test_update_of_an_unknown_id_always_fails(repo, changes, choice):
    missing = choice.draw(unknown_id(repo))
    before = repo.list_all()

    with pytest.raises(NotFoundError):
        repo.update(missing, **changes)

    assert repo.list_all() == before


# --- Delete -----------------------------------------------------------------


@given(repo=repositories(min_size=1), choice=st.data())
def test_delete_removes_only_the_target(repo, choice):
    target = choice.draw(st.sampled_from(repo.list_all()))
    before = repo.list_all()

    deleted = repo.delete(target.id)

    assert deleted == target
    assert repo.list_all() == [p for p in before if p.id != target.id]
    assert len(repo) == len(before) - 1
    with pytest.raises(NotFoundError):
        repo.get(target.id)


@given(repo=repositories(min_size=1), choice=st.data())
def test_deleting_the_same_product_twice_fails(repo, choice):
    target = choice.draw(st.sampled_from(repo.list_all()))
    repo.delete(target.id)
    before = repo.list_all()

    with pytest.raises(NotFoundError):
        repo.delete(target.id)

    assert repo.list_all() == before


@given(repo=repositories(), choice=st.data())
def test_delete_of_an_unknown_id_always_fails(repo, choice):
    missing = choice.draw(unknown_id(repo))
    before = repo.list_all()

    with pytest.raises(NotFoundError):
        repo.delete(missing)

    assert repo.list_all() == before


@given(repo=repositories(min_size=1), data=product_data(), choice=st.data())
def test_deleted_sku_can_be_reused_but_the_id_cannot(repo, data, choice):
    target = choice.draw(st.sampled_from(repo.list_all()))
    highest_id = max(p.id for p in repo.list_all())
    repo.delete(target.id)

    new = repo.create(**{**data, "sku": target.sku})

    assert new.sku == target.sku
    assert new.id > highest_id
