# Contrato de dados, catálogo e fixtures — guia

Leia antes o [caminho avançado](GUIA_TECNICO.md) e o [extrator do balanço](EXTRATOR_BALANCO.md). Este guia cobre quatro coisas: o **contrato** (o formato que um JSON de métricas precisa ter para o verificador aceitá-lo), os **avisos** do verificador, o **catálogo** dos dados e as **fixtures** com os testes. O desenho completo está no SPEC em `claude-lab-case3-planejamento/SPEC_contrato_catalogo_fixtures.md`, fora do repo.

O verificador confere cada número contra o PDF, mas só depois de checar a forma do arquivo. Um `pagina` que falta ou uma unidade inventada travariam a conferência no meio do caminho. Por isso o contrato roda primeiro: se o JSON não passar, o verificador para com código 2 e não confere nenhuma métrica.

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

### Os três schemas

Os schemas ficam em `schemas/` e seguem o JSON Schema Draft 2020-12. Validam forma e tipos. Não conferem números.

| Arquivo | Valida | Usado para |
|---|---|---|
| `schemas/metricas.schema.json` | Registro-base: a lista de métricas que o time extrai (`metricas/metricas_<empresa>.json`). | Qualquer JSON que não seja balanço. |
| `schemas/balanco.schema.json` | Contas do balanço: o registro-base mais 12 campos próprios (19 obrigatórios). Campo fora da lista é rejeitado. | `metricas/balanco_<empresa>[_controladora].json`. |
| `schemas/balanco_meta.schema.json` | Metadados gravados pelo extrator. | `metricas/balanco_*.meta.json`. Só pelo `src/contrato.py`. |

O `escolher_schema` decide sozinho: se a lista tem um item com a chave `demonstracao`, usa `balanco`; senão, `metricas`. Para forçar, use `--schema`.

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

### Balanço (`balanco.schema.json`)

- Os 19 campos obrigatórios são os 7 do registro-base mais 12 próprios: `anterior`, `anterior_como_aparece`, `codigo_conta`, `descricao`, `codigo_pai`, `nivel`, `demonstracao`, `visao`, `empresa`, `data_atual`, `data_anterior`, `ambiguo`.
- `unidade` tem de ser `R$ mil` (o extrator só aceita `(Reais Mil)`).
- `valor` e `anterior` são inteiros.
- `codigo_conta` começa com `1` ou `2` e segue o padrão `1`, `1.01`, `2.03.05`. `codigo_pai` é `null` só na conta de nível 1.
- `variacao_pct` e `criterio_ebitda` são proibidos (balanço compara posições e não tem EBITDA). `base_comparacao`, se aparecer, só pode ser `posição`.
- Campo que não está na lista é rejeitado.

### O que o schema não confere

- Não compara `valor` com `valor_como_aparece`, não recalcula variação e não soma contas.
- Não confere se `trecho` ou `valor_como_aparece` estão na página. Isso é do verificador.
- Não confere se a data é real. Confere só o formato `AAAA-MM-DD`.
- No balanço, não confere as somas (V04 a V06 ficam no extrator).

### Como validar um JSON

```bash
python src/contrato.py ARQUIVO [ARQUIVO ...] [--schema {auto,metricas,balanco,balanco_meta}]
```

Com `auto` (o padrão), um arquivo que termina em `.meta.json` usa `balanco_meta`, e os demais usam `escolher_schema`. Para cada arquivo, a saída é:

```
<arquivo>: válido (<nome>)
<arquivo>: <n> erro(s) (<nome>)
  <caminho>: <mensagem>
```

Código de saída: 0 se todos forem válidos; 2 se algum for inválido, ilegível ou se o uso for inválido. Arquivo ausente ou JSON sintaticamente inválido sai em stderr como `ERRO: <mensagem>`, por exemplo `ERRO: JSON inválido em <caminho>: linha <l>, coluna <c>: <msg>`.

### Mensagens `[CONTRATO]`

O caminho do erro aponta para o campo: `$` é a raiz, `$[0]` é o primeiro registro, `$[0].pagina` é o campo `pagina` do primeiro registro, `$.paginas.ativo[0]` aparece no meta. Exemplo, com o registro sem `pagina` (fixture `sem_pagina.json`):

