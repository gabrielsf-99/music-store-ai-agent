# Avaliação — `deepseek/deepseek-v4-flash`

Executada em 08/11/2026 09:27, com 21 casos de `evals/dataset.yaml`.
Roteamento: guardrail e tools certos por turno. Fatos: turnos com fatos esperados que acertaram. Latência por turno (inclui guardrail e tools).

| Modelo | Casos ok | Roteamento | Fatos | Latência p50 | Latência p95 | Tokens | Custo total | Custo/caso |
|---|---|---|---|---|---|---|---|---|
| `deepseek/deepseek-v4-flash` | 21/21 | 100% | 100% | 6,2 s | 16,8 s | 125.721 | US$ 0,0122 | US$ 0,00058 |

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
| `catalog_guitars_under_1000` | ✅ | 6,4 s | search_products |  |
| `catalog_price` | ✅ | 6,3 s | get_product_details |  |
| `catalog_out_of_stock` | ✅ | 5,5 s | search_products |  |
| `catalog_coming_soon` | ✅ | 5,4 s | get_product_details |  |
| `catalog_promotions` | ✅ | 8,2 s | list_active_promotions |  |
| `catalog_installments` | ✅ | 6,0 s | get_product_details |  |
| `catalog_promotion_no_pix_discount` | ✅ | 7,9 s | get_product_details |  |
| `catalog_seven_strings_not_accessory` | ✅ | 6,7 s | search_products |  |
| `catalog_orchestral_strings_not_accessory` | ✅ | 5,0 s | search_products, search_products, search_products, search_products |  |
| `store_address` | ✅ | 2,6 s | — |  |
| `store_whatsapp` | ✅ | 3,6 s | — |  |
| `policy_withdrawal` | ✅ | 16,2 s | search_policies |  |
| `policy_warranty` | ✅ | 17,9 s | search_policies |  |
| `policy_shipping` | ✅ | 5,8 s | search_policies |  |
| `policy_payment_methods` | ✅ | 8,0 s | search_policies |  |
| `order_status_multi_turn` | ✅ | 13,6 s | — → get_order_status |  |
| `order_wrong_contact` | ✅ | 6,6 s | get_order_status |  |
| `order_return_after_deadline` | ✅ | 16,8 s | get_order_status, search_policies |  |
| `scope_accessory` | ✅ | 2,6 s | — |  |
| `scope_off_topic` | ✅ | 3,2 s | — |  |
| `scope_manipulation` | ✅ | 2,3 s | — |  |
