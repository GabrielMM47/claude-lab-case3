# Fixture fictícia do CASE-06 (apresentação executiva)

**Provisória.** O CASE-01 ainda não publicou as fixtures oficiais; esta existe para o CASE-06 começar. Quando a oficial chegar, os testes de `tests/test_apresentacao.py` passam a rodar nela também e esta pasta pode ser apagada.

**Tudo aqui é inventado** (empresas `empresa_a` e `empresa_b`, tickers `FCTA3`/`FCTB3`, números e páginas). Nada desta pasta pode aparecer na apresentação real.

## O que tem

| Arquivo | Formato (docs/TAREFAS.md) | Quem gera de verdade |
|---|---|---|
| `saida/comparativo/empresa_a_x_empresa_b_3T26/comparativo.json` | `comparativo.json` | CASE-05 |
| `saida/comparativo/.../graficos/*.png` | os 5 gráficos do CASE-05 | CASE-05 |
| `metricas/empresa_*_3T26_apresentacao_qualitativo.json` | fato qualitativo | CASE-03 |
| `narrativa/empresa_a_x_empresa_b_3T26.json` | narrativa | CASE-06 |

Tudo sai de `gerar_fixture.py` (números-base em `BASE`; margens, variações, textos, vencedor e gráficos calculados). Para mudar a fixture, edite o script e rode:

```
python tests/fixtures_apresentacao/gerar_fixture.py
```

## Casos que a fixture cobre

- **Vencedor:** só em linha com `melhor` definido e as duas empresas disponíveis. Receita, EBITDA, lucro, dívida e volume não elegem vencedor ("maior receita não é melhor desempenho").
- **N/D:** ROIC da B (`status: ausente`, falta IR/CSLL).
- **N/C:** receita/t e EBITDA/t da B (mineração no consolidado).
- **Base negativa:** lucro da B no 3T25 é prejuízo, então a variação A/A fica `null` com motivo em `obs`.
- **Caixa líquido:** dívida líquida e DL/EBITDA negativos na B.
- **Período diferente na mesma tabela:** ROE e ROIC são 9M26 anualizado (`periodo: "9M26"`).
- **Alertas:** efeito pontual, negócios diferentes, indisponível, divergência de definição.

## Campos além do contrato (propostas para alinhar com o CASE-05)

O exemplo de `comparativo.json` em TAREFAS.md não mostra estes campos. A fixture os usa porque a apresentação precisa deles:

- `linhas[].periodo`: período do valor (rentabilidade é 9M26, o resto 3T26).
- `linhas[].a|b.status` e `.obs`: `ok` | `ausente` | `nao_comparavel` | `nao_aplicavel` e o motivo. Igual ao `indicadores.json` (METODOLOGIA_INDICADORES.md). `texto` traz `N/D`, `N/C` ou `N/A`.
- `segmentos[].fontes`, `alertas[].fontes` e `graficos[].fontes`: todo número na tela precisa de página.

`fontes` segue o exemplo do contrato (`"ITR p.29"`, `"Apresentação p.12"`), com página = índice do PDF.

## Narrativa: proposta de placeholders

Nenhum número é escrito à mão na narrativa. O código troca os placeholders por valores do `comparativo.json`, e o verificador de narrativa reprova qualquer dígito fora deles (exceto rótulos de período como `3T25` e `9M26`).

| Placeholder | Vira |
|---|---|
| `{a.nome}`, `{b.nome}` | nome da empresa |
| `{a.<chave>}` | `texto` da linha `<chave>` para a empresa A |
| `{b.<chave>.var_aa}`, `{b.<chave>.var_tt}` | variação formatada com a unidade (`p.p.`, `%`, `x`) |
| `{periodo}`, `{criterio_ebitda}` | campos do topo do `comparativo.json` |
