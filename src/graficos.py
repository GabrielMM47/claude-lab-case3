"""Gráficos do comparativo (CASE-05): lê só o dict do `comparativo.json` e grava PNGs 16:9.

    from graficos import gerar_graficos
    entradas = gerar_graficos(comp, Path("saida/comparativo/a_x_b_3T26"))

Gera `graficos/<id>.png` para receita_ebitda, margens, dl_ebitda, volume_rpt e mix_segmentos e
devolve as entradas de `comp["graficos"]`. Nada específico de empresa: nomes, cores e fontes vêm do
comparativo. Valor ausente nunca vira zero: a barra não é desenhada e o texto N/D/N/C/N/A fica no lugar.
"""
from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrato import TEXTO_STATUS, fmt_br, fmt_var  # noqa: E402

TAMANHO = (12.8, 7.2)
DPI = 150
LADOS = ("a", "b")
COR_TEXTO = "#222222"
COR_SUAVE = "#666666"
AVISO_SEM_DADOS = "dados indisponíveis"
LARGURA_RODAPE = 160
RODAPE_PDF = "páginas na numeração do PDF"
NOME_CRITERIO = {"ajustado": "ajustado", "contabil": "contábil"}

plt.rcParams.update({
    "font.size": 12,
    "axes.titlesize": 14,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#999999",
    "axes.labelcolor": COR_TEXTO,
    "xtick.color": COR_TEXTO,
    "ytick.color": COR_SUAVE,
})


# --------------------------------------------------------------------------- dados

def _linha(comp: dict, chave: str) -> dict | None:
    for linha in comp.get("linhas") or []:
        if linha.get("chave") == chave:
            return linha
    return None


def _chave_ebitda(comp: dict) -> str:
    crit = comp.get("criterio_ebitda")
    return f"ebitda_{crit}" if crit else "ebitda"


def _texto_criterio(comp: dict) -> str:
    crit = comp.get("criterio_ebitda")
    return f"EBITDA {NOME_CRITERIO.get(crit, crit)}" if crit else "EBITDA (sem critério comum)"


def periodo_anterior_aa(periodo: str) -> str | None:
    """Mesmo período do ano anterior: 3T26 -> 3T25, 9M26 -> 9M25, 1S2026 -> 1S2025."""
    m = re.fullmatch(r"(.*?)(\d{2}|\d{4})", periodo or "")
    if not m or not m.group(1):
        return None
    ano = int(m.group(2)) - 1
    if ano < 0:
        return None
    return f"{m.group(1)}{ano:0{len(m.group(2))}d}"


def _lado(linha: dict | None, x: str) -> dict:
    return (linha or {}).get(x) or {}


def _valor(linha: dict | None, x: str, periodo: str | None = None) -> tuple[float | None, str]:
    """(valor, texto) de um lado; valor None quando indisponível (texto = N/D/N/C/N/A)."""
    lado = _lado(linha, x)
    status = lado.get("status") or ("ok" if lado.get("disponivel", True) else "ausente")
    unidade = (linha or {}).get("unidade")
    if not lado or status != "ok":
        return None, TEXTO_STATUS.get(status, "N/D")
    if periodo is None or periodo == (linha or {}).get("periodo"):
        v = lado.get("valor")
        if v is None:
            v = (lado.get("valores") or {}).get((linha or {}).get("periodo"))
    else:
        v = (lado.get("valores") or {}).get(periodo)
    if v is None or isinstance(v, bool):
        return None, "N/D"
    return float(v), _rotulo(float(v), unidade)


def _rotulo(v: float, unidade: str | None) -> str:
    """Rótulo de barra: R$ milhões sem decimais a partir de 100 (cabe ao lado da barra vizinha)."""
    casas = 0 if unidade == "R$ milhões" and abs(v) >= 100 else None
    return fmt_br(v, unidade, casas=casas)


def _fontes(linhas: list[dict | None], x: str) -> list[str]:
    vistas: list[str] = []
    for linha in linhas:
        for f in _lado(linha, x).get("fontes") or []:
            if f not in vistas:
                vistas.append(f)
    return vistas


