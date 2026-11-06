# ADR 0001 — Arquitetura do agente de atendimento da Empório da Música

- **Status:** Aceito
- **Data:** 2026-11-05

## 1. Contexto

A Empório da Música (loja de instrumentos musicais em Campo Grande/MS) precisa de um
agente de atendimento por texto que:

1. Assuma uma persona alinhada ao tom da loja ("informal mas profissional, como um amigo que entende de música").
2. Responda com base no contexto disponibilizado.
3. Saiba **quando consultar dados** (preço, estoque, status de pedido) e **quando consultar políticas** (trocas, horários, pagamento).
4. Lide adequadamente com perguntas fora do escopo (inclusive acessórios, que a loja não vende).

Restrição obrigatória: **Python como linguagem principal**.

### Fontes de dados

| Fonte | Volume | Natureza |
|---|---|---|
| `products.csv` | 64 linhas | Estruturado (preço, estoque, status, specs em JSON) |
| `categories.csv` | 9 linhas | Estruturado |
| `orders.csv` / `order_items.csv` | 20 / 22 linhas | Estruturado |
| `promotions.csv` | 25 linhas (4 ativas) | Estruturado |
| `customers.csv` | 49 linhas | Estruturado, **dados pessoais (LGPD)** |
| `store_policies.pdf` | 8 páginas (~3–4k tokens) | Texto não estruturado, organizado em seções numeradas |

## 2. Decisão

Agente **híbrido**: **function calling com tools tipadas** sobre dados estruturados (SQL) e
**RAG** apenas sobre o manual de políticas, orquestrado por **LangGraph**.

### 2.1 Visão geral

```
emporio.ingest (Python, idempotente)
  CSV → validação/limpeza → Postgres (tabelas relacionais, specs → jsonb)
  PDF → extração → chunk por seção → embeddings → pgvector

app (Chainlit)
  └─ LangGraph
       [scope guardrail] → [agente ReAct + tools] → resposta
       tools: search_products | get_product_details | get_order_status
              | list_active_promotions | search_policies
       memória: PostgresSaver (thread_id por conversa)

Postgres (DATABASE_URL) → Supabase | Postgres em VPS (Docker) | docker-compose local
tests/  → unit | integration | e2e
evals/  → conjunto de perguntas com comportamento esperado + relatório de acurácia
```

### 2.2 Decisões por componente

