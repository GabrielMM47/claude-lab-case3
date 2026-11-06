# Case 3 — Comparativo de resultados: apresentação executiva

Claude Lab · Economia & Finanças · PUC-Rio · 06/11/2026

## Contexto

Temporada de balanços. Em poucos dias, as empresas da bolsa divulgam seus resultados do trimestre, e o documento oficial entregue à CVM é o **ITR (Informações Trimestrais)**: um PDF de 80 a 110 páginas com demonstrações financeiras, notas explicativas e o comentário da administração. Num banco ou numa gestora, alguém precisa ler esses documentos rápido, **comparar as empresas de um mesmo setor** e levar a conclusão para quem decide, num formato que se lê em poucos minutos: uma apresentação.

Neste case, vocês são os **estagiários/analistas** desse time, cobrindo **siderurgia**.

## A demanda

> **De:** Diretor de Research
> **Para:** time de análise
> **Assunto:** Gerdau × Usiminas no 3T26 — preciso de slides para o comitê
>
> "Saíram os ITRs do 3º trimestre. Quero comparar **Gerdau e Usiminas** lado a lado: receita, EBITDA, margem, lucro, endividamento e as métricas que importam para siderurgia. Monte uma **apresentação curta, de 6 a 8 slides**, para eu levar ao comitê de investimentos. Todo número precisa ter a página do ITR de onde saiu. Não quero tabelão: quero a mensagem de cada slide no título."

## Resultado esperado

Uma **apresentação executiva** (PowerPoint ou HTML), gerada com o Claude a partir dos números extraídos e conferidos. Uma estrutura que funciona:

1. **Capa** com a mensagem principal: quem foi melhor no trimestre e por quê;
2. **Resumo executivo**: as 3 conclusões que o diretor precisa levar;
3. **Tabela comparativa** das métricas principais (mesma unidade e mesmo critério para as duas);
4. **Gráficos**: receita, EBITDA e margem, no trimestre e contra o mesmo trimestre de 2025;
5. **Destaques por empresa**: o que foi positivo e negativo em cada uma;
6. **Métricas do setor**: volume vendido, preço ou receita por tonelada, dívida líquida/EBITDA;
7. **Riscos e o que observar** no próximo trimestre (as próprias empresas comentam isso no ITR);
8. **Fontes e metodologia**: páginas dos ITRs, contábil × ajustado, aviso de que não é recomendação de investimento.

O artefato público é a versão publicada da apresentação (HTML ou PDF).

> A diferença para o Case 2: lá o produto é um site para conversar com os dados. Aqui o produto é uma **apresentação pronta para a diretoria**, que cruza as duas empresas.

## Os dados

Os ITRs **já estão no repositório**, na pasta [`data/itrs/`](../data/itrs/):

| Arquivo | Empresa | Período | Páginas |
|---|---|---|---|
| [`gerdau_ITR_3T26.pdf`](../data/itrs/gerdau_ITR_3T26.pdf) | Gerdau S.A. (GGBR) | 3º trimestre de 2026 (até 30/09/2026) | 80 |
| [`usiminas_ITR_3T26.pdf`](../data/itrs/usiminas_ITR_3T26.pdf) | Usiminas (USIM) | 3º trimestre de 2026 (até 30/09/2026) | 110 |

Fonte: as próprias empresas (sites de Relações com Investidores e CVM).

**Mapa rápido para não se perder nas páginas:**

- **Demonstração do resultado consolidada:** Gerdau, pág. 29 e 30; Usiminas, pág. 14;
- **Comentário da administração:** a Usiminas traz o **release de resultados completo** dentro do ITR (pág. 21 a 47, com EBITDA ajustado e dados por unidade de negócio); a Gerdau traz o comentário de desempenho **da holding** (pág. 2 em diante, ver cuidado nº 1);
- **EBITDA ajustado e dados por segmento da Gerdau:** notas explicativas, "Informações por segmentos de negócio" (pág. 71 a 74).

## Guia sugerido

O guia é uma sugestão de caminho, não uma receita. O que importa é entregar o resultado esperado com números confiáveis.

### 1. Definir as métricas

