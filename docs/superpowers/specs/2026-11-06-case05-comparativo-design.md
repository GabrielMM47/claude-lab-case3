# CASE-05 — Comparativo, insights e gráficos (spec)

Responsável: João Vitor · Branch `Joao-Maia` · Card em `docs/TAREFAS.md` (CASE-05).

## Intenção

Transformar dois `metricas/<slug>_<tri>_indicadores.json` (saída do CASE-04) em
`saida/comparativo/<a>_x_<b>_<tri>/` com `comparativo.json`, `tabela.csv`, `tabela.md`
e `graficos/*.png`, que o CASE-06 (`src/apresentacao.py`) consome.
Nenhum código, cor, chave ou texto específico de empresa: tudo vem dos indicadores e de
`config/empresas.toml`.

## Regras que valem para todos os módulos

1. **Nenhum número digitado.** Todo número sai de um `indicadores.json` ou é calculado a partir dele. Fixtures de teste usam só empresas fictícias (`empresa_a`, `empresa_b`, `empresa_c`).
2. Ausência nunca vira zero. Status por lado: `ok` (valor), `ausente` (N/D), `nao_comparavel` (N/C), `nao_aplicavel` (N/A), sempre com `obs` explicando o motivo quando não for `ok`.
3. "p. X" é sempre o índice do PDF (campo `pagina` dos `insumos`), nunca o número impresso.
4. Rotular variações: `var_aa` = A/A (3T26 × 3T25), `var_tt` = T/T (3T26 × 2T26). Sem base → `null`.
5. Sem vencedor global; maior receita/volume/dívida absoluta **não** é "melhor".

## Entradas

### `metricas/<slug>_<tri>_indicadores.json` (CASE-04, já existe em `main`)
Gerado por `python src/indicadores.py --empresa <slug> --tri <tri>`. Campos usados:
- topo: `empresa`, `periodo`, `setor`, `unidade_monetaria`, `unidade_volume`, `anualizacao`,
  `saldos_medios`, `criterios_ebitda` (lista: `contabil`, `ajustado`), `ajustes_ebitda`, `alertas`.
- `indicadores[]`: `chave`, `nome`, `grupo`, `unidade`, `melhor` (`maior`|`menor`|`neutro`),
  `escopo` (`consolidado` | `segmento:<nome>`), `periodo`, `valores` (dict período→número|null),
  `var_aa`, `var_tt`, `unidade_var` (`%`|`p.p.`), `insumos[]` (`documento`, `pagina`, ...),
  `disponivel`, `status`, `obs`.
- Indicadores com EBITDA vêm em duas versões: `<base>_contabil` e `<base>_ajustado`
  (`ebitda_*`, `margem_ebitda_*`, `dl_ebitda_*`, `ebitda_por_t_*`).
- Rentabilidade e caixa usam período acumulado (`9M26`), não `3T26`: usar o campo `periodo` do indicador.
- `alertas[]`: dicts com `tipo` (`efeito_pontual`, `divergencia`, `divergencia_definicao`, `unidade`, ...),
  `texto` e às vezes `chave`, `periodo`, `escopo`, `valores`.

### `config/empresas.toml`
```toml
[empresas.gerdau]
nome = "Gerdau"
ticker = "GGBR4"
cor = "#1f5fa8"

[empresas.usiminas]
nome = "Usiminas"
ticker = "USIM5"
cor = "#d9822b"
```
Slug ausente no TOML → nome = slug capitalizado, ticker = `null`, cor de uma paleta neutra de reserva
(e um alerta `tipo: "config"`). Se A e B tiverem a mesma cor, B usa a reserva.

## Módulos e interfaces

### 1. `src/contrato.py` (acréscimos; dono: João Vitor/CASE-01)
```python
def fmt_br(valor: float | None, unidade: str | None, casas: int | None = None, status: str = "ok") -> str
def fmt_var(valor: float | None, unidade_var: str | None, casas: int = 1) -> str
```
- `status != "ok"` → `"N/D"`/`"N/C"`/`"N/A"` (pela legenda); `valor is None` com `ok` → `"N/D"`.
- Separador de milhar `.`, decimal `,`; sinal negativo ASCII `-`.
- Tabela de formatos (casas padrão entre parênteses):
  | unidade | exemplo |
  |---|---|
  | `R$ milhões` (1) | `R$ 15.000,0 mi` |
  | `R$ mil` (0) | `R$ 1.234 mil` |
  | `%` (1) | `16,0%` |
  | `p.p.` (1) | `6,0 p.p.` |
  | `x` (2) | `0,57x` |
  | `mil t`, `mil t/ano` (0) | `1.034 mil t` |
  | `R$/t` (0) | `R$ 4.849/t` |
  | `US$/t` (0) | `US$ 75/t` |
  | outra/None (1) | `1.234,5 <unidade>` |
