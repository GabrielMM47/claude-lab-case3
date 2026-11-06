# Prompt — extração financeira complementar do ITR (CASE-02)

Reutilizável para qualquer empresa e trimestre. Troque só `<slug>`, `<tri>` e as páginas candidatas.

---

Leia `docs/TAREFAS.md` (seção "Contrato de dados") e os arquivos `saida/<slug>_ITR_<tri>/pagina_NN.txt` das páginas candidatas abaixo. Gere `metricas/<slug>_<tri>_itr_complementar.json`: uma **lista JSON** de fatos, com as chaves complementares do catálogo:

- `ebitda_contabil` (EBITDA Res./Instrução CVM 156), `ebitda_ajustado`, um `ajuste_ebitda` por linha da reconciliação (o campo `metrica` descreve o ajuste);
- `depreciacao_amortizacao_tri` (D&A só do trimestre);
- `divida_bruta_reportada`, `divida_liquida_reportada`, `dl_ebitda_reportado` (unidade `x`).

Períodos: `<tri>`, o mesmo trimestre do ano anterior, o trimestre anterior (se o documento trouxer) e os acumulados do ano. Saldos usam o rótulo do trimestre que termina na data.

**Regras (inegociáveis)**
1. Só números **consolidados**. Comentário de desempenho da controladora/holding e DFs Individuais: não usar. Dado por segmento não entra aqui.
2. `trecho` = a **linha inteira copiada** de `pagina_NN.txt`, sem corrigir espaços nem letras. `valor_como_aparece` = o token exatamente como está nessa linha (`(60.412)`, `-0,20x`).
3. `evidencia`: `escopo`, `unidade` e `periodo` são trechos **literais da mesma página** que provam o escopo, a unidade e o período. `coluna` e `n_colunas` = posição do valor entre os valores do fim da linha (células `-` contam como coluna).
4. `unidade` como aparece no documento (`R$ mil`, `R$ milhões`, `x`). Não converta. Se a mesma página mistura unidades, confira o cabeçalho da tabela de cada linha.
5. Prefira a tabela em R$ mil quando o mesmo número aparecer também em R$ milhões.
6. Página com dígitos espaçados (`3 .7 7 0 .1 7 6`): procure o mesmo número em outra tabela com texto limpo; se não houver, registre na cobertura e não invente.
7. Procure **efeitos pontuais** (impairment, baixa, ganho na venda de ativo, recuperação de créditos) no ano anterior e no trimestre anterior; cada um vira `ajuste_ebitda`, com `obs` dizendo se é recorrente ou pontual.
8. Não divulgado → **não crie fato**. Escreva em `metricas/cobertura/<slug>_<tri>_itr_complementar.json` um item `{"chave", "periodo", "status": "ausente", "motivo"}`. Nunca preencha com zero nem calcule (cálculo é do CASE-04).
9. Confira a reconciliação em código: EBITDA CVM 156 + ajustes = EBITDA ajustado.

Depois rode:

```bash
python src/verificar_numeros.py saida/<slug>_ITR_<tri> metricas/<slug>_<tri>_itr_complementar.json
```

Corrija só os itens com ERRO, olhando a página indicada. Para REVISAR, confira à mão e registre `"revisao_manual": {"por": "<nome>", "nota": "<o que conferiu>"}` no fato. Anote cada erro em `docs/registro/<pessoa>.md`.

**Páginas candidatas:** <listar, por exemplo da busca por "EBITDA", "reconciliação", "Dívida Líquida", "Endividamento">