```
[CONTRATO] $[0].pagina: campo obrigatório ausente

JSON fora do contrato (schemas/metricas.schema.json): 1 erro(s). Nenhuma métrica foi conferida.
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

Se houver mais de 50 erros, o verificador mostra as 50 primeiras e diz quantos sobraram.

### Códigos de saída do verificador

```
python src/verificar_numeros.py PASTA ARQUIVO [--sem-contrato] [--schema {auto,metricas,balanco}]
```

| Código | Significado |
|---|---|
| 0 | Tudo confere. Avisos são permitidos. |
| 1 | Pelo menos um `[ERRO]`: número, trecho ou variação não batem com a página. |
| 2 | Fora do contrato, ou entrada inutilizável, ou uso inválido. Nenhuma métrica foi conferida. |

Os casos do código 2 são: arquivo não encontrado, JSON sintaticamente inválido, pasta de textos não encontrada, `jsonschema` ausente com o contrato ligado, uso inválido e JSON fora do contrato. As mensagens de entrada saem em stderr com o prefixo `ERRO: `, por exemplo `ERRO: pasta de textos não encontrada: <pasta>`.

**Regra de ordem:** o contrato vem antes da pasta. Um JSON inválido dá código 2 mesmo que a pasta de textos esteja errada.

### `--sem-contrato`

A flag pula a validação do schema. O código continua 0 ou 1. Em stderr aparece:

```
aviso: --sem-contrato: o JSON não foi validado contra o schema (use só para destravar a oficina)
```

Use em dois casos: quando a biblioteca `jsonschema` não está instalada (sem ela e sem a flag, o verificador sai com código 2 e a mensagem `jsonschema não instalado: rode 'pip install -r requirements.txt' (ou use --sem-contrato)`), ou para ver a conferência de números enquanto o JSON ainda está sendo corrigido na oficina.

Não use para fechar a entrega. Sem contrato, o verificador aceita o que o schema proibiria: unidade fora da lista vira só aviso, e campo não previsto passa. Um `pagina` ausente vira ERRO `campo 'pagina' ausente ou inválido`, em vez de ser barrado antes. O JSON que vai para `metricas/` tem de passar pelo contrato.

### Erros comuns e como corrigi-los

As fixtures em `tests/fixtures/invalidos/` têm um registro cada, com um erro cada. Servem de exemplo:

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

Depois, rode `python src/contrato.py metricas/metricas_gerdau.json` antes do verificador.

---

## Parte 2 — Avisos do verificador

O verificador tem dois níveis. **ERRO** muda o código para 1. **AVISO** aparece na saída, mas não muda o código. O aviso serve para o caso em que a conferência passou, mas há um sinal de que ela pode ter passado por acaso ou que a citação está incompleta.

Exemplo de saída com aviso (formato de `imprimir`):

```
[OK ] <metrica> (<periodo>): confere com o PDF
[AVISO] <metrica> (<periodo>): valor_como_aparece '9' está na página, mas fora do trecho citado

