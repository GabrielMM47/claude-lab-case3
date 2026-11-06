# [Nome do projeto] — Case 3 · Comparativo de resultados (Gerdau × Usiminas, 3T26)

> Claude Lab · Economia & Finanças · PUC-Rio · 06/11/2026
> **Deadline: 16h00.** Este README é a porta de entrada da entrega: a banca lê isto primeiro. As seções abaixo seguem o modelo oficial; vão preenchendo ao longo do dia.

**🎬 Vídeo (2 min):** [link]
**🔗 Artefato público:** [link]

---

## 🧭 Para o time (apagar esta seção antes da entrega)

**Comecem por:** [docs/GUIA_CASE3.md](docs/GUIA_CASE3.md), um resumo de tudo (demanda, cuidados, entregas, critérios).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/extrair_release.py data/itrs/gerdau_ITR_3T26.pdf data/itrs/usiminas_ITR_3T26.pdf
# Claude gera metricas/metricas_gerdau.json e metricas/metricas_usiminas.json
python src/verificar_numeros.py saida/gerdau_ITR_3T26 metricas/metricas_gerdau.json
python src/verificar_numeros.py saida/usiminas_ITR_3T26 metricas/metricas_usiminas.json
```

| Pasta / arquivo | O que tem |
|---|---|
| [data/itrs/](data/itrs/) | ITRs 3T26 da Gerdau (80 p.) e da Usiminas (110 p.) |
| [src/](src/) | `extrair_release.py` (PDF → texto/tabelas) e `verificar_numeros.py` (confere cada número no PDF) |
| [templates/](templates/) | formato do JSON de métricas e roteiro dos slides |
| [metricas/](metricas/) | os JSONs de métricas do time (verificados) |
| [docs/CASE3.md](docs/CASE3.md) | enunciado oficial do case |
| [docs/GUIA_TECNICO.md](docs/GUIA_TECNICO.md) | trilha técnica oficial |
| [docs/REGRAS_E_AVALIACAO.md](docs/REGRAS_E_AVALIACAO.md) · [docs/CHECKLIST_ENTREGA.md](docs/CHECKLIST_ENTREGA.md) · [docs/USO-DOS-DADOS.md](docs/USO-DOS-DADOS.md) | regras, critérios, checklist |
| [docs/ERROS_ENCONTRADOS.md](docs/ERROS_ENCONTRADOS.md) · [docs/PROMPTS.md](docs/PROMPTS.md) | registrem aqui ao longo do dia |
| [CLAUDE.md](CLAUDE.md) | contexto e regras que o Claude Code carrega sozinho |
| `saida/` | gerado pelos scripts (não vai para o Git) |

**Entrega:** [formulário oficial](https://github.com/jplucas29/claude-lab-financas-puc2026/issues/new?template=entrega.yml), uma vez por time, com os 3 links públicos.

---

## Equipe

| Nome | Curso / período | Papel no projeto | LinkedIn / GitHub |
|---|---|---|---|
| | | | |
| | | | |
| | | | |
| | | | |

## O problema

Em 2 a 3 frases: qual problema vocês atacaram, para quem, e por que ele importa.

## A solução

O que vocês construíram e como se usa. Prints ajudam.

## Como funciona

Fluxo: extrair (pdfplumber) → Claude extrai métricas para JSON com página e trecho → verificador confere cada número no PDF → comparação e gráficos → slides gerados só com números verificados.

## Dados usados

ITRs do 3º trimestre de 2026 (até 30/09/2026) da Gerdau S.A. e da Usiminas, em `data/itrs/`. Fonte: as próprias empresas (RI) e a CVM. Como tratamos os cuidados do case: consolidado × holding, contábil × ajustado, efeitos pontuais, A/A × T/T, unidades, segmentos.

## Como verificamos os resultados

Pelo menos 2 ou 3 exemplos concretos: que número o Claude produziu, onde conferimos, se bateu ou não, e o que ajustamos. Ver [docs/ERROS_ENCONTRADOS.md](docs/ERROS_ENCONTRADOS.md).

## Como reproduzir

```bash
pip install -r requirements.txt
python src/extrair_release.py data/itrs/*.pdf
python src/verificar_numeros.py saida/gerdau_ITR_3T26 metricas/metricas_gerdau.json
```

Prompts principais em [docs/PROMPTS.md](docs/PROMPTS.md).

## Limitações e próximos passos

O que ficou de fora, que suposições fizemos, o que faríamos com mais um dia.

## Aviso

Projeto acadêmico desenvolvido em workshop. Não constitui recomendação de investimento. Fonte dos dados: ITRs 3T26 da Gerdau e da Usiminas (CVM / RI das empresas).

**Feito com:** Claude + Claude Code, Python, pdfplumber, pandas, matplotlib, python-pptx. Material de partida: [claude-lab-financas-puc2026](https://github.com/jplucas29/claude-lab-financas-puc2026).
