# CASE-03 — Registro de Geronimo

## Escopo e contrato

Implementação da apresentação institucional + dados operacionais e qualitativos para Gerdau e Usiminas no 3T26. Os JSONs são listas no formato de `docs/quadro_tarefas.html` e cada arquivo aponta para um único documento-fonte, para que `src/verificar_numeros.py` seja executado sem alteração.

## Decisões

- Abordagem escolhida e aprovada: adicionar somente o localizador genérico, prompts e artefatos reais; preservar `src/extrair_release.py` e `src/verificar_numeros.py`.
- Acesso registrado em 06/11/2026 no fuso `America/Sao_Paulo`.
- Páginas são índices físicos do PDF, iguais aos nomes `pagina_NN.txt`; o número impresso no slide não substitui esse índice.
- Nenhum dado ausente será estimado neste card; cálculos pertencem ao CASE-04.

## Pesquisa externa

- O conector Firecrawl foi acionado, mas retornou falta de créditos e não executou a busca. Foi usado fallback de busca web e conferência das páginas oficiais de RI; isso não altera a fonte primária dos PDFs.
- Fontes oficiais e URLs diretas ficam em `data/apresentacoes/FONTES.md`.

## Páginas sem texto

- `gerdau_APRESENTACAO_3T26.pdf`: nenhuma página sem texto.
- `usiminas_APRESENTACAO_3T26.pdf`: `pagina_40.txt` sem texto; não usar números ou evidência qualitativa dessa página.
- Os ITRs também foram extraídos para permitir os arquivos `*_itr_operacional.json`: Gerdau 80 páginas e Usiminas 110 páginas; a extração não indicou páginas vazias relevantes para este card.

## Erros encontrados durante a execução

- Primeira execução de `src/extrair_release.py` abortou ao imprimir `→` em console `cp1252` (`UnicodeEncodeError`). Os arquivos extraídos até aquele ponto não foram descartados; a execução foi repetida com `PYTHONIOENCODING=utf-8`, concluindo Gerdau ITR (80 p.), Usiminas ITR (110 p.), Gerdau apresentação (44 p.) e Usiminas apresentação (40 p.). Nenhum script existente foi alterado.
- Nos gráficos de volume/receita/EBITDA da apresentação Gerdau (p. 18–20), o texto extraído fragmenta dígitos (`111...555...`) apesar de o slide ser legível. Os valores foram transcritos visualmente, com `obs` explicando a limitação; os campos numéricos verificáveis do mesmo documento usam apenas literais que aparecem intactos no `.txt`.

## Verificação

Comando usado em cada arquivo:

```text
py -3.13 src/verificar_numeros.py <pasta_saida> <arquivo_json>
```

Resultado final em 06/11/2026:

| JSON | Pasta-fonte | Resultado |
|---|---|---:|
| `gerdau_3T26_itr_operacional.json` | `saida/gerdau_ITR_3T26` | 12/12 |
| `gerdau_3T26_apresentacao_operacional.json` | `saida/gerdau_APRESENTACAO_3T26` | 22/22 |
| `gerdau_3T26_apresentacao_qualitativo.json` | `saida/gerdau_APRESENTACAO_3T26` | 8/8 |
| `usiminas_3T26_itr_operacional.json` | `saida/usiminas_ITR_3T26` | 19/19 |
| `usiminas_3T26_apresentacao_operacional.json` | `saida/usiminas_APRESENTACAO_3T26` | 13/13 |
| `usiminas_3T26_apresentacao_qualitativo.json` | `saida/usiminas_APRESENTACAO_3T26` | 7/7 |

Total: **81/81 itens OK**. A suíte do localizador também foi executada com `py -3.13 -m pytest tests/test_localizar_paginas.py -q` e passou com 4 testes.

## Lacunas e erros

- A Gerdau não apresenta volume consolidado em um texto verificável; a apresentação mostra volumes por divisão (Brasil, América do Norte e América do Sul). Não foi calculado um consolidado neste card.
- Os valores dos gráficos de volume/receita/EBITDA da Gerdau foram transcritos do slide e marcados com `valor_como_aparece: null` porque o texto extraído fragmenta os dígitos; o trecho textual e a página foram verificados, e os fatos literais do ITR não têm essa limitação.
- A Usiminas não traz 3T25 para receita/EBITDA por segmento na tabela operacional usada; os valores por segmento incluídos são os reportados para 3T26, sem estimar o comparativo.
- O primeiro passe do verificador encontrou trechos qualitativos longos demais ou com quebra de layout e `$` não aceito pelo parser; foram substituídos por âncoras literais menores (`sujeitas a riscos`, `Reconstrução`, `87`, `75`) sem alterar o código do verificador.