- `fmt_var`: sinal sempre explícito (`+5,6%`, `-4,8%`, `+6,0 p.p.`); `None` → `"—"`.

### 2. `schemas/comparativo.schema.json` + `contrato.escolher_schema`
JSON Schema (draft 2020-12) do `comparativo.json` abaixo. `escolher_schema` reconhece um dict com
`linhas` e `empresas` como `comparativo`. Campos obrigatórios = os marcados **(obr.)**; o resto é opcional
para que a fixture do CASE-06 (`origin/feat/gabriel-patricio:tests/fixtures_apresentacao/comparativo/empresa_a_x_empresa_b_3T26/comparativo.json`,
cópia em `tests/fixtures_comparar/comparativo_case06.json`) continue válida.
`python src/contrato.py saida/comparativo/<pasta>/comparativo.json` precisa sair com código 0.

### 3. `src/comparar.py` (CLI + funções puras)
```
python src/comparar.py --a <slug> --b <slug> --tri <tri>
    [--metricas metricas] [--config config/empresas.toml] [--saida saida/comparativo] [--sem-graficos]
```
Funções públicas (puras, testáveis sem disco):
```python
def carregar_config(caminho: Path) -> dict                         # slug -> {nome, ticker, cor}
def validar_compatibilidade(ind_a: dict, ind_b: dict, tri: str) -> tuple[list[dict], list[str]]
    # (alertas, erros_fatais). Fatal: periodo != tri em qualquer lado, unidade_monetaria diferente, slug A == slug B.
def escolher_criterio(ind_a: dict, ind_b: dict) -> str | None      # "ajustado" > "contabil" > None
def montar_comparativo(ind_a: dict, ind_b: dict, cfg: dict, tri: str) -> dict   # sem gráficos (graficos = [])
def escrever_saida(comp: dict, pasta: Path) -> None                 # comparativo.json, tabela.csv, tabela.md
def main(argv: list[str] | None = None) -> int                      # 0 ok, 1 entrada ausente, 2 incompatível
```
`main` chama `graficos.gerar_graficos(comp, pasta)` (salvo `--sem-graficos`), grava a lista retornada em
`comp["graficos"]`, escreve a saída e valida com `contrato.validar(comp, "comparativo")` (erro → código 2).
Entrada ausente → mensagem dizendo para rodar `python src/indicadores.py --empresa <slug> --tri <tri>`.

#### Catálogo de linhas (constante genérica em `comparar.py`; `{c}` = critério escolhido)
| chave da linha | indicador de origem | grupo | `melhor` na linha |
|---|---|---|---|
| `receita_liquida` | `receita_liquida` | escala | `null` (tamanho não é desempenho) |
| `ebitda_{c}` | `ebitda_{c}` | escala | `null` |
| `lucro_liquido` | `lucro_liquido` | escala | `null` |
| `margem_bruta` | `margem_bruta` | margens | do indicador |
| `margem_ebitda` | `margem_ebitda_{c}` | margens | do indicador |
| `margem_ebit` | `margem_ebit` | margens | do indicador |
| `margem_liquida` | `margem_liquida` | margens | do indicador |
| `divida_liquida` | `divida_liquida` | endividamento | `null` |
| `dl_ebitda` | `dl_ebitda_{c}` | endividamento | do indicador |
| `divida_liquida_pl` | `divida_liquida_pl` | endividamento | do indicador |
| `roe`, `roa`, `roic` | idem | rentabilidade | do indicador |
| `fco`, `fcl` | idem | caixa | `null` |
| `capex_receita` | idem | caixa | `null` (neutro) |
| `volume_vendas` | `volume_vendas` | setor | `null` |
| `receita_por_t` | `receita_por_t` | setor | do indicador |
| `ebitda_por_t` | `ebitda_por_t_{c}` | setor | do indicador |

Só escopo `consolidado`. Indicador inexistente → lado com status `ausente`, `obs` "indicador não calculado pelo CASE-04".
Sem critério comum (`escolher_criterio` → `None`): linhas com `{c}` saem com os dois lados `nao_comparavel`,
`obs` = "sem EBITDA de mesmo critério nas duas empresas", e `ebitda_{c}` vira `ebitda`.

