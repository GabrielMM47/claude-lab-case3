---
name: bcb-sgs
description: Busca séries temporais do Banco Central do Brasil (SGS) como IPCA, Selic, câmbio e IBC-Br e salva em CSV. Use sempre que o usuário pedir dados macroeconômicos brasileiros do Banco Central, mesmo sem citar o SGS.
---

# Séries do Banco Central (SGS)

## Quando usar
Pedidos de dados macro brasileiros: inflação, juros, câmbio, atividade. Ex.: "pega o IPCA desde 2023", "qual a Selic hoje".

## Como fazer
1. Identifique o código da série na tabela abaixo. Se não estiver aqui, diga ao usuário e sugira consultar o SGS (www3.bcb.gov.br/sgspub) em vez de adivinhar o código.
2. Rode o script, nunca digite números de memória:
   ```bash
   python scripts/sgs.py <codigo> --inicio AAAA-MM-DD --saida <arquivo.csv>
   ```
3. Confira o resultado antes de responder: a última data é recente? Há valores vazios?
4. Na resposta, cite sempre **"Fonte: Banco Central do Brasil, SGS, série <código>, dados até <data>"**.

## Códigos mais usados
| Série | Código | Unidade |
|---|---|---|
| IPCA — variação mensal | 433 | % no mês |
| IPCA — acumulado 12 meses | 13522 | % |
| Selic meta | 432 | % a.a. |
| Dólar PTAX venda | 1 | R$/US$ |
| IBC-Br | 24363 | índice |

## Cuidados
- Variação mensal se **compõe**, não se soma.
- Séries diárias aceitam no máximo 10 anos por consulta.
