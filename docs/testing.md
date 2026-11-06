# Testes

Estratégia e motivação das camadas: [ADR 0001, seção 2.6](adr/0001-agent-architecture.md#26-estratégia-de-testes).

## Pré-requisitos

- [uv](https://docs.astral.sh/uv/) instalado (`uv sync` cria o ambiente e instala as dependências).
- Docker Desktop aberto, apenas para testes de integração e E2E.

## Comandos

Rodar na raiz do projeto.

| Comando | O que roda | Requer |
|---|---|---|
| `uv run pytest` | unitários | nada |
| `uv run pytest -m integration` | integração | Docker |
| `uv run pytest -m e2e` | E2E | Docker + `OPENROUTER_API_KEY` no `.env` |
| `uv run pytest -m "not e2e"` | unitários + integração | Docker |

Sem `-m`, integração e E2E ficam de fora (configurado em `addopts` no `pyproject.toml`).

### Opções úteis

```powershell
uv run pytest -v                                    # lista cada teste pelo nome
uv run pytest tests/unit/test_ingest_cleaning.py    # um arquivo
uv run pytest -k payment                            # testes com "payment" no nome
uv run pytest -x                                    # para no primeiro erro
```

### Lint

```powershell
uv run ruff check .
uv run ruff format --check .
```

## Como os testes funcionam

| Pasta | Camada | Detalhes |
|---|---|---|
| `tests/unit/` | Unitários | Lógica pura, sem banco nem LLM. |
| `tests/integration/` | Integração | Sobem um Postgres temporário (`pgvector/pgvector:pg16`) com testcontainers. Na primeira execução a imagem é baixada; depois leva cerca de 20 s. O container é removido ao final e não afeta o banco do `docker compose`. |
| `tests/e2e/` | E2E | Grafo completo do agente com LLM real (a partir da Fase 3). |
| `tests/fixtures/data/` | Fixtures | CSVs sintéticos usados pelos testes, com um caso de cada situação relevante (produto esgotado, descontinuado, `coming_soon`, promoções ativas duplicadas, e-mail compartilhado, total divergente). Os dados reais de `data/` não são usados. |

## Problemas comuns

- **`uv` ou `docker` não reconhecido:** o terminal foi aberto antes da instalação. Abra um terminal novo.
- **Integração falha ao conectar no Docker:** confira se o Docker Desktop está rodando (`docker info`).