1 aviso(s): revise as linhas [AVISO] (não mudam o código de saída).
```

Sem avisos, a saída é idêntica à do verificador anterior. Nos quatro balanços versionados em `metricas/balanco_*.json`, a saída não traz nenhum aviso (CA-A3).

| Aviso | Quando aparece | Mensagem exata | O que fazer |
|---|---|---|---|
| 1 | O registro não tem `trecho`. | `sem 'trecho': a citação não foi conferida` | Incluir o `trecho`. Sem ele, a citação não foi conferida. |
| 2 | `valor_como_aparece` está na página, mas não no `trecho`. | `valor_como_aparece '<lit>' está na página, mas fora do trecho citado` | Conferir se o `trecho` é a linha certa. O número existe na página, mas pode não ser o citado. |
| 3 | Mesma situação do 2, com `anterior_como_aparece` curto (até 3 caracteres). | `anterior_como_aparece '<lit>' é curto e foi achado fora do trecho; pode ter casado por acaso` | Número curto como `7` ou `0` casa em qualquer lugar. Conferir a linha da página. |
| 4 | `unidade` não está na lista do contrato (só com `--sem-contrato`). | `unidade '<u>' fora da lista do contrato` | Trocar pelo valor do enum. |
| 5 | A unidade não aparece no `trecho`, no `valor_como_aparece` nem na página. | `unidade '<u>' não aparece no trecho nem na página` | Conferir a escala na página (ex.: `R$ milhões` sem nenhuma menção a milhões). |

Os avisos 4 e 5 são heurísticos. A unidade é procurada por marcadores no texto (por exemplo, `mil` ou `milhares` para `R$ mil`, e `%` para `%`). Notas da Gerdau citam valores como `R$ 289.505` sem "mil" por perto. Se a página não trouxer um marcador, o aviso aparece. É um lembrete para conferir a escala, não um bloqueio.

Os avisos não aparecem para literal que não está na página. Nesse caso já é ERRO.

Limitação: a busca do verificador é por substring. Um literal curto dentro do próprio `trecho` passa sem aviso. Por exemplo, `0` dentro de `3.204.533` (caso fixado no teste `B-V24`). O aviso 3 só cobre o literal curto que aparece **fora** do `trecho`. Na oficina os avisos ficam como lembrete. O próximo passo, ainda não feito, é promover o aviso 2 a ERRO quando o time sair da oficina.

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
| O que checa | V01 a V08 do balanço (contas, somas, ordem) | Contrato do JSON e conferência de cada número contra `saida/<stem>/` |
| Status | `aprovado` ou `reprovado` | `94/94 conferem`, `fora do contrato (<n> erro(s))`, `não verificado (saida/ ausente)` e outros |

Um balanço pode estar `aprovado` na autovalidação e ainda não ter sido conferido pelo verificador. O catálogo mostra as duas colunas separadas.

### Status do verificador no catálogo

| Status | Quando |
|---|---|
| `<n_ok>/<n_total> conferem` | Há `saida/<stem>/` e o verificador rodou. Com avisos, acrescenta `, <n_avisos> aviso(s)`. |
| `fora do contrato (<n> erro(s))` | O JSON não passou no contrato. |
| `não verificado (saida/ ausente)` | Não há `saida/<stem>/` e não há status herdado (ver abaixo). |
| `não verificado (fonte desconhecida)` | Não se sabe de qual PDF o artefato vem. |
| `erro de entrada (ver terminal)` | O verificador levantou erro de entrada. A mensagem vai para o terminal. |
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

Os números de páginas e contas vêm dos `metricas/balanco_*.meta.json` (`paginas` e `n_contas`). Com as fixtures, o verificador confere 94/94, 88/88, 81/81 e 78/78 nessa ordem.

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

Para saber se os testes realmente pegam erro, apague, uma por vez, a checagem de trecho, a comparação de `valor` com o literal e a checagem de variação em `checar` (`src/verificar_numeros.py`). Em cada caso, pelo menos um teste tem de falhar (`B-V6`/`B-V8`, `B-V10`, `B-V13`).

Arquivos de teste:

| Arquivo | Cobre |
|---|---|
| `tests/test_contrato.py` | Os três schemas, mensagens em português, ordem dos erros, EBITDA, leitura de JSON e CLI do `contrato.py`. |
| `tests/test_fixtures.py` | Manifesto, hashes, páginas do BP contra os metas, tamanho da pasta (< 50 KB). |
| `tests/test_verificar_numeros.py` | Verificador: contrato, conferência, avisos, códigos de saída e mensagens de erro. |
| `tests/test_extrair_balanco.py` | Extrator, em processo, sobre as fixtures e um PDF falso. |
| `tests/test_catalogo.py` | Catálogo: determinismo, `--check`, herança do status, pendentes. |

Os testes do extrator e do verificador rodam em processo, sem subprocess. Por isso a cobertura de `src/verificar_numeros.py` é medida. O alvo é 90% ou mais.

### Dependências

- `jsonschema>=4.20` é dependência de execução (`requirements.txt` e `pyproject.toml`). Sem ela, só o `--sem-contrato` do verificador funciona.
- `pytest` e `pytest-cov` são dependências de desenvolvimento (`pyproject.toml`).
- O catálogo usa só a biblioteca padrão e os módulos do projeto.
