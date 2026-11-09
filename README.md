# Empório da Música — Customer Support Agent

Virtual assistant for **Empório da Música**, a musical instrument store in Campo Grande/MS, Brazil. It chats with customers over text and answers questions about:

- **Catalog:** products, prices, availability, PIX payment, installments and promotions, by querying the database.
- **Store policies:** exchanges, returns, warranty, shipping and payment, by searching the policy manual (RAG).
- **General information:** address, contacts and opening hours, including whether the store is open right now.
- **Orders:** status, items, tracking and return/exchange/warranty deadlines, after confirming the customer's email or phone.

You can chat in the browser (Chainlit) or in the terminal. Conversations are stored in Postgres.

The agent talks to customers in Brazilian Portuguese, since it serves a store in Brazil. Prompts, agent answers and the [conversation examples](#conversation-examples) are therefore in pt-BR.

## How it works

```
Customer ──► Scope guardrail ──(out of scope: answers without tools)
               │
               ▼
            Agent (LangGraph + LLM via OpenRouter) ──► conversation history in Postgres
               ├── catalog tools  ──► Postgres (parameterized SQL, fuzzy search)
               ├── policy tool    ──► Postgres + pgvector (hybrid search over the manual)
               └── order tool     ──► Postgres (only with the customer's email or phone)
```

The guardrail blocks requests for accessories (the store only sells instruments), off-topic subjects and manipulation attempts. Prices, PIX discount and installments are calculated in code, not by the LLM. Decisions and their rationale: [ADR 0001](docs/adr/0001-agent-architecture.md).

## Requirements

| Tool | Purpose |
|---|---|
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Manages Python 3.12 and the dependencies (downloads Python by itself). |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Local Postgres database and integration tests. |
| An [OpenRouter](https://openrouter.ai/) account | API key for the LLM. |

## Getting started

### 1. Install the dependencies

```powershell
git clone https://github.com/gabrielsf-99/music-store-ai-agent.git
cd music-store-ai-agent
uv sync
```

### 2. Configure `.env`

```powershell
Copy-Item .env.example .env      # Linux/macOS: cp .env.example .env
```

| Variable | What to set |
|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter key. |
| `LLM_MODEL` | An OpenRouter model with tool support. `.env.example` already has the default, `anthropic/claude-haiku-5.5` (see [Model choice](#model-choice)). |
| `POSTGRES_PASSWORD` | A password for the local database. |
| `DATABASE_URL` | The same password in place of `change-me`. Keep `127.0.0.1` (with `localhost`, each connection takes ~5 s longer on Windows). |

The other variables already have default values.

### 3. Start the database and load the data

```powershell
docker compose up -d db
uv run python -m emporio.ingest
```

The store data (6 CSVs and the policy manual in PDF) is already in `data/`; the format is described in [data/README.md](data/README.md). Ingestion validates the data, prints warnings about inconsistencies and loads everything in a single transaction. The first run downloads the embedding model (~0.22 GB, into `.cache/fastembed`). It can be run again at any time: it replaces the previous content.

### 4. Chat with the agent

```powershell
uv run chainlit run app.py          # browser, at http://localhost:8000
uv run python -m emporio.cli        # or in the terminal
```

## Using the agent in the terminal

### Interactive mode

```powershell
uv run python -m emporio.cli
```

Type your messages and `sair` to quit. Each tool the agent calls is shown before the answer:

```
Conversa: cli-3f2a...  (para continuar depois: --thread cli-3f2a...)
Empório da Música — digite 'sair' para encerrar.

Você: Quanto custa o Takamine GD20?
  [tool] get_product_details({"product": "Takamine GD20"})

Empório: O Takamine GD20 Dreadnought Natural está por R$ 2.199,00. No PIX, fica R$ 2.089,05...

Você: Vocês vendem palhetas?
  [guardrail] accessory

Empório: Trabalhamos exclusivamente com instrumentos musicais, então não vendemos palhetas...
```

### Scripted mode

Sends messages in sequence, in the same conversation, without interaction. Useful for testing scenarios:

```powershell
uv run python -m emporio.cli -m "Quais violões vocês têm até R$ 1000?" -m "E o Giannini GF-3D, tem?"
```

### Resuming a conversation

Every conversation is saved in Postgres with an id, shown at the start of the session. To pick up where you left off, even after closing the terminal:

```powershell
uv run python -m emporio.cli --thread cli-3f2a...
```

### Questions to try

| Type | Example (pt-BR) | Meaning |
|---|---|---|
| Price | "Quanto custa o Takamine GD20?" | How much is the Takamine GD20? |
| Catalog | "Quais violões vocês têm até R$ 1000?" | Which acoustic guitars do you have up to R$ 1,000? |
| Out of stock | "Tem o Giannini GF-3D?" | Do you have the Giannini GF-3D? |
| Promotions | "Tem alguma promoção rolando?" | Any promotions going on? |
| Policy | "Me arrependi da compra, posso devolver?" | I regret the purchase, can I return it? |
| Warranty | "Qual a garantia dos instrumentos?" | What is the warranty on instruments? |
| Order | "Quero saber do meu pedido 1" | I want to know about my order 1 (the agent asks for the purchase email or phone) |
| Order return | "Posso devolver?" | Can I return it? (after looking up the order) |
| Accessory | "Vocês vendem encordoamento?" | Do you sell guitar strings? |
| Off topic | "Quem ganhou o jogo ontem?" | Who won the game yesterday? |
| Complaint | "Meu ukulele chegou riscado, estou chateado" | My ukulele arrived scratched, I'm upset |

Customer and order data for testing is in `data/customers.csv` and `data/orders.csv`.

## Using the agent in the browser

```powershell
uv run chainlit run app.py
```

Opens at http://localhost:8000. Use `--headless` to avoid opening the browser automatically, and `--port 8080` for another port.

- **Starters:** buttons with sample questions (guitars, promotions, exchanges, order).
- **Visible tools:** each agent query shows up as a collapsible step above the answer ("Buscando no catálogo", "Consultando o pedido"…), with its input and result.
- **One conversation per tab:** each tab or "New chat" starts a new session, saved in Postgres with id `web-<session>`.
- **Readme:** the info button shows `chainlit.md`, describing what the assistant can do.

The UI configuration lives in `.chainlit/config.toml` (name, language, step display). File upload and message editing are disabled: the agent doesn't read files, and editing a message would duplicate the turn in the saved history.

The answer streams in as the model generates it. Some models (e.g. `openai/gpt-6-luna-pro`) return the whole answer at once; with them, it appears at the end.

## Inspecting the agent in LangGraph Studio

To see the graph and debug conversations step by step (state of each node, tool calls, guardrail decision):

```powershell
uv run langgraph dev
```

The server starts at http://127.0.0.1:2024 and opens Studio in the browser (`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`). Use `--no-browser` to skip opening it. The configuration is in `langgraph.json`, which points to the `emporio` graph in `src/emporio/agent/studio.py`.

It is the same agent as the CLI and the web UI (real guardrail, tools, database and LLM), with one difference: conversations are stored in the dev server's own persistence (`.langgraph_api/` folder), not in Postgres.

## Model choice

The default model was chosen by measuring, not by preference. `uv run python -m evals.run` runs 21 evaluation cases (catalog, store info, policies, orders, out of scope) against the real data and measures whether the agent uses the right tool, whether the answer contains the expected facts, latency and cost. Final round results ([report](evals/reports/2026-11-08-0927-comparison.md)):

| Model | Cases passed | Median / p95 latency | Cost per conversation | Streaming |
|---|---|---|---|---|
| **`anthropic/claude-haiku-5.5`** (default) | 21/21 | 4.4 s / 6.0 s | US$ 0.0010 | yes |
| `deepseek/deepseek-v4-flash` | 21/21 | 6.2 s / 16.8 s | US$ 0.0006 | yes |
| `openai/gpt-6-luna-pro` | 21/21 | 11.9 s / 16.9 s | US$ 0.0019 | no |

With all three tied on accuracy, Haiku won for being the fastest and most stable, and it was the only one to pass every E2E test: DeepSeek, the cheapest, sometimes skipped mandatory catalog lookups. To switch models, change `LLM_MODEL` in `.env` and run the evals. How to evaluate: [docs/testing.md](docs/testing.md#avaliação-evals).

## Conversation examples

Real conversations exported from the CLI (in pt-BR), showing the tools called and the guardrail decisions:

| Example | What it shows |
|---|---|
| [Catalog and pricing](examples/01-catalog-and-pricing.md) | Search by category and price, out-of-stock product with alternatives, PIX and installments. |
| [Store information](examples/02-store-info.md) | Address, opening hours and contact; whether the store is open now. |
| [Order and return](examples/03-order-and-return.md) | Identity verification, order deadlines and warranty policy in the following turn. |
| [Promotions and policies](examples/04-promotions-and-policies.md) | Promotions without stacking the PIX discount, warranty and shipping from the manual. |
| [Out of scope](examples/05-out-of-scope.md) | Accessory, off-topic subject and manipulation attempt blocked by the guardrail. |

## Technical decisions

Summary of [ADR 0001](docs/adr/0001-agent-architecture.md), which also lists the alternatives considered:

| Decision | Choice | Why |
|---|---|---|
| Approach | Hybrid agent: function calling (ReAct) for structured data and RAG only for the manual | The LLM decides which source to query, including mixed questions ("does the GD20 get the PIX discount?"). |
| Structured data | Tools with parameterized SQL | No text-to-SQL: avoids leaking customer data and wrong queries. |
| Policy manual | Hybrid RAG (pgvector + Portuguese full-text search, RRF fusion), returning the 2 most relevant full sections | Measured with 14 questions: vector-only got 11 right; hybrid with full sections, 13. |
| Product search by name | `pg_trgm` (text similarity) | Customers type "gd20" or "takamine gd 20"; 65 products don't justify embeddings. |
| Calculations | Promotion, PIX, installments and deadlines in code | LLMs get arithmetic wrong; the manual forbids quoting prices without checking the system. |
| Privacy | Orders only with the purchase email or phone, matched against the order's customer | LGPD (Brazil's data protection law): never expose another customer's data. |
| Scope | Guardrail with structured output before the agent | Blocks accessories, off-topic subjects and manipulation without spending tool calls. |
| Orchestration and memory | LangGraph with `PostgresSaver` | Explicit guardrail node and per-conversation history that survives restarts. |
| Database | PostgreSQL 16 with pgvector, accessed only through `DATABASE_URL` | One database for data, vectors and history; runs locally, on Supabase or on a VPS. |
| LLM | OpenRouter, model set in `LLM_MODEL` | Switch models without code changes; choice made by the evals. |
| Embeddings | Local multilingual model (fastembed) | No cost or second API key; good in Portuguese. |
| Interface | Chainlit + CLI | Pure Python, with tools visible in each answer. |

## Data assumptions

The data has inconsistencies that required a decision. The main ones (full list in [ADR 0001, section 3](docs/adr/0001-agent-architecture.md#3-data-assumptions-and-inconsistencies)):

| Inconsistency | Decision |
|---|---|
| Two WhatsApp numbers in the manual | (67) 3341-4444, the one on the cover and in the company data table. |
| Store email with and without an accent | `contato@emporiodamusica.com.br`, without the accent. |
| Minimum installment: R$ 100 in the table vs tiers in section 3.1 | Section 3.1 wins: up to 3x with a R$ 50 minimum, 4–6x with R$ 80, 7–12x with R$ 100. |
| Orders 3 and 20 with a total different from the sum of items | The recorded total wins; ingestion prints a warning. |
| `active` product with zero stock | Available = `active` and stock greater than zero. |
| Categories with no products (winds, orchestral strings) | Not offered; if the customer asks, the agent checks the catalog and says there are none. |
| No delivery date | The estimated delivery date is used as the delivery date for return deadlines. |
| More than one promotion for the same product | Only active ones count; if more than one is active, the largest discount applies (they don't stack). |
| Two customers with the same email | Verification matches the contact against the order's customer and never looks a customer up by email. |
| Undefined order statuses | `pending`, `confirmed`, `shipped`, `delivered` and `cancelled`, with meanings defined in the ADR. |
| Orders without a sales channel | Treated as online purchases: the right of withdrawal applies. |

## Limitations

| Limitation | Impact |
|---|---|
| Order verification doesn't limit attempts. | Someone can try several emails or phones for the same order. |
| The guardrail is an extra LLM call. | +2.7 s on the median response time. |
| Two customer records share the same email. | Whoever uses that email sees both customers' orders. |
| Alternatives to an out-of-stock product consider only category and price. | For a nylon-string guitar, it may suggest a steel-string one. |
| Shipping is not calculated by postal code. | The agent explains shipping options and delivery times, but not the cost. |
| Tool results are sent to the LLM provider. | First name and order items go through OpenRouter (email, phone and last name don't). |
| Complaints are not recorded. | The agent only refers the customer to the team. |
| No observability or CI. | No conversation tracing and no tests on every push. |

## Next steps

**Business**

| Next step | Goal |
|---|---|
| Integrate with a payment gateway | Close the order inside the conversation. |
| Integrate with the WhatsApp API or Evolution API | Serve customers on the channel they already use. |
| Customer registration | Recognize who is talking and skip the contact confirmation on every order. |
| Account recovery | Let customers recover their account (e.g. a code sent by email or WhatsApp). |
| Push messages with promotions | Increase conversion with notifications segmented by interest. |
| Product photos in messages, including POV shots | Increase perceived value and make the conversation feel more real and human. |

**Technical**

| Next step | Addresses |
|---|---|
| Per-conversation counter of failed verifications, blocking after N attempts | Unlimited attempts. |
| Run the guardrail and the agent in parallel | Guardrail latency. |
| Verify by phone when the email is not unique | Shared email. |
| Prioritize similar specs in alternatives | Suggestions of a different product type. |
| Integrate with the Correios (Brazilian postal service) or carrier API | Shipping by postal code. |
| Data processing agreement and zero-retention providers on OpenRouter | Data sent to the LLM provider. |
| Tool that opens a complaint ticket | Unrecorded complaints. |
| LangSmith or Langfuse; unit and integration tests on every push | Observability and CI. |

## Use of Claude Code

The project was built with Claude Code as a pair programmer, phase by phase, following the [development plan](docs/development-plan.md). [CLAUDE.md](CLAUDE.md) defines the rules it follows: the ADR architecture, parameterized SQL, calculations in code, tests for every new piece of logic, and small commits run by the developer.

The assistant generated code, tests and documentation; decisions and validation stayed with the developer. Several fixes came from manual testing and measurement rather than from the first generated version: the retrieval strategy was chosen by measuring, the UI revealed that the agent offered empty categories, and the evals showed that the search hid out-of-stock products. The log of each phase (what was asked, what was generated and what changed in review) is in [docs/ai-workflow.md](docs/ai-workflow.md).

## Useful commands

| Command | Purpose |
|---|---|
| `uv run python -m emporio.db` | Tests the database connection. |
| `uv run python -m emporio.ingest --data-dir <folder>` | Runs ingestion from another folder. |
| `docker compose down` | Stops the database (data stays in the volume). |
| `docker compose down -v` | Stops the database and deletes the data. |
| `uv run pytest` | Unit tests. Full guide in [docs/testing.md](docs/testing.md). |
| `uv run python -m evals.run` | Agent evaluation (quality, latency and cost); uses tokens. |

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `uv` or `docker` not recognized | The terminal was opened before the installation. Open a new one. |
| Database connection takes ~5 s | `DATABASE_URL` uses `localhost`. Change it to `127.0.0.1`. |
| `missing input files in data` | Files are missing in `data/`; the message lists which ones. |
| `401` when chatting | Invalid OpenRouter key or account without access. Generate a new key in the dashboard. |
| Column error in `policy_chunks` during ingestion | Database created with an older schema. Run `docker compose down -v` and repeat step 3. |
| Agent answers "não foi possível consultar agora" | A tool failed; the full error appears in the terminal. Common cause: database without data (`relation ... does not exist`) — run the ingestion. |
| `address already in use` when starting the web UI | Port 8000 is taken. Use `uv run chainlit run app.py --port 8080`. |
| Studio shows "Failed to fetch" | The browser blocks `smith.langchain.com` from reaching the local server. Click the padlock in the address bar → Site settings → **Local network access** → Allow (in Brave, turn off Shields for the site). |

## Project structure

```
data/                 store data: CSVs and policy manual (format in data/README.md)
docs/                 ADRs, plan, testing and contributing guides
src/emporio/
  agent/              LangGraph graph, guardrail, tools exposed to the LLM and memory
  db/                 connection, pool and SQL schema
  domain/             business rules (prices, return deadlines, store hours)
  ingest/             ingestion pipeline (CSVs and PDF)
  prompts/            agent and guardrail prompts
  rag/                embeddings and policy manual search
  tools/              catalog and order queries
  ui/                 conversation events for the web UI
  cli.py              terminal chat
app.py                web UI (Chainlit)
langgraph.json        `langgraph dev` / LangGraph Studio configuration
chainlit.md           web UI welcome text
.chainlit/            Chainlit configuration
evals/                evaluation cases, script and reports
examples/             real conversations with the agent
tests/                unit, integration and e2e
```

## Documentation

- [ADR 0001](docs/adr/0001-agent-architecture.md): architecture, decisions and data assumptions.
- [Use of Claude Code](docs/ai-workflow.md): how the AI assistant was used in the project.
- In Portuguese (internal development guides):
  - [Contributing guide](docs/contributing.md): development workflow, standards and how to extend the agent.
  - [Testing](docs/testing.md): layers, commands and fixtures.
  - [Development plan](docs/development-plan.md): phases and validation criteria.
