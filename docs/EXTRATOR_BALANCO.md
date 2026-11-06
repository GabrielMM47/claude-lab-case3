# Extrator do Balanço Patrimonial — guia de uso

Leia antes o [README do case](CASE3.md) e o [caminho avançado](GUIA_TECNICO.md). Este guia cobre só a ferramenta `src/extrair_balanco.py`. O desenho completo (regras, algoritmo, validações e plano de testes) está no SPEC em `claude-lab-case3-planejamento/SPEC_extrator_balanco.md`, fora do repo.

## Para que serve

O Claude não deve escrever número de memória. O Balanço Patrimonial (BP) é a fonte de posição: ativo, passivo e patrimônio líquido, nas datas 30/09/2026 e 31/12/2025. O extrator lê as páginas do BP no ITR, transforma cada linha de conta em um registro JSON e confere a consistência interna do balanço antes de gravar.

Ele entra no fluxo entre a extração de texto e a verificação:

```
extrair                      verificar                       comparar
extrair_release.py  ──►  extrair_balanco.py  ──►  verificar_numeros.py  ──►  tabela e gráficos
(texto por página)      (metricas/balanco_*.json)  (confere cada número no PDF)
```

Ele não substitui o `verificar_numeros.py`. O JSON gerado é uma etapa intermediária: só entra na tabela comparativa depois de passar pelo verificador com 0 erros.

## Pré-requisitos e instalação

- Python com `pdfplumber`, a mesma dependência de `src/extrair_release.py`. O extrator não exige pacotes novos.
- Os PDFs dos ITRs em `data/itrs/`.
- O `src/contrato.py` valida o JSON com `jsonschema` (`jsonschema>=4.20` em `requirements.txt`). O verificador não usa essa biblioteca (ver [CONTRATO_DADOS.md](CONTRATO_DADOS.md)).
- Para os testes (opcional): `pytest` e `pytest-cov`, como dependências de desenvolvimento (`uv add --dev pytest` ou `pip install pytest`). Eles não entram no `requirements.txt` de execução.

Rode os comandos sempre a partir da raiz do repo, como os demais scripts. O extrator calcula a raiz a partir do próprio arquivo.

## Uso rápido

Gerdau e Usiminas, consolidado (padrão), com os textos já extraídos:

```bash
python src/extrair_balanco.py data/itrs/gerdau_ITR_3T26.pdf
python src/extrair_balanco.py data/itrs/usiminas_ITR_3T26.pdf
```

Ou os dois de uma vez:

```bash
python src/extrair_balanco.py data/itrs/*.pdf
```

Se ainda não existir `saida/<stem>/pagina_NN.txt`, o extrator chama `extrair_release.py` sozinho. A primeira execução é a mais lenta por causa disso. Com os textos prontos, a meta é menos de 10 s por PDF.

Depois, verifique cada empresa:

```bash
python src/verificar_numeros.py saida/gerdau_ITR_3T26   metricas/balanco_gerdau.json
python src/verificar_numeros.py saida/usiminas_ITR_3T26 metricas/balanco_usiminas.json
```

## Opções da linha de comando

```
python src/extrair_balanco.py PDF [PDF ...]
       [--visao {consolidado,controladora,ambas}]   # padrão: consolidado
       [--empresa NOME]                             # só com 1 PDF
       [--saida DIR]                                # padrão: <raiz>/metricas
       [--textos DIR]                               # padrão: <raiz>/saida/<stem do PDF>; só com 1 PDF
       [--paginas ESPEC]                            # override; só com 1 PDF e visão ≠ ambas
       [--csv]                                      # grava também o CSV plano
```

| Opção | O que faz | Exemplo |
|---|---|---|
| `PDF` | Caminho do ITR (ou DFP). Obrigatório, 1 ou mais. `stem` é o nome sem extensão. | `data/itrs/gerdau_ITR_3T26.pdf` |
| `--visao` | `consolidado` procura `DFs Consolidadas`; `controladora` procura `DFs Individuais`; `ambas` roda as duas e grava dois arquivos. | `--visao controladora` |
| `--empresa` | Nome usado nos arquivos e no campo `empresa`. Vira minúsculas e deve casar `^[a-z0-9_-]+$`. Padrão: primeira parte do nome do arquivo. | `--empresa gerdau` |
| `--saida` | Pasta de saída. É criada se não existir. | `--saida /tmp/teste` |
| `--textos` | Usa uma pasta de `pagina_NN.txt` já existente e não chama o `extrair_release`. Se a pasta estiver incompleta, falha. | `--textos saida/gerdau_ITR_3T26` |
| `--paginas` | Informa as páginas manualmente, no formato `ATIVO:PASSIVO`. Pula a localização automática. | `--paginas 26:27-28` |
| `--csv` | Grava também o CSV plano. Só sai quando o código de saída é 0. | `--csv` |

