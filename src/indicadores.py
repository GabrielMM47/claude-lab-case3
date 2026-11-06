"""
Case 3 — motor de indicadores (CASE-04).

Lê os fatos verificados de uma empresa (metricas/<slug>_<tri>_*.json), põe tudo
na mesma unidade e calcula margens, endividamento, rentabilidade e as métricas de
siderurgia. Nenhum número é digitado aqui: tudo sai dos fatos, e cada indicador
leva a lista de insumos (documento e página) de onde veio.

Rode da raiz do repositório:
    python src/indicadores.py --empresa gerdau --tri 3T26

Saída: metricas/<slug>_<tri>_indicadores.json (formato em docs/TAREFAS.md).
Fórmulas e escolhas: docs/METODOLOGIA_INDICADORES.md.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parent.parent

TOLERANCIA_DUPLICATA = 0.005      # 0,5%: o mesmo fato vindo de dois documentos
TOLERANCIA_DEFINICAO = 0.05       # 5%: calculado × reportado (critérios podem diferir)
LIMITE_EFEITO_PONTUAL = 0.10      # ajustes acima de 10% do EBITDA ajustado do período
ALIQUOTA_NOMINAL = 0.34           # IR + CSLL; hipótese metodológica, parametrizável na CLI
PRIORIDADE_DOCUMENTO = {"itr": 0, "apresentacao": 1}
CRITERIOS_EBITDA = ("contabil", "ajustado")
SETOR_SIDERURGIA = "siderurgia"
STATUS = ("ok", "ausente", "nao_comparavel", "nao_aplicavel")   # exibidos como valor, N/D, N/C, N/A

# --- Entrada: usa o contrato (CASE-01) quando ele existir ---------------------
try:
    from contrato import carregar_fatos, para_milhoes  # type: ignore[import-not-found]
except ImportError:  # provisório até o CASE-01 entrar no main; mesmas assinaturas do card
    _FATOR_MONETARIO = {"r$ mil": 1e-3, "r$ milhões": 1.0, "r$ milhoes": 1.0,
                        "r$ bilhões": 1e3, "r$ bilhoes": 1e3}

    def carregar_fatos(slug: str, tri: str, pasta: str = "metricas") -> list[dict]:
        fatos: list[dict] = []
        for arquivo in sorted(Path(pasta).glob(f"{slug}_{tri}_*.json")):
            if arquivo.stem.endswith("_indicadores"):
                continue
            fatos.extend(json.loads(arquivo.read_text(encoding="utf-8")))
        return fatos

    def para_milhoes(valor: float, unidade: str) -> float:
        chave = " ".join(unidade.lower().split())
        if chave not in _FATOR_MONETARIO:
            raise ValueError(f"unidade monetária desconhecida: {unidade!r}")
        return valor * _FATOR_MONETARIO[chave]


# --- Unidades -----------------------------------------------------------------
_VOLUME_EM_MIL_T = {"t": 1e-3, "toneladas": 1e-3, "mil t": 1.0, "kt": 1.0, "mil toneladas": 1.0,
                    "milhões de t": 1e3, "milhoes de t": 1e3, "milhões de toneladas": 1e3,
                    "milhoes de toneladas": 1e3, "mt": 1e3}
_SEM_CONVERSAO = {"%", "x", "r$/t", "us$/t"}


def normalizar(valor: float, unidade: str) -> tuple[float, str]:
    """Dinheiro em R$ milhões, volume em mil t; %, x, R$/t e US$/t ficam como estão."""
    u = " ".join((unidade or "").lower().split())
    if u.startswith("r$") and "/" not in u:
        return para_milhoes(valor, unidade), "R$ milhões"
    por_ano = u.endswith("/ano")
    base = u.removesuffix("/ano").strip()
    if base in _VOLUME_EM_MIL_T:
        return valor * _VOLUME_EM_MIL_T[base], "mil t/ano" if por_ano else "mil t"
    if u in _SEM_CONVERSAO:
        return valor, unidade.strip()
    raise ValueError(f"unidade não suportada: {unidade!r}")


# --- Períodos -----------------------------------------------------------------
_TRIMESTRE = re.compile(r"^([1-4])T(\d{2})$")


def _partes(rotulo: str) -> tuple[int, int]:
    m = _TRIMESTRE.match(rotulo)
    if not m:
        raise ValueError(f"período inválido: {rotulo!r} (esperado nTaa, ex.: 3T26)")
    return int(m[1]), int(m[2])


def _rotulo(n: int, aa: int) -> str:
    return f"{n}T{aa:02d}"


def periodo_aa(tri: str) -> str:
    n, aa = _partes(tri)
    return _rotulo(n, aa - 1)


def periodo_tt(tri: str) -> str:
    n, aa = _partes(tri)
    return _rotulo(4, aa - 1) if n == 1 else _rotulo(n - 1, aa)


def acumulado(tri: str) -> str:
    """Acumulado do ano até o trimestre: 3T26 -> 9M26 (no 1T, o próprio trimestre)."""
    n, aa = _partes(tri)
    return tri if n == 1 else f"{3 * n}M{aa:02d}"


def fim_exercicio_anterior(tri: str) -> str:
    _, aa = _partes(tri)
    return _rotulo(4, aa - 1)


def fator_anualizacao(tri: str) -> float:
    n, _ = _partes(tri)
    return 4 / n


def _texto_fator(tri: str) -> str:
    return {1: "4", 2: "2", 3: "4/3", 4: "1"}[_partes(tri)[0]]


# --- Base de fatos --------------------------------------------------------------
class Indisponivel(Exception):
    """Indicador sem valor. O status diz por quê; nada é estimado."""
    status = "ausente"


class Faltando(Indisponivel):
    """Insumo ausente (N/D)."""
    status = "ausente"


class NaoComparavel(Indisponivel):
    """Numerador e denominador de negócios, escopos ou bases diferentes (N/C)."""
    status = "nao_comparavel"


class NaoAplicavel(Indisponivel):
    """Métrica que não se aplica ao setor da empresa (N/A)."""
    status = "nao_aplicavel"


@dataclass
class Valor:
    valor: float
    unidade: str
    fonte: dict


def _diferenca_relativa(a: float, b: float) -> float:
    maior = max(abs(a), abs(b))
    return 0.0 if maior == 0 else abs(a - b) / maior


class Base:
    """Fatos normalizados, indexados por (chave, período, escopo)."""

    def __init__(self, fatos: list[dict]):
        self.dados: dict[tuple[str, str, str], Valor] = {}
        self.ajustes: dict[tuple[str, str], list[dict]] = {}
        self.alertas: list[dict] = []
        for fato in fatos:
            self._incluir(fato)

    def _incluir(self, f: dict) -> None:
        if f.get("chave") in (None, "qualitativo") or f.get("valor") is None:
            return
        escopo = f.get("escopo") or "consolidado"
        try:
            valor, unidade = normalizar(float(f["valor"]), f.get("unidade", ""))
        except ValueError as erro:
            self.alertas.append({"tipo": "unidade", "texto":
                                 f"{f['chave']} {f.get('periodo')} ({escopo}) ignorado: {erro}"})
            return
        fonte = {"chave": f["chave"], "periodo": f.get("periodo"), "escopo": escopo,
                 "documento": f.get("documento"), "pagina": f.get("pagina")}
        if f["chave"] == "ajuste_ebitda":
            self.ajustes.setdefault((f["periodo"], escopo), []).append(
                {"descricao": f.get("metrica", ""), "valor": valor, "unidade": unidade, **fonte})
            return
        # A chave inclui período e escopo, e EBITDA contábil e ajustado são chaves distintas:
        # a prioridade abaixo só decide entre fontes do MESMO fato, nunca entre bases diferentes.
        chave = (f["chave"], f["periodo"], escopo)
        novo, atual = Valor(valor, unidade, fonte), self.dados.get(chave)
        if atual is None:
            self.dados[chave] = novo
            return
        mantido = novo if self._prioridade(novo) < self._prioridade(atual) else atual
        if _diferenca_relativa(atual.valor, novo.valor) > TOLERANCIA_DUPLICATA:
            self.alertas.append({
                "tipo": "divergencia", "chave": chave[0], "periodo": chave[1], "escopo": escopo,
                "valores": [{"documento": v.fonte["documento"], "pagina": v.fonte["pagina"],
                             "valor": round(v.valor, 4), "unidade": v.unidade} for v in (atual, novo)],
                "mantido": mantido.fonte["documento"],
                "texto": (f"{chave[0]} {chave[1]} ({escopo}): {atual.fonte['documento']} "
                          f"p.{atual.fonte['pagina']} = {atual.valor:.1f} x {novo.fonte['documento']} "
                          f"p.{novo.fonte['pagina']} = {novo.valor:.1f} {novo.unidade}; mantido o do "
                          f"{mantido.fonte['documento']} (itr > apresentacao)")})
        self.dados[chave] = mantido

    @staticmethod
    def _prioridade(v: Valor) -> int:
        return PRIORIDADE_DOCUMENTO.get(v.fonte["documento"], 9)

    def get(self, chave: str, periodo: str, escopo: str = "consolidado") -> Valor:
        valor = self.dados.get((chave, periodo, escopo))
        if valor is None:
            raise Faltando(f"falta {chave} {periodo} ({escopo})")
        return valor

    def tem(self, chave: str, escopo: str = "consolidado") -> bool:
        return any(c == chave and e == escopo for (c, _, e) in self.dados)

    def escopos_segmento(self, chave: str) -> list[str]:
        return sorted({e for (c, _, e) in self.dados if c == chave and e.startswith("segmento:")})


class Leitor:
    """Lê fatos para um cálculo e guarda de onde cada um veio."""

    def __init__(self, base: Base):
        self.base, self.insumos, self.unidade = base, [], None

    def __call__(self, chave: str, periodo: str, escopo: str = "consolidado") -> float:
        v = self.base.get(chave, periodo, escopo)
        self.insumos.append(v.fonte)
        self.unidade = self.unidade or v.unidade
        return v.valor


# --- Blocos de cálculo (q = trimestre de referência, ex.: 3T26) ----------------
def _div(a: float, b: float, motivo: str = "denominador zero") -> float:
    if b == 0:
        raise Faltando(motivo)
    return a / b


def _ebitda(L: Leitor, periodo: str, criterio: str, escopo: str = "consolidado") -> float:
    """Ajustado: o reportado. Contábil: o reportado ou, se faltar, EBIT + D&A do mesmo período."""
    if criterio == "ajustado":
        return L("ebitda_ajustado", periodo, escopo)
    if ("ebitda_contabil", periodo, escopo) in L.base.dados:
        return L("ebitda_contabil", periodo, escopo)
    chaves_da = ("depreciacao_amortizacao_tri", "depreciacao_amortizacao") \
        if _TRIMESTRE.match(periodo) else ("depreciacao_amortizacao",)
    for chave in chaves_da:
        if (chave, periodo, escopo) in L.base.dados:
            return L("ebit", periodo, escopo) + abs(L(chave, periodo, escopo))
    raise Faltando(f"falta ebitda_contabil {periodo} ({escopo}) e a D&A do período para calcular EBIT + D&A")


def _divida_bruta(L, q):
    return L("emprestimos_cp", q) + L("emprestimos_lp", q)


def _caixa(L, q):
    return L("caixa_equivalentes", q) + L("aplicacoes_financeiras", q)


def _divida_liquida(L, q):
    return _divida_bruta(L, q) - _caixa(L, q)


def _pl_controladores(L, q):
    return L("pl_total", q) - L("pl_nao_controladores", q)


def _capital_investido(L, q):
    return _divida_liquida(L, q) + L("pl_total", q)


def _ativo_total(L, q):
    return L("ativo_total", q)


def _media(saldo: Callable, L, q):
    return (saldo(L, fim_exercicio_anterior(q)) + saldo(L, q)) / 2


def _anualizado(L, chave, q):
    return L(chave, acumulado(q)) * fator_anualizacao(q)


def _ebitda_anualizado(L, q, criterio):
    valor = _ebitda(L, acumulado(q), criterio) * fator_anualizacao(q)
    if valor <= 0:
        raise Faltando("EBITDA não positivo: DL/EBITDA sem significado")
    return valor


def _aliquota_efetiva(L, q, nominal: float):
    p = acumulado(q)
    lair = L("lair", p)
    if lair <= 0:
        return nominal
    return min(max(-L("ir_csll", p) / lair, 0.0), nominal)


def _nopat(L, q, nominal: float):
    return _anualizado(L, "ebit", q) * (1 - _aliquota_efetiva(L, q, nominal))


def _retorno(numerador: Callable, saldo: Callable):
    """Fluxo acumulado anualizado ÷ média do saldo (fim do exercício anterior e trimestre)."""
    def calc(L, q):
        media = _media(saldo, L, q)
        if media <= 0:
            raise Faltando("saldo médio não positivo")
        return numerador(L, q) / media * 100
    return calc


def _volume(L, q, escopo):
    volume = L("volume_vendas", q, escopo)
    if volume <= 0:
        raise Faltando(f"volume vendido zero em {q} ({escopo})")
    return volume


def _por_tonelada(valor_milhoes: Callable, escopo: str):
    """R$ milhões ÷ mil t = R$ mil por t; × 1000 para R$/t."""
    def calc(L, q):
        return valor_milhoes(L, q) * 1000 / _volume(L, q, escopo)
    return calc


def _pct_receita(valor: float, L, periodo) -> float:
    return _div(valor, L("receita_liquida", periodo), "receita zero") * 100


def _margem(chave_numerador: str):
    return lambda L, q: _pct_receita(L(chave_numerador, q), L, q)


# --- Catálogo de indicadores -----------------------------------------------------
@dataclass
class Spec:
    chave: str
    nome: str
    grupo: str
    unidade: str | None   # None: a unidade do próprio fato (repasse)
    melhor: str           # maior | menor | neutro
    base: str             # tri (trimestre) | acum (acumulado do ano) | saldo (fim do período)
    formula: str
    calc: Callable[[Leitor, str], float]
    escopo: str = "consolidado"
    obs: str | None = None


def _repasse(chave: str, escopo: str = "consolidado"):
    return lambda L, q: L(chave, q, escopo)


def _bloqueado(erro: type[Indisponivel], motivo: str):
    def calc(L, q):
        raise erro(motivo)
    return calc


def _repasse_acum(chave: str, absoluto: bool = False):
    def calc(L, q):
        v = L(chave, acumulado(q))
        return abs(v) if absoluto else v
    return calc


def _specs_consolidadas(tri: str, aliquota: float = ALIQUOTA_NOMINAL) -> list[Spec]:
    acum, ini = acumulado(tri), fim_exercicio_anterior(tri)
    anual = f"{acum} × {_texto_fator(tri)}"
    media = f"média de {ini} e {tri}"
    specs = [
        # Escala
        Spec("receita_liquida", "Receita líquida", "escala", "R$ milhões", "maior", "tri",
             "receita_liquida (3.01)", _repasse("receita_liquida")),
        Spec("ebit", "EBIT", "escala", "R$ milhões", "maior", "tri",
             "ebit (3.05, inclui equivalência patrimonial)", _repasse("ebit")),
        Spec("lucro_liquido", "Lucro líquido consolidado", "escala", "R$ milhões", "maior", "tri",
             "lucro_liquido (3.11)", _repasse("lucro_liquido")),
        Spec("lucro_liquido_controladores", "Lucro líquido dos controladores", "escala", "R$ milhões",
             "maior", "tri", "lucro_liquido_controladores (3.11.01)", _repasse("lucro_liquido_controladores")),
    ]
    for crit in CRITERIOS_EBITDA:
        rotulo = "contábil" if crit == "contabil" else "ajustado"
        formula_ebitda = ("ebitda_ajustado (reportado)" if crit == "ajustado"
                          else "ebitda_contabil (reportado) ou ebit + D&A do período")
        specs.append(Spec(f"ebitda_{crit}", f"EBITDA {rotulo}", "escala", "R$ milhões", "maior", "tri",
                          formula_ebitda, lambda L, q, c=crit: _ebitda(L, q, c)))
    # Margens
    specs += [
        Spec("margem_bruta", "Margem bruta", "margens", "%", "maior", "tri",
             "lucro_bruto / receita_liquida", _margem("lucro_bruto")),
        Spec("margem_ebit", "Margem EBIT", "margens", "%", "maior", "tri",
             "ebit / receita_liquida", _margem("ebit")),
        Spec("margem_liquida", "Margem líquida", "margens", "%", "maior", "tri",
             "lucro_liquido / receita_liquida", _margem("lucro_liquido")),
    ]
    for crit in CRITERIOS_EBITDA:
        rotulo = "contábil" if crit == "contabil" else "ajustada"
        specs.append(Spec(
            f"margem_ebitda_{crit}", f"Margem EBITDA {rotulo}", "margens", "%", "maior", "tri",
            f"ebitda_{crit} / receita_liquida",
            lambda L, q, c=crit: _pct_receita(_ebitda(L, q, c), L, q)))
    # Endividamento
    specs += [
        Spec("divida_bruta", "Dívida bruta", "endividamento", "R$ milhões", "menor", "saldo",
             "emprestimos_cp (2.01.04) + emprestimos_lp (2.02.01)", _divida_bruta),
        Spec("caixa_total", "Caixa e aplicações", "endividamento", "R$ milhões", "maior", "saldo",
             "caixa_equivalentes (1.01.01) + aplicacoes_financeiras (1.01.02)", _caixa),
        Spec("divida_liquida", "Dívida líquida", "endividamento", "R$ milhões", "menor", "saldo",
             "divida_bruta - caixa_total", _divida_liquida),
        Spec("divida_liquida_pl", "Dívida líquida / PL", "endividamento", "x", "menor", "saldo",
             "divida_liquida / pl_total",
             lambda L, q: _div(_divida_liquida(L, q), L("pl_total", q), "PL zero")),
    ]
    for crit in CRITERIOS_EBITDA:
        rotulo = "contábil" if crit == "contabil" else "ajustado"
        specs.append(Spec(
            f"dl_ebitda_{crit}", f"Dívida líquida / EBITDA {rotulo}", "endividamento", "x", "menor", "saldo",
            f"divida_liquida / (ebitda_{crit} {anual})",
            lambda L, q, c=crit: _divida_liquida(L, q) / _ebitda_anualizado(L, q, c),
            obs=f"EBITDA anualizado ({anual}); a empresa costuma divulgar com EBITDA dos últimos 12 meses"))
    # Rentabilidade
    specs += [
        Spec("roe", "ROE", "rentabilidade", "%", "maior", "acum",
             f"lucro_liquido_controladores {anual} / {media} de (pl_total - pl_nao_controladores)",
             _retorno(lambda L, q: _anualizado(L, "lucro_liquido_controladores", q), _pl_controladores)),
        Spec("roa", "ROA", "rentabilidade", "%", "maior", "acum",
             f"lucro_liquido {anual} / {media} de ativo_total",
             _retorno(lambda L, q: _anualizado(L, "lucro_liquido", q), _ativo_total)),
        Spec("roi", "ROI (antes de impostos)", "rentabilidade", "%", "maior", "acum",
             f"ebit {anual} / {media} de capital investido (divida_liquida + pl_total), antes de impostos",
             _retorno(lambda L, q: _anualizado(L, "ebit", q), _capital_investido),
             obs="ROI não tem definição única; aqui é o retorno sobre capital investido antes de impostos"),
        Spec("roic", "ROIC", "rentabilidade", "%", "maior", "acum",
             f"ebit {anual} × (1 - alíquota efetiva {acum}, entre 0% e {aliquota:.0%}) / {media} "
             f"de capital investido",
             _retorno(lambda L, q: _nopat(L, q, aliquota), _capital_investido),
             obs=(f"hipótese metodológica, não dado reportado: alíquota efetiva = -ir_csll / lair, "
                  f"limitada a {aliquota:.0%}; LAIR <= 0 usa {aliquota:.0%}")),
    ]
    # Geração de caixa (a DFC só traz o acumulado)
    specs += [
        Spec("fco", "Caixa das operações", "caixa", "R$ milhões", "maior", "acum",
             "fco (6.01)", _repasse_acum("fco")),
        Spec("capex", "Capex", "caixa", "R$ milhões", "neutro", "acum",
             "capex (aquisição de imobilizado na DFC, em módulo)", _repasse_acum("capex", absoluto=True)),
        Spec("fcl", "Fluxo de caixa livre", "caixa", "R$ milhões", "maior", "acum",
             "fco - |capex|", lambda L, q: L("fco", acumulado(q)) - abs(L("capex", acumulado(q)))),
        Spec("capex_receita", "Capex / receita", "caixa", "%", "neutro", "acum",
             "|capex| / receita_liquida do acumulado",
             lambda L, q: _pct_receita(abs(L("capex", acumulado(q))), L, acumulado(q))),
    ]
    return specs


def _tem_mineracao(base: Base) -> bool:
    return any("minera" in s for chave in ("receita_liquida", "ebitda_ajustado", "volume_vendas")
               for s in base.escopos_segmento(chave))


def _specs_setor(base: Base, escopo: str, consolidado: bool) -> list[Spec]:
    # Por tonelada exige numerador e denominador do mesmo negócio: com mineração no grupo,
    # receita/CPV/EBITDA consolidados não podem ser divididos pelo volume de aço.
    mistura = consolidado and _tem_mineracao(base)
    motivo_nc = ("não comparável: o consolidado inclui mineração e o volume é de aço; "
                 "use o indicador do segmento siderúrgico")

    def por_t(valor_milhoes):
        return _bloqueado(NaoComparavel, motivo_nc) if mistura else _por_tonelada(valor_milhoes, escopo)

    specs = [
        Spec("volume_vendas", "Volume vendido", "setor", "mil t", "maior", "tri",
             "volume_vendas", _repasse("volume_vendas", escopo), escopo),
        Spec("receita_por_t", "Receita por tonelada", "setor", "R$/t", "maior", "tri",
             "receita_liquida × 1000 / volume_vendas (mesmo escopo)",
             por_t(lambda L, q: L("receita_liquida", q, escopo)), escopo),
        Spec("custo_por_t", "CPV por tonelada", "setor", "R$/t", "menor", "tri",
             "|cpv| × 1000 / volume_vendas (mesmo escopo)",
             por_t(lambda L, q: abs(L("cpv", q, escopo))), escopo),
    ]
    for crit in CRITERIOS_EBITDA:
        rotulo = "contábil" if crit == "contabil" else "ajustado"
        specs.append(Spec(
            f"ebitda_por_t_{crit}", f"EBITDA {rotulo} por tonelada", "setor", "R$/t", "maior", "tri",
            f"ebitda_{crit} × 1000 / volume_vendas (mesmo escopo)",
            por_t(lambda L, q, c=crit: _ebitda(L, q, c, escopo)), escopo))
    specs.append(Spec(
        "utilizacao_capacidade", "Utilização da capacidade", "setor", "%", "maior", "tri",
        "volume_producao × 4 / capacidade_instalada (trimestre anualizado, sem sazonalidade)",
        lambda L, q: _div(L("volume_producao", q, escopo) * 4,
                          L("capacidade_instalada", q, escopo), "capacidade zero") * 100, escopo))
    return specs


# Fatos reportados que entram como estão (só quando existirem).
_REPASSES = [
    ("volume_producao", "Produção de aço bruto", "setor", "maior", "tri"),
    ("capacidade_instalada", "Capacidade instalada", "setor", "maior", "saldo"),
    ("receita_por_t_reportada", "Receita por tonelada (reportada)", "setor", "maior", "tri"),
    ("custo_por_t_reportado", "Custo por tonelada (reportado)", "setor", "menor", "tri"),
    ("ebitda_por_t_reportado", "EBITDA por tonelada (reportado)", "setor", "maior", "tri"),
    ("volume_minerio", "Vendas de minério", "setor", "maior", "tri"),
    ("participacao_exportacao", "Participação da exportação", "setor", "neutro", "tri"),
    ("divida_liquida_reportada", "Dívida líquida (reportada)", "endividamento", "menor", "saldo"),
    ("dl_ebitda_reportado", "Dívida líquida / EBITDA (reportado)", "endividamento", "menor", "saldo"),
]


# --- Avaliação ----------------------------------------------------------------------
def variacao(atual: float | None, anterior: float | None, unidade: str | None):
    """(variação, motivo da omissão). % e x: diferença; demais: variação percentual."""
    if atual is None or anterior is None:
        return None, None
    if unidade in ("%", "x"):
        return round(atual - anterior, 4), None
    if anterior <= 0 or atual < 0:
        return None, "variação omitida: base negativa ou zero"
    return round((atual / anterior - 1) * 100, 4), None


def _unidade_var(unidade: str | None) -> str:
    return {"%": "p.p.", "x": "x"}.get(unidade or "", "%")


def _sem_repeticao(insumos: list[dict]) -> list[dict]:
    vistos, saida = set(), []
    for i in insumos:
        chave = tuple(sorted(i.items()))
        if chave not in vistos:
            vistos.add(chave)
            saida.append(i)
    return saida


def avaliar(spec: Spec, base: Base, tri: str) -> dict:
    papeis = {"atual": tri, "aa": periodo_aa(tri)}
    if spec.base != "acum":
        papeis["tt"] = periodo_tt(tri)
    if spec.base == "saldo":
        papeis["ano"] = fim_exercicio_anterior(tri)
    rotulo = acumulado if spec.base == "acum" else (lambda q: q)

    valores, insumos, motivos, unidade = {}, [], {}, spec.unidade
    for papel, q in papeis.items():
        L = Leitor(base)
        try:
            v = spec.calc(L, q)
        except Indisponivel as erro:
            valores[rotulo(q)], motivos[papel] = None, erro
            continue
        valores[rotulo(q)] = round(v, 4)
        insumos += L.insumos
        unidade = unidade or L.unidade

    atual = valores[rotulo(tri)]
    status = "ok" if atual is not None else motivos["atual"].status
    var_aa, omit_aa = variacao(atual, valores[rotulo(papeis["aa"])], unidade)
    motivo_atual = str(motivos["atual"]) if "atual" in motivos else None
    obs = [o for o in (spec.obs, motivo_atual, omit_aa and f"A/A: {omit_aa}") if o]
    item = {
        "chave": spec.chave, "nome": spec.nome, "grupo": spec.grupo, "unidade": unidade,
        "melhor": spec.melhor, "escopo": spec.escopo,
        "periodo": rotulo(tri), "periodo_aa": rotulo(papeis["aa"]), "periodo_tt": None,
        "valores": valores, "var_aa": var_aa, "var_tt": None, "unidade_var": _unidade_var(unidade),
    }
    if "tt" in papeis:
        var_tt, omit_tt = variacao(atual, valores[papeis["tt"]], unidade)
        item.update(periodo_tt=papeis["tt"], var_tt=var_tt)
        if omit_tt:
            obs.append(f"T/T: {omit_tt}")
    if spec.base == "saldo":
        var_ano, omit_ano = variacao(atual, valores[papeis["ano"]], unidade)
        item.update(periodo_ano=papeis["ano"], var_ano=var_ano)
        if omit_ano:
            obs.append(f"vs. {papeis['ano']}: {omit_ano}")
    item.update(formula=spec.formula, insumos=_sem_repeticao(insumos),
                disponivel=atual is not None, status=status, obs="; ".join(obs) or None)
    return item


def _algum_valor(item: dict) -> bool:
    return any(v is not None for v in item["valores"].values())


def _mix_segmentos(base: Base, tri: str, chave_fato: str, chave: str, nome: str) -> list[dict]:
    """Participação de cada segmento na soma dos segmentos (as eliminações ficam de fora)."""
    segmentos = base.escopos_segmento(chave_fato)
    if len(segmentos) < 2:
        return []
    periodos = {"atual": tri, "aa": periodo_aa(tri), "tt": periodo_tt(tri)}
    partes = {s: {} for s in segmentos}
    insumos: list[dict] = []
    negativo = False
    for q in periodos.values():
        valores = {s: base.dados.get((chave_fato, q, s)) for s in segmentos}
        total = sum(v.valor for v in valores.values() if v is not None)
        if any(v is None for v in valores.values()) or total <= 0:
            for s in segmentos:
                partes[s][q] = None
            continue
        negativo |= any(v.valor < 0 for v in valores.values())
        insumos += [v.fonte for v in valores.values()]
        for s, v in valores.items():
            partes[s][q] = round(v.valor / total * 100, 4)
    itens = []
    for s in segmentos:
        vals = partes[s]
        atual = vals[tri]
        obs = ["participação na soma dos segmentos, sem eliminações"]
        if negativo:
            obs.append("há segmento com valor negativo")
        if atual is None:
            obs.append(f"faltam dados de algum segmento em {tri}")
        itens.append({
            "chave": chave, "nome": nome, "grupo": "segmentos", "unidade": "%", "melhor": "neutro",
            "escopo": s, "periodo": tri, "periodo_aa": periodos["aa"], "periodo_tt": periodos["tt"],
            "valores": vals,
            "var_aa": variacao(atual, vals[periodos["aa"]], "%")[0],
            "var_tt": variacao(atual, vals[periodos["tt"]], "%")[0], "unidade_var": "p.p.",
            "formula": f"{chave_fato} do segmento / soma de {chave_fato} dos segmentos",
            "insumos": _sem_repeticao([i for i in insumos if i["escopo"] == s]),
            "disponivel": atual is not None, "status": "ok" if atual is not None else "ausente",
            "obs": "; ".join(obs),
        })
    return [i for i in itens if _algum_valor(i)]


def _alertas_derivados(base: Base, tri: str) -> list[dict]:
    alertas = []
    for q in (tri, periodo_aa(tri), periodo_tt(tri)):
        ajustes = base.ajustes.get((q, "consolidado"))
        ebitda = base.dados.get(("ebitda_ajustado", q, "consolidado"))
        if not ajustes or ebitda is None or ebitda.valor == 0:
            continue
        peso = sum(abs(a["valor"]) for a in ajustes) / abs(ebitda.valor)
        if peso > LIMITE_EFEITO_PONTUAL:
            descricoes = "; ".join(a["descricao"] or "sem descrição" for a in ajustes)
            alertas.append({"tipo": "efeito_pontual", "periodo": q, "texto": (
                f"ajustes não recorrentes somam {peso * 100:.0f}% do EBITDA ajustado do {q} "
                f"({descricoes}); variações contra esse período podem enganar")})
    calculada, reportada = Leitor(base), base.dados.get(("divida_liquida_reportada", tri, "consolidado"))
    try:
        dl = _divida_liquida(calculada, tri)
    except Faltando:
        dl = None
    if dl is not None and reportada is not None and \
            _diferenca_relativa(dl, reportada.valor) > TOLERANCIA_DEFINICAO:
        alertas.append({"tipo": "divergencia_definicao", "periodo": tri, "texto": (
            f"dívida líquida calculada ({dl:.1f}) difere da reportada ({reportada.valor:.1f}, "
            f"{reportada.fonte['documento']} p.{reportada.fonte['pagina']}) em "
            f"{_diferenca_relativa(dl, reportada.valor) * 100:.0f}%; conferir o critério "
            f"(arrendamentos, derivativos, aplicações de longo prazo)")})
    return alertas


def calcular(fatos: list[dict], empresa: str, tri: str, setor: str = SETOR_SIDERURGIA,
             aliquota_nominal: float = ALIQUOTA_NOMINAL) -> dict:
    """Função pura: fatos do contrato -> conteúdo de <slug>_<tri>_indicadores.json."""
    _partes(tri)
    if not 0 <= aliquota_nominal < 1:
        raise ValueError(f"alíquota nominal fora de [0, 1): {aliquota_nominal}")
    base = Base(fatos)
    siderurgia = setor == SETOR_SIDERURGIA

    itens = [avaliar(s, base, tri) for s in _specs_consolidadas(tri, aliquota_nominal)]
    specs_setor = _specs_setor(base, "consolidado", consolidado=True)
    if not siderurgia:  # métricas por tonelada não se aplicam a outros setores
        motivo = f"métrica de siderurgia; setor da empresa: {setor}"
        specs_setor = [replace(s, calc=_bloqueado(NaoAplicavel, motivo)) for s in specs_setor]
    itens += [avaliar(s, base, tri) for s in specs_setor]
    if siderurgia:
        for escopo in base.escopos_segmento("volume_vendas"):
            itens += [i for i in (avaliar(s, base, tri) for s in _specs_setor(base, escopo, False))
                      if _algum_valor(i)]
    for chave, nome, grupo, melhor, tipo in _REPASSES:
        if grupo == "setor" and not siderurgia:
            continue
        for escopo in ["consolidado", *base.escopos_segmento(chave)]:
            if base.tem(chave, escopo):
                spec = Spec(chave, nome, grupo, None, melhor, tipo, f"{chave} (reportado)",
                            _repasse(chave, escopo), escopo)
                itens.append(avaliar(spec, base, tri))
    itens += _mix_segmentos(base, tri, "receita_liquida", "participacao_receita", "Participação na receita")
    itens += _mix_segmentos(base, tri, "ebitda_ajustado", "participacao_ebitda",
                            "Participação no EBITDA ajustado")

    ajustes = {q: lista for (q, escopo), lista in sorted(base.ajustes.items()) if escopo == "consolidado"}
    cobertura = {s: sum(i["status"] == s for i in itens) for s in STATUS}
    return {
        "empresa": empresa,
        "periodo": tri,
        "setor": setor,
        "unidade_monetaria": "R$ milhões",
        "unidade_volume": "mil t",
        "anualizacao": f"{acumulado(tri)} × {_texto_fator(tri)}",
        "saldos_medios": f"média de {fim_exercicio_anterior(tri)} e {tri}",
        "politica_tributaria": (
            f"ROIC usa a alíquota efetiva do {acumulado(tri)} (-IR/CSLL ÷ LAIR), limitada entre 0% e "
            f"{aliquota_nominal:.0%}; com LAIR <= 0, usa {aliquota_nominal:.0%}. Hipótese metodológica, "
            f"não dado reportado"),
        "criterios_ebitda": list(CRITERIOS_EBITDA),
        "nota_criterio": ("indicadores com EBITDA vêm nas duas versões (_contabil e _ajustado); "
                          "o comparativo usa o mesmo critério para as duas empresas"),
        "legenda_status": {"ok": "valor", "ausente": "N/D", "nao_comparavel": "N/C",
                           "nao_aplicavel": "N/A"},
        "cobertura": cobertura,
        "indicadores": itens,
        "ajustes_ebitda": ajustes,
        "alertas": base.alertas + _alertas_derivados(base, tri),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Calcula os indicadores de uma empresa a partir dos fatos verificados.")
    ap.add_argument("--empresa", required=True, help="slug, ex.: gerdau")
    ap.add_argument("--tri", required=True, help="trimestre, ex.: 3T26")
    ap.add_argument("--metricas", default=str(RAIZ / "metricas"), help="pasta dos JSONs de fatos")
    ap.add_argument("--saida", help="arquivo de saída (padrão: <metricas>/<slug>_<tri>_indicadores.json)")
    ap.add_argument("--setor", default=SETOR_SIDERURGIA,
                    help="setor da empresa; fora de siderurgia, as métricas por tonelada ficam N/A")
    ap.add_argument("--aliquota-nominal", type=float, default=ALIQUOTA_NOMINAL,
                    help="teto da alíquota efetiva e valor usado com LAIR <= 0 no ROIC (padrão: 0.34)")
    a = ap.parse_args(argv)

    fatos = carregar_fatos(a.empresa, a.tri, pasta=a.metricas)
    if not fatos:
        raise SystemExit(f"Nenhum fato em {a.metricas}/{a.empresa}_{a.tri}_*.json")
    resultado = calcular(fatos, a.empresa, a.tri, setor=a.setor, aliquota_nominal=a.aliquota_nominal)
    saida = Path(a.saida) if a.saida else Path(a.metricas) / f"{a.empresa}_{a.tri}_indicadores.json"
    saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    c = resultado["cobertura"]
    print(f"{a.empresa} {a.tri}: {c['ok']}/{len(resultado['indicadores'])} com valor "
          f"(N/D {c['ausente']}, N/C {c['nao_comparavel']}, N/A {c['nao_aplicavel']}), "
          f"{len(resultado['alertas'])} alertas -> {saida}")
    for alerta in resultado["alertas"]:
        print(f"  [{alerta['tipo']}] {alerta['texto']}")


if __name__ == "__main__":
    main()
