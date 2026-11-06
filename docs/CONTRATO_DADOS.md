# Contrato de dados, catálogo e fixtures — guia

Leia antes o [caminho avançado](GUIA_TECNICO.md) e o [extrator do balanço](EXTRATOR_BALANCO.md). Este guia cobre quatro coisas: o **contrato** (a forma que um JSON precisa ter, checada por `src/contrato.py`), o **verificador** (resumo do que ele faz hoje), o **catálogo** dos dados e as **fixtures** com os testes. O contrato oficial do time para os JSONs de fatos é a seção "Contrato de dados" de [TAREFAS.md](TAREFAS.md); o schema `fato` é a versão em JSON Schema dela. O desenho completo está no SPEC em `claude-lab-case3-planejamento/SPEC_contrato_catalogo_fixtures.md`, fora do repo.

São duas etapas separadas. Primeiro `src/contrato.py` valida a **forma** do JSON (campos, tipos, unidades permitidas) e sai com código 2 se algo estiver errado. Depois `src/verificar_numeros.py` confere **cada número contra o PDF** e classifica cada fato em OK, REVISAR ou ERRO. O verificador não chama o contrato: quem quiser as duas checagens roda os dois comandos.

```bash
python src/contrato.py metricas/metricas_gerdau.json           # valida a forma do JSON
python src/verificar_numeros.py saida/gerdau_ITR_3T26 metricas/metricas_gerdau.json
python src/gerar_catalogo.py                                    # regenera o catálogo
python src/gerar_catalogo.py --check                            # diz se está em dia
pytest                                                          # testes, sem PDF
pytest --com-pdf                                                # inclui os testes com data/itrs/*.pdf
```

---

## Parte 1 — Contrato

### Os quatro schemas

Os schemas ficam em `schemas/` e seguem o JSON Schema Draft 2020-12. Validam forma e tipos. Não conferem números.

| Arquivo | Valida | Usado para |
|---|---|---|
| `schemas/metricas.schema.json` | Registro-base: a lista de métricas que o time extrai (`metricas/metricas_<empresa>.json`). | Qualquer JSON que não seja balanço. |
| `schemas/balanco.schema.json` | Contas do balanço: o registro-base mais 12 campos próprios (19 obrigatórios). Campo fora da lista é rejeitado. | `metricas/balanco_<empresa>[_controladora].json`. |
| `schemas/balanco_meta.schema.json` | Metadados gravados pelo extrator. | `metricas/balanco_*.meta.json`. |
| `schemas/fato.schema.json` | Fatos do contrato do time ([TAREFAS.md](TAREFAS.md), "Contrato de dados"): `chave`, `empresa`, `documento`, `escopo`, `periodo`, `evidencia`, `revisao_manual`... | `metricas/<slug>_<tri>_itr_*.json` e `*_apresentacao_*.json`. |

O `escolher_schema` decide sozinho: se algum item tem a chave `chave`, usa `fato`; se tem `demonstracao`, usa `balanco`; senão, `metricas`. Para forçar, use `--schema` no `src/contrato.py`. O `metricas/catalogo.json` é ignorado.

O `status` do `.meta.json` é a **autovalidação do extrator** (V01 a V08 de [EXTRATOR_BALANCO.md](EXTRATOR_BALANCO.md)). Não é o resultado do verificador.

### Campos do registro-base

| Campo | Obrigatório | Regra |
|---|---|---|
| `metrica` | sim | Texto não vazio. Se contiver `EBITDA` em qualquer caixa, exige `criterio_ebitda`. |
| `periodo` | sim | Texto livre, ex.: `3T26 vs 3T25`. O rótulo formal fica em `base_comparacao`. |
| `unidade` | sim | Um destes valores: `R$ mil`, `R$ milhões`, `%`, `p.p.`, `mil t`, `R$/t`, `x`. |
| `valor` | sim | Número JSON (sem aspas), na mesma escala de `valor_como_aparece`. |
| `valor_como_aparece` | sim | Texto literal do número no PDF, ex.: `12.345,6`, `21,4%`. |
| `anterior` | não | Número do período de comparação. Exige `anterior_como_aparece`. |
| `anterior_como_aparece` | não | Texto literal do período de comparação. Exige `anterior`. |
| `variacao_pct` | não | Variação em %. Exige `anterior`. O verificador recalcula e compara. |
| `pagina` | sim | Inteiro maior ou igual a 1: índice da página no PDF (base 1), o mesmo `NN` de `pagina_NN.txt`. |
| `trecho` | sim | Texto de pelo menos 5 caracteres. Cópia literal da linha de `pagina_NN.txt` que contém o número. |
| `base_comparacao` | não (recomendado) | `A/A` (3T26 × 3T25), `T/T` (3T26 × 2T26) ou `posição` (saldo de balanço). |
| `visao` | não no registro-base | `consolidado` ou `controladora`. Use sempre `consolidado`. No balanço é obrigatório. |
| `criterio_ebitda` | sim, se `metrica` tem EBITDA | `contábil` ou `ajustado`. O mesmo critério para as duas empresas. |

