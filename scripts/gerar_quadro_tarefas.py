"""Gera o quadro de tarefas em HTML a partir de docs/TAREFAS.md (fonte única).

Rode da raiz do repositório depois de editar docs/TAREFAS.md:
    python scripts/gerar_quadro_tarefas.py

Opções:
    --md / --saida   caminhos (padrão: docs/TAREFAS.md → docs/quadro_tarefas.html)
    --artifact       gera só o miolo da página, para publicar como artefato no claude.ai
                     (sem <html>/<head> e sem mermaid via CDN, que o artefato já renderiza)
"""
import argparse
import html
import re
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--md", default="docs/TAREFAS.md")
parser.add_argument("--saida", default="docs/quadro_tarefas.html")
parser.add_argument("--artifact", action="store_true")
args = parser.parse_args()

md_path, out_path = Path(args.md), Path(args.saida)
md = md_path.read_text(encoding="utf-8")


def secao(inicio: str, fim: str | None) -> str:
    i = md.index(inicio)
    j = md.index(fim, i + len(inicio)) if fim else len(md)
    return md[i:j].strip().rstrip("-").strip()


objetivo = secao("## Objetivo", "## Quadro")
dependencias = secao("## Dependências", "## Marcos sugeridos")
# troca o diagrama ASCII de dependências pelo mermaid do quadro
dependencias = re.sub(r"```\nCASE-01.*?```\n", "", dependencias, flags=re.S)
marcos = secao("## Marcos sugeridos", "## Contrato de dados")
contrato = secao("## Contrato de dados", "## Cards")
cards_md = {}
for m in re.finditer(r"^### (CASE-0\d) .*?(?=^### CASE-0\d |\Z)", md, flags=re.S | re.M):
    cards_md[m.group(1)] = m.group(0).strip().rstrip("-").strip()

PESSOAS = [
    ("gp", "Gabriel Patrício", "feat/gabriel-patricio", "Contrato e apresentação"),
    ("gm", "Gabriel Martins", "feat/gabriel-martins", "ITR financeiro e pipeline"),
    ("ge", "Geronimo", "feat/geronimo", "Institucional e entrega"),
    ("jv", "João Vitor", "feat/joao-vitor", "Indicadores e comparativo"),
]
CARDS = {
    "gp": [
        ("CASE-01", "Contrato de dados, catálogo e fixtures", "P0", "45 min", "—", "—", "todos (merge cedo)"),
        ("CASE-06", "Gerador da apresentação executiva", "P1", "2,5 h", "fixture do 01", "05 + qualitativo do 03", "07, 08"),
    ],
    "gm": [
        ("CASE-02", "Extração financeira do ITR (parser CVM + EBITDA)", "P0", "3 h", "contrato", "—", "04, 07"),
        ("CASE-07", "Pipeline “um comando” + relatório de verificação", "P1", "1,5 h", "interfaces de CLI", "02, 04, 05, 06 (+03)", "08"),
    ],
    "ge": [
        ("CASE-03", "Apresentação institucional + operacional e qualitativo", "P0", "3 h", "contrato", "—", "04, 06, 07"),
        ("CASE-08", "Entrega: Skill, README, registros, publicação e vídeo", "P1", "1,5 h", "—", "todos", "—"),
    ],
    "jv": [
        ("CASE-04", "Motor de indicadores (ROE, ROIC, margens, R$/t)", "P0", "2 h", "01 (contrato + fixtures)", "02 e 03", "05"),
        ("CASE-05", "Comparativo, insights e gráficos", "P1", "1,5 h", "fixture do 01", "04", "06, 07"),
    ],
}
DONO = {cid: p for p, cs in CARDS.items() for cid, *_ in cs}

MERMAID = """flowchart LR
  C01["CASE-01 · Contrato<br/>Gabriel Patrício"]
  C02["CASE-02 · ITR financeiro<br/>Gabriel Martins"]
  C03["CASE-03 · Institucional<br/>Geronimo"]
  C04["CASE-04 · Indicadores<br/>João Vitor"]
  C05["CASE-05 · Comparativo<br/>João Vitor"]
  C06["CASE-06 · Slides<br/>Gabriel Patrício"]
  C07["CASE-07 · Pipeline<br/>Gabriel Martins"]
  C08["CASE-08 · Entrega<br/>Geronimo"]
  C01 -. merge cedo .-> C02
  C01 -. merge cedo .-> C03
  C01 -. fixtures .-> C04
  C02 --> C04
  C03 --> C04
  C04 --> C05
  C05 --> C06
  C03 -. qualitativo .-> C06
  C02 --> C07
  C06 --> C07
  C07 --> C08"""


