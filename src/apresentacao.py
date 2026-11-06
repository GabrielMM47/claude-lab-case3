"""CASE-06 · Gerador da apresentação executiva (HTML 16:9, arquivo único).

    python src/apresentacao.py --comparativo saida/comparativo/<a>_x_<b>_<tri> \\
        [--narrativa narrativa/<a>_x_<b>_<tri>.json] [--metricas metricas] [--saida arquivo.html]

Entradas (contrato em docs/TAREFAS.md): comparativo.json + graficos/ (CASE-05), qualitativo da
apresentação institucional (CASE-03, opcional) e a narrativa com os títulos-mensagem (opcional;
sem ela, usa os insights automáticos do comparativo).

Regras:
- nenhum número é digitado aqui nem na narrativa. A narrativa usa placeholders
  ({a.margem_ebitda}, {b.receita_liquida.var_aa}, {a.nome}, {periodo}, {criterio_ebitda}) que o
  código resolve a partir do comparativo.json;
- todo slide tem rodapé com as fontes dos números que mostra (página = índice do PDF) e o aviso
  "Não constitui recomendação de investimento";
- narrativa reprovada no verificador não vira apresentação (sai com código 1).

Saída: um .html com CSS e imagens embutidos. Setas/PageUp/PageDown/Home/End navegam; imprimir
(Ctrl+P, paisagem, sem margens) gera o PDF com um slide por página.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AVISO = "Não constitui recomendação de investimento"
IDS_SLIDES = ["capa", "resumo", "perfil", "comparativo", "graficos", "setor", "destaques_riscos", "metodologia"]
DOCUMENTOS = {"itr": "ITR", "apresentacao": "Apresentação"}
TEMAS_PERFIL = ["perfil", "capacidade_footprint", "mercados_produtos", "estrategia"]
# linhas preferidas para a tabela do slide comparativo (as que existirem, até 8)
TABELA = ["receita_liquida", "ebitda_ajustado", "ebitda_contabil", "margem_ebitda", "lucro_liquido",
          "margem_liquida", "dl_ebitda", "roe", "roic"]
GRUPOS_SETOR = {"setor"}
EXTRA_SETOR = ["dl_ebitda"]
# Linhas contábeis que carregam os ajustes pontuais (impairment, venda de ativo...). O EBITDA
# ajustado os exclui; EBIT, lucro e EBITDA contábil não. Um alerta de efeito pontual da empresa
# distorce a variação A/A delas, mesmo que o comparativo só cite as linhas de EBITDA.
LINHAS_COM_PONTUAIS = ["ebitda_contabil", "margem_ebitda_contabil", "margem_ebit", "lucro_liquido",
                       "margem_liquida"]
# Sem indicador de margem/retorno que piorou (ou melhorou), o destaque cai para a variação A/A de
# uma linha financeira do trimestre: queda de receita é notícia, mesmo sem eleger vencedor.
LINHAS_DESTAQUE_ABSOLUTO = ["receita_liquida", "ebitda_ajustado", "ebitda_contabil", "lucro_liquido"]

RE_FONTE = re.compile(r"^(?P<doc>.+?) p\. ?(?P<pag>\d+)$")
RE_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
RE_PERIODO = re.compile(r"\b\d[TM]\d{2}\b")


# ---------------------------------------------------------------- formatação
def fmt_br(x: float, casas: int = 1) -> str:
    s = f"{abs(x):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if x < 0 else "") + s


def fmt_var(v: float | None, unidade_var: str | None) -> str | None:
    """+2,6 p.p. · -4,8% · +0,10x (sinal sempre explícito)."""
    if v is None:
        return None
    sinal = "+" if v > 0 else "-" if v < 0 else ""
    if unidade_var == "p.p.":
        return f"{sinal}{fmt_br(abs(v))} p.p."
    if unidade_var == "x":
        return f"{sinal}{fmt_br(abs(v), 2)}x"
    return f"{sinal}{fmt_br(abs(v))}%"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def periodos_validos(periodo: str) -> set[str]:
    """Rótulos que a narrativa pode citar: o trimestre, as bases A/A e T/T, acumulados e o 4T anterior."""
    m = re.fullmatch(r"(\d)T(\d{2})", periodo)
    if not m:
        return {periodo}
    n, ano = int(m.group(1)), int(m.group(2))
    tt = f"{n - 1}T{ano:02d}" if n > 1 else f"4T{ano - 1:02d}"
    return {periodo, f"{n}T{ano - 1:02d}", tt, f"{3 * n}M{ano:02d}", f"{3 * n}M{ano - 1:02d}", f"4T{ano - 1:02d}"}


# ---------------------------------------------------------------- fontes do rodapé
@dataclass
class Fontes:
    """Junta as fontes de um slide e escreve 'Empresa A — ITR p. 29, 71; Apresentação p. 12'."""
    paginas: dict = field(default_factory=dict)  # empresa -> documento -> {páginas}
    outras: dict = field(default_factory=dict)  # empresa -> {texto livre}

    def add(self, empresa: str | None, fontes) -> None:
        if isinstance(fontes, dict):  # {"a": [...], "b": [...]}
            for e, lista in fontes.items():
                self.add(e, lista)
            return
        for f in fontes or []:
            m = RE_FONTE.match(f.strip())
            if m:
                self.paginas.setdefault(empresa, {}).setdefault(m["doc"], set()).add(int(m["pag"]))
            else:
                self.outras.setdefault(empresa, set()).add(f.strip())

    def add_fato(self, empresa: str, fato: dict) -> None:
        doc = DOCUMENTOS.get(fato.get("documento"), fato.get("documento") or "?")
        self.add(empresa, [f"{doc} p.{fato['pagina']}"])

    def juntar(self, outra: Fontes) -> None:
        for e, docs in outra.paginas.items():
            for doc, pags in docs.items():
                self.paginas.setdefault(e, {}).setdefault(doc, set()).update(pags)
        for e, textos in outra.outras.items():
            self.outras.setdefault(e, set()).update(textos)

    def vazio(self) -> bool:
        return not self.paginas and not self.outras

    def texto(self, nomes: dict) -> str:
        partes = []
        for e in [k for k in ("a", "b") if k in self.paginas or k in self.outras] + \
                 [k for k in set(self.paginas) | set(self.outras) if k not in ("a", "b")]:
            itens = [f"{doc} p. {', '.join(map(str, sorted(pags)))}"
                     for doc, pags in sorted(self.paginas.get(e, {}).items())]
            itens += sorted(self.outras.get(e, set()))
            rotulo = nomes.get(e)
            partes.append(f"{rotulo} — {'; '.join(itens)}" if rotulo else "; ".join(itens))
        return " · ".join(partes)


# ---------------------------------------------------------------- dados de entrada
@dataclass
class Dados:
    comp: dict
    pasta: Path
    qualitativo: dict  # "a"/"b" -> lista de fatos
    fontes_total: Fontes = field(default_factory=Fontes)  # tudo o que os slides citaram

    @property
    def linhas(self) -> dict:
        return {linha["chave"]: linha for linha in self.comp["linhas"]}

    @property
    def nomes(self) -> dict:
        return {e: self.comp["empresas"][e]["nome"] for e in ("a", "b")}

    def qual(self, e: str, tema: str) -> list[dict]:
        return [f for f in self.qualitativo.get(e, []) if f.get("tema") == tema]

    def alertas(self, e: str) -> list[dict]:
        return [a for a in self.comp.get("alertas", []) if a.get("empresa") == e]


def carregar(pasta_comparativo: Path, pasta_metricas: Path | None) -> Dados:
    comp = json.loads((pasta_comparativo / "comparativo.json").read_text(encoding="utf-8"))
    qualitativo = {}
    if pasta_metricas:
        for e in ("a", "b"):
            arq = pasta_metricas / f"{comp['empresas'][e]['slug']}_{comp['periodo']}_apresentacao_qualitativo.json"
            if arq.exists():
                qualitativo[e] = json.loads(arq.read_text(encoding="utf-8"))
    return Dados(comp, pasta_comparativo, qualitativo)


# ---------------------------------------------------------------- narrativa: resolver e verificar
class ErroNarrativa(ValueError):
    pass


def resolver(texto: str, d: Dados, fontes: Fontes) -> str:
    """Troca os placeholders pelos valores do comparativo e registra as fontes usadas."""
    linhas, nomes = d.linhas, d.nomes

    def troca(m: re.Match) -> str:
        nome = m.group(1)
        partes = nome.split(".")
        if nome in ("periodo", "criterio_ebitda"):
            return str(d.comp[nome])
        if partes[0] not in ("a", "b") or len(partes) < 2:
            raise ErroNarrativa(f"{{{nome}}}: placeholder desconhecido")
        e = partes[0]
        if partes[1:] == ["nome"]:
            return nomes[e]
        linha = linhas.get(partes[1])
        if linha is None:
            raise ErroNarrativa(f"{{{nome}}}: chave '{partes[1]}' não existe no comparativo")
        lado = linha[e]
        if not lado.get("disponivel"):
            raise ErroNarrativa(f"{{{nome}}}: valor indisponível ({lado.get('texto')}: {lado.get('obs')})")
        if len(partes) == 2:
            valor = lado["texto"]
        elif len(partes) == 3 and partes[2] in ("var_aa", "var_tt"):
            valor = fmt_var(lado.get(partes[2]), lado.get("unidade_var"))
            if valor is None:
                raise ErroNarrativa(f"{{{nome}}}: variação indisponível ({lado.get('obs') or 'sem base'})")
        else:
            raise ErroNarrativa(f"{{{nome}}}: formato inválido (use {{a.chave}} ou {{a.chave.var_aa}})")
        fontes.add(e, lado.get("fontes"))
        return valor

    return RE_PLACEHOLDER.sub(troca, texto)


def textos_da_narrativa(narrativa: dict):
    for slide in narrativa.get("slides", []):
        for campo in ("titulo", "subtitulo"):
            if slide.get(campo):
                yield slide.get("id"), slide[campo]
        for bullet in slide.get("bullets", []):
            yield slide.get("id"), bullet


def verificar_narrativa(narrativa: dict, d: Dados) -> list[str]:
    """Problemas da narrativa. Lista vazia = pode virar apresentação."""
    problemas = []
    ids = [s.get("id") for s in narrativa.get("slides", [])]
    for sid in ids:
        if sid not in IDS_SLIDES:
            problemas.append(f"slide desconhecido: {sid!r} (válidos: {', '.join(IDS_SLIDES)})")
    for sid in {i for i in ids if ids.count(i) > 1}:
        problemas.append(f"slide repetido: {sid!r}")
    validos = periodos_validos(d.comp["periodo"]) | {l.get("periodo") for l in d.comp["linhas"] if l.get("periodo")}
    for sid, texto in textos_da_narrativa(narrativa):
        fora = RE_PLACEHOLDER.sub(" ", texto)
        for p in RE_PERIODO.findall(fora):
            if p not in validos:
                problemas.append(f"[{sid}] período {p} não pertence a esta comparação ({d.comp['periodo']})")
        if re.search(r"\d", RE_PERIODO.sub("", fora)):
            problemas.append(f"[{sid}] número escrito à mão (use placeholder): {texto!r}")
        try:
            resolver(texto, d, Fontes())
        except ErroNarrativa as erro:
            problemas.append(f"[{sid}] {erro}")
    return problemas


# ---------------------------------------------------------------- blocos de HTML
def img_grafico(d: Dados, gid: str, fontes: Fontes) -> str | None:
    g = next((g for g in d.comp.get("graficos", []) if g.get("id") == gid), None)
    if not g or not (d.pasta / g["arquivo"]).is_file():
        return None
    dados = base64.b64encode((d.pasta / g["arquivo"]).read_bytes()).decode("ascii")
    fontes.add(None, g.get("fontes"))  # {"a": [...], "b": [...]} ou lista sem empresa
    return f'<img src="data:image/png;base64,{dados}" alt="{esc(g.get("descricao", gid))}">'


def valor_html(lado: dict, mostrar_var: bool = True) -> str:
    if not lado.get("disponivel"):
        return (f'<span class="nd">{esc(lado.get("texto") or "N/D")}</span>'
                f'<span class="obs">{esc(lado.get("obs") or "")}</span>')
    partes = [f'<span class="v">{esc(lado["texto"])}</span>']
    if mostrar_var:
        variacoes = [f"{rot} {fmt_var(lado.get(k), lado.get('unidade_var'))}"
                     for k, rot in (("var_aa", "A/A"), ("var_tt", "T/T")) if lado.get(k) is not None]
        if variacoes:
            partes.append(f'<span class="var">{esc(" · ".join(variacoes))}</span>')
    if lado.get("obs"):  # motivo de variação omitida, base de cálculo, caixa líquido...
        partes.append(f'<span class="obs">{esc(lado["obs"])}</span>')
    return "".join(partes)


def rotulo_linha(linha: dict, periodo: str) -> str:
    extra = []
    if linha.get("periodo") and linha["periodo"] != periodo:
        extra.append(f"{linha['periodo']} anualizado" if "M" in linha["periodo"] else linha["periodo"])
    extra.append(linha["unidade"])
    return f'{esc(linha["nome"])}<span class="obs">{esc(" · ".join(extra))}</span>'


def lista(itens: list[str], classe: str = "") -> str:
    return f'<ul class="{classe}">' + "".join(f"<li>{i}</li>" for i in itens) + "</ul>"


def fontes_de_insight(ins: dict, d: Dados, fontes: Fontes) -> None:
    for chave in ins.get("chaves", []):
        linha = d.linhas.get(chave)
        if linha:
            for e in ("a", "b"):
                fontes.add(e, linha[e].get("fontes"))
    fontes.add(None, ins.get("fontes") or {})


# ---------------------------------------------------------------- slides
# Cada função recebe (dados, narrativa do slide, fontes) e devolve (título, subtítulo, corpo).
def slide_capa(d, n, fontes):
    a, b = d.comp["empresas"]["a"], d.comp["empresas"]["b"]
    insights = d.comp.get("insights", [])
    if n.get("titulo"):
        titulo = resolver(n["titulo"], d, fontes)
    elif insights:
        titulo = insights[0]["texto"]
        fontes_de_insight(insights[0], d, fontes)
    else:
        titulo = f"{a['nome']} × {b['nome']} no {d.comp['periodo']}"
    sub = resolver(n["subtitulo"], d, fontes) if n.get("subtitulo") else \
        f"Comparação de resultados do {d.comp['periodo']} para o comitê de investimentos"
    corpo = (f'<div class="capa"><span style="color:{esc(a["cor"])}">{esc(a["nome"])}'
             f' <small>{esc(a["ticker"])}</small></span><span class="x">×</span>'
             f'<span style="color:{esc(b["cor"])}">{esc(b["nome"])} <small>{esc(b["ticker"])}</small></span></div>'
             f'<p class="nota">Critério de EBITDA: {esc(d.comp["criterio_ebitda"])} para as duas empresas. '
             f'Fontes: ITRs e apresentações das empresas.</p>')
    return titulo, sub, corpo


def slide_resumo(d, n, fontes):
    titulo = resolver(n.get("titulo") or "Três coisas que o comitê precisa saber", d, fontes)
    def item(texto: str) -> str:  # "Rentabilidade: ..." vira rótulo + texto
        rot, sep, resto = texto.partition(": ")
        if sep and len(rot) <= 40:
            return f'<b class="rotulo">{esc(rot)}</b>{esc(resto)}'
        return esc(texto)

    if n.get("bullets"):
        bullets = [item(resolver(b, d, fontes)) for b in n["bullets"]]
    else:
        bullets = []
        for ins in d.comp.get("insights", [])[:3]:
            bullets.append(item(ins["texto"]))
            fontes_de_insight(ins, d, fontes)
    if not bullets:
        bullets = ['<span class="nd">Sem conclusões: o comparativo não trouxe insights.</span>']
    return titulo, None, lista(bullets, "grande")


def slide_perfil(d, n, fontes):
    titulo = resolver(n.get("titulo") or f"Quem são {d.nomes['a']} e {d.nomes['b']}", d, fontes)
    colunas = []
    for e in ("a", "b"):
        emp = d.comp["empresas"][e]
        itens = []
        for tema in TEMAS_PERFIL:
            for fato in d.qual(e, tema)[:1]:
                itens.append(esc(fato["resumo"]))
                fontes.add_fato(e, fato)
        segs = d.comp.get("segmentos", {}).get(e, [])
        if segs:
            mix = ", ".join(f"{s.get('rotulo') or s['segmento']} {fmt_br(s['pct_receita'], 0)}% da receita / "
                            f"{fmt_br(s['pct_ebitda'], 0)}% do EBITDA" for s in segs)
            itens.append(f"Segmentos: {esc(mix)}")
            for s in segs:
                fontes.add(e, s.get("fontes"))
        if not itens:
            itens = ['<span class="nd">Sem dados da apresentação institucional.</span>']
        colunas.append(f'<div class="empresa" style="--cor:{esc(emp["cor"])}"><h2>{esc(emp["nome"])} '
                       f'<small>{esc(emp["ticker"])}</small></h2>{lista(itens, "compacta")}</div>')
    corpo = f'<div class="duas">{"".join(colunas)}</div>'
    grafico = img_grafico(d, "mix_segmentos", fontes)
    if grafico:
        corpo += f'<div class="graf um">{grafico}</div>'
    return titulo, None, corpo


def slide_comparativo(d, n, fontes):
    linhas = d.linhas
    escolhidas = [linhas[c] for c in TABELA if c in linhas][:8]
    if not escolhidas:
        escolhidas = [l for l in d.comp["linhas"] if l.get("grupo") not in GRUPOS_SETOR][:8]
    a, b = d.comp["empresas"]["a"], d.comp["empresas"]["b"]
    titulo = resolver(n.get("titulo") or f"Comparativo do {d.comp['periodo']}", d, fontes)
    corpo = [(f'<table class="tabela"><thead><tr><th>Métrica</th>'
              f'<th style="--cor:{esc(a["cor"])}">{esc(a["nome"])}</th>'
              f'<th style="--cor:{esc(b["cor"])}">{esc(b["nome"])}</th><th>Fonte</th></tr></thead><tbody>')]
    for linha in escolhidas:
        celulas = []
        for e in ("a", "b"):
            venc = linha.get("vencedor") == e
            marca = '<span class="melhor">melhor</span>' if venc else ""
            cor = esc(d.comp["empresas"][e]["cor"])
            celulas.append(f'<td class="{"venc" if venc else ""}" style="--cor:{cor}">{valor_html(linha[e])}{marca}</td>')
            fontes.add(e, linha[e].get("fontes"))
        fonte_linha = Fontes()
        for e in ("a", "b"):
            fonte_linha.add(e, linha[e].get("fontes"))
        celulas.append(f'<td class="fonte">{esc(fonte_linha.texto({"a": a["nome"], "b": b["nome"]}))}</td>')
        corpo.append(f"<tr><td>{rotulo_linha(linha, d.comp['periodo'])}</td>{''.join(celulas)}</tr>")
    corpo.append("</tbody></table>")
    nota = (f'<p class="nota">EBITDA {esc(d.comp["criterio_ebitda"])} nas duas empresas. A/A = '
            f'{d.comp["periodo"]} × mesmo trimestre do ano anterior; T/T = contra o trimestre anterior. '
            f'"melhor" só onde há regra econômica clara.</p>')
    return titulo, None, "".join(corpo) + nota


def slide_graficos(d, n, fontes):
    titulo = resolver(n.get("titulo") or f"Receita, EBITDA e margens no {d.comp['periodo']}", d, fontes)
    imgs = [i for i in (img_grafico(d, gid, fontes) for gid in ("receita_ebitda", "margens")) if i]
    if not imgs:
        return titulo, None, '<p class="nd">Gráficos não encontrados no comparativo.</p>'
    return titulo, None, f'<div class="graf">{"".join(imgs)}</div>'


def slide_setor(d, n, fontes):
    titulo = resolver(n.get("titulo") or "Métricas de siderurgia", d, fontes)
    linhas = [l for l in d.comp["linhas"] if l.get("grupo") in GRUPOS_SETOR]
    linhas += [d.linhas[c] for c in EXTRA_SETOR if c in d.linhas and d.linhas[c] not in linhas]
    tiles = []
    for linha in linhas[:5]:
        lados = []
        for e in ("a", "b"):
            venc = " venc" if linha.get("vencedor") == e else ""
            lados.append(f'<div class="lado{venc}" style="--cor:{esc(d.comp["empresas"][e]["cor"])}">'
                         f'<span class="quem">{esc(d.nomes[e])}</span>{valor_html(linha[e])}</div>')
            fontes.add(e, linha[e].get("fontes"))
        tiles.append(f'<div class="tile"><div class="nome">{rotulo_linha(linha, d.comp["periodo"])}</div>'
                     f'{"".join(lados)}</div>')
    grafico = img_grafico(d, "volume_rpt", fontes)
    corpo = f'<div class="tiles" style="--n:{max(len(tiles), 1)}">{"".join(tiles)}</div>'
    if grafico:
        corpo += f'<div class="graf um">{grafico}</div>'
    return titulo, None, corpo


def destaques_numericos(d: Dados, e: str) -> tuple[str | None, str | None, Fontes]:
    """Melhor e pior variação A/A entre as linhas com direção definida (p.p. primeiro).

    Linhas afetadas por efeito pontual da empresa ficam de fora: a variação A/A delas engana e
    o próprio alerta aparece no slide. Afetadas = as que o alerta cita + as contábeis
    (LINHAS_COM_PONTUAIS), quando o alerta vale para esta comparação (cita alguma linha).
    Sem candidato num dos lados, usa a variação A/A de uma linha financeira do trimestre.
    """
    fontes = Fontes()
    distorcidas = set()
    for alerta in d.alertas(e):
        if alerta.get("tipo") == "efeito_pontual" and alerta.get("chaves"):
            distorcidas |= set(alerta["chaves"]) | set(LINHAS_COM_PONTUAIS)

    def tem_var(linha):
        lado = linha[e]
        return linha["chave"] not in distorcidas and lado.get("disponivel") and lado.get("var_aa") is not None

    cands = []
    for linha in d.comp["linhas"]:
        if linha.get("melhor") in ("maior", "menor") and tem_var(linha):
            lado = linha[e]
            score = lado["var_aa"] if linha["melhor"] == "maior" else -lado["var_aa"]
            cands.append((lado.get("unidade_var") != "p.p.", score, linha))
    absolutos = [(True, d.linhas[c][e]["var_aa"], d.linhas[c]) for c in LINHAS_DESTAQUE_ABSOLUTO
                 if c in d.linhas and d.linhas[c].get("periodo", d.comp["periodo"]) == d.comp["periodo"]
                 and tem_var(d.linhas[c])]

    def frase(item):
        _, _, linha = item
        lado = linha[e]
        fontes.add(e, lado.get("fontes"))
        return f"{linha['nome']}: {lado['texto']} ({fmt_var(lado['var_aa'], lado['unidade_var'])} A/A)"

    def escolher(sinal):
        for grupo in (cands, absolutos):
            achados = sorted([c for c in grupo if c[1] * sinal > 0], key=lambda c: (c[0], -sinal * c[1]))
            if achados:
                return frase(achados[0])
        return None

    return escolher(+1), escolher(-1), fontes


def slide_destaques_riscos(d, n, fontes):
    titulo = resolver(n.get("titulo") or "Destaques do trimestre e o que observar", d, fontes)
    colunas = []
    for e in ("a", "b"):
        emp = d.comp["empresas"][e]
        pos, neg, f_num = destaques_numericos(d, e)
        fontes.juntar(f_num)
        itens = [f'<b class="pos">+</b> {esc(pos or "Nenhum indicador comparável melhorou A/A")}',
                 f'<b class="neg">−</b> {esc(neg or "Nenhum indicador comparável piorou A/A")}']
        for tema, rotulo in (("destaques_trimestre", "Trimestre"), ("riscos", "Riscos"),
                             ("guidance_perspectivas", "O que observar")):
            for fato in d.qual(e, tema)[:1]:
                itens.append(f"<b>{rotulo}:</b> {esc(fato['resumo'])}")
                fontes.add_fato(e, fato)
        for alerta in d.alertas(e)[:2]:
            itens.append(f'<span class="alerta">{esc(alerta["texto"])}</span>')
            fontes.add(e, alerta.get("fontes"))
        colunas.append(f'<div class="empresa" style="--cor:{esc(emp["cor"])}"><h2>{esc(emp["nome"])}</h2>'
                       f'{lista(itens, "compacta")}</div>')
    return titulo, None, f'<div class="duas">{"".join(colunas)}</div>'


def slide_metodologia(d, n, fontes):
    titulo = resolver(n.get("titulo") or "Como chegamos aos números", d, fontes)
    periodo = d.comp["periodo"]
    todas = Fontes()  # o que os slides anteriores citaram + todas as linhas do comparativo
    todas.juntar(d.fontes_total)
    for linha in d.comp["linhas"]:
        for e in ("a", "b"):
            todas.add(e, linha[e].get("fontes"))
    acumulados = sorted({l["periodo"] for l in d.comp["linhas"] if l.get("periodo") not in (None, periodo)})
    nomes_acum = [l["nome"] for l in d.comp["linhas"] if l.get("periodo") in acumulados]
    ver = d.comp.get("verificacao")
    if ver:
        txt_ver = (f"Verificação automática: {ver['ok']} de {ver['total']} números conferidos no PDF "
                   f"(trecho, valor e página).")
    else:
        txt_ver = "Verificação automática ainda não rodou para este comparativo: números não conferidos."
    itens = [
        esc(f"EBITDA {d.comp['criterio_ebitda']}, o mesmo critério para as duas empresas. Números consolidados."),
        esc(f"A/A = {periodo} × mesmo trimestre do ano anterior; T/T = × trimestre anterior; "
            f"variação de percentuais em p.p."),
    ]
    if acumulados:
        itens.append(esc(f"{', '.join(nomes_acum)}: {', '.join(acumulados)} anualizado, sobre saldos médios."))
    itens += [
        f'<span class="{"" if ver else "nd"}">{esc(txt_ver)}</span>',
        esc("Páginas na numeração do PDF (a que o leitor de PDF mostra), não a impressa na folha."),
        esc(f"Fontes completas: {todas.texto(d.nomes)}"),
        f"<b>{esc(AVISO)}.</b> Trabalho acadêmico (Claude Lab · PUC-Rio).",
    ]
    fontes.juntar(todas)
    return titulo, None, lista(itens, "compacta")


SLIDES = {"capa": slide_capa, "resumo": slide_resumo, "perfil": slide_perfil, "comparativo": slide_comparativo,
          "graficos": slide_graficos, "setor": slide_setor, "destaques_riscos": slide_destaques_riscos,
          "metodologia": slide_metodologia}


# ---------------------------------------------------------------- página
# Design system "Comitê" (docs/DESIGN_SYSTEM.md): contenção; só números e as cores das empresas
# chamam atenção. Fonte Archivo embutida (SIL OFL 1.1, templates/fontes/OFL-Archivo.txt): arquivo
# único, abre offline. Sem o arquivo, cai na pilha de sistema.
_FONTE = RAIZ / "templates" / "fontes" / "archivo-latin.woff2"
FONTE_CSS = ("@font-face{font-family:'Archivo';font-style:normal;font-weight:100 900;font-stretch:62% 125%;"
             "font-display:block;src:url(data:font/woff2;base64,"
             + base64.b64encode(_FONTE.read_bytes()).decode() + ") format('woff2')}") if _FONTE.exists() else ""

CSS = """
:root{--superficie:#F4F6F8;--palco:#D9DEE3;--tinta:#1F2328;--sec:#59636E;--linha:#D8DEE4;--nd:#9A6700;
  --pos:#1A7F37;--neg:#CF222E;--t-xs:12px;--t-s:15px;--t-m:18px;--t-l:23px;--t-xl:29px;--t-capa:44px}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--palco);color:var(--tinta);
  font-family:Archivo,"Helvetica Neue",Arial,sans-serif;font-variant-numeric:tabular-nums;
  -webkit-font-smoothing:antialiased}