Regras que o schema aplica entre campos:

- **Pares:** `anterior` e `anterior_como_aparece` aparecem juntos. `variacao_pct` exige `anterior`.
- **EBITDA:** `EBITDA ajustado`, `Margem Ebitda` e `ebitda` exigem `criterio_ebitda`.
- **`base_comparacao` não é obrigatório no schema.** Quem exige o preenchimento é a regra do `CLAUDE.md`: preencher sempre que houver `anterior`.
- **`p.p.` e `variacao_pct`:** não use `variacao_pct` em métrica de margem. Ela seria recalculada como variação relativa. Registre a diferença em `p.p.` como métrica própria.

A `unidade` é a do documento. Demonstrações vêm em `R$ mil`. O release da Usiminas mistura `R$ mil` e `R$ milhões`. A conversão para a mesma unidade fica na etapa de comparação, nunca no JSON verificado.

### Fato (`fato.schema.json`)

É o contrato do time para os JSONs `metricas/<slug>_<tri>_itr_*.json` e `*_apresentacao_*.json` ([TAREFAS.md](TAREFAS.md), "Contrato de dados"; em caso de dúvida, vale o TAREFAS.md). A lista não pode estar vazia e campos não listados são permitidos, como diz o contrato.

- Obrigatórios em todo fato: `chave` (minúsculas, dígitos e `_`), `metrica`, `empresa` (slug), `documento` (`itr` ou `apresentacao`), `pagina` (inteiro a partir de 1) e `trecho`.
- Para fatos numéricos (todos, exceto `chave` igual a `qualitativo`) também são obrigatórios `escopo` (`consolidado` ou `segmento:<nome>`), `periodo` (`3T26`, `9M26`...), `unidade`, `valor` e `valor_como_aparece`. Fato `qualitativo` exige `tema` e `resumo`.
- `unidade` aceita `R$ mil`, `R$ milhões`, `R$ bilhões`, `mil t`, `mil t/ano`, `R$/t`, `US$/t`, `%` e `x`; `criterio` é `contabil` ou `ajustado`; `tipo` é `fluxo` ou `saldo`.
- `revisao_manual`, se presente, exige `por` e `nota`. É o que o verificador usa para transformar um REVISAR em OK.
- **Contexto macro** (`metricas/<slug>_<tri>_<itr|apresentacao>_macro.json`): o que a própria empresa publica sobre o mercado (importações, defesa comercial, tarifas, demanda, minério e insumos). Número vai com `chave` = `contexto_macro` (mesmos campos de um fato numérico); afirmação sem número vai como `qualitativo` com `tema` = `contexto_macro`. Os dois levam `id` (estável, citado pela narrativa como `{a.macro.<id>}` ou em `"cita": ["a.<id>"]`) e `resumo` sem dígitos. O verificador confere igual aos demais; os indicadores ignoram esses fatos (não são resultado da empresa).

### Balanço (`balanco.schema.json`)

- Os 19 campos obrigatórios são os 7 do registro-base mais 12 próprios: `anterior`, `anterior_como_aparece`, `codigo_conta`, `descricao`, `codigo_pai`, `nivel`, `demonstracao`, `visao`, `empresa`, `data_atual`, `data_anterior`, `ambiguo`.
- `unidade` tem de ser `R$ mil` (o extrator só aceita `(Reais Mil)`).
- `valor` e `anterior` são inteiros.
- `codigo_conta` começa com `1` ou `2` e segue o padrão `1`, `1.01`, `2.03.05`. `codigo_pai` é `null` só na conta de nível 1.
- `variacao_pct` e `criterio_ebitda` são proibidos (balanço compara posições e não tem EBITDA). `base_comparacao`, se aparecer, só pode ser `posição`.
- Campo que não está na lista é rejeitado.