def _juntar_fontes(fontes: list[str]) -> str:
    """["ITR p.29", "ITR p.71", "Apresentação p.9"] -> "ITR p.29, p.71; Apresentação p.9"."""
    grupos: dict[str, list[str]] = {}
    for f in fontes:
        m = re.fullmatch(r"(.*?)\s*(p\.\s*\d+.*)", f)
        doc, pag = (m.group(1), m.group(2)) if m and m.group(1) else (f, "")
        grupos.setdefault(doc, [])
        if pag and pag not in grupos[doc]:
            grupos[doc].append(pag)
    partes = [f"{doc} {', '.join(pags)}".strip() for doc, pags in grupos.items()]
    return "; ".join(partes) if partes else "—"


def _nome(comp: dict, x: str) -> str:
    emp = (comp.get("empresas") or {}).get(x) or {}
    return emp.get("nome") or emp.get("slug") or x.upper()


def _cor(comp: dict, x: str) -> str:
    emp = (comp.get("empresas") or {}).get(x) or {}
    return emp.get("cor") or ("#4c6a8a" if x == "a" else "#9a6a3a")


def _clarear(cor: str, fator: float = 0.55) -> tuple[float, float, float]:
    r, g, b = to_rgb(cor)
    return (r + (1 - r) * fator, g + (1 - g) * fator, b + (1 - b) * fator)


# --------------------------------------------------------------------------- desenho

def _figura(ncols: int = 1):
    fig, eixos = plt.subplots(1, ncols, figsize=TAMANHO, dpi=DPI, squeeze=False)
    return fig, list(eixos[0])


def _finalizar(fig, titulo: str, rodape: str, notas: list[str]) -> None:
    fig.suptitle(titulo, fontsize=18, fontweight="bold", color=COR_TEXTO, x=0.03, ha="left", y=0.97)
    linhas_base = []
    if notas:
        linhas_base += textwrap.wrap("Notas: " + " · ".join(_sem_repeticao(notas)), LARGURA_RODAPE)
    linhas_base += textwrap.wrap(rodape, LARGURA_RODAPE)
    fig.text(0.03, 0.02, "\n".join(linhas_base), ha="left", va="bottom", fontsize=10, color=COR_SUAVE)
    base = 0.10 + 0.032 * (len(linhas_base) - 1)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.80, bottom=base + 0.08, wspace=0.25)


def _sem_repeticao(notas: list[str]) -> list[str]:
    """Remove notas repetidas e junta as que só diferem pelo nome da empresa ("A e B: obs")."""
    por_texto: dict[str, list[str]] = {}
    for n in notas:
        quem, sep, resto = n.partition(": ")
        chave = resto if sep else n
        por_texto.setdefault(chave, [])
        if sep and quem not in por_texto[chave]:
            por_texto[chave].append(quem)
    return [f"{' e '.join(q)}: {t}" if q else t for t, q in por_texto.items()]


def _rodape(comp: dict, fontes: dict[str, list[str]]) -> str:
    partes = [f"{_nome(comp, x)}: {_juntar_fontes(fontes[x])}" for x in LADOS]
    return "Fontes — " + " · ".join(partes) + " · " + RODAPE_PDF


def _aviso_sem_dados(ax) -> None:
    ax.text(0.5, 0.5, AVISO_SEM_DADOS, transform=ax.transAxes, ha="center", va="center",
            fontsize=16, color=COR_SUAVE, style="italic")
    ax.set_yticks([])


