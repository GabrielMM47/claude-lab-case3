# CASE-03 — Apresentações institucionais e fatos operacionais

## Intenção

Entregar ao CASE-04/06/07 fontes institucionais reproduzíveis e fatos operacionais/qualitativos rastreáveis para Gerdau e Usiminas no 3T26, sem colocar cálculos ou dados consolidados das demonstrações financeiras no escopo deste card.

## Objetivos

- Baixar as apresentações oficiais mais recentes disponíveis no RI, priorizando o material associado ao 3T26.
- Extrair cada PDF com o pipeline existente e registrar páginas sem texto.
- Oferecer um localizador genérico por tema, sem nomes ou regras específicas de empresa.
- Produzir prompts reutilizáveis e JSONs compatíveis com `src/verificar_numeros.py` e com o contrato em `docs/quadro_tarefas.html`.
- Deixar cada número ou afirmação com página e trecho literal curto; resumos qualitativos serão redigidos em palavras próprias.

## Fora de escopo

- DFs consolidadas, EBITDA consolidado e qualquer métrica pertencente ao CASE-02.
- Cálculos de R$/t, margens, variações ou comparações pertencentes ao CASE-04.
- Alterações em `src/extrair_release.py` e `src/verificar_numeros.py`.
- Download de fontes não oficiais ou uso de números de páginas que saíram sem texto.

## Abordagens consideradas

1. **Incremental e compatível (escolhida):** preservar os scripts atuais, adicionar o localizador/testes, prompts e artefatos reais com o contrato já publicado. É o menor risco e atende aos consumidores posteriores.
2. **Refatoração de pipeline:** criar uma CLI nova que faça descoberta, extração, ranking, verificação e geração. Não cabe no P0 e criaria uma segunda interface antes do CASE-07.
3. **Fixtures sem fontes reais:** documentar apenas exemplos. Não atende ao aceite de PDFs oficiais, páginas e verificação 100%.

## Desenho escolhido

`src/localizar_paginas.py` lê todos os `pagina_*.txt` de uma pasta, normaliza acentos para comparar palavras-chave, pontua cada página por ocorrências dos termos do tema e imprime um ranking determinístico com página, pontuação e termos encontrados. Os temas são `operacional`, `qualitativo` e `ebitda`; `--top` limita a saída e a função pública será pequena o suficiente para ser reutilizada pelo CASE-07.

Os três tipos de JSON serão listas no topo. Fatos numéricos usam `chave`, `metrica`, `empresa`, `documento`, `escopo`, `periodo`, `unidade`, `valor`, `valor_como_aparece`, `pagina` e `trecho`, com os campos de variação apenas quando o documento trouxer os dois períodos. Fatos qualitativos usam `chave: qualitativo`, `tema`, `resumo`, `pagina` e `trecho`, mantendo o trecho curto.

As apresentações serão guardadas em `data/apresentacoes/` com o nome do contrato. `FONTES.md` registrará página de RI, URL direta, título/data publicados e acesso em 06/11/2026. A extração de texto ficará em `saida/` (ignorada pelo Git); páginas vazias serão listadas em `docs/registro/geronimo.md` e não terão números usados nos JSONs.

## Critérios de aceite cobertos

- Cada empresa terá arquivos operacional de ITR, operacional da apresentação e qualitativo da apresentação.
- Os JSONs operacionais incluirão volumes 3T26/3T25 quando reportados, dados por segmento, capacidade e pelo menos um indicador por tonelada ou seus insumos literais.
- O qualitativo terá ao menos cinco temas, incluindo `perfil`, `estrategia` e `riscos` ou `guidance_perspectivas`.
- O localizador será testado em pastas representativas das duas empresas.
- Cada arquivo será executado contra a pasta de saída correspondente até 100% OK.

## Decisões do executor

- Usar a apresentação oficial disponível no RI no momento do acesso; quando a página de RI não oferecer um arquivo exatamente rotulado 3T26, registrar o título/data real e manter `3T26` no nome do artefato por compatibilidade com o contrato do case.
- Se o PDF misturar release e institucional, usar páginas de ambas as seções somente quando elas forem parte do mesmo documento-fonte e separar o campo `documento` pelo arquivo, não pela seção.
- Se uma métrica do aceite não estiver publicada em um documento, registrar a lacuna em `obs`/log em vez de estimar.
