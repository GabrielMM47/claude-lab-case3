# Registro — Gabriel Patrício (CASE-04 e CASE-06)

## Erros encontrados

| # | Empresa | Métrica | O que o Claude/código disse | O que estava no documento (pág. = índice do PDF) | Como pegamos | Correção |
|---|---|---|---|---|---|---|
| 1 | Usiminas | Efeito pontual no EBITDA ajustado | o motor somava todos os ajustes como "não recorrentes": alerta de 23% no 3T26, 544% no 3T25 e 15% no 2T26 | ITR p. 28: a reconciliação mistura ajustes recorrentes (equivalência patrimonial, EBITDA proporcional de controladas em conjunto) com um pontual (impairment de R$ 2.226.332 mil no 3T25) | primeira rodada do CASE-04 com o complementar real do CASE-02, que marca `natureza` em cada ajuste | só `natureza: "pontual"` conta. Sobra o alerta certo (3T25, 513%, impairment); os de 3T26 e 2T26 eram falsos |
| 2 | Usiminas | Volume de vendas e capacidade | o motor escolhia pela ordem de leitura dos arquivos ("mantido o do itr" entre dois valores do próprio ITR). Por sorte ficou o aço; com outra ordem, o volume de minério viraria volume de aço | ITR p. 24: aço 1.034 e minério 2.014 mil t, ambos como `volume_vendas` consolidado. ITR p. 36: total 1.034, mercado interno 979 e exportação 55, todos como `volume_vendas` de siderurgia. Apresentação p. 16: capacidade 6,9 total, 4,6 Ipatinga e 2,3 Cubatão no mesmo escopo | alerta de divergência entre valores do mesmo documento na rodada com dados reais | valores diferentes no documento de maior prioridade viram alerta `ambiguo` e nenhum é usado (N/D com motivo). A correção dos JSONs é do CASE-03 |
| 3 | Gerdau | Volume de vendas por segmento | fatos ignorados ("unidade não suportada: '1.000 toneladas'"), então receita/t e EBITDA/t por segmento saíam N/D | apresentação p. 18–20: Brasil 1.351, América do Norte 1.313, América do Sul 309 mil t no 3T26 | alerta `unidade` na rodada com dados reais | aceitas as variantes "1.000 toneladas", "mil toneladas", "kton" e "R$ milhão" |
| 4 | Gerdau | Capacidade instalada | "MT" era convertido como milhões de t (× 1.000) | o mesmo JSON traz 6884 MT e 0,9 MT (apresentação p. 7, 8 e 12): não pode ser a mesma unidade | revisão das unidades usadas nos JSONs reais | "MT" passa a ser ambígua: o fato é ignorado com alerta, nunca adivinhado. O CASE-03 precisa registrar "mil t" ou "milhões de t" |
| 5 | — | Direção `melhor` no indicadores.json | receita, EBITDA, lucro, dívida e volume saíam com `maior`/`menor`: o comparativo elegeria vencedor por tamanho | regra do CASE-05 em TAREFAS.md ("maior receita não é melhor desempenho") | leitura do indicadores.json real da Gerdau, bem maior que a Usiminas | valores absolutos saem com `melhor: "neutro"` |
| 6 | Gerdau | Página da fonte | o mapa de páginas do CLAUDE.md e do GUIA_CASE3.md dizia "páginas impressas" | DRE consolidada: índice 29 do PDF, impressa como 24 e "PÁGINA: 16 de 65" | comparação dos `pagina_NN.txt` com o mapa | documentos corrigidos: página é sempre o índice do PDF |
| 7 | — | Fixture do CASE-06 | o `comparativo.json` e os gráficos da fixture "estavam no commit" | o `.gitignore` ignora qualquer pasta `saida/`, inclusive dentro de `tests/` | testes rodados num clone limpo da branch | fixture movida para `tests/fixtures_apresentacao/comparativo/` |
| 8 | Usiminas | Destaque positivo do slide 7 | "+ Margem líquida: 3,9% (+57,0 p.p. A/A)" como o melhor resultado do trimestre, no mesmo slide do alerta de impairment | ITR p. 28: impairment de R$ 2.226.332 mil no 3T25. Ele está no lucro e no EBIT; o EBITDA ajustado já o exclui. O `comparativo.json` real marca como distorcidas só as linhas de EBITDA, e a fixture marcava lucro e margem líquida | leitura dos slides gerados com dados reais | `destaques_numericos` também exclui as linhas contábeis (EBIT, lucro, margens) quando há efeito pontual. Sem margem que piorou, o destaque negativo passa a ser a pior linha financeira do trimestre (Usiminas: receita -6,1% A/A, ITR p. 14), em vez de "nenhum indicador piorou" |