### O que o schema não confere

- Não compara `valor` com `valor_como_aparece`, não recalcula variação e não soma contas.
- Não confere se `trecho` ou `valor_como_aparece` estão na página. Isso é do verificador (`src/verificar_numeros.py`).
- Não confere se a data é real. Confere só o formato `AAAA-MM-DD`.
- No balanço, não confere as somas (V04 a V06 ficam no extrator).

### Como validar um JSON

```bash
python src/contrato.py ARQUIVO [ARQUIVO ...] [--schema {auto,metricas,balanco,balanco_meta,fato}]
```

Com `auto` (o padrão), um arquivo que termina em `.meta.json` usa `balanco_meta`, e os demais usam `escolher_schema` (`fato`, `balanco` ou `metricas`). Para cada arquivo, a saída é:

```
<arquivo>: válido (<nome>)
<arquivo>: <n> erro(s) (<nome>)
  <caminho>: <mensagem>
```

Código de saída: 0 se todos forem válidos; 2 se algum for inválido, ilegível ou se o uso for inválido. Arquivo ausente ou JSON sintaticamente inválido sai em stderr como `ERRO: <mensagem>`, por exemplo `ERRO: JSON inválido em <caminho>: linha <l>, coluna <c>: <msg>`.

### Mensagens do `contrato.py`

O caminho do erro aponta para o campo: `$` é a raiz, `$[0]` é o primeiro registro, `$[0].pagina` é o campo `pagina` do primeiro registro, `$.paginas.ativo[0]` aparece no meta. Exemplo, com o registro sem `pagina` (fixture `sem_pagina.json`):

```
tests/fixtures/invalidos/sem_pagina.json: 1 erro(s) (metricas)
  $[0].pagina: campo obrigatório ausente
```

Mensagens mais comuns:

| Mensagem | Quando aparece |
|---|---|
| `campo obrigatório ausente` | Falta um campo exigido. |
| `campo obrigatório quando '<campo>' está presente` | `anterior` sem `anterior_como_aparece` (ou o par contrário). |
| `métrica de EBITDA exige 'criterio_ebitda' ("contábil" ou "ajustado")` | Métrica com EBITDA sem critério. |
| `esperado número, veio texto ("12345.6")` | Tipo errado: número escrito entre aspas. |
| `0 é menor que o mínimo 1` | `pagina` igual a 0. |
| `valor "R$ MM" fora da lista permitida: ...` | Valor fora do enum de `unidade`. |
| `valor "x" não segue o padrão ...` | Texto fora do padrão (ex.: código de conta). |
| `texto curto demais (3 caractere(s); mínimo 5)` | `trecho` curto demais. |
| `campo não previsto no contrato` | Campo extra no balanço. |
| `campo não permitido neste contrato` | Campo proibido (ex.: `variacao_pct` no balanço). |
| `valor "A/A" deveria ser "posição"` | Valor fixo diferente (balanço com `base_comparacao`). |

Se houver mais de 50 erros, o `contrato.py` mostra as 50 primeiras e diz quantos sobraram.

### Verificador: o que ele faz hoje

```
python src/verificar_numeros.py PASTA ARQUIVO [--estrito] [--relatorio ARQ.json]
```

O verificador (dono: CASE-02) não valida o contrato: ele lê o JSON e confere cada fato contra `saida/<pdf>/pagina_NN.txt`. Cada fato recebe um destes resultados:

| Resultado | Significado |
|---|---|
| `OK` | Conferido literalmente contra o PDF (trecho na página, valor como token inteiro, variação recalculada, evidências de período, unidade e escopo coerentes). |
| `REVISAR` | A automação não comprovou o vínculo: falta evidência (`evidencia.periodo`, `evidencia.unidade`, `evidencia.escopo`, coluna), ou o JSON está fora do contrato. Vira OK só com `revisao_manual` (`por` e `nota`) no fato. |
| `ERRO` | Algo não bate com a página: trecho ausente, valor ou variação divergente, escopo individual, etc. |

