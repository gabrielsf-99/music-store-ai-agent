# CLAUDE.md

Guia para o Claude Code neste repositório.

## Projeto

Agente de atendimento da **Empório da Música**, loja de instrumentos musicais em Campo Grande/MS.
A arquitetura está definida em [docs/adr/0001-agent-architecture.md](docs/adr/0001-agent-architecture.md). **Leia o ADR antes de propor mudanças estruturais**; se uma decisão precisar mudar, proponha um novo ADR em vez de desviar silenciosamente.

## Stack

- Python 3.12, gerenciado com **uv** (`pyproject.toml` + `uv.lock`)
- **LangGraph** (agente ReAct + nó de guardrail), LLM via **OpenRouter** (`langchain-openai` com `base_url`)
- **PostgreSQL 16 + pgvector + pg_trgm**, acessado só via `DATABASE_URL` (psycopg 3). Hospedagem: Supabase ou Postgres em VPS (Docker); `docker-compose.yml` local para desenvolvimento. Ver ADR 0001, seção 2.5.
- Embeddings locais multilíngues (fastembed / sentence-transformers)
- UI: **Chainlit**
- Histórico: LangGraph `PostgresSaver`
- Testes: **pytest** (unit, integration com testcontainers, e2e com LLM real) + evals

## Princípios de implementação

- **Python é a linguagem principal** (requisito do projeto). Não introduzir frontend em JS.
- **Idioma:** nomes de arquivos e pastas, código, identificadores, nomes de tools e mensagens de commit em **inglês** (`snake_case` para arquivos Python, `kebab-case` para docs). Conteúdo da documentação e textos voltados ao cliente (prompts, respostas) em **pt-BR**.
- **Banco agnóstico de provedor:** nada de SDK do Supabase; só SQL via `DATABASE_URL`. Tabelas no schema `emporio` (não em `public`).
- **Dados estruturados → tools com SQL parametrizado.** Nunca text-to-SQL livre; nunca concatenar input do usuário em SQL.
- **RAG apenas para o manual de políticas**, chunk por seção, com metadado da seção.
- **Cálculos (promoção, PIX 5%, parcelamento, frete) sempre no código**, nunca pelo LLM. Promoções não são cumulativas.
- **LGPD:** `get_order_status` exige `order_id` + e-mail ou telefone do cliente. Nunca expor dados de outro cliente.
- Data/hora atual injetada no system prompt (fuso `America/Campo_Grande`).
- Inconsistências dos dados e suposições ficam registradas no ADR 0001 (seção 3) e no README — ao encontrar uma nova, registrar.
- Manter simples: é um protótipo. Sem abstrações especulativas.

## Estrutura alvo

```
data/              CSVs e PDF de entrada (products.csv, ..., store_policies.pdf)
docs/              documentação e ADRs
src/emporio/       código da aplicação (agent/, tools/, db/, prompts/, domain/, rag/)
src/emporio/ingest/  pipeline de ingestão (uv run python -m emporio.ingest)
evals/             perguntas de teste e script de avaliação
examples/          3–5 conversas de exemplo (.md) — entregável obrigatório
tests/
  unit/            lógica pura, sem banco nem LLM
  integration/     tools/ingestão/retrieval contra Postgres em container
  e2e/             grafo completo com LLM real
```

## Testes

Estratégia completa no ADR 0001, seção 2.6.

| Comando | Camada | Requer |
|---|---|---|
| `uv run pytest` | unit (padrão; integration e e2e excluídos) | nada |
| `uv run pytest -m integration` | integration | Docker |
| `uv run pytest -m e2e` | e2e | Docker + `OPENROUTER_API_KEY` |

- Toda lógica nova (cálculo, regra de política, limpeza de dado) vem acompanhada de teste unitário.
- Toda tool nova ganha teste de integração.
- Integração e E2E **nunca** apontam para Supabase/VPS — sempre container efêmero.
- E2E verificam tools chamadas e fatos-chave, não o texto exato da resposta.

## Segurança

- **Nunca commitar credenciais.** `.env` fica no `.gitignore`; manter `.env.example` sem valores reais.
- Antes de sugerir `git add`, conferir que nenhum arquivo com segredos (`.env`, chaves, tokens) está incluído. Preferir adicionar arquivos explicitamente em vez de `git add .`.

## Plano de desenvolvimento

O trabalho segue [docs/development-plan.md](docs/development-plan.md), fase a fase.

- Antes de começar, identifique a fase atual pela coluna **Status** e trabalhe só nas entregas dela.
- Ao concluir uma fase, rode os itens de **Validação (gate)**, marque os que passaram e atualize o status (⬜ → 🟨 → ✅). Não avance de fase com gate pendente sem o usuário aprovar.
- Se algo do plano precisar mudar, atualize o plano no mesmo commit da mudança e explique o motivo.

## Fluxo de trabalho e commits

O histórico de commits deve refletir o **progresso real do desenvolvimento**. Por isso:

- **Ao final de cada etapa de trabalho, sempre apresente os comandos `git add` + `git commit`** prontos para o usuário executar. Não execute o commit — o usuário roda os comandos.
- Agrupe as mudanças em **commits pequenos e por escopo** — se a etapa tocou escopos diferentes, sugira commits separados.
- Mensagens **em inglês**, seguindo **Conventional Commits**:

```
<type>(<scope>): <short imperative summary, lowercase, no period>

[optional body: what and why]
```

**Types:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `style`

Testes usam o type `test` com o scope da área testada (ex.: `test(tools): add integration tests for get_order_status`). Se teste e implementação forem da mesma mudança pequena, podem ir no mesmo commit `feat`.

**Scopes do projeto:**

| Scope | Uso |
|---|---|
| `ingest` | pipeline de ingestão de CSV/PDF |
| `db` | schema, migrations, docker-compose do Postgres |
| `rag` | chunking, embeddings, retrieval de políticas |
| `tools` | tools do agente |
| `agent` | grafo LangGraph, guardrail, prompts, memória |
| `ui` | Chainlit |
| `evals` | conjunto de avaliação e scripts |
| `config` | settings, env, dependências |
| `docs` | README, ADRs, exemplos de conversa |

**Formato de entrega dos comandos** (PowerShell, um bloco por commit):

```powershell
git add docs/adr/0001-agent-architecture.md docs/README.md
git commit -m "docs(adr): add architecture decision record for support agent"
```

## Uso de assistente de IA

O README deve ter uma seção explicando o uso do Claude Code no projeto. Ao concluir etapas relevantes, anote em `docs/ai-workflow.md` (breve: o que foi pedido, o que foi gerado, o que foi revisado/ajustado manualmente).
