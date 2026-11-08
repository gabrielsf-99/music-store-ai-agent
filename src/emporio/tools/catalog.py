"""Catalog queries used by the agent tools: products, prices and promotions."""

import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from emporio.domain.pricing import Price, price_product

# word_similarity threshold for free-text product search (0..1).
NAME_MATCH_THRESHOLD = 0.3
CATEGORY_MATCH_THRESHOLD = 0.75
MAX_ALTERNATIVES = 3

_BASE_QUERY = """
SELECT p.product_id, p.name, c.name AS category, p.category_id, p.status, p.stock_quantity,
       p.price_brl, p.description, p.specs, promo.discount_percent, promo.description AS promo_name,
       {score} AS score
FROM products p
JOIN categories c USING (category_id)
LEFT JOIN LATERAL (
    SELECT discount_percent, description
    FROM promotions pr
    WHERE pr.product_id = p.product_id AND pr.is_active
    ORDER BY discount_percent DESC
    LIMIT 1
) promo ON true
"""


class UnknownCategoryError(ValueError):
    pass


@dataclass(frozen=True)
class ProductOffer:
    product_id: int
    name: str
    category: str
    status: str
    stock_quantity: int
    price: Price

    @property
    def available(self) -> bool:
        return self.status == "active" and self.stock_quantity > 0


@dataclass(frozen=True)
class ProductDetails(ProductOffer):
    description: str | None = None
    specs: dict = field(default_factory=dict)
    alternatives: list[ProductOffer] = field(default_factory=list)
    other_matches: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def match_categories(categories: dict[int, str], query: str) -> list[int]:
    """Category ids whose name best matches `query`, tolerating accents and plurals.

    "violão" -> Violões; "piano" -> Teclados e Pianos; "sopro" -> both wind categories.
    """
    target = _normalize(query)
    scores = {}
    for category_id, name in categories.items():
        normalized = _normalize(name)
        candidates = [normalized, *(word for word in normalized.split() if len(word) >= 3)]
        scores[category_id] = max(SequenceMatcher(None, target, c).ratio() for c in candidates)

    best = max(scores.values(), default=0)
    if best < CATEGORY_MATCH_THRESHOLD:
        return []
    return sorted(cid for cid, score in scores.items() if score == best)


def list_offered_categories(conn: psycopg.Connection) -> list[str]:
    """Names of categories with at least one product; empty ones are not presented as offered."""
    rows = conn.execute(
        "SELECT name FROM categories c"
        " WHERE EXISTS (SELECT 1 FROM products p WHERE p.category_id = c.category_id)"
        " ORDER BY name"
    )
    return [row[0] for row in rows]


def _resolve_categories(conn: psycopg.Connection, query: str) -> list[int]:
    categories = dict(conn.execute("SELECT category_id, name FROM categories").fetchall())
    matched = match_categories(categories, query)
    if not matched:
        names = ", ".join(sorted(categories.values()))
        raise UnknownCategoryError(f"categoria '{query}' não encontrada. Categorias: {names}")
    return matched


def _offer(row: dict) -> ProductOffer:
    return ProductOffer(
        product_id=row["product_id"],
        name=row["name"],
        category=row["category"],
        status=row["status"],
        stock_quantity=row["stock_quantity"],
        price=price_product(row["price_brl"], row["discount_percent"], row["promo_name"]),
    )


def _fetch(
    conn: psycopg.Connection,
    *,
    text_query: str | None = None,
    category_ids: list[int] | None = None,
    product_id: int | None = None,
    only_active_promotions: bool = False,
) -> list[dict]:
    conditions, params = [], []
    if text_query:
        score = sql.SQL("word_similarity(%s, p.name)")
        params.append(text_query)
        conditions.append(sql.SQL("word_similarity(%s, p.name) >= %s"))
        params += [text_query, NAME_MATCH_THRESHOLD]
    else:
        score = sql.SQL("1.0")
    if category_ids:
        conditions.append(sql.SQL("p.category_id = ANY(%s)"))
        params.append(category_ids)
    if product_id is not None:
        conditions.append(sql.SQL("p.product_id = %s"))
        params.append(product_id)
    if only_active_promotions:
        conditions.append(sql.SQL("promo.discount_percent IS NOT NULL"))

    query = sql.SQL(_BASE_QUERY).format(score=score)
    if conditions:
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)
    query += sql.SQL(" ORDER BY score DESC, p.price_brl")

    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(query, params).fetchall()


def search_products(
    conn: psycopg.Connection,
    query: str | None = None,
    category: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    only_available: bool = True,
    limit: int | None = None,
) -> list[ProductOffer]:
    """Search by name/brand, category and price range (on the final, promotional price)."""
    category_ids = _resolve_categories(conn, category) if category else None
    offers = [_offer(row) for row in _fetch(conn, text_query=query, category_ids=category_ids)]

    if only_available:
        offers = [o for o in offers if o.available]
    if min_price is not None:
        offers = [o for o in offers if o.price.final_price >= min_price]
    if max_price is not None:
        offers = [o for o in offers if o.price.final_price <= max_price]
    if not query:
        offers.sort(key=lambda o: o.price.final_price)
    return offers[:limit]


def _alternatives(conn: psycopg.Connection, product: ProductOffer, category_id: int) -> list:
    candidates = [
        offer
        for offer in map(_offer, _fetch(conn, category_ids=[category_id]))
        if offer.available and offer.product_id != product.product_id
    ]
    candidates.sort(key=lambda o: abs(o.price.final_price - product.price.final_price))
    return candidates[:MAX_ALTERNATIVES]


def get_product_details(conn: psycopg.Connection, name_or_id: str | int) -> ProductDetails | None:
    """Best match by id or name. Suggests alternatives when the product is not available."""
    if isinstance(name_or_id, int) or str(name_or_id).strip().isdigit():
        rows = _fetch(conn, product_id=int(name_or_id))
    else:
        rows = _fetch(conn, text_query=str(name_or_id))
    if not rows:
        return None

    best, others = rows[0], rows[1:4]
    offer = _offer(best)
    alternatives = [] if offer.available else _alternatives(conn, offer, best["category_id"])
    return ProductDetails(
        **vars(offer),
        description=best["description"],
        specs=best["specs"],
        alternatives=alternatives,
        other_matches=[row["name"] for row in others],
    )


def list_active_promotions(
    conn: psycopg.Connection, category: str | None = None
) -> list[ProductOffer]:
    category_ids = _resolve_categories(conn, category) if category else None
    rows = _fetch(conn, category_ids=category_ids, only_active_promotions=True)
    offers = [_offer(row) for row in rows]
    offers.sort(key=lambda o: (-o.price.discount_percent, o.price.final_price))
    return offers
