# Design system "Tarja" — apresentação executiva

Apresentação para comitê de investimentos. A cor de cada empresa ocupa **faixas inteiras**
(metade da capa, cabeçalho da coluna, campo do número), e tudo o mais é cinza-concreto e tinta.
Quem é quem se lê de longe, sem legenda. Implementado no CSS de `src/apresentacao.py` e vale
para qualquer par de empresas: as cores vêm de `config/empresas.toml`, as mesmas dos gráficos
do CASE-05 (`src/graficos.py` lê a cor do `comparativo.json`).

## Princípios
1. **Uma mensagem por slide.** O título é a conclusão (vem da narrativa ou do insight). O corpo só prova o título.
2. **Cor = empresa, em blocos.** Azul e laranja só aparecem como faixa da empresa. Verde/vermelho só nos sinais + / −; âmbar só em N/D e alertas.
3. **Cada número com a sua página.** Na tabela, a página do ITR (numeração do PDF) fica embaixo de cada número; o rodapé junta as fontes do slide.
4. **Notas no pé, não na célula.** Bases de cálculo e motivos de N/D viram notas numeradas (¹ ² ³).
5. **Aviso sempre visível.** "Não constitui recomendação de investimento" no rodapé de todos os slides.

## Tokens
| Token | Valor | Uso |
|---|---|---|
| `--superficie` | `#E7EAEC` | slide (cinza-concreto) |
| `--palco` | `#B9C0C6` | em volta do slide |
| `--tinta` | `#161B21` | texto, títulos |
| `--sec` | `#56616C` | legendas, variações, páginas |
| `--linha` | `#C9D0D6` | réguas de 1 px |
| `--faixa` | `#DDE1E4` | linhas alternadas da tabela |
| `--nd` | `#8A5A00` | N/D e alertas (texto) |
| `--pos` / `--neg` | `#1A7F37` / `#C4262E` | sinais + / − |
| Gerdau | `#14529C` | `config/empresas.toml` |
| Usiminas | `#E07818` | `config/empresas.toml` |

**Tipografia:** só Archivo (SIL OFL 1.1, embutida em base64; `templates/fontes/`), usando o eixo
de largura. Títulos e nomes em **Archivo condensada** (`font-stretch:75%`), peso 700–800; texto e
números em largura normal, algarismos tabulares. Escala: 12 / 15 / 18 / 22 / 36 px; capa 48 px
(título) e 84 px (nome da empresa).

**Layout:** slide 1280×720, margem 64 px, alinhado à esquerda; rodapé com régua de 1 px.

## Componentes
- **Capa**: duas metades na cor de cada empresa (nome, ticker, margem EBITDA); título-mensagem embaixo.
- **Tarja**: faixa na cor da empresa com nome e ticker; abre cada coluna (perfil, destaques).
- **Par de números** (resumo): os dois valores lado a lado, cada um num campo na cor da empresa. Vem de `"destaques"` na narrativa (`"margem_ebitda"`, `"receita_liquida.var_aa"`) ou da 1ª chave do insight.
- **Tabela**: cabeçalho em blocos de cor; linhas alternadas; valor + "A/A · ITR p. N" embaixo; vencedor em negrito com barra de 6 px na cor da empresa (só onde há regra econômica clara).
- **Item de destaque**: rótulo à esquerda (+, −, Observar, Atenção, Sem dado) e texto à direita.
- **Gráficos**: PNG de fundo branco, sem moldura.
- **Tabela por negócio** (setor): cabeçalho em tinta, faixa da empresa à esquerda, barra de EBITDA/t na cor dela.
- **Cartões de contexto** (setor): régua de 4 px em tinta, título condensado; números do contexto macro com página.
- **Tabela de cenários** (destaques): cabeçalhos em blocos de cor; vantagem com barra de 6 px na cor da empresa; efeito com símbolo (▲ ▼ ●), não só cor.

## Conteúdo por slide (o que entra e por quê)
| Slide | Mensagem | Conteúdo |
|---|---|---|
| capa | quem foi mais rentável | margem EBITDA das duas + título |
| resumo | três conclusões | Rentabilidade, Crescimento, Caixa e balanço: par de números + uma frase |
| perfil | negócios diferentes | uma frase institucional por empresa + "Segmentos: …" + gráfico de mix |
| comparativo | quem vence em quê | 8 linhas: receita, EBITDA, margem, lucro, FCL, DL/EBITDA, ROE, ROIC |
| graficos | crescimento e margens | receita/EBITDA A/A e margens |
| setor | caixa e balanço; por tonelada sem base | caixa das operações, FCL, capex/receita, dívida líquida; por tonelada com motivo do N/D; gráfico de alavancagem |
| destaques_riscos | o que distorce a leitura | + e − A/A (sem linhas com efeito pontual), guidance/capex, alertas; N/D agrupados numa linha |
| metodologia | como confiar nos números | critério, períodos (anualizado × acumulado), verificação em destaque, fontes |

Cortes: capacidade, mercados e estratégia (texto institucional) saem do perfil; "riscos" das
apresentações (texto padrão de governança/previsões) sai dos destaques, porque os riscos que
importam são os alertas do comparativo; margem líquida sai da tabela (repete o lucro) e fica de reserva.
