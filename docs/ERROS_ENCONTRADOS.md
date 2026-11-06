# Erros encontrados e como foram corrigidos

Os exemplos abaixo são evidências reais encontradas durante a extração e a conferência. Eles também servem de material para o vídeo e para a seção de verificação do README.

| # | Empresa | Métrica / página | Problema encontrado | Como foi detectado | Tratamento |
|---|---|---|---|---|---|
| 1 | Usiminas | EBITDA, p. 28 | O token `156` de “Instrução CVM 156” foi interpretado como valor da coluna 3T26. | Reconciliação do EBITDA e conferência de cabeçalho. | O verificador passou a exigir coluna e cabeçalho compatíveis com o período. |
| 2 | Usiminas | Dívida bruta, p. 32 | A soma das contas das DFs (R$ 6.181.166 mil) não coincide com a dívida bruta reportada (R$ 6.276.500 mil). | Comparação entre DFs e release. | Mantidas as duas medidas, com observação de que a reportada inclui tributos parcelados. |
| 3 | Usiminas | D&A, p. 16 e p. 45 | O release informa 735.383, enquanto a DFC informa 735.386. | Conferência cruzada entre DFC e release. | A DFC foi usada nas DFs e o release no complementar, preservando as páginas. |
| 4 | Gerdau | EBITDA ajustado, p. 72–74 | A reconciliação da p. 74 tem dígitos espaçados e não gera token confiável. | Verificador e comparação com a tabela consolidada. | Usada a p. 72, onde 3.770.176 aparece em texto verificável. |
| 5 | Gerdau | Volumes, receita e EBITDA, p. 18–20 | O extrator fragmenta os dígitos dos gráficos, embora o slide seja visualmente legível. | Extração PDF versus conferência visual. | Valores foram marcados com observação e não usados como literal automatizado quando não havia token íntegro. |
| 6 | Usiminas | Apresentação institucional, p. 40 | A página saiu sem texto. | Inspeção da pasta `saida/usiminas_APRESENTACAO_3T26`. | A página foi registrada como indisponível e não foi usada como evidência. |
| 7 | Usiminas | Operacional, p. 24 e p. 36 | Volume de minério estava no consolidado; total de aço, mercado interno e exportação colidiam na mesma chave/escopo. | Recalculo dos indicadores e alertas de duplicidade. | Minério passou para `segmento:mineracao`; total de aço ficou em `segmento:siderurgia`; subcomponentes receberam subescopos próprios. |
| 8 | Ambas | Caixa das operações, FCL e capex/receita (9M26) | A apresentação dizia “9M26 anualizado, sobre saldos médios” para esses indicadores, mas eles são o acumulado do 9M26, sem anualizar; só ROE, ROA e ROIC são anualizados (`src/indicadores.py`, modo `acum`). | Revisão do conteúdo dos slides durante o redesenho (time). | `src/apresentacao.py` passou a rotular “9M26 anualizado” só o grupo rentabilidade e “9M26 acumulado” os demais, na tabela e na metodologia. |

## Limitações ainda abertas

- A apresentação da Gerdau não fornece volume consolidado textual verificável.
- Alguns fatos antigos ainda precisam de evidências literais adicionais para o verificador estrito.
- A publicação do artefato e o vídeo dependem dos CASEs de comparação e apresentação.
