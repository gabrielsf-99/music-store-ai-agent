from datetime import date
from decimal import Decimal

import pytest

from emporio.ingest.cleaning import (
    DataValidationError,
    clean_order,
    clean_product,
    clean_rows,
    normalize_email,
    parse_flag,
    parse_money,
    parse_payment_method,
    parse_specs,
    phone_digits,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("pix", ("pix", None)),
        ("debit", ("debit", None)),
        ("boleto", ("boleto", None)),
        ("credit_1x", ("credit_card", 1)),
        ("credit_12x", ("credit_card", 12)),
        (" Credit_6x ", ("credit_card", 6)),
    ],
)
def test_parse_payment_method(raw, expected):
    assert parse_payment_method(raw) == expected


@pytest.mark.parametrize("raw", ["credit_13x", "credit_0x", "credit", "cash", ""])
def test_parse_payment_method_rejects_unknown(raw):
    with pytest.raises(DataValidationError):
        parse_payment_method(raw)


def test_parse_money_rounds_to_cents():
    assert parse_money("799.9", "price") == Decimal("799.90")
    assert parse_money("11499", "price") == Decimal("11499.00")


@pytest.mark.parametrize("raw", ["-1", "abc", ""])
def test_parse_money_rejects_invalid(raw):
    with pytest.raises(DataValidationError):
        parse_money(raw, "price")


def test_phone_digits_strips_formatting():
    assert phone_digits("(67) 99812-3456") == "67998123456"
    assert phone_digits("(67) 3341-4444") == "6733414444"


def test_phone_digits_rejects_wrong_length():
    with pytest.raises(DataValidationError):
        phone_digits("99812-3456")


def test_normalize_email_lowercases():
    assert normalize_email(" Ana.Exemplo@Example.COM ") == "ana.exemplo@example.com"


def test_parse_flag():
    assert parse_flag("1", "is_active") is True
    assert parse_flag("0", "is_active") is False
    with pytest.raises(DataValidationError):
        parse_flag("yes", "is_active")


def test_parse_specs():
    assert parse_specs('{"top":"Spruce"}') == {"top": "Spruce"}
    assert parse_specs("") == {}
    with pytest.raises(DataValidationError):
        parse_specs("[1, 2]")
    with pytest.raises(DataValidationError):
        parse_specs("{not json")


def _product_row(**overrides):
    row = {
        "product_id": "95",
        "price_brl": "2199",
        "name": "Takamine GD20 Dreadnought Natural",
        "category_id": "5",
        "description": "Violão dreadnought",
        "stock_quantity": "4",
        "status": "active",
        "specs": '{"top":"Cedro"}',
        "created_at": "2021-03-15",
    }
    return row | overrides


def test_clean_product():
    record = clean_product(_product_row())

    assert record["product_id"] == 95
    assert record["price_brl"] == Decimal("2199.00")
    assert record["status"] == "active"
    assert record["specs"] == {"top": "Cedro"}
    assert record["created_at"] == date(2021, 3, 15)


def test_clean_product_rejects_unknown_status():
    with pytest.raises(DataValidationError, match="status"):
        clean_product(_product_row(status="sold_out"))


def test_clean_order_splits_payment_and_handles_optional_fields():
    record = clean_order(
        {
            "order_id": "9",
            "customer_id": "6",
            "order_date": "2026-02-20",
            "status": "confirmed",
            "total_brl": "349.9",
            "payment_method": "credit_6x",
            "tracking_code": "",
            "estimated_delivery": "",
            "notes": "",
        }
    )

    assert record["payment_method"] == "credit_card"
    assert record["installments"] == 6
    assert record["tracking_code"] is None
    assert record["estimated_delivery"] is None
    assert record["notes"] is None


def test_clean_rows_reports_file_and_line():
    rows = [_product_row(), _product_row(product_id="96", price_brl="abc")]

    with pytest.raises(DataValidationError, match=r"products\.csv:3: 'price_brl'"):
        clean_rows("products.csv", rows, clean_product)
