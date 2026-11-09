# Use of Claude Code in the project

A log of how the assistant was used in each phase: what was asked, what it generated and what changed in review.

## Analysis and architecture

- **Asked:** technical analysis of the requirements and the data, evaluation of the proposed stack (LangGraph, OpenRouter, Postgres, ingestion pipeline, React).
- **Generated:** data analysis (volume, inconsistencies), recommendation of RAG only for the policy manual and SQL tools for structured data, replacing React with Chainlit; ADR 0001 and `CLAUDE.md`.
- **Reviewed/adjusted:** English names for files and code; a three-layer testing strategy; provider-agnostic database (Supabase or VPS).

## Development plan

- **Asked:** an incremental plan with validation at each phase.
- **Generated:** `docs/development-plan.md` with 10 phases, each with deliverables, a validation gate and planned commits.
- **Reviewed/adjusted:** input data kept out of the repository at first (only `data/README.md` with the format); automated tests with synthetic fixtures.

## Phase 0 — Foundation

- **Generated:** `pyproject.toml` (uv), settings, `docker-compose.yml`, connection check.
- **Reviewed/adjusted:** installing uv and Docker Desktop; diagnosing a connection hang on Windows (`localhost` → IPv6), fixed with `127.0.0.1` and a timeout.

## Phase 1 — Schema and ingestion

- **Generated:** SQL schema, ingestion pipeline (cleaning, checks, transactional load), synthetic fixtures, unit and integration tests with testcontainers.
- **Reviewed/adjusted:** profiling the real data revealed wrong counts in the ADR (65 products, 50 customers) and an email shared by two customers — recorded as assumption 13.

## Phase 2 — Pricing rules and catalog

- **Generated:** the manual's pricing rules as pure functions (promotion, PIX, tiered installments, shipping), catalog queries with fuzzy search, unit tests with cases from the manual and integration tests with fixtures.
- **Reviewed/adjusted:** a test that didn't prove what it claimed (installments with a promotion) was rewritten with a case where the promotion changes the result; the limitation of the suggested alternatives was recorded in the plan.

## Phase 3 — Minimal agent

- **Generated:** system prompt (persona, store data, opening hours with open/closed status), LangChain tools with pre-formatted values, LangGraph graph, CLI with scripted mode, E2E tests.
- **Reviewed/adjusted:** diagnosed an OpenRouter 401 error by isolating LangChain with a direct call (the problem was the account); manual validation through the CLI revealed that the search truncated results without telling the agent — fixed with `total_found`/`shown`.

## Phase 4 — Policy manual RAG

- **Generated:** PDF extraction (pypdf layout mode), chunking by numbered section with sequence validation, local embeddings with fastembed, retriever, `search_policies` tool, synthetic PDF for tests.
- **Reviewed/adjusted:** the retrieval strategy was decided by measurement, not assumption — 14 real questions comparing vector search (11/14 in the top 3), full-text, hybrid, and hybrid with full sections (13/14). pypdf's default extraction put each word on its own line; switched to layout mode after inspection.

## Phase 5 — Orders, LGPD and memory

- **Generated:** return/exchange/warranty deadlines, order lookup with identity verification, memory with `PostgresSaver`, conversation resume in the CLI, scripted LLM model for tests.
- **Reviewed/adjusted:** manual validation revealed two problems the tests missed: (1) a tool exception permanently corrupted the saved conversation — solved by handling errors in the `ToolNode`; (2) the LLM refused an already verified order because it distrusted an earlier wrong contact — solved by making it explicit in the prompt that the tool decides verification. The lack of an attempt limit was recorded as a limitation.

## Phase 6 — Guardrail and prompt refinement

- **Generated:** scope guardrail with structured output, classifier prompt, complaint and security sections in the agent prompt, blocking and false-positive tests.
- **Reviewed/adjusted:** the classifier was evaluated on its own before joining the graph (10/10, and `reasoning_effort="low"` chosen after measuring 2.8 s vs 4.0 s at the same accuracy); total latency measured with and without the guardrail (+2.7 s on the median) and recorded in the ADR; the E2E regression revealed that the new complaints section hurt defect questions — fixed and repeated 3 times to confirm stability.

## Phase 7 — Chainlit interface

- **Generated:** a Chainlit-independent event layer (LangGraph stream → events, thread → async bridge), `app.py` with starters and tool steps, Chainlit configuration, event layer tests.
- **Reviewed/adjusted:** the missing streaming was traced to the provider (a direct model call, outside the graph); the unit test revealed that answers from non-streaming models would disappear from the screen; when starting the server, it turned out Chainlit was trying to use the project's `DATABASE_URL` for its own persistence. Browser validation was done by the developer.
- **Empty categories:** while testing, the developer noticed the agent offered orchestral strings and winds (categories with no products) and, once that was fixed, started refusing "orchestral strings" as if it were an accessory. The prompt now lists only categories with products and tells a missing instrument apart from an accessory; scenario covered by E2E.
- **LangGraph Studio:** on request, `langgraph.json` and a module that exports the graph without `PostgresSaver` (the server has its own persistence); validated with a conversation through the `langgraph dev` API (catalog tool and guardrail working, no blocking-call warnings).

## Phase 8 — Evals and model choice

- **Generated:** a set of 21 cases, scoring with unit tests, a script that measures routing, facts, latency and cost and generates comparison reports; an isolated guardrail battery for borderline messages.
- **Reviewed/adjusted:** every failure was read in the full answer before becoming a conclusion: two were false negatives in the scoring; one (out-of-stock product "doesn't exist") was a tool defect, fixed in code. The model was chosen twice: first DeepSeek, by the evals; then the E2E regression showed it skipped instructions, and with the tool defect fixed the developer chose Haiku. It also turned out cost was reported as zero when streaming through OpenRouter (`stream_usage`).

## Delivery

- **Asked:** wrap up the project with a complete README, conversation examples and versioned data, so anyone cloning it can run everything from scratch; main documentation in English.
- **Generated:** decisions, assumptions, limitations, next steps and Claude Code usage sections in the README; 5 real conversations exported from the CLI in `examples/`; English translation of the README, ADR and this log.
- **Reviewed/adjusted:** the values in each example (prices, PIX, installments and return deadlines) were checked against the manual's rules before going into the repository; a clean-clone test confirmed the README is enough to get the agent running. The business next steps came from the developer.