Exemplos:

```bash
# Controladora, em arquivo separado
python src/extrair_balanco.py data/itrs/gerdau_ITR_3T26.pdf --visao controladora

# As duas visões de uma vez (dois arquivos por empresa)
python src/extrair_balanco.py data/itrs/usiminas_ITR_3T26.pdf --visao ambas --csv

# Textos já extraídos e páginas informadas à mão
python src/extrair_balanco.py data/itrs/gerdau_ITR_3T26.pdf \
    --textos saida/gerdau_ITR_3T26 --paginas 26:27-28 --empresa gerdau
```

Restrições (violação gera erro de uso, código 2):

- `--empresa`, `--textos` e `--paginas` exigem exatamente 1 PDF.
- `--paginas` não combina com `--visao ambas`.
- `--paginas` no formato `ATIVO:PASSIVO`, com índices base 1, vírgulas e intervalos. Exemplos válidos: `26:27-28`, `12:13`.

Com `--visao ambas` ou vários PDFs, cada combinação é processada de forma independente. Uma falha não interrompe as outras. O código final é o maior código individual.

## O que é gerado

Para cada empresa e visão, na pasta `metricas/` (ou a pasta de `--saida`):

| Arquivo | Conteúdo |
|---|---|
| `balanco_<empresa>.json` | Contas consolidadas. É o arquivo que o verificador lê. |
| `balanco_<empresa>_controladora.json` | Contas da controladora (arquivo separado). |
| `balanco_<empresa>[_controladora].meta.json` | Metadados, validações e avisos. |
| `balanco_<empresa>[_controladora].csv` | Opcional, com `--csv`. |

### Campos do JSON principal

Lista de objetos, um por conta, na ordem de aparição no PDF (Ativo, depois Passivo):

| Campo | Significado |
|---|---|
| `metrica` | `código + descrição`, única no arquivo. |
| `periodo` | Ex.: `30/09/2026 vs 31/12/2025`. |
| `unidade` | Sempre `R$ mil`. |
| `valor` / `anterior` | Inteiros convertidos do texto. Coluna atual e coluna anterior. |
| `valor_como_aparece` / `anterior_como_aparece` | Texto literal do PDF. |
| `pagina` | Índice da página no PDF (base 1), igual ao `pagina_NN.txt`. |
| `trecho` | Linha do texto (ou linhas consecutivas unidas por espaço) onde está a conta. |
| `codigo_conta`, `descricao` | Código e descrição literais. |
| `codigo_pai`, `nivel` | Hierarquia pelo código (`1.01.04` tem pai `1.01` e nível 3). |
| `demonstracao` | `BPA` (ativo) ou `BPP` (passivo). |
| `visao`, `empresa` | `consolidado` ou `controladora`; nome da empresa. |
| `data_atual`, `data_anterior` | Datas ISO, ex.: `2026-09-30`, `2025-12-31`. |
| `ambiguo` | `true` se o mesmo literal aparece mais de uma vez na página. |

Exemplo de objeto (valores copiados do SPEC, Gerdau consolidado):

```json
{
  "metrica": "1.01.04 Estoques",
  "periodo": "30/09/2026 vs 31/12/2025",
  "unidade": "R$ mil",
  "valor": 16490132,
  "valor_como_aparece": "16.490.132",
  "anterior": 14731081,
  "anterior_como_aparece": "14.731.081",
  "pagina": 26,
  "trecho": "1.01.04 Estoques 16.490.132 14.731.081",
  "codigo_conta": "1.01.04",
  "descricao": "Estoques",
  "codigo_pai": "1.01",
  "nivel": 3,
  "demonstracao": "BPA",
  "visao": "consolidado",
  "empresa": "gerdau",
  "data_atual": "2026-09-30",
  "data_anterior": "2025-12-31",
  "ambiguo": false
}
```

Não há campo de variação (`variacao_pct`). O BP compara posições, não A/A nem T/T. Não há timestamp no arquivo principal, então duas execuções sobre o mesmo texto geram o mesmo arquivo.

### Arquivo de metadados (`.meta.json`)

Gravado com código 0 ou 1. Traz o script e a versão, o hash SHA-256 do PDF, a pasta de textos usada, as páginas localizadas (`paginas`), a escala original, o número de contas, `n_ambiguos`, o `status` (`aprovado` ou `reprovado`), a lista de validações e a lista de avisos.

```json
{
  "script": "extrair_balanco.py",
  "versao_script": "1.0.0",
  "empresa": "gerdau",
  "visao": "consolidado",
  "paginas": {"ativo": [26], "passivo": [27, 28]},
  "localizacao": "automatica",
  "escala_original": "Reais Mil",
  "unidade": "R$ mil",
  "n_contas": {"ativo": 33, "passivo": 61, "total": 94},
  "n_ambiguos": 32,
  "status": "aprovado"
}
```

