# Pedido e devolução

Consulta de pedido só depois de confirmar o e-mail (LGPD), prazos de devolução calculados no código e política de garantia buscada no manual (RAG) no turno seguinte, usando o contexto da conversa.

Conversa real exportada da CLI (`uv run python -m emporio.cli -m ...`) com o modelo `anthropic/claude-haiku-5.5`, num domingo à noite (08/11/2026). Linhas em itálico mostram as tools chamadas e a decisão do guardrail.

---

**Cliente:** Quero saber do meu pedido 1

**Empório:**

Oi! Pra consultar o pedido 1, preciso de mais uma info: qual e-mail ou telefone (com DDD) você usou na hora da compra?

**Cliente:** pedro.oliveira@jmail.com

*Tool: `get_order_status({"order_id": 1, "email_or_phone": "pedro.oliveira@jmail.com"})`*

**Empório:**

Oi, Pedro! Encontrei o seu pedido 1:

- **Item:** 1x Martin D-28 Dreadnought Natural
- **Data do pedido:** 15/10/2025
- **Total:** R$ 11.499,00 (pago no PIX)
- **Status:** entregue
- **Previsão de entrega:** 25/10/2025
- **Código de rastreio:** BRAB1234567BR

Sobre os prazos:
- Arrependimento e troca por preferência: encerraram em 01/11/2025.
- Troca por defeito: encerrou em 14/11/2025.
- Garantia legal: encerrou em 23/01/2026.

Todos os prazos já passaram. Se o violão apresentar algum problema, fale com a equipe pelo WhatsApp (67) 3341-4444 para verificarmos a situação. Posso ajudar em mais alguma coisa?

**Cliente:** Posso devolver?

*Tool: `search_policies({"question": "Posso devolver um produto após o prazo de arrependimento, troca ou garantia? Quais as condições de devolução?"})`*

**Empório:**

Pelo que consta no seu pedido, a devolução por arrependimento e a troca por preferência já não são possíveis, porque o prazo terminou em 01/11/2025. A troca por defeito e a garantia legal também já venceram.

Pela nossa política, a devolução por arrependimento vale por 7 dias corridos após o recebimento, com o produto na embalagem original, sem sinais de uso e com todos os acessórios e manuais. Trocas por defeito de fabricação valem por 30 dias após a compra, e a garantia legal cobre defeitos por 90 dias após o recebimento.

Se o violão apresentar defeito, ainda pode valer a **garantia do fabricante** (Martin). Ela varia conforme o fabricante e está no certificado de garantia que veio com o instrumento. A loja pode intermediar esse processo se você pedir. Para isso, fale com a equipe pelo WhatsApp (67) 3341-4444. Nosso atendimento reabre amanhã, segunda-feira, 09/11, às 09:00.
