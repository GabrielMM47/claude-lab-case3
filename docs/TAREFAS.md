# Tarefas do time — Comparador de siderúrgicas (qualquer empresa × qualquer empresa)

> Cards no estilo Jira. Cada pessoa trabalha na própria branch e abre um PR por card.
> Para o Claude Code de cada um: *"Leia docs/TAREFAS.md, seção Contrato e o card CASE-0X, e implemente."*

## Objetivo

Um fluxo que recebe **ITR + apresentação institucional de duas empresas quaisquer** e devolve uma **apresentação executiva** comparando as duas, com métricas comuns (receita, margens, ROE, ROA, ROI, ROIC, dívida líquida...) e métricas de siderurgia (volume, R$/t, EBITDA/t...). Gerdau × Usiminas no 3T26 é o primeiro caso, não o único: **nada de código específico por empresa**.

A generalização deve vir de um **contrato único e adaptadores de entrada**, sem condicionar regras ao nome da empresa. O primeiro adaptador será para PDFs textuais de ITRs no padrão CVM. Cabeçalhos e códigos ajudam, mas não garantem extração correta de qualquer PDF: layout, subcontas, setores e documentos digitalizados exigem tratamento ou rejeição explícita. Outros formatos contábeis e moedas exigem novos adaptadores e políticas de conversão.

O núcleo compara quaisquer duas empresas cadastradas com fatos compatíveis. O perfil `siderurgia` acrescenta volumes e indicadores por tonelada; para outros setores essas métricas ficam **não aplicáveis**. Bancos e seguradoras, por exemplo, exigem catálogo e critérios próprios. Não prometer cobertura universal só por funcionar com Gerdau e Usiminas. O que não for extraído deterministicamente terá uma etapa assistida documentada, com conferência antes do uso.

### Diagnóstico do repositório em 06/11/2026

**Conclusão: há uma base aproveitável, mas o sistema solicitado ainda não está pronto.** Esta é uma inspeção de código e arquivos, sem validação ponta a ponta dos PDFs.

| Requisito | Evidência atual | Situação / card |
|---|---|---|
| PDF → texto e tabelas | `src/extrair_release.py`: páginas TXT e tabelas CSV, caminho de entrada parametrizado | Base existente; não extrai fatos financeiros estruturados nem faz OCR (02/03) |
| Fatos estruturados reutilizáveis | `templates/metricas_exemplo.json`: exemplo com nome, valor, página e trecho | Faltam contrato validado, catálogo e identificadores de documento/empresa/escopo (01/02/03) |
| Verificação | `src/verificar_numeros.py`: procura trecho e token na página, converte número e recalcula variação | Não comprova unidade, coluna temporal ou escopo; campos omitidos podem passar. Endurecer em 02 e aplicar em 07 |
| Indicadores comuns e siderurgia | `src/indicadores.py`: funções de normalização, leitura e cálculo parcial | Trabalho local não rastreado no Git; falta montagem dos indicadores, CLI e escrita de saída. Não está concluído (04) |
| Apresentação institucional | Não há PDFs institucionais nos arquivos inspecionados | Entrada e extração ausentes (03) |
| Comparação genérica | Não existem `src/contrato.py`, `src/dfs_cvm.py` ou `src/comparar.py` | Implementar 01/02/05 |
| Apresentação executiva | Existe roteiro em Markdown e dependência `python-pptx` | Não há gerador de apresentação executiva nem pipeline (06/07) |
| Entrada do projeto | `main.py` na pasta externa imprime `Hello from workshop!`; projeto efetivo em `claude-lab-case3/` | Usar a raiz interna nos comandos e documentar isso (08) |

O `docs/quadro_tarefas.html` existente é um quadro de trabalho, não a apresentação executiva das empresas. Os oito cards abaixo eram planejamento, não evidência de funcionalidades implementadas. Preservar o código local de indicadores e concluir no CASE-04.

**Estratégia de implementação:** contrato e fixtures primeiro; quatro frentes em paralelo com arquivos próprios; integração por etapas. As estimativas abaixo são iniciais de workshop, não garantia de concluir no horário do case: reestimar após testar o parser nos PDFs. OCR e extração totalmente autônoma ficam fora do primeiro incremento e devem aparecer como limitações.

```
data/itrs/*.pdf ──────────┐
data/apresentacoes/*.pdf ─┴► extrair_release.py ► saida/<pdf>/pagina_NN.txt
                                   │
          ┌────────────────────────┼─────────────────────────────┐
          ▼                        ▼                             ▼
   dfs_cvm.py (código)     Claude Code + prompts/        Claude Code + prompts/
   *_itr_dfs.json          *_itr_complementar.json       *_operacional.json / *_qualitativo.json
   [CASE-02]               [CASE-02]                     [CASE-03]
          └───────────── verificar_numeros.py (100% OK) ─────────┘
                                   ▼
                 indicadores.py ► *_indicadores.json          [CASE-04]
                                   ▼
                 comparar.py ► comparativo.json + gráficos      [CASE-05]
                                   ▼
                 apresentacao.py (+ narrativa.json) ► slides    [CASE-06]

                 pipeline.py: tudo acima num comando           [CASE-07]
```

---

## Quadro

| Card | Título | Responsável | Branch | Prioridade | Estimativa |
|---|---|---|---|---|---|
| CASE-01 | Contrato de dados, catálogo e fixtures | João Vitor | `Joao-Maia` | P0 (primeiro) | 45 min |
| CASE-02 | Extração financeira do ITR (parser CVM + EBITDA) | Gabriel Martins | `feat/gabriel-martins` | P0 | 3 h |
| CASE-03 | Apresentação institucional + dados operacionais e qualitativos | Geronimo | `feat/geronimo` | P0 | 3 h |
| CASE-04 | Motor de indicadores (ROE, ROIC, margens, R$/t...) | Gabriel Patrício | `feat/gabriel-patricio` | P0 | 2 h |
| CASE-05 | Comparativo, insights e gráficos | João Vitor | `Joao-Maia` | P1 | 1,5 h |
| CASE-06 | Gerador da apresentação executiva | Gabriel Patrício | `feat/gabriel-patricio` | P1 | 2,5 h |
| CASE-07 | Pipeline "um comando" + relatório de verificação | Gabriel Martins | `feat/gabriel-martins` | P1 | 1,5 h |
| CASE-08 | Entrega: Skill, README, registros, publicação e vídeo | Geronimo | `feat/geronimo` | P1 | 1,5 h |

## Dependências

