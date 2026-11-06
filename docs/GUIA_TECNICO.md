# Caminho avançado — Case 3 · Comparativo de resultados

Leia antes o [README do case](CASE3.md) (demanda, resultado esperado e cuidados com os dados).

## A ideia: extrair → verificar → comparar → apresentar

O erro clássico de IA em finanças é o número errado escrito com confiança. Por isso o trabalho é separado em **etapas encadeadas**, com uma checagem automática no meio:

```
PDFs dos ITRs ──────► 1. extrair texto e tabelas ──► 2. Claude extrai métricas para JSON
                                                              │
4. comparar as empresas ◄── 3. verificador confere cada número no PDF
         │                      (se falhar, volta para o passo 2)
         ▼
5. Claude gera a apresentação (só com números verificados)
```

## Ponto de partida

```bash
# 1. extrair os ITRs
python src/extrair_release.py data/itrs/gerdau_ITR_3T26.pdf data/itrs/usiminas_ITR_3T26.pdf

# 2. peça ao Claude um metricas.json por empresa, no formato de metricas_exemplo.json,
#    validando em schemas/metricas.schema.json (com base_comparacao, visao e criterio_ebitda;
#    inclusive 'valor_como_aparece', 'pagina' e 'trecho' de cada número)
python src/contrato.py metricas/metricas_EMPRESA.json

# 3. verificar cada empresa
#    cada fato sai como OK, REVISAR (falta evidência) ou ERRO (não bate com a página)
#    código 0: nenhum ERRO; código 1: algum ERRO (com --estrito, também REVISAR): corrigir os [ERRO]
#    o verificador não valida o contrato: a forma do JSON é checada antes, com contrato.py (passo 2)
python src/verificar_numeros.py saida/EMPRESA_ITR_3T26 metricas/metricas_EMPRESA.json
```

> O ITR tem de 80 a 110 páginas. Antes de pedir a extração, achem as páginas certas (demonstração do resultado consolidada, release ou comentário de desempenho, notas por segmento; o mapa está no README do case) e passem só elas ao Claude.

Arquivos de apoio:
- [`extrair_release.py`](../src/extrair_release.py): texto por página e tabelas em CSV.
- [`metricas_exemplo.json`](../templates/metricas_exemplo.json): o formato que o Claude deve preencher.
- [`verificar_numeros.py`](../src/verificar_numeros.py): confere trecho, valor, variação, período, unidade e escopo de cada fato contra o PDF e classifica em OK, REVISAR ou ERRO (`--estrito` e `--relatorio` disponíveis). Não valida o contrato; isso é do `contrato.py`.
- [`schemas/`](../schemas/): os schemas do JSON (`metricas`, `balanco`, `balanco_meta`, `fato`).
- [`contrato.py`](../src/contrato.py): valida a forma de um JSON contra o schema (escolhido sozinho ou com `--schema`), inclusive `.meta.json`.
- [`catalogo/fontes.toml`](../catalogo/fontes.toml) e [`docs/CATALOGO_DADOS.md`](CATALOGO_DADOS.md): catálogo das fontes e dos artefatos, gerado por `src/gerar_catalogo.py`.
- [`CONTRATO_DADOS.md`](CONTRATO_DADOS.md): o contrato, um resumo do verificador, o catálogo e as fixtures de teste.
- [`roteiro_apresentacao.md`](../templates/roteiro_apresentacao.md): roteiro dos slides da apresentação executiva.

## Trilha sugerida

**Manhã — nível 1: uma empresa verificada**
- O fluxo completo para uma empresa: extrair, pedir o JSON ao Claude, verificar e corrigir.
- Anotem **cada erro** que o verificador pegou.

**Manhã — nível 2: as duas empresas**
- Rodem o fluxo para a segunda empresa e juntem tudo numa tabela comparativa, na mesma unidade e com o mesmo critério.
- Gerem os gráficos da comparação (receita, margens).

**Tarde (depois da palestra das 13h30) — nível 3: a apresentação**
- Escrevam a mensagem de cada slide seguindo o [`roteiro_apresentacao.md`](../templates/roteiro_apresentacao.md).
- Gerem a apresentação a partir da tabela verificada: `.pptx` com `python-pptx` (ou direto no claude.ai) ou slides em HTML.
- Bônus: um comando só que recebe os PDFs e devolve a apresentação, **refazendo automaticamente o que o verificador reprovar**.
- Bônus: transformem o formato da apresentação numa **Skill** (`SKILL.md`, veja o [exemplo](../referencia/SKILL_exemplo_bcb-sgs.md)), para que o Claude sempre monte os slides no padrão da "casa".

## Onde o Claude Code ajuda

- "Leia saida/EMPRESA/texto_completo.txt e gere metricas_EMPRESA.json no formato de metricas_exemplo.json com as métricas que definimos."
- "Valide o JSON com `python src/contrato.py` antes de rodar o verificador."
- "Rode o verificador e corrija no JSON só os itens com ERRO, olhando a página indicada."
- "Junte os JSONs verificados numa tabela comparativa em R$ milhões e faça um gráfico de margem EBITDA por empresa."
- "Gere apresentacao.pptx com python-pptx seguindo roteiro_apresentacao.md, usando só os números verificados."
