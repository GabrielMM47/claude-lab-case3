# Roteiro do vídeo — 2 minutos

Gravar a tela com a apresentação aberta no link público (https://claude.ai/artifact/CuFHhUEJA44KkaTf9MNsYC), o terminal na raiz do repositório e o PDF do ITR da Usiminas aberto na p. 28. Ensaiar uma vez antes de gravar. Total de falas: cerca de 270 palavras.

## 0:00–0:20 · O problema (Pessoa 1)

**Tela:** capa da apresentação (slide 1).

> Um comitê de investimentos quer saber qual siderúrgica teve o melhor terceiro trimestre: Gerdau ou Usiminas. A resposta está espalhada em ITRs de cem páginas e apresentações de RI, com unidades, períodos e critérios de EBITDA diferentes. Um número na coluna errada muda a conclusão.

## 0:20–1:20 · A solução funcionando (Pessoa 2)

**Tela:** terminal rodando `python src/pipeline.py --a gerdau --b usiminas --tri 3T26` (cerca de 10 segundos com os PDFs já extraídos). Mostrar a linha "202/239 OK · 0 erro · status APROVADO" e o "ENTREGUE".

> Com um comando, o fluxo lê os PDFs oficiais, extrai as demonstrações, confere cada número contra a página de onde veio, calcula os indicadores e gera a apresentação.

**Tela:** passar pelos slides 2, 4 e 7 da apresentação, apontando o rodapé com as páginas.

> A conclusão: a Gerdau foi mais rentável, com margem EBITDA de 20,2% contra 9,0%, e cresceu; a Usiminas tem caixa líquido, mas a receita caiu. Todo número tem a página do PDF no rodapé. E quando falta dado, como volume consolidado da Gerdau, o slide diz isso em vez de inventar.

> O Claude escreveu os títulos, mas sem digitar nenhum número: o texto usa marcadores que o código troca pelo valor verificado.

## 1:20–1:40 · Um número conferido na fonte (Pessoa 3)

**Tela:** ITR da Usiminas, p. 28, linha "EBITDA (Instrução CVM 156)".

> Aqui o Claude errou. O 156 do nome "Instrução CVM 156" foi lido como o EBITDA do trimestre, e cada valor escorregou uma coluna. O primeiro verificador aprovou, porque os números existiam na linha. Quem pegou foi a reconciliação: o EBITDA mais os ajustes não fechava. Hoje o verificador exige a coluna certa, e o valor correto, 588 milhões, fecha com o EBITDA ajustado de 558 milhões.

## 1:40–2:00 · Impacto e próximos passos (Pessoa 4)

**Tela:** slide 8 (metodologia) e depois o README no GitHub.

> Um analista troca os PDFs e roda o mesmo comando para outra empresa ou outro trimestre: o que é determinístico roda sozinho, e o que precisa do Claude vem como um prompt pronto. Com mais um dia, completaríamos a evidência dos 37 números ainda para revisar e o volume consolidado da Gerdau. Não é recomendação de investimento.

## Checagem antes de publicar

- Duração até 2:00 (a banca para de assistir em 2:00).
- Publicar como YouTube "não listado" ou Drive "qualquer pessoa com o link"; abrir o link numa aba anônima.
- Colar o link no README (linha "Vídeo") e no formulário de entrega.
