# Dados de entrada

Coloque os arquivos abaixo nesta pasta antes de rodar a ingestão (`uv run python -m emporio.ingest`).

## Arquivos esperados

| Arquivo | Conteúdo |
|---|---|
| `categories.csv` | Categorias de instrumentos |
| `products.csv` | Catálogo de produtos |
| `promotions.csv` | Promoções por produto |
| `customers.csv` | Clientes (dados pessoais — LGPD) |
| `orders.csv` | Pedidos |
| `order_items.csv` | Itens de cada pedido |
| `store_policies.pdf` | Manual de políticas e procedimentos de atendimento |

Todos os CSVs em UTF-8, separados por vírgula, com cabeçalho na primeira linha.

## Colunas

### `categories.csv`
| Coluna | Tipo | Observação |
|---|---|---|
| `category_id` | inteiro | chave |
| `name` | texto | |
| `description` | texto | |

### `products.csv`
| Coluna | Tipo | Observação |
|---|---|---|
| `product_id` | inteiro | chave |
| `price_brl` | decimal | preço de tabela, ponto como separador decimal |
| `name` | texto | |
| `category_id` | inteiro | referência a `categories` |
| `description` | texto | |
| `stock_quantity` | inteiro | |
| `status` | texto | `active`, `discontinued` ou `coming_soon` |
| `specs` | JSON | objeto com especificações técnicas |
| `created_at` | data | `AAAA-MM-DD` |

### `promotions.csv`
| Coluna | Tipo | Observação |
|---|---|---|
| `promotion_id` | inteiro | chave |
| `product_id` | inteiro | referência a `products` |
| `discount_percent` | inteiro | 0–100 |
| `description` | texto | nome da campanha |
| `is_active` | 0 ou 1 | |

### `customers.csv`
| Coluna | Tipo | Observação |
|---|---|---|
| `customer_id` | inteiro | chave |
| `name` | texto | |
| `phone` | texto | ex.: `(67) 99812-3456` |
| `email` | texto | |
| `city` | texto | |

### `orders.csv`
| Coluna | Tipo | Observação |
|---|---|---|
| `order_id` | inteiro | chave |
| `customer_id` | inteiro | referência a `customers` |
| `order_date` | data | `AAAA-MM-DD` |
| `status` | texto | `pending`, `confirmed`, `shipped`, `delivered` ou `cancelled` |
| `total_brl` | decimal | |
| `payment_method` | texto | `pix`, `debit`, `boleto`, `credit_<N>x` |
| `tracking_code` | texto | opcional |
| `estimated_delivery` | data | opcional |
| `notes` | texto | opcional |

### `order_items.csv`
| Coluna | Tipo | Observação |
|---|---|---|
| `order_id` | inteiro | referência a `orders` |
| `quantity` | inteiro | |
| `product_id` | inteiro | referência a `products` |