def _barra(ax, x: float, valor: float | None, texto: str, largura: float, cor, hachura: str | None,
           unidade: str | None) -> bool:
    """Desenha uma barra com rótulo; sem valor, só escreve o texto (N/D...) na linha do zero."""
    if valor is None:
        ax.text(x, 0, texto, ha="center", va="bottom", fontsize=12, fontweight="bold",
                color=COR_SUAVE, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#bbbbbb"))
        return False
    ax.bar(x, valor, largura, color=cor, hatch=hachura, edgecolor="white" if not hachura else _escurecer(cor),
           linewidth=0.8, zorder=2)
    ax.annotate(texto, (x, valor), xytext=(0, 4 if valor >= 0 else -4), textcoords="offset points",
                ha="center", va="bottom" if valor >= 0 else "top", fontsize=10, color=COR_TEXTO)
    return True


def _escurecer(cor, fator: float = 0.35):
    r, g, b = to_rgb(cor)
    return (r * (1 - fator), g * (1 - fator), b * (1 - fator))


def _ajustar_eixo(ax, valores: list[float]) -> None:
    """Margem para os rótulos e eixo atravessando o zero quando há negativos."""
    if not valores:
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        return
    lo, hi = min(0.0, *valores), max(0.0, *valores)
    folga = (hi - lo) * 0.15 or 1.0
    ax.set_ylim(lo - (folga if lo < 0 else 0), hi + folga)
    ax.axhline(0, color="#888888", linewidth=0.9, zorder=3)
    ax.grid(axis="y", color="#e5e5e5", zorder=0)


def _formatar_eixo_y(ax, unidade: str | None) -> None:
    from matplotlib.ticker import FuncFormatter
    def _tick(v, _):
        # casas mínimas para representar o tick sem arredondar (2,5 não pode virar "2")
        casas = next((c for c in range(3) if abs(round(v, c) - v) < 1e-9), 2)
        return fmt_br(v, None, casas=casas)

    ax.yaxis.set_major_formatter(FuncFormatter(_tick))
    if unidade:
        ax.set_ylabel(unidade)


def _salvar(fig, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.savefig(caminho, dpi=DPI)
    finally:
        plt.close(fig)


# --------------------------------------------------------------------------- gráficos

def _painel_aa(ax, comp: dict, linha: dict | None, titulo: str, atual: str, anterior: str | None) -> bool:
    """Barras período anterior (clara, hachurada) × atual por empresa; rótulo A/A no eixo x."""
    unidade = (linha or {}).get("unidade")
    largura, passo = 0.38, 0.21
    desenhou, vals = False, []
    rotulos = []
    for i, x in enumerate(LADOS):
        cor = _cor(comp, x)
        if _valor(linha, x)[0] is None and _lado(linha, x).get("status", "ok") != "ok" or not _lado(linha, x):
            _barra(ax, i, None, _valor(linha, x)[1], largura, cor, None, unidade)
            rotulos.append(_nome(comp, x) + ("\nA/A: —" if anterior else ""))
            continue
        if anterior:
            v, t = _valor(linha, x, anterior)
            desenhou |= _barra(ax, i - passo, v, t, largura, _clarear(cor), "//", unidade)
            vals += [v] if v is not None else []
        v, t = _valor(linha, x, atual)
        desenhou |= _barra(ax, i + (passo if anterior else 0), v, t, largura, cor, None, unidade)
        vals += [v] if v is not None else []
        var = _lado(linha, x).get("var_aa") if _lado(linha, x).get("status", "ok") == "ok" else None
        rot = _nome(comp, x)
        if anterior:
            rot += f"\nA/A: {fmt_var(var, _lado(linha, x).get('unidade_var') or '%')}"
        rotulos.append(rot)
    ax.set_xticks(range(len(LADOS)), rotulos)
    ax.set_xlim(-0.7, len(LADOS) - 0.3)
    ax.set_title(f"{titulo} ({unidade})" if unidade else titulo, loc="left")
    _ajustar_eixo(ax, vals)
    _formatar_eixo_y(ax, unidade)
    if not desenhou:
        _aviso_sem_dados(ax)
    return desenhou


def _legenda_periodos(fig, comp: dict, atual: str, anterior: str | None) -> None:
    alca = []
    for x in LADOS:
        if anterior:
            alca.append(Patch(facecolor=_clarear(_cor(comp, x)), hatch="//", edgecolor=_escurecer(_cor(comp, x)),
                              label=f"{_nome(comp, x)} {anterior}"))
        alca.append(Patch(facecolor=_cor(comp, x), label=f"{_nome(comp, x)} {atual}"))
    fig.legend(handles=alca, loc="upper left", ncol=len(alca), frameon=False, fontsize=11,
               bbox_to_anchor=(0.03, 0.915))


def _g_receita_ebitda(comp: dict) -> tuple:
    atual = comp.get("periodo") or ""
    anterior = periodo_anterior_aa(atual)
    rec, ebt = _linha(comp, "receita_liquida"), _linha(comp, _chave_ebitda(comp))
    fig, (ax1, ax2) = _figura(2)
    ok = _painel_aa(ax1, comp, rec, "Receita líquida", atual, anterior)
    ok |= _painel_aa(ax2, comp, ebt, _texto_criterio(comp), atual, anterior)
    _legenda_periodos(fig, comp, atual, anterior)
    rot = f"{atual} × {anterior} (A/A)" if anterior else atual
    titulo = f"Receita e {_texto_criterio(comp)} — {rot}"
    notas = [f"{_nome(comp, x)}: {_lado(l, x).get('obs')}" for l in (rec, ebt) for x in LADOS
             if _lado(l, x).get("obs") and _lado(l, x).get("status", "ok") != "ok"]
    return fig, titulo, notas, [rec, ebt], titulo, ok


MARGENS = (("margem_bruta", "Bruta"), ("margem_ebitda", "EBITDA"), ("margem_ebit", "EBIT"),
           ("margem_liquida", "Líquida"))


def _g_margens(comp: dict) -> tuple:
    atual = comp.get("periodo") or ""
    fig, (ax,) = _figura(1)
    linhas = [_linha(comp, c) for c, _ in MARGENS]
    largura = 0.36
    vals, desenhou = [], False
    for j, x in enumerate(LADOS):
        for i, linha in enumerate(linhas):
            v, t = _valor(linha, x, atual)
            desenhou |= _barra(ax, i + (j - 0.5) * largura, v, t, largura, _cor(comp, x), None, "%")
            vals += [v] if v is not None else []
    rotulos = []
    for (c, rotulo), linha in zip(MARGENS, linhas):
        if c == "margem_ebitda" and comp.get("criterio_ebitda"):
            rotulo = f"EBITDA {NOME_CRITERIO.get(comp['criterio_ebitda'], comp['criterio_ebitda'])}"
        rotulos.append(rotulo)
    ax.set_xticks(range(len(MARGENS)), rotulos)
    ax.set_xlim(-0.6, len(MARGENS) - 0.4)
    ax.set_title(f"Margens sobre a receita líquida, {atual} (%)", loc="left")
    _ajustar_eixo(ax, vals)
    _formatar_eixo_y(ax, "%")
    if not desenhou:
        _aviso_sem_dados(ax)
    fig.legend(handles=[Patch(facecolor=_cor(comp, x), label=_nome(comp, x)) for x in LADOS],
               loc="upper left", ncol=2, frameon=False, fontsize=11, bbox_to_anchor=(0.03, 0.915))
    titulo = f"Margens — {atual}"
    notas = [f"{_nome(comp, x)}, {r.lower()}: {_lado(l, x).get('obs')}"
             for (_, r), l in zip(MARGENS, linhas) for x in LADOS
             if _lado(l, x).get("obs") and _lado(l, x).get("status", "ok") != "ok"]
    return fig, titulo, notas, linhas, f"Margens bruta, EBITDA, EBIT e líquida, {atual}", desenhou


def _g_dl_ebitda(comp: dict) -> tuple:
    atual = comp.get("periodo") or ""
    calc, rep = _linha(comp, "dl_ebitda"), _linha(comp, "dl_ebitda_reportado")
    ebt = _linha(comp, _chave_ebitda(comp))
    fig, (ax,) = _figura(1)
    largura = 0.36 if rep else 0.5
    vals, desenhou, notas = [], False, []
    for i, x in enumerate(LADOS):
        cor = _cor(comp, x)
        v, t = _valor(calc, x, atual)
        desenhou |= _barra(ax, i - (largura / 2 if rep else 0), v, t, largura, cor, None, "x")
        vals += [v] if v is not None else []
        if rep:
            vr, tr = _valor(rep, x, atual)
            desenhou |= _barra(ax, i + largura / 2, vr, tr, largura, _clarear(cor), "//", "x")
            vals += [vr] if vr is not None else []
        ve, _ = _valor(ebt, x, atual)
        if (ve is not None and ve <= 0) or (v is not None and v < 0):
            notas.append(f"{_nome(comp, x)}: EBITDA ≤ 0, múltiplo sem leitura")
    if not rep:
        notas.append("reportado: N/D")
    ax.set_xticks(range(len(LADOS)), [_nome(comp, x) for x in LADOS])
    ax.set_xlim(-0.7, len(LADOS) - 0.3)
    crit = _texto_criterio(comp)
    ax.set_title(f"Dívida líquida / {crit} (x)", loc="left")
    _ajustar_eixo(ax, vals)
    _formatar_eixo_y(ax, "x")
    if not desenhou:
        _aviso_sem_dados(ax)
    alca = []
    for x in LADOS:
        alca.append(Patch(facecolor=_cor(comp, x), label=f"{_nome(comp, x)} calculado"))
        if rep:
            alca.append(Patch(facecolor=_clarear(_cor(comp, x)), hatch="//", edgecolor=_escurecer(_cor(comp, x)),
                              label=f"{_nome(comp, x)} reportado"))
    fig.legend(handles=alca, loc="upper left", ncol=len(alca), frameon=False, fontsize=11,
               bbox_to_anchor=(0.03, 0.915))
    for x in LADOS:
        obs = _lado(calc, x).get("obs")
        if obs:
            notas.append(f"{_nome(comp, x)}: {obs}")
    titulo = f"Alavancagem — DL/{crit}, {atual}"
    return fig, titulo, notas, [calc, rep, ebt], titulo, desenhou


def _g_volume_rpt(comp: dict) -> tuple:
    atual = comp.get("periodo") or ""
    anterior = periodo_anterior_aa(atual)
    vol, rpt = _linha(comp, "volume_vendas"), _linha(comp, "receita_por_t")
    fig, (ax1, ax2) = _figura(2)
    ok = _painel_aa(ax1, comp, vol, "Volume de vendas", atual, anterior)
    ok |= _painel_aa(ax2, comp, rpt, "Receita por tonelada", atual, anterior)
    _legenda_periodos(fig, comp, atual, anterior)
    rot = f"{atual} × {anterior} (A/A)" if anterior else atual
    titulo = f"Volume e receita por tonelada — {rot}"
    notas = [f"{_nome(comp, x)}: {_lado(l, x).get('obs')}" for l in (vol, rpt) for x in LADOS
             if _lado(l, x).get("obs") and _lado(l, x).get("status", "ok") != "ok"]
    return fig, titulo, notas, [vol, rpt], titulo, ok


def _tons(cor: str, n: int) -> list:
    if n <= 1:
        return [to_rgb(cor)]
    return [_clarear(cor, 0.65 * k / (n - 1)) if k else _escurecer(cor, 0.15) for k in range(n)]


def _g_mix(comp: dict) -> tuple:
    atual = comp.get("periodo") or ""
    segs = comp.get("segmentos") or {}
    fig, (ax,) = _figura(1)
    notas, desenhou = [], False
    ticks, rotulos = [], []
    topo = 100.0
    for i, x in enumerate(LADOS):
        lista = [s for s in segs.get(x) or [] if isinstance(s, dict)]
        cores = _tons(_cor(comp, x), len(lista))
        for j, (campo, nome_campo) in enumerate((("pct_receita", "Receita"), ("pct_ebitda", "EBITDA"))):
            pos = i * 2.6 + j * 1.1
            ticks.append(pos)
            rotulos.append(nome_campo)
            base, algum = 0.0, False
            for seg, cor in zip(lista, cores):
                v = seg.get(campo)
                nome = seg.get("rotulo") or seg.get("segmento") or "?"
                if v is None or isinstance(v, bool):
                    notas.append(f"{_nome(comp, x)}, {nome}: {nome_campo.lower()} N/D (fora da barra)")
                    continue
                if v < 0:
                    notas.append(f"{_nome(comp, x)}, {nome}: {nome_campo.lower()} {fmt_br(v, '%')} (negativo, fora da barra)")
                    continue
                ax.bar(pos, v, 0.9, bottom=base, color=cor, edgecolor="white", linewidth=1.2, zorder=2)
                if v >= 6:
                    lum = sum(to_rgb(cor)) / 3 if isinstance(cor, str) else sum(cor) / 3
                    ax.text(pos, base + v / 2, f"{nome}\n{fmt_br(v, '%')}", ha="center", va="center",
                            fontsize=10, color="white" if lum < 0.55 else COR_TEXTO)
                elif v > 0:
                    ax.annotate(f"{nome} {fmt_br(v, '%')}", (pos + 0.45, base + v / 2), xytext=(4, 0),
                                textcoords="offset points", va="center", fontsize=9, color=COR_TEXTO)
                base += v
                algum = True
            if not algum:
                ax.text(pos, 2, "N/D", ha="center", va="bottom", fontsize=12, fontweight="bold", color=COR_SUAVE,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#bbbbbb"))
            else:
                desenhou = True
                topo = max(topo, base)
                if abs(base - 100) > 0.5:
                    notas.append(f"{_nome(comp, x)}: {nome_campo.lower()} soma {fmt_br(base, '%')}")
    ax.set_xticks(ticks, rotulos)
    ax.set_xlim(-0.8, 2.6 * (len(LADOS) - 1) + 1.1 + 0.8)
    ax.set_ylim(0, topo * 1.05)
    ax.set_title(f"Participação de cada segmento na receita e no EBITDA, {atual} (%)", loc="left")
    _formatar_eixo_y(ax, "%")
    ax.grid(axis="y", color="#e5e5e5", zorder=0)
    if not desenhou:
        _aviso_sem_dados(ax)
    for i, x in enumerate(LADOS):
        ax.annotate(_nome(comp, x), (i * 2.6 + 0.55, 0), xycoords=("data", "axes fraction"), xytext=(0, -42),
                    textcoords="offset points", ha="center", va="top", fontsize=13, fontweight="bold",
                    color=_escurecer(_cor(comp, x), 0.2))
    fontes = {x: [] for x in LADOS}
    for x in LADOS:
        for s in segs.get(x) or []:
            for f in (s or {}).get("fontes") or []:
                if f not in fontes[x]:
                    fontes[x].append(f)
    titulo = f"Mix de segmentos — {atual}"
    return fig, titulo, notas, fontes, f"Participação de cada segmento na receita e no EBITDA, {atual}", desenhou


GRAFICOS = (
    ("receita_ebitda", _g_receita_ebitda),
    ("margens", _g_margens),
    ("dl_ebitda", _g_dl_ebitda),
    ("volume_rpt", _g_volume_rpt),
    ("mix_segmentos", _g_mix),
)


def gerar_graficos(comp: dict, pasta: Path) -> list[dict]:
    """Grava `pasta/graficos/<id>.png` (5 gráficos) e devolve as entradas de `comp["graficos"]`."""
    pasta = Path(pasta)
    entradas = []
    for gid, funcao in GRAFICOS:
        fig, titulo, notas, usadas, descricao, desenhou = funcao(comp)
        try:
            if isinstance(usadas, dict):
                fontes = usadas
            else:
                fontes = {x: _fontes(usadas, x) for x in LADOS}
            if not desenhou:
                notas = [AVISO_SEM_DADOS] + notas
            _finalizar(fig, titulo, _rodape(comp, fontes), notas)
        except Exception:
            plt.close(fig)
            raise
        arquivo = f"graficos/{gid}.png"
        _salvar(fig, pasta / arquivo)
        entradas.append({"id": gid, "arquivo": arquivo, "descricao": descricao, "fontes": fontes})
    return entradas


if __name__ == "__main__":  # uso rápido: python src/graficos.py comparativo.json pasta_saida
    import json

    if len(sys.argv) != 3:
        print("uso: python src/graficos.py <comparativo.json> <pasta_saida>", file=sys.stderr)
        raise SystemExit(1)
    dados = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for e in gerar_graficos(dados, Path(sys.argv[2])):
        print(e["arquivo"], "-", e["descricao"])
