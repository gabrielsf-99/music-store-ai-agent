"""LangChain tools exposed to the LLM. Results carry values already formatted in BRL."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from langchain_core.tools import BaseTool, tool
from psycopg_pool import ConnectionPool

from emporio.domain.pricing import PIX_DISCOUNT_PERCENT, format_brl
from emporio.rag import retriever
from emporio.rag.embeddings import Embedder
from emporio.tools import catalog, orders
from emporio.tools.catalog import ProductDetails, ProductOffer, UnknownCategoryError
from emporio.tools.orders import OrderStatus

# Meaning of each status in orders.csv (ADR 0001, assumption 14).
ORDER_STATUS_LABELS = {
    "pending": "pendente (aguardando confirmação do pagamento)",
    "confirmed": "confirmado (pagamento aprovado, em separação)",
    "shipped": "enviado (a caminho)",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
PAYMENT_LABELS = {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto bancário"}
ORDER_NOT_FOUND = (
    "Não foi possível localizar um pedido com esses dados. Peça ao cliente para conferir o "
    "número do pedido e o e-mail ou telefone usado na compra."
)

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


def payment_label(method: str, installments: int | None) -> str:
    if method == "credit_card":
        return f"cartão de crédito em {installments}x"
    return PAYMENT_LABELS[method]


def order_to_dict(order: OrderStatus) -> dict:
    data = {
        "order_id": order.order_id,
        "customer_first_name": order.customer_first_name,
        "status": ORDER_STATUS_LABELS[order.status],
        "order_date": f"{order.order_date:%d/%m/%Y}",
        "total": format_brl(order.total),
        "payment": payment_label(order.payment_method, order.installments),
        "items": [f"{item.quantity}x {item.name}" for item in order.items],
    }
    if order.tracking_code:
        data["tracking_code"] = order.tracking_code
    if order.estimated_delivery:
        data["estimated_delivery"] = f"{order.estimated_delivery:%d/%m/%Y}"
    if order.notes:
        data["notes"] = order.notes
    if order.deadlines:
        data["return_deadlines"] = [
            {
                "type": d.name,
                "until": f"{d.until:%d/%m/%Y}",
                "situation": f"dentro do prazo (faltam {d.days_left} dias)"
                if d.is_open
                else "prazo encerrado",
            }
            for d in order.deadlines
        ]
    elif order.status != "cancelled":
        data["return_deadlines_note"] = (
            "os prazos de devolução e troca contam a partir do recebimento"
        )
    return data


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


def build_policy_tools(pool: ConnectionPool, embed: Embedder) -> list[BaseTool]:
    @tool(parse_docstring=True)
    def search_policies(question: str) -> dict:
        """Consulta as políticas da loja e retorna as seções mais relevantes.

        Use para trocas e devoluções, garantia, frete e entrega, formas de pagamento e
        parcelamento, regras de promoção, horário de funcionamento e privacidade de dados.

        Args:
            question: A dúvida do cliente, em linguagem natural.
        """
        with pool.connection() as conn:
            sections = retriever.search_policies(conn, embed, question)
        return {
            "sections": [
                {"section": s.section, "title": s.title, "content": s.content} for s in sections
            ]
        }

    return [search_policies]


def build_order_tools(pool: ConnectionPool, today: Callable[[], date]) -> list[BaseTool]:
    @tool(parse_docstring=True)
    def get_order_status(order_id: int, email_or_phone: str) -> dict:
        """Consulta um pedido: status, itens, pagamento, rastreio e prazos de devolução/troca.

        Exige o número do pedido E o e-mail ou telefone usado na compra, ambos informados pelo
        cliente nesta conversa. Nunca invente nem reutilize dados de outro cliente.

        Args:
            order_id: Número do pedido.
            email_or_phone: E-mail ou telefone (com DDD) cadastrado na compra.
        """
        with pool.connection() as conn:
            order = orders.get_order_status(conn, order_id, email_or_phone, today())
        if order is None:
            return {"error": ORDER_NOT_FOUND}
        return order_to_dict(order)

    return [get_order_status]
