# Guia rápido do Case 3: Gerdau × Usiminas no 3T26

Resumo de tudo o que importa para o case, extraído do repositório oficial do workshop. Para o enunciado completo, ver [CASE3.md](CASE3.md).

## 1. O pedido
O Diretor de Research quer uma **apresentação de 6 a 8 slides** para o comitê de investimentos, comparando **Gerdau e Usiminas** lado a lado no 3T26. Nós somos os analistas de siderurgia.

- Métricas: **receita, EBITDA, margem, lucro, endividamento** e as **métricas de siderurgia** (volume vendido, receita/preço por tonelada, dívida líquida/EBITDA).
- **Todo número com a página do ITR** de onde saiu (índice do PDF, não o número impresso na folha).
- **Nada de tabelão.** O **título de cada slide é a mensagem** ("Gerdau amplia margem enquanto Usiminas sofre com o minério", e não "Margem EBITDA").

## 2. Estrutura dos slides
| # | Slide | Conteúdo |
|---|---|---|
| 1 | Capa | Mensagem principal: quem foi melhor e por quê |
| 2 | Resumo executivo | 3 conclusões, cada uma com um número |
| 3 | Tabela comparativa | Métricas principais, mesma unidade e mesmo critério |
| 4 | Gráficos | Receita, EBITDA e margem: 3T26 e 3T26 contra 3T25 |
| 5 | Destaques por empresa | 1 positivo e 1 negativo de cada |
| 6 | Métricas do setor | Volume, receita/t, dívida líquida/EBITDA |
| 7 | Riscos e o que observar | O que as próprias empresas dizem no ITR |
| 8 | Fontes e metodologia | Páginas, contábil × ajustado, aviso de não recomendação |

Roteiro em [../templates/roteiro_apresentacao.md](../templates/roteiro_apresentacao.md). Formato: `.pptx` (python-pptx) ou slides HTML. **O artefato público é a apresentação publicada (HTML ou PDF).**

## 3. Mapa de páginas (índice do PDF, o mesmo número do `pagina_NN.txt`)
| O quê | Gerdau | Usiminas |
|---|---|---|
| DRE consolidada | pág. 29–30 | pág. 14 |
| Comentário / release | pág. 2+ (é da **holding**!) | pág. 21–47 (release completo, EBITDA ajustado, por unidade) |
| Segmentos / EBITDA ajustado | notas, pág. 71–74 | dentro do release |

Os números impressos na folha são outros (a DRE da Gerdau está impressa como 24 e "PÁGINA: 16 de 65"). Nos JSONs e nos slides vale sempre o índice do PDF.

## 4. Os 7 cuidados com os dados (a banca olha)
1. **Holding ≠ consolidado.** Usar sempre o **consolidado**.
2. **Contábil ≠ ajustado.** O mesmo critério de EBITDA para as duas, e dizer qual.
3. **Efeitos pontuais.** Um evento extraordinário no 3T25 distorce a variação anual. Achar e explicar.
4. **T/T ≠ A/A.** Rotular sempre.
5. **Unidades.** As demonstrações estão em R$ mil; o release da Usiminas mistura R$ mil e R$ milhões.
6. **Negócios diferentes.** Gerdau tem América do Norte; Usiminas tem mineração. Olhar os segmentos.
7. **Aviso de "não é recomendação de investimento"** na apresentação.

A Gerdau é bem maior: comparar **margens e variações**, não só valores absolutos.

## 5. Fluxo técnico
```
PDFs → src/extrair_release.py → Claude gera metricas/metricas_EMPRESA.json → src/verificar_numeros.py
     → (ERRO? corrige e verifica de novo) → tabela comparativa + gráficos → mensagens → slides
```
O verificador confere: o trecho existe na página; o valor aparece exatamente como escrito; o valor numérico bate com o texto; a variação recalculada bate (tolerância de 0,5 p.p.).

**Atenção:**
- `pagina` é o índice do PDF (o mesmo do `pagina_NN.txt`), que pode diferir do número impresso.
- `trecho` e `valor_como_aparece` devem ser cópias literais do texto extraído. Gerem o JSON a partir dos `pagina_NN.txt`.
- Margens e dívida líquida/EBITDA calculadas por nós não aparecem no PDF. Precisam ser recalculadas em código a partir dos números verificados.
- **Anotem cada erro pego** em [ERROS_ENCONTRADOS.md](ERROS_ENCONTRADOS.md) ("vale ouro" no vídeo e no README).

**Bônus que diferenciam:**
- um comando só: PDFs → apresentação, refazendo o que o verificador reprovar (dá para repetir no próximo trimestre trocando só os PDFs);
- uma Skill `apresentacao-resultados` (`.claude/skills/apresentacao-resultados/SKILL.md`, no padrão de [../referencia/SKILL_exemplo_bcb-sgs.md](../referencia/SKILL_exemplo_bcb-sgs.md)), dizendo quando usar, o passo a passo, o que nunca fazer e como verificar.

## 6. Entregas: tudo público, até as 16h00
1. **Vídeo de até 2 min** (a banca para em 2:00): problema (20s) → solução na tela (60s) → um número conferido na fonte (20s) → impacto e próximos passos (20s). YouTube não listado ou Drive com link aberto.
2. **Artefato público**: a apresentação publicada. Testar numa aba anônima.
3. **GitHub público** com o README preenchido (o [README.md](../README.md) deste repo já está no modelo), código e prompts ([PROMPTS.md](PROMPTS.md)).
4. **[Formulário de entrega](https://github.com/jplucas29/claude-lab-financas-puc2026/issues/new?template=entrega.yml)**, uma vez por time. Nenhuma chave ou `.env` no GitHub.

## 7. Critérios (nota de 1 a 5, ponderada)
| Peso | Critério | No Case 3 |
|---|---|---|
| 30 | Utilidade real | O diretor levaria a apresentação ao comitê como está? |
| 20 | Rigor e verificação | Todo número com página, verificado; mostrar **onde o Claude errou** |
| 20 | Produto | Slides curtos, claros, mensagem no título |
| 15 | Ideia | Bom recorte (Brasil × exterior, peso da mineração...) |
| 15 | Comunicação | Vídeo e README contam a história |

Os finalistas apresentam às 17h (5 min + 2 min de perguntas). Preparem resposta para: *"como vocês sabem que esse número está certo?"*

## 8. Perguntas para responder nos slides
- Quem foi melhor no trimestre, e em quê? A resposta muda se olharmos margem em vez de tamanho?
- Quanto do resultado veio do Brasil, quanto de fora e quanto da mineração?
- Onde o Claude errou na leitura do ITR (tabelas, unidades, individual × consolidado)?

## 9. Ritmo sugerido
- **Manhã (até 13h):** definir 5 a 8 métricas e os critérios (consolidado, ajustado?, A/A e T/T); extrair e verificar a Gerdau, depois a Usiminas.
- **Tarde (14h–16h):** tabela comparativa e gráficos → mensagens dos slides → gerar e publicar a apresentação → README, vídeo, formulário.

**Sugestão de divisão (4–5 pessoas):** 1 pessoa por empresa na extração e verificação · 1 em comparação e gráficos · 1 em mensagens e slides · 1 em README, vídeo e registro de erros e prompts.