#deck{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;overflow:hidden}
.slide{width:1280px;height:720px;flex:none;background:var(--superficie);display:none;flex-direction:column;
  padding:52px 64px 0;position:absolute}
.slide.ativo{display:flex}
.slide h1{font-size:var(--t-xl);line-height:1.2;margin:0 0 6px;font-weight:600;max-width:1080px}
.slide .sub{color:var(--sec);font-size:var(--t-m);line-height:1.4;margin:0;max-width:900px}
.corpo{flex:1;min-height:0;display:flex;flex-direction:column;gap:16px;font-size:var(--t-m);padding-top:22px}
footer{display:flex;gap:24px;align-items:flex-end;border-top:1px solid var(--linha);
  padding:10px 0 14px;font-size:11px;line-height:1.4;color:var(--sec)}
footer .fontes{flex:1}
footer .aviso{white-space:nowrap}
ul{margin:0;padding-left:1.1em}
li{margin:0 0 .55em;line-height:1.45}
li::marker{color:var(--sec)}
#resumo .corpo{justify-content:center;padding-bottom:40px}
ul.grande{font-size:var(--t-l);display:grid;grid-template-columns:repeat(3,1fr);gap:44px;padding:0;
  list-style:none}
ul.grande li{margin:0;line-height:1.4;border-top:2px solid var(--tinta);padding-top:18px}
ul.grande .rotulo{display:block;font-size:var(--t-xl);font-weight:600;line-height:1.15;margin-bottom:14px}
ul.compacta{font-size:var(--t-s)}
#capa h1{font-size:52px;line-height:1.08;max-width:1150px;margin-top:80px}
#capa .sub{font-size:var(--t-l);margin-top:18px}
.capa{display:flex;gap:28px;align-items:baseline;font-size:48px;font-weight:600;margin-top:auto;
  padding-top:22px;border-top:1px solid var(--linha)}
