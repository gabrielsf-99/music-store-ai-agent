# Uso do Claude Code no projeto

Registro de como o assistente foi usado em cada etapa: o que foi pedido, o que ele gerou e o que mudou na revisão.

## Análise e arquitetura

- **Pedido:** análise técnica dos requisitos e dos dados, avaliação da stack proposta (LangGraph, OpenRouter, Postgres, pipeline de ingestão, React).
- **Gerado:** análise dos dados (volume, inconsistências), recomendação de RAG apenas para o manual de políticas e tools com SQL para dados estruturados, troca de React por Chainlit; ADR 0001 e `CLAUDE.md`.
- **Revisado/ajustado:** padronização de nomes de arquivos e código em inglês; inclusão da estratégia de testes em três camadas; banco agnóstico de provedor (Supabase ou VPS).

## Plano de desenvolvimento

- **Pedido:** plano incremental com validação por etapa.
- **Gerado:** `docs/development-plan.md` com 10 fases, cada uma com entregas, gate de validação e commits previstos.
- **Revisado/ajustado:** dados de entrada fora do repositório (só `data/README.md` com o formato); testes automatizados com fixtures sintéticas.

## Fase 0 — Fundação

- **Gerado:** `pyproject.toml` (uv), settings, `docker-compose.yml`, checagem de conexão.
- **Revisado/ajustado:** instalação do uv e do Docker Desktop; diagnóstico de conexão travando no Windows (`localhost` → IPv6), corrigido com `127.0.0.1` e timeout.

## Fase 1 — Schema e ingestão

- **Gerado:** schema SQL, pipeline de ingestão (limpeza, checagens, carga transacional), fixtures sintéticas, testes unitários e de integração com testcontainers.
- **Revisado/ajustado:** perfil dos dados reais revelou contagens erradas no ADR (65 produtos, 50 clientes) e e-mail compartilhado entre dois clientes — registrado como suposição nº 13.

## Fase 2 — Regras de preço e catálogo

- **Gerado:** regras de preço do manual como funções puras (promoção, PIX, parcelamento por faixa, frete), consultas de catálogo com busca fuzzy, testes unitários com casos do manual e testes de integração com fixtures.
- **Revisado/ajustado:** um teste que não provava o que dizia (parcelamento com promoção) foi reescrito com um caso em que a promoção muda o resultado; limitação das alternativas sugeridas registrada no plano.

## Fase 3 — Agente mínimo

- **Gerado:** prompt de sistema (persona, dados da loja, horário com aberto/fechado), tools LangChain com valores já formatados, grafo LangGraph, CLI com modo roteirizado, testes E2E.
- **Revisado/ajustado:** diagnóstico do erro 401 do OpenRouter isolando LangChain com chamada direta (problema era da conta); a validação manual pela CLI revelou que a busca cortava resultados sem avisar o agente — corrigido com `total_found`/`shown`.

## Fase 4 — RAG do manual de políticas

- **Gerado:** extração do PDF (modo layout do pypdf), chunking por seção numerada com validação de sequência, embeddings locais com fastembed, retriever, tool `search_policies`, PDF sintético para testes.
- **Revisado/ajustado:** a estratégia de retrieval foi decidida por medição, não por suposição — 14 perguntas reais comparando busca vetorial (11/14 no top-3), full-text, híbrida e híbrida com seção completa (13/14). A extração padrão do pypdf quebrava cada palavra em uma linha; trocada pelo modo layout após inspeção.

## Fase 5 — Pedidos, LGPD e memória

- **Gerado:** prazos de devolução/troca/garantia, consulta de pedido com verificação de identidade, memória com `PostgresSaver`, retomada de conversa na CLI, modelo de LLM roteirizado para testes.
- **Revisado/ajustado:** a validação manual revelou dois problemas que os testes não pegavam: (1) uma exceção em tool corrompia permanentemente a conversa salva — resolvido tratando erros no `ToolNode`; (2) o LLM recusava um pedido já verificado por desconfiar de um contato errado anterior — resolvido deixando explícito no prompt que a ferramenta decide a verificação. A falta de limite de tentativas foi registrada como limitação.

## Fase 6 — Guardrail e refinamento do prompt

- **Gerado:** guardrail de escopo com saída estruturada, prompt do classificador, seções de reclamações e segurança no prompt do agente, testes de bloqueio e de falsos positivos.
- **Revisado/ajustado:** classificador avaliado isoladamente antes de entrar no grafo (10/10, e `reasoning_effort="low"` escolhido por medir 2,8 s contra 4,0 s com a mesma precisão); latência total medida com e sem guardrail (+2,7 s na mediana) e registrada no ADR; a regressão E2E revelou que a nova seção de reclamações atrapalhava perguntas de defeito — corrigido e repetido 3 vezes para confirmar estabilidade.