#### Formato de `comparativo.json`
```json
{
  "periodo": "3T26",                                   (obr.)
  "criterio_ebitda": "ajustado",                       (obr., "ajustado" | "contabil" | null)
  "empresas": {"a": {"slug","nome","ticker","cor"}, "b": {...}},   (obr.)
  "metodologia": {"unidade_monetaria", "anualizacao", "saldos_medios", "politica_tributaria": {"a","b"}},
  "linhas": [                                          (obr.)
    {"chave", "nome", "grupo", "unidade", "periodo",   (obr. chave, nome, unidade, a, b)
     "melhor": "maior"|"menor"|null, "vencedor": "a"|"b"|null, "motivo_sem_vencedor": str|null,
     "a": {"valor": float|null, "texto": str, "valores": {"3T26":..,"3T25":..,"2T26":..},
           "var_aa": float|null, "var_tt": float|null, "unidade_var": "%"|"p.p."|null,
           "texto_var_aa": str, "texto_var_tt": str,
           "fontes": ["ITR p.29", "Apresentação p.12"], "disponivel": bool, "status": str, "obs": str|null},
     "b": {...}}
  ],
  "segmentos": {"a": [{"segmento","pct_receita","pct_ebitda","fontes"}], "b": [...]},  (obr.)
  "insights": [{"id","texto","chaves"}],               (obr.)
  "alertas": [{"tipo","empresa":"a"|"b"|null,"texto","chaves","fontes"}],  (obr.)
  "graficos": [{"id","arquivo","descricao","fontes":{"a":[...],"b":[...]}}],   (obr.)
  "verificacao": null                                  (obr.; preenchido pelo CASE-07)
}
```
- `fontes`: de `insumos`, `documento` `itr` → `"ITR p.N"`, `apresentacao` → `"Apresentação p.N"`, outro → `"<Documento> p.N"`; sem repetição, ordenadas por documento e página.
- `texto` com `contrato.fmt_br(valor, unidade, status=...)`; `texto_var_*` com `contrato.fmt_var`.
- `vencedor` só quando: os dois lados `ok`, mesma unidade, `melhor` da linha ∈ {maior, menor}, valores diferentes,
  e nenhuma base negativa (para `dl_ebitda`: EBITDA ≤ 0 em algum lado; `roe`: PL ≤ 0; `divida_liquida_pl`: PL ≤ 0 →
  sem vencedor, `motivo_sem_vencedor` explicando). Senão `null` com `motivo_sem_vencedor`.
- Inverter A/B gera as mesmas linhas com `a`/`b` trocados e `vencedor` trocado.

#### Segmentos
De `participacao_receita` e `participacao_ebitda` com escopo `segmento:<nome>` (valor do período `tri`), juntando por nome.
Segmento só com um dos dois → o outro `null`. Ordenar por `pct_receita` decrescente (null por último).

#### Insights (determinísticos; cada um só se houver dado; texto com `fmt_br`/`fmt_var` e nomes da config)
| id | conteúdo |
|---|---|
| `margem` | a linha de margem (`margem_*`) com maior diferença absoluta entre A e B, em p.p., com os dois valores |
| `crescimento` | `var_aa` da receita das duas (e de EBITDA se houver) |
| `alavancagem` | `dl_ebitda` das duas, com a `obs` de anualização quando existir |
| `por_tonelada` | `receita_por_t`/`ebitda_por_t`; se N/C em algum lado, dizer o motivo |
| `mix` | para cada empresa, o segmento com maior `pct_ebitda` e seu peso |

#### Alertas
- Repassar os alertas dos indicadores de cada lado (`empresa` = `a`/`b`) dos tipos `efeito_pontual`, `divergencia`,
  `divergencia_definicao`; os do tipo `unidade` viram **um** alerta-resumo por empresa (contagem + primeiro texto).
- `efeito_pontual`: `chaves` = linhas cuja variação usa o período afetado (período de `alerta["periodo"]`, ou o
  primeiro `\dT\d\d` do texto). 3T25 → linhas com `var_aa` que dependem de EBITDA (`ebitda_*`, `margem_ebitda`,
  `ebitda_por_t`); 2T26 → as mesmas, para `var_tt`.
- `indisponivel`: um por lado com status ≠ `ok` (texto com o `obs`).
- `negocios_diferentes`: conjuntos de segmentos diferentes entre A e B, ou alguma linha `por_t` N/C.
- `metodologia`: `anualizacao`/`saldos_medios` diferentes → alerta e linhas de rentabilidade e `dl_ebitda` N/C nos dois lados.
- `config`: slug sem entrada no TOML.

#### `tabela.csv` / `tabela.md`
Uma linha por linha do comparativo: `Indicador | Unidade | Período | <A> | <A> A/A | <A> T/T | <B> | <B> A/A | <B> T/T | Vencedor | Fontes`.
Valores formatados (`texto`). `tabela.md` termina com: critério de EBITDA, "páginas na numeração do PDF" e
"Não constitui recomendação de investimento".

