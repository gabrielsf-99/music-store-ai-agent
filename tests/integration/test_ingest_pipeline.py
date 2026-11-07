import shutil
from decimal import Decimal

import pytest

from emporio.ingest.cleaning import DataValidationError
from emporio.ingest.loader import LOAD_ORDER
from emporio.ingest.pipeline import run

pytestmark = pytest.mark.integration

SCHEMA = "emporio"

EXPECTED_COUNTS = {
    "categories": 3,
    "products": 5,
    "promotions": 4,
    "customers": 3,
    "orders": 5,
    "order_items": 6,
    "policy_chunks": 7,
}
TABLES = (*LOAD_ORDER, "policy_chunks")


def _table_counts(conn):
    return {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in TABLES}


def _snapshot(conn):
    return {
        table: conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall() for table in TABLES
    }


def test_loads_all_fixture_rows(conn, fixture_data_dir):
    report = run(fixture_data_dir, conn, SCHEMA)

    assert report.counts == EXPECTED_COUNTS
    assert _table_counts(conn) == EXPECTED_COUNTS
    assert len(report.warnings) == 4


def test_ingestion_is_idempotent(conn, fixture_data_dir):
    run(fixture_data_dir, conn, SCHEMA)
    first = _snapshot(conn)

    run(fixture_data_dir, conn, SCHEMA)

    assert _snapshot(conn) == first


def test_values_are_typed(conn, fixture_data_dir):
    run(fixture_data_dir, conn, SCHEMA)

    price, specs = conn.execute(
        "SELECT price_brl, specs FROM products WHERE product_id = 1"
    ).fetchone()
    method, installments = conn.execute(
        "SELECT payment_method, installments FROM orders WHERE order_id = 2"
    ).fetchone()

    assert price == Decimal("499.90")
    assert specs == {"strings": "nylon", "color": "Natural"}
    assert (method, installments) == ("credit_card", 12)


def test_product_name_supports_trigram_search(conn, fixture_data_dir):
    run(fixture_data_dir, conn, SCHEMA)

    best_match = conn.execute(
        "SELECT product_id FROM products ORDER BY similarity(name, %s) DESC LIMIT 1",
        ("serra folk",),
    ).fetchone()[0]

    assert best_match == 2


def test_invalid_input_keeps_previous_data(conn, fixture_data_dir, tmp_path):
    run(fixture_data_dir, conn, SCHEMA)
    before = _snapshot(conn)

    broken_dir = tmp_path / "data"
    shutil.copytree(fixture_data_dir, broken_dir)
    with (broken_dir / "orders.csv").open("a", encoding="utf-8") as file:
        file.write("6,1,2026-03-10,lost,10,pix,,,\n")

    with pytest.raises(DataValidationError, match=r"orders\.csv:7: 'status'"):
        run(broken_dir, conn, SCHEMA)

    assert _snapshot(conn) == before
