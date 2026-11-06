# Fixtures fictícias do CASE-01

**Tudo aqui é fictício.** `empresa_a`, `empresa_b` e `empresa_c` não existem; números, páginas e
trechos foram inventados (os trechos terminam em `(FICTÍCIO)`). Nada daqui pode ir para a apresentação.

Gerado por `python tests/fixtures_ficticias/gerar.py` (não editar à mão; `--check` confere, e o
`tests/test_contrato_api.py` roda o `--check`). Fica fora de `tests/fixtures/` porque aquela pasta guarda só
páginas reais dos ITRs, com limite de 50 KB.

- `metricas/empresa_{a,b}_3T26_*.json`: fatos no contrato (`docs/TAREFAS.md`), um arquivo por documento-fonte,
  com todas as chaves de `contrato.CATALOGO_FATOS` (a A não tem `ajuste_ebitda`), fluxos em 3T26/3T25/2T26/9M26/9M25
  e saldos em 3T26/4T25. ITR em R$ mil, release em R$ milhões (o código precisa converter).
  - A: segmentos `brasil`/`exterior`.
  - B: segmentos `siderurgia`/`mineracao`; impairment fictício no 3T25 (gera alerta `efeito_pontual` no CASE-04).
- `metricas/empresa_c_3T26_itr_dfs.json`: empresa **incompleta** (só DRE e balanço), para testar generalização
  sem nomes fixos e ausência que nunca vira zero.
- `comparativo/empresa_a_x_empresa_b_3T26/`: `comparativo.json` A × B (base: `tests/fixtures_comparar/comparativo_exemplo.json`)
  com 2 PNGs placeholder cinza em `graficos/`, para o CASE-06 desenvolver sem depender do CASE-05.

Uso: `python src/indicadores.py --empresa empresa_a --tri 3T26 --metricas tests/fixtures_ficticias/metricas --saida /tmp/x.json`
