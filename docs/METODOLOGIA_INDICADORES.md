# Metodologia dos indicadores

Como o `src/indicadores.py` (CASE-04) transforma os fatos verificados em indicadores. Vale para qualquer empresa: nada aqui depende de Gerdau ou Usiminas.

```
python src/indicadores.py --empresa <slug> --tri <tri> [--setor siderurgia] [--aliquota-nominal 0.34]
→ metricas/<slug>_<tri>_indicadores.json
```

## Princípios

1. **Só fatos verificados entram.** O motor lê `metricas/<slug>_<tri>_*.json` (menos `_indicadores`). Nenhum número é digitado no código.
2. **Sem valor, o indicador diz por quê** (`status` e `obs`). Nada é estimado, interpolado ou preenchido com zero.
3. **Todo indicador é rastreável**: `insumos` lista chave, período, documento e página de cada fato usado.
4. **Consolidado por padrão**; segmentos aparecem com `escopo: segmento:<nome>`.
5. **Hipóteses ficam explícitas.** Anualização, saldo médio e política tributária do ROIC estão no cabeçalho do JSON e no `obs` de cada indicador; não são dados reportados.

## Status

| `status` | Na apresentação | Quando |
|---|---|---|
| `ok` | o valor | Todos os insumos existem e são compatíveis |
| `ausente` | N/D | Falta algum insumo no período |
| `nao_comparavel` | N/C | Os insumos existem, mas não são da mesma base (ex.: receita consolidada com mineração ÷ volume de aço) |
| `nao_aplicavel` | N/A | Métrica de outro setor (ex.: R$/t para uma empresa que não é siderúrgica) |

O cabeçalho traz `cobertura`, com a contagem de indicadores em cada status. `disponivel` continua existindo (é `status == "ok"`).

## Unidades

| Grandeza | Unidade final | Conversão |
|---|---|---|
| Dinheiro | R$ milhões | R$ mil ÷ 1.000; R$ bilhões × 1.000 (singular e plural: "R$ milhão" = "R$ milhões") |
| Volume | mil t | t ÷ 1.000; milhões de t × 1.000; "1.000 toneladas", "mil toneladas", "kt" e "kton" já são mil t |
| Capacidade | mil t/ano | idem |

"MT"/"Mt" é **ambígua** e o fato é ignorado com alerta: no mesmo arquivo apareceram "6884 MT" (mil t) e "0,9 MT" (milhões de t). O JSON de origem deve dizer "mil t" ou "milhões de t".
| %, x, R$/t, US$/t | como no documento | — |

Unidade fora da lista (ex.: US$ milhões) não é convertida: o fato é ignorado e vira um alerta do tipo `unidade`. Converter moeda exigiria um câmbio, que não está nos fatos.

## Períodos

| Tipo de indicador | Período de referência | A/A | T/T | Extra |
|---|---|---|---|---|
| Trimestre (margens, escala, setor) | 3T26 | 3T25 | 2T26 | — |
| Saldo (dívida, caixa, alavancagem) | 3T26 (30/09) | 3T25 | 2T26 | `var_ano`: contra 4T25 (31/12) |
| Acumulado (rentabilidade, caixa) | 9M26 | 9M25 | — | — |

- O ITR do 3T traz o 3T26, o 3T25, o 9M26 e o 9M25 na DRE, mas só o 30/09/26 e o 31/12/25 no balanço. Por isso A/A de saldos e de rentabilidade fica `null` com um único ITR. A rentabilidade do 9M25 precisa dos saldos de 31/12/24 (4T24) e 30/09/25 (3T25): quando esses fatos forem carregados (do ITR 3T25), o motor calcula sem mudar código.
- Acumulado anualizado e últimos 12 meses (LTM) são bases diferentes. O motor só usa o acumulado anualizado e não troca uma pela outra; o valor LTM reportado pela empresa entra como fato separado (`dl_ebitda_reportado`).
- **Variação:** em p.p. para indicadores em %; diferença simples para múltiplos (x); variação percentual para o resto. Se a base for zero ou negativa (ex.: prejuízo no 3T25), a variação percentual é omitida e o motivo vai em `obs`.

## Critério de EBITDA

Todo indicador que usa EBITDA sai em duas versões, com sufixo `_contabil` e `_ajustado`. O comparativo (CASE-05) escolhe **o mesmo critério para as duas empresas**: ajustado se as duas divulgam, senão contábil.

- **Ajustado:** o valor reportado pela empresa (`ebitda_ajustado`).
- **Contábil (Res. CVM 156):** o reportado (`ebitda_contabil`); se faltar, EBIT (conta 3.05) + D&A do mesmo período. A DFC só traz D&A acumulada, então no trimestre isso exige `depreciacao_amortizacao_tri` (CASE-02).

## Fórmulas

**Anualização:** fluxo acumulado × 4/n (no 3T: 9M × 4/3). **Saldo médio:** média entre o fim do exercício anterior e o fim do trimestre (4T25 e 3T26).

