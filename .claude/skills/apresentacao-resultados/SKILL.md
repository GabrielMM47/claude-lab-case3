---
name: apresentacao-resultados
description: Use para transformar ITRs, apresentações institucionais e fatos verificados em uma análise comparativa de Gerdau e Usiminas, com rastreabilidade por página.
---

# Apresentação de resultados

## Quando usar

Use esta skill quando o pedido envolver extração, validação, comparação ou apresentação de resultados financeiros e operacionais de empresas listadas.

Ela se aplica especialmente a ITRs, apresentações institucionais, volumes, capacidade, receita por tonelada, EBITDA, mix e narrativa executiva.

## Fluxo recomendado

1. Leia `docs/CONTRATO_DADOS.md` e `CLAUDE.md`.
2. Confira os PDFs em `data/itrs/` e `data/apresentacoes/` e registre as fontes.
3. Extraia as páginas com `src/extrair_release.py`.
4. Use `src/localizar_paginas.py` para ranquear páginas por `operacional`, `qualitativo` e `ebitda`.
5. Para etapas assistidas, use os prompts de `prompts/` somente com páginas candidatas de um documento.
6. Grave cada fato com documento, página, trecho literal, unidade e escopo.
7. Rode `src/verificar_numeros.py` na pasta de texto correspondente. Corrija ou marque revisão manual; não ignore erro.
8. Rode `src/indicadores.py` somente depois que os fatos estiverem corrigidos.
9. Gere comparação, gráficos e apresentação apenas a partir dos JSONs verificados.
10. Antes da entrega, confira README, vídeo, artefato público e checklist.

Comandos de localização:

```bash
python src/localizar_paginas.py saida/<documento> --tema operacional --top 10
python src/localizar_paginas.py saida/<documento> --tema qualitativo --top 10
python src/localizar_paginas.py saida/<documento> --tema ebitda --top 10
```

Prompts principais:

- `prompts/extracao_financeira_complementar.md`;
- `prompts/extracao_operacional.md`;
- `prompts/extracao_qualitativo.md`.

## O que nunca fazer

- Não digite números de memória nem complete dado ausente por inferência.
- Não use holding, controladora ou DFs individuais quando o fato pedido é consolidado.
- Não misture R$ mil, R$ milhões, toneladas e milhões de toneladas.
- Não compare EBITDA contábil de uma empresa com EBITDA ajustado da outra.
- Não transforme volume de mineração em volume de aço.
- Não calcule R$/t quando receita e volume não pertencem ao mesmo escopo.
- Não use página sem texto extraído como evidência numérica.
- Não copie trechos longos; use resumo próprio e âncora literal curta.
- Não coloque no slide um número que não tenha fonte ou não esteja no comparativo verificado.

## Verificação mínima

Para cada número usado na narrativa ou no slide, confirme arquivo-fonte, página física do PDF, período, unidade, escopo, trecho literal, `valor_como_aparece` e resultado do verificador.

Se a automação não provar a coluna ou o escopo, registre `revisao_manual` com pessoa e nota. O slide de metodologia deve informar cobertura e limitações.
