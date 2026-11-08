# Empório da Música — Agente de atendimento

Assistente virtual da **Empório da Música**, loja de instrumentos musicais em Campo Grande/MS. Ele conversa com clientes por texto e responde sobre:

- **Catálogo:** produtos, preços, disponibilidade, PIX, parcelamento e promoções, consultando o banco de dados.
- **Políticas da loja:** trocas, devoluções, garantia, frete, pagamento, consultando o manual de políticas (RAG).
- **Informações gerais:** endereço, contatos e horário de funcionamento, incluindo se a loja está aberta agora.
- **Pedidos:** status, itens, rastreio e prazos de devolução/troca/garantia, após confirmar o e-mail ou telefone do cliente.

Dá para conversar pelo navegador (Chainlit) ou pelo terminal. As conversas ficam salvas no Postgres.

## Como funciona

```
Cliente ──► Guardrail de escopo ──(fora do escopo: responde sem tools)
               │
               ▼
            Agente (LangGraph + LLM via OpenRouter) ──► histórico da conversa no Postgres
               ├── tools de catálogo ──► Postgres (SQL parametrizado, busca fuzzy)
               ├── tool de políticas  ──► Postgres + pgvector (busca híbrida no manual)
               └── tool de pedidos    ──► Postgres (só com e-mail ou telefone do cliente)
```

O guardrail barra pedidos de acessórios (a loja só vende instrumentos), assuntos fora da loja e tentativas de manipulação. Preços, PIX e parcelas são calculados no código, não pelo LLM. Decisões e justificativas: [ADR 0001](docs/adr/0001-agent-architecture.md).

## Requisitos