def md_block(texto: str, alvo: str) -> str:
    return (f'<div class="md" id="{alvo}"></div>\n'
            f'<script type="text/markdown" data-alvo="{alvo}">\n{texto}\n</script>')


colunas = []
for chave, nome, branch, foco in PESSOAS:
    tiles = []
    for cid, titulo, prio, est, comeca, fecha, bloqueia in CARDS[chave]:
        tiles.append(f"""
      <a class="tile" href="#{cid.lower()}">
        <span class="tile-top"><span class="cid">{cid}</span><span class="prio prio-{prio.lower()}">{prio}</span><span class="est">{est}</span></span>
        <span class="tile-title">{html.escape(titulo)}</span>
        <span class="deps">
          <span><b>Começa com</b> {html.escape(comeca)}</span>
          <span><b>Fecha com</b> {html.escape(fecha)}</span>
          <span><b>Bloqueia</b> {html.escape(bloqueia)}</span>
        </span>
      </a>""")
    colunas.append(f"""
    <section class="lane lane-{chave}" aria-label="{nome}">
      <header class="lane-head">
        <span class="avatar">{''.join(w[0] for w in nome.split()[:2])}</span>
        <span><span class="lane-name">{nome}</span><span class="lane-focus">{foco}</span></span>
      </header>
      <code class="branch">{branch}</code>
      {''.join(tiles)}
    </section>""")

cards_html = []
for cid, texto in cards_md.items():
    p = DONO[cid]
    nome = next(n for k, n, *_ in PESSOAS if k == p)
    cards_html.append(f"""
  <article class="card card-{p}" id="{cid.lower()}">
    <div class="card-owner">{nome}</div>
    {md_block(texto, cid.lower() + '-md')}
  </article>""")