Todo mundo começa **já**: o contrato está escrito abaixo, e quem consome dados de outro card desenvolve em cima das **fixtures fictícias** do CASE-01. A dependência real só aparece na hora de rodar com dados de verdade.

| Card | Para **começar** precisa de | Para **fechar** precisa de | Bloqueia |
|---|---|---|---|
| CASE-01 | — | — | todos (só "merge cedo") |
| CASE-02 | Contrato (este doc) | — | 04 (dados reais), 07 |
| CASE-03 | Contrato (este doc) | — | 04 (dados reais), 06 (perfil/riscos), 07 |
| CASE-04 | CASE-01 (`contrato.py` + fixtures) | JSONs verificados de 02 e 03 | 05 |
| CASE-05 | CASE-01 (fixture de indicadores) | CASE-04 | 06, 07 |
| CASE-06 | CASE-01 (fixture de comparativo) | CASE-05 + qualitativo do 03 | 07, 08 |
| CASE-07 | Interfaces de CLI (este doc) | 02, 04, 05, 06 mergeados (+ prompts e `localizar_paginas.py` do 03) | 08 |
| CASE-08 | — (rascunho desde cedo) | Todos | — |

```
CASE-01 ─(merge cedo)─► todos
CASE-02 ─┐
         ├─► CASE-04 ─► CASE-05 ─► CASE-06 ─► CASE-07 ─► CASE-08
CASE-03 ─┘                            ▲
         └──── qualitativo ───────────┘
```

**Onde pode dar conflito (e como evitar):**
- `requirements.txt`, `pyproject.toml`, `CLAUDE.md`: só o CASE-01 mexe. Precisa de biblioteca nova? Pede ao João Vitor.
- `src/contrato.py`: chave nova no catálogo pode entrar no seu PR; o conflito, se houver, é numa lista e se resolve rápido.
- `docs/ERROS_ENCONTRADOS.md` e `docs/PROMPTS.md`: ninguém edita direto. Cada um registra em `docs/registro/<seu-nome>.md`; o CASE-08 consolida.
- `metricas/`: cada arquivo tem um dono só (o nome diz de qual card ele vem).
- `src/verificar_numeros.py`: Gabriel Martins altera no CASE-02, mantendo `checar(m, pasta) -> list[str]`; CASE-07 reutiliza. Nenhum outro card edita esse arquivo.
- `uv.lock`: João Vitor atualiza junto de `pyproject.toml`. Cada pessoa cria e altera seus próprios testes e registros; CASE-01 fornece só as fixtures compartilhadas.
- A branch `Joao-Maia` já consta no quadro existente; mantida para João Vitor. Não criar nem trocar branches neste planejamento. Cada pessoa abre PRs menores na própria branch e atualiza sua base após os merges.

## Marcos sugeridos

| Marco | Quando | O que tem que estar pronto |
|---|---|---|
| M0 | início + 45 min | CASE-01 no `main`; todos fazem `git pull --rebase origin main` |
| M1 | ~13h00 | 02 e 03 com JSONs 100% verificados; 04 e 05 rodando nas fixtures; 06 gerando slides da fixture |
| M2 | ~14h30 | Primeira rodada ponta a ponta Gerdau × Usiminas (07) |
| M3 | ~15h30 | Código congelado; só narrativa, README, vídeo e publicação |
| — | 16h00 | Entrega |

---

## Contrato de dados (vale para todos os cards)

### Convenção de arquivos

| Caminho | O que é | Dono |
|---|---|---|
| `data/itrs/<slug>_ITR_<tri>.pdf` | ITR (já existe) | — |
| `data/apresentacoes/<slug>_APRESENTACAO_<tri>.pdf` | Apresentação institucional | CASE-03 |
| `config/empresas.toml` | Cadastro: nome, ticker, cor, segmentos (**sem números**) | CASE-01 |
| `metricas/<slug>_<tri>_itr_dfs.json` | Fatos das DFs padronizadas (gerado por código) | CASE-02 |
| `metricas/<slug>_<tri>_itr_complementar.json` | EBITDA contábil/ajustado, ajustes, dívida reportada | CASE-02 |
| `metricas/<slug>_<tri>_itr_operacional.json` | Volumes, R$/t, segmentos vindos do ITR/release | CASE-03 |
| `metricas/<slug>_<tri>_apresentacao_operacional.json` | Idem, vindos da apresentação | CASE-03 |
| `metricas/<slug>_<tri>_apresentacao_qualitativo.json` | Temas da apresentação institucional | CASE-03 |
| `metricas/<slug>_<tri>_indicadores.json` | Indicadores calculados | CASE-04 |
| `saida/comparativo/<a>_x_<b>_<tri>/` | `comparativo.json`, `tabela.csv`, `graficos/*.png` | CASE-05 |
| `narrativa/<a>_x_<b>_<tri>.json` | Títulos-mensagem e bullets dos slides | CASE-06 |
| `entrega/apresentacao_<a>_x_<b>_<tri>.html` | Apresentação final (versionada) | CASE-06 |

`slug` = minúsculo, sem acento (`gerdau`, `usiminas`). `tri` = `3T26`.

**Regra de ouro dos JSONs de fatos: um arquivo = um documento-fonte.** O pedaço `itr`/`apresentacao` do nome diz em qual `saida/<pdf>/` o verificador procura. Assim cada arquivo roda no `verificar_numeros.py` sem alteração.

### Fato (item de `metricas/*_itr_*.json` e `*_apresentacao_*.json`)

Lista JSON no topo (compatível com o verificador atual). Campos novos são ignorados pelo verificador.

```json
{
  "chave": "receita_liquida",
  "metrica": "Receita de Venda de Bens e/ou Serviços",
  "empresa": "gerdau",
  "documento": "itr",
  "escopo": "consolidado",
  "periodo": "3T26",
  "unidade": "R$ mil",
  "valor": 0.0,
  "valor_como_aparece": "<literal da página>",
  "pagina": 29,
  "trecho": "<cópia literal da página>",
  "codigo_cvm": "3.01"
}
```

