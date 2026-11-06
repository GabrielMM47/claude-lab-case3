# Erros encontrados e como foram corrigidos

Consolidação dos registros individuais em [`docs/registro/`](registro/). Todos são casos reais desta rodada (Gerdau × Usiminas, 3T26). Páginas sempre no índice do PDF (o mesmo número do `pagina_NN.txt`), não o número impresso na folha. Os casos marcados com ★ são os usados no vídeo e no README.

## Extração e verificação dos números

| # | Empresa | Métrica · página | O que o Claude/código disse | O que estava no documento | Como pegamos | Correção |
|---|---|---|---|---|---|---|
| 1 ★ | Usiminas | EBITDA CVM 156 · ITR p. 28 | O "156" de "Instrução CVM 156" foi lido como o EBITDA do 3T26; cada valor escorregou uma coluna (3T26 = 156; 2T26 = 588.039, que era o 3T26) | 3T26 = 588.039; 2T26 = 798.602; 3T25 = (1.747.170) | O verificador original **aprovou** (cada número existia na linha). Pegou a reconciliação recalculada: CVM 156 + ajustes ≠ EBITDA ajustado | Verificador exige o cabeçalho das colunas e confere o período de cada coluna; número entre parênteses só vale com parênteses balanceados |
| 2 | — | Verificador original | Número existente na página "conferia" mesmo na coluna de outro período ou na página das DFs individuais | — | Teste com coluna trocada de propósito | Verificador passou a checar coluna, período, unidade e escopo |
| 3 ★ | Usiminas | Receita de mineração por t · apresentação p. 28 | US$ 87/t no 3T25 | US$ 79 no 3T25 (os US$ 87 são do 4T25 e do 1T26) | Verificador: "valor fora do trecho"; a página renderizada mostrou o trimestre errado | Valor 79, trecho com a linha literal e revisão manual registrada |
| 4 ★ | Gerdau | Volume, receita e EBITDA por divisão · apresentação p. 18–20 | `valor_como_aparece` nulo: "a extração fragmenta os dígitos"; valores transcritos olhando o slide | O texto extraído triplica cada caractere (negrito falso): `111...555888222` = 1.582 | Contrato recusou os 17 fatos sem literal | Verificador reconhece a forma triplicada (tokens de 3+ caracteres); os 17 fatos ganharam trecho literal e revisão manual |
| 5 | Usiminas | Operacionais · ITR p. 24 e 36, apresentação | Trecho = só o título da linha ("Volume de Vendas Aço (mil t)"), sem o número | A linha inteira, com a coluna provada pelo cabeçalho (`3T26 2T26 ∆ 3T25 ∆`) | Verificador: "existe na página, mas não no trecho" | 21 fatos refeitos com a linha literal e o cabeçalho das colunas |
| 6 | Gerdau / Usiminas | Unidades e períodos | `"1.000 toneladas"`, `"mil toneladas"`, `"Mil toneladas"`, `"milhões de toneladas/ano"`, período `"3T26 vs 2T26"` | Vocabulário do contrato (`mil t`); período é um trimestre | Contrato dentro do pipeline (37 violações) | Unidades padronizadas; capacidades e a variação T/T foram para a cobertura com motivo |
| 7 | Gerdau | EBITDA ajustado · ITR p. 72–74 | A reconciliação da p. 74 sai com dígitos espaçados (`3 .7 7 0 .1 7 6`) e o verificador não acha o token | p. 72, coluna Consolidado, texto limpo: 3.770.176 | Verificador | Usada a p. 72 |
| 8 | Usiminas | Página sem texto · apresentação p. 40 | — | A página saiu sem texto na extração | Inspeção da pasta extraída | Não usada como evidência |

## Conflitos entre fontes

| # | Empresa | Métrica · páginas | Divergência | Tratamento |
|---|---|---|---|---|
| 9 | Usiminas | Dívida bruta · ITR p. 32 | Três medidas: "Dívida Bruta" 6.276.500 (com tributos parcelados), "Somente Principal" 6.121.577 e soma das DFs 6.181.166 (R$ mil) | Usada a "Dívida Bruta", base da dívida líquida reportada; o alerta de 17% entre calculada e reportada aparece no slide |
| 10 | Usiminas | D&A 9M26 · ITR p. 16 e 45 | DFC 735.386 × release 735.383 (R$ mil) | DFC nas DFs, release no complementar, cada um com sua página |

