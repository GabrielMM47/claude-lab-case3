# Prompts principais

Os prompts completos ficam versionados em [`prompts/`](../prompts/). Todos recebem páginas candidatas de um único documento e exigem rastreabilidade até página e trecho. O pipeline (`src/pipeline.py`) monta cada prompt sozinho quando falta um JSON assistido: troca empresa e trimestre, anexa as páginas candidatas do `localizar_paginas.py` e salva o texto em `saida/prompts/` para colar no Claude Code.

## Extração financeira complementar

[`prompts/extracao_financeira_complementar.md`](../prompts/extracao_financeira_complementar.md)

Usado para EBITDA contábil/ajustado, ajustes pontuais, D&A, dívida reportada e dívida líquida. Regras centrais: copiar literais, preservar unidade, distinguir consolidado de segmento, marcar a `natureza` de cada ajuste (pontual ou recorrente) e não estimar ausências.

**O que funcionou:** para não digitar nenhum número, o JSON foi montado por um script que recebe (página, início da linha, coluna) e copia trecho e token literais do `pagina_NN.txt`. As reconciliações foram conferidas em código antes de gravar (ex.: Usiminas 3T26, ITR p. 28: 588.039 − 80.452 + 50.430 = 558.017).

## Extração operacional

[`prompts/extracao_operacional.md`](../prompts/extracao_operacional.md)

Usado para volume de vendas, produção, capacidade, receita/CPV/EBITDA por tonelada e exportação. Exige objetos separados para 3T26 e 3T25 e proíbe conversões ou cálculos no momento da extração.

**O que aprendemos:** o trecho precisa ser a linha inteira com o número, e a coluna precisa ser provada pelo cabeçalho literal (`3T26 2T26 ∆ 3T25 ∆`). Só o título da linha não serve como evidência.

## Extração qualitativa

[`prompts/extracao_qualitativo.md`](../prompts/extracao_qualitativo.md)

Usado para perfil, footprint, mercados, estratégia, capex, riscos, guidance e ESG. Exige 5 a 8 temas, resumo em palavras próprias e trecho literal curto para auditoria.

## Narrativa da apresentação

Prompt usado no Claude Code:

> Leia `saida/comparativo/gerdau_x_usiminas_3T26/comparativo.json` e escreva `narrativa/gerdau_x_usiminas_3T26.json` no contrato de `docs/TAREFAS.md`: título-mensagem por slide, só placeholders para números, nenhum A/A em linha marcada com efeito pontual; rode o verificador de narrativa.

O verificador de narrativa (`src/apresentacao.py`) reprova número escrito à mão, empresa ou período fora da comparação e marcador sem valor (N/D ou N/C). Uma narrativa reprovada não vira apresentação.

## Como trabalhamos com o Claude Code

- **Spec primeiro, um agente por arquivo:** no comparativo, a especificação fechou as interfaces e cada agente só podia editar o próprio arquivo ([spec do CASE-05](superpowers/specs/2026-11-06-case05-comparativo-design.md)).
- **Fixtures fictícias** (`empresa_a`, `empresa_b`, `empresa_c`) para cada card começar sem esperar os dados reais, sem risco de vazarem para a apresentação.
- **Registro de erros por pessoa** em [`docs/registro/`](registro/), consolidado em [`ERROS_ENCONTRADOS.md`](ERROS_ENCONTRADOS.md).

## Regras de verificação

Depois da extração:

1. conferir a forma do JSON (`python src/contrato.py <arquivo>`);
2. apontar o arquivo para a pasta `saida/` do documento certo;
3. executar `src/verificar_numeros.py` (o pipeline faz isso em todos os arquivos de fatos);
4. corrigir erros, registrar revisões manuais e repetir;
5. só então calcular indicadores ou escrever narrativa.

Não usar números de memória, não misturar unidades e não transformar uma evidência de segmento em consolidado.
