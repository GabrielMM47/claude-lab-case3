"""CASE-06 · Gerador da apresentação executiva (HTML 16:9, arquivo único).

    python src/apresentacao.py --comparativo saida/comparativo/<a>_x_<b>_<tri> \\
        [--narrativa narrativa/<a>_x_<b>_<tri>.json] [--metricas metricas] [--saida arquivo.html]

Entradas (contrato em docs/TAREFAS.md): comparativo.json + graficos/ (CASE-05), qualitativo da
apresentação institucional (CASE-03, opcional), contexto macro citado pelas empresas
(metricas/<slug>_<tri>_<doc>_macro.json, opcional) e a narrativa com os títulos-mensagem
(opcional; sem ela, usa os insights automáticos do comparativo).

Regras:
- nenhum número é digitado aqui nem na narrativa. A narrativa usa placeholders que o código
  resolve a partir dos dados verificados:
    {a.margem_ebitda} {b.receita_liquida.var_aa} {a.nome} {periodo} {criterio_ebitda}  comparativo
    {a.seg.brasil.pct_ebitda} {a.seg.brasil.ebitda_por_t} {a.seg.brasil.volume_vendas.var_aa}
                                                     segmento (comparativo.segmentos)
    {a.macro.tarifa_aco_eua}                         número do contexto macro (pelo id do fato)
  Afirmação sem número tirada de um documento entra com "cita": ["a.<id>"], que põe a página
  do fato no rodapé;
- a leitura de cenários (slide destaques_riscos) é do time e vem só da narrativa: o código
  confere os números e as citações, não o julgamento;
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
# Alertas que não vão para o slide de destaques: o N/D já aparece na tabela e no slide do setor.
ALERTAS_FORA_DOS_DESTAQUES = {"indisponivel"}
# Efeito de um cenário sobre cada empresa: símbolo (forma, não só cor) e classe de cor.
EFEITOS = {"++": ("▲▲", "pos"), "+": ("▲", "pos"), "0": ("●", "neutro"), "-": ("▼", "neg"), "--": ("▼▼", "neg")}
# Campos do segmento que a narrativa pode citar: participação (comparativo.segmentos) e por tonelada
CAMPOS_PCT_SEGMENTO = ("pct_receita", "pct_ebitda")
CAMPOS_POR_T = ("volume_vendas", "receita_por_t", "ebitda_por_t")

RE_FONTE = re.compile(r"^(?P<doc>.+?) p\. ?(?P<pag>\d+)$")
RE_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")
RE_PERIODO = re.compile(r"\b\d[TM]\d{2}\b")
# Nomes próprios com dígito que não são dado (lei, norma). Lista fechada: qualquer outro dígito
# na narrativa continua reprovado.
TERMOS_COM_DIGITO = ("Seção 232",)


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
    macro: dict = field(default_factory=dict)  # "a"/"b" -> {id: fato} do contexto macro
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

    def segmento(self, e: str, nome: str) -> dict | None:
        return next((s for s in self.comp.get("segmentos", {}).get(e, []) if s.get("segmento") == nome), None)


def carregar(pasta_comparativo: Path, pasta_metricas: Path | None) -> Dados:
    comp = json.loads((pasta_comparativo / "comparativo.json").read_text(encoding="utf-8"))
    qualitativo, macro = {}, {}
    if pasta_metricas:
        for e in ("a", "b"):
            prefixo = f"{comp['empresas'][e]['slug']}_{comp['periodo']}"
            arq = pasta_metricas / f"{prefixo}_apresentacao_qualitativo.json"
            if arq.exists():
                qualitativo[e] = json.loads(arq.read_text(encoding="utf-8"))
            # contexto macro: um arquivo por documento-fonte (itr, apresentacao); o id é a chave
            for arq in sorted(pasta_metricas.glob(f"{prefixo}_*_macro.json")):
                for fato in json.loads(arq.read_text(encoding="utf-8")):
                    if isinstance(fato, dict) and fato.get("id"):
                        macro.setdefault(e, {}).setdefault(fato["id"], fato)
    return Dados(comp, pasta_comparativo, qualitativo, macro)


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
        if partes[1] == "macro":
            return valor_macro(d, e, partes, nome, fontes)
        if partes[1] == "seg":
            return valor_segmento(d, e, partes, nome, fontes)
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


def valor_macro(d: Dados, e: str, partes: list[str], nome: str, fontes: Fontes) -> str:
    """{a.macro.<id>}: o número do fato de contexto macro, como aparece no documento."""
    if len(partes) != 3:
        raise ErroNarrativa(f"{{{nome}}}: formato inválido (use {{a.macro.<id>}})")
    fato = d.macro.get(e, {}).get(partes[2])
    if fato is None:
        raise ErroNarrativa(f"{{{nome}}}: contexto macro '{partes[2]}' não existe em metricas/*_macro.json")
    if not fato.get("valor_como_aparece"):
        raise ErroNarrativa(f"{{{nome}}}: '{partes[2]}' não tem número; cite com \"cita\": [\"{e}.{partes[2]}\"]")
    fontes.add_fato(e, fato)
    return str(fato["valor_como_aparece"])


def valor_segmento(d: Dados, e: str, partes: list[str], nome: str, fontes: Fontes) -> str:
    """{a.seg.<segmento>.<campo>[.var_aa]}: participação ou métrica por tonelada do segmento."""
    if len(partes) not in (4, 5):
        raise ErroNarrativa(f"{{{nome}}}: formato inválido (use {{a.seg.<segmento>.<campo>}})")
    seg = d.segmento(e, partes[2])
    if seg is None:
        raise ErroNarrativa(f"{{{nome}}}: segmento '{partes[2]}' não existe no comparativo")
    campo = partes[3]
    if campo in CAMPOS_PCT_SEGMENTO and len(partes) == 4:
        if seg.get(campo) is None:
            raise ErroNarrativa(f"{{{nome}}}: valor indisponível")
        fontes.add(e, seg.get("fontes"))
        return f"{fmt_br(seg[campo], 0)}%"
    if campo not in CAMPOS_POR_T:
        raise ErroNarrativa(f"{{{nome}}}: campo '{campo}' inválido "
                            f"(válidos: {', '.join(CAMPOS_PCT_SEGMENTO + CAMPOS_POR_T)})")
    item = (seg.get("por_t") or {}).get(campo)
    if item is None:
        raise ErroNarrativa(f"{{{nome}}}: valor indisponível (o segmento não tem {campo})")
    if len(partes) == 4:
        valor = item["texto"]
    elif partes[4] == "var_aa":
        valor = fmt_var(item.get("var_aa"), item.get("unidade_var"))
        if valor is None:
            raise ErroNarrativa(f"{{{nome}}}: variação indisponível")
    else:
        raise ErroNarrativa(f"{{{nome}}}: formato inválido (só .var_aa depois do campo)")
    fontes.add(e, item.get("fontes"))
    return valor


def item_texto(item) -> tuple[str, list]:
    """Item da narrativa: texto puro ou {"texto": ..., "cita": ["a.<id>"]}."""
    if isinstance(item, dict):
        return str(item.get("texto") or ""), list(item.get("cita") or [])
    return str(item), []


def citar(cita: list, d: Dados, fontes: Fontes) -> None:
    """Põe no rodapé a página dos fatos de contexto citados ('a.<id>')."""
    for ref in cita:
        e, _, mid = str(ref).partition(".")
        fato = d.macro.get(e, {}).get(mid) if e in ("a", "b") else None
        if fato is None:
            raise ErroNarrativa(f"cita {ref!r}: não existe em metricas/*_macro.json (use 'a.<id>' ou 'b.<id>')")
        fontes.add_fato(e, fato)


def render_item(item, d: Dados, fontes: Fontes) -> str:
    """Texto do item resolvido, citações registradas e HTML escapado."""
    texto, cita = item_texto(item)
    citar(cita, d, fontes)
    return esc(resolver(texto, d, fontes))


def itens_da_narrativa(narrativa: dict):
    """(id do slide, item) de todo texto da narrativa, em qualquer campo que vira slide."""
    for slide in narrativa.get("slides", []):
        sid = slide.get("id")
        for campo in ("titulo", "subtitulo", "nota", "monitorar"):
            if slide.get(campo):
                yield sid, slide[campo]
        for campo in ("bullets", "a", "b"):
            for item in slide.get(campo) or []:
                yield sid, item
        for card in slide.get("contexto") or []:
            yield sid, card.get("titulo") or ""
            yield sid, card
        for c in slide.get("cenarios") or []:
            for campo in ("nome", "gatilho", "nota"):
                if c.get(campo):
                    yield sid, c[campo]
            for lado in ("a", "b"):
                if isinstance(c.get(lado), dict):
                    yield sid, c[lado]


def textos_da_narrativa(narrativa: dict):
    for sid, item in itens_da_narrativa(narrativa):
        yield sid, item_texto(item)[0]


def verificar_cenarios(slide: dict) -> list[str]:
    problemas = []
    for i, c in enumerate(slide.get("cenarios") or [], 1):
        rot = f"[{slide.get('id')}] cenário {i}"
        if not c.get("nome"):
            problemas.append(f"{rot}: sem nome")
        for lado in ("a", "b"):
            efeito = (c.get(lado) or {}).get("efeito") if isinstance(c.get(lado), dict) else None
            if efeito not in EFEITOS:
                problemas.append(f"{rot}: efeito de '{lado}' deve ser um de {', '.join(EFEITOS)}")
        if c.get("vantagem") not in (None, "a", "b"):
            problemas.append(f"{rot}: vantagem deve ser 'a', 'b' ou null")
    return problemas


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
    for sid, item in itens_da_narrativa(narrativa):
        texto, cita = item_texto(item)
        fora = RE_PLACEHOLDER.sub(" ", texto)
        for termo in TERMOS_COM_DIGITO:
            fora = fora.replace(termo, " ")
        for p in RE_PERIODO.findall(fora):
            if p not in validos:
                problemas.append(f"[{sid}] período {p} não pertence a esta comparação ({d.comp['periodo']})")
        if re.search(r"\d", RE_PERIODO.sub("", fora)):
            problemas.append(f"[{sid}] número escrito à mão (use placeholder): {texto!r}")
        try:
            citar(cita, d, Fontes())
            resolver(texto, d, Fontes())
        except ErroNarrativa as erro:
            problemas.append(f"[{sid}] {erro}")
    for slide in narrativa.get("slides", []):
        problemas += verificar_cenarios(slide)
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
    if n.get("bullets"):
        bullets = [render_item(b, d, fontes) for b in n["bullets"]]
    else:
        bullets = []
        for ins in d.comp.get("insights", [])[:3]:
            bullets.append(esc(ins["texto"]))
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
        itens += [f"<b>{render_item(i, d, fontes)}</b>" for i in n.get(e) or []]  # exposição (narrativa)
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


def tiles_consolidados(d: Dados, fontes: Fontes) -> str:
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
    return f'<div class="tiles" style="--n:{max(len(tiles), 1)}">{"".join(tiles)}</div>'


def celula_por_t(item: dict | None) -> str:
    if not item:
        return '<span class="nd">—</span>'
    var = fmt_var(item.get("var_aa"), item.get("unidade_var"))
    return f'{esc(item["texto"])}<span class="var">{esc("A/A " + var) if var else "sem base A/A"}</span>'


def tabela_segmentos(d: Dados, fontes: Fontes) -> str | None:
    """Por negócio: volume, receita/t e EBITDA/t de cada segmento (numerador e denominador do
    mesmo negócio). Barra = EBITDA/t, na mesma escala para todas as linhas. None sem dados."""
    linhas = [(e, s, s["por_t"]) for e in ("a", "b") for s in d.comp.get("segmentos", {}).get(e, [])
              if (s.get("por_t") or {}).get("ebitda_por_t")]
    if not linhas:
        return None
    maximo = max(max(pt["ebitda_por_t"]["valor"], 0) for _, _, pt in linhas) or 1
    corpo = ['<table class="tabela segs"><thead><tr><th>Negócio</th><th>Volume vendido</th>'
             '<th>Receita por t</th><th>EBITDA ' + esc(d.comp.get("criterio_ebitda") or "") +
             ' por t</th><th>Fatia do EBITDA</th></tr></thead><tbody>']
    for e, s, pt in linhas:
        cor = esc(d.comp["empresas"][e]["cor"])
        eb = pt["ebitda_por_t"]
        largura = max(eb["valor"], 0) / maximo * 100
        barra = (f'<div class="barra" title="{esc(d.nomes[e])} · {esc(s.get("rotulo") or s["segmento"])}: '
                 f'{esc(eb["texto"])}"><i style="width:{largura:.1f}%;background:{cor}"></i>'
                 f'<span>{celula_por_t(eb)}</span></div>')
        pct = f'{fmt_br(s["pct_ebitda"], 0)}%' if s.get("pct_ebitda") is not None else "—"
        corpo.append(f'<tr><td class="negocio" style="--cor:{cor}">{esc(d.nomes[e])}'
                     f'<span class="obs">{esc(s.get("rotulo") or s["segmento"])}</span></td>'
                     f'<td>{celula_por_t(pt.get("volume_vendas"))}</td>'
                     f'<td>{celula_por_t(pt.get("receita_por_t"))}</td><td class="col-barra">{barra}</td>'
                     f'<td>{esc(pct)}</td></tr>')
        for item in pt.values():
            fontes.add(e, item.get("fontes"))
        fontes.add(e, s.get("fontes"))
    corpo.append("</tbody></table>")
    return "".join(corpo)


def painel_contexto(cards: list, d: Dados, fontes: Fontes) -> str:
    """Cartões 'o que move o setor agora': texto da narrativa com números do contexto macro."""
    html_cards = [f'<div class="card"><h3>{esc(resolver(c.get("titulo") or "", d, fontes))}</h3>'
                  f'<p>{render_item(c, d, fontes)}</p></div>' for c in cards]
    return f'<div class="contexto" style="--n:{len(html_cards)}">{"".join(html_cards)}</div>'


def slide_setor(d, n, fontes):
    titulo = resolver(n.get("titulo") or "Métricas de siderurgia", d, fontes)
    # por negócio quando há segmentos com métrica por tonelada; senão, o consolidado
    corpo = tabela_segmentos(d, fontes) or tiles_consolidados(d, fontes)
    if n.get("nota"):
        corpo += f'<p class="nota">{render_item(n["nota"], d, fontes)}</p>'
    if n.get("contexto"):
        corpo += painel_contexto(n["contexto"], d, fontes)
    else:
        grafico = img_grafico(d, "volume_rpt", fontes)
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


SINAIS = {"+": '<b class="pos">+</b> ', "-": '<b class="neg">−</b> '}


def item_empresa(item, d: Dados, fontes: Fontes) -> str:
    """Bullet da narrativa numa coluna de empresa; {"sinal": "+"|"-"} marca positivo/negativo."""
    sinal = item.get("sinal") if isinstance(item, dict) else None
    return SINAIS.get(sinal, "") + render_item(item, d, fontes)


def tabela_cenarios(cenarios: list, d: Dados, fontes: Fontes) -> str:
    """Cenário macro × efeito em cada empresa × quem leva vantagem (leitura do time)."""
    a, b = d.comp["empresas"]["a"], d.comp["empresas"]["b"]
    corpo = [f'<table class="cenarios"><thead><tr><th>Se o cenário for…</th>'
             f'<th style="--cor:{esc(a["cor"])}">{esc(a["nome"])}</th>'
             f'<th style="--cor:{esc(b["cor"])}">{esc(b["nome"])}</th><th>Vantagem</th></tr></thead><tbody>']
    for c in cenarios:
        celulas = [f'<td><b>{render_item(c["nome"], d, fontes)}</b>'
                   + (f'<span class="obs">{render_item(c["gatilho"], d, fontes)}</span>' if c.get("gatilho") else "")
                   + "</td>"]
        for lado in ("a", "b"):
            simbolo, classe = EFEITOS[c[lado]["efeito"]]
            celulas.append(f'<td><span class="efeito {classe}">{simbolo}</span> {render_item(c[lado], d, fontes)}</td>')
        v = c.get("vantagem")
        nota = f'<span class="obs">{render_item(c["nota"], d, fontes)}</span>' if c.get("nota") else ""
        if v in ("a", "b"):
            celulas.append(f'<td class="venc" style="--cor:{esc(d.comp["empresas"][v]["cor"])}">'
                           f'{esc(d.nomes[v])}{nota}</td>')
        else:
            celulas.append(f"<td>—{nota}</td>")
        corpo.append(f"<tr>{''.join(celulas)}</tr>")
    corpo.append("</tbody></table>")
    return "".join(corpo)


def slide_destaques_riscos(d, n, fontes):
    titulo = resolver(n.get("titulo") or "Destaques do trimestre e o que observar", d, fontes)
    cenarios = n.get("cenarios") or []
    colunas = []
    for e in ("a", "b"):
        emp = d.comp["empresas"][e]
        pos, neg, f_num = destaques_numericos(d, e)
        fontes.juntar(f_num)
        extras = n.get(e) or []
        itens = [f'<b class="pos">+</b> {esc(pos or "Nenhum indicador comparável melhorou A/A")}']
        if neg or not extras:  # sem piora consolidada, a narrativa traz o ponto negativo
            itens.append(f'<b class="neg">−</b> {esc(neg or "Nenhum indicador comparável piorou A/A")}')
        itens += [item_empresa(i, d, fontes) for i in extras]
        if not cenarios:  # com cenários, riscos e perspectivas genéricos dão lugar à tabela
            for tema, rotulo in (("destaques_trimestre", "Trimestre"), ("riscos", "Riscos"),
                                 ("guidance_perspectivas", "O que observar")):
                for fato in d.qual(e, tema)[:1]:
                    itens.append(f"<b>{rotulo}:</b> {esc(fato['resumo'])}")
                    fontes.add_fato(e, fato)
        # efeito pontual primeiro (é o que distorce o A/A); com cenários, só cabe um
        alertas = sorted((a for a in d.alertas(e) if a.get("tipo") not in ALERTAS_FORA_DOS_DESTAQUES),
                         key=lambda a: a.get("tipo") != "efeito_pontual")
        for alerta in alertas[:1 if cenarios else 2]:
            itens.append(f'<span class="alerta">{esc(alerta["texto"])}</span>')
            fontes.add(e, alerta.get("fontes"))
        colunas.append(f'<div class="empresa" style="--cor:{esc(emp["cor"])}"><h2>{esc(emp["nome"])}</h2>'
                       f'{lista(itens, "compacta")}</div>')
    corpo = f'<div class="duas">{"".join(colunas)}</div>'
    if cenarios:
        corpo += tabela_cenarios(cenarios, d, fontes)
    if n.get("monitorar"):
        corpo += f'<p class="monitorar"><b>O que acompanhar:</b> {render_item(n["monitorar"], d, fontes)}</p>'
    return titulo, None, corpo


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
        if ver.get("revisar"):
            txt_ver += (f" Outros {ver['revisar']} estão no PDF, mas a coluna ou o período ainda não foi "
                        f"comprovado por código; {ver.get('erro', 0)} com erro.")
    else:
        txt_ver = "Verificação automática ainda não rodou para este comparativo: números não conferidos."
    itens = [
        esc(f"EBITDA {d.comp['criterio_ebitda']}, o mesmo critério para as duas empresas. Números consolidados."),
        esc(f"A/A = {periodo} × mesmo trimestre do ano anterior; T/T = × trimestre anterior; "
            f"variação de percentuais em p.p."),
    ]
    if acumulados:
        itens.append(esc(f"{', '.join(nomes_acum)}: {', '.join(acumulados)} anualizado, sobre saldos médios."))
    if d.macro:
        itens.append(esc("Contexto macro e setorial: só o que as próprias empresas publicaram (ITR e "
                         "apresentação), com página e verificado como os demais números; projeções de "
                         "demanda são das fontes citadas pelas empresas. Os cenários são leitura do time."))
    for alerta in d.comp.get("alertas", []):  # divergência de definição é ressalva de método
        if str(alerta.get("tipo", "")).startswith("divergencia"):
            quem = d.nomes.get(alerta.get("empresa"), "")
            itens.append(f'<span class="nd">{esc((quem + ": " if quem else "") + alerta["texto"])}</span>')
            todas.add(alerta.get("empresa"), alerta.get("fontes"))
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
CSS = """
:root{--tinta:#1d2430;--suave:#5b6474;--linha:#e3e6eb;--nd:#9a6b00}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:#2b2f36;color:var(--tinta);
  font-family:"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
#deck{position:fixed;inset:0 0 46px 0;display:flex;align-items:center;justify-content:center;overflow:hidden}
.slide{width:1280px;height:720px;flex:none;background:#fff;display:none;flex-direction:column;
  padding:44px 64px 0;position:absolute}
.slide.ativo{display:flex}
.slide h1{font-size:32px;line-height:1.2;margin:0 0 6px;font-weight:650;letter-spacing:-.01em}
.slide .sub{color:var(--suave);font-size:18px;margin:0 0 10px}
.corpo{flex:1;min-height:0;display:flex;flex-direction:column;gap:14px;font-size:18px;padding-top:10px}
footer{display:flex;gap:18px;align-items:flex-end;border-top:1px solid var(--linha);
  padding:8px 0 12px;font-size:11px;line-height:1.35;color:var(--suave)}
footer .fontes{flex:1}
footer .aviso{white-space:nowrap;font-weight:600}
ul{margin:0;padding-left:1.1em}
li{margin:0 0 .45em}
ul.grande{font-size:24px}
ul.grande li{margin-bottom:.8em}
ul.compacta{font-size:15px}
.capa{display:flex;gap:28px;align-items:baseline;font-size:46px;font-weight:700;margin-top:90px}
.capa small{font-size:18px;color:var(--suave);font-weight:500}
.capa .x{color:var(--suave);font-weight:300}
.nota{font-size:13px;color:var(--suave);margin:0}
.duas{display:grid;grid-template-columns:1fr 1fr;gap:36px;min-height:0;flex:none}
.empresa h2{font-size:21px;margin:0 0 10px;padding-bottom:6px;border-bottom:3px solid var(--cor)}
.empresa h2 small{font-size:13px;color:var(--suave);font-weight:500}
.tabela{width:100%;border-collapse:collapse;font-size:16px}
.tabela th{text-align:left;font-size:13px;color:var(--suave);font-weight:600;padding:4px 10px;
  border-bottom:2px solid var(--linha)}
.tabela th[style]{border-bottom-color:var(--cor);color:var(--tinta)}
.tabela td{padding:5px 10px;border-bottom:1px solid var(--linha);vertical-align:top}
.tabela td.venc{box-shadow:inset 4px 0 0 var(--cor);font-weight:700}
.tabela td.fonte{font-size:11px;color:var(--suave);max-width:250px}
.v{display:inline}
.var,.obs{display:block;font-size:11.5px;color:var(--suave);font-weight:400}
.nd{color:var(--nd);font-weight:600}
.melhor{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--cor);margin-left:6px}
.graf{flex:1;min-height:0;display:flex;gap:16px;justify-content:center;align-items:center}
.graf img{max-width:50%;max-height:100%;object-fit:contain}
.graf.um img{max-width:100%}
.tiles{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:10px}
.tile{border:1px solid var(--linha);border-radius:8px;padding:10px;font-size:15px}
.tile .nome{font-size:14px;font-weight:600;margin-bottom:6px}
.tile .lado{padding:4px 0 4px 8px;border-left:3px solid transparent;margin-top:4px}
.tile .lado.venc{border-left-color:var(--cor);font-weight:700}
.tile .quem{display:block;font-size:11px;color:var(--suave);font-weight:400}
.pos{color:#1a7f37}.neg{color:#b42318}.neutro{color:var(--suave)}
.alerta{display:block;font-size:13px;color:#7a4b00;background:#fff6e5;border-radius:4px;padding:4px 8px}
.segs{font-size:15px}
.segs td{padding:4px 10px}
.segs td.negocio{box-shadow:inset 4px 0 0 var(--cor);font-weight:600}
.segs td.negocio .obs{font-size:13px;color:var(--tinta);font-weight:400}
.segs .col-barra{width:34%}
.barra{position:relative;display:flex;align-items:center;gap:10px}
.barra i{display:block;height:16px;min-width:3px;border-radius:0 4px 4px 0;flex:none;max-width:62%}
.barra span{flex:none}
.contexto{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:10px}
.contexto .card{border:1px solid var(--linha);border-radius:8px;padding:8px 10px;font-size:13px;line-height:1.38}
.contexto h3{font-size:14px;margin:0 0 4px}
.contexto p{margin:0}
.cenarios{width:100%;border-collapse:collapse;font-size:13.5px;line-height:1.3}
.cenarios th{text-align:left;font-size:12.5px;color:var(--suave);font-weight:600;padding:3px 8px;
  border-bottom:2px solid var(--linha)}
.cenarios th[style]{border-bottom-color:var(--cor);color:var(--tinta)}
.cenarios td{padding:4px 8px;border-bottom:1px solid var(--linha);vertical-align:top}
.cenarios td:first-child{width:27%}
.cenarios td:last-child{width:13%}
.cenarios td.venc{box-shadow:inset 4px 0 0 var(--cor);font-weight:700}
.cenarios .obs{font-size:12px}
.efeito{font-size:12px;letter-spacing:-.08em;margin-right:2px}
.monitorar{font-size:13px;margin:0;color:var(--tinta)}
#nav{position:fixed;right:14px;bottom:8px;display:flex;gap:8px;align-items:center;z-index:5;
  color:#cfd3da;font:13px system-ui,sans-serif}
#nav button{background:#454b55;color:#fff;border:0;border-radius:6px;width:38px;height:32px;
  font-size:20px;line-height:1;cursor:pointer}
#nav button:hover{background:#5d6470}
#nav button:disabled{opacity:.35;cursor:default}
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
// a faixa de 46px embaixo é dos botões: o slide nunca fica sob eles
function escala(){const k=Math.min(innerWidth/1280,(innerHeight-46)/720)*0.97;s.forEach(x=>x.style.transform='scale('+k+')')}
const ant=document.getElementById('ant'),prox=document.getElementById('prox');
function ir(n){i=Math.max(0,Math.min(s.length-1,n));s.forEach((x,j)=>x.classList.toggle('ativo',j===i));
  document.getElementById('pos').textContent=(i+1)+' / '+s.length;ant.disabled=i===0;prox.disabled=i===s.length-1;
  try{history.replaceState(null,'','#'+(i+1))}catch(e){}}
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key))ir(i+1);
  else if(['ArrowLeft','PageUp'].includes(e.key))ir(i-1);else if(e.key==='Home')ir(0);
  else if(e.key==='End')ir(s.length-1)});