| Código | Significado |
|---|---|
| 0 | Nenhum ERRO (REVISAR não muda o código). |
| 1 | Pelo menos um ERRO, ou pelo menos um REVISAR com `--estrito`. |

A última linha resume: `<ok>/<total> conferem · <n> para revisar · <n> com erro.` O `--relatorio` grava o resultado em JSON. Fato sem `chave`, `documento` ou `escopo` (formato legado, como os `balanco_*.json`) sai como REVISAR com a mensagem `fora do contrato (sem chave, documento, escopo): não entra no pipeline`.

Exemplo real: `metricas/gerdau_3T26_itr_dfs.json` contra `saida/gerdau_ITR_3T26` dá `62/62 conferem · 0 para revisar · 0 com erro.`

Para a entrega, rode as duas etapas: `contrato.py` para a forma e `verificar_numeros.py` para os números. Um JSON só vale para o pipeline se passar na primeira e não tiver ERRO (nem REVISAR sem revisão manual) na segunda.

### Erros comuns e como corrigi-los

As fixtures em `tests/fixtures/invalidos/` têm um registro cada, com um erro cada. Elas são validadas pelo `contrato.py` (não pelo verificador) e servem de exemplo:

| Fixture | Erro | Correção |
|---|---|---|
| `sem_pagina.json` | Falta `pagina`. | Incluir o índice da página no PDF (base 1), igual ao `NN` de `pagina_NN.txt`. |
| `pagina_zero.json` | `pagina` é 0. | O índice começa em 1. |
| `unidade_invalida.json` | `unidade` é `R$ MM`. | Usar um dos 7 valores da lista. Em milhões, `R$ milhões`. |
| `valor_string.json` | `valor` está entre aspas. | Escrever o número sem aspas (`12345.6`). O texto do PDF vai em `valor_como_aparece`. |
| `sem_trecho.json` | Falta `trecho`. | Copiar a linha inteira de `pagina_NN.txt` que contém o número. |
| `ebitda_sem_criterio.json` | Métrica de EBITDA sem `criterio_ebitda`. | Incluir `"contábil"` ou `"ajustado"`, o mesmo critério para as duas empresas. |
| `base_comparacao_invalida.json` | `base_comparacao` com texto livre (`3T26 vs 3T25`). | Usar `A/A`, `T/T` ou `posição`. O período em texto vai em `periodo`. |
| `anterior_sem_literal.json` | `anterior` sem `anterior_como_aparece`. | Copiar o número do período de comparação da página e colocar em `anterior_como_aparece`. |

### Prompt sugerido

Para pedir o JSON ao Claude, inclua a exigência do schema no próprio pedido:

> Gere `metricas/metricas_gerdau.json` no formato de `templates/metricas_exemplo.json`. O JSON tem de validar em `schemas/metricas.schema.json`. Cada número traz `pagina`, `trecho` e `valor_como_aparece` copiados de `saida/gerdau_ITR_3T26/pagina_NN.txt`.

Depois, rode `python src/contrato.py metricas/metricas_gerdau.json` (forma) e `python src/verificar_numeros.py saida/gerdau_ITR_3T26 metricas/metricas_gerdau.json` (números).

---

## Parte 2 — Verificador (resumo)

O comportamento completo está no docstring de `src/verificar_numeros.py` e no card CASE-02 de [TAREFAS.md](TAREFAS.md). O que importa aqui:

- Três níveis por fato: OK, REVISAR e ERRO (tabela da Parte 1). Não há nível de aviso.
- REVISAR é o padrão quando falta evidência literal. O time resolve incluindo `evidencia` no fato ou registrando `revisao_manual`.
- A busca do valor é por token inteiro, dentro do `trecho` e na página. Número curto como `0` exige atenção à coluna (`evidencia.coluna`/`n_colunas`); trecho com vários números e sem coluna vira REVISAR.
- Escopo: texto de controladora, holding ou DFs individuais sem evidência de consolidado não passa como OK.
- `--estrito` faz o REVISAR também sair com código 1, útil para fechar a entrega.

---

## Parte 3 — Catálogo de dados

O catálogo responde, num só lugar: quais PDFs são a fonte, quais artefatos foram produzidos a partir deles, se cada um passa no contrato, qual foi o resultado do verificador e o que ainda falta.