| Decisão | Escolha | Justificativa | Alternativas consideradas |
|---|---|---|---|
| Orquestração | **LangGraph** | Grafo explícito permite um nó de guardrail antes do agente, checkpointer nativo para histórico e fácil inspeção de passos. | LangChain AgentExecutor (menos controle); loop manual de tool calling (mais código de infraestrutura). |
| Padrão do agente | **ReAct com tools tipadas** | O LLM decide *qual* fonte consultar — é exatamente o requisito central do agente. | Roteador fixo por classificação (rígido para perguntas mistas, ex.: "o Takamine GD20 tem desconto no PIX?"). |
| Acesso a dados estruturados | **Tools com SQL parametrizado** | Segurança (sem SQL livre sobre `customers`), previsibilidade, testabilidade. | Agente text-to-SQL: flexível, mas arrisca vazamento de dados pessoais e queries incorretas. |
| Retrieval de políticas | **RAG com chunk por seção** (4.1, 4.2, 5.1…) | Seções do manual já são unidades semânticas; metadado `section` permite citar a fonte. Escala se o manual crescer. | Manual inteiro no system prompt: viável pelo tamanho (~4k tokens) e mais simples; descartado para manter retrieval rastreável e escalável — registrado como alternativa válida. Chunk de tamanho fixo: quebra regras no meio. |
| Busca de produtos por nome | **`pg_trgm` (similaridade fuzzy)** | Clientes escrevem "GD20", "takamine gd 20". Catálogo de 64 itens não justifica embeddings. | Embeddings no catálogo (overkill); `ILIKE` (frágil). |
| Banco | **PostgreSQL 16 + pgvector + pg_trgm**, hospedagem agnóstica (ver 2.5) | Um único banco para relacional, vetores e histórico de conversa. | SQLite + Chroma/FAISS (setup zero, porém três mecanismos de persistência distintos). |
| LLM | **OpenRouter** (via `langchain-openai` com `base_url`), modelo configurável por `LLM_MODEL` | Troca de modelo sem mudar código; permite comparar modelos nos evals. Requisito: tool calling confiável. | API direta de um provedor (acoplamento). |
| Embeddings | **Modelo local multilíngue** (`fastembed` / sentence-transformers, ex.: `paraphrase-multilingual-MiniLM-L12-v2`) | Sem custo, sem segunda API key, determinístico, bom em pt-BR. Volume minúsculo (~20 chunks). | Embeddings via API (confirmar suporte no OpenRouter; adiciona dependência externa). |
| Interface | **Chainlit** | Python puro (respeita a restrição), UI de chat pronta, exibe chamadas de tools/etapas — torna o raciocínio do agente visível para a equipe. | React + FastAPI (adiciona base JS e tempo sem ganho funcional para o protótipo); Streamlit (menos adequado a chat com steps); CLI (menos demonstrável). |
| Histórico | **LangGraph `PostgresSaver`**, `thread_id` por sessão | Contexto multi-turno (ex.: cliente informa nº do pedido e depois pergunta sobre devolução). | Memória em processo (perde ao reiniciar). |
| Cálculos de preço | **Determinísticos no código** (promoção, PIX 5%, parcelamento, frete) | O manual proíbe informar preços sem consultar o sistema; LLM erra aritmética. | Deixar o LLM calcular (não confiável). |
| Gerenciador de pacotes | **uv** + `pyproject.toml` | Rápido, lockfile reprodutível. | pip + requirements.txt. |
| Ingestão | **Script Python idempotente** (`python -m emporio.ingest`), dentro do pacote da aplicação | Volume pequeno; foco em validação e limpeza, não em orquestração. Um único pacote instalável compartilha config e conexão com o app. | Airflow/Prefect (overkill). |
| Testes | **pytest em três camadas** (unit, integration, e2e) + evals (ver 2.6) | Cada camada cobre um tipo de risco diferente com custo proporcional. | Apenas evals (não isola falhas de lógica); apenas unitários (não cobre SQL nem comportamento do LLM). |
| Idioma | **Inglês** para nomes de arquivos, código, tools e commits; **pt-BR** para documentação e textos voltados ao cliente | Padrão de mercado para código; atendimento é em português. | Tudo em português (mistura com APIs/bibliotecas em inglês). |

### 2.3 Tools do agente

| Tool | Entrada | Regras |
|---|---|---|
| `search_products` | `query?`, `category?`, `max_price?`, `min_price?`, `only_available=True` | Retorna preço de tabela, preço promocional (se houver promoção ativa), estoque, status. |
| `get_product_details` | `name_or_id` | Busca fuzzy; retorna specs, preço, promoção, opções de pagamento calculadas. Sugere alternativas se esgotado/descontinuado. |
| `get_order_status` | `order_id`, `email_or_phone` | **Exige verificação de identidade** (LGPD). Nunca expõe dados de outro cliente. |
| `list_active_promotions` | `category?` | Somente `is_active = 1`; sempre mostra preço original + % (seção 6.2 do manual). |
| `search_policies` | `question` | Top-k chunks do manual com metadado de seção. |

As descrições das tools (lidas pelo LLM) podem ser em português para melhorar o roteamento em conversas pt-BR.

### 2.4 Estratégia de prompt

