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
# "O que observar" no slide de destaques: o primeiro destes temas qualitativos que a empresa tiver.
# "riscos" fica de fora: nas apresentações é texto padrão (governança, previsões); os riscos que
# importam são os alertas do comparativo (efeito pontual, divergência), que aparecem no slide.
TEMAS_OBSERVAR = ["guidance_perspectivas", "capex_investimentos"]
# linhas preferidas para a tabela do slide comparativo (as que existirem, até 8). Fluxo de caixa
# livre entra no lugar da margem líquida, que repete o lucro; margem líquida fica de reserva.
TABELA = ["receita_liquida", "ebitda_ajustado", "ebitda_contabil", "margem_ebitda", "lucro_liquido",
          "fcl", "dl_ebitda", "roe", "roic", "margem_liquida"]
GRUPOS_SETOR = {"setor"}
# slide "setor": caixa e balanço (comparáveis nas duas) antes das métricas por tonelada
LINHAS_CAIXA = ["fco", "fcl", "capex_receita", "divida_liquida"]
GRAFICOS_SETOR = ["dl_ebitda", "volume_rpt"]  # o primeiro que existir
# Só os indicadores de rentabilidade são anualizados (× 4/3, sobre saldos médios); os de caixa
# no período acumulado (9M26) são a soma dos trimestres, sem anualizar (src/indicadores.py).
GRUPOS_ANUALIZADOS = {"rentabilidade"}
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
    for slide in narrativa.get("slides", []):  # "destaques": par de números de cada bullet do resumo
        for ref in slide.get("destaques") or []:
            chave, _, var = (ref or "").partition(".")
            if chave not in d.linhas or var not in ("", "var_aa", "var_tt"):
                problemas.append(f"[{slide.get('id')}] destaque inválido: {ref!r} (use 'chave' ou 'chave.var_aa')")
    return problemas


# ---------------------------------------------------------------- blocos de HTML
SOBRESCRITOS = "¹²³⁴⁵⁶⁷⁸⁹"


class Notas:
    """Observações longas (base de cálculo, motivo de N/D) viram notas numeradas no pé do slide."""

    def __init__(self) -> None:
        self.textos: list[str] = []

    def marca(self, texto: str | None) -> str:
        if not texto:
            return ""
        if texto not in self.textos:
            self.textos.append(texto)
        i = self.textos.index(texto)
        return f"<sup>{SOBRESCRITOS[i] if i < len(SOBRESCRITOS) else i + 1}</sup>"

    def html(self, prefixo: str = "") -> str:
        itens = [f"{SOBRESCRITOS[i] if i < len(SOBRESCRITOS) else i + 1} {esc(t)}." for i, t in enumerate(self.textos)]
        corpo = " ".join(x for x in [prefixo] + itens if x)
        return f'<p class="nota">{corpo}</p>' if corpo else ""


def img_grafico(d: Dados, gid: str, fontes: Fontes) -> str | None:
    g = next((g for g in d.comp.get("graficos", []) if g.get("id") == gid), None)
    if not g or not (d.pasta / g["arquivo"]).is_file():
        return None
    dados = base64.b64encode((d.pasta / g["arquivo"]).read_bytes()).decode("ascii")
    fontes.add(None, g.get("fontes"))  # {"a": [...], "b": [...]} ou lista sem empresa
    return f'<img src="data:image/png;base64,{dados}" alt="{esc(g.get("descricao", gid))}">'


def texto_var(lado: dict) -> str:
    return " · ".join(f"{rot} {fmt_var(lado.get(k), lado.get('unidade_var'))}"
                      for k, rot in (("var_aa", "A/A"), ("var_tt", "T/T")) if lado.get(k) is not None)


def periodo_da_linha(linha: dict, periodo: str) -> str | None:
    """'9M26 anualizado' (ROE/ROA/ROIC) ou '9M26 acumulado' (fluxos de caixa); None se for o trimestre."""
    p = linha.get("periodo")
    if not p or p == periodo:
        return None
    if "M" in p:
        return f"{p} anualizado" if linha.get("grupo") in GRUPOS_ANUALIZADOS else f"{p} acumulado"
    return p


