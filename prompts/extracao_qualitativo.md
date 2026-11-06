# Extração qualitativa — CASE-03

Você é um analista de research. Leia somente as páginas candidatas da apresentação institucional indicada abaixo e produza temas verificáveis para os slides de perfil, setor e riscos. Não copie trechos longos e não invente fatos.

## Temas

Escolha de 5 a 8 temas realmente sustentados pelo documento, incluindo obrigatoriamente `perfil`, `capacidade_footprint`, `mercados_produtos`, `estrategia` e pelo menos um entre `riscos` e `guidance_perspectivas`. Quando houver evidência, prefira também `capex_investimentos`, `esg` e `destaques_trimestre`.

## Saída obrigatória

Responda somente com uma lista JSON válida, sem markdown:

```json
[
  {
    "chave": "qualitativo",
    "metrica": "estrategia",
    "tema": "estrategia",
    "empresa": "gerdau",
    "documento": "apresentacao",
    "resumo": "síntese em palavras nossas, com no máximo 30 palavras",
    "pagina": 1,
    "trecho": "trecho literal curto, com no máximo 25 palavras"
  }
]
```

Regras:

- `pagina` é o índice do `pagina_NN.txt`, a partir de 1, não o número impresso no slide.
- `resumo` é paráfrase própria, objetiva e com no máximo 30 palavras; não copie frases do documento.
- `trecho` é somente uma âncora literal curta para auditoria, preservada exatamente como aparece na página. Não inclua um parágrafo inteiro.
- Não use páginas sem texto e não use números que você não consiga localizar literalmente.
- Se o documento misturar release e apresentação institucional, mantenha `documento: "apresentacao"` porque o arquivo-fonte é a apresentação; registre a seção em `obs` apenas se necessário.
- Não transforme o resumo em recomendação de investimento. Descreva perfil, estratégia, riscos e perspectivas com linguagem neutra.
- Não crie tema só porque ele aparece na lista: cada item precisa de uma página e uma evidência literal.

## Entrada

Empresa: `<slug>`  
Documento: `apresentacao`  
Pasta de texto: `<pasta_saida>`  
Páginas candidatas: `<cole aqui o ranking do localizar_paginas.py>`