- `chave`: do catálogo abaixo. `metrica`: nome legível (o verificador imprime esse campo, é **obrigatório**).
- `documento`: `itr` | `apresentacao`.
- `escopo`: `consolidado` ou `segmento:<slug_do_segmento>` (ex.: `segmento:america_do_norte`, `segmento:mineracao`). Nunca controladora/holding.
- `unidade`: **como aparece no documento** (`R$ mil`, `R$ milhões`, `mil t`, `R$/t`, `US$/t`, `%`, `x`). A conversão é feita em código no CASE-04.
- `pagina` e `trecho`: **obrigatórios em todo fato**. Número sem página não entra no JSON nem na apresentação.
- `pagina`: índice do PDF a partir de 1 (o mesmo de `pagina_NN.txt` e o que o leitor de PDF mostra), não o número impresso no rodapé da folha nem o "PÁGINA: X de N" do formulário CVM. Ex.: a DRE consolidada da Gerdau é `pagina` 29, impressa como 24 e "PÁGINA: 16 de 65".
- Opcionais: `codigo_cvm`, `obs`, e os campos do verificador `anterior`, `anterior_como_aparece`, `variacao_pct`.
- Rastreabilidade obrigatória: `documento_id` identifica o PDF exato (caminho e hash em manifesto), `data_documento`, `moeda` quando monetário, `criterio` (contábil/ajustado quando aplicável), início/fim do período e evidência da unidade e dos cabeçalhos. `documento` sozinho identifica apenas o tipo. O manifesto mantém URL, data de acesso e data de referência do documento.
- Registrar ausência separadamente em um relatório de cobertura: `ausente`, `nao_aplicavel` ou `nao_comparavel`, com motivo. Não criar fato de valor zero para preencher ausência. `null` nos indicadores mantém essa distinção em `obs`/status.
- Apresentações de datas distintas preservam a data original; o nome do arquivo não transforma conteúdo histórico em dado do trimestre analisado. Guidance e metas são projeções identificadas, nunca resultados realizados.

**Rótulos de período**
- Fluxo (DRE, DFC, volumes): `3T26` (trimestre), `9M26` (acumulado do ano), `3T25`, `9M25`, `2T26`.
- Saldo (balanço, dívida, capacidade): o trimestre que termina na data. `3T26` = 30/09/2026, `4T25` = 31/12/2025.
- O tipo (fluxo ou saldo) vem do catálogo, não do rótulo.

### Catálogo de chaves de fatos

**DFs padronizadas CVM, consolidado (CASE-02, `*_itr_dfs.json`)**

| chave | Conta CVM | Tipo | Observação |
|---|---|---|---|
| `receita_liquida` | 3.01 | fluxo | |
| `cpv` | 3.02 | fluxo | vem negativo |
| `lucro_bruto` | 3.03 | fluxo | |
| `despesas_receitas_operacionais` | 3.04 | fluxo | |
| `ebit` | 3.05 | fluxo | inclui equivalência patrimonial |
| `resultado_financeiro` | 3.06 | fluxo | |
| `lair` | 3.07 | fluxo | |
| `ir_csll` | 3.08 | fluxo | |
| `lucro_liquido` | 3.11 | fluxo | consolidado |
| `lucro_liquido_controladores` | 3.11.01 | fluxo | |
| `ativo_total` | 1 | saldo | |
| `passivo_total` | 2 | saldo | só para checagem (= ativo) |
| `caixa_equivalentes` | 1.01.01 | saldo | |
| `aplicacoes_financeiras` | 1.01.02 | saldo | |
| `emprestimos_cp` | 2.01.04 | saldo | |
| `emprestimos_lp` | 2.02.01 | saldo | |
| `pl_total` | 2.03 | saldo | |
| `pl_nao_controladores` | 2.03.xx "Não Controladores" | saldo | código varia: achar pela descrição |
| `depreciacao_amortizacao` | 6.01.01.xx "Deprecia..." | fluxo (9M) | código varia (Gerdau ≠ Usiminas) |
| `fco` | 6.01 | fluxo (9M) | |
| `capex` | 6.02.xx "imobilizado" (Adições/Compras/Aquisição) | fluxo (9M) | código e texto variam |

**Complementares do ITR/release (CASE-02, `*_itr_complementar.json`)**

| chave | Observação |
|---|---|
| `ebitda_contabil` | EBITDA Res. CVM 156, consolidado |
| `ebitda_ajustado` | consolidado |
| `ajuste_ebitda` | um item por ajuste; `metrica` = descrição do ajuste (ex.: impairment) |
| `depreciacao_amortizacao_tri` | D&A só do trimestre (a DFC só tem o acumulado) |
| `divida_bruta_reportada`, `divida_liquida_reportada` | como a empresa divulga |
| `dl_ebitda_reportado` | unidade `x` |

**Operacionais e por segmento (CASE-03, `*_operacional.json`)**

| chave | Unidade típica | Escopo |
|---|---|---|
| `volume_vendas` | mil t | consolidado e por segmento |
| `volume_producao` | mil t | aço bruto |
| `capacidade_instalada` | mil t/ano | saldo |
| `receita_por_t_reportada`, `custo_por_t_reportado`, `ebitda_por_t_reportado` | R$/t ou US$/t | |
| `receita_liquida`, `ebitda_ajustado` | R$ | **só** `segmento:*` (o consolidado é do CASE-02) |
| `volume_minerio` | mil t | mineração |
| `participacao_exportacao` | % | |

**Qualitativo (CASE-03, `*_apresentacao_qualitativo.json`)**

```json
{"chave": "qualitativo", "metrica": "estrategia", "tema": "estrategia", "empresa": "gerdau",
 "documento": "apresentacao", "resumo": "<palavras nossas, até 30>", "pagina": 5,
 "trecho": "<cópia literal curta, para o verificador>"}
```
Temas: `perfil`, `capacidade_footprint`, `mercados_produtos`, `estrategia`, `capex_investimentos`, `guidance_perspectivas`, `riscos`, `esg`, `destaques_trimestre`.

### `metricas/<slug>_<tri>_indicadores.json` (sai do CASE-04)

```json
{
  "empresa": "gerdau", "periodo": "3T26", "unidade_monetaria": "R$ milhões",
  "anualizacao": "9M26 × 4/3", "saldos_medios": "média de 4T25 e 3T26",
  "indicadores": [
    {"chave": "margem_ebitda_ajustada", "nome": "Margem EBITDA ajustada", "grupo": "margens",
     "unidade": "%", "melhor": "maior", "escopo": "consolidado",
     "valores": {"3T26": 0.0, "3T25": 0.0, "2T26": null},
     "var_aa": 0.0, "var_tt": null, "unidade_var": "p.p.",
     "formula": "ebitda_ajustado / receita_liquida",
     "insumos": [{"chave": "ebitda_ajustado", "periodo": "3T26", "documento": "itr", "pagina": 71}],
     "disponivel": true, "obs": null}
  ],
  "alertas": [{"tipo": "divergencia", "texto": "..."}]
}
```

