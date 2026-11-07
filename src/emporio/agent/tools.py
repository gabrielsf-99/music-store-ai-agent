"""LangChain tools exposed to the LLM. Results carry values already formatted in BRL."""

from decimal import Decimal

from langchain_core.tools import BaseTool, tool
from psycopg_pool import ConnectionPool

from emporio.domain.pricing import PIX_DISCOUNT_PERCENT, format_brl
from emporio.tools import catalog
from emporio.tools.catalog import ProductDetails, ProductOffer, UnknownCategoryError

MAX_PRODUCTS_PER_RESULT = 10


def availability(offer: ProductOffer) -> str:
    if offer.status == "discontinued":
        return "descontinuado (não faz mais parte do catálogo)"
    if offer.status == "coming_soon":
        return "em breve (ainda não disponível para venda)"
    if offer.stock_quantity <= 0:
        return "esgotado no momento"
    return "disponível"


def offer_to_dict(offer: ProductOffer) -> dict:
    price = offer.price
    if price.max_installments > 1:
        installments = (
            f"até {price.max_installments}x de {format_brl(price.installment_value)} sem juros"
        )
    else:
        installments = "somente à vista"

    data = {
        "product_id": offer.product_id,
        "name": offer.name,
        "category": offer.category,
        "availability": availability(offer),
        "price": format_brl(price.final_price),
        "pix_price": format_brl(price.pix_price),
        "pix_discount": (
            f"{PIX_DISCOUNT_PERCENT}%"
            if price.pix_discount_applies
            else "não se aplica (produto em promoção)"
        ),
        "installments": installments,
    }
    if price.has_promotion:
        data["promotion"] = {
            "name": price.promotion_name,
            "discount": f"{price.discount_percent}%",
            "original_price": format_brl(price.list_price),
        }
    return data


def details_to_dict(details: ProductDetails) -> dict:
    return {
        **offer_to_dict(details),
        "description": details.description,
        "specs": details.specs,
        "alternatives": [offer_to_dict(a) for a in details.alternatives],
        "other_matches": details.other_matches,
    }


def offers_result(offers: list[ProductOffer]) -> dict:
    """Cap the list sent to the LLM, telling it how many were left out."""
    shown = offers[:MAX_PRODUCTS_PER_RESULT]
    result = {
        "total_found": len(offers),
        "shown": len(shown),
        "products": [offer_to_dict(o) for o in shown],
    }
    if len(offers) > len(shown):
        result["note"] = (
            f"Há mais {len(offers) - len(shown)} produtos além dos listados; avise o cliente "
            "e ofereça refinar a busca (faixa de preço, tipo, marca)."
        )
    return result


def _to_decimal(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def build_catalog_tools(pool: ConnectionPool) -> list[BaseTool]:
    @tool(parse_docstring=True)
    def search_products(
        query: str | None = None,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        only_available: bool = True,
    ) -> dict:
        """Busca instrumentos no catálogo por nome/marca, categoria e faixa de preço.

        Use para perguntas como "quais violões até R$ 1000?" ou "vocês têm Yamaha?".
        O filtro de preço considera o preço final, já com promoções.

        Args:
            query: Nome, modelo ou marca (ex.: "Yamaha", "GD20"). Omita para listar por categoria.
            category: Categoria do catálogo (ex.: "Violões", "Ukuleles").
            min_price: Preço mínimo em reais.
            max_price: Preço máximo em reais.
            only_available: Se true, retorna só produtos disponíveis para compra.
        """
        try:
            with pool.connection() as conn:
                offers = catalog.search_products(
                    conn,
                    query=query,
                    category=category,
                    min_price=_to_decimal(min_price),
                    max_price=_to_decimal(max_price),
                    only_available=only_available,
                )
        except UnknownCategoryError as exc:
            return {"error": str(exc)}
        return offers_result(offers)

    @tool(parse_docstring=True)
    def get_product_details(product: str) -> dict:
        """Detalhes de um produto: preço, PIX, parcelamento, promoção, disponibilidade e specs.

        Use quando o cliente perguntar sobre um produto específico. Se o produto não estiver
        disponível, o resultado traz alternativas semelhantes.

        Args:
            product: Nome do produto (pode ser parcial, ex.: "Takamine GD20") ou o product_id.
        """
        with pool.connection() as conn:
            details = catalog.get_product_details(conn, product)
        if details is None:
            return {"error": f"nenhum produto encontrado para '{product}'"}
        return details_to_dict(details)

    @tool(parse_docstring=True)
    def list_active_promotions(category: str | None = None) -> dict:
        """Lista os produtos com promoção ativa, com preço original, desconto e preço final.

        Args:
            category: Categoria do catálogo para filtrar (opcional).
        """
        try:
            with pool.connection() as conn:
                offers = catalog.list_active_promotions(conn, category=category)
        except UnknownCategoryError as exc:
            return {"error": str(exc)}
        return offers_result(offers)

    return [search_products, get_product_details, list_active_promotions]