.capa small{font-size:var(--t-m);color:var(--sec);font-weight:400;margin-left:6px}
.capa .x{color:var(--sec);font-weight:400}
.nota{font-size:var(--t-xs);color:var(--sec);margin:0 0 18px}
.duas{display:grid;grid-template-columns:1fr 1fr;gap:56px;min-height:0}
.empresa h2{font-size:var(--t-m);font-weight:600;margin:0 0 12px;color:var(--cor)}
.empresa h2 small{font-size:var(--t-xs);color:var(--sec);font-weight:400}
.tabela{width:100%;border-collapse:collapse;font-size:var(--t-s)}
.tabela th{text-align:left;font-size:var(--t-xs);color:var(--sec);font-weight:400;padding:4px 12px 6px;
  border-bottom:1px solid var(--tinta)}
.tabela th[style]{color:var(--cor);font-size:var(--t-s);font-weight:600}
.tabela td{padding:6px 12px;border-bottom:1px solid var(--linha);vertical-align:top}
.tabela td.venc .v{font-weight:600}
.tabela td.fonte{font-size:11px;color:var(--sec);max-width:240px}
.v{display:inline}
.var,.obs{display:block;font-size:var(--t-xs);color:var(--sec);font-weight:400}
.nd{color:var(--nd)}
.melhor{font-size:var(--t-xs);color:var(--cor);margin-left:6px;font-weight:600}
.graf{flex:1;min-height:0;display:flex;gap:24px;justify-content:center;align-items:center}
.graf img{max-width:50%;max-height:100%;object-fit:contain;background:#fff;border:1px solid var(--linha)}
.graf.um img{max-width:100%}
.tiles{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:32px}
.tile{font-size:var(--t-s)}
.tile .nome{font-size:var(--t-s);font-weight:600;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--linha)}
.tile .lado{padding:4px 0;margin-top:4px}
.tile .lado.venc .v{font-weight:600}
.tile .quem{display:block;font-size:var(--t-xs);color:var(--cor);font-weight:600}
.pos{color:var(--pos)}.neg{color:var(--neg)}
.alerta{display:block;font-size:var(--t-s);color:var(--nd)}
#destaques_riscos ul.compacta{font-size:var(--t-m)}
#metodologia ul.compacta{font-size:var(--t-m);columns:2;column-gap:56px}
#metodologia li{break-inside:avoid}
.alerta::before{content:"Atenção: ";font-weight:600}
#nav{position:fixed;right:16px;bottom:10px;color:var(--sec);font:12px Archivo,system-ui,sans-serif}
@media print{
  @page{size:1280px 720px;margin:0}
  html,body{background:#fff;height:auto}
  #deck{position:static;display:block}
  .slide{display:flex!important;position:relative;transform:none!important;break-after:page}
  #nav{display:none}
}
"""

JS = """
const s=[...document.querySelectorAll('.slide')];let i=0;
function escala(){const k=Math.min(innerWidth/1280,innerHeight/720)*0.97;s.forEach(x=>x.style.transform='scale('+k+')')}
function ir(n){i=Math.max(0,Math.min(s.length-1,n));s.forEach((x,j)=>x.classList.toggle('ativo',j===i));
  document.getElementById('pos').textContent=(i+1)+' / '+s.length;history.replaceState(null,'','#'+(i+1))}
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key))ir(i+1);
  else if(['ArrowLeft','PageUp'].includes(e.key))ir(i-1);else if(e.key==='Home')ir(0);
  else if(e.key==='End')ir(s.length-1)});
