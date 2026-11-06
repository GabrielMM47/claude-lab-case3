# Design system "Comitê" — apresentação executiva

Uma apresentação para comitê de investimentos: só os números e as cores das duas empresas chamam
atenção. Implementado no CSS de `src/apresentacao.py`; vale para qualquer par de empresas.

## Princípios
1. **Contenção.** Nada de faixas, barras laterais, caixas coloridas, sombras ou cantos arredondados.
2. **Cor = empresa.** As únicas cores fortes vêm de `config/empresas.toml` (as mesmas dos gráficos do
   CASE-05). Verde/vermelho só nos sinais +/− de destaque; âmbar só em N/D e alertas.
3. **Números legíveis.** Algarismos tabulares; vencedor em peso 600 + "melhor" na cor da empresa.
4. **Fonte sempre visível.** Rodapé com páginas (numeração do PDF) e o aviso em todos os slides.

## Tokens
| Token | Valor | Uso |
|---|---|---|
| `--superficie` | `#F4F6F8` | slide (cinza-azulado claro; gráficos brancos viram placas com régua de 1px) |
| `--palco` | `#D9DEE3` | em volta do slide |
| `--tinta` | `#1F2328` | texto |
| `--sec` | `#59636E` | legendas, variações, fontes |
| `--linha` | `#D8DEE4` | réguas de 1px (tabela, rodapé) |
| `--nd` | `#9A6700` | N/D e alertas (só texto) |
| `--pos` / `--neg` | `#1A7F37` / `#CF222E` | sinais + / − |
| empresa | `--cor` (do config) | nome da empresa, cabeçalho da coluna, "melhor" |

**Tipografia:** Archivo (SIL OFL 1.1, embutida em base64; `templates/fontes/`), largura normal,
pesos 400 e 600. Escala 1,25: 12 / 15 / 18 / 23 / 29 px; 44 px só no título da capa.

**Layout:** slide 1280×720, margem 64 px, alinhado à esquerda; rodapé com régua de 1 px.

## Componentes
- **Título + subtítulo**: o título é a mensagem do slide (vem da narrativa ou do insight).
- **Tabela comparativa**: cabeçalho das empresas na cor de cada uma; linhas com régua de 1 px.
- **Duas colunas**: nome da empresa na cor dela, sem sublinhado.
- **Alerta**: texto âmbar com prefixo "Atenção:", sem caixa.
- **Gráficos**: PNG de fundo branco, sem moldura.
