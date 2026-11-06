# Documentação

## Plano de desenvolvimento

[development-plan.md](development-plan.md): fases incrementais, cada uma com entregas e critérios de validação.

## Testes

[testing.md](testing.md): como rodar os testes unitários, de integração e E2E.

## Architecture Decision Records (ADR)

Decisões arquiteturais relevantes ficam em [`adr/`](adr/), numeradas sequencialmente com nome em inglês (`NNNN-short-title.md`).
Um ADR aceito não é editado para mudar a decisão — cria-se um novo ADR que o substitui (status `Substituído por ADR NNNN`).

| ADR | Título | Status |
|---|---|---|
| [0001](adr/0001-agent-architecture.md) | Arquitetura do agente de atendimento | Aceito |

### Template

```markdown
# ADR NNNN — Título

- **Status:** Proposto | Aceito | Substituído por ADR NNNN
- **Data:** AAAA-MM-DD

## Contexto
## Decisão
## Alternativas consideradas
## Consequências
```
