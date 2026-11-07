-- Applied by emporio.ingest after `CREATE SCHEMA IF NOT EXISTS <DB_SCHEMA>`;
-- unqualified names resolve to that schema through the connection search_path.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS categories (
    category_id integer PRIMARY KEY,
    name        text NOT NULL,
    description text
);

CREATE TABLE IF NOT EXISTS products (
    product_id     integer PRIMARY KEY,
    category_id    integer NOT NULL REFERENCES categories,
    name           text NOT NULL,
    description    text,
    price_brl      numeric(10, 2) NOT NULL CHECK (price_brl >= 0),
    stock_quantity integer NOT NULL CHECK (stock_quantity >= 0),
    status         text NOT NULL CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    specs          jsonb NOT NULL DEFAULT '{}',
    created_at     date
);

CREATE INDEX IF NOT EXISTS products_name_trgm_idx ON products USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS products_category_idx ON products (category_id);

CREATE TABLE IF NOT EXISTS promotions (
    promotion_id     integer PRIMARY KEY,
    product_id       integer NOT NULL REFERENCES products,
    discount_percent integer NOT NULL CHECK (discount_percent BETWEEN 1 AND 100),
    description      text,
    is_active        boolean NOT NULL
);

CREATE INDEX IF NOT EXISTS promotions_product_idx ON promotions (product_id);

CREATE TABLE IF NOT EXISTS customers (
    customer_id  integer PRIMARY KEY,
    name         text NOT NULL,
    phone        text NOT NULL,
    phone_digits text NOT NULL,
    email        text NOT NULL,
    city         text
);

CREATE TABLE IF NOT EXISTS orders (
    order_id           integer PRIMARY KEY,
    customer_id        integer NOT NULL REFERENCES customers,
    order_date         date NOT NULL,
    status             text NOT NULL
        CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    total_brl          numeric(10, 2) NOT NULL CHECK (total_brl >= 0),
    payment_method     text NOT NULL CHECK (payment_method IN ('pix', 'debit', 'boleto', 'credit_card')),
    installments       smallint CHECK (installments BETWEEN 1 AND 12),
    tracking_code      text,
    estimated_delivery date,
    notes              text,
    CHECK ((payment_method = 'credit_card') = (installments IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS orders_customer_idx ON orders (customer_id);

-- One row per numbered (sub)section of the policy manual, searched by vector and full text.
-- Dimension = rag.embeddings.EMBEDDING_DIM. No indexes: ~25 rows, an exact scan is fastest.
CREATE TABLE IF NOT EXISTS policy_chunks (
    section      text PRIMARY KEY,
    top_section  text NOT NULL,
    title        text NOT NULL,
    parent_title text,
    content      text NOT NULL,
    embedding    vector(384) NOT NULL,
    search_doc   tsvector GENERATED ALWAYS AS (
        to_tsvector('portuguese', coalesce(parent_title, '') || ' ' || title || ' ' || content)
    ) STORED
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id   integer NOT NULL REFERENCES orders,
    product_id integer NOT NULL REFERENCES products,
    quantity   integer NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (order_id, product_id)
);