## Observações dos dados

- Usiminas, ROIC 9M26 = ROI: o IR/CSLL do 9M26 é crédito (+R$ 218 mi, ITR p. 14), a alíquota efetiva fica negativa e é limitada a 0%. É a hipótese documentada em METODOLOGIA_INDICADORES.md, mas precisa aparecer explicada no slide.
- Usiminas: dívida líquida calculada (−R$ 566,0 mi) difere da reportada (−R$ 470,7 mi, ITR p. 32) em 17%. A reportada inclui tributos parcelados (registro do CASE-02, item 4).
- Gerdau não divulga volume consolidado, só por segmento: receita/t consolidada fica N/D e vale a por segmento.

## Integração e validação em 06/11/2026

- Integrados os commits de `origin/main` com CASE-01, CASE-03, CASE-05 e documentação. Preservados o motor e o gerador da apresentação desta branch; indicadores reais regenerados a partir dos fatos corrigidos.
- Indicadores das duas empresas e comparativo real passam nos schemas específicos. O comparativo gera cinco gráficos e o gerador produz oito slides em `saida/apresentacao/gerdau_x_usiminas_3T26.html`.
- Corrigido o catálogo: indicadores calculados não são mais enviados ao verificador de fatos contra um único PDF. Isso não certifica os fatos usados nos cálculos.
- Regeneradas as fixtures fictícias e o catálogo local.
- Ainda pendente no CASE-03: 37 violações do schema de fatos (24 em `gerdau_3T26_apresentacao_operacional.json`, 7 em `usiminas_3T26_apresentacao_operacional.json`, 6 em `usiminas_3T26_itr_operacional.json`). Incluem 17 valores literais nulos nos gráficos da Gerdau (p. 18–20), unidades fora da lista aceita e o período `3T26 vs 2T26` na variação da receita por tonelada (p. 19). Não foram inventados literais nem relaxado o schema para aprovar esses dados.
- A apresentação gerada é rascunho para revisão: gerar slides e passar no schema dos indicadores não substitui a verificação dos fatos de origem.
- Validação final: `python -m pytest -q --tb=short` executado no venv: 802 passaram, 3 ignorados e 1 falhou (`test_c_t3b_fatos_dentro_do_contrato`, pelas 37 violações acima). Catálogo e fixtures passaram em `--check`.

## Narrativa e versão de entrega (CASE-06, itens 4 e 6)

- `narrativa/gerdau_x_usiminas_3T26.json`: títulos-mensagem dos 8 slides e os 3 bullets do resumo, escritos com o Claude Code a partir do `comparativo.json`. Nenhum número digitado: tudo entra por placeholder (`{a.margem_ebitda}`, `{b.receita_liquida.var_aa}`...) e passa no verificador de narrativa.
- Escolhas de redação: não citar o EBITDA ajustado A/A da Usiminas (base 3T25 marcada com efeito pontual); citar o T/T (-26,7%). O slide de destaques diz que a volta do lucro da Usiminas parte de um 3T25 com impairment.
- `entrega/apresentacao_gerdau_x_usiminas_3T26.html` gerado com a narrativa. Continua rascunho: `verificacao` do comparativo está `null` (CASE-07) e os JSONs operacionais do CASE-03 ainda reprovam no verificador.
- Prompt que funcionou: "Leia saida/comparativo/gerdau_x_usiminas_3T26/comparativo.json e escreva narrativa/gerdau_x_usiminas_3T26.json no contrato de docs/TAREFAS.md: título-mensagem por slide, só placeholders para números, nenhum A/A em linha marcada com efeito pontual; rode o verificador de narrativa."