### `saida/comparativo/<a>_x_<b>_<tri>/comparativo.json` (sai do CASE-05)

```json
{
  "periodo": "3T26", "criterio_ebitda": "ajustado",
  "empresas": {"a": {"slug": "gerdau", "nome": "Gerdau", "ticker": "GGBR4", "cor": "#..."},
               "b": {"slug": "usiminas", "nome": "Usiminas", "ticker": "USIM5", "cor": "#..."}},
  "linhas": [
    {"chave": "margem_ebitda", "nome": "Margem EBITDA ajustada", "grupo": "margens", "unidade": "%",
     "melhor": "maior", "vencedor": "a",
     "a": {"valor": 0.0, "texto": "0,0%", "var_aa": 0.0, "var_tt": null, "unidade_var": "p.p.",
           "fontes": ["ITR p.29", "ITR p.71"], "disponivel": true},
     "b": {"...": "..."}}
  ],
  "segmentos": {"a": [{"segmento": "brasil", "pct_receita": 0.0, "pct_ebitda": 0.0}], "b": []},
  "insights": [{"id": "margem", "texto": "...", "chaves": ["margem_ebitda"]}],
  "alertas": [{"tipo": "efeito_pontual", "empresa": "b", "texto": "..."}],
  "graficos": [{"id": "receita_ebitda", "arquivo": "graficos/receita_ebitda.png", "descricao": "..."}],
  "verificacao": null
}
```
`verificacao` é preenchido pelo CASE-07: `{"total": N, "ok": N, "por_arquivo": {...}}`.

### `narrativa/<a>_x_<b>_<tri>.json` (CASE-06)

```json
{"slides": [
  {"id": "capa", "titulo": "<mensagem principal>", "subtitulo": "..."},
  {"id": "resumo", "titulo": "...", "bullets": ["...", "...", "..."]}
]}
```
Ids: `capa`, `resumo`, `perfil`, `comparativo`, `graficos`, `setor`, `destaques_riscos`, `metodologia`.

### Regras gerais (todos os cards)

1. **Nenhum número de memória.** Todo número vem de um JSON verificado ou é calculado em código a partir dele. As fixtures são de empresas fictícias (`empresa_a`, `empresa_b`) justamente para nunca vazarem para a apresentação real.
2. **Consolidado sempre.** Nada de `DFs Individuais` nem do comentário da holding.
3. Todo fato tem `pagina` (índice do PDF) e `trecho`; `trecho` e `valor_como_aparece` são cópias literais do `pagina_NN.txt`.
4. Unidade registrada como aparece; conversão só em código.
5. Rotular A/A (3T26 × 3T25) e T/T (3T26 × 2T26). Sem dado de 2T26 → `null`, nunca estimar.
6. Cada erro que o verificador ou você pegar vai em `docs/registro/<seu-nome>.md` (empresa, métrica, o que o Claude disse, o que estava no ITR, como pegou, correção). É material do vídeo e do README.
7. Prompts que funcionaram vão no mesmo arquivo.
8. Conflitos entre fontes ficam registrados com ambos os valores e suas referências. ITR tem preferência para fatos contábeis de mesmo critério; essa preferência não resolve divergência entre escopos, períodos ou EBITDA contábil/ajustado.
9. Indicadores por tonelada exigem numerador e denominador do mesmo negócio, produto, período, moeda e escopo. Receita consolidada incluindo mineração não pode ser dividida só pelo volume de aço.
10. Em `comparativo.json`, gráficos e slides, "p. X" é sempre o índice do PDF (o mesmo `pagina` dos JSONs), nunca o número impresso na folha. O slide de metodologia avisa: "páginas na numeração do PDF".

**Definição de pronto (todo card):** PR aberto para `main`; testes passando (`pytest`); nenhum arquivo de outro dono alterado (exceto catálogo em `contrato.py`); registro de erros/prompts atualizado.

---

## Cards

### CASE-01 · Contrato de dados, catálogo e fixtures

**Responsável:** João Vitor · **Branch:** `Joao-Maia` · **Prioridade:** P0, primeira coisa do dia · **Estimativa:** 45 min
**Depende de:** — · **Bloqueia:** todos (merge cedo; ninguém precisa esperar para começar)

**Contexto.** Quatro branches em paralelo só funcionam se todos escreverem e lerem o mesmo formato. O contrato está acima; este card transforma ele em código e dados de teste.

**Escopo**
1. `docs/CONTRATO_DADOS.md`: a seção "Contrato de dados" deste arquivo, como referência oficial.
2. `src/contrato.py`:
   - `CATALOGO_FATOS` (chave → nome, tipo fluxo/saldo, código CVM quando houver).
   - `carregar_fatos(slug, tri, pasta="metricas") -> list[dict]`: lê todos os `metricas/{slug}_{tri}_*.json`, menos `_indicadores`.
   - `validar_fato(d) -> list[str]`: campos obrigatórios, chave no catálogo, período e escopo válidos.
   - `para_milhoes(valor, unidade)`: `R$ mil` → ÷1000, `R$ milhões` → ×1, `R$ bilhões` → ×1000; unidade desconhecida → erro.
   - `periodo_comparavel(tri, "aa" | "tt")`: `3T26` → `3T25` / `2T26`.
   - `pasta_saida(slug, tri, documento)`: devolve `saida/<slug>_ITR_<tri>` ou `saida/<slug>_APRESENTACAO_<tri>`.
   - `fmt_br(valor, unidade)`: `R$ 12.345,6 mi`, `18,2%`, `+2,1 p.p.`, `1,8x` (usado por 05 e 06).
3. `config/empresas.toml`: `gerdau` e `usiminas` com nome, ticker, cor e lista de segmentos (Gerdau: Brasil, América do Norte, América do Sul; Usiminas: Mineração, Siderurgia, Transformação do Aço — confirmar no ITR), mais observações ("comentário de desempenho da Gerdau é da holding"). Sem números. Ler com `tomllib` (nativo).
4. Fixtures fictícias em `tests/fixtures/`: fatos de `empresa_a` e `empresa_b` (todas as chaves do catálogo, 3T26/3T25/9M26/9M25 e saldos 3T26/4T25), um `*_indicadores.json` e um `comparativo.json` completo com 2 PNGs placeholder. Valores redondos e claramente falsos.
5. `requirements.txt` + `pyproject.toml`: adicionar `pytest`; `[tool.pytest.ini_options] pythonpath = ["src"]`.
6. `CLAUDE.md`: atualizar o fluxo e a convenção de arquivos (o Claude Code de todos lê isso sozinho).
7. Criar `docs/registro/` com um arquivo vazio por pessoa.
8. Formalizar os campos de rastreabilidade e cobertura acima e a configuração de setor, moeda e aplicabilidade. Acrescentar uma terceira empresa fictícia, com dados incompletos, para testar generalização sem nomes fixos. O catálogo deve aceitar novas empresas só por configuração e dados.