Os valores de `paginas`, `n_contas` e `n_ambiguos` são os da Gerdau consolidada (saída real do extrator). Os demais campos foram omitidos do exemplo; use o arquivo real para conferir.

### CSV (`--csv`)

Cabeçalho: `codigo_conta,descricao,nivel,demonstracao,valor,anterior,pagina,visao,data_atual,data_anterior`. Valores inteiros, sem separador de milhar.

### Resumo em tela

```
gerdau_ITR_3T26.pdf · visão consolidado · textos: saida/gerdau_ITR_3T26 (reutilizados)
  Ativo: pág. 26 · Passivo: págs. 27, 28 · escala: Reais Mil · colunas: 30/09/2026 e 31/12/2025
  94 contas (Ativo 33, Passivo 61) · literais ambíguos: 32
  [OK  ] V01 contas obrigatórias presentes
  ...
  → metricas/balanco_gerdau.json · metricas/balanco_gerdau.meta.json
```

## Como rodar o verificador sobre a saída

O `verificar_numeros.py` confere cada registro contra a página indicada em `pagina`:

```bash
python src/verificar_numeros.py saida/<stem> metricas/balanco_<empresa>.json
```

A pasta passada ao verificador tem de ser a mesma de onde o extrator leu o texto (`saida/<stem>`), e o JSON tem de ser o principal (`balanco_<empresa>.json`), não o `.meta.json`. O verificador não valida o contrato. Para checar a forma do JSON contra `schemas/balanco.schema.json`, rode antes `python src/contrato.py metricas/balanco_<empresa>.json` (código 2 se estiver fora do contrato).

O verificador confere, para cada registro:

1. Se o `trecho` está na página indicada.
2. Se o `valor_como_aparece` está na página indicada e dentro do `trecho`.
3. Se o número convertido bate com `valor`.

Cada registro sai como OK, REVISAR ou ERRO.

**Os balanços saem como REVISAR.** O formato legado (sem `chave`, `documento` nem `escopo`) fica "fora do contrato" do time para o verificador atual, que o classifica como REVISAR: `fora do contrato (sem chave, documento, escopo): não entra no pipeline`, além de pedir evidência literal de período, unidade e escopo. Hoje os quatro balanços dão 0/94, 0/88, 0/81 e 0/78 conferem, com todos os registros em REVISAR e nenhum ERRO (código 0). Isso significa que a conferência automática não comprovou o vínculo, não que o número esteja errado; os balanços ainda não entram no pipeline de fatos.

Se algum item der ERRO, o problema está no registro, na página ou no texto extraído. Corrija só o item indicado, olhando a página em `pagina_NN.txt` e o PDF. Não ajuste o número sem conferir a fonte.

Códigos do verificador: 0 (nenhum ERRO) e 1 (algum ERRO; com `--estrito`, também REVISAR). Para validar o `.meta.json`, que o verificador não lê, use o `src/contrato.py`:

```bash
python src/contrato.py metricas/balanco_gerdau.meta.json
```

Detalhes do contrato e do resumo do verificador estão em [CONTRATO_DADOS.md](CONTRATO_DADOS.md).

## Validações

O extrator roda validações sobre o balanço inteiro antes de gravar. Todas usam comparação exata (inteiros, tolerância zero) e são avaliadas nas duas colunas.

### Severidade erro (qualquer falha dá código 1)

| ID | Regra |
|---|---|
| V01 | Contas obrigatórias presentes: `1`, `1.01`, `1.02`, `2`, `2.01`, `2.02`, `2.03`. |
| V02 | Códigos únicos. |
| V03 | Códigos do Ativo começam com `1`; do Passivo, com `2`. |
| V04 | Ativo Total = Passivo Total (`1 == 2`). |
| V05 | `1 == 1.01 + 1.02`. |
| V06 | `2 == 2.01 + 2.02 + 2.03`. |
| V07 | Número de linhas com código no texto == número de contas extraídas. Detecta linha perdida. |
| V08 | Autoverificação com a mesma lógica do verificador, conta a conta. |

### Severidade aviso (não muda o código de saída)

| ID | Regra |
|---|---|
| A01 | Soma das subcontas diferente da conta pai. O PDF pode omitir subcontas, por isso é aviso. |
| A02 | Conta cujo pai não está no bloco. |
| A03 | Códigos fora de ordem. |
| A04 | Literal ambíguo (contado no meta). |
| A05 | Descrição montada de mais de uma linha, inclusive quebra entre páginas. |
| A06 | Linha do corpo ignorada por não ser conta nem rodapé conhecido. |
| A07 | Com `--paginas`, o título da página não confere com a visão pedida. |
| A08 | Visão consolidada sem `Consolidado` na descrição de `2.03`. |