| Ferramenta | Para quê |
|---|---|
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Gerencia Python 3.12 e as dependências (baixa o Python sozinho). |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Banco Postgres local e testes de integração. |
| Conta no [OpenRouter](https://openrouter.ai/) | Chave de API para o LLM. |
| Arquivos de dados | 6 CSVs e o manual em PDF, no formato descrito em [data/README.md](data/README.md). |

## Primeiros passos

### 1. Instalar as dependências

```powershell
git clone https://github.com/gabrielsf-99/music-store-ai-agent.git
cd music-store-ai-agent
uv sync
```

### 2. Configurar o `.env`

```powershell
Copy-Item .env.example .env      # Linux/macOS: cp .env.example .env
```

| Variável | O que colocar |
|---|---|
| `OPENROUTER_API_KEY` | Sua chave do OpenRouter. |
| `LLM_MODEL` | Modelo do OpenRouter com suporte a tools. O `.env.example` já traz o padrão, `anthropic/claude-haiku-5.5` (ver [Escolha do modelo](#escolha-do-modelo)). |
| `POSTGRES_PASSWORD` | Uma senha para o banco local. |
| `DATABASE_URL` | A mesma senha no lugar de `change-me`. Mantenha `127.0.0.1` (com `localhost`, cada conexão atrasa ~5 s no Windows). |

As demais variáveis já vêm com valores padrão.

### 3. Colocar os dados em `data/`

Copie os arquivos `categories.csv`, `products.csv`, `promotions.csv`, `customers.csv`, `orders.csv`, `order_items.csv` e `store_policies.pdf` para a pasta `data/`. Não é preciso renomear: o manual também é aceito como `políticas_da_loja.pdf` e os CSVs com prefixo no nome (ex.: `planilha - orders.csv`).

### 4. Subir o banco e carregar os dados

```powershell
docker compose up -d db
uv run python -m emporio.ingest
```

A ingestão valida os dados, mostra avisos de inconsistência e carrega tudo em uma transação. Na primeira vez, baixa o modelo de embeddings (~0,22 GB, em `.cache/fastembed`). Pode ser executada de novo a qualquer momento: substitui o conteúdo anterior.

### 5. Conversar com o agente

```powershell
uv run chainlit run app.py          # navegador, em http://localhost:8000
uv run python -m emporio.cli        # ou pelo terminal
```

## Usando o agente pelo terminal

### Modo interativo

```powershell
uv run python -m emporio.cli
```

Digite as mensagens e `sair` para encerrar. Cada ferramenta consultada aparece antes da resposta:

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

### Modo roteirizado

Envia mensagens em sequência, na mesma conversa, sem interação. Útil para testar cenários:

```powershell
uv run python -m emporio.cli -m "Quais violões vocês têm até R$ 1000?" -m "E o Giannini GF-3D, tem?"
```

### Retomar uma conversa

Toda conversa fica salva no Postgres com um id, mostrado no início da sessão. Para continuar de onde parou, mesmo depois de fechar o terminal:

```powershell
uv run python -m emporio.cli --thread cli-3f2a...
```

### Perguntas para experimentar

| Tipo | Exemplo |
|---|---|
| Preço | "Quanto custa o Takamine GD20?" |
| Catálogo | "Quais violões vocês têm até R$ 1000?" |
| Produto esgotado | "Tem o Giannini GF-3D?" |
| Promoções | "Tem alguma promoção rolando?" |
| Política | "Me arrependi da compra, posso devolver?" |
| Garantia | "Qual a garantia dos instrumentos?" |
| Pedido | "Quero saber do meu pedido 1" → o agente pede o e-mail ou telefone da compra |
| Devolução de um pedido | Depois de consultar o pedido: "Posso devolver?" |
| Acessório | "Vocês vendem encordoamento?" |
| Fora do escopo | "Quem ganhou o jogo ontem?" |
| Reclamação | "Meu ukulele chegou riscado, estou chateado" |

Os dados de clientes e pedidos para testar estão em `data/customers.csv` e `data/orders.csv`.

## Usando o agente pelo navegador

```powershell
uv run chainlit run app.py
```

Abre em http://localhost:8000. Para não abrir o navegador automaticamente, use `--headless`; para outra porta, `--port 8080`.

- **Sugestões iniciais:** botões com perguntas de exemplo (violões, promoções, trocas, pedido).
- **Ferramentas visíveis:** cada consulta do agente aparece como um passo recolhível acima da resposta ("Buscando no catálogo", "Consultando o pedido"…), com a entrada e o resultado.
- **Uma conversa por aba:** cada aba ou "Nova conversa" começa um atendimento novo, salvo no Postgres com id `web-<sessão>`.
- **Readme:** o botão de informações mostra o `chainlit.md` com o que o assistente sabe fazer.

A configuração da interface fica em `.chainlit/config.toml` (nome, idioma, exibição dos passos). Upload de arquivos e edição de mensagens estão desligados: o agente não lê arquivos, e editar uma mensagem duplicaria o turno no histórico salvo.

A resposta aparece aos poucos, conforme o modelo gera o texto. Alguns modelos (ex.: `openai/gpt-6-luna-pro`) entregam a resposta de uma vez; com eles, ela aparece inteira no final.

## Inspecionando o agente no LangGraph Studio

Para ver o grafo e depurar conversas passo a passo (estado de cada nó, chamadas de tool, decisão do guardrail):

```powershell
uv run langgraph dev
```

O servidor sobe em http://127.0.0.1:2024 e abre o Studio no navegador (`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`). Use `--no-browser` para não abrir automaticamente. A configuração está em `langgraph.json`, que aponta para o grafo `emporio` em `src/emporio/agent/studio.py`.

É o mesmo agente da CLI e da interface web (guardrail, tools, banco e LLM reais), com uma diferença: as conversas ficam na persistência do próprio servidor de desenvolvimento (pasta `.langgraph_api/`), não no Postgres.

## Escolha do modelo

O modelo padrão foi escolhido medindo, não por preferência: `uv run python -m evals.run` roda 21 casos de avaliação (catálogo, loja, políticas, pedidos, fora do escopo) contra os dados reais e mede se o agente usa a ferramenta certa, se a resposta traz os fatos esperados, a latência e o custo. Resultado da rodada final ([relatório](evals/reports/2026-11-08-0927-comparison.md)):

| Modelo | Casos ok | Latência mediana / p95 | Custo por conversa | Resposta em partes |
|---|---|---|---|---|
| **`anthropic/claude-haiku-5.5`** (padrão) | 21/21 | 4,4 s / 6,0 s | US$ 0,0010 | sim |
| `deepseek/deepseek-v4-flash` | 21/21 | 6,2 s / 16,8 s | US$ 0,0006 | sim |
| `openai/gpt-6-luna-pro` | 21/21 | 11,9 s / 16,9 s | US$ 0,0019 | não |

Com os três empatados em acerto, o Haiku venceu por ser o mais rápido e o mais estável, e foi o único que passou em todos os testes E2E: o DeepSeek, mais barato, às vezes pulava consultas obrigatórias ao catálogo. Para trocar de modelo, mude `LLM_MODEL` no `.env` e rode os evals. Como avaliar: [docs/testing.md](docs/testing.md#avaliação-evals).

## Comandos úteis

| Comando | Para quê |
|---|---|
| `uv run python -m emporio.db` | Testa a conexão com o banco. |
| `uv run python -m emporio.ingest --data-dir <pasta>` | Ingestão a partir de outra pasta. |
| `docker compose down` | Para o banco (os dados ficam no volume). |
| `docker compose down -v` | Para o banco e apaga os dados. |
| `uv run pytest` | Testes unitários. Guia completo em [docs/testing.md](docs/testing.md). |
| `uv run python -m evals.run` | Avaliação do agente (qualidade, latência e custo); consome tokens. |

## Problemas comuns

| Sintoma | Causa e solução |
|---|---|
| `uv` ou `docker` não reconhecido | O terminal foi aberto antes da instalação. Abra um terminal novo. |
| Conexão com o banco demora ~5 s | `DATABASE_URL` com `localhost`. Troque por `127.0.0.1`. |
| `missing input files in data` | Faltam arquivos em `data/`; a mensagem lista quais. |
| `401` ao conversar | Chave do OpenRouter inválida ou conta sem acesso. Gere uma nova chave no painel. |
| Erro de coluna em `policy_chunks` na ingestão | Banco criado com um schema anterior. Rode `docker compose down -v` e repita o passo 4. |
| Agente responde "não foi possível consultar agora" | Uma tool falhou; o erro completo aparece no terminal. Causa comum: banco sem dados (`relation ... does not exist`) — rode a ingestão. |
| `address already in use` ao subir a interface web | A porta 8000 está ocupada. Use `uv run chainlit run app.py --port 8080`. |
| Studio mostra "Failed to fetch" | O navegador bloqueia o acesso de `smith.langchain.com` ao servidor local. No cadeado da URL → Configurações do site → **Acesso à rede local** → Permitir (no Brave, desative o Shields para o site). |

## Estrutura do projeto

```
data/                 dados de entrada (formato em data/README.md)
docs/                 ADRs, plano, guias de testes e de contribuição
src/emporio/
  agent/              grafo LangGraph, guardrail, tools expostas ao LLM e memória
  db/                 conexão, pool e schema SQL
  domain/             regras de negócio (preços, prazos de devolução, horário da loja)
  ingest/             pipeline de ingestão (CSVs e PDF)
  prompts/            prompts do agente e do guardrail
  rag/                embeddings e busca no manual de políticas
  tools/              consultas ao catálogo e a pedidos
  ui/                 eventos da conversa para a interface web
  cli.py              chat no terminal
app.py                interface web (Chainlit)
langgraph.json        configuração do `langgraph dev` / LangGraph Studio
chainlit.md           texto de apresentação da interface web
.chainlit/            configuração do Chainlit
evals/                casos de avaliação, script e relatórios
tests/                unit, integration e e2e
```

## Documentação

- [Guia de contribuição](docs/contributing.md): fluxo de desenvolvimento, padrões e como estender o agente.
- [Testes](docs/testing.md): camadas, comandos e fixtures.
- [Plano de desenvolvimento](docs/development-plan.md): fases e critérios de validação.
- [ADR 0001](docs/adr/0001-agent-architecture.md): arquitetura, decisões e suposições sobre os dados.
- [Uso do Claude Code](docs/ai-workflow.md): como o assistente de IA foi usado no projeto.
