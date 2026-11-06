# Roteiro do vídeo — 1:52, só texto

O vídeo mostra a jornada de quem vai usar o projeto, do clone à apresentação. Não tem narração nem
som: tudo está escrito na tela. Arquivo: `entrega/video_jornada_gerdau_x_usiminas_3T26.mp4`.
Fonte editável em `video/index.html` (HyperFrames); para renderizar de novo:
`cd video && npx hyperframes@0.9.19 render -o ../entrega/video_jornada_gerdau_x_usiminas_3T26.mp4`.

| Tempo | Cena | O que aparece |
|---|---|---|
| 0:00 | Abertura | Gerdau e Usiminas nas cores do design system; "Do ITR em PDF à apresentação do comitê, com um comando" |
| 0:07 | Problema | Os quatro riscos: período, unidade, escopo e critério de EBITDA |
| 0:18 | 1 · Instalar | `git clone`, `python3 -m venv`, `pip install -r requirements.txt`; os PDFs já vêm em `data/` |
| 0:30 | 2 · Rodar | `python src/pipeline.py --a gerdau --b usiminas --tri 3T26` e as 8 etapas até "ENTREGUE" |
| 0:47 | 3 · Rastrear | Um fato real: EBITDA da Usiminas, ITR p. 28, com `pagina` e `trecho` |
| 1:00 | 4 · Verificar | 233 conferidos, 39 para revisar, 0 com erro; o caso do "156" de "Instrução CVM 156" |
| 1:18 | 5 · Abrir | Capa, resumo, tabela e destaques da apresentação |
| 1:38 | Outro par | Mesmo comando com outros PDFs; o pipeline imprime o prompt quando falta um arquivo de fatos; link do repositório e aviso |

Testado num clone limpo: o pipeline vai do zero à entrega em menos de um minuto.
Os números da cena 4 vêm de `saida/verificacao_gerdau_x_usiminas_3T26.json`; se a verificação mudar,
atualize `video/index.html` e renderize de novo.
