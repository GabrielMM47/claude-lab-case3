# CASE-03 Apresentações institucionais Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar fontes oficiais, ranking genérico de páginas, prompts e JSONs operacionais/qualitativos verificados para Gerdau e Usiminas no 3T26.

**Architecture:** O pipeline existente continua sendo a fonte de extração/verificação. Um módulo independente pontua páginas de texto por tema; prompts e JSONs seguem o contrato já publicado no quadro de tarefas, deixando cálculos para os cards seguintes.

**Tech Stack:** Python 3.14, `pathlib`, `argparse`, `unicodedata`, `json`, `pytest`, `pdfplumber` e scripts existentes.

**Spec:** `docs/superpowers/specs/2026-11-06-case03-apresentacoes-design.md` e CASE-03 em `docs/quadro_tarefas.html`.

## Global Constraints

- `src/localizar_paginas.py <pasta_saida> --tema operacional|qualitativo|ebitda [--top 10]` permanece genérico, sem nada específico de empresa.
- A convenção de páginas é o índice do PDF a partir de 1, igual a `pagina_NN.txt`.
- Um JSON de fatos é uma lista compatível com `verificar_numeros.py`; um arquivo corresponde a um documento-fonte.
- `trecho` e `valor_como_aparece` devem ser cópias literais do texto extraído.
- Unidade deve ser mantida como aparece no documento; não calcular neste card.
- Não usar números de páginas que saíram sem texto.
- Não alterar `src/extrair_release.py` nem `src/verificar_numeros.py`.

## Review Focus

- Acentos, caixa e hífens em palavras-chave não podem fazer uma página relevante desaparecer — teste de normalização e ranking.
- Páginas sem texto devem ser ignoradas pelo localizador, não pontuadas como vazias relevantes — teste com arquivo vazio.
- `--top` deve rejeitar tema inválido e limitar o ranking de forma determinística — testes de CLI.
- A apresentação da Gerdau pode ser a versão mais recente de novembro, não rotulada 3T26 — `FONTES.md` deve registrar título/data reais e o nome do artefato contratual.
- A Usiminas mistura release e institucional no mesmo PDF — os fatos devem conservar `documento: apresentacao`, páginas literais e observações de seção.

### Task 1: Localizador genérico de páginas

**Files:**
- Create: `src/localizar_paginas.py`
- Create: `tests/test_localizar_paginas.py`

**Interfaces:**
- Produces `TERMOS_POR_TEMA`, `normalizar`, `pontuar_pagina`, `localizar`, `main`.
- `localizar(pasta: Path, tema: str, top: int = 10) -> list[dict]` devolve itens com `pagina`, `pontuacao` e `termos`.

- [x] **Step 1: Write the failing test**

  Criar testes para: normalização de acentos; pontuação por ocorrência; ignorar `pagina_*.txt` vazio; ordenação por pontuação e número da página; limite `top`; e CLI com tema inválido.

- [x] **Step 2: Run test to verify it fails**

  Run: `python -m pytest tests/test_localizar_paginas.py -q`

  Expected: FAIL porque `src/localizar_paginas.py` ainda não existe.

- [x] **Step 3: Implement the minimal localizer**

  Definir os três dicionários de termos do contrato, ler apenas `pagina_*.txt`, normalizar acentos/case, contar ocorrências por termo, descartar pontuação zero e ordenar por `(-pontuacao, pagina)`.

- [x] **Step 4: Run test to verify it passes**

  Run: `python -m pytest tests/test_localizar_paginas.py -q`

  Expected: PASS.

- [x] **Step 5: Commit**

  Registrar a alteração quando o executável Git estiver disponível; se não estiver, deixar o estado no diretório e registrar a limitação no log.

### Task 2: Prompts e registro operacional

**Files:**
- Create: `prompts/extracao_operacional.md`
- Create: `prompts/extracao_qualitativa.md`
- Create: `docs/registro/geronimo.md`

**Interfaces:**
- Prompts consomem uma lista de páginas candidatas e instruem saída em JSON do contrato.
- O registro recebe fontes, páginas sem texto, erros do verificador e limitações.

- [x] **Step 1: Escrever o prompt operacional**

  Cobrir escopo consolidado/segmento, literalidade, unidades, períodos 3T26/3T25, não calcular e campos obrigatórios.