**Critérios de aceite**
- [ ] `pytest` roda; `validar_fato` aceita todas as fixtures e rejeita um fato sem `pagina`.
- [ ] `para_milhoes` e `fmt_br` com testes.
- [ ] PR mergeado no `main` e time avisado para dar `pull --rebase`.

**Arquivos:** `src/contrato.py`, `config/empresas.toml`, `tests/fixtures/**`, `tests/test_contrato.py`, `docs/CONTRATO_DADOS.md`, `docs/registro/*`, `requirements.txt`, `pyproject.toml`, `CLAUDE.md`.

---

### CASE-02 · Extração financeira do ITR (parser CVM + EBITDA)

**Responsável:** Gabriel Martins · **Branch:** `feat/gabriel-martins` · **Prioridade:** P0 · **Estimativa:** 3 h
**Depende de:** contrato (já neste doc) · **Bloqueia:** CASE-04 (dados reais), CASE-07

**Contexto.** As DFs consolidadas estão no formato padronizado da CVM: Gerdau p. 26–33 (BP 26–28, DRE 29–30, DFC 32–33), Usiminas p. 12–17 (índices do PDF). O código de conta é o mesmo para qualquer empresa; o que varia são subcontas como D&A (`6.01.01.02` numa, `6.01.01.04` na outra) e capex ("Adições de imobilizado" × "Compras de Imobilizado"). Um parser determinístico aqui é o que torna o produto genérico.

**Escopo**
1. `src/dfs_cvm.py <pasta_saida> --empresa <slug> --tri <tri>` → `metricas/<slug>_<tri>_itr_dfs.json`:
   - Achar as páginas pelo cabeçalho `DFs Consolidadas / Balanço Patrimonial Ativo|Passivo`, `/ Demonstração do Resultado`, `/ Demonstração do Fluxo de Caixa`. Ignorar `DFs Individuais` e páginas de índice (exigir linhas com código de conta).
   - Juntar demonstrações que continuam na página seguinte (a DRE da Gerdau ocupa 2 páginas).
   - Ler as colunas **pelas datas do cabeçalho**, não por posição fixa: assim funciona para 1T (DRE com 2 colunas), 2T e 3T de qualquer ano. Converter as datas nos rótulos do contrato (3T26, 9M26, 3T25, 9M25; saldos 3T26 e 4T25).
   - Mapear código → chave (tabela do contrato). Contas sem código fixo por regex na descrição, dentro do grupo certo (`6.01.01.*`, `6.02.*`, `2.03.*`).
   - `valor_como_aparece` = token literal (ex.: `-880.867`); `trecho` = a linha inteira; `unidade` = `R$ mil` (lida do cabeçalho `(Reais Mil)`).
   - Checagens de consistência em código: `lucro_bruto == receita_liquida + cpv`; `ativo_total == passivo_total`; `lucro_liquido == controladores + não controladores`. Falhou → erro explícito.
2. `tests/test_dfs_cvm.py` com recortes pequenos de páginas reais (incluir um caso de DRE em 2 páginas e um de subconta com código diferente).
3. Complementar, assistido pelo Claude Code → `metricas/<slug>_<tri>_itr_complementar.json` com `ebitda_contabil`, `ebitda_ajustado`, cada `ajuste_ebitda`, `depreciacao_amortizacao_tri`, `divida_*_reportada`, `dl_ebitda_reportado` (3T26, 3T25 e 2T26 se houver; consolidado).
   - Gerdau: notas "Informações por segmentos de negócio" (pág. impressa 71–74). **O comentário de desempenho (pág. 2 em diante) é da holding: não usar.**
   - Usiminas: release dentro do ITR (pág. 21–47). Atenção à mistura R$ mil × R$ milhões.
   - Procurar efeitos pontuais no 3T25 e no 2T26 (ex.: comparar a linha 3.04 da Usiminas entre 3T26 e 3T25 na p. 14) e registrar cada um como `ajuste_ebitda`.
   - Prompt reutilizável em `prompts/extracao_financeira_complementar.md` (sem nada específico de empresa).
4. `verificar_numeros.py` nos 4 arquivos (2 empresas × dfs/complementar) até 100% OK.
5. Endurecer `src/verificar_numeros.py` e criar `tests/test_verificar_numeros.py`: rejeitar campos obrigatórios ausentes; verificar token na linha/contexto citado; exigir evidências do período, unidade e consolidado/segmento. Testar um número que existe na página, mas pertence à coluna ou ao escopo errado. Onde a automação não comprovar o vínculo, marcar revisão pendente; não declarar validação semântica completa por mera ocorrência do token.
6. PDF sem camada de texto ou layout não suportado gera diagnóstico acionável e etapa assistida; nunca JSON vazio tratado como sucesso. Não fixar páginas nem subcontas por empresa.

**Fora de escopo:** volumes, R$/t e dados por segmento (CASE-03); cálculo de indicadores (CASE-04).

**Critérios de aceite**
- [ ] O mesmo comando funciona para Gerdau e Usiminas, sem `if empresa == ...`.
- [ ] Extrair os períodos efetivamente divulgados e emitir cobertura das chaves ausentes. DFC acumulada não vira trimestral sem saldos acumulados anteriores compatíveis. Ausência não impede estruturar os demais dados.
- [ ] Checagens de consistência passam nas duas empresas.
- [ ] Verificador: 100% OK nos 4 arquivos.
- [ ] Erros e prompts em `docs/registro/gabriel-martins.md`.

**Arquivos:** `src/dfs_cvm.py`, `src/verificar_numeros.py`, `tests/test_dfs_cvm.py`, `tests/test_verificar_numeros.py`, `prompts/extracao_financeira_complementar.md`, `metricas/*_itr_dfs.json`, `metricas/*_itr_complementar.json`, `docs/registro/gabriel-martins.md`.

---

### CASE-03 · Apresentação institucional + dados operacionais e qualitativos

**Responsável:** Geronimo · **Branch:** `feat/geronimo` · **Prioridade:** P0 · **Estimativa:** 3 h
**Depende de:** contrato (já neste doc) · **Bloqueia:** CASE-04 (dados reais), CASE-06 (slides de perfil e riscos), CASE-07