def rotulo_linha(linha: dict, periodo: str) -> str:
    extra = [x for x in (periodo_da_linha(linha, periodo), linha["unidade"]) if x]
    return f'{esc(linha["nome"])}<span class="obs">{esc(" · ".join(extra))}</span>'


def maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def lista(itens: list[str], classe: str = "") -> str:
    return f'<ul class="{classe}">' + "".join(f"<li>{i}</li>" for i in itens) + "</ul>"


def tarja(emp: dict, extra: str = "") -> str:
    """Faixa na cor da empresa: a identidade visual do design system 'Tarja'."""
    tk = f'<small>{esc(emp["ticker"])}</small>' if emp.get("ticker") else ""
    return f'<div class="tarja" style="--cor:{esc(emp["cor"])}"><b>{esc(emp["nome"])}</b>{tk}{extra}</div>'


def tabela(d: Dados, linhas: list[dict], fontes: Fontes, notas: Notas, classe: str = "") -> str:
    """Métrica × empresas. Cada número leva a página dele (numeração do PDF) logo abaixo."""
    emp = d.comp["empresas"]
    cab = ""
    for e in ("a", "b"):
        tk = f"<small>{esc(emp[e]['ticker'])}</small>" if emp[e].get("ticker") else ""
        cab += f'<th class="emp" style="--cor:{esc(emp[e]["cor"])}">{esc(emp[e]["nome"])}{tk}</th>'

    corpo = []
    for linha in linhas:
        celulas = []
        for e in ("a", "b"):
            lado = linha[e]
            fontes.add(e, lado.get("fontes"))
            so_esta = Fontes()
            so_esta.add(e, lado.get("fontes"))
            pag = so_esta.texto({})
            venc = linha.get("vencedor") == e
            if lado.get("disponivel"):
                valor = f'<span class="v">{esc(lado["texto"])}{notas.marca(lado.get("obs"))}</span>'
                var = texto_var(lado)
            else:
                valor = (f'<span class="v nd">{esc(lado.get("texto") or "N/D")}'
                         f'{notas.marca(lado.get("obs"))}</span>')
                var = ""
            meta = " · ".join(x for x in (esc(var), esc(pag)) if x)
            celulas.append(f'<td class="{"venc" if venc else ""}" style="--cor:{esc(emp[e]["cor"])}">'
                           f'{valor}<span class="var">{meta or "&nbsp;"}</span></td>')
        corpo.append(f'<tr><th scope="row">{rotulo_linha(linha, d.comp["periodo"])}</th>{"".join(celulas)}</tr>')
    return (f'<table class="tabela {classe}"><colgroup><col class="c-metrica"><col><col></colgroup><thead><tr><th></th>{cab}</tr></thead>'
            f'<tbody>{"".join(corpo)}</tbody></table>')


def fontes_de_insight(ins: dict, d: Dados, fontes: Fontes) -> None:
    for chave in ins.get("chaves", []):
        linha = d.linhas.get(chave)
        if linha:
            for e in ("a", "b"):
                fontes.add(e, linha[e].get("fontes"))
    fontes.add(None, ins.get("fontes") or {})


def par_de_numeros(d: Dados, ref: str | None, fontes: Fontes) -> str:
    """'margem_ebitda' ou 'receita_liquida.var_aa' -> o número de cada empresa lado a lado, na cor dela."""
    if not ref:
        return ""
    chave, _, var = ref.partition(".")
    linha = d.linhas.get(chave)
    if not linha:
        return ""
    valores = []
    for e in ("a", "b"):
        lado = linha[e]
        if not lado.get("disponivel"):
            return ""
        txt = fmt_var(lado.get(var), lado.get("unidade_var")) if var else lado["texto"]
        if txt is None:
            return ""
        fontes.add(e, lado.get("fontes"))
        tam = " longo" if len(txt) > 8 else ""  # "R$ 2.408,2 mi" não cabe no corpo grande
        valores.append(f'<span class="campo{tam}" style="--cor:{esc(d.comp["empresas"][e]["cor"])}">'
                       f'<small>{esc(d.nomes[e])}</small><b>{esc(txt)}</b></span>')
    rot = linha["nome"] + {"var_aa": ", A/A", "var_tt": ", T/T"}.get(var, "")
    per = periodo_da_linha(linha, d.comp["periodo"])
    rot += f" ({per})" if per else ""
    return f'<div class="par">{"".join(valores)}</div><p class="par-rot">{esc(rot)}</p>'


