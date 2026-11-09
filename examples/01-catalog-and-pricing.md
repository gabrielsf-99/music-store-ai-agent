# Catálogo e preço

Busca por categoria e faixa de preço, produto esgotado com alternativas da mesma marca e cálculo de PIX e parcelamento feito no código.

Conversa real exportada da CLI (`uv run python -m emporio.cli -m ...`) com o modelo `anthropic/claude-haiku-5.5`, num domingo à noite (08/11/2026). Linhas em itálico mostram as tools chamadas e a decisão do guardrail.

---

**Cliente:** Quais violões vocês têm até R$ 1000?

*Tool: `search_products({"category": "Violões", "max_price": 1000})`*

**Empório:**

Temos 12 violões até R$ 1.000. Estes são os 10 primeiros, do mais barato ao mais caro:

1. **Tagima Memphis AC-39 Nylon Natural**: R$ 429,90 (PIX R$ 408,41)
2. **Rozini RC-104 Nylon Estudante**: R$ 459,90 (PIX R$ 436,91)
3. **Shelby SN-100 Folk Aço Preto**: R$ 549,00 (PIX R$ 521,55)
4. **Giannini GF-1R Aço Folk Sunburst**: R$ 579,90 (PIX R$ 550,91)
5. **Yamaha C40 Nylon Natural**: R$ 599,90 (PIX R$ 569,91)
6. **Giannini GN-15 Nylon Cedro Natural**: R$ 689,00 (PIX R$ 654,55)
7. **Yamaha F310 Aço Natural**: R$ 699,90 (PIX R$ 664,91)
8. **Tagima Dallas Tuner Aço Natural**: R$ 749,00 (PIX R$ 711,55)
9. **Shelby SGD-195E Elétrico Aço Sunburst**: R$ 799,00 (PIX R$ 759,05)
10. **Yamaha C70 Nylon Natural**: R$ 849,00 (PIX R$ 806,55)

No cartão, a maioria parcela em até 5x a 8x sem juros. No PIX, você ganha 5% de desconto.

Quer que eu filtre por nylon ou aço, ou por marca?

**Cliente:** E o Giannini GF-3D, tem?

*Tool: `search_products({"query": "Giannini GF-3D"})`*

**Empório:**

O **Giannini GF-3D Dreadnought Sunburst** está esgotado no momento.

Se quiser uma Giannini parecida, estas estão disponíveis:

- **Giannini GF-1R Aço Folk Sunburst**: R$ 579,90 (PIX R$ 550,91)
- **Giannini GN-15 Nylon Cedro Natural**: R$ 689,00 (PIX R$ 654,55)
- **Giannini GNF-3 CEQ Elétrico Nylon Natural**: R$ 1.049,00 (PIX R$ 996,55)
- **Giannini GWNE-7 7 Cordas Nylon Natural**: R$ 1.149,00 (PIX R$ 1.091,55)

Quer que eu veja os detalhes de alguma delas?

**Cliente:** Quanto fica o Takamine GD20 no PIX? E parcelado?

*Tool: `get_product_details({"product": "Takamine GD20"})`*

**Empório:**

O **Takamine GD20 Dreadnought Natural** está disponível:

- **No PIX:** R$ 2.089,05 (5% de desconto sobre R$ 2.199,00)
- **Parcelado:** até 12x de R$ 183,25 sem juros

Ele tem tampo de cedro sólido, fundo e laterais de sapele e braço de mogno. Ótimo para fingerstyle, com timbre quente e definido.

Quer saber mais sobre ele ou comparar com outro modelo?
