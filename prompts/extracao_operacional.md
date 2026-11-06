# Extração operacional — CASE-03

Você é um analista de dados. Receba somente as páginas candidatas listadas ao final deste prompt, vindas de `pagina_NN.txt` de um único documento-fonte. Extraia os fatos operacionais publicados; não preencha lacunas com memória, cálculo ou inferência.

## Escopo

Procure, quando publicados: `volume_vendas` (3T26 e 3T25, consolidado e por segmento), `volume_producao`, `capacidade_instalada`, `receita_por_t_reportada`, `custo_por_t_reportado`, `ebitda_por_t_reportado`, `participacao_exportacao`, além de `receita_liquida` e `ebitda_ajustado` somente quando o escopo for um segmento. Inclua o nome do segmento no campo `escopo` como `segmento:<slug>`; use `consolidado` apenas para fatos consolidados.

## Saída obrigatória

Responda somente com uma lista JSON válida, sem markdown:

```json
[
  {
    "chave": "volume_vendas",
    "metrica": "Vendas de aço",
    "empresa": "gerdau",
    "documento": "apresentacao",
    "escopo": "consolidado",
    "periodo": "3T26",
    "unidade": "mil t",
    "valor": 0.0,
    "valor_como_aparece": "1.234",
    "pagina": 1,
    "trecho": "cópia literal curta da página"
  }
]
```

Regras:

- `pagina` é o número do arquivo `pagina_NN.txt`, começando em 1; não use o número impresso no slide.
- `trecho` e `valor_como_aparece` devem ser cópias literais, preservando separadores, sinais, caixa e unidade como aparecem no texto extraído.
- `unidade` deve repetir a unidade publicada (`mil t`, `Kt`, `R$ milhões`, `R$/t`, `US$/t`, `%` etc.); não converta.
- Se houver 3T26 e 3T25, represente-os como objetos separados. Só inclua `anterior`, `anterior_como_aparece` e `variacao_pct` quando a mesma página/documento trouxer os dois períodos e a variação estiver reportada ou puder ser conferida pelo contrato existente.
- Não calcule R$/t, EBITDA/t, margens, volumes ou conversões neste card.
- Não transforme uma afirmação de segmento em consolidado e não use controladora/holding.
- Para páginas sem texto, não extraia números; para dado ausente, não invente um objeto.
- Inclua `obs` quando o documento declarar uma definição importante, misturar seções (release/institucional) ou não permitir distinguir o escopo.

## Entrada

Empresa: `<slug>`  
Documento: `<itr|apresentacao>`  
Pasta de texto: `<pasta_saida>`  
Páginas candidatas: `<cole aqui o ranking do localizar_paginas.py>`