**Contexto.** O ITR não tem tudo. A Gerdau quase não fala de toneladas no ITR; a Usiminas tem volumes no release (pág. 21–47). Volume, R$/t, capacidade, mix e o "quem é quem" (estratégia, footprint, guidance, riscos) vêm do release e da apresentação institucional, e entram nos slides de perfil, setor e riscos.

**Escopo**
1. Baixar dos sites de RI as apresentações institucionais (a mais recente, de preferência do 3T26) → `data/apresentacoes/<slug>_APRESENTACAO_<tri>.pdf`. Registrar URL e data de acesso em `data/apresentacoes/FONTES.md`.
2. Rodar `extrair_release.py` nelas (já funciona para qualquer PDF). Se alguma página sair sem texto (slide em imagem), registrar e não usar números dela.
3. `src/localizar_paginas.py <pasta_saida> --tema operacional|qualitativo|ebitda [--top 10]`: ranking de páginas por palavras-chave (toneladas, mil t, R$/t, capacidade, embarques, vendas, exportação, segmento; estratégia, perspectivas, guidance, capex, riscos). Genérico, sem nada de empresa. O CASE-07 usa isso.
4. Prompts reutilizáveis: `prompts/extracao_operacional.md` e `prompts/extracao_qualitativa.md` (entrada: páginas candidatas; saída: JSON no contrato; regras: literal, unidade como aparece, consolidado × segmento).
5. Gerar com o Claude Code, por empresa:
   - `metricas/<slug>_<tri>_itr_operacional.json`: o que estiver no ITR (Usiminas: release; Gerdau: notas de segmento, pág. 71–74 → receita e EBITDA por segmento).
   - `metricas/<slug>_<tri>_apresentacao_operacional.json`: volumes, R$/t, capacidade, mix, exportação.
   - `metricas/<slug>_<tri>_apresentacao_qualitativo.json`: 5 a 8 temas, `resumo` em palavras nossas (a regra de uso dos dados proíbe trechos longos), `trecho` curto e literal só para verificar.
6. Verificar todos os arquivos com `verificar_numeros.py` (pasta certa para cada documento) até 100% OK.
7. Preservar data e referência de cada apresentação, distinguir afirmação da administração de fato realizado e marcar metas/guidance. Não preencher os cinco temas por inferência quando não estiverem no documento; emitir cobertura e pendências. PDF sem texto deve ser identificado como não suportado no MVP.

**Fora de escopo:** dados consolidados das DFs e EBITDA consolidado (CASE-02); cálculos (CASE-04).

**Critérios de aceite**
- [ ] Buscar volumes, receita/EBITDA por segmento e capacidade nos períodos divulgados; cada item disponível tem fonte, cada ausência tem motivo no relatório de cobertura.
- [ ] Qualitativo cobre os temas disponíveis, buscando ao menos `perfil`, `estrategia` e `riscos` ou `guidance_perspectivas`; temas não divulgados ficam explícitos.
- [ ] Verificador: 100% OK em todos os arquivos.
- [ ] `localizar_paginas.py` testado nas duas empresas sem mudar código.
- [ ] Erros e prompts em `docs/registro/geronimo.md`.

**Arquivos:** `data/apresentacoes/*`, `src/localizar_paginas.py`, `tests/test_localizar_paginas.py`, `prompts/extracao_operacional.md`, `prompts/extracao_qualitativa.md`, `metricas/*_operacional.json`, `metricas/*_qualitativo.json`, `docs/registro/geronimo.md`.

---

### CASE-04 · Motor de indicadores

**Responsável:** Gabriel Patrício · **Branch:** `feat/gabriel-patricio` · **Prioridade:** P0 · **Estimativa:** 2 h
**Depende de:** CASE-01 para começar (`contrato.py` + fixtures); 02 e 03 para rodar com dados reais · **Bloqueia:** CASE-05

**Contexto.** Margens, rentabilidade e alavancagem não aparecem prontas no ITR (ou aparecem com critérios diferentes entre empresas). Calcular tudo em código, a partir dos fatos verificados, é o que garante a mesma régua para as duas.

**Escopo**
1. `src/indicadores.py --empresa <slug> --tri <tri>` → `metricas/<slug>_<tri>_indicadores.json` (formato do contrato).
2. Carregar fatos com `contrato.carregar_fatos`, converter tudo para R$ milhões e resolver duplicatas (mesma chave, período e escopo em dois arquivos): prioridade `itr` > `apresentacao`; diferença acima de 0,5% → `alerta` do tipo `divergencia`.
3. Indicadores (cada um com `formula`, `insumos` com página, `var_aa` e `var_tt`; variação em p.p. para %):

| Grupo | Indicador | Fórmula |
|---|---|---|
| Escala | Receita, EBIT, lucro líquido, EBITDA contábil e ajustado | fatos |
| Margens | Bruta, EBIT, EBITDA (contábil e ajustada), líquida | ÷ receita líquida |
| Endividamento | Dívida bruta | `emprestimos_cp + emprestimos_lp` |
| | Caixa | `caixa_equivalentes + aplicacoes_financeiras` |
| | Dívida líquida | dívida bruta − caixa (comparar com a reportada) |
| | DL/EBITDA | DL ÷ EBITDA 9M26 anualizado (×4/3); mostrar ao lado do `dl_ebitda_reportado` (LTM) |
| | DL/PL | DL ÷ `pl_total` |
| Rentabilidade (9M26 anualizado, saldos médios 4T25–3T26) | ROE | `lucro_liquido_controladores` ÷ (`pl_total − pl_nao_controladores`) |
| | ROA | `lucro_liquido` ÷ `ativo_total` |
| | ROI | `ebit` ÷ capital investido (DL + `pl_total`), antes de impostos |
| | ROIC | NOPAT ÷ capital investido; NOPAT = EBIT × (1 − alíquota efetiva 9M de `ir_csll/lair`, limitada a 0–34%) |
| Caixa | FCL 9M | `fco + capex` (capex vem negativo) |
| | Capex/receita | 9M |
| Setor | Volume vendido | fato (consolidado e segmentos) |
| | Receita/t, CPV/t, EBITDA/t | ÷ `volume_vendas`; usar o segmento de aço quando a empresa tiver mineração; se só houver consolidado, `obs` dizendo isso |
| | Mix de segmentos | % da receita e do EBITDA por segmento |