| Indicador | Fórmula |
|---|---|
| Margem bruta, EBIT, líquida | lucro bruto, EBIT, lucro líquido consolidado ÷ receita líquida |
| Margem EBITDA | EBITDA ÷ receita líquida |
| Dívida bruta | empréstimos e financiamentos CP (2.01.04) + LP (2.02.01) |
| Caixa | caixa e equivalentes (1.01.01) + aplicações financeiras (1.01.02) |
| Dívida líquida | dívida bruta − caixa (negativa = caixa líquido) |
| DL/PL | dívida líquida ÷ PL total |
| DL/EBITDA | dívida líquida ÷ EBITDA acumulado anualizado. A empresa costuma divulgar com EBITDA dos últimos 12 meses; quando o valor reportado existe, ele aparece ao lado (`dl_ebitda_reportado`) |
| ROE | lucro dos controladores anualizado ÷ PL dos controladores médio (PL total − não controladores) |
| ROA | lucro líquido consolidado anualizado ÷ ativo total médio |
| ROI (antes de impostos) | EBIT anualizado ÷ capital investido médio. ROI não tem definição única; o nome no JSON já diz qual é a nossa |
| ROIC | EBIT anualizado × (1 − alíquota efetiva) ÷ capital investido médio |
| Capital investido | dívida líquida + PL total |
| Alíquota efetiva | −IR/CSLL ÷ LAIR do acumulado, limitada entre 0% e a alíquota nominal; com LAIR ≤ 0, usa a nominal. Nominal padrão 34%, ajustável com `--aliquota-nominal`. É hipótese metodológica e aparece em `politica_tributaria` |
| FCL | caixa das operações (6.01) − capex, no acumulado |
| Capex/receita | capex ÷ receita líquida, no acumulado |
| Receita, CPV e EBITDA por tonelada | valor em R$ milhões × 1.000 ÷ volume vendido em mil t = R$/t |
| Utilização da capacidade | produção do trimestre × 4 ÷ capacidade instalada (não corrige sazonalidade) |
| Participação do segmento | valor do segmento ÷ soma dos segmentos (sem eliminações intersegmento) |

**Por tonelada exige o mesmo negócio no numerador e no denominador.** Se a empresa tem segmento de mineração (receita, EBITDA ou volume com escopo `segmento:*minera*`), receita, CPV e EBITDA consolidados por tonelada saem como `nao_comparavel`: o volume é de aço e o valor inclui minério. Nesse caso vale o indicador do segmento siderúrgico, que sai separado quando há volume por segmento. O volume consolidado continua disponível.

**Setor:** o padrão é `siderurgia`. Com outro `--setor`, as métricas por tonelada e os fatos operacionais de siderurgia ficam `nao_aplicavel`; margens, endividamento e rentabilidade continuam valendo.

**Direção (`melhor`):** valores absolutos (receita, EBIT, EBITDA, lucro, dívida, caixa, FCO, FCL, volume, capacidade) saem com `melhor: "neutro"`. Eles medem tamanho, e entre empresas de portes diferentes não há vencedor. Margens, múltiplos, retornos e valores por tonelada mantêm `maior` ou `menor`.

**Fatos reportados que entram como estão** (quando existem): produção, capacidade, R$/t, custo/t e EBITDA/t reportados, vendas de minério, participação da exportação, dívida líquida e DL/EBITDA reportados.

## Alertas

| Tipo | Quando |
|---|---|
| `divergencia` | O mesmo fato (chave, período, escopo) aparece em dois arquivos com diferença acima de 0,5%. O alerta guarda os dois valores com documento e página (`valores`) e diz qual foi mantido (`mantido`: ITR antes da apresentação). A prioridade só decide entre fontes do mesmo fato: escopos, períodos e EBITDA contábil × ajustado nunca se substituem |
| `ambiguo` | O documento de maior prioridade traz **valores diferentes** para a mesma chave, período e escopo (ex.: aço e minério, ou mercado interno e exportação, gravados como `volume_vendas`). A prioridade não decide e a ordem de leitura não pode decidir: **nenhum valor é usado** e o indicador sai N/D com o motivo. Corrige-se no JSON de origem, com chave ou escopo próprios |
| `divergencia_definicao` | Dívida líquida calculada difere da reportada em mais de 5% (costuma ser critério: arrendamentos, derivativos) |
| `efeito_pontual` | Ajustes **pontuais** passam de 10% do EBITDA ajustado de um período (3T26, 3T25 ou 2T26): variações contra esse período podem enganar. Ajuste com `natureza: "recorrente"` (ex.: EBITDA proporcional de controladas em conjunto) é critério de cálculo e não conta; sem `natureza`, conta por cautela. Todos os ajustes vão em `ajustes_ebitda` |
| `unidade` | Fato com unidade não suportada ou ambígua, ignorado |

## Limitações conhecidas

- Sem os últimos 12 meses: a anualização do acumulado distorce quando há sazonalidade forte.
- EBIT da conta 3.05 inclui equivalência patrimonial; ROI e ROIC herdam isso.
- Saldo médio usa só dois pontos (31/12 e 30/09).