# ---------------------------------------------------------------- slides
# Cada função recebe (dados, narrativa do slide, fontes) e devolve (título, subtítulo, corpo).
def slide_capa(d, n, fontes):
    insights = d.comp.get("insights", [])
    if n.get("titulo"):
        titulo = resolver(n["titulo"], d, fontes)
    elif insights:
        titulo = insights[0]["texto"]
        fontes_de_insight(insights[0], d, fontes)
    else:
        titulo = f"{d.nomes['a']} × {d.nomes['b']} no {d.comp['periodo']}"
    sub = resolver(n["subtitulo"], d, fontes) if n.get("subtitulo") else \
        f"Comparação de resultados do {d.comp['periodo']} para o comitê de investimentos"
    margem = d.linhas.get("margem_ebitda")
    campos = []
    for e in ("a", "b"):
        emp = d.comp["empresas"][e]
        destaque = ""
        if margem and margem[e].get("disponivel"):
            fontes.add(e, margem[e].get("fontes"))
            destaque = (f'<span class="mg">{esc(margem[e]["texto"])}'
                        f'<small>{esc(margem["nome"].lower().replace("ebitda", "EBITDA"))}, {esc(d.comp["periodo"])}</small></span>')
        tk = f'<span class="tk">{esc(emp["ticker"])}</span>' if emp.get("ticker") else ""
        campos.append(f'<div class="campo" style="--cor:{esc(emp["cor"])}"><b>{esc(emp["nome"])}</b>{tk}{destaque}</div>')
    corpo = (f'<div class="campos">{"".join(campos)}</div>'
             f'<p class="nota">EBITDA {esc(d.comp["criterio_ebitda"])} para as duas empresas; números consolidados.</p>')
    return titulo, sub, corpo


def slide_resumo(d, n, fontes):
    titulo = resolver(n.get("titulo") or "Três coisas que o comitê precisa saber", d, fontes)
    blocos = []  # (texto já resolvido, referência do par de números)
    if n.get("bullets"):
        refs = n.get("destaques") or []
        for i, b in enumerate(n["bullets"]):
            blocos.append((resolver(b, d, fontes), refs[i] if i < len(refs) else None))
    else:
        for ins in d.comp.get("insights", [])[:3]:
            fontes_de_insight(ins, d, fontes)
            blocos.append((ins["texto"], (ins.get("chaves") or [None])[0]))
    if not blocos:
        return titulo, None, '<p class="nd">Sem conclusões: o comparativo não trouxe insights.</p>'
    html_blocos = []
    for texto, ref in blocos:
        rot, sep, resto = texto.partition(": ")
        if not (sep and len(rot) <= 40):
            rot, resto = "", texto
        html_blocos.append(f'<div class="bloco">{f"<h2>{esc(rot)}</h2>" if rot else ""}'
                           f'{par_de_numeros(d, ref, fontes)}<p>{esc(maiuscula(resto))}</p></div>')
    return titulo, None, f'<div class="blocos">{"".join(html_blocos)}</div>'


