# Registro — Gabriel Martins (CASE-02 e CASE-07)

## Erros encontrados

| # | Empresa | Métrica | O que o Claude/código disse | O que estava no ITR (pág.) | Como pegamos | Correção |
|---|---|---|---|---|---|---|
| 1 | (teste) | Lucro bruto | identidade lucro_bruto = receita + cpv quebrada de propósito | DRE consolidada | `checar_consistencia` no `dfs_cvm.py` | o parser recusa gravar o JSON (exit 1) |
| 2 | — | Verificador original | um número que existe na página "conferia" mesmo estando na coluna de outro período (ex.: 3T25 no lugar do 3T26) ou na página das DFs Individuais | — | teste `test_numero_existe_na_pagina_mas_na_coluna_errada` | verificador passou a checar coluna, período, unidade e escopo |

| 3 | Usiminas | D&A 9M26 | release (p. 45): 735.383 | DFC consolidada (p. 16): 735.386 | comparação DFC × release | diferença de R$ 3 mil; usamos a DFC nas DFs e o release no complementar, cada um com sua página |
| 4 | Usiminas | Dívida bruta | soma das DFs: emprestimos_cp + emprestimos_lp = 6.181.166 | release (p. 32): 6.276.500 | comparação DFs × release | a reportada inclui tributos parcelados (95.333); o CASE-04 deve mostrar as duas e explicar |
| 5 | Gerdau | EBITDA ajustado | a reconciliação da p. 74 sai com dígitos espaçados ("3 .7 7 0 .1 7 6"): o verificador não acha o token | p. 72 (coluna Consolidado, texto limpo): 3.770.176 | verificador | usamos a p. 72 |
| 6 | Usiminas / Gerdau | Dívida (p. 32) / EBITDA e D&A por segmento (p. 72–73) | Usiminas p. 32 sem a palavra "consolidado"; Gerdau com cabeçalho de colunas espaçado ("3 0 /0 9 /2 0 2 6") | — | verificador marcou REVISAR (15 itens): não dá para provar por código qual coluna é qual período | conferência visual das páginas renderizadas + âncoras (receita = DRE; caixa da p. 32 = soma do BP consolidado p. 12); registrado em `revisao_manual` em cada fato |

| 7 | Usiminas | EBITDA CVM 156 (3T26, 2T26, 3T25, 9M26, 9M25) | **o "156" de "Instrução CVM 156" foi lido como a coluna do 3T26**: 3T26 = 156, 2T26 = 588.039 (era o 3T26), 3T25 = 798.602 (era o 2T26); na linha acumulada, "(Instrução CVM 156)" virou o token "156)" | p. 28: 588.039 / 798.602 / (1.747.170); p. 45: 2.041.362 / (547.928) | o verificador original **aprovou** (cada número existia na linha); quem pegou foi a reconciliação recalculada a partir do JSON (CVM 156 + ajustes ≠ EBITDA ajustado) | verificador passou a exigir `cabecalho_colunas` e a conferir o rótulo da coluna contra o período; regex de número exige parênteses balanceados; testes `test_numero_no_nome_da_conta_nao_vira_coluna` e `test_parentese_sem_par_nao_e_numero` |

| 8 | Usiminas | Dívida bruta | o texto extraído não deixa claro, mas a imagem da p. 32 mostra **três** medidas de dívida: "Dívida Bruta" 6.276.500 (com tributos parcelados), "Dívida Bruta (Somente Principal)" 6.121.577 e a soma das DFs 6.181.166 | p. 32 renderizada | conferência visual | usamos a "Dívida Bruta" (base da Dívida Líquida reportada); o CASE-04 deve dizer qual critério usa |

**CASE-07 (pipeline)**