ant.onclick=()=>ir(i-1);prox.onclick=()=>ir(i+1);
// clique no slide: terço esquerdo volta, o resto avança (sem atrapalhar seleção de texto)
document.getElementById('deck').addEventListener('click',e=>{if(String(getSelection()))return;
  ir(e.clientX<innerWidth/3?i-1:i+1)});
let x0=null;addEventListener('touchstart',e=>{x0=e.touches[0].clientX},{passive:true});
addEventListener('touchend',e=>{if(x0===null)return;const dx=e.changedTouches[0].clientX-x0;x0=null;
  if(Math.abs(dx)>40)ir(dx<0?i+1:i-1)},{passive:true});
addEventListener('resize',escala);escala();
let h=1;try{h=parseInt(location.hash.slice(1))||1}catch(e){}ir(h-1);
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
            f'<title>{esc(a)} × {esc(b)} · {esc(d.comp["periodo"])}</title><style>{CSS}</style></head>'
            f'<body><main id="deck">{"".join(secoes)}</main>'
            f'<div id="nav"><button id="ant" type="button" aria-label="Slide anterior">‹</button>'
            f'<span id="pos"></span><button id="prox" type="button" aria-label="Próximo slide">›</button></div>'
            f'<script>{JS}</script></body></html>\n')


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