def slide_perfil(d, n, fontes):
    titulo = resolver(n.get("titulo") or f"Quem são {d.nomes['a']} e {d.nomes['b']}", d, fontes)
    colunas = []
    for e in ("a", "b"):
        emp = d.comp["empresas"][e]
        itens = []
        for fato in d.qual(e, "perfil")[:1]:  # uma frase por empresa; o resto é texto institucional
            itens.append(f"<p>{esc(fato['resumo'])}</p>")
            fontes.add_fato(e, fato)
        segs = d.comp.get("segmentos", {}).get(e, [])
        if segs:
            mix = ", ".join(f"{s.get('rotulo') or s['segmento']} {fmt_br(s['pct_receita'], 0)}% da receita / "
                            f"{fmt_br(s['pct_ebitda'], 0)}% do EBITDA" for s in segs)
            itens.append(f'<p class="segs">Segmentos: {esc(mix)}</p>')
            for s in segs:
                fontes.add(e, s.get("fontes"))
        if not itens:
            itens = ['<p class="nd">Sem dados da apresentação institucional.</p>']
        colunas.append(f'<div class="empresa">{tarja(emp)}{"".join(itens)}</div>')
    grafico = img_grafico(d, "mix_segmentos", fontes)
    lado = f'<div class="graf">{grafico}</div>' if grafico else ""
    return titulo, None, f'<div class="perfil"><div class="pilha">{"".join(colunas)}</div>{lado}</div>'


def slide_comparativo(d, n, fontes):
    linhas = d.linhas
    escolhidas = [linhas[c] for c in TABELA if c in linhas][:8]
    if not escolhidas:
        escolhidas = [l for l in d.comp["linhas"] if l.get("grupo") not in GRUPOS_SETOR][:8]
    titulo = resolver(n.get("titulo") or f"Comparativo do {d.comp['periodo']}", d, fontes)
    notas = Notas()
    corpo = tabela(d, escolhidas, fontes, notas)
    legenda = (f'<span class="marca"></span> melhor no indicador, só onde há regra econômica clara. '
               f'EBITDA {esc(d.comp["criterio_ebitda"])} nas duas. A/A = {esc(d.comp["periodo"])} × mesmo '
               f'trimestre do ano anterior; T/T = × trimestre anterior.')
    return titulo, None, corpo + notas.html(legenda)


def slide_graficos(d, n, fontes):
    titulo = resolver(n.get("titulo") or f"Receita, EBITDA e margens no {d.comp['periodo']}", d, fontes)
    imgs = [i for i in (img_grafico(d, gid, fontes) for gid in ("receita_ebitda", "margens")) if i]
    if not imgs:
        return titulo, None, '<p class="nd">Gráficos não encontrados no comparativo.</p>'
    return titulo, None, f'<div class="graf dois">{"".join(imgs)}</div>'


def slide_setor(d, n, fontes):
    """Caixa e balanço (comparáveis) + métricas por tonelada (com o motivo quando não comparáveis)."""
    titulo = resolver(n.get("titulo") or "Caixa, balanço e métricas por tonelada", d, fontes)
    notas = Notas()
    caixa = [d.linhas[c] for c in LINHAS_CAIXA if c in d.linhas]
    por_t = [l for l in d.comp["linhas"] if l.get("grupo") in GRUPOS_SETOR]
    partes = []
    if caixa:
        partes.append(tabela(d, caixa, fontes, notas, "compacta"))
    if por_t:
        partes.append('<h2 class="secao">Por tonelada</h2>' + tabela(d, por_t, fontes, notas, "compacta sem-cab"))
    if not partes:
        partes.append('<p class="nd">Sem métricas de caixa ou por tonelada no comparativo.</p>')
    grafico = next((g for g in (img_grafico(d, gid, fontes) for gid in GRAFICOS_SETOR) if g), None)
    lado = f'<div class="graf">{grafico}</div>' if grafico else ""
    return titulo, None, (f'<div class="setor"><div class="pilha">{"".join(partes)}</div>{lado}</div>'
                          + notas.html())


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
        linhas = [("pos", "+", esc(pos or "Nenhum indicador comparável melhorou A/A")),
                  ("neg", "−", esc(neg or "Nenhum indicador comparável piorou A/A"))]
        for tema in TEMAS_OBSERVAR:  # o primeiro tema que a empresa tiver
            fato = next(iter(d.qual(e, tema)), None)
            if fato:
                linhas.append(("obs", "Observar", esc(fato["resumo"])))
                fontes.add_fato(e, fato)
                break
        sem_dado = []
        for alerta in d.alertas(e):
            if alerta.get("tipo") == "indisponivel":  # vários N/D viram uma linha só
                sem_dado += [d.linhas[c]["nome"] for c in alerta.get("chaves", []) if c in d.linhas]
            else:
                linhas.append(("alerta", "Atenção", esc(maiuscula(alerta["texto"]))))
            fontes.add(e, alerta.get("fontes"))
        if sem_dado:
            linhas.append(("alerta", "Sem dado", esc(", ".join(dict.fromkeys(sem_dado)))))
        itens = "".join(f'<div class="item {c}"><b>{r}</b><span>{t}</span></div>' for c, r, t in linhas)
        colunas.append(f'<div class="empresa">{tarja(emp)}{itens}</div>')
    return titulo, None, f'<div class="duas">{"".join(colunas)}</div>'