- **System prompt** com: persona e tom (seção 7.1 do manual), escopo (só instrumentos; redirecionar acessórios), **data e hora atuais** (horário de funcionamento e prazos de troca dependem disso), dados fixos da loja (nome, endereço, horários), regras de não inventar preço/estoque/prazo.
- **Scope guardrail** antes do agente: classifica mensagens claramente fora do domínio e responde com redirecionamento cordial sem acionar tools.
- Respostas citam a seção do manual quando aplicam uma política.

### 2.5 Hospedagem do banco

O código depende **apenas de `DATABASE_URL`** (psycopg 3). Nenhum SDK de provedor é usado — o banco é tratado como Postgres puro, o que permite trocar de hospedagem sem alterar código.

| Ambiente | Hospedagem | Observações |
|---|---|---|
| Desenvolvimento local / quem clonar o repositório | `docker-compose.yml` com imagem `pgvector/pgvector:pg16` | Um comando para subir; não depende de conta externa. |
| Testes de integração | Container efêmero (testcontainers, mesma imagem) | **Nunca** rodar testes contra banco remoto. |
| Ambiente hospedado | **Supabase** ou **Postgres próprio em VPS (Docker)** — decisão em aberto, sem impacto no código | Ver cuidados abaixo. |

Requisitos do banco: extensões `vector` e `pg_trgm` (criadas pelo schema com `CREATE EXTENSION IF NOT EXISTS`).

**Cuidados com Supabase:**
- Usar um **schema dedicado (`emporio`)** em vez de `public`: tabelas em `public` são expostas pela Data API (PostgREST) e `customers` contém dados pessoais. Alternativa: habilitar RLS sem policies.
- Usar conexão direta ou **session pooler (porta 5432)**. O transaction pooler (porta 6543) não suporta prepared statements, usados pelo psycopg 3 / `PostgresSaver`. Verificar suporte a IPv4 da conexão escolhida.

**Cuidados com VPS:**
- Usar a imagem `pgvector/pgvector:pg16` (pg_trgm já vem incluído no contrib).
- Não expor a porta 5432 publicamente sem restrição de IP/firewall e TLS; usuário dedicado com privilégios mínimos para a aplicação.

### 2.6 Estratégia de testes

| Camada | Pasta / marcador | O que cobre | Dependências | Quando roda |
|---|---|---|---|---|
| **Unit** | `tests/unit/` | Lógica pura: cálculo de preço (promoção, PIX, parcelamento, frete), regras de elegibilidade de troca/devolução, limpeza e validação dos CSVs, chunking do PDF por seção, montagem do system prompt. LLM e banco mockados. | Nenhuma | Sempre (`uv run pytest`) |
| **Integration** | `tests/integration/` · `@pytest.mark.integration` | Tools executando SQL real; idempotência da ingestão; busca fuzzy (`pg_trgm`); retrieval retorna a seção esperada para perguntas conhecidas; persistência do `PostgresSaver`; verificação de identidade em `get_order_status`. | Docker (testcontainers + `pgvector/pgvector:pg16`) | `uv run pytest -m integration` |
| **E2E** | `tests/e2e/` · `@pytest.mark.e2e` | Grafo completo com LLM real via OpenRouter, cenários de conversa: consulta de preço, catálogo com filtro, status de pedido com e sem verificação, devolução fora do prazo, acessório fora do escopo, pergunta fora do domínio, conversa multi-turno. Asserções sobre **tools chamadas e fatos-chave** (ex.: preço correto), não sobre o texto exato. | Docker + `OPENROUTER_API_KEY` | `uv run pytest -m e2e` (opt-in; consome tokens) |
| **Evals** | `evals/` | Conjunto maior de perguntas com comportamento esperado; gera relatório de acurácia de roteamento (tool correta) e de fatos. Serve para comparar modelos/prompts. | Igual ao E2E | `uv run python -m evals` |

Diferença entre E2E e evals: E2E é **regressão pass/fail** com poucos cenários críticos; evals **medem qualidade** em um conjunto maior e produzem métricas.

Os testes unitários e de integração não fazem chamadas ao LLM, então são determinísticos e gratuitos. Os E2E são não determinísticos por natureza; as asserções focam em comportamento verificável para reduzir flakiness.

