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

## Observações dos dados

- Usiminas, ROIC 9M26 = ROI: o IR/CSLL do 9M26 é crédito (+R$ 218 mi, ITR p. 14), a alíquota efetiva fica negativa e é limitada a 0%. É a hipótese documentada em METODOLOGIA_INDICADORES.md, mas precisa aparecer explicada no slide.
- Usiminas: dívida líquida calculada (−R$ 566,0 mi) difere da reportada (−R$ 470,7 mi, ITR p. 32) em 17%. A reportada inclui tributos parcelados (registro do CASE-02, item 4).
- Gerdau não divulga volume consolidado, só por segmento: receita/t consolidada fica N/D e vale a por segmento.
