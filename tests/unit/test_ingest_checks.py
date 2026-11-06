from dataclasses import replace

import pytest

from emporio.ingest.checks import check_integrity, find_inconsistencies
from emporio.ingest.cleaning import DataValidationError
from emporio.ingest.pipeline import MissingInputFilesError, build_dataset


@pytest.fixture
def dataset(fixture_data_dir):
    return build_dataset(fixture_data_dir)


def test_build_dataset_reads_all_fixture_rows(dataset):
    assert len(dataset.categories) == 3
    assert len(dataset.products) == 5
    assert len(dataset.promotions) == 4
    assert len(dataset.customers) == 3
    assert len(dataset.orders) == 5
    assert len(dataset.order_items) == 6


def test_missing_files_are_listed(tmp_path):
    (tmp_path / "products.csv").write_text("product_id\n", encoding="utf-8")

    with pytest.raises(MissingInputFilesError) as exc:
        build_dataset(tmp_path)

    message = str(exc.value)
    assert "categories.csv" in message
    assert "order_items.csv" in message
    assert "products.csv," not in message


def test_find_inconsistencies(dataset):
    warnings = find_inconsistencies(dataset)

    assert warnings == [
        "order 2: total 1400.00 differs from current catalog prices 1498.90",
        "order 3: contains product 4 with status 'coming_soon'",
        "product 5: 2 active promotions (highest discount applies)",
        "customers [2, 3] share the email compartilhado@example.com",
    ]


def test_integrity_rejects_unknown_product_reference(dataset):
    unknown_item = {"order_id": 1, "product_id": 999, "quantity": 1}
    broken = replace(dataset, order_items=[*dataset.order_items, unknown_item])

    with pytest.raises(DataValidationError, match=r"unknown product_id: \[999\]"):
        check_integrity(broken)


def test_integrity_rejects_duplicated_primary_key(dataset):
    broken = replace(dataset, products=[*dataset.products, dataset.products[0]])

    with pytest.raises(DataValidationError, match="duplicated product_id"):
        check_integrity(broken)


def test_integrity_rejects_order_without_items(dataset):
    broken = replace(dataset, order_items=[i for i in dataset.order_items if i["order_id"] != 1])

    with pytest.raises(DataValidationError, match=r"orders without items: \[1\]"):
        check_integrity(broken)
