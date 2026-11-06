# Registro — Gabriel Martins (CASE-02 e CASE-07)

## Erros encontrados

| # | Empresa | Métrica | O que o Claude/código disse | O que estava no ITR (pág.) | Como pegamos | Correção |
|---|---|---|---|---|---|---|
| 1 | (teste) | Lucro bruto | identidade lucro_bruto = receita + cpv quebrada de propósito | DRE consolidada | `checar_consistencia` no `dfs_cvm.py` | o parser recusa gravar o JSON (exit 1) |
| 2 | — | Verificador original | um número que existe na página "conferia" mesmo estando na coluna de outro período (ex.: 3T25 no lugar do 3T26) ou na página das DFs Individuais | — | teste `test_numero_existe_na_pagina_mas_na_coluna_errada` | verificador passou a checar coluna, período, unidade e escopo |

| 3 | Usiminas | D&A 9M26 | release (p. 45): 735.383 | DFC consolidada (p. 16): 735.386 | comparação DFC × release | diferença de R$ 3 mil; usamos a DFC nas DFs e o release no complementar, cada um com sua página |
| 4 | Usiminas | Dívida bruta | soma das DFs: emprestimos_cp + emprestimos_lp = 6.181.166 | release (p. 32): 6.276.500 | comparação DFs × release | a reportada inclui tributos parcelados (95.333); o CASE-04 deve mostrar as duas e explicar |
| 5 | Gerdau | EBITDA ajustado | a reconciliação da p. 74 sai com dígitos espaçados ("3 .7 7 0 .1 7 6"): o verificador não acha o token | p. 72 (coluna Consolidado, texto limpo): 3.770.176 | verificador | usamos a p. 72 |
| 6 | Usiminas / Gerdau | Dívida (p. 32) / EBITDA e D&A por segmento (p. 72–73) | Usiminas p. 32 sem a palavra "consolidado"; Gerdau com cabeçalho de colunas espaçado ("3 0 /0 9 /2 0 2 6") | — | verificador marcou REVISAR (15 itens): não dá para provar por código qual coluna é qual período | revisão manual pendente |

| 7 | Usiminas | EBITDA CVM 156 (3T26, 2T26, 3T25, 9M26, 9M25) | **o "156" de "Instrução CVM 156" foi lido como a coluna do 3T26**: 3T26 = 156, 2T26 = 588.039 (era o 3T26), 3T25 = 798.602 (era o 2T26); na linha acumulada, "(Instrução CVM 156)" virou o token "156)" | p. 28: 588.039 / 798.602 / (1.747.170); p. 45: 2.041.362 / (547.928) | o verificador original **aprovou** (cada número existia na linha); quem pegou foi a reconciliação recalculada a partir do JSON (CVM 156 + ajustes ≠ EBITDA ajustado) | verificador passou a exigir `cabecalho_colunas` e a conferir o rótulo da coluna contra o período; regex de número exige parênteses balanceados; testes `test_numero_no_nome_da_conta_nao_vira_coluna` e `test_parentese_sem_par_nao_e_numero` |

## Observações dos dados

- Gerdau e Usiminas usam códigos diferentes para D&A (`6.01.01.02` × `6.01.01.04`) e capex (`6.02.01 Adições de imobilizado` × `6.02.02 Compras de Imobilizado`): achados pela descrição, sem `if empresa`.
- A DFC do ITR só traz o acumulado (9M26, 9M25): FCO, capex e D&A **trimestrais** ficam `nao_comparavel` na cobertura.
- Usiminas 3T25: `3.04.05 Outras Despesas Operacionais` de -2.346.416 (p. 14), contra -113.945 no 3T26: é o impairment de R$ 2,23 bi do 3T25 (release, p. 44). Lucro líquido A/A da Usiminas não é comparável sem esse ajuste.
- Na DRE da Gerdau (p. 29–30) o texto extraído é limpo; nas notas de segmento (p. 71–74) as letras saem espaçadas ("R eceita líquida").

## Prompts que funcionaram

- Extração complementar: [prompts/extracao_financeira_complementar.md](../../prompts/extracao_financeira_complementar.md). Para não digitar nenhum número, a montagem do JSON foi feita por um script que recebe (página, início da linha, coluna) e copia trecho e token literais do `pagina_NN.txt`.
- Reconciliações conferidas em código antes de gravar:
  - Usiminas 3T26: 588.039 − 80.452 + 50.430 = 558.017 (p. 28)
  - Usiminas 3T25: −1.747.170 − 91.216 + 46.177 + 2.226.332 = 434.123 (p. 28)
  - Gerdau 3T26: 3.350.950 − 532.654 − 119.203 + 937.901 + 193.594 − 60.412 = 3.770.176 (p. 72)
  - Usiminas dívida líquida 3T26: 6.276.500 − 6.747.169 = −470.669 (p. 32)

## Estado e próximos passos (para retomar numa nova sessão)

**CASE-02: código e dados prontos.** 129 testes passando no repo inteiro (`.venv/bin/pytest -q tests`).
- `src/dfs_cvm.py`: parser CVM; `metricas/{gerdau,usiminas}_3T26_itr_dfs.json` 62/62 OK.
- `metricas/*_itr_complementar.json` gerados por `scripts/montar_complementar_3T26.py`; Gerdau 9 REVISAR, Usiminas 23 OK + 6 REVISAR.
- `src/verificar_numeros.py` endurecido (coluna × cabeçalho, unidade, escopo, `revisao_manual`, formato legado sem `chave` → REVISAR).

**Pendências**
1. A branch local foi rebaseada sobre o `main` e está à frente da remota: falta `git push --force-with-lease` (bloqueado pela permissão na sessão anterior).
2. Revisão manual de 15 itens, depois registrar `"revisao_manual": {"por": "Gabriel Martins", "nota": "..."}` no script de montagem e regerar:
   - Gerdau p. 72–73: cabeçalho espaçado; conferir que a 1ª coluna do bloco Consolidado é 30/09/2026 (a receita 18.690.518 bate com a DRE 3T26, p. 29).
   - Usiminas p. 32: dívida bruta/líquida; confirmar que é consolidado (o release p. 24 diz "Valores Consolidados") e a ordem 30-set-26 / 30-jun-26 / 30-set-25.
3. Abrir PR `feat/gabriel-martins` → `main` (fecha o CASE-02).
4. Avisar o dono do CASE-04: filtrar `ajuste_ebitda` por `natureza == "pontual"` no alerta de efeito pontual; dívida líquida da Usiminas calculada × reportada difere pelos tributos parcelados (95.333).
5. Depois: CASE-07 (`src/pipeline.py`), ver `docs/TAREFAS.md`.