## 3. Suposições e inconsistências dos dados

Documentadas aqui e replicadas no README.

| # | Inconsistência | Suposição adotada |
|---|---|---|
| 1 | WhatsApp: (67) 3341-4444 (seção 1.2) vs (67) 3321-4500 (seção 7) | Usar (67) 3341-4444 (capa + tabela de dados da empresa); registrar a divergência. |
| 2 | E-mail com acento na tabela (`empóriodamusica`) vs sem acento na capa | Usar `contato@emporiodamusica.com.br` (domínios não usam acento na prática). |
| 3 | Tabela de pagamento: "parcela mínima R$100" vs seção 3.1 com faixas (até 3x / 4–6x R$80 / 7–12x R$100) | Seção 3.1 prevalece (mais específica); até 3x com parcela mínima de R$50. |
| 4 | Pedido 3: 2 × R$1.749 = R$3.498, total registrado R$3.450; produto 130 está `coming_soon` | Total do pedido é fonte da verdade para o pedido; não recalcular. |
| 5 | Pedido 20: R$799 + R$689 = R$1.488, total registrado R$1.400 | Idem item 4; ingestão emite *warning*. |
| 6 | Produto 96 `active` com estoque 0; 113 e 136 `discontinued` | Disponível = `status = 'active' AND stock_quantity > 0`; aplicar seção 7.3 do manual. |
| 7 | Categorias 6, 7, 8 sem produtos | Informar que no momento não há itens disponíveis na categoria. |
| 8 | Não há data de recebimento real, só `estimated_delivery` | Usar `estimated_delivery` como proxy da data de recebimento para prazos de devolução. |
| 9 | Pedidos até mar/2026; data atual posterior | Agente usa a data real do sistema; pedidos entregues tendem a estar fora do prazo de arrependimento (7 dias) → oferecer garantia legal/fabricante. |
| 10 | Promoções múltiplas para o mesmo produto (96, 93, 99), todas inativas | Considerar apenas `is_active = 1`; se houver mais de uma ativa, aplicar a de maior desconto (não cumulativas). |
| 11 | Pagamentos em `orders` usam códigos (`credit_6x`, `pix`) | Normalizar para rótulos legíveis na ingestão. |
| 12 | Arquivos de entrada com prefixo longo, espaços e nomes em português (ex.: `políticas_da_loja.pdf`) | A pipeline espera os nomes `products.csv`, …, `store_policies.pdf` em `data/` (ver `data/README.md`). |

## 4. Consequências

**Positivas**
- Separação clara entre dados exatos (SQL) e conhecimento textual (RAG) — atende diretamente ao requisito "saber quando consultar dados vs políticas".
- Baixo risco de alucinação de preços e vazamento de dados pessoais.
- Banco portável entre Supabase, VPS e local apenas trocando `DATABASE_URL`.
- Testes em camadas: falhas de lógica, de SQL e de comportamento do agente são detectadas separadamente.
- Raciocínio do agente visível na UI.

**Negativas / riscos**
- Testes de integração e E2E exigem Docker (mitigado: unitários rodam sem nada).- E2E consomem tokens e podem oscilar (mitigado: opt-in e asserções sobre comportamento, não texto).
- RAG sobre 8 páginas é discutivelmente excessivo (mitigado pela justificativa de escalabilidade e rastreabilidade).
- Modelo de embeddings local adiciona download na primeira execução.
- Guardrail extra adiciona uma chamada de LLM por mensagem (pode ser substituído por instrução no prompt se a latência for problema).

## 5. Fora de escopo (possível evolução)

- Canal WhatsApp real, autenticação de cliente, registro efetivo de reclamações, cálculo real de frete por CEP, observabilidade (LangSmith/Langfuse), reranking, avaliação automatizada com LLM-as-judge, CI rodando unit + integration a cada push.
