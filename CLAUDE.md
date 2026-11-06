# CLAUDE.md — Case 3 · Gerdau × Usiminas no 3T26

Contexto para o Claude Code. Projeto de workshop (Claude Lab PUC-Rio, 06/11/2026): apresentação executiva de 6 a 8 slides comparando os resultados do 3T26 da Gerdau e da Usiminas para um comitê de investimentos.

Leia primeiro: `docs/CASE3.md` (demanda e cuidados) e `docs/GUIA_TECNICO.md` (o fluxo).

## Fluxo
1. `python src/extrair_release.py data/itrs/*.pdf` → gera `saida/<pdf>/pagina_NN.txt`
2. Gerar `metricas/metricas_<empresa>.json` no formato de `templates/metricas_exemplo.json`, **a partir de `saida/<pdf>/pagina_NN.txt`**
3. `python src/verificar_numeros.py saida/<pdf> metricas/metricas_<empresa>.json`; corrigir só os itens com ERRO, olhando a página indicada
4. Tabela comparativa e gráficos a partir dos JSONs verificados
5. Slides (python-pptx ou HTML) seguindo `templates/roteiro_apresentacao.md`

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

## Mapa de páginas (índice do PDF = número do pagina_NN.txt)
Os números impressos na folha são outros (a DRE da Gerdau está impressa como 24 e "PÁGINA: 16 de 65"); não usar.
- DRE consolidada: Gerdau pág. 29–30; Usiminas pág. 14
- Release completo da Usiminas: pág. 21–47
- Segmentos e EBITDA ajustado da Gerdau: notas, pág. 71–74