4. Dado faltando → `disponivel: false` + `obs` com o motivo. Nunca estimar. (Ex.: EBITDA contábil do trimestre sem D&A trimestral → indisponível.)
5. `docs/METODOLOGIA_INDICADORES.md`: fórmulas, anualização, saldos médios e escolhas (vai para o slide de metodologia e o README).
6. `tests/test_indicadores.py` com as fixtures, valores esperados calculados à mão.
7. Concluir o `src/indicadores.py` parcial já existente: registro dos indicadores, chamada dos cálculos, CLI e serialização. Revisar o fallback provisório de contrato e a função `_por_tonelada`; importar o contrato oficial quando CASE-01 estiver integrado.
8. Fórmulas da tabela são convenções propostas, a documentar. ROI não tem definição única: rotular explicitamente como retorno sobre capital investido antes de impostos. ROIC deve declarar a política tributária; limitar alíquota ou adotar 34% é hipótese metodológica e exige identificação e parametrização. Não apresentar essas hipóteses como dado reportado.
9. Para A/A de retornos com saldos médios, buscar também o saldo inicial do ano anterior (ex.: 4T24 para 9M25); sem ele, variação fica indisponível. LTM e acumulado anualizado são bases distintas. Não substituir uma silenciosamente pela outra. Sem escopo compatível, receita/t e EBITDA/t ficam não comparáveis.

**Critérios de aceite**
- [ ] Roda nas fixtures e, quando 02/03 mergearem, em Gerdau e Usiminas sem mudar código.
- [ ] Todo indicador com `insumos` rastreáveis até página.
- [ ] Testes cobrem conversão de unidade, p.p. × %, duplicata divergente e dado faltante.

**Arquivos:** `src/indicadores.py`, `tests/test_indicadores.py`, `docs/METODOLOGIA_INDICADORES.md`, `metricas/*_indicadores.json`, `docs/registro/gabriel-patricio.md`.

---

### CASE-05 · Comparativo, insights e gráficos

**Responsável:** João Vitor · **Branch:** `Joao-Maia` · **Prioridade:** P1 · **Estimativa:** 1,5 h
**Depende de:** CASE-04 · **Bloqueia:** CASE-06 (dados reais), CASE-07

**Contexto.** A Gerdau é bem maior que a Usiminas: a história está em margens, variações e mix, não em valor absoluto. Este card transforma dois `indicadores.json` no material que a apresentação consome.

**Escopo**
1. `src/comparar.py --a <slug> --b <slug> --tri <tri>` → `saida/comparativo/<a>_x_<b>_<tri>/` com `comparativo.json`, `tabela.csv`, `tabela.md`, `graficos/`.
2. **Mesmo critério de EBITDA para as duas:** `ajustado` se as duas têm, senão `contabil`. Gravar em `criterio_ebitda`.
3. Cada linha com valores, variações, `vencedor` (pela regra `melhor` maior/menor), `texto` já formatado com `contrato.fmt_br` e `fontes` com página.
4. `insights` determinísticos com números (base para os títulos dos slides): maior diferença de margem, quem cresceu mais A/A, alavancagem, R$/t e EBITDA/t, peso de exterior/mineração no EBITDA.
5. `alertas`: efeito pontual (ajuste relevante no 3T25 ou 2T26 distorcendo a variação), divergência calculado × reportado, indicador indisponível, negócios diferentes (mix de segmentos).
6. Gráficos (matplotlib, 16:9, cores do `config/empresas.toml`, rótulos em pt-BR, "Fonte: ITR 3T26, p. X" no rodapé, com X = índice do PDF):
   1. Receita e EBITDA, 3T26 × 3T25;
   2. Margens lado a lado;
   3. DL/EBITDA (calculado e reportado);
   4. Volume e R$/t;
   5. Mix de segmentos (receita e EBITDA).
7. Antes de comparar, validar período, moeda, escopo, critério e metodologia. Sem EBITDA de mesmo critério nas duas, apresentar N/C com motivo. `vencedor` só existe em linha comparável com regra econômica justificada; não eleger vencedor global, nem tratar maior receita como melhor desempenho. Dívida e retorno com base negativa exigem tratamento específico.
8. Generalização obrigatória: terceira empresa fictícia e inversão A/B; inclusão por configuração sem alteração no código. Exibir N/D, N/A e N/C com motivos, sem converter ausência em zero.

**Critérios de aceite**
- [ ] Trocar `--a/--b` funciona (testar com `empresa_a`/`empresa_b` invertidas).
- [ ] Nenhum gráfico com unidade misturada; todo gráfico com fonte.
- [ ] `comparativo.json` passa no formato do contrato.

**Arquivos:** `src/comparar.py`, `src/graficos.py`, `tests/test_comparar.py`.

---

### CASE-06 · Gerador da apresentação executiva

**Responsável:** Gabriel Patrício · **Branch:** `feat/gabriel-patricio` · **Prioridade:** P1 · **Estimativa:** 2,5 h
**Depende de:** fixture de `comparativo.json` (CASE-01) para começar; CASE-05 e qualitativo do CASE-03 para fechar · **Bloqueia:** CASE-07, CASE-08

**Contexto.** O diretor quer 6 a 8 slides com a mensagem no título, todo número com página. A apresentação institucional entra no perfil das empresas e nos riscos.

**Escopo**
1. `src/apresentacao.py --comparativo <pasta> [--narrativa <json>]` → `saida/apresentacao/<a>_x_<b>_<tri>.html`: arquivo único (CSS e imagens embutidos em base64), 16:9, navegação por teclado, CSS de impressão para gerar PDF pelo navegador. Opcional: `.pptx` com `python-pptx`.
2. Slides:

| # | id | Conteúdo |
|---|---|---|
| 1 | `capa` | Mensagem principal: quem foi melhor e por quê |
| 2 | `resumo` | 3 conclusões, cada uma com um número |
| 3 | `perfil` | Quem são as empresas (apresentação institucional): perfil, capacidade/footprint, mercados, estratégia + mix de segmentos |
| 4 | `comparativo` | Tabela enxuta (6–8 linhas), vencedor destacado, fonte por linha |
| 5 | `graficos` | Receita, EBITDA e margem, 3T26 × 3T25 (A/A rotulado) |
| 6 | `setor` | Volume, R$/t, EBITDA/t, DL/EBITDA |
| 7 | `destaques_riscos` | 1 positivo e 1 negativo por empresa + o que observar (guidance/riscos) + alertas de efeito pontual |
| 8 | `metodologia` | Páginas (numeração do PDF, não a impressa), contábil × ajustado, anualização, `verificacao` (X/Y números conferidos), aviso |

