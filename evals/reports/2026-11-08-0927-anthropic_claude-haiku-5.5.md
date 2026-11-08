# Avaliação — `anthropic/claude-haiku-5.5`

Executada em 08/11/2026 09:27, com 21 casos de `evals/dataset.yaml`.
Roteamento: guardrail e tools certos por turno. Fatos: turnos com fatos esperados que acertaram. Latência por turno (inclui guardrail e tools).

| Modelo | Casos ok | Roteamento | Fatos | Latência p50 | Latência p95 | Tokens | Custo total | Custo/caso |
|---|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-5.5` | 21/21 | 100% | 100% | 4,4 s | 6,0 s | 176.860 | US$ 0,0206 | US$ 0,00098 |

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
| `catalog_guitars_under_1000` | ✅ | 4,9 s | search_products |  |
| `catalog_price` | ✅ | 4,2 s | get_product_details |  |
| `catalog_out_of_stock` | ✅ | 4,5 s | search_products |  |
| `catalog_coming_soon` | ✅ | 4,7 s | get_product_details |  |
| `catalog_promotions` | ✅ | 4,4 s | list_active_promotions |  |
| `catalog_installments` | ✅ | 4,2 s | get_product_details |  |
| `catalog_promotion_no_pix_discount` | ✅ | 4,3 s | get_product_details |  |
| `catalog_seven_strings_not_accessory` | ✅ | 4,5 s | search_products |  |
| `catalog_orchestral_strings_not_accessory` | ✅ | 5,0 s | search_products, search_products, search_products |  |
| `store_address` | ✅ | 2,9 s | — |  |
| `store_whatsapp` | ✅ | 2,1 s | — |  |
| `policy_withdrawal` | ✅ | 4,7 s | search_policies |  |
| `policy_warranty` | ✅ | 4,4 s | search_policies |  |
| `policy_shipping` | ✅ | 5,2 s | search_policies |  |
| `policy_payment_methods` | ✅ | 5,8 s | search_policies |  |
| `order_status_multi_turn` | ✅ | 9,4 s | — → get_order_status |  |
| `order_wrong_contact` | ✅ | 5,0 s | get_order_status |  |
| `order_return_after_deadline` | ✅ | 6,0 s | get_order_status |  |
| `scope_accessory` | ✅ | 1,2 s | — |  |
| `scope_off_topic` | ✅ | 1,3 s | — |  |
| `scope_manipulation` | ✅ | 1,4 s | — |  |