| Arquivo | Quem edita | Para que serve |
|---|---|---|
| `catalogo/fontes.toml` | Time, à mão | Cadastro das fontes e dos artefatos esperados. |
| `metricas/catalogo.json` | Gerado | Versão estruturada, para programas. |
| `docs/CATALOGO_DADOS.md` | Gerado | Versão para leitura. |

**Não edite os dois arquivos gerados à mão.** A mudança some na próxima geração.

### Como gerar e como conferir

```bash
python src/gerar_catalogo.py            # grava docs/CATALOGO_DADOS.md e metricas/catalogo.json
python src/gerar_catalogo.py --check    # não grava nada; diz se está em dia
```

Na geração, o terminal mostra `→ docs/CATALOGO_DADOS.md · metricas/catalogo.json` e um resumo de `saida/`, uma linha por fonte: `saida/<stem>: <n> páginas de texto, <k> tabelas` ou `saida/<stem>: ausente`. O resumo de `saida/` não entra nos arquivos.

No `--check`, cada arquivo diferente ou ausente sai como `desatualizado: <arquivo> (rode: python src/gerar_catalogo.py)`, com código 1. Se tudo bater, a saída é `catálogo em dia`, com código 0. Rode o `--check` depois de mudar um JSON de métricas ou um meta.

| Código | Significado |
|---|---|
| 0 | Gravou, ou `--check` em dia. |
| 1 | `--check` divergente. |
| 2 | `catalogo/fontes.toml` ausente ou inválido, JSON ilegível em `metricas/`, uso inválido. |

### Duas verificações diferentes

| | Autovalidação do extrator | Verificador |
|---|---|---|
| Onde aparece | `status` no `.meta.json` | Coluna "Verificador" do catálogo |
| O que checa | V01 a V08 do balanço (contas, somas, ordem) | Conferência de cada fato contra `saida/<stem>/` (OK, REVISAR, ERRO) |
| Status | `aprovado` ou `reprovado` | `<ok>/<n> conferem, <r> para revisar, <e> com erro`, `não verificado (saida/ ausente)` e outros |

Um balanço pode estar `aprovado` na autovalidação e ainda ter todos os registros em REVISAR no verificador, porque o formato legado não entra no contrato do time. O catálogo mostra as duas colunas separadas, e a coluna de contrato (`válido` ou `fora do contrato (<n>)`) vem do `contrato.py`, não do verificador.

### Status do verificador no catálogo

| Status | Quando |
|---|---|
| `<n_ok>/<n_total> conferem` | Há `saida/<stem>/` e o verificador rodou (`verificar_numeros.avaliar`). Com REVISAR, acrescenta `, <n> para revisar`; com ERRO, `, <n> com erro`. |
| `não verificado (saida/ ausente)` | Não há `saida/<stem>/` e não há status herdado (ver abaixo). |
| `não verificado (fonte desconhecida)` | Não se sabe de qual PDF o artefato vem. |
| `erro de entrada (ver terminal)` | O JSON não é uma lista de fatos legível. A mensagem vai para o terminal. |
| `pendente` | Artefato esperado (em `fontes.toml`) que ainda não existe. |

No terminal, cada artefato mostra a origem do status: `calculado`, `herdado` ou `não verificado`. Essa origem não entra nos arquivos.

### Herança do status

`saida/` não vai para o Git (está no `.gitignore`). Num clone limpo, o verificador não roda, e sem herança o catálogo mostraria tudo como não verificado.

Por isso, quando `saida/<stem>/` não existe, o gerador usa o status que já está em `metricas/catalogo.json`, **desde que o hash do JSON não tenha mudado** (`json_sha256`). Se o JSON mudou, ou não há registro anterior, o status vira `não verificado (saida/ ausente)`. Assim, o status herdado só vale para o conteúdo exato que foi conferido.

Limitação: o `json_sha256` amarra o status ao JSON, não ao texto das páginas. Se o pdfplumber mudar a extração, só uma regeneração com `saida/` nova atualiza o status.

### Como preencher `catalogo/fontes.toml`

O arquivo tem duas seções: `[[fonte]]` (um por PDF) e `[[esperado]]` (um por artefato que o time ainda vai produzir).

