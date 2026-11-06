# Registro — Gabriel Martins (CASE-02 e CASE-07)

## Erros encontrados

| # | Empresa | Métrica | O que o Claude/código disse | O que estava no ITR (pág.) | Como pegamos | Correção |
|---|---|---|---|---|---|---|
| 1 | (teste) | Lucro bruto | identidade lucro_bruto = receita + cpv quebrada de propósito | DRE consolidada | `checar_consistencia` no `dfs_cvm.py` | o parser recusa gravar o JSON (exit 1) |
| 2 | — | Verificador original | um número que existe na página "conferia" mesmo estando na coluna de outro período (ex.: 3T25 no lugar do 3T26) ou na página das DFs Individuais | — | teste `test_numero_existe_na_pagina_mas_na_coluna_errada` | verificador passou a checar coluna, período, unidade e escopo |

## Observações dos dados

- Gerdau e Usiminas usam códigos diferentes para D&A (`6.01.01.02` × `6.01.01.04`) e capex (`6.02.01 Adições de imobilizado` × `6.02.02 Compras de Imobilizado`): achados pela descrição, sem `if empresa`.
- A DFC do ITR só traz o acumulado (9M26, 9M25): FCO, capex e D&A **trimestrais** ficam `nao_comparavel` na cobertura.
- Usiminas 3T25: `3.04.05 Outras Despesas Operacionais` de -2.346.416 (p. 14), contra -113.945 no 3T26: é o impairment de R$ 2,23 bi do 3T25 (release, p. 44). Lucro líquido A/A da Usiminas não é comparável sem esse ajuste.
- Na DRE da Gerdau (p. 29–30) o texto extraído é limpo; nas notas de segmento (p. 71–74) as letras saem espaçadas ("R eceita líquida").

## Prompts que funcionaram

(preencher)