## Indicadores, comparativo e apresentação

| # | Empresa | O que o código fez | O que devia | Como pegamos | Correção |
|---|---|---|---|---|---|
| 11 | Usiminas | Alerta "ajustes não recorrentes somam 544% do EBITDA do 3T25", somando ajustes recorrentes (equivalência, EBITDA proporcional) | Só o impairment é pontual: 513% (ITR p. 28) | Primeira rodada com o complementar real | Só ajustes com `natureza: "pontual"` contam; os alertas falsos de 3T26 e 2T26 sumiram |
| 12 ★ | Usiminas | Slide de destaques mostrava "+ Margem líquida 3,9% (+57,0 p.p. A/A)" como o melhor resultado, ao lado do alerta de impairment | O impairment do 3T25 (ITR p. 28) está no lucro e no EBIT; a variação A/A dessas linhas engana | Leitura dos slides gerados com dados reais | Com efeito pontual, o gerador ignora a variação A/A das linhas contábeis; o destaque negativo passou a ser a receita (-6,1% A/A) |
| 13 | Usiminas | Volume de vendas escolhido pela ordem de leitura dos arquivos: com outra ordem, o volume de minério viraria volume de aço | ITR p. 24: aço 1.034 e minério 2.014 mil t | Alerta de divergência entre valores do mesmo documento | Valores diferentes no mesmo escopo viram alerta "ambíguo" (N/D com motivo); minério foi para o segmento mineração |
| 14 | Gerdau | "MT" convertido como milhões de t | O mesmo arquivo trazia 6884 MT e 0,9 MT (apresentação p. 7, 8 e 12) | Revisão das unidades | Unidade ambígua é ignorada com alerta, nunca adivinhada |
| 15 | — | Receita, EBITDA e lucro com `melhor: maior`: o comparativo elegeria vencedor por tamanho | "Maior receita não é melhor desempenho" | Leitura do indicadores.json real | Valores absolutos não elegem vencedor |
| 16 | — | Mapa de páginas do CLAUDE.md dizia "páginas impressas" | DRE consolidada da Gerdau: índice 29 do PDF, impressa como 24 | Comparação com os `pagina_NN.txt` | Página é sempre o índice do PDF; o slide de metodologia avisa |
| 17 | — | Slugs crus nos gráficos (`america_do_norte`) | Rótulo legível | Leitura dos gráficos | Tabela `[segmentos]` em `config/empresas.toml` |

## Pipeline de um comando

| # | O que o código fez | O que devia | Como pegamos | Correção |
|---|---|---|---|---|
| 18 | O modo rascunho (`--permitir-pendencias`) sobrescreveu os `metricas/*_indicadores.json` oficiais com uma versão sem os fatos reprovados | Rascunho não pode tocar arquivo oficial | `git status` depois da rodada | Derivados do rascunho vão para `saida/rascunho/`; teste dedicado |
| 19 | O HTML do rascunho era idêntico ao final; só o nome do arquivo dizia "rascunho" | Rascunho identificado no próprio slide | Abrindo o HTML | Faixa fixa "RASCUNHO — NÃO ENTREGAR" com o número de fatos reprovados |
| 20 | PDF republicado com o mesmo nome reaproveitava as páginas antigas, e a verificação passava contra o texto velho | Re-extrair quando o PDF muda | Revisão do fluxo "trocar só os PDFs" | Carimbo sha256 do PDF; teste com PDF trocado |
| 21 | O prompt gerado trocava o exemplo `segmento:<slug>` pelo nome da empresa (`segmento:gerdau`) | `segmento:<segmento>` (ex.: `america_do_norte`) | Leitura do prompt impresso | Marcador do exemplo renomeado |
| 22 | Sem a apresentação institucional, o pipeline parava com "verificação reprovada", sem nenhum fato errado | Parar com "insumo ausente" e dizer qual PDF falta | Log da rodada real | Código de saída 2 com o caminho do PDF |

## Limitações ainda abertas

- 37 fatos operacionais sem evidência literal completa de período/unidade/escopo ("para revisar"): não bloqueiam a entrega e aparecem no relatório de verificação.
- A Gerdau não divulga volume consolidado em texto verificável; R$/t e EBITDA/t da Gerdau ficam N/D.
- Dívida líquida/EBITDA com EBITDA 9M26 anualizado, não o dos últimos 12 meses que as empresas divulgam.
