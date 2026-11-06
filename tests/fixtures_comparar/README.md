# Fixtures do CASE-05 (comparativo)

**Tudo aqui é fictício.** `empresa_a`, `empresa_b` e `empresa_c` não existem; números e
páginas foram inventados. Nenhum valor destas fixtures pode ir para a apresentação.

- `indicadores/empresa_{a,b,c}_3T26_indicadores.json`: mesma estrutura da saída real do
  CASE-04 (`src/indicadores.py`), com números inventados.
  - A: critérios contábil e ajustado, tudo `ok` (exceto `utilizacao_capacidade`), segmentos
    `brasil`/`exterior`, alerta `efeito_pontual` no 3T25 e um alerta `unidade`.
  - B: critérios contábil e ajustado, segmentos `siderurgia`/`mineracao`, `receita_por_t`,
    `custo_por_t` e `ebitda_por_t_*` `nao_comparavel`, `roic` `ausente`, EBITDA do 3T26 negativo,
    alertas `divergencia`, `efeito_pontual` (2T26) e `divergencia_definicao`.
  - C: só critério contábil, anualização diferente de A e B, segmentos `laminados`/`distribuicao`;
    fica fora de `config/empresas.toml` para testar o fallback.
- `comparativo_exemplo.json`: comparativo A × B completo (critério ajustado), usado nos testes de gráficos.
- `comparativo_case06.json`: cópia da fixture do CASE-06; o schema `comparativo` precisa aceitá-la.