### Erro ou aviso?

- **Erro** significa que o número ou a estrutura não fecham. O JSON principal não é gravado e o código é 1. Só o `.meta.json` fica, com `status: reprovado`.
- **Aviso** significa algo a conferir, mas que não invalida o balanço. Ele aparece na tela e no meta, e o JSON é gravado.

### Códigos de saída

| Código | Significado |
|---|---|
| 0 | Extraiu e nenhuma validação de erro falhou. JSON gravado. |
| 1 | Extraiu, mas uma validação de erro falhou. Só o `.meta.json` é gravado, com `reprovado`. |
| 2 | Não extraiu: uso inválido, PDF ou textos ausentes, página não encontrada, escala não suportada ou linha de conta mal formada. Nada é gravado. A mensagem sai em `stderr`. |

Em execuções com vários PDFs ou `--visao ambas`, o código final é o maior dos individuais.

## Problemas comuns

| Mensagem ou sintoma | O que fazer |
|---|---|
| `PDF não encontrado` | Confira o caminho. Rode a partir da raiz do repo. |
| `Pasta de textos incompleta` | Rode `python src/extrair_release.py <pdf>` e tente de novo, ou tire `--textos` para o extrator rodar a extração sozinho. |
| `Balanço Patrimonial ... não encontrado` | O título ou a estrutura do BP não casa com o padrão. Confira se a visão pedida existe no PDF (`DFs Consolidadas` ou `DFs Individuais`). Se o PDF estiver fora do padrão, use `--paginas` com as páginas corretas. |
| `Mais de um bloco ... use --paginas` | Mais de um trecho do BP casa com a visão. Informe as páginas com `--paginas`. |
| `escala ... não suportada (só Reais Mil)` | Esperado para `(Reais)` ou `(Reais Milhões)`. A ferramenta não converte escala; o caso é de código 2. |
| `datas/escala divergentes entre as págs.` | Páginas do mesmo bloco têm datas ou escala diferentes. Confira se a localização pegou páginas de outro bloco. |
| `conta ... sem valores` | Conta sem os dois valores no fim da linha. Confira o texto em `pagina_NN.txt`. |
| `linha não reconhecida na conta` | Linha com dígitos que não casa com o padrão. Confira a página indicada na mensagem. |
| `--paginas inválido` | Use `ATIVO:PASSIVO`, por exemplo `26:27-28`. |
| Código 1 com V04 ou V05 falhando | O balanço não fecha. Muitas vezes é um dígito errado no texto extraído ou um texto editado à mão. Confira a página e o PDF antes de mexer em qualquer coisa. |
| `ambiguo: true` | Não é erro. O literal aparece mais de uma vez na página (por exemplo, pai e filho com o mesmo valor). |
| `contrato.py` sai com código 2 | O JSON do balanço não passou no schema. Corrija os campos apontados. O caminho `$[n].campo` diz qual registro e qual campo. Ver [CONTRATO_DADOS.md](CONTRATO_DADOS.md). |
| Verificador marca tudo como `[REVISAR]` (`fora do contrato`) | Esperado para o formato legado do balanço. Não é erro do extrator; ver a seção do verificador acima. |

## Limitações

- Só aceita escala `Reais Mil`. Outras escalas abortam com código 2. Não há conversão para R$ milhões; a conversão deve ser feita na etapa de comparação.
- Só extrai o Balanço Patrimonial. DRE, DFC, notas e release não entram.
- Não calcula variações nem indicadores.
- O DFP deve funcionar se o cabeçalho seguir o mesmo padrão, mas não foi testado.
- Não lê CSV da CVM e não acessa a rede.
- Planos de contas diferentes do padrão CVM (bancos, seguradoras) falham nas validações com mensagem.
- Não usa OCR nem PDF escaneado.
- O verificador busca por substring, e literais curtos como `0` podem casar por acaso. O extrator mitiga isso com `trecho` de linha inteira e o campo `ambiguo`, mas não corrige a limitação do verificador. O verificador atual trata o valor como token inteiro e pede a coluna quando o trecho tem vários números, o que reduz esse risco. Ver [CONTRATO_DADOS.md](CONTRATO_DADOS.md), parte 2.

## Testes

- `pytest` roda sem PDF: os testes do extrator e do verificador usam as páginas de `tests/fixtures/` e um PDF falso em `tmp_path`.
- `pytest --com-pdf` roda também os testes que leem os PDFs reais em `data/itrs/`. Sem o PDF, o teste aparece como `skipped` com a razão `PDF ausente`.
- As fixtures, o manifesto e como regenerá-las estão em [CONTRATO_DADOS.md](CONTRATO_DADOS.md), parte 4.