def slide_metodologia(d, n, fontes):
    titulo = resolver(n.get("titulo") or "Como chegamos aos números", d, fontes)
    periodo = d.comp["periodo"]
    todas = Fontes()  # o que os slides anteriores citaram + todas as linhas do comparativo
    todas.juntar(d.fontes_total)
    for linha in d.comp["linhas"]:
        for e in ("a", "b"):
            todas.add(e, linha[e].get("fontes"))
    acumulados = {}
    for l in d.comp["linhas"]:
        rot = periodo_da_linha(l, periodo)
        if rot:
            acumulados.setdefault(rot, []).append(l["nome"])
    ver = d.comp.get("verificacao")
    if ver:
        num_ver = f'<p class="grande">{esc(ver["ok"])} de {esc(ver["total"])}</p>'
        txt_ver = ("números conferidos automaticamente no PDF (trecho, valor e página); "
                   f"{ver.get('erro', 0)} com erro.")
    else:
        num_ver = ""
        txt_ver = "Verificação automática ainda não rodou para este comparativo: números não conferidos."
    periodos = [f"A/A = {periodo} × mesmo trimestre do ano anterior; T/T = × trimestre anterior; "
                f"percentuais variam em p.p."]
    periodos += [f"{', '.join(nomes)}: {rot}" + (", sobre saldos médios" if "anualizado" in rot else "") + "."
                 for rot, nomes in acumulados.items()]
    blocos = [
        ("Critério", [f"EBITDA {d.comp['criterio_ebitda']}, o mesmo para as duas empresas.",
                      "Números consolidados, nunca os da controladora."]),
        ("Períodos", periodos),
        ("Verificação", [txt_ver]),
        ("Fontes", [f"{todas.texto(d.nomes)}.",
                    "Páginas na numeração do PDF (a que o leitor de PDF mostra), não a impressa na folha."]),
    ]
    html_blocos = []
    for nome, textos in blocos:
        extra = num_ver if nome == "Verificação" else ""
        html_blocos.append(f'<div class="bloco"><h2>{nome}</h2>{extra}'
                           + "".join(f"<p>{esc(t)}</p>" for t in textos) + "</div>")
    fontes.juntar(todas)
    aviso = f'<p class="nota"><b>{esc(AVISO)}.</b> Trabalho acadêmico (Claude Lab · PUC-Rio).</p>'
    return titulo, None, f'<div class="quatro">{"".join(html_blocos)}</div>{aviso}'


SLIDES = {"capa": slide_capa, "resumo": slide_resumo, "perfil": slide_perfil, "comparativo": slide_comparativo,
          "graficos": slide_graficos, "setor": slide_setor, "destaques_riscos": slide_destaques_riscos,
          "metodologia": slide_metodologia}


# ---------------------------------------------------------------- página
# Design system "Tarja" (docs/DESIGN_SYSTEM.md): a cor de cada empresa ocupa faixas inteiras
# (capa, cabeçalhos, colunas); o resto é cinza-concreto e tinta. Títulos em Archivo condensada.
# Fonte embutida (SIL OFL 1.1, templates/fontes/OFL-Archivo.txt): arquivo único, abre offline.
_FONTE = RAIZ / "templates" / "fontes" / "archivo-latin.woff2"
FONTE_CSS = ("@font-face{font-family:'Archivo';font-style:normal;font-weight:100 900;font-stretch:62% 125%;"
             "font-display:block;src:url(data:font/woff2;base64,"
             + base64.b64encode(_FONTE.read_bytes()).decode() + ") format('woff2')}") if _FONTE.exists() else ""

