# Catálogo de dados — Case 3 (Gerdau × Usiminas, 3T26)

> Gerado por `python src/gerar_catalogo.py`. Não edite à mão; `python src/gerar_catalogo.py --check` diz se está em dia.
> Versão estruturada: [`metricas/catalogo.json`](../metricas/catalogo.json). Cadastro manual: [`catalogo/fontes.toml`](../catalogo/fontes.toml).
> **Autovalidação do extrator** (V01–V08, `status` do `.meta.json`) ≠ **verificador** (`verificar_numeros.py`: contrato + conferência contra `saida/<pdf>/`).

## Fontes
| PDF | Empresa | Tipo | Período | Data-base | SHA-256 | Tamanho | Origem |
|---|---|---|---|---|---|---|---|
| data/itrs/gerdau_ITR_3T26.pdf | Gerdau | ITR | 3T26 | 30/09/2026 | 1bb773ec9178 | 4,1 | (a preencher) |
| data/itrs/usiminas_ITR_3T26.pdf | Usiminas | ITR | 3T26 | 30/09/2026 | 4bc2fcd69480 | 9,7 | (a preencher) |

## Artefatos verificáveis
| Artefato | Visão | Unidade (escala original) | Páginas (Ativo; Passivo) | Registros (ambíguos) | Datas | Gerado por | Contrato | Autovalidação do extrator | Verificador | EBITDA | Fonte |
|---|---|---|---|---|---|---|---|---|---|---|---|
| metricas/balanco_gerdau.json | consolidado | R$ mil (Reais Mil) | 26; 27, 28 | 94 (32) | 30/09/2026 × 31/12/2025 | extrair_balanco.py 1.0.0 | válido | aprovado | 0/94 conferem, 94 para revisar | n/a | gerdau_ITR_3T26 |
| metricas/balanco_gerdau_controladora.json | controladora | R$ mil (Reais Mil) | 15; 16, 17 | 88 (39) | 30/09/2026 × 31/12/2025 | extrair_balanco.py 1.0.0 | válido | aprovado | 0/88 conferem, 88 para revisar | n/a | gerdau_ITR_3T26 |
| metricas/balanco_usiminas.json | consolidado | R$ mil (Reais Mil) | 12; 13 | 81 (18) | 30/09/2026 × 31/12/2025 | extrair_balanco.py 1.0.0 | válido | aprovado | 0/81 conferem, 81 para revisar | n/a | usiminas_ITR_3T26 |
| metricas/balanco_usiminas_controladora.json | controladora | R$ mil (Reais Mil) | 3; 4 | 78 (17) | 30/09/2026 × 31/12/2025 | extrair_balanco.py 1.0.0 | válido | aprovado | 0/78 conferem, 78 para revisar | n/a | usiminas_ITR_3T26 |

## Arquivos auxiliares
| Arquivo | Tipo | Derivado de | Contrato |
|---|---|---|---|
| metricas/balanco_gerdau.csv | csv | metricas/balanco_gerdau.json | — |
| metricas/balanco_gerdau.meta.json | meta | metricas/balanco_gerdau.json | válido |
| metricas/balanco_gerdau_controladora.csv | csv | metricas/balanco_gerdau_controladora.json | — |
| metricas/balanco_gerdau_controladora.meta.json | meta | metricas/balanco_gerdau_controladora.json | válido |
| metricas/balanco_usiminas.csv | csv | metricas/balanco_usiminas.json | — |
| metricas/balanco_usiminas.meta.json | meta | metricas/balanco_usiminas.json | válido |
| metricas/balanco_usiminas_controladora.csv | csv | metricas/balanco_usiminas_controladora.json | — |
| metricas/balanco_usiminas_controladora.meta.json | meta | metricas/balanco_usiminas_controladora.json | válido |

## Pendentes
| Artefato esperado | Fonte | Descrição | Status |
|---|---|---|---|
| metricas/metricas_gerdau.json | gerdau_ITR_3T26 | DRE, EBITDA e segmentos (consolidado), no formato de templates/metricas_exemplo.json | pendente |
| metricas/metricas_usiminas.json | usiminas_ITR_3T26 | DRE, EBITDA e segmentos (consolidado), no formato de templates/metricas_exemplo.json | pendente |

## Intermediários não versionados
- `saida/<stem>/`: texto por página (`pagina_NN.txt`) e tabelas, gerados por `src/extrair_release.py`; ficam fora do Git e por isso fora deste catálogo (o gerador mostra a contagem no terminal).
