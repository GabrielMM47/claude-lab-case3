# Comparativo de resultados — Gerdau × Usiminas, 3T26

> Claude Lab · Economia & Finanças · PUC-Rio · 06/11/2026

**Artefato público (apresentação de 8 slides):** https://claude.ai/artifact/JxvcGaxB6T6mTx8CYU2JH4  
**Vídeo (1:52, só texto):** https://youtu.be/GwUmfo0mLNY · arquivo: [`entrega/video_jornada_gerdau_x_usiminas_3T26.mp4`](entrega/video_jornada_gerdau_x_usiminas_3T26.mp4) (fonte em [`video/`](video/), HyperFrames)  
**Arquivo da apresentação no repositório:** [`entrega/apresentacao_gerdau_x_usiminas_3T26.html`](entrega/apresentacao_gerdau_x_usiminas_3T26.html) (abre em qualquer navegador; setas, clique ou toque para navegar)

## Equipe

| Pessoa | Curso | Responsabilidade |
|---|---|---|
| Gabriel Patrício | Engenharia de Computação, 8º período | indicadores (CASE-04) e apresentação executiva com narrativa verificada (CASE-06) |
| Gabriel Martins | Engenharia de Computação, 8º período | DFs CVM, EBITDA e verificador (CASE-02); pipeline de um comando (CASE-07) |
| Geronimo | Economia, 7º período | apresentações institucionais, dados operacionais e qualitativos (CASE-03); entrega (CASE-08) |
| João Vitor | Ciência da Computação, 7º período | contrato de dados, catálogo e fixtures (CASE-01); comparativo e gráficos (CASE-05) |

## O problema

Um comitê de investimentos quer saber, em 6 a 8 slides, qual siderúrgica teve o melhor 3T26 e por quê. Montar isso a partir de ITRs e apresentações de RI exige juntar demonstrações padronizadas, números operacionais e informação qualitativa, e o risco é colocar lado a lado números de períodos, unidades, escopos ou critérios de EBITDA diferentes sem perceber. Um número na coluna errada muda a conclusão do slide.

## A solução

Um fluxo em Python + Claude Code que vai dos PDFs oficiais até a apresentação executiva **com um comando**, em que todo número na tela tem a página do PDF de onde veio e passou por um verificador automático. O que exige leitura (EBITDA ajustado, dados operacionais, temas qualitativos) é extraído pelo Claude com prompts versionados; o que é determinístico (DFs, conferência, indicadores, comparativo, slides) roda sozinho.

### O que a apresentação conclui (3T26)

- **Gerdau foi mais rentável:** margem EBITDA ajustada de 20,2% contra 9,0% da Usiminas, com ROIC 9M26 anualizado de 10,3% contra 7,5%.
- **Gerdau cresceu, Usiminas encolheu:** receita +3,9% A/A e EBITDA ajustado +37,8% A/A na Gerdau; na Usiminas, receita -6,1% A/A e EBITDA ajustado -26,7% T/T.
- **Usiminas tem o balanço mais leve:** caixa líquido (dívida líquida/EBITDA de -0,22x) contra 0,57x da Gerdau.
- **Cuidado com o lucro da Usiminas:** R$ 243,4 mi no 3T26, positivo sobre um 3T25 com impairment de R$ 2,23 bi (ITR p. 28). A melhora A/A não é tendência, e a apresentação não a usa como destaque.
- **Por negócio, o Brasil quase empata:** EBITDA ajustado por tonelada de R$ 549/t na Gerdau Brasil contra R$ 520/t na siderurgia da Usiminas. A Gerdau se distancia na América do Norte (R$ 2.217/t, +57,5% A/A), que gera 76% do seu EBITDA. A comparação é por segmento (numerador e denominador do mesmo negócio), porque a Gerdau não divulga volume consolidado e o consolidado da Usiminas inclui mineração.
- **O macro explica a distância:** nos EUA, a Seção 232 taxa o aço importado em 50% (apresentação da Gerdau, p. 9); no Brasil, as importações subiram 19,8% sobre o 2T26, com planos +33,8% (p. 18), e as projeções de demanda para 2026 vão de -4,0% (automotivo) a +0,4% (indústria) (p. 14).
- **Cenários (leitura do time):** o quadro atual, uma pressão dupla (importação indireta + minério fraco) e um real mais fraco favorecem a Gerdau. A Usiminas ganha mais numa virada do Brasil (antidumping de bobinas a quente confirmado, juros em queda, montadoras reagindo) e encosta se a Seção 232 for afrouxada na revisão do USMCA.

Fontes de cada número no rodapé de cada slide (Gerdau: ITR p. 29 e 72; Usiminas: ITR p. 14 e 28, entre outras). Páginas sempre na numeração do PDF.

