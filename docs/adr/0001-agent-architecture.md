# ADR 0001 — Architecture of the Empório da Música customer support agent

- **Status:** Accepted
- **Date:** 2026-11-05

## 1. Context

Empório da Música (a musical instrument store in Campo Grande/MS, Brazil) needs a text-based
customer support agent that:

1. Takes on a persona aligned with the store's tone ("informal but professional, like a friend who knows music").
2. Answers based on the available context.
3. Knows **when to query data** (price, stock, order status) and **when to query policies** (exchanges, opening hours, payment).
4. Handles out-of-scope questions properly (including accessories, which the store doesn't sell).

Mandatory constraint: **Python as the main language**.

### Data sources

| Source | Volume | Nature |
|---|---|---|
| `products.csv` | 65 rows | Structured (price, stock, status, specs as JSON) |
| `categories.csv` | 9 rows | Structured |
| `orders.csv` / `order_items.csv` | 20 / 22 rows | Structured |
| `promotions.csv` | 25 rows (4 active) | Structured |
| `customers.csv` | 50 rows | Structured, **personal data (LGPD)** |
| `store_policies.pdf` | 8 pages (~3–4k tokens) | Unstructured text, organized in numbered sections |

## 2. Decision

A **hybrid** agent: **function calling with typed tools** over structured data (SQL) and
**RAG** only over the policy manual, orchestrated by **LangGraph**.

### 2.1 Overview

```
emporio.ingest (Python, idempotent)
  CSV → validation/cleaning → Postgres (relational tables, specs → jsonb)
  PDF → extraction → chunk per section → embeddings → pgvector

app (Chainlit)
  └─ LangGraph
       [scope guardrail] → [ReAct agent + tools] → answer
       tools: search_products | get_product_details | get_order_status
              | list_active_promotions | search_policies
       memory: PostgresSaver (thread_id per conversation)

Postgres (DATABASE_URL) → Supabase | Postgres on a VPS (Docker) | local docker-compose
tests/  → unit | integration | e2e
evals/  → question set with expected behavior + accuracy report
```

### 2.2 Decisions per component

| Decision | Choice | Rationale | Alternatives considered |
|---|---|---|---|
| Orchestration | **LangGraph** | An explicit graph allows a guardrail node before the agent, a native checkpointer for history and easy step inspection. | LangChain AgentExecutor (less control); manual tool-calling loop (more infrastructure code). |
| Agent pattern | **ReAct with typed tools** | The LLM decides *which* source to query — exactly the agent's core requirement. | Fixed router by classification (rigid for mixed questions, e.g. "does the Takamine GD20 get the PIX discount?"). |
| Structured data access | **Tools with parameterized SQL** | Security (no free-form SQL over `customers`), predictability, testability. | Text-to-SQL agent: flexible, but risks leaking personal data and wrong queries. |
| Policy retrieval | **Hybrid RAG with one chunk per subsection** (4.1, 4.2, 5.1…): vector search + Postgres full-text search (`portuguese` dictionary) fused by RRF; the agent receives the **top 2 full sections** (e.g. all of section 8 for "what is the warranty?") | The manual's sections are already semantic units; the `section` metadata makes the source traceable. Measured with 14 real questions: vector-only got 11 right in the top 3; hybrid + full section found the right section in 13 (the miss, "address", is covered by the prompt). Scales if the manual grows. | Whole manual in the system prompt: feasible given its size (~4k tokens) and simpler; discarded to keep retrieval traceable and scalable — recorded as a valid alternative. Fixed-size chunks: split rules in the middle. |
| Product search by name | **`pg_trgm` (fuzzy similarity)** | Customers type "GD20", "takamine gd 20". A 65-item catalog doesn't justify embeddings. | Embeddings over the catalog (overkill); `ILIKE` (fragile). |
| Database | **PostgreSQL 16 + pgvector + pg_trgm**, provider-agnostic hosting (see 2.5) | A single database for relational data, vectors and conversation history. | SQLite + Chroma/FAISS (zero setup, but three separate persistence mechanisms). |
| LLM | **OpenRouter** (via `langchain-openai` with `base_url`), model configurable through `LLM_MODEL` | Switch models without code changes; allows comparing models in the evals. Requirement: reliable tool calling. **Default: `anthropic/claude-haiku-5.5`**, chosen by the evals and E2E tests: in the final round all three candidates scored 21/21; Haiku was the fastest (median 4.4 s, p95 6.0 s, vs 6.2 s / 16.8 s for `deepseek/deepseek-v4-flash` and 11.9 s / 16.9 s for `openai/gpt-6-luna-pro`), streams, and was the only one to pass every E2E test. DeepSeek costs ~40% less but followed instructions less strictly (skipped mandatory lookups, empty structured output in the guardrail). In earlier rounds Haiku failed an out-of-stock case; the cause was the search hiding unavailable products, which was fixed in the tool. Reports in `evals/reports/`. | A provider's API directly (coupling). |
| Embeddings | **Local multilingual model** via `fastembed` (ONNX): `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions, 0.22 GB | No cost, no second API key, deterministic, good in pt-BR, no PyTorch. Tiny volume (25 chunks). Larger models (mpnet 1 GB, e5-large 2.2 GB) are a possible evolution. | Embeddings via API (OpenRouter support to be confirmed; adds an external dependency). |
| Interface | **Chainlit** (+ CLI for development) | Pure Python (respects the constraint), ready-made chat UI, shows tool calls/steps — makes the agent's reasoning visible to the team. The graph stays synchronous and runs in a thread, connected to Chainlit by an event queue (`ui/events.py`): avoids maintaining two versions (sync and async) of the pool and the checkpointer. Chainlit's own persistence is disabled; history belongs to `PostgresSaver`. | React + FastAPI (adds a JS codebase and time with no functional gain for the prototype); Streamlit (less suited to chat with steps); CLI only (less demonstrable). |
| History | **LangGraph `PostgresSaver`**, `thread_id` per session | Multi-turn context (e.g. the customer gives the order number and then asks about returns). | In-process memory (lost on restart). |
| Price calculations | **Deterministic, in code** (promotion, 5% PIX discount, installments, shipping) | The manual forbids quoting prices without checking the system; LLMs get arithmetic wrong. | Letting the LLM calculate (unreliable). |
| Package manager | **uv** + `pyproject.toml` | Fast, reproducible lockfile. | pip + requirements.txt. |
| Ingestion | **Idempotent Python script** (`python -m emporio.ingest`), inside the application package | Small volume; the focus is validation and cleaning, not orchestration. A single installable package shares config and connection with the app. | Airflow/Prefect (overkill). |
| Tests | **pytest in three layers** (unit, integration, e2e) + evals (see 2.6) | Each layer covers a different kind of risk at a proportional cost. | Evals only (don't isolate logic failures); unit tests only (don't cover SQL or LLM behavior). |
| Language | **English** for file names, code, tools, commits and the main documentation (README, ADR, AI workflow log); **pt-BR** for customer-facing text (prompts, answers, conversation examples) and the internal development guides | Industry standard for code and project documentation; customer service is in Portuguese. | Everything in Portuguese (mixed with English APIs/libraries). |

### 2.3 Agent tools

| Tool | Input | Rules |
|---|---|---|
| `search_products` | `query?`, `category?`, `max_price?`, `min_price?`, `only_available=True` | Returns list price, promotional price (if there is an active promotion), stock and status. In a search by name, it also reports similar products that were filtered out as unavailable, so the agent doesn't claim an out-of-stock product doesn't exist. |
| `get_product_details` | `name_or_id` | Fuzzy search; returns specs, price, promotion and calculated payment options. Suggests alternatives if out of stock/discontinued. |
| `get_order_status` | `order_id`, `email_or_phone` | **Requires identity verification** (LGPD). Never exposes another customer's data. |
| `list_active_promotions` | `category?` | Only `is_active = 1`; always shows the original price + % (manual section 6.2). |
| `search_policies` | `question` | The 2 most relevant manual sections, in full (title + subsections). |

Tool descriptions (read by the LLM) may be in Portuguese to improve routing in pt-BR conversations.

### 2.4 Prompt strategy

- **System prompt** with: persona and tone (manual section 7.1), scope (instruments only; redirect accessories), **current date and time** (opening hours and exchange deadlines depend on it), fixed store data (name, address, hours), rules against making up prices/stock/deadlines.
- **Scope guardrail** before the agent: a structured LLM call (`reasoning_effort="low"`) classifies the last message, with the 6 previous messages as context, as `in_scope`, `accessory`, `off_topic` or `manipulation`. When out of scope, the guardrail itself answers in the store's tone, without calling tools. When in doubt or on error, the message goes on to the agent (*fail open*): blocking a legitimate customer is the most expensive mistake, and the agent prompt keeps the scope rules as a second layer.
- **Security in the agent prompt:** instructions don't change at the customer's request; customer and tool text is data, not commands; never list customers. The main protection against leaks is structural: no tool lists customers, and orders require verification.
- When applying a policy, the answer refers to it by name ("our exchange policy") without quoting section numbers: the manual is an internal document. The section used stays traceable in the tool steps (CLI/UI).
- If the manual has contact details that differ from the fixed store data (assumption 1), the prompt says to use the fixed data.

### 2.5 Database hosting

The code depends **only on `DATABASE_URL`** (psycopg 3). No provider SDK is used — the database is treated as plain Postgres, so hosting can change without code changes.

| Environment | Hosting | Notes |
|---|---|---|
| Local development / anyone cloning the repository | `docker-compose.yml` with the `pgvector/pgvector:pg16` image | One command to start; no external account needed. |
| Integration tests | Ephemeral container (testcontainers, same image) | **Never** run tests against a remote database. |
| Hosted environment | **Supabase** or **self-managed Postgres on a VPS (Docker)** — open decision, no impact on the code | See the precautions below. |

Database requirements: the `vector` and `pg_trgm` extensions (created by the schema with `CREATE EXTENSION IF NOT EXISTS`).

**Supabase precautions:**
- Use a **dedicated schema (`emporio`)** instead of `public`: tables in `public` are exposed by the Data API (PostgREST), and `customers` contains personal data. Alternative: enable RLS without policies.
- Use a direct connection or the **session pooler (port 5432)**. The transaction pooler (port 6543) doesn't support prepared statements, which psycopg 3 / `PostgresSaver` use. Check IPv4 support for the chosen connection.

**VPS precautions:**
- Use the `pgvector/pgvector:pg16` image (pg_trgm already ships with contrib).
- Don't expose port 5432 publicly without IP/firewall restrictions and TLS; use a dedicated application user with minimal privileges.

### 2.6 Testing strategy

| Layer | Folder / marker | What it covers | Dependencies | When it runs |
|---|---|---|---|---|
| **Unit** | `tests/unit/` | Pure logic: price calculation (promotion, PIX, installments, shipping), exchange/return eligibility rules, CSV cleaning and validation, PDF chunking by section, system prompt assembly. LLM and database mocked. | None | Always (`uv run pytest`) |
| **Integration** | `tests/integration/` · `@pytest.mark.integration` | Tools running real SQL; ingestion idempotency; fuzzy search (`pg_trgm`); retrieval returns the expected section for known questions; `PostgresSaver` persistence; identity verification in `get_order_status`. | Docker (testcontainers + `pgvector/pgvector:pg16`) | `uv run pytest -m integration` |
| **E2E** | `tests/e2e/` · `@pytest.mark.e2e` | Full graph with a real LLM via OpenRouter, conversation scenarios: price lookup, filtered catalog, order status with and without verification, return after the deadline, out-of-scope accessory, off-domain question, multi-turn conversation. Assertions on **tools called and key facts** (e.g. correct price), not on the exact text. | Docker + `OPENROUTER_API_KEY` | `uv run pytest -m e2e` (opt-in; uses tokens) |
| **Evals** | `evals/` | 21 cases (some multi-turn) against the real data; report with routing accuracy (right guardrail decision and tool), fact accuracy, latency and cost. Used to compare models and prompts. | Local database with ingestion + `OPENROUTER_API_KEY` | `uv run python -m evals.run` |

E2E vs evals: E2E is **pass/fail regression** over a few critical scenarios; evals **measure quality** over a larger set and produce metrics.

Unit and integration tests make no LLM calls, so they are deterministic and free. E2E tests are non-deterministic by nature; assertions focus on verifiable behavior to reduce flakiness.

## 3. Data assumptions and inconsistencies

Documented here and summarized in the README.

| # | Inconsistency | Assumption adopted |
|---|---|---|
| 1 | WhatsApp: (67) 3341-4444 (section 1.2) vs (67) 3321-4500 (section 7) | Use (67) 3341-4444 (cover + company data table); record the discrepancy. |
| 2 | Email with an accent in the table (`empóriodamusica`) vs without it on the cover | Use `contato@emporiodamusica.com.br` (domains don't use accents in practice). |
| 3 | Payment table: "minimum installment R$100" vs section 3.1 with tiers (up to 3x / 4–6x R$80 / 7–12x R$100) | Section 3.1 prevails (more specific); up to 3x with a R$50 minimum installment. |
| 4 | Order 3: 2 × R$1,749 = R$3,498, recorded total R$3,450; product 130 is `coming_soon` | The order total is the source of truth for the order; don't recalculate. |
| 5 | Order 20: R$799 + R$689 = R$1,488, recorded total R$1,400 | Same as item 4; ingestion prints a *warning*. |
| 6 | Product 96 is `active` with stock 0; 113 and 136 are `discontinued` | Available = `status = 'active' AND stock_quantity > 0`; apply manual section 7.3. |
| 7 | Categories 6, 7 and 8 have no products | The prompt lists only categories with products, so the agent doesn't offer winds or orchestral strings; if the customer asks, it checks the catalog and says those instruments aren't available at the moment (without mistaking "orchestral strings" for an accessory). |
| 8 | There is no actual delivery date, only `estimated_delivery` | Use `estimated_delivery` as a proxy for the delivery date in return deadlines. |
| 9 | Orders go up to Mar/2026; the current date is later | The agent uses the real system date; delivered orders tend to be past the 7-day withdrawal period → offer legal/manufacturer warranty. |
| 10 | Multiple promotions for the same product (96, 93, 99), all inactive | Consider only `is_active = 1`; if more than one is active, apply the largest discount (they don't stack). |
| 11 | Payments in `orders` use codes (`credit_6x`, `pix`) | Split during ingestion into `payment_method` (`pix`, `debit`, `boleto`, `credit_card`) and `installments`; the readable label is generated in code. |
| 12 | Input files with a long prefix, spaces and Portuguese names (e.g. `políticas_da_loja.pdf`) | The pipeline uses the names `products.csv`, …, `store_policies.pdf` in `data/`, but also accepts `políticas_da_loja.pdf` and CSVs with a prefix in the name (`... - orders.csv`), so no renaming is needed (see `data/README.md`). |
| 13 | Customers 11 and 43 share the email `bruno.martins@jmail.com` | Email is not unique. Identity verification matches the contact against the **order's** customer and never looks a customer up by email; ingestion prints a *warning*. Accepted consequence: whoever uses the shared email can look up the orders of both records. |
| 14 | The statuses in `orders.csv` have no definition | `pending` = awaiting payment confirmation; `confirmed` = payment approved, being prepared; `shipped` = shipped; `delivered` = delivered; `cancelled` = cancelled. |
| 15 | Orders have no sales channel (physical store or online) | All orders have a delivery and are treated as online purchases, so the right of withdrawal (section 4.1) applies. |
| 16 | Section 4.3 (exchange by preference) says "within 7 days" without saying from when | Counted from delivery, like the withdrawal period. |
| 17 | `shipped` orders with an estimated delivery date already past (e.g. order 8, 2026-02-28) | The recorded status is reported as is; the agent points out the overdue date and suggests contacting the team. |
| 18 | Tool results go to the LLM provider (via OpenRouter), including the customer's first name and the items of the verified order | Accepted for the prototype: only the minimum is sent (no email, phone or last name). In production: a data processing agreement with the provider (international transfer, LGPD) and restricting OpenRouter to zero-retention providers. |

## 4. Consequences

**Positive**
- Clear separation between exact data (SQL) and textual knowledge (RAG) — directly meets the requirement of "knowing when to query data vs policies".
- Low risk of hallucinated prices and personal data leaks.
- Database portable between Supabase, a VPS and local just by changing `DATABASE_URL`.
- Layered tests: logic, SQL and agent behavior failures are caught separately.
- Agent reasoning visible in the UI.

**Negative / risks**
- Integration and E2E tests require Docker (mitigated: unit tests run with nothing).
- E2E tests use tokens and may fluctuate (mitigated: opt-in and assertions on behavior, not text).
- RAG over 8 pages is arguably excessive (mitigated by the scalability and traceability rationale).
- The local embedding model adds a download on the first run.
- The extra guardrail adds one LLM call per message: measured +2.7 s on the median (~7.5 s → ~10.1 s). Alternatives if latency becomes a problem: run the guardrail and the agent in parallel, or remove the guardrail and rely on the prompt alone.
- Order verification doesn't limit attempts per conversation: someone can try several contacts for the same order (evolution: failure counter per `thread_id`).
- Conversation history lives in the same schema as the data (`PostgresSaver` tables); ingestion doesn't delete them.

## 5. Out of scope (possible evolution)

- Real WhatsApp channel, customer authentication, actual complaint recording, real shipping calculation by postal code, observability (LangSmith/Langfuse), reranking, automated evaluation with LLM-as-judge, CI running unit + integration tests on every push.