page = f"""<title>Quadro Siderurgia Case 3</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap">
<style>
/* Layout: assignee swimlanes (the board) up top, dependency map, then full card specs in one reading column */
:root {{
  --bg: #ECEFF2;
  --surface: #FFFFFF;
  --sunken: #E2E7EC;
  --ink: #16202A;
  --muted: #56636F;
  --line: #CDD4DB;
  --accent: #B4501A;
  --gp: #2C67A8; --gm: #23806A; --ge: #7F55AE; --jv: #A57618;
  --p0-bg: #F6DED0; --p0-fg: #8A3A0F;
  --p1-bg: #DCE4EC; --p1-fg: #34495E;
  --f-display: "IBM Plex Sans Condensed", "Arial Narrow", "Roboto Condensed", sans-serif;
  --f-body: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --f-mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #11161B; --surface: #192028; --sunken: #0D1216; --ink: #E3E8ED; --muted: #98A4AF; --line: #2B3540;
    --accent: #E58046;
    --gp: #6FA3DB; --gm: #5BBE9F; --ge: #B293D8; --jv: #D8AB4E;
    --p0-bg: #4A2614; --p0-fg: #F2B38E; --p1-bg: #24313D; --p1-fg: #B7C6D4;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #11161B; --surface: #192028; --sunken: #0D1216; --ink: #E3E8ED; --muted: #98A4AF; --line: #2B3540;
  --accent: #E58046;
  --gp: #6FA3DB; --gm: #5BBE9F; --ge: #B293D8; --jv: #D8AB4E;
  --p0-bg: #4A2614; --p0-fg: #F2B38E; --p1-bg: #24313D; --p1-fg: #B7C6D4;
  color-scheme: dark;
}}
* {{ box-sizing: border-box; }}
body {{
  background: var(--bg); color: var(--ink); font-family: var(--f-body); font-size: 15px; line-height: 1.55;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 32px 64px;
}}
.wrap {{ max-width: 1240px; margin: 0 auto; display: grid; gap: 40px; }}
h1, h2, h3, h4 {{ font-family: var(--f-display); text-wrap: balance; line-height: 1.15; margin: 0; }}
a {{ color: var(--accent); }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}

.masthead {{ display: grid; gap: 14px; border-bottom: 3px solid var(--ink); padding-bottom: 20px; }}
.eyebrow {{ font-family: var(--f-mono); font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
.masthead h1 {{ font-size: clamp(30px, 5vw, 52px); font-weight: 700; letter-spacing: -.01em; }}
.masthead h1 span {{ color: var(--accent); }}
.lede {{ max-width: 68ch; color: var(--muted); font-size: 16px; margin: 0; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 8px 20px; font-family: var(--f-mono); font-size: 12.5px; color: var(--muted); }}
.meta b {{ color: var(--ink); font-weight: 500; }}

.section-head {{ display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
.section-head h2 {{ font-size: 26px; font-weight: 700; }}
.section-head p {{ margin: 0; color: var(--muted); }}

.board {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
@media (max-width: 1000px) {{ .board {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 560px) {{ .board {{ grid-template-columns: minmax(0, 1fr); }} }}
.lane {{ background: var(--sunken); border-radius: 6px; padding: 12px; display: flex; flex-direction: column; gap: 10px; border-top: 4px solid var(--c); min-width: 0; }}
.lane-gp {{ --c: var(--gp); }} .lane-gm {{ --c: var(--gm); }} .lane-ge {{ --c: var(--ge); }} .lane-jv {{ --c: var(--jv); }}
.lane-head {{ display: flex; align-items: center; gap: 10px; }}
.avatar {{ width: 34px; height: 34px; border-radius: 50%; background: var(--c); color: var(--surface); display: grid; place-items: center; font-family: var(--f-display); font-weight: 700; font-size: 14px; flex: none; }}
.lane-name {{ display: block; font-family: var(--f-display); font-weight: 700; font-size: 17px; }}
.lane-focus {{ display: block; font-size: 12.5px; color: var(--muted); }}
.branch {{ font-family: var(--f-mono); font-size: 12px; color: var(--muted); background: var(--surface); border: 1px solid var(--line); border-radius: 4px; padding: 3px 7px; align-self: flex-start; max-width: 100%; overflow-wrap: anywhere; }}
.tile {{ display: grid; gap: 8px; background: var(--surface); border: 1px solid var(--line); border-radius: 5px; padding: 12px; color: var(--ink); text-decoration: none; transition: border-color .15s; }}
.tile:hover {{ border-color: var(--c); }}
.tile-top {{ display: flex; align-items: center; gap: 8px; font-family: var(--f-mono); font-size: 12px; }}
.cid {{ color: var(--c); font-weight: 500; }}
.est {{ margin-left: auto; color: var(--muted); font-variant-numeric: tabular-nums; }}
.prio {{ border-radius: 3px; padding: 1px 6px; font-weight: 500; }}
.prio-p0 {{ background: var(--p0-bg); color: var(--p0-fg); }}
.prio-p1 {{ background: var(--p1-bg); color: var(--p1-fg); }}
.tile-title {{ font-family: var(--f-display); font-weight: 600; font-size: 16.5px; line-height: 1.25; }}
.deps {{ display: grid; gap: 3px; font-size: 12.5px; color: var(--muted); border-top: 1px dashed var(--line); padding-top: 8px; }}
.deps b {{ color: var(--ink); font-weight: 600; display: inline-block; min-width: 76px; }}

.panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 20px; min-width: 0; }}
.two {{ display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 20px; align-items: start; }}
@media (max-width: 900px) {{ .two {{ grid-template-columns: minmax(0, 1fr); }} }}
.diagram {{ overflow-x: auto; }}
pre.mermaid {{ background: transparent; margin: 0; text-align: center; }}

.cards {{ display: grid; gap: 22px; }}
.card {{ background: var(--surface); border: 1px solid var(--line); border-left: 5px solid var(--c); border-radius: 6px; padding: 22px clamp(16px, 3vw, 32px); min-width: 0; scroll-margin-top: 16px; }}
.card-gp {{ --c: var(--gp); }} .card-gm {{ --c: var(--gm); }} .card-ge {{ --c: var(--ge); }} .card-jv {{ --c: var(--jv); }}
.card-owner {{ font-family: var(--f-mono); font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--c); margin-bottom: 6px; }}

.md {{ min-width: 0; }}
.md > :first-child {{ margin-top: 0; }}
.md h2 {{ font-size: 24px; margin: 28px 0 10px; }}
.md h3 {{ font-size: 21px; margin: 26px 0 10px; }}
.card .md h3:first-child {{ font-size: 24px; }}
.md h4 {{ font-size: 16px; margin: 20px 0 8px; }}
.md p, .md li {{ max-width: 80ch; }}
.md p {{ margin: 0 0 12px; }}
.md ul, .md ol {{ padding-left: 22px; margin: 0 0 12px; }}
.md li {{ margin: 3px 0; }}
.md li > ul, .md li > ol {{ margin: 4px 0; }}
.md code {{ font-family: var(--f-mono); font-size: .86em; background: var(--sunken); border-radius: 3px; padding: 1px 5px; overflow-wrap: anywhere; }}
.md pre {{ background: var(--sunken); border: 1px solid var(--line); border-radius: 5px; padding: 14px; overflow-x: auto; font-size: 12.5px; line-height: 1.45; margin: 0 0 14px; }}
.md pre code {{ background: none; padding: 0; overflow-wrap: normal; font-size: inherit; }}
.md blockquote {{ margin: 0 0 14px; padding: 10px 14px; border-left: 3px solid var(--accent); background: var(--sunken); color: var(--muted); }}
.md blockquote p {{ margin: 0; }}
.md hr {{ border: 0; border-top: 1px solid var(--line); margin: 20px 0; }}
.table-wrap {{ overflow-x: auto; margin: 0 0 16px; border: 1px solid var(--line); border-radius: 5px; }}
.md table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; font-variant-numeric: tabular-nums; }}
.md th, .md td {{ text-align: left; vertical-align: top; padding: 7px 10px; border-bottom: 1px solid var(--line); }}
.md th {{ background: var(--sunken); font-family: var(--f-display); font-weight: 600; font-size: 13.5px; white-space: nowrap; }}
.md tr:last-child td {{ border-bottom: 0; }}
.md input[type=checkbox] {{ margin: 0 6px 0 0; accent-color: var(--c, var(--accent)); }}
.md li:has(> input[type=checkbox]) {{ list-style: none; margin-left: -20px; }}
.contract {{ border-top: 3px solid var(--accent); }}
.foot {{ color: var(--muted); font-size: 13px; border-top: 1px solid var(--line); padding-top: 16px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; scroll-behavior: auto !important; }} }}
</style>

<div class="wrap">
  <header class="masthead">
    <div class="eyebrow">Claude Lab PUC-Rio · Case 3 · Siderurgia · 3T26</div>
    <h1>Comparador de <span>siderúrgicas</span></h1>
    <p class="lede">ITR e apresentação institucional de duas empresas quaisquer entram; uma apresentação executiva com métricas comuns e de siderurgia sai. Gerdau × Usiminas é o primeiro caso, não o único.</p>
    <div class="meta"><span>Fonte deste quadro: <b>docs/TAREFAS.md</b></span><span>Repo: <b>claude-lab-case3</b></span><span>Entrega: <b>16h00</b></span></div>
  </header>

  <section>
    <div class="section-head"><h2>Quadro por pessoa</h2><p>Clique num card para ver escopo e critérios de aceite.</p></div>
    <div class="board">{''.join(colunas)}
    </div>
  </section>

  <section class="two">
    <div class="panel">
      <div class="section-head"><h2>Quem depende de quem</h2></div>
      <div class="diagram"><pre class="mermaid">
{MERMAID}
</pre></div>
      {md_block(dependencias.split(chr(10), 1)[1], 'dependencias-md')}
    </div>
    <div class="panel">
      {md_block(marcos, 'marcos-md')}
    </div>
  </section>

  <section class="panel">
    {md_block(objetivo, 'objetivo-md')}
  </section>

  <section>
    <div class="section-head"><h2>Cards</h2></div>
    <div class="cards">{''.join(cards_html)}
    </div>
  </section>

  <section class="panel contract" id="contrato">
    {md_block(contrato, 'contrato-md')}
  </section>

  <footer class="foot">Gerado a partir de docs/TAREFAS.md. Edite o arquivo no repositório; este quadro é a versão para leitura e compartilhamento.</footer>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script>
(function () {{
  var blocos = document.querySelectorAll('script[type="text/markdown"]');
  blocos.forEach(function (s) {{
    var alvo = document.getElementById(s.dataset.alvo);
    if (!alvo) return;
    var texto = s.textContent.replace(/^\\n/, '');
    if (window.marked && marked.parse) {{
      alvo.innerHTML = marked.parse(texto, {{ gfm: true }});
      alvo.querySelectorAll('table').forEach(function (t) {{
        var w = document.createElement('div'); w.className = 'table-wrap';
        t.parentNode.insertBefore(w, t); w.appendChild(t);
      }});
      alvo.querySelectorAll('h2, h3').forEach(function (h) {{
        if (h.textContent.indexOf('Contrato de dados') === 0) h.id = 'contrato-titulo';
      }});
    }} else {{
      var pre = document.createElement('pre'); pre.textContent = texto; alvo.appendChild(pre);
    }}
  }});
}})();
</script>
"""
if not args.artifact:
    # versão para abrir direto do repositório: esqueleto completo, charset e mermaid via CDN
    page = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>body {{ margin: 0; }} img {{ max-width: 100%; }}</style>
</head>
<body>
{page}
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>
if (window.mermaid) {{
  var escuro = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  mermaid.initialize({{ startOnLoad: false, theme: escuro ? 'dark' : 'default' }});
  mermaid.run();
}}
</script>
</body>
</html>
"""
out_path.write_text(page, encoding="utf-8")
print(f"{out_path} ({len(page)//1024} KB), cards: {list(cards_md)}")
