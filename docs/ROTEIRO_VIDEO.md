# Roteiro do vídeo — 2 minutos

## 0:00–0:20 · O problema

**Tela:** título do projeto e dois PDFs lado a lado.

**Fala:**

> Comparar Gerdau e Usiminas não é apenas copiar números. É garantir que cada valor pertence ao mesmo período, unidade, escopo e critério de EBITDA. Um erro de coluna ou de unidade muda a conclusão do slide.

## 0:20–1:20 · A solução na tela

**Tela:** mostrar o fluxo do README, depois `saida/`, um ranking do `localizar_paginas.py` e um JSON de métricas.

**Fala:**

> O fluxo começa nos PDFs oficiais de RI e CVM. Extraímos as páginas, localizamos as páginas candidatas por tema e usamos prompts para transformar evidências em JSON. Cada fato guarda a página, o trecho, a unidade e o escopo. Depois, o verificador procura o token literalmente no texto e só então os indicadores são calculados.

**Tela:** abrir `docs/ERROS_ENCONTRADOS.md` e destacar os erros documentados.

> Quando a automação não prova a coluna, registramos revisão manual. Quando uma página não tem texto, ela não vira fonte numérica.

## 1:20–1:40 · Um número conferido na fonte

**Tela:** Usiminas, ITR p. 28, linha do EBITDA com cabeçalhos de período.

**Fala:**

> Um caso real foi o número 156, que fazia parte do texto “Instrução CVM 156”. O parser poderia tratá-lo como EBITDA. A reconciliação e a conferência do cabeçalho mostraram o erro; o verificador passou a exigir a coluna e o período corretos.

## 1:40–2:00 · Impacto e próximos passos

**Tela:** comparativo final ou, enquanto ele não existe, o painel de status dos CASEs.

**Fala:**

> O resultado é uma análise auditável: cada número tem uma origem e cada limitação fica visível. O próximo passo é conectar os indicadores ao comparativo, gerar os oito slides e publicar o artefato para teste em aba anônima.

## Organização da gravação

- Pessoa 1: problema e contexto — 20 segundos.
- Pessoa 2: demonstração do fluxo — 60 segundos.
- Pessoa 3: erro real e conferência na fonte — 20 segundos.
- Pessoa 4: impacto, limitações e próximos passos — 20 segundos.

Se o artefato final ainda não estiver publicado, usar o fluxo documental e os JSONs verificados como demonstração provisória; substituir essa tela antes do envio.
