# Guia de contribuição

Como desenvolver no projeto. Para instalar e rodar, comece pelo [README](../README.md).

## Fluxo de trabalho

O desenvolvimento segue o [plano](development-plan.md), em fases. Cada fase tem entregas e um **gate de validação**: a próxima só começa quando os itens do gate passam e estão marcados no plano.

1. Veja a fase atual na coluna **Status** do plano.
2. Implemente as entregas da fase, com testes.
3. Rode os itens do gate e marque os que passaram; registre descobertas em **Notas da execução**.
4. Faça commits pequenos, um por escopo (ver [Commits](#commits)).

Decisões que mudam a arquitetura viram um novo ADR em [`adr/`](adr/), em vez de desviar do ADR atual sem registro.

## Padrões do código

| Tema | Regra |
|---|---|
| Idioma | Código, nomes de arquivos, tools e commits em inglês. Documentação, prompts e respostas ao cliente em pt-BR. |
| Banco | Só SQL parametrizado (`%s` / `psycopg.sql`); nunca concatenar texto do usuário em SQL. Nada de SDK de provedor: só `DATABASE_URL`. |
| Cálculos | Preço, PIX, parcelas e frete são calculados em `domain/pricing.py`. O LLM recebe os valores prontos e formatados. |
| Dados pessoais | Dados de clientes só com verificação de identidade (ver ADR 0001, LGPD). |
| Simplicidade | Protótipo: sem abstrações para casos que ainda não existem. |
| Lint | `uv run ruff check .` e `uv run ruff format .` antes de commitar. |

## Onde cada coisa fica

| Mudança | Arquivo(s) |
|---|---|
| Regra de preço, prazos de devolução, horário da loja | `src/emporio/domain/` |
| Consulta ao banco usada por uma tool | `src/emporio/tools/` |
| Memória de conversa | `src/emporio/agent/memory.py` |
| O que a interface web mostra de cada execução (tokens, tools, guardrail) | `src/emporio/ui/events.py` |
| Tela do chat: starters, rótulos das tools, mensagens de erro | `app.py` |
| Nome, idioma e recursos da interface | `.chainlit/config.toml` |
| Tool exposta ao LLM (descrição, formato do resultado) | `src/emporio/agent/tools.py` |
| Ligar uma tool ao agente | `build_agent` em `src/emporio/agent/graph.py` |
| Comportamento e tom do agente | `src/emporio/prompts/system.md` |
| O que o guardrail barra e como responde | `src/emporio/prompts/guardrail.md` (lógica em `agent/guardrail.py`) |
| Tabelas | `src/emporio/db/schema.sql` |
| Limpeza e validação dos CSVs | `src/emporio/ingest/cleaning.py` e `checks.py` |
| Chunking do manual | `src/emporio/ingest/policies.py` |
| Busca no manual | `src/emporio/rag/retriever.py` |

## Receitas

### Adicionar uma tool

1. **Consulta:** função em `src/emporio/tools/` que recebe uma conexão e devolve dataclasses (sem formatação para o LLM).
2. **Teste de integração** da consulta em `tests/integration/`, usando a fixture `loaded_conn`.
3. **Tool:** em `src/emporio/agent/tools.py`, uma função com `@tool(parse_docstring=True)`. A docstring vira a descrição que o LLM lê: diga quando usar e descreva cada argumento na seção `Args`. Formate valores para o cliente (ex.: `format_brl`) e devolva um `dict`. Erros esperados (ex.: categoria inexistente) voltam como `{"error": "..."}` para o agente se corrigir; exceções inesperadas são capturadas pelo grafo e viram uma mensagem de falha, sem quebrar a conversa salva.
4. **Teste unitário** do formato do resultado em `tests/unit/`.
5. **Registro:** inclua a tool na lista de `build_agent`.
6. **Prompt:** se o agente precisar de orientação sobre quando usar a tool, ajuste `system.md`.
7. **E2E:** um cenário em `tests/e2e/` verificando que a tool é chamada e os fatos-chave aparecem na resposta.
8. **Validação manual:** `uv run python -m emporio.cli -m "<pergunta>"` e confira a linha `[tool]`.
9. **Interface web:** adicione um rótulo amigável em `TOOL_LABELS` (`app.py`); sem ele, o passo aparece com o nome técnico da tool.

### Alterar a interface web

O grafo é síncrono (o `PostgresSaver` não tem API assíncrona) e o Chainlit é assíncrono. A ponte fica em `src/emporio/ui/events.py`: `turn_events` traduz o stream do LangGraph em eventos simples e `in_thread` o executa numa thread. O `app.py` só desenha esses eventos. Lógica nova de exibição vai em `events.py`, com teste em `tests/unit/test_ui_events.py`; o `app.py` deve continuar fino.

Para validar, rode `uv run chainlit run app.py` e teste no navegador; `--watch` recarrega ao salvar arquivos.

### Depurar no LangGraph Studio

`uv run langgraph dev` sobe o agente com o servidor de desenvolvimento do LangGraph (configurado em `langgraph.json`) e abre o Studio. Útil para ver por onde a conversa passou (guardrail → agente → tools), o estado em cada nó e repetir um passo. O servidor recarrega quando o código muda.

O grafo exportado (`src/emporio/agent/studio.py`) não usa o `PostgresSaver`: o servidor do LangGraph fornece a própria persistência. Se mudar a forma de montar o agente em `build_agent`, o Studio acompanha automaticamente.

### Alterar o prompt

O prompt fica em `src/emporio/prompts/system.md`, com campos entre chaves (`{phone}`, `{now_line}`, `{categories}`…) preenchidos por `prompts/system.py`. Para usar chaves literais no texto, escreva `{{` e `}}`. Depois de alterar:

```powershell
uv run pytest tests/unit/test_system_prompt.py
uv run python -m emporio.cli -m "<pergunta afetada pela mudança>"
uv run pytest -m e2e
```

Rode **todos** os E2E, não só os da área alterada: uma regra nova pode competir com outra (na Fase 6, a seção de reclamações fez o agente deixar de consultar a política de defeito).

### Alterar o guardrail

As categorias e o tom das recusas ficam em `src/emporio/prompts/guardrail.md`. Ao mudar, valide os dois lados nos E2E de `tests/e2e/test_guardrail_flows.py`: o que deve ser barrado e, igualmente importante, as mensagens legítimas que **não** podem ser barradas (ex.: "violão de 7 cordas" contém "cordas", mas é instrumento).

### Alterar o schema

`schema.sql` usa `CREATE TABLE IF NOT EXISTS`: tabelas novas são criadas na próxima ingestão, mas colunas novas em tabelas existentes não. Como todo o conteúdo vem da ingestão, recrie o banco local:

```powershell
docker compose down -v
docker compose up -d db
uv run python -m emporio.ingest
```

Os testes de integração sempre usam um banco novo, então não precisam disso.

### Alterar os dados de teste

- **CSVs:** `tests/fixtures/data/`. Cada linha existe para cobrir um caso (produto esgotado, promoção duplicada etc.); a docstring de `tests/integration/test_catalog.py` lista os produtos e o papel de cada um.
- **Manual de políticas:** `POLICY_PAGES` em `tests/conftest.py`, gerado como PDF a cada execução dos testes.

Ao mudar uma fixture, rode unit, integration e e2e: vários testes dependem das mesmas linhas.

### Testar o grafo sem LLM

`tests/fake_llm.py` tem um modelo roteirizado: devolve as mensagens na ordem dada, inclusive chamadas de tool (`tool_call(...)`). Serve para testar a montagem do grafo, tratamento de erros e memória sem custo nem variação (ex.: `tests/unit/test_graph_tool_errors.py`, `tests/integration/test_memory.py`).

## Testes

Camadas, comandos e fixtures: [testing.md](testing.md). Antes de abrir um commit de código:

```powershell
uv run pytest                       # unitários
uv run pytest -m integration        # quando mexer em SQL, ingestão ou retrieval
uv run pytest -m e2e                # quando mexer em prompt, tools ou grafo
```

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) em inglês: `<type>(<scope>): <resumo no imperativo, minúsculo, sem ponto>`.

| Type | Uso |
|---|---|
| `feat` / `fix` | Funcionalidade nova / correção |
| `test` | Só testes (com o scope da área testada) |
| `docs` | Documentação |
| `refactor` | Mudança de código sem mudar comportamento |
| `build` / `chore` | Dependências / tarefas de manutenção |

| Scope | Área |
|---|---|
| `ingest` | Pipeline de ingestão |
| `db` | Schema, conexão, docker-compose |
| `rag` | Embeddings e busca no manual |
| `tools` | Consultas e tools do agente |
| `agent` | Grafo, prompt, memória |
| `ui` | CLI e interface web |
| `evals` | Avaliação |
| `config` | Settings e dependências |

Exemplo:

```powershell
git add src/emporio/rag/retriever.py tests/unit/test_retriever_assembly.py
git commit -m "feat(rag): return full top-level sections from policy search"
```
