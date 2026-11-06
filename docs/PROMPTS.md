# Prompts principais

Os prompts completos ficam versionados em `prompts/`. Todos recebem páginas candidatas extraídas de um único documento e exigem rastreabilidade até página e trecho.

## Extração financeira complementar

[`prompts/extracao_financeira_complementar.md`](../prompts/extracao_financeira_complementar.md)

Usado para EBITDA contábil/ajustado, ajustes pontuais, D&A, dívida reportada e dívida líquida. Regras centrais: copiar literais, preservar unidade, distinguir consolidado de segmento e não estimar ausências.

## Extração operacional

[`prompts/extracao_operacional.md`](../prompts/extracao_operacional.md)

Usado para volume de vendas, produção, capacidade, receita/CPV/EBITDA por tonelada e exportação. Exige objetos separados para 3T26 e 3T25 e proíbe conversões ou cálculos no momento da extração.

## Extração qualitativa

[`prompts/extracao_qualitativo.md`](../prompts/extracao_qualitativo.md)

Usado para perfil, footprint, mercados, estratégia, capex, riscos, guidance e ESG. Exige 5 a 8 temas, resumo em palavras próprias e trecho literal curto para auditoria.

## Regras de verificação

Depois da extração:

1. conferir a forma do JSON;
2. apontar o arquivo para a pasta `saida/` correta;
3. executar `src/verificar_numeros.py`;
4. corrigir erros, registrar revisões manuais e repetir;
5. só então calcular indicadores ou escrever narrativa.

Não usar números de memória, não misturar unidades e não transformar uma evidência de segmento em consolidado.