CSS = """
:root{--superficie:#E7EAEC;--palco:#B9C0C6;--tinta:#161B21;--sec:#56616C;--linha:#C9D0D6;--faixa:#DDE1E4;
  --nd:#8A5A00;--pos:#1A7F37;--neg:#C4262E;--t-xs:12px;--t-s:15px;--t-m:18px;--t-l:22px;--t-xl:36px}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--palco);color:var(--tinta);
  font-family:Archivo,"Helvetica Neue",Arial,sans-serif;font-variant-numeric:tabular-nums lining-nums;
  -webkit-font-smoothing:antialiased}
#deck{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;overflow:hidden}
.slide{width:1280px;height:720px;flex:none;background:var(--superficie);display:none;flex-direction:column;
  padding:48px 64px 0;position:absolute;overflow:hidden}
.slide.ativo{display:flex}
.slide h1{font-size:var(--t-xl);line-height:1.06;margin:0;font-weight:700;font-stretch:75%;max-width:1150px;
  text-wrap:balance}
.slide .sub{color:var(--sec);font-size:var(--t-m);line-height:1.4;margin:10px 0 0;max-width:960px}
.corpo{flex:1;min-height:0;display:flex;flex-direction:column;gap:16px;font-size:var(--t-m);padding:24px 0 14px}
footer{display:flex;gap:24px;align-items:flex-end;border-top:1px solid var(--linha);
  padding:10px 0 14px;font-size:11px;line-height:1.4;color:var(--sec)}
footer .fontes{flex:1}
footer .aviso{white-space:nowrap;color:var(--tinta)}
p{margin:0}
.nota{font-size:var(--t-xs);line-height:1.45;color:var(--sec);margin-top:auto}
.nota .marca{display:inline-block;width:6px;height:12px;background:var(--tinta);vertical-align:-1px}
.nd{color:var(--nd)}
sup{font-size:.6em;margin-left:2px;color:var(--sec);font-weight:400}
h2{margin:0;font-weight:700;font-stretch:75%}

/* tarja: faixa na cor da empresa */
.tarja{background:var(--cor);color:#fff;padding:10px 16px;display:flex;align-items:baseline;gap:10px}
.tarja b{font-size:var(--t-l);font-stretch:75%;font-weight:700}
.tarja small{font-size:var(--t-xs);opacity:.85}

/* capa */
#capa{padding:0}
#capa h1{order:2;font-size:48px;padding:34px 64px 0;max-width:1180px}
#capa .sub{order:3;padding:0 64px;font-size:var(--t-m)}
#capa .corpo{order:1;flex:none;padding:0;gap:0}
#capa .corpo .nota{display:none}
#capa footer{order:5;margin:0 64px}
#capa::after{content:"";order:4;flex:1}
.campos{display:grid;grid-template-columns:1fr 1fr;height:380px}
.campo{background:var(--cor);color:#fff;padding:44px 64px;display:flex;flex-direction:column}
.campo b{font-size:84px;font-stretch:75%;font-weight:800;line-height:.9}
.campo .tk{font-size:var(--t-s);opacity:.85;margin-top:8px}
.campo .mg{margin-top:auto;font-size:56px;font-weight:700;font-stretch:75%;line-height:1}
.campo .mg small{display:block;font-size:var(--t-s);font-weight:400;font-stretch:100%;opacity:.9;margin-top:6px}

/* resumo */
.blocos{display:grid;grid-template-columns:repeat(3,1fr);gap:40px;flex:1;align-content:start;padding-top:40px}
.bloco h2{font-size:28px;line-height:1.05;margin-bottom:14px}
.par{display:grid;grid-template-columns:1fr 1fr;gap:4px}
.par .campo{padding:12px 14px 14px}
.par .campo small{font-size:var(--t-xs);opacity:.9}
.par .campo b{font-size:40px;line-height:1;margin-top:4px;font-weight:700;white-space:nowrap}
.par .campo.longo b{font-size:27px;line-height:1.48}
.par-rot{font-size:var(--t-xs);color:var(--sec);margin:6px 0 14px}
.bloco p:last-child{font-size:19px;line-height:1.45}

/* tabela */
.tabela{width:100%;border-collapse:collapse;table-layout:fixed}
.tabela thead th{text-align:left;font-size:var(--t-l);font-weight:700;font-stretch:75%;padding:10px 16px}
.tabela col.c-metrica{width:31%}
.tabela thead th.emp{background:var(--cor);color:#fff}
.tabela thead th small{font-size:var(--t-xs);font-weight:400;font-stretch:100%;opacity:.85;margin-left:8px}
.tabela tbody tr:nth-child(odd)>*{background:var(--faixa)}
.tabela tbody th{text-align:left;font-weight:400;font-size:16px;padding:7px 12px;vertical-align:top}
.tabela td{padding:7px 16px;vertical-align:top}
.tabela .v{display:block;font-size:20px;line-height:1.2}
.tabela .var{display:block;font-size:var(--t-xs);color:var(--sec);margin-top:2px}
.tabela td.venc{box-shadow:inset 6px 0 0 var(--cor)}
.tabela td.venc .v{font-weight:700}
.obs{display:block;font-size:var(--t-xs);color:var(--sec)}
.tabela.compacta tbody th{font-size:var(--t-s);padding:5px 12px}
.tabela.compacta td{padding:5px 16px}
.tabela.compacta .v{font-size:18px}
.tabela.compacta thead th{font-size:var(--t-m);padding:7px 16px}
.tabela.sem-cab thead tr{visibility:collapse}  /* some, mas mantém as larguras das colunas */
.secao{font-size:var(--t-m);margin:14px 0 6px}

/* gráficos: PNG de fundo branco, placas lado a lado */
.graf{flex:1;min-height:0;display:flex;gap:20px;justify-content:center;align-items:center}
.graf img{max-width:100%;max-height:100%;object-fit:contain;background:#fff}
.graf.dois img{max-width:calc(50% - 10px)}

/* perfil e setor: texto à esquerda, gráfico à direita */
.perfil,.setor{display:grid;grid-template-columns:1fr 1.15fr;gap:40px;flex:1;min-height:0}
.setor{grid-template-columns:1.35fr 1fr;gap:32px}
.pilha{display:flex;flex-direction:column;gap:22px;min-height:0}
.setor .pilha{gap:0}
.perfil .graf,.setor .graf{align-items:flex-start}
.empresa p{font-size:var(--t-m);line-height:1.45;margin-top:12px}
.empresa p.segs{font-size:var(--t-s);color:var(--sec)}

/* destaques */
.duas{display:grid;grid-template-columns:1fr 1fr;gap:40px;min-height:0}
.item{display:grid;grid-template-columns:84px 1fr;gap:12px;padding:10px 0;border-bottom:1px solid var(--linha);
  font-size:var(--t-s);line-height:1.4}
.item b{font-stretch:75%;font-size:var(--t-s)}
.item.pos b{color:var(--pos);font-size:var(--t-l);line-height:1}
.item.neg b{color:var(--neg);font-size:var(--t-l);line-height:1}
.item.pos span,.item.neg span{font-size:var(--t-m)}
.item.alerta b,.item.alerta span{color:var(--nd)}

/* metodologia */
.quatro{display:grid;grid-template-columns:1fr 1fr;gap:28px 48px;flex:1;align-content:start}
.quatro .bloco h2{font-size:var(--t-l);border-top:4px solid var(--tinta);padding-top:8px;margin-bottom:8px}
.quatro .bloco p{font-size:17px;line-height:1.45;margin-bottom:6px}
.quatro .bloco p.grande{font-size:52px;font-weight:700;font-stretch:75%;line-height:1;margin-bottom:4px}

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
