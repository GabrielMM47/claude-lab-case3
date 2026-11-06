# Comparativo de resultados — Gerdau × Usiminas, 3T26

> Claude Lab · Economia & Finanças · PUC-Rio · 06/11/2026

**Vídeo:** pendente de gravação e publicação  
**Artefato público:** pendente da apresentação final

## Equipe

| Pessoa | Responsabilidade |
|---|---|
| Gabriel Patrício | contrato, fixtures e apresentação executiva |
| Gabriel Martins | DFs CVM, EBITDA e pipeline |
| Geronimo | apresentações institucionais, dados operacionais, qualitativos e entrega |
| João Vitor | indicadores, comparativo e gráficos |

## O problema

Comparar duas siderúrgicas a partir de ITRs e releases exige combinar demonstrações padronizadas, métricas operacionais e informação qualitativa. O risco é colocar no mesmo slide números de períodos, unidades, escopos ou critérios de EBITDA diferentes sem perceber.

## A solução

O projeto organiza os PDFs em texto pesquisável, extrai fatos para JSON, confere cada número contra sua página e calcula indicadores a partir dos fatos verificados. A apresentação final deverá consumir apenas comparativos e narrativas rastreáveis.

## Como funciona

```text
PDFs de RI/CVM
      ↓
extração de páginas e tabelas
      ↓
localização de páginas por tema
      ↓
Claude extrai JSON com página, unidade, escopo e trecho
      ↓
verificador confere cada número no PDF
      ↓
indicadores e comparativo
      ↓
slides com fontes e limitações
```

Os prompts assistidos estão em [`prompts/`](prompts/) e a skill reutilizável está em [`.claude/skills/apresentacao-resultados/SKILL.md`](.claude/skills/apresentacao-resultados/SKILL.md).

## Dados usados

Foram usados os ITRs 3T26 da Gerdau e da Usiminas, além das apresentações institucionais registradas em [`data/apresentacoes/FONTES.md`](data/apresentacoes/FONTES.md). Os dados cobrem demonstrações financeiras, segmentos, volumes, capacidade, indicadores por tonelada e temas qualitativos.

Cuidados aplicados: consolidado versus segmento, holding versus controlada, EBITDA contábil versus ajustado, 3T26 versus 3T25, unidades e efeitos pontuais.

## Como verificamos

O processo tem duas camadas:

1. o contrato valida campos, tipos, unidades e escopos;
2. `src/verificar_numeros.py` procura o trecho e o token literal na página correta, conferindo período, unidade, escopo e coluna quando disponíveis.

Erros reais encontrados estão consolidados em [`docs/ERROS_ENCONTRADOS.md`](docs/ERROS_ENCONTRADOS.md). Exemplos:

- o `156` de “Instrução CVM 156” foi confundido com um valor de EBITDA na p. 28 da Usiminas;
- a dívida bruta da Usiminas na p. 32 diferia da soma das contas das DFs porque incluía tributos parcelados;
- os dígitos dos gráficos da Gerdau nas p. 18–20 foram fragmentados pelo extrator;
- a p. 40 da apresentação da Usiminas saiu sem texto e foi excluída das evidências.

## Como reproduzir

Instale as dependências:

```bash
pip install -r requirements.txt
```

Extraia os PDFs e localize páginas candidatas:

```bash
python src/extrair_release.py data/itrs/gerdau_ITR_3T26.pdf data/itrs/usiminas_ITR_3T26.pdf
python src/extrair_release.py data/apresentacoes/gerdau_APRESENTACAO_3T26.pdf data/apresentacoes/usiminas_APRESENTACAO_3T26.pdf
python src/localizar_paginas.py saida/gerdau_APRESENTACAO_3T26 --tema operacional --top 10
```

Depois da conclusão dos CASEs 05–07, o comando-alvo será:

```bash
python src/pipeline.py --a gerdau --b usiminas --tri 3T26
```

No estado atual, o pipeline integrado e a apresentação final ainda não existem. Para testes locais:

```bash
pytest -q
```

## Limitações e próximos passos

- A apresentação da Gerdau não traz volume consolidado textual verificável.
- A Usiminas não apresenta receita/EBITDA segmentados de 3T25 na tabela operacional utilizada.
- Alguns gráficos têm texto extraído com dígitos fragmentados.
- CASE-05, CASE-06 e CASE-07 ainda precisam gerar comparativo, apresentação e pipeline integrados.
- Ainda faltam publicação pública, vídeo e teste em aba anônima.

## Entrega

O vídeo, o artefato público e o formulário serão adicionados quando a apresentação final estiver publicada. O checklist está em [`docs/CHECKLIST_ENTREGA.md`](docs/CHECKLIST_ENTREGA.md).

## Aviso

Projeto acadêmico desenvolvido em workshop. Não constitui recomendação de investimento.