3. Rodapé em todos os slides: fontes com a página na numeração do PDF ("Gerdau — ITR p. 29; Apresentação p. 7") e "Não constitui recomendação de investimento".
4. `narrativa/<a>_x_<b>_<tri>.json`: títulos-mensagem e bullets escritos com o Claude Code **a partir do `comparativo.json`**. Sem narrativa → usar `insights` automáticos (o produto continua genérico).
5. **Verificador de narrativa:** cada afirmação numérica referencia a chave da métrica, empresa, período, critério e fonte; o código resolve e formata os valores. Testar troca indevida de empresa/período e fatos qualitativos sem fonte. A simples existência de um número igual no JSON não comprova a afirmação. Datas e números de slides devem ser tratados separadamente dos valores financeiros.
6. Gerar a versão final em `entrega/apresentacao_gerdau_x_usiminas_3T26.html` (versionada).

**Critérios de aceite**
- [ ] Gera os 8 slides a partir da fixture e, depois, de Gerdau × Usiminas, sem mudar código.
- [ ] Títulos comunicam conclusões sustentadas pelos dados; quando faltarem evidências, comunicam a limitação e não inventam uma conclusão.
- [ ] Verificador de narrativa passa.
- [ ] Abre bem no navegador e imprime em PDF sem cortar.

**Arquivos:** `src/apresentacao.py`, `templates/slides/*`, `narrativa/*`, `entrega/*`, `tests/test_apresentacao.py`, `docs/registro/gabriel-patricio.md`.

---

### CASE-07 · Pipeline "um comando" + relatório de verificação

**Responsável:** Gabriel Martins · **Branch:** `feat/gabriel-martins` (rebase no `main` depois do merge do CASE-02) · **Prioridade:** P1 · **Estimativa:** 1,5 h
**Depende de:** 02, 04, 05, 06 mergeados (+ prompts e `localizar_paginas.py` do 03). Dá para começar com stubs a partir do M1. · **Bloqueia:** CASE-08

**Contexto.** O bônus do case: trocar só os PDFs e ter a apresentação de novo. O que é determinístico roda sozinho; o que precisa do Claude vira uma instrução pronta.

**Escopo**
1. `src/pipeline.py --a <slug> --b <slug> --tri <tri> [--forcar] [--permitir-pendencias]`:
   1. Confere os insumos (`data/itrs/{slug}_ITR_{tri}.pdf`, `data/apresentacoes/{slug}_APRESENTACAO_{tri}.pdf`).
   2. Extrai páginas se `saida/<pdf>/` não existir (ou com `--forcar`).
   3. Roda `dfs_cvm`.
   4. Faltou JSON assistido (complementar, operacional, qualitativo)? Para e imprime o prompt pronto (de `prompts/`) já com as páginas candidatas do `localizar_paginas.py`, para colar no Claude Code.
   5. Valida o contrato e verifica **somente arquivos de fatos de entrada**, excluindo `*_indicadores.json` e relatórios derivados. Importa `checar` do verificador na pasta do documento exato e grava `saida/verificacao_<a>_x_<b>_<tri>.json`. Erro bloqueia a entrega. `--permitir-pendencias` gera apenas rascunho identificado, excluindo fatos reprovados de cálculos e slides; ausência legítima pode seguir como N/D com motivo.
   6. Indicadores → comparativo (preenchendo `verificacao`) → apresentação.
2. Idempotente: rodar duas vezes não muda nada.
3. Teste de fumaça com as fixtures.
4. Obrigatório: integrar terceira empresa fictícia sem alterar o código, testar A/B invertidos, arquivo ausente, fato reprovado e execução repetida com indicadores antigos presentes. Recomendado: validar uma terceira empresa real fornecida pelo time e documentar os limites do adaptador. Três empresas não comprovam cobertura universal.
5. O modo inicial é assistido: se faltar extração complementar, o comando pausa e orienta a revisão, retomando depois. Extração totalmente automática requer integração adicional com modelo e configuração de acesso; não está implementada apenas por imprimir prompts.

**Critérios de aceite**
- [ ] `python src/pipeline.py --a gerdau --b usiminas --tri 3T26` gera a apresentação final.
- [ ] Invertendo `--a/--b`, funciona.
- [ ] Item reprovado no verificador interrompe o fluxo com mensagem útil.

**Arquivos:** `src/pipeline.py`, `tests/test_pipeline.py`.

---

### CASE-08 · Entrega: Skill, README, registros, publicação e vídeo

**Responsável:** Geronimo · **Branch:** `feat/geronimo` (rebase no `main` depois do merge do CASE-03) · **Prioridade:** P1 · **Estimativa:** 1,5 h
**Depende de:** nada para rascunhar; de todos para fechar · **Bloqueia:** —

**Contexto.** A banca lê o README primeiro, assiste 2 minutos de vídeo e quer ver onde o Claude errou. 35% da nota (Rigor + Comunicação) mora aqui.

**Escopo**
1. Skill `.claude/skills/apresentacao-resultados/SKILL.md` no padrão de `referencia/SKILL_exemplo_bcb-sgs.md`: quando usar, passo a passo (pipeline + etapas assistidas com os prompts de `prompts/`), o que nunca fazer (número de memória, holding, misturar unidades, comparar contábil com ajustado), como verificar.
2. `README.md` preenchido no modelo: equipe, problema, solução, como funciona (o diagrama do topo deste doc), dados, **como verificamos (2–3 exemplos reais de erro pego)**, como reproduzir (o comando do CASE-07), limitações e próximos passos. Remover a seção "Para o time".
3. Consolidar `docs/registro/*.md` em `docs/ERROS_ENCONTRADOS.md` e `docs/PROMPTS.md`.
4. Publicar a apresentação (GitHub Pages ou artefato público) e testar numa aba anônima; links no README.
5. `docs/ROTEIRO_VIDEO.md`: 20s problema → 60s solução na tela → 20s um número conferido na fonte → 20s impacto. Combinar quem grava.
6. Rodar o `docs/CHECKLIST_ENTREGA.md` e enviar o formulário até 16h00.

**Critérios de aceite**
- [ ] Repositório público, README completo, links de vídeo e artefato funcionando em aba anônima.
- [ ] Pelo menos 3 erros reais documentados com página.
- [ ] Formulário enviado.

**Arquivos:** `.claude/skills/apresentacao-resultados/SKILL.md`, `README.md`, `docs/ERROS_ENCONTRADOS.md`, `docs/PROMPTS.md`, `docs/ROTEIRO_VIDEO.md`.
