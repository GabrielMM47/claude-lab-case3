# CASE-01 e CASE-05 — Registro de João Vitor

## Erros encontrados

<!-- empresa · métrica · o que o Claude disse · o que estava no ITR · como pegou · correção -->

- **Contrato · indicadores.json.** `contrato.escolher_schema` mandava o `*_indicadores.json` (um objeto) para o
  schema `metricas` (lista), e a CLI respondia "esperado lista, veio objeto". Pego ao validar a fixture do CASE-05.
  Correção: schema novo `schemas/indicadores.schema.json` e `escolher_schema` reconhece dict com `indicadores`.
- **Catálogo · test_c_t3.** O teste contava só `*_itr_*.json` como fato (12 + 6), mas o catálogo inclui os
  `*_apresentacao_*.json` do CASE-03 (22 artefatos). Correção: contagem derivada de itr + apresentacao + indicadores.
- **CASE-03 · fatos fora do contrato** (aviso ao Geronimo; arquivos dele, não alterados), pegos por
  `validar_fato`/`test_c_t3b`: `gerdau_3T26_apresentacao_operacional.json` (período `"3T26 vs 2T26"`, unidades
  `"1.000 toneladas"` e `"MT"`, 17 `valor_como_aparece` nulos); `usiminas_3T26_apresentacao_operacional.json` e
  `usiminas_3T26_itr_operacional.json` (escopo `segmento:mineração` com acento; unidades `"mil toneladas"`,
  `"milhões de toneladas/ano"`, `"Mil toneladas"`, `"kton"`, `"R$ milhão"`). Decisão pendente do time: o contrato
  diz "unidade como aparece", mas o schema só aceita a lista fechada.

## Prompts que funcionaram


## CASE-05 — achados na execução real (gerdau × usiminas, 3T26)

Comparativo gerado com `python src/comparar.py --a gerdau --b usiminas --tri 3T26` (e invertido) sobre os
indicadores do CASE-04. Achados nos dados de entrada (arquivos de outros donos; avisar, não alterar):

- **Usiminas · segmentos vazios.** Receita/EBITDA por segmento vêm em `"R$ milhão"` (singular) e a mineração em
  `"kton"`: o CASE-04 descarta como unidade não suportada e o comparativo sai com `segmentos.b = []` (gráfico de mix
  com N/D). Pego pelo alerta `unidade` repassado ao comparativo. Dono: CASE-03/CASE-04.
- **Gerdau · volume N/D.** Volumes por segmento em `"1.000 toneladas"` são ignorados; sem volume consolidado,
  volume, R$/t e EBITDA/t da Gerdau saem N/D. Dono: CASE-03/CASE-04.
- **Usiminas · volume consolidado.** Alertas de divergência põem lado a lado aço e minério (ITR p.24) e, no segmento
  siderurgia, o total contra mercado interno/exportação (ITR p.36): mistura de linhas, não divergência real.
- **Gerdau · capacidade instalada.** Valores em t rotulados como "mil t" (ordem de grandeza 1.000× maior). Não entra
  no comparativo, mas está no indicadores.json.
- **Usiminas · variações A/A de margem EBIT e líquida muito altas.** O 3T25 traz ajustes não recorrentes de 544% do
  EBITDA ajustado (impairment); o comparativo marca `efeito_pontual` com as chaves afetadas. Não usar essas variações
  como título de slide.
- **Gerdau · sem 2T26.** Todas as variações T/T da Gerdau saem `null` (sem dado, nunca estimado).
- **Segmentos com slug cru nos gráficos** (`america_do_norte`). Correção: tabela `[segmentos]` em
  `config/empresas.toml` + rótulo genérico de reserva (`rotulo_segmento`).

### Prompts que funcionaram (CASE-05)
- Spec primeiro (`docs/superpowers/specs/2026-11-06-case05-comparativo-design.md`) com as interfaces fechadas;
  depois um agente por arquivo (base → `comparar.py` ‖ `graficos.py`), cada um proibido de editar arquivos dos outros.