## Como funciona

```text
data/itrs/*.pdf + data/apresentacoes/*.pdf
      │  python src/pipeline.py --a gerdau --b usiminas --tri 3T26
      ▼
1. insumos           confere os 4 PDFs
2. extração          saida/<pdf>/pagina_NN.txt (pdfplumber; carimbo sha256 do PDF)
3. DFs CVM           parser determinístico das DFs consolidadas → metricas/*_itr_dfs.json
4. extração assistida  falta complementar/operacional/qualitativo? imprime o prompt pronto
                     (prompts/) com as páginas candidatas e para — o Claude Code extrai
5. verificação       contrato (schemas/) + verificador literal de cada fato → ERRO bloqueia
6. indicadores       margens, ROE, ROIC, DL/EBITDA, R$/t… só com fatos aprovados
7. comparativo       tabela, vencedor só com regra econômica clara, alertas, 5 gráficos
8. apresentação      8 slides HTML; títulos da narrativa/ resolvidos por código;
                     contexto macro (metricas/*_macro.json) e cenários no slide 7
      ▼
entrega/apresentacao_gerdau_x_usiminas_3T26.html
```

A narrativa ([`narrativa/gerdau_x_usiminas_3T26.json`](narrativa/gerdau_x_usiminas_3T26.json)) traz os títulos-mensagem escritos com o Claude Code, mas **sem nenhum número digitado**: os números entram por marcadores (`{a.margem_ebitda}`, `{b.receita_liquida.var_aa}`) que o código troca pelo valor verificado. Uma narrativa com número escrito à mão, empresa ou período trocado é reprovada e a apresentação não é gerada.

## Dados usados

| Documento | Gerdau | Usiminas |
|---|---|---|
| ITR 3T26 (CVM) | [`data/itrs/gerdau_ITR_3T26.pdf`](data/itrs/gerdau_ITR_3T26.pdf) | [`data/itrs/usiminas_ITR_3T26.pdf`](data/itrs/usiminas_ITR_3T26.pdf) |
| Apresentação institucional | [`data/apresentacoes/gerdau_APRESENTACAO_3T26.pdf`](data/apresentacoes/gerdau_APRESENTACAO_3T26.pdf) | [`data/apresentacoes/usiminas_APRESENTACAO_3T26.pdf`](data/apresentacoes/usiminas_APRESENTACAO_3T26.pdf) |

Origem, URLs de RI e data de acesso: [`data/apresentacoes/FONTES.md`](data/apresentacoes/FONTES.md). Catálogo de cada arquivo de dados: [`docs/CATALOGO_DADOS.md`](docs/CATALOGO_DADOS.md).

Cuidados do case tratados em código: consolidado (nunca a controladora/holding), mesmo critério de EBITDA para as duas (ajustado), unidades convertidas antes de comparar (R$ mil × R$ milhões), rótulo A/A × T/T em toda variação, alerta de efeito pontual (impairment da Usiminas no 3T25), segmentos diferentes (Gerdau com América do Norte; Usiminas com mineração).

## Como verificamos

Três camadas, todas automáticas e rodadas pelo pipeline:

1. **Contrato:** cada fato tem empresa, período, unidade, escopo, `pagina` (índice do PDF) e `trecho` literal; o schema recusa o resto.
2. **Verificador literal** ([`src/verificar_numeros.py`](src/verificar_numeros.py)): o trecho tem de existir na página citada e o número tem de aparecer como token inteiro **na coluna do período certo**, conferindo unidade e escopo. Quando a automação não prova a coluna, o fato fica "para revisar" e só passa com revisão manual registrada (pessoa e nota).
3. **Reconciliações em código:** EBITDA ajustado = EBITDA CVM 156 + ajustes (ex.: Usiminas 3T26: 588.039 − 80.452 + 50.430 = 558.017, ITR p. 28); identidades contábeis das DFs; dívida líquida calculada × reportada.

**Resultado da rodada final: 233 de 272 números conferidos no PDF, 0 com erro.** Os 39 restantes são fatos operacionais sem evidência literal de período/unidade/escopo: não bloqueiam, mas estão listados no relatório `saida/verificacao_gerdau_x_usiminas_3T26.json` que o pipeline gera.

Erros reais que o processo pegou (lista completa em [`docs/ERROS_ENCONTRADOS.md`](docs/ERROS_ENCONTRADOS.md)):