Antes de extrair qualquer coisa, decidam **o que comparar**: de 5 a 8 métricas, comuns às duas (receita líquida, EBITDA ajustado, margem EBITDA, lucro líquido, dívida líquida) mais as de siderurgia (volume vendido, receita por tonelada). Combinem as definições: contábil ou ajustado? Trimestre contra o mesmo trimestre de 2025 ou contra o 2º trimestre de 2026?

### 2. Achar as páginas e extrair os números com o Claude

Com o mapa acima, separem as páginas que importam e peçam ao Claude para extrair as métricas para uma tabela (JSON ou CSV), **cada número com a página e o trecho de onde saiu**. O formato está em [`metricas_exemplo.json`](../templates/metricas_exemplo.json).

### 3. Verificar

Rodem o [`verificar_numeros.py`](../src/verificar_numeros.py), que confere cada número contra o PDF (trecho, valor, unidade e variação). Corrijam o que falhar e **anotem os erros que o verificador pegou**: isso vale ouro no vídeo e no README do time.

### 4. Comparar

Juntem as duas empresas numa tabela única, **na mesma unidade e com o mesmo critério**, calculem as variações e montem os gráficos. A Gerdau é bem maior que a Usiminas: comparem **margens e variações**, não só valores absolutos. É aqui que aparece a história.

### 5. Escrever a história

Antes de gerar os slides, escrevam (com o Claude) a **mensagem de cada slide**, uma frase por título. Exemplo: "Gerdau amplia margem enquanto Usiminas sofre com o minério" em vez de "Margem EBITDA".

### 6. Gerar a apresentação

Peçam ao Claude para gerar a apresentação **a partir da tabela verificada e das mensagens**, nunca de memória:

- **PowerPoint:** o Claude cria o arquivo `.pptx` direto no claude.ai, ou pelo Claude Code com a biblioteca `python-pptx`;
- **HTML:** slides numa página web, que já servem como artefato publicado.

Revisem como se fossem o diretor: algum número sem fonte? Algum título que não diz nada?

### Ritmo sugerido no dia

| Momento | Passos |
|---|---|
| Manhã (10h30–13h00) | 1 a 3: métricas definidas, números extraídos e verificados |
| Tarde (14h00–16h00) | 4 a 6: comparação, mensagens, apresentação gerada e publicada |

Guia técnico em **[GUIA_TECNICO.md](GUIA_TECNICO.md)**.

## Cuidados com os dados

1. **Holding (controladora) ≠ consolidado.** O ITR traz as demonstrações individuais e as consolidadas. O comentário de desempenho da Gerdau fala da **holding**, cuja receita é só uma fração da do grupo: comparem sempre os números **consolidados**.
2. **Contábil ≠ ajustado.** As duas divulgam EBITDA "ajustado", que exclui efeitos pontuais. Usem o mesmo critério para as duas e digam qual.
3. **Efeitos pontuais distorcem a comparação anual.** Se um trimestre de 2025 teve um evento extraordinário (uma baixa contábil, por exemplo), a variação contra ele engana. Procurem e expliquem.
4. **Trimestre contra trimestre (T/T) ≠ ano contra ano (A/A).** Deixem claro qual comparação é qual.
5. **Unidades.** As demonstrações estão em **R$ mil**; o release da Usiminas mistura R$ mil e R$ milhões. Confiram antes de calcular.
6. **Negócios diferentes.** A Gerdau tem operações fora do Brasil (América do Norte); a Usiminas tem também mineração. Olhem os segmentos antes de concluir que uma "é melhor" que a outra.
7. **Não é recomendação de investimento.** Coloquem o aviso na apresentação.

## O que a banca vai olhar neste case

- A apresentação está **pronta para um diretor**: curta, com a mensagem no título de cada slide?
- Todo número tem **fonte (página do ITR)** e foi **verificado**?
- A comparação é **justa** (consolidado, mesma unidade, mesmo critério, efeitos pontuais explicados)?
- O time mostrou **onde o Claude errou** e como pegou o erro?

## Perguntas para atacar

- Quem foi melhor no trimestre, e em quê? A resposta muda se olharmos margem em vez de tamanho?
- Quanto do resultado de cada uma veio do Brasil e quanto de fora (ou da mineração, no caso da Usiminas)?
- Onde o Claude erra na leitura do ITR (tabelas, unidades, individual × consolidado)? Como vocês pegaram o erro?
- Dá para ter um **fluxo** que gera a mesma apresentação para o próximo trimestre, trocando só os PDFs?