- `url_origem = ""` significa "(a preencher)" no catálogo. **Não invente URL.** Coloque o link de RI ou da CVM quando o time tiver.
- `data_referencia` é a data do período, no formato `AAAA-MM-DD`.
- `stem` é único. Ele é o nome do PDF sem extensão.
- Para cada `metricas/metricas_<empresa>.json` que o time vai gerar, acrescente um `[[esperado]]`. Enquanto o arquivo não existir, ele aparece como `pendente`.

Validação do `fontes.toml`: `versao = 1`; cada `[[fonte]]` tem as 9 chaves (`stem`, `pdf`, `empresa`, `nome`, `tipo`, `periodo`, `data_referencia`, `url_origem`, `descricao`), todas texto; cada `[[esperado]]` tem `artefato`, `fonte` (um dos `stem`) e `descricao`. Violação sai como `ERRO: catalogo/fontes.toml: <detalhe>`, com código 2.

### O que o catálogo mostra

`docs/CATALOGO_DADOS.md` tem estas seções:

- **Fontes:** PDF, empresa, tipo, período, data-base, SHA-256 (12 caracteres), tamanho e origem.
- **Artefatos verificáveis:** visão, unidade e escala original, páginas (Ativo; Passivo), registros (ambíguos), datas, gerado por, contrato, autovalidação, verificador e critério de EBITDA.
- **Arquivos auxiliares:** os `.meta.json` (com contrato do `balanco_meta`) e os `.csv`.
- **Pendentes:** os `[[esperado]]` que ainda não existem.
- **Intermediários não versionados:** `saida/`, explicado em uma linha.

O `metricas/catalogo.json` tem os mesmos dados em forma estruturada: `versao_catalogo`, `fontes`, `artefatos` (em ordem de `caminho`) e `pendentes`. Ele não guarda `gerado_em`, datas de geração nem caminhos absolutos, para que duas gerações iguais deem o mesmo arquivo.

Para o balanço, o campo `criterio_ebitda` vem como `n/a`. Para as métricas, vem a lista de critérios usados nos registros de EBITDA, ou `não informado`.

---

## Parte 4 — Fixtures e testes

### O que são as fixtures

`tests/fixtures/` tem o **texto real** de 10 páginas do Balanço Patrimonial dos ITRs 3T26: consolidado e controladora, da Gerdau e da Usiminas. O texto é copiado do PDF por `scripts/gerar_fixtures.py`, sem edição. As páginas usam o índice do PDF, base 1, igual ao `pagina_NN.txt`.

| Empresa | Visão | Ativo | Passivo | Contas (Ativo/Passivo) |
|---|---|---|---|---|
| Gerdau | consolidado | 26 | 27, 28 | 94 (33/61) |
| Gerdau | controladora | 15 | 16, 17 | 88 (33/55) |
| Usiminas | consolidado | 12 | 13 | 81 (36/45) |
| Usiminas | controladora | 3 | 4 | 78 (35/43) |

Os números de páginas e contas vêm dos `metricas/balanco_*.meta.json` (`paginas` e `n_contas`). Os testes com essas fixtures conferem a extração do balanço. No verificador atual, os quatro `balanco_*.json` saem com todos os registros em REVISAR (0/94, 0/88, 0/81 e 0/78 conferem), sem ERRO.

Estrutura:

```
tests/fixtures/
  .gitattributes                 # "* -text": o hash não depende de autocrlf
  README.md                      # o que são, de onde vêm, como regenerar
  MANIFEST.json                  # lista de arquivos com bytes e SHA-256, e de PDFs
  gerdau_ITR_3T26/               # pagina_15, 16, 17, 26, 27, 28
  usiminas_ITR_3T26/             # pagina_03, 04, 12, 13
  invalidos/                     # 8 JSONs fora do contrato (Parte 1)
```

**Origem e uso.** São documentos públicos publicados pelas empresas e na CVM, os mesmos PDFs de `data/itrs/`. O uso é exclusivo de teste, com cópia literal e mínima (10 páginas). Veja [USO-DOS-DADOS.md](USO-DOS-DADOS.md).

**Nunca edite as fixtures à mão.** Um teste compara o hash de cada arquivo com o `MANIFEST.json`, e qualquer edição quebra esse teste.