| # | Empresa | Etapa | O que o Claude/código fez | O que devia | Como pegamos | Correção |
|---|---|---|---|---|---|---|
| 9 | Gerdau / Usiminas | prompt genérico (etapa 4) | o `.replace("<slug>", slug)` do prompt também trocou o exemplo `segmento:<slug>` por `segmento:gerdau`: o prompt mandava usar o nome da empresa como segmento | `segmento:<segmento>` (ex.: `america_do_norte`) | lendo o prompt impresso na primeira rodada real | placeholder do exemplo renomeado |
| 10 | — | assistidos sem PDF-fonte | faltando só o qualitativo (sem apresentação), o pipeline seguia e parava na verificação com "Verificação reprovada", sendo que nenhum fato tinha erro | parar com "insumo ausente" e dizer qual PDF falta | revisão do log da rodada real | pendência sem documento-fonte para com código 2 e cita `data/apresentacoes/<slug>_APRESENTACAO_<tri>.pdf` |
| 11 | — | relatório no terminal | "PAROU em ..." (stderr) aparecia antes do log das etapas (stdout com buffer) | mensagem de parada no fim | primeira rodada real | `flush` no log antes da parada |
| 12 | (teste) | helper do teste | o Claude converteu `(50)` com `float()` e quebrou a fixture | negativo entre parênteses = −50 | pytest | helper usa `br_para_float` do verificador |
| 13 | — | modo rascunho | `--permitir-pendencias` **sobrescreveu os `metricas/*_indicadores.json` versionados do CASE-04** com uma versão sem os fatos reprovados | rascunho não pode tocar arquivo oficial | `git status` depois da rodada de 14h30 | derivados do rascunho vão para `saida/rascunho/<a>_x_<b>_<tri>/`; teste `test_rascunho_nao_toca_arquivos_oficiais` |
| 14 | — | modo rascunho | o HTML do rascunho era idêntico ao final; só o nome do arquivo dizia "RASCUNHO" | rascunho identificado no próprio slide | abrindo o HTML gerado com o CASE-06 | faixa fixa "RASCUNHO — NÃO ENTREGAR" com nº de fatos reprovados |
| 15 | — | troca de PDF | PDF republicado com o mesmo nome reaproveitava páginas e DFs antigas, e a verificação **passava** (comparava com as páginas velhas) | re-extrair quando o PDF muda | revisão do fluxo "trocar só os PDFs" | carimbo sha256 em `saida/<pdf>/_origem.sha256` (ITR: também o manifesto); teste `test_pdf_trocado_reextrai_e_refaz_dfs` |
| 16 | Usiminas | alerta de efeito pontual (CASE-04) | "ajustes não recorrentes somam 544% do EBITDA do 3T25" somando itens recorrentes (participação em controladas, EBITDA proporcional) | só o impairment: 513% | lendo os alertas do comparativo | corrigido pelo Gabriel Patrício na `feat/gabriel-patricio` (filtra `natureza`); confirmado na rodada integrada |

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

- CASE-07: o pipeline gera o prompt de cada JSON assistido faltante a partir de `prompts/<arquivo>.md` (troca `<slug>`/`<tri>`) e anexa as páginas candidatas; o texto também fica salvo em `saida/prompts/<slug>_<tri>_<doc>_<tipo>.md`. Sem o arquivo do CASE-03, usa um prompt mínimo que aponta para o contrato.

## Estado e próximos passos (para retomar numa nova sessão)

**CASE-02 concluído e mergeado** (PR #3). `*_itr_dfs.json` 62/62 OK cada; complementares 9/9 e 29/29 OK.

**CASE-07 pronto do lado do pipeline** — `src/pipeline.py` + `tests/test_pipeline.py` (22 testes).
- Rodada de 14h45 (main + CASE-06 da `feat/gabriel-patricio` num worktree): `--permitir-pendencias` vai **até o fim** e gera os 8 slides em `saida/rascunho/gerdau_x_usiminas_3T26/RASCUNHO_*.html`, com faixa de rascunho, aviso "Não constitui recomendação" e páginas. Funciona com A/B invertidos e é idempotente.
- Sem a flag, **bloqueia na verificação**: 177/243 OK, 38 ERROs, todos nos operacionais do CASE-03 (`gerdau_..._apresentacao_operacional` 17, `usiminas_..._itr_operacional` 12, `usiminas_..._apresentacao_operacional` 9: unidade fora do contrato, `valor_como_aparece` nulo, trecho sem o valor). Meus arquivos e os qualitativos: 100% OK e válidos no `contrato.py`.
- Para a entrega final faltam: (1) CASE-03 corrigir os 38 ERROs; (2) CASE-06 mergeado (a `feat/gabriel-patricio` conflita com o main em `metricas/*_indicadores.json` e no registro dela: precisa de rebase).
- Decisão: REVISAR não bloqueia (só ERRO); aparece no relatório.

**Avisos para o time**
- CASE-04: aprovado, o pipeline regrava `metricas/<slug>_<tri>_indicadores.json` com a mesma serialização do CLI (byte a byte igual com os mesmos fatos); rascunho nunca toca esse arquivo.
- CASE-06: o pipeline chama `apresentacao.py --comparativo --metricas --saida` e copia para `entrega/` só se a verificação estiver aprovada.
- Testes: `pytest` puro não importa `tests/test_localizar_paginas.py` (`from src. ...`); use `python -m pytest`. `test_catalogo` falha por causa dos operacionais do CASE-03 (já falhava no main).
- CASE-04: filtrar `ajuste_ebitda` por `natureza == "pontual"`; dívida líquida da Usiminas calculada × reportada difere pelos tributos parcelados (95.333).

**Próximo:** depois que CASE-03 corrigir e CASE-06 mergear: `git pull --rebase origin main` e `python src/pipeline.py --a gerdau --b usiminas --tri 3T26` (sem flag) até `entrega/apresentacao_gerdau_x_usiminas_3T26.html`.