### 4. `src/graficos.py`
```python
def gerar_graficos(comp: dict, pasta: Path) -> list[dict]   # grava pasta/graficos/*.png e devolve as entradas de comp["graficos"]
```
Lê **só** o `comparativo.json` (dict) — nunca os indicadores. matplotlib com backend `Agg`, figura 16:9 (12.8×7.2 in, 150 dpi),
cores de `comp["empresas"][x]["cor"]`, rótulos em pt-BR (números com `contrato.fmt_br`), título com o rótulo A/A ou T/T
quando houver comparação temporal, e rodapé `"Fontes — <A>: ITR p.29, p.71 · <B>: ITR p.14 · páginas na numeração do PDF"`
montado das `fontes` das linhas usadas. Uma unidade por eixo; nunca misturar unidades no mesmo eixo.
Valor ausente: barra não desenhada e anotação `N/D`/`N/C` no lugar, nunca zero.

| id | arquivo | conteúdo |
|---|---|---|
| `receita_ebitda` | `graficos/receita_ebitda.png` | 2 painéis (R$ milhões): receita e EBITDA do critério, 3T26 × 3T25 (A/A), por empresa (`valores` das linhas) |
| `margens` | `graficos/margens.png` | barras agrupadas (%): margem bruta, EBITDA, EBIT, líquida no `tri` |
| `dl_ebitda` | `graficos/dl_ebitda.png` | barras (x): DL/EBITDA calculado; se existir linha `dl_ebitda_reportado`, barra ao lado; senão nota "reportado: N/D" |
| `volume_rpt` | `graficos/volume_rpt.png` | 2 painéis: volume (mil t) e R$/t (`receita_por_t`), cada um com sua unidade |
| `mix_segmentos` | `graficos/mix_segmentos.png` | barras empilhadas 100% por empresa: receita e EBITDA por segmento |

Gráfico sem nenhum dado nas duas empresas → ainda gera a imagem com aviso "dados indisponíveis" (o CASE-06 espera os 5 ids).
Cada entrada: `{"id","arquivo","descricao","fontes":{"a":[...],"b":[...]}}`.

## Testes (pytest)

- `tests/test_contrato.py` (ou novo `tests/test_fmt.py`): tabela de formatos, status, `None`, negativos, `fmt_var`.
- `tests/test_comparativo_schema.py`: fixture do CASE-06 válida; comparativo sem `linhas` inválido; `contrato.py` CLI com código 0/2.
- `tests/test_comparar.py` com `tests/fixtures_comparar/indicadores/empresa_{a,b,c}_3T26_indicadores.json`
  (fictícias, no formato real do CASE-04):
  - A×B e B×A: mesmas chaves, lados trocados, vencedor trocado.
  - `empresa_c` só tem critério `contabil` → `criterio_ebitda == "contabil"` contra A; e uma variante sem critério comum → N/C com motivo.
  - Status ≠ ok nunca vira 0 (valor `null`, texto N/D/N/C).
  - `vencedor` nulo em receita, volume, dívida absoluta e quando EBITDA ≤ 0 em `dl_ebitda`.
  - Período diferente → erro fatal (código 2). Indicadores ausentes → código 1.
  - Slug fora do TOML → cor de reserva + alerta `config`.
  - Efeito pontual no 3T25 → alerta com `chaves` incluindo `margem_ebitda`.
  - Saída completa passa em `contrato.validar(..., "comparativo")`.
- `tests/test_graficos.py` com `tests/fixtures_comparar/comparativo_exemplo.json`: gera 5 PNGs 16:9, entradas com fontes,
  linha N/D não quebra, gráfico sem dados ainda gera arquivo.

## Plano de execução (agentes)

| Fase | Agente | Arquivos (exclusivos) |
|---|---|---|
| 1 | base | `src/contrato.py` (só `fmt_br`, `fmt_var`, `escolher_schema`), `schemas/comparativo.schema.json`, `config/empresas.toml`, `tests/fixtures_comparar/**`, `tests/test_fmt.py`, `tests/test_comparativo_schema.py` |
| 2 | comparar | `src/comparar.py`, `tests/test_comparar.py` |
| 2 | graficos | `src/graficos.py`, `tests/test_graficos.py` |
| 3 | João (sessão principal) | integração com dados reais, revisão, `docs/registro/joao-vitor.md`, PR |

Fase 2 roda em paralelo; ninguém edita arquivo de outra linha da tabela.

## Fora de escopo
- Corrigir o CASE-04 (ex.: unidade `1.000 toneladas` ignorada; capacidade da Gerdau em t rotulada como mil t) — registrar e avisar o dono.
- Narrativa e slides (CASE-06); pipeline e `verificacao` (CASE-07).
