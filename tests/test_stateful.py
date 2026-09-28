"""Stateful property-based test.

Hypothesis generates random sequences of create / read / update / delete
calls and, after every step, compares the repository against a trivial
model: a plain dict from id to field values.
"""

import pytest
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, invariant, rule

from inventory import DuplicateSkuError, NotFoundError, ProductRepository
from strategies import VALID_VALUES, product_data

# A tiny pool of SKUs so that duplicates actually happen during a run.
few_skus = st.sampled_from(["A-1", "B-2", "C-3", "D-4", "E-5"])
changes_with_few_skus = st.fixed_dictionaries(
    {}, optional={**VALID_VALUES, "sku": few_skus}
).filter(bool)


class ProductRepositoryMachine(RuleBasedStateMachine):
    ids = Bundle("ids")

    def __init__(self):
        super().__init__()
        self.repo = ProductRepository()
        self.model: dict[int, dict] = {}
        self.seen_ids: set[int] = set()

    def sku_owner(self, sku):
        return next((pid for pid, fields in self.model.items() if fields["sku"] == sku), None)

    @rule(target=ids, data=product_data(few_skus))
    def create(self, data):
        if self.sku_owner(data["sku"]) is not None:
            with pytest.raises(DuplicateSkuError):
                self.repo.create(**data)
            # -1 is never a valid id, so later rules exercise the error paths.
            return -1

        product = self.repo.create(**data)
        assert product.id not in self.seen_ids
        self.seen_ids.add(product.id)
        self.model[product.id] = data
        return product.id

    @rule(product_id=ids)
    def get(self, product_id):
        if product_id in self.model:
            product = self.repo.get(product_id)
            assert product.id == product_id
            assert vars(product) == {"id": product_id, **self.model[product_id]}
        else:
            with pytest.raises(NotFoundError):
                self.repo.get(product_id)

    @rule(product_id=ids, changes=changes_with_few_skus)
    def update(self, product_id, changes):
        if product_id not in self.model:
            with pytest.raises(NotFoundError):
                self.repo.update(product_id, **changes)
            return

        owner = self.sku_owner(changes.get("sku"))
        if owner is not None and owner != product_id:
            with pytest.raises(DuplicateSkuError):
                self.repo.update(product_id, **changes)
            return

        self.repo.update(product_id, **changes)
        self.model[product_id] = {**self.model[product_id], **changes}

    @rule(product_id=ids)
    def delete(self, product_id):
        if product_id in self.model:
            self.repo.delete(product_id)
            del self.model[product_id]
        else:
            with pytest.raises(NotFoundError):
                self.repo.delete(product_id)

    @invariant()
    def repository_matches_the_model(self):
        listed = {p.id: {k: v for k, v in vars(p).items() if k != "id"} for p in self.repo.list_all()}
        assert listed == self.model
        assert len(self.repo) == len(self.model)

    @invariant()
    def skus_are_unique(self):
        skus = [p.sku for p in self.repo.list_all()]
        assert len(skus) == len(set(skus))

    @invariant()
    def prices_and_stock_are_never_negative(self):
        for product in self.repo.list_all():
            assert product.price >= 0
            assert product.stock >= 0


TestProductRepository = ProductRepositoryMachine.TestCase