- [x] **Step 2: Escrever o prompt qualitativo**

  Cobrir 5–8 temas, resumos próprios de até 30 palavras, trechos curtos literais e rejeição de números de páginas vazias.

- [x] **Step 3: Registrar decisões e limitações**

  Documentar a abordagem aprovada, fallback da pesquisa externa, fontes, uso de páginas e qualquer lacuna sem inventar números.

### Task 3: Fontes, PDFs e texto extraído

**Files:**
- Create: `data/apresentacoes/FONTES.md`
- Create: `data/apresentacoes/gerdau_APRESENTACAO_3T26.pdf`
- Create: `data/apresentacoes/usiminas_APRESENTACAO_3T26.pdf`

**Interfaces:**
- Os PDFs alimentam `src/extrair_release.py` e criam `saida/<stem>/` para o verificador.

- [x] **Step 1: Baixar os PDFs oficiais**

  Usar os links do RI descobertos em 06/11/2026 e conferir que ambos são PDFs válidos.

- [x] **Step 2: Registrar URL e acesso**

  Incluir página de RI, URL direta, título/data publicados, data de acesso `06/11/2026` e a observação de que o Firecrawl estava sem créditos.

- [x] **Step 3: Extrair os PDFs**

  Run: `python src/extrair_release.py data/apresentacoes/gerdau_APRESENTACAO_3T26.pdf data/apresentacoes/usiminas_APRESENTACAO_3T26.pdf`

  Expected: duas pastas em `saida/` com `pagina_NN.txt`; registrar no log páginas sem texto.

- [x] **Step 4: Rodar o localizador em ambas**

  Run: `python src/localizar_paginas.py saida/gerdau_APRESENTACAO_3T26 --tema operacional --top 10` e equivalente para Usiminas, repetindo para `qualitativo` e `ebitda`.

  Expected: ranking sem erro e sem alterar código entre empresas.

### Task 4: JSONs de fatos literais

**Files:**
- Create: `metricas/gerdau_3T26_itr_operacional.json`
- Create: `metricas/gerdau_3T26_apresentacao_operacional.json`
- Create: `metricas/gerdau_3T26_apresentacao_qualitativo.json`
- Create: `metricas/usiminas_3T26_itr_operacional.json`
- Create: `metricas/usiminas_3T26_apresentacao_operacional.json`
- Create: `metricas/usiminas_3T26_apresentacao_qualitativo.json`

**Interfaces:**
- Todos são listas JSON compatíveis com `verificar_numeros.py`.
- Arquivos `*_itr_*` apontam para `saida/gerdau_ITR_3T26` ou `saida/usiminas_ITR_3T26`; arquivos `*_apresentacao_*` apontam para as pastas dos PDFs novos.

- [x] **Step 1: Extrair e selecionar fatos do ITR/release**

  Usar páginas já extraídas dos ITRs: Usiminas release e Gerdau notas de segmento, incluindo receita/EBITDA por segmento quando publicados; manter `obs` para dados ausentes.

- [x] **Step 2: Extrair fatos operacionais das apresentações**

  Incluir volumes 3T26/3T25 quando reportados, segmentos, capacidade, R$/t ou insumos reportados e exportação/mix quando houver.

- [x] **Step 3: Escrever temas qualitativos**

  Incluir pelo menos cinco temas por empresa, obrigatoriamente `perfil`, `capacidade_footprint`, `mercados_produtos`, `estrategia` e `riscos` ou `guidance_perspectivas`.

- [x] **Step 4: Validar forma JSON**

  Run: `python -m json.tool` em cada arquivo e checar que todos os objetos têm `metrica`, `pagina` e `trecho`.

### Task 5: Verificação 100% e fechamento do registro

**Files:**
- Modify: `docs/registro/geronimo.md`

- [x] **Step 1: Rodar `verificar_numeros.py` nos seis arquivos**

  Executar cada arquivo contra a pasta de saída correspondente; esperado: processo com código 0 e `N/N métricas conferem`.

- [x] **Step 2: Corrigir apenas erros encontrados**

  Reabrir a página indicada, ajustar o JSON literal e repetir o verificador até 100%.

- [x] **Step 3: Registrar resultado final**

  Anotar comandos, contagens, páginas sem texto, lacunas e a confirmação de que `localizar_paginas.py` foi usado nas duas empresas.

- [x] **Step 4: Rodar a suíte completa**

  Run: `python -m pytest -q`

  Expected: todos os testes passarem.