### Como regenerar e conferir

```bash
python scripts/gerar_fixtures.py [--check] [--destino DIR]    # DIR padrão: tests/fixtures
```

- Sem flag, grava as 10 páginas, o `MANIFEST.json`, o `.gitattributes` e o `README.md`. A pasta `invalidos/` não é tocada.
- `--check` reextrai em memória e compara com os arquivos e com o manifesto. Não grava nada. Cada divergência sai como `divergente: <arquivo>`. Código 0 se tudo bater, 1 se houver divergência.
- PDF ausente: `ERRO: PDF não encontrado: <caminho>` em stderr, código 2.

Quando a versão do pdfplumber mudar e o texto extraído mudar, regenere as fixtures **e** os metas juntos. Os testes `B-F2` e `B-F6` (ver abaixo) são os que pegam a mudança.

O `MANIFEST.json` não tem data nem hora. Ele traz a versão do formato, o script que gerou os arquivos, a versão do pdfplumber, os PDFs de origem (caminho, SHA-256 e número de páginas) e a lista de arquivos com bytes e SHA-256.

As fixtures negativas de texto (dígito trocado, título alterado) são criadas por mutação dentro dos testes, em `tmp_path`. Elas não ficam salvas no repo.

### Testes

```bash
pytest                                                     # padrão: sem PDF, hermético
pytest --com-pdf                                           # inclui os testes com PDF real
pytest -q --cov=src --cov-report=term-missing              # cobertura (precisa de pytest-cov)
```

**`pytest` (padrão).** Não precisa de PDF nem de `saida/`. Os testes usam `tests/fixtures/` e um PDF falso em `tmp_path`. O alvo é rodar em menos de 5 segundos. Os testes marcados com `pdf` aparecem como `skipped` com a razão `use --com-pdf`.

**`pytest --com-pdf`.** Roda os testes marcados com `pdf`. Eles leem `data/itrs/*.pdf`. Se o PDF não existir, o teste sai como `skipped` com a razão `PDF ausente: <caminho>`.

Os testes marcados com `pdf` são:

- `B-F6` (`tests/test_fixtures.py`): `gerar_fixtures.main(["--check"]) == 0`, ou seja, as fixtures batem com o PDF real.
- `test_cli_pdf_real[stem]` (`tests/test_extrair_balanco.py`): roda o extrator sobre o PDF real e confere que o JSON gerado é igual ao `metricas/balanco_<empresa>.json` versionado.

O `C-T15` (`tests/test_catalogo.py`) não é marcado com `pdf`. Ele roda por padrão, checa `gerar_catalogo.py --check` no repo real, e sai como `skipped` se `data/itrs/*.pdf` não existir.

Para saber se os testes realmente pegam erro, apague, uma por vez, a checagem de trecho, a comparação de `valor` com o literal e a checagem de variação em `checar` (`src/verificar_numeros.py`). Em cada caso, pelo menos um teste de `tests/test_verificar_numeros.py` tem de falhar.

Arquivos de teste:

| Arquivo | Cobre |
|---|---|
| `tests/test_contrato.py` | Os três schemas, mensagens em português, ordem dos erros, EBITDA, leitura de JSON e CLI do `contrato.py`. |
| `tests/test_fixtures.py` | Manifesto, hashes, páginas do BP contra os metas, tamanho da pasta (< 50 KB). |
| `tests/test_verificar_numeros.py` | Verificador (CASE-02): OK, REVISAR e ERRO, `--estrito`, `--relatorio` e códigos de saída. |
| `tests/test_extrair_balanco.py` | Extrator, em processo, sobre as fixtures e um PDF falso. |
| `tests/test_catalogo.py` | Catálogo: determinismo, `--check`, herança do status, pendentes. |

Os testes do extrator e do verificador rodam em processo, sem subprocess. Por isso a cobertura de `src/verificar_numeros.py` é medida. O alvo é 90% ou mais.

### Dependências

- `jsonschema>=4.20` é dependência de execução (`requirements.txt` e `pyproject.toml`). Sem ela, o `contrato.py` não roda.
- `pytest` e `pytest-cov` são dependências de desenvolvimento (`pyproject.toml`).
- O catálogo usa só a biblioteca padrão e os módulos do projeto.
