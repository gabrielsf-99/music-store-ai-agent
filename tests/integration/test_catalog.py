"""Catalog tools against the synthetic fixture dataset (tests/fixtures/data).

Fixture products:
  1 Violão Aurora Nylon      R$ 499,90  active, 10 in stock, 10% promotion -> R$ 449,91
  2 Violão Serra Folk Aço    R$ 1.299   active, out of stock, inactive promotion only
  3 Violão Pampa Clássico    R$ 899     discontinued
  4 Ukulele Brisa Concert    R$ 350     coming_soon
  5 Ukulele Brisa Soprano    R$ 199,90  active, promotions of 15% and 20% -> R$ 159,92
"""

from decimal import Decimal

import pytest

from emporio.tools.catalog import (
    UnknownCategoryError,
    get_product_details,
    list_active_promotions,
    list_offered_categories,
    search_products,
)

pytestmark = pytest.mark.integration


def _ids(offers):
    return [o.product_id for o in offers]


def test_search_by_category_and_max_price_returns_only_available(loaded_conn):
    offers = search_products(loaded_conn, category="violão", max_price=Decimal("1000"))

    assert _ids(offers) == [1]


def test_search_can_include_unavailable_products(loaded_conn):
    offers = search_products(loaded_conn, category="violões", only_available=False)

    assert _ids(offers) == [1, 3, 2]  # ordered by final price


def test_price_filter_uses_promotional_price(loaded_conn):
    # Product 1 lists at R$ 499,90 but costs R$ 449,91 with the active promotion.
    offers = search_products(loaded_conn, category="violão", max_price=Decimal("450"))

    assert _ids(offers) == [1]
    assert offers[0].price.final_price == Decimal("449.91")


def test_search_by_name_ranks_best_match_first(loaded_conn):
    offers = search_products(loaded_conn, query="serra folk", only_available=False)

    assert offers[0].product_id == 2


def test_search_by_brand_like_term(loaded_conn):
    offers = search_products(loaded_conn, query="brisa", only_available=False)

    assert set(_ids(offers)) == {4, 5}


def test_unknown_category_lists_valid_ones(loaded_conn):
    with pytest.raises(UnknownCategoryError, match="Ukuleles"):
        search_products(loaded_conn, category="amplificador")


def test_category_without_products_returns_empty(loaded_conn):
    assert search_products(loaded_conn, category="sopro") == []


def test_offered_categories_skip_categories_without_products(loaded_conn):
    assert list_offered_categories(loaded_conn) == ["Ukuleles", "Violões"]


def test_product_details_by_name(loaded_conn):
    details = get_product_details(loaded_conn, "aurora nylon")

    assert details.product_id == 1
    assert details.available
    assert details.specs == {"strings": "nylon", "color": "Natural"}
    assert details.price.discount_percent == 10
    assert details.alternatives == []


def test_product_details_by_id_suggests_alternatives_when_out_of_stock(loaded_conn):
    details = get_product_details(loaded_conn, "2")

    assert not details.available
    assert _ids(details.alternatives) == [1]


def test_product_details_uses_highest_active_promotion(loaded_conn):
    details = get_product_details(loaded_conn, 5)

    assert details.price.discount_percent == 20
    assert details.price.final_price == Decimal("159.92")
    assert not details.price.pix_discount_applies


def test_product_details_not_found(loaded_conn):
    assert get_product_details(loaded_conn, "trompete dourado") is None


def test_list_active_promotions_orders_by_discount(loaded_conn):
    offers = list_active_promotions(loaded_conn)

    assert _ids(offers) == [5, 1]
    assert [o.price.discount_percent for o in offers] == [20, 10]


def test_list_active_promotions_by_category(loaded_conn):
    assert _ids(list_active_promotions(loaded_conn, category="ukulele")) == [5]
