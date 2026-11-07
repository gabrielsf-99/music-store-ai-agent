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