addEventListener('resize',escala);escala();ir((parseInt(location.hash.slice(1))||1)-1);
"""


def gerar_html(d: Dados, narrativa: dict | None = None) -> str:
    por_id = {s["id"]: s for s in (narrativa or {}).get("slides", [])}
    secoes = []
    for num, sid in enumerate(IDS_SLIDES, 1):
        fontes = Fontes()
        titulo, sub, corpo = SLIDES[sid](d, por_id.get(sid, {}), fontes)
        d.fontes_total.juntar(fontes)
        txt_fontes = fontes.texto(d.nomes)
        rodape = (f'<span class="fontes">{"Fontes: " + esc(txt_fontes) + " · páginas na numeração do PDF" if txt_fontes else ""}</span>'
                  f'<span class="aviso">{esc(AVISO)}</span><span class="num">{num}/{len(IDS_SLIDES)}</span>')
        secoes.append(f'<section class="slide" id="{sid}" data-fontes="{"sim" if txt_fontes else "nao"}">'
                      f'<h1>{esc(titulo)}</h1>{f"<p class=sub>{esc(sub)}</p>" if sub else ""}'
                      f'<div class="corpo">{corpo}</div><footer>{rodape}</footer></section>')
    a, b = d.nomes["a"], d.nomes["b"]
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(a)} × {esc(b)} · {esc(d.comp["periodo"])}</title><style>{FONTE_CSS}{CSS}</style></head>'
            f'<body><main id="deck">{"".join(secoes)}</main>'
            f'<div id="nav">← → navegar · <span id="pos"></span></div><script>{JS}</script></body></html>\n')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comparativo", required=True, type=Path, help="pasta com comparativo.json e graficos/")
    ap.add_argument("--narrativa", type=Path, help="JSON com títulos e bullets (placeholders)")
    ap.add_argument("--metricas", type=Path, default=RAIZ / "metricas", help="pasta dos *_apresentacao_qualitativo.json")
    ap.add_argument("--saida", type=Path, help="padrão: saida/apresentacao/<a>_x_<b>_<tri>.html")
    a = ap.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):  # console do Windows (cp1252) não quebra com acento
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(errors="replace")

    d = carregar(a.comparativo, a.metricas)
    narrativa = None
    if a.narrativa:
        narrativa = json.loads(a.narrativa.read_text(encoding="utf-8"))
        problemas = verificar_narrativa(narrativa, d)
        if problemas:
            print("Narrativa reprovada; apresentação NÃO gerada:", file=sys.stderr)
            for p in problemas:
                print(f"  - {p}", file=sys.stderr)
            return 1
    for e in ("a", "b"):
        if e not in d.qualitativo:
            print(f"aviso: sem qualitativo de {d.nomes[e]} em {a.metricas} (perfil e riscos ficam incompletos)",
                  file=sys.stderr)

    emp = d.comp["empresas"]
    saida = a.saida or RAIZ / "saida" / "apresentacao" / f"{emp['a']['slug']}_x_{emp['b']['slug']}_{d.comp['periodo']}.html"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(gerar_html(d, narrativa), encoding="utf-8")
    print(f"{len(IDS_SLIDES)} slides -> {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
