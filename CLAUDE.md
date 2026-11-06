# CLAUDE.md — Case 3 · Gerdau × Usiminas no 3T26

Contexto para o Claude Code. Projeto de workshop (Claude Lab PUC-Rio, 06/11/2026): apresentação executiva de 6 a 8 slides comparando os resultados do 3T26 da Gerdau e da Usiminas para um comitê de investimentos.

Leia primeiro: `docs/CASE3.md` (demanda e cuidados) e `docs/GUIA_TECNICO.md` (o fluxo).

## Fluxo
Ambiente: `pip install -r requirements.txt` (ou `.venv/bin/python`); testes com `python -m pytest`.
1. `python src/extrair_release.py data/itrs/*.pdf` → gera `saida/<pdf>/pagina_NN.txt`
2. Fatos em `metricas/<slug>_<tri>_{itr,apresentacao}_<tipo>.json` (um arquivo = um documento-fonte; contrato em `docs/TAREFAS.md`), **a partir de `saida/<pdf>/pagina_NN.txt`**
   - Validar a forma antes de conferir: `python src/contrato.py metricas/<arquivo>.json`
   - Em código: `contrato.validar_fato`, `carregar_fatos`, `para_milhoes`, `periodo_comparavel`, `pasta_saida`, `fmt_br`, `CATALOGO_FATOS`
3. `python src/verificar_numeros.py saida/<pdf> metricas/<arquivo>.json`; corrigir só os itens com ERRO, olhando a página indicada
   - Resultado por fato: OK, REVISAR (falta evidência; `--estrito` reprova) ou ERRO.
4. `python src/indicadores.py --empresa <slug> --tri 3T26` → `metricas/<slug>_<tri>_indicadores.json` (CASE-04)
5. `python src/comparar.py --a <slug> --b <slug> --tri 3T26` → `saida/comparativo/<a>_x_<b>_<tri>/` (CASE-05)
6. Slides (python-pptx ou HTML) seguindo `templates/roteiro_apresentacao.md` (CASE-06)

Cadastro das empresas (nome, ticker, cor; sem números): `config/empresas.toml`. Fixtures fictícias
(`empresa_a/b/c`, nunca na apresentação): `tests/fixtures_ficticias/` e `tests/fixtures_comparar/`.

## Regras inegociáveis
- **Nunca escreva um número de memória.** Todo número vem de um JSON verificado ou é calculado em código a partir dele.
- `pagina` e `trecho` são **obrigatórios** em todo número. `pagina` = índice da página no PDF contado a partir de 1 (o mesmo número de `pagina_NN.txt`), não o número impresso na folha nem o "PÁGINA: X de N" do formulário.
- `trecho` e `valor_como_aparece` precisam ser cópias literais do texto em `pagina_NN.txt`.
- Usar números **consolidados**, nunca os da controladora/holding (o comentário de desempenho da Gerdau é da holding).
- Mesmo critério de EBITDA (contábil ou ajustado) para as duas empresas, e dizer qual.
- Demonstrações em **R$ mil**; o release da Usiminas mistura R$ mil e R$ milhões. Converter tudo para a mesma unidade antes de comparar.
- Rotular sempre A/A (3T26 × 3T25) ou T/T (3T26 × 2T26).
- Procurar efeitos pontuais no 3T25 e no 2T26 que distorçam as variações.
- Gerdau tem América do Norte; Usiminas tem mineração. Olhar os segmentos antes de concluir.
- Toda apresentação leva a página do ITR de cada número (índice do PDF, o mesmo `pagina` do JSON) e o aviso "Não constitui recomendação de investimento".
- Registrar em `docs/ERROS_ENCONTRADOS.md` cada erro que o verificador ou o time pegou (vai para o vídeo e o README).

## Contrato e catálogo
- Contrato do time: `docs/TAREFAS.md`, seção "Contrato de dados". Schemas em `schemas/` (`fato` para os fatos do time, `indicadores`, `comparativo`, `metricas`, `balanco`, `balanco_meta`); detalhes em `docs/CONTRATO_DADOS.md`.
- Validar a forma de um JSON: `python src/contrato.py metricas/<arquivo>.json` (código 2 = fora do contrato). O verificador (CASE-02) não chama o contrato.
- Catálogo: `docs/CATALOGO_DADOS.md` e `metricas/catalogo.json` são gerados (`python src/gerar_catalogo.py`; não editar à mão). Cadastro manual em `catalogo/fontes.toml`.

## Mapa de páginas (índice do PDF = número do pagina_NN.txt)
Os números impressos na folha são outros (a DRE da Gerdau está impressa como 24 e "PÁGINA: 16 de 65"); não usar.
- DRE consolidada: Gerdau pág. 29–30; Usiminas pág. 14
- Release completo da Usiminas: pág. 21–47
- Segmentos e EBITDA ajustado da Gerdau: notas, pág. 71–74
