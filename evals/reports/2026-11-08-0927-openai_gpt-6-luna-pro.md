# Avaliação — `openai/gpt-6-luna-pro`

Executada em 08/11/2026 09:27, com 21 casos de `evals/dataset.yaml`.
Roteamento: guardrail e tools certos por turno. Fatos: turnos com fatos esperados que acertaram. Latência por turno (inclui guardrail e tools).

| Modelo | Casos ok | Roteamento | Fatos | Latência p50 | Latência p95 | Tokens | Custo total | Custo/caso |
|---|---|---|---|---|---|---|---|---|
| `openai/gpt-6-luna-pro` | 21/21 | 100% | 100% | 11,9 s | 16,9 s | 338.552 | US$ 0,0398 | US$ 0,00189 |

## Por categoria

| Categoria | Casos ok |
|---|---|
| catálogo | 9/9 |
| loja | 2/2 |
| política | 4/4 |
| pedido | 3/3 |
| fora do escopo | 3/3 |

## Casos

| Caso | Resultado | Latência | Tools | Problemas |
|---|---|---|---|---|
| `catalog_guitars_under_1000` | ✅ | 14,0 s | search_products |  |
| `catalog_price` | ✅ | 9,2 s | get_product_details |  |
| `catalog_out_of_stock` | ✅ | 11,1 s | search_products |  |
| `catalog_coming_soon` | ✅ | 15,2 s | get_product_details |  |
| `catalog_promotions` | ✅ | 12,8 s | list_active_promotions |  |
| `catalog_installments` | ✅ | 9,8 s | get_product_details |  |
| `catalog_promotion_no_pix_discount` | ✅ | 11,1 s | get_product_details |  |
| `catalog_seven_strings_not_accessory` | ✅ | 13,2 s | search_products |  |
| `catalog_orchestral_strings_not_accessory` | ✅ | 12,7 s | search_products |  |
| `store_address` | ✅ | 4,7 s | — |  |
| `store_whatsapp` | ✅ | 5,3 s | — |  |
| `policy_withdrawal` | ✅ | 16,3 s | search_policies |  |
| `policy_warranty` | ✅ | 13,2 s | search_policies |  |
| `policy_shipping` | ✅ | 13,1 s | search_policies |  |
| `policy_payment_methods` | ✅ | 15,9 s | search_policies |  |
| `order_status_multi_turn` | ✅ | 24,9 s | — → get_order_status |  |
| `order_wrong_contact` | ✅ | 10,8 s | get_order_status |  |
| `order_return_after_deadline` | ✅ | 27,5 s | get_order_status, search_policies |  |
| `scope_accessory` | ✅ | 3,1 s | — |  |
| `scope_off_topic` | ✅ | 3,0 s | — |  |
| `scope_manipulation` | ✅ | 3,0 s | — |  |