- **"Instrução CVM 156" virou EBITDA** (Usiminas, ITR p. 28): o 156 do nome da instrução foi lido como o EBITDA do 3T26 e cada valor escorregou uma coluna. O verificador original **aprovou**, porque os números existiam na linha; quem pegou foi a reconciliação recalculada. Correção: o verificador passou a exigir o cabeçalho das colunas.
- **Número de outro trimestre** (Usiminas, apresentação p. 28): receita de mineração do 3T25 extraída como US$ 87/t; o 3T25 era US$ 79 (os 87 eram do 4T25 e do 1T26). O verificador acusou "valor fora do trecho".
- **Destaque distorcido por impairment** (Usiminas, ITR p. 28): o slide de destaques mostrava "+57 p.p. de margem líquida" como ponto positivo, efeito do impairment do 3T25. O gerador passou a ignorar variações A/A de linhas contábeis quando há efeito pontual.
- **Dígitos "em negrito falso"** (Gerdau, apresentação p. 18–20): o texto extraído triplica cada caractere (`111...555888222` = 1.582); o verificador passou a reconhecer essa forma em vez de aceitar números transcritos sem prova.

## Como reproduzir

```bash
git clone https://github.com/GabrielMM47/claude-lab-case3 && cd claude-lab-case3
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/pipeline.py --a gerdau --b usiminas --tri 3T26
```

Saída: `entrega/apresentacao_gerdau_x_usiminas_3T26.html` (e o relatório de verificação em `saida/`). Leva cerca de 1 minuto na primeira vez (extração dos PDFs) e é idempotente. No Windows, rode antes `set PYTHONIOENCODING=utf-8` (PowerShell: `$env:PYTHONIOENCODING="utf-8"`).

- **Outras empresas:** coloque `data/itrs/<slug>_ITR_<tri>.pdf` e `data/apresentacoes/<slug>_APRESENTACAO_<tri>.pdf`, cadastre nome/ticker/cor em `config/empresas.toml` e rode o mesmo comando. Ele para na etapa assistida e imprime o prompt pronto para colar no Claude Code; depois de gravar o JSON, rode de novo.
- **Rascunho com pendências:** `--permitir-pendencias` gera uma versão marcada "RASCUNHO — NÃO ENTREGAR", sem os fatos reprovados e sem tocar os arquivos oficiais.
- **Testes:** `python -m pytest`.

Skill para o Claude Code repetir o fluxo: [`.claude/skills/apresentacao-resultados/SKILL.md`](.claude/skills/apresentacao-resultados/SKILL.md). Prompts principais: [`prompts/`](prompts/) e [`docs/PROMPTS.md`](docs/PROMPTS.md).

## Limitações e próximos passos

- **Sem volume consolidado da Gerdau:** a comparação por tonelada é feita por segmento (slide 6). A receita da divisão Brasil da Gerdau inclui minério e coprodutos (apresentação p. 26).
- **Contexto macro só do que as empresas publicam:** tarifas, importações e projeções de demanda vêm das apresentações e do ITR, com página e verificador. Não há dado externo (Selic, preço do minério em US$, exportações da China): para usá-los, é preciso uma fonte em PDF no mesmo fluxo. Os cenários do slide 7 são julgamento do time, não projeção.
- **Sem 2T26 da Gerdau no ITR:** variações T/T só existem para a Usiminas.
- **Dívida líquida/EBITDA** usa o EBITDA 9M26 anualizado (× 4/3); as empresas divulgam com o EBITDA dos últimos 12 meses. A dívida líquida calculada da Usiminas difere 17% da reportada (a reportada inclui tributos parcelados, ITR p. 32).
- **ROIC** usa uma hipótese de alíquota efetiva (limitada a 34%), indicada no slide.
- **39 fatos "para revisar"** ainda sem evidência literal completa (dois deles de contexto macro: importação de longos nos EUA e tarifa acima da cota no Brasil); próximo passo: completar a `evidencia` desses fatos.
- **Extração assistida:** complementar, operacional e qualitativo exigem o Claude Code com os prompts prontos; o pipeline não chama o modelo sozinho.
- Testado com Gerdau, Usiminas e empresas fictícias (A/B invertidos, arquivo ausente, fato reprovado). Duas empresas reais não provam cobertura de qualquer layout de ITR.

## Entrega

Checklist em [`docs/CHECKLIST_ENTREGA.md`](docs/CHECKLIST_ENTREGA.md); roteiro do vídeo em [`docs/ROTEIRO_VIDEO.md`](docs/ROTEIRO_VIDEO.md).

## Aviso

Projeto acadêmico desenvolvido em workshop. **Não constitui recomendação de investimento.** Dados públicos das empresas (ITRs na CVM e apresentações de RI); ver [`docs/USO-DOS-DADOS.md`](docs/USO-DOS-DADOS.md).
