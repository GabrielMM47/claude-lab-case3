"""
Case 3 — comparativo entre duas empresas (CASE-05).

Lê dois `metricas/<slug>_<tri>_indicadores.json` (saída do CASE-04) e monta
`saida/comparativo/<a>_x_<b>_<tri>/` com `comparativo.json`, `tabela.csv`, `tabela.md`
e (salvo `--sem-graficos`) `graficos/*.png`. Nenhum número é digitado aqui: tudo sai
dos indicadores. Nada é específico de empresa: nomes, tickers e cores vêm de
`config/empresas.toml`; o resto vem dos indicadores.

Rode da raiz do repositório:
    python src/comparar.py --a gerdau --b usiminas --tri 3T26
        [--metricas metricas] [--config config/empresas.toml]
        [--saida saida/comparativo] [--sem-graficos]

Código de saída: 0 = ok; 1 = indicadores ausentes/ilegíveis; 2 = entradas incompatíveis
ou comparativo fora do contrato (schemas/comparativo.schema.json).
Spec: docs/superpowers/specs/2026-11-06-case05-comparativo-design.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contrato  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent

# Paleta neutra de reserva: slug fora do TOML ou cor repetida entre A e B.
CORES_RESERVA = ("#6c757d", "#343a40", "#adb5bd", "#495057")

PRIORIDADE_CRITERIO = ("ajustado", "contabil")
ESCOPO_CONSOLIDADO = "consolidado"
PREFIXO_SEGMENTO = "segmento:"
NOME_DOCUMENTO = {"itr": "ITR", "apresentacao": "Apresentação"}

# Catálogo de linhas: (chave da linha, indicador de origem, grupo, melhor).
# "{c}" = critério de EBITDA escolhido. melhor = "indicador" usa o do indicador
# (neutro -> null); None = a linha nunca tem vencedor (escala/caixa/neutro).
CATALOGO: tuple[tuple[str, str, str, str | None], ...] = (
    ("receita_liquida", "receita_liquida", "escala", None),
    ("ebitda_{c}", "ebitda_{c}", "escala", None),
    ("lucro_liquido", "lucro_liquido", "escala", None),
    ("margem_bruta", "margem_bruta", "margens", "indicador"),
    ("margem_ebitda", "margem_ebitda_{c}", "margens", "indicador"),
    ("margem_ebit", "margem_ebit", "margens", "indicador"),
    ("margem_liquida", "margem_liquida", "margens", "indicador"),
    ("divida_liquida", "divida_liquida", "endividamento", None),
    ("dl_ebitda", "dl_ebitda_{c}", "endividamento", "indicador"),
    ("divida_liquida_pl", "divida_liquida_pl", "endividamento", "indicador"),
    ("roe", "roe", "rentabilidade", "indicador"),
    ("roa", "roa", "rentabilidade", "indicador"),
    ("roic", "roic", "rentabilidade", "indicador"),
    ("fco", "fco", "caixa", None),
    ("fcl", "fcl", "caixa", None),
    ("capex_receita", "capex_receita", "caixa", None),
    ("volume_vendas", "volume_vendas", "setor", None),
    ("receita_por_t", "receita_por_t", "setor", "indicador"),
    ("ebitda_por_t", "ebitda_por_t_{c}", "setor", "indicador"),
)
# Linha opcional: entra logo após `dl_ebitda` se algum lado tiver o indicador consolidado.
LINHA_REPORTADA = ("dl_ebitda_reportado", "dl_ebitda_reportado", "endividamento", "indicador")

# Nome/unidade quando nenhum lado tem o indicador (ou não há critério comum de EBITDA).
NOME_PADRAO = {
    "ebitda": "EBITDA", "margem_ebitda": "Margem EBITDA", "dl_ebitda": "Dívida líquida / EBITDA",
    "ebitda_por_t": "EBITDA por tonelada",
}
UNIDADE_PADRAO = {"ebitda": None, "margem_ebitda": "%", "dl_ebitda": "x", "ebitda_por_t": "R$/t"}

LINHAS_RENTABILIDADE = ("roe", "roa", "roic")
LINHAS_PL = ("roe", "divida_liquida_pl")              # base = PL
LINHAS_DL_EBITDA = ("dl_ebitda", "dl_ebitda_reportado")   # base = EBITDA
ROTULO_METODOLOGIA = {"anualizacao": "anualização", "saldos_medios": "saldos médios"}
TIPOS_REPASSADOS = ("efeito_pontual", "divergencia", "divergencia_definicao")

OBS_INEXISTENTE = "indicador não calculado pelo CASE-04"
OBS_SEM_CRITERIO = "sem EBITDA de mesmo critério nas duas empresas"
MOTIVO_NEUTRO = "indicador de escala/neutro: maior não é melhor"
MOTIVO_INDISPONIVEL = "valor indisponível ou não comparável em um dos lados"
MOTIVO_UNIDADE = "unidades diferentes entre as empresas"
MOTIVO_PERIODO = "períodos diferentes entre as empresas"
MOTIVO_EBITDA = "EBITDA negativo ou zero em um dos lados: múltiplo sem leitura"
MOTIVO_PL = "PL negativo ou zero em um dos lados: indicador sem leitura"
MOTIVO_IGUAIS = "valores iguais"

RE_TRI = re.compile(r"\b([1-4])T(\d{2})\b")
LADOS = ("a", "b")


# --------------------------------------------------------------------------- utilidades

def _outro(lado: str) -> str:
    return "b" if lado == "a" else "a"


def _num(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _sinal(x: float | None) -> int | None:
    if x is None:
        return None
    return (x > 0) - (x < 0)


def _minusc(texto: str) -> str:
    """Primeira letra minúscula, preservando siglas (`Margem EBITDA` -> `margem EBITDA`)."""
    if len(texto) > 1 and texto[:2].isupper():
        return texto
    return texto[:1].lower() + texto[1:]


def _base_aa(tri: str) -> str | None:
    m = RE_TRI.fullmatch(tri)
    return f"{m.group(1)}T{int(m.group(2)) - 1:02d}" if m else None


def _base_tt(tri: str) -> str | None:
    m = RE_TRI.fullmatch(tri)
    if not m:
        return None
    q, a = int(m.group(1)), int(m.group(2))
    return f"{q - 1}T{a:02d}" if q > 1 else f"4T{a - 1:02d}"


def _fonte(insumo: dict) -> tuple[str, int] | None:
    pagina = insumo.get("pagina")
    if not isinstance(pagina, int) or isinstance(pagina, bool):
        return None
    doc = str(insumo.get("documento") or "").strip()
    nome = NOME_DOCUMENTO.get(doc.lower(), doc[:1].upper() + doc[1:] if doc else "Documento")
    return nome, pagina


def fontes_de(insumos: list[dict] | None) -> list[str]:
    """`insumos` -> ["ITR p.29", "Apresentação p.12"], sem repetição, por documento e página."""
    pares = {f for f in (_fonte(i) for i in insumos or [] if isinstance(i, dict)) if f}
    return [f"{doc} p.{pag}" for doc, pag in sorted(pares)]


def _juntar_fontes(*listas: list[str]) -> list[str]:
    pares = set()
    for lista in listas:
        for f in lista:
            m = re.fullmatch(r"(.+) p\.(\d+)", f)
            if m:
                pares.add((m.group(1), int(m.group(2))))
    return [f"{doc} p.{pag}" for doc, pag in sorted(pares)]


def _indice(ind: dict) -> dict[tuple[str, str], dict]:
    """(chave, escopo) -> indicador."""
    return {(i.get("chave"), i.get("escopo") or ESCOPO_CONSOLIDADO): i
            for i in ind.get("indicadores") or [] if isinstance(i, dict)}


def _consolidado(ind: dict, chave: str) -> dict | None:
    return _indice(ind).get((chave, ESCOPO_CONSOLIDADO))


# --------------------------------------------------------------------------- configuração

def carregar_config(caminho: Path) -> dict:
    """config/empresas.toml -> {slug: {nome, ticker, cor}}. Arquivo ausente -> {}."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return {}
    with caminho.open("rb") as f:
        dados = tomllib.load(f)
    saida = {}
    for slug, info in (dados.get("empresas") or {}).items():
        if not isinstance(info, dict):
            continue
        saida[slug] = {"nome": info.get("nome") or _nome_padrao(slug),
                       "ticker": info.get("ticker"),
                       "cor": info.get("cor")}
    return saida


def carregar_rotulos_segmentos(caminho: Path) -> dict:
    """Tabela [segmentos] de config/empresas.toml -> {slug_do_segmento: rótulo}. Ausente -> {}."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return {}
    with caminho.open("rb") as f:
        dados = tomllib.load(f)
    return {k: v for k, v in (dados.get("segmentos") or {}).items() if isinstance(v, str) and v.strip()}


def rotulo_segmento(segmento: str, rotulos: dict | None = None) -> str:
    """Rótulo legível: o da config, senão o slug sem '_' e com a primeira letra maiúscula."""
    if rotulos and segmento in rotulos:
        return rotulos[segmento]
    texto = segmento.replace("_", " ").strip()
    return texto[:1].upper() + texto[1:] if texto else segmento


def _nome_padrao(slug: str) -> str:
    return slug.replace("_", " ").strip().title() or slug


def _cor_valida(cor: Any) -> bool:
    return isinstance(cor, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", cor) is not None


def _empresas(slug_a: str, slug_b: str, cfg: dict) -> tuple[dict, list[dict]]:
    """Identificação dos lados (com fallback) e os alertas `config`."""
    empresas, alertas, usadas = {}, [], set()
    for lado, slug in (("a", slug_a), ("b", slug_b)):
        info = cfg.get(slug)
        if info is None:
            alertas.append({"tipo": "config", "empresa": lado, "chaves": [], "fontes": [],
                            "texto": f"'{slug}' sem entrada em config/empresas.toml: nome "
                                     f"'{_nome_padrao(slug)}', sem ticker e cor da paleta de reserva"})
            info = {"nome": _nome_padrao(slug), "ticker": None, "cor": None}
        cor = info.get("cor") if _cor_valida(info.get("cor")) else None
        if cor is not None and cor.lower() in usadas:
            alertas.append({"tipo": "config", "empresa": lado, "chaves": [], "fontes": [],
                            "texto": f"'{slug}' tem a mesma cor da outra empresa em "
                                     "config/empresas.toml; usada a cor da paleta de reserva"})
            cor = None
        if cor is None:
            cor = next(c for c in CORES_RESERVA if c.lower() not in usadas)
        usadas.add(cor.lower())
        empresas[lado] = {"slug": slug, "nome": info.get("nome") or _nome_padrao(slug),
                          "ticker": info.get("ticker"), "cor": cor}
    return empresas, alertas


# --------------------------------------------------------------------------- compatibilidade

def validar_compatibilidade(ind_a: dict, ind_b: dict, tri: str) -> tuple[list[dict], list[str]]:
    """(alertas, erros_fatais). Fatal: período != tri, unidade monetária diferente, mesmo slug."""
    erros: list[str] = []
    alertas: list[dict] = []
    for lado, ind in (("A", ind_a), ("B", ind_b)):
        if ind.get("periodo") != tri:
            erros.append(f"empresa {lado} ({ind.get('empresa')}): período {ind.get('periodo')!r} "
                         f"diferente do pedido {tri!r}")
    if ind_a.get("unidade_monetaria") != ind_b.get("unidade_monetaria"):
        erros.append(f"unidade monetária diferente: {ind_a.get('unidade_monetaria')!r} × "
                     f"{ind_b.get('unidade_monetaria')!r}")
    if ind_a.get("empresa") and ind_a.get("empresa") == ind_b.get("empresa"):
        erros.append(f"as duas entradas são da mesma empresa ({ind_a.get('empresa')!r})")

    difs = [campo for campo in ROTULO_METODOLOGIA if ind_a.get(campo) != ind_b.get(campo)]
    if difs:
        partes = "; ".join(f"{ROTULO_METODOLOGIA[campo]}: {ind_a.get('empresa')} = {ind_a.get(campo)!r}, "
                           f"{ind_b.get('empresa')} = {ind_b.get(campo)!r}" for campo in difs)
        alertas.append({"tipo": "metodologia", "empresa": None,
                        "chaves": [*LINHAS_RENTABILIDADE, "dl_ebitda"], "fontes": [],
                        "texto": f"metodologia diferente entre as empresas ({partes}); "
                                 "rentabilidade e DL/EBITDA ficam N/C"})
    if ind_a.get("unidade_volume") != ind_b.get("unidade_volume"):
        alertas.append({"tipo": "unidade", "empresa": None, "chaves": ["volume_vendas"], "fontes": [],
                        "texto": f"unidade de volume diferente: {ind_a.get('unidade_volume')!r} × "
                                 f"{ind_b.get('unidade_volume')!r}"})
    if ind_a.get("setor") != ind_b.get("setor"):
        alertas.append({"tipo": "negocios_diferentes", "empresa": None, "chaves": [], "fontes": [],
                        "texto": f"setores diferentes: {ind_a.get('setor')!r} × {ind_b.get('setor')!r}"})
    return alertas, erros


def _criterios(ind: dict) -> list[str]:
    lista = ind.get("criterios_ebitda")
    if isinstance(lista, list):
        return [c for c in lista if isinstance(c, str)]
    chaves = {i.get("chave") for i in ind.get("indicadores") or [] if isinstance(i, dict)}
    return [c for c in PRIORIDADE_CRITERIO if f"ebitda_{c}" in chaves]


def escolher_criterio(ind_a: dict, ind_b: dict) -> str | None:
    """'ajustado' se as duas têm, senão 'contabil', senão None."""
    ca, cb = set(_criterios(ind_a)), set(_criterios(ind_b))
    return next((c for c in PRIORIDADE_CRITERIO if c in ca and c in cb), None)


# --------------------------------------------------------------------------- linhas

def _catalogo(ind_a: dict, ind_b: dict) -> list[tuple[str, str, str, str | None]]:
    linhas = list(CATALOGO)
    chave_rep = LINHA_REPORTADA[1]
    if _consolidado(ind_a, chave_rep) or _consolidado(ind_b, chave_rep):
        pos = next(i for i, l in enumerate(linhas) if l[0] == "dl_ebitda")
        linhas.insert(pos + 1, LINHA_REPORTADA)
    return linhas


def _periodos(indicador: dict | None, periodo: str) -> list[str]:
    if not indicador:
        return [periodo]
    ps = [periodo, indicador.get("periodo_aa"), indicador.get("periodo_tt")]
    return list(dict.fromkeys(p for p in ps if isinstance(p, str) and p))


def _lado(indicador: dict | None, periodo: str, unidade: str | None,
          forcar: tuple[str, str] | None = None) -> dict:
    """Um lado da linha. `forcar` = (status, obs) sobrepõe o do indicador."""
    if indicador is None:
        status, obs = forcar or ("ausente", OBS_INEXISTENTE)
        return {"valor": None, "texto": contrato.fmt_br(None, unidade, status=status),
                "valores": {periodo: None}, "var_aa": None, "var_tt": None, "unidade_var": None,
                "texto_var_aa": "—", "texto_var_tt": "—", "fontes": [], "disponivel": False,
                "status": status, "obs": obs}

    status = indicador.get("status")
    if status != "ok" and status not in contrato.TEXTO_STATUS:
        status = "ausente"
    obs = indicador.get("obs")
    per_ind = indicador.get("periodo") or periodo
    valores = {p: _num((indicador.get("valores") or {}).get(p)) for p in _periodos(indicador, per_ind)}
    valor = valores.get(per_ind)
    if status == "ok" and valor is None:
        status, obs = "ausente", obs or f"valor de {per_ind} ausente"
    if forcar:
        status, obs = forcar
    ok = status == "ok"
    if not ok:
        valor = None
        valores = {p: None for p in valores}
        if not obs:
            obs = contrato.TEXTO_STATUS.get(status, "N/D")
    var_aa = _num(indicador.get("var_aa")) if ok else None
    var_tt = _num(indicador.get("var_tt")) if ok else None
    unidade_var = indicador.get("unidade_var")
    casas_var = 2 if unidade_var == "x" else 1
    return {"valor": valor, "texto": contrato.fmt_br(valor, unidade, status=status),
            "valores": valores, "var_aa": var_aa, "var_tt": var_tt, "unidade_var": unidade_var,
            "texto_var_aa": contrato.fmt_var(var_aa, unidade_var, casas_var),
            "texto_var_tt": contrato.fmt_var(var_tt, unidade_var, casas_var),
            "fontes": fontes_de(indicador.get("insumos")), "disponivel": ok,
            "status": status, "obs": obs}


def _sinal_base(ind: dict, linha: str, criterio: str | None, periodo: str) -> int | None:
    """Sinal da base (EBITDA ou PL) do indicador `linha` de uma empresa; None = indeterminado.

    EBITDA: o do critério no período (se <= 0, base não positiva) e o sinal implícito em DL ÷ (DL/EBITDA).
    PL: sinal implícito em DL ÷ (DL/PL) no período do balanço.
    """
    def valor(chave: str, per: str) -> float | None:
        i = _consolidado(ind, chave)
        if not i or i.get("status") != "ok":
            return None
        return _num((i.get("valores") or {}).get(per))

    def implicito(chave_dl: str, chave_ratio: str, per: str) -> int | None:
        dl, r = _sinal(valor(chave_dl, per)), _sinal(valor(chave_ratio, per))
        if not dl or not r:
            return None
        return dl * r

    if linha in LINHAS_DL_EBITDA:
        sinais = []
        if criterio:
            sinais.append(_sinal(valor(f"ebitda_{criterio}", periodo)))
        if linha == "dl_ebitda" and criterio:
            sinais.append(implicito("divida_liquida", f"dl_ebitda_{criterio}", periodo))
        if linha == "dl_ebitda_reportado":
            dl = "divida_liquida_reportada" if _consolidado(ind, "divida_liquida_reportada") else "divida_liquida"
            sinais.append(implicito(dl, "dl_ebitda_reportado", periodo))
        conhecidos = [s for s in sinais if s is not None]
        if not conhecidos:
            return None
        return min(conhecidos)
    if linha in LINHAS_PL:
        dl_pl = _consolidado(ind, "divida_liquida_pl")
        per = (dl_pl or {}).get("periodo") or periodo
        return implicito("divida_liquida", "divida_liquida_pl", per)
    return 1


def _vencedor(linha: dict, ind: dict[str, dict], criterio: str | None) -> tuple[str | None, str | None]:
    melhor = linha["melhor"]
    a, b = linha["a"], linha["b"]
    if melhor not in ("maior", "menor"):
        return None, MOTIVO_NEUTRO
    if a["status"] != "ok" or b["status"] != "ok" or a["valor"] is None or b["valor"] is None:
        return None, MOTIVO_INDISPONIVEL
    if linha.get("_unidades_diferentes"):
        return None, MOTIVO_UNIDADE
    if linha.get("_periodos_diferentes"):
        return None, MOTIVO_PERIODO
    chave = linha["chave"]
    if chave in LINHAS_DL_EBITDA or chave in LINHAS_PL:
        for lado in LADOS:
            s = _sinal_base(ind[lado], chave, criterio, linha["periodo"])
            if s is not None and s <= 0:
                return None, MOTIVO_EBITDA if chave in LINHAS_DL_EBITDA else MOTIVO_PL
    va, vb = a["valor"], b["valor"]
    if math.isclose(va, vb, rel_tol=1e-9, abs_tol=1e-12):
        return None, MOTIVO_IGUAIS
    a_maior = va > vb
    return ("a" if a_maior == (melhor == "maior") else "b"), None


def _montar_linha(entrada: tuple, ind: dict[str, dict], criterio: str | None,
                  forcar_nc: dict[str, str], tri: str) -> dict:
    chave_mod, origem_mod, grupo, regra = entrada
    tem_c = "{c}" in origem_mod
    base = origem_mod.replace("_{c}", "")
    chave = chave_mod.replace("_{c}", "") if (tem_c and criterio is None) else chave_mod.format(c=criterio)

    if tem_c and criterio is None:
        # Sem critério comum: nome/unidade de qualquer versão existente, só para rotular.
        alguma = next((i for lado in LADOS for c in PRIORIDADE_CRITERIO
                       if (i := _consolidado(ind[lado], origem_mod.format(c=c)))), None)
        ind_lados = {lado: None for lado in LADOS}
        forcar = ("nao_comparavel", OBS_SEM_CRITERIO)
        nome = NOME_PADRAO.get(base, base)
        unidade = (alguma or {}).get("unidade") or UNIDADE_PADRAO.get(base)
        melhor_ind = (alguma or {}).get("melhor")
        periodo = (alguma or {}).get("periodo") or tri
    else:
        origem = origem_mod.format(c=criterio)
        ind_lados = {lado: _consolidado(ind[lado], origem) for lado in LADOS}
        forcar = None
        ref = ind_lados["a"] or ind_lados["b"]
        nome = (ref or {}).get("nome") or NOME_PADRAO.get(base, origem)
        unidade = (ref or {}).get("unidade") or UNIDADE_PADRAO.get(base)
        melhor_ind = (ref or {}).get("melhor")
        periodo = (ref or {}).get("periodo") or tri
    if unidade is None:
        unidade = ind["a"].get("unidade_monetaria") or ind["b"].get("unidade_monetaria")
    if forcar is None and chave in forcar_nc:
        forcar = ("nao_comparavel", forcar_nc[chave])

    lados = {}
    for lado in LADOS:
        i = ind_lados[lado]
        if i is None and forcar is None:
            lados[lado] = _lado(None, periodo, unidade)
        elif i is None:
            lados[lado] = _lado(None, periodo, unidade, forcar)
        else:
            lados[lado] = _lado(i, i.get("periodo") or periodo, i.get("unidade") or unidade, forcar)

    melhor = None
    if regra == "indicador" and melhor_ind in ("maior", "menor"):
        melhor = melhor_ind
    linha = {"chave": chave, "nome": nome, "grupo": grupo, "unidade": unidade, "periodo": periodo,
             "melhor": melhor, "vencedor": None, "motivo_sem_vencedor": None,
             "a": lados["a"], "b": lados["b"]}
    ia, ib = ind_lados["a"], ind_lados["b"]
    if ia and ib:
        linha["_unidades_diferentes"] = ia.get("unidade") != ib.get("unidade")
        linha["_periodos_diferentes"] = ia.get("periodo") != ib.get("periodo")
    linha["vencedor"], linha["motivo_sem_vencedor"] = _vencedor(linha, ind, criterio)
    linha.pop("_unidades_diferentes", None)
    linha.pop("_periodos_diferentes", None)
    return linha


# --------------------------------------------------------------------------- segmentos

def _segmentos(ind: dict, tri: str, rotulos: dict | None = None) -> list[dict]:
    por_nome: dict[str, dict] = {}
    for i in ind.get("indicadores") or []:
        if not isinstance(i, dict):
            continue
        escopo = i.get("escopo") or ""
        campo = {"participacao_receita": "pct_receita", "participacao_ebitda": "pct_ebitda"}.get(i.get("chave"))
        if not campo or not escopo.startswith(PREFIXO_SEGMENTO):
            continue
        nome = escopo[len(PREFIXO_SEGMENTO):]
        seg = por_nome.setdefault(nome, {"segmento": nome, "rotulo": rotulo_segmento(nome, rotulos), "pct_receita": None, "pct_ebitda": None,
                                         "fontes": []})
        valor = _num((i.get("valores") or {}).get(tri)) if i.get("status") == "ok" else None
        seg[campo] = valor
        if valor is not None:
            seg["fontes"] = _juntar_fontes(seg["fontes"], fontes_de(i.get("insumos")))
    segs = [s for s in por_nome.values() if s["pct_receita"] is not None or s["pct_ebitda"] is not None]
    return sorted(segs, key=lambda s: (s["pct_receita"] is None, -(s["pct_receita"] or 0), s["segmento"]))


# --------------------------------------------------------------------------- alertas

def _chaves_ebitda(linhas: list[dict]) -> list[str]:
    return [l["chave"] for l in linhas
            if l["chave"].startswith("ebitda") or l["chave"] == "margem_ebitda"]


def _periodo_alerta(alerta: dict) -> str | None:
    per = alerta.get("periodo")
    if isinstance(per, str) and RE_TRI.fullmatch(per):
        return per
    m = RE_TRI.search(str(alerta.get("texto") or ""))
    return m.group(0) if m else None


def _alertas_indicadores(ind: dict, lado: str, linhas: list[dict], tri: str) -> list[dict]:
    chaves_linhas = {l["chave"] for l in linhas}
    saida, unidade = [], []
    for alerta in ind.get("alertas") or []:
        if not isinstance(alerta, dict):
            continue
        tipo = alerta.get("tipo")
        texto = str(alerta.get("texto") or "").strip()
        if tipo == "unidade":
            unidade.append(texto)
            continue
        if tipo not in TIPOS_REPASSADOS or not texto:
            continue
        fontes = fontes_de([v for v in alerta.get("valores") or [] if isinstance(v, dict)])
        if tipo == "efeito_pontual":
            per = _periodo_alerta(alerta)
            chaves = _chaves_ebitda(linhas) if per in (_base_aa(tri), _base_tt(tri), tri) else []
        else:
            escopo = alerta.get("escopo") or ESCOPO_CONSOLIDADO
            ch = alerta.get("chave")
            chaves = [ch] if ch in chaves_linhas and escopo == ESCOPO_CONSOLIDADO else []
        saida.append({"tipo": tipo, "empresa": lado, "texto": texto, "chaves": chaves, "fontes": fontes})
    if unidade:
        saida.append({"tipo": "unidade", "empresa": lado, "chaves": [], "fontes": [],
                      "texto": f"{len(unidade)} dado(s) ignorado(s) por unidade não suportada; "
                               f"ex.: {unidade[0]}"})
    return saida


def _alertas_indisponiveis(linhas: list[dict], empresas: dict) -> list[dict]:
    saida = []
    for lado in LADOS:
        nome = empresas[lado]["nome"]
        for l in linhas:
            s = l[lado]
            if s["status"] == "ok":
                continue
            motivo = f" ({s['obs']})" if s.get("obs") else ""
            saida.append({"tipo": "indisponivel", "empresa": lado, "chaves": [l["chave"]],
                          "fontes": s["fontes"], "texto": f"{l['nome']} da {nome}: {s['texto']}{motivo}"})
    return saida


def _alerta_negocios(segmentos: dict, linhas: list[dict], empresas: dict) -> dict | None:
    nomes = {lado: [s["segmento"] for s in segmentos[lado]] for lado in LADOS}
    rotulos = {lado: [s.get("rotulo") or s["segmento"] for s in segmentos[lado]] for lado in LADOS}
    difere = set(nomes["a"]) != set(nomes["b"])
    por_t_nc = [l["chave"] for l in linhas if "por_t" in l["chave"]
                and "nao_comparavel" in (l["a"]["status"], l["b"]["status"])]
    if not difere and not por_t_nc:
        return None
    partes = []
    if difere:
        desc = "; ".join(f"{empresas[lado]['nome']}: {', '.join(rotulos[lado]) or 'sem dados de segmento'}"
                         for lado in LADOS)
        partes.append(f"Segmentos diferentes ({desc})")
    if por_t_nc:
        partes.append("indicadores por tonelada N/C")
    fontes = _juntar_fontes(*(s["fontes"] for lado in LADOS for s in segmentos[lado]))
    return {"tipo": "negocios_diferentes", "empresa": None, "chaves": por_t_nc, "fontes": fontes,
            "texto": "; ".join(partes)}


# --------------------------------------------------------------------------- insights

def _linha(linhas: list[dict], chave: str) -> dict | None:
    return next((l for l in linhas if l["chave"] == chave), None)


def _ok(lado: dict) -> bool:
    return lado["status"] == "ok" and lado["valor"] is not None


def _insight_margem(linhas: list[dict], emp: dict) -> dict | None:
    candidatas = [l for l in linhas if l["chave"].startswith("margem_") and _ok(l["a"]) and _ok(l["b"])
                  and l["unidade"] == "%"]
    if not candidatas:
        return None
    l = max(candidatas, key=lambda x: abs(x["a"]["valor"] - x["b"]["valor"]))
    dif = l["a"]["valor"] - l["b"]["valor"]
    nome = _minusc(l["nome"])
    if round(abs(dif), 1) == 0:
        texto = (f"{emp['a']['nome']} e {emp['b']['nome']} têm {nome} praticamente igual "
                 f"({l['a']['texto']} × {l['b']['texto']})")
    else:
        x, y = ("a", "b") if dif > 0 else ("b", "a")
        texto = (f"{emp[x]['nome']} tem {nome} {contrato.fmt_br(abs(dif), 'p.p.')} acima da "
                 f"{emp[y]['nome']} ({l[x]['texto']} × {l[y]['texto']})")
    return {"id": "margem", "chaves": [l["chave"]], "texto": texto}


def _insight_crescimento(linhas: list[dict], emp: dict, criterio: str | None) -> dict | None:
    partes, chaves = [], []
    rotulos = [("receita_liquida", "Receita")]
    if criterio:
        rotulos.append((f"ebitda_{criterio}", None))
    for chave, rotulo in rotulos:
        l = _linha(linhas, chave)
        if not l or (l["a"]["var_aa"] is None and l["b"]["var_aa"] is None):
            continue
        rotulo = rotulo or l["nome"]
        partes.append(f"{rotulo} A/A: {emp['a']['nome']} {l['a']['texto_var_aa']}, "
                      f"{emp['b']['nome']} {l['b']['texto_var_aa']}")
        chaves.append(chave)
    if not partes:
        return None
    return {"id": "crescimento", "chaves": chaves, "texto": "; ".join(partes)}


def _insight_alavancagem(linhas: list[dict], emp: dict, ind: dict, criterio: str | None) -> dict | None:
    l = _linha(linhas, "dl_ebitda")
    if not l or not (_ok(l["a"]) or _ok(l["b"])):
        return None
    notas = []
    for lado in LADOS:
        s = _sinal_base(ind[lado], "dl_ebitda", criterio, l["periodo"]) if _ok(l[lado]) else None
        if s is not None and s <= 0:
            notas.append(f"EBITDA da {emp[lado]['nome']} negativo: múltiplo sem leitura")
        elif _ok(l[lado]) and l[lado]["valor"] < 0:
            notas.append(f"{emp[lado]['nome']} com caixa líquido")
    texto = (f"{l['nome'].replace('Dívida líquida', 'DL')}: {emp['a']['nome']} {l['a']['texto']}, "
             f"{emp['b']['nome']} {l['b']['texto']}")
    if notas:
        texto += f" ({'; '.join(notas)})"
    obs = list(dict.fromkeys(l[lado]["obs"] for lado in LADOS if l[lado].get("obs")))
    if obs:
        texto += "; " + "; ".join(obs)
    return {"id": "alavancagem", "chaves": ["dl_ebitda"], "texto": texto}


def _insight_por_tonelada(linhas: list[dict], emp: dict) -> dict | None:
    ls = [l for l in (_linha(linhas, "receita_por_t"), _linha(linhas, "ebitda_por_t")) if l]
    relevantes = [l for l in ls if any(_ok(l[x]) or l[x]["status"] == "nao_comparavel" for x in LADOS)]
    if not relevantes:
        return None
    partes, obs_ditas = [], set()
    for l in relevantes:
        lados = []
        for lado in LADOS:
            s = l[lado]
            txt = f"{emp[lado]['nome']} {s['texto']}"
            if s["status"] != "ok" and s.get("obs") and s["obs"] not in obs_ditas:
                txt += f" ({s['obs']})"
                obs_ditas.add(s["obs"])
            lados.append(txt)
        partes.append(f"{l['nome']}: {'; '.join(lados)}")
    return {"id": "por_tonelada", "chaves": [l["chave"] for l in relevantes], "texto": ". ".join(partes)}


def _insight_mix(segmentos: dict, emp: dict) -> dict | None:
    partes = []
    for lado in LADOS:
        com = [s for s in segmentos[lado] if s["pct_ebitda"] is not None]
        if not com:
            continue
        top = max(com, key=lambda s: (s["pct_ebitda"], s["segmento"]))
        partes.append(f"{emp[lado]['nome']}, {top.get('rotulo') or top['segmento']} ({contrato.fmt_br(top['pct_ebitda'], '%')})")
    if not partes:
        return None
    return {"id": "mix", "chaves": [], "texto": "Maior peso no EBITDA: " + "; ".join(partes)}


# --------------------------------------------------------------------------- montagem

def montar_comparativo(ind_a: dict, ind_b: dict, cfg: dict, tri: str,
                       rotulos_segmentos: dict | None = None) -> dict:
    """Comparativo completo (sem gráficos: `graficos` = []). ValueError se incompatível."""
    alertas_compat, erros = validar_compatibilidade(ind_a, ind_b, tri)
    if erros:
        raise ValueError("; ".join(erros))
    ind = {"a": ind_a, "b": ind_b}
    criterio = escolher_criterio(ind_a, ind_b)
    empresas, alertas_cfg = _empresas(str(ind_a.get("empresa")), str(ind_b.get("empresa")), cfg)

    forcar_nc: dict[str, str] = {}
    metod = next((a for a in alertas_compat if a["tipo"] == "metodologia"), None)
    if metod:
        difs = [ROTULO_METODOLOGIA[c] for c in ROTULO_METODOLOGIA if ind_a.get(c) != ind_b.get(c)]
        obs = f"não comparável: {' e '.join(difs)} {'diferentes' if len(difs) > 1 else 'diferente'} entre as empresas"
        forcar_nc = {chave: obs for chave in metod["chaves"]}

    linhas = [_montar_linha(e, ind, criterio, forcar_nc, tri) for e in _catalogo(ind_a, ind_b)]
    segmentos = {lado: _segmentos(ind[lado], tri, rotulos_segmentos) for lado in LADOS}

    insights = [i for i in (
        _insight_margem(linhas, empresas),
        _insight_crescimento(linhas, empresas, criterio),
        _insight_alavancagem(linhas, empresas, ind, criterio),
        _insight_por_tonelada(linhas, empresas),
        _insight_mix(segmentos, empresas),
    ) if i]

    alertas = [*alertas_cfg, *alertas_compat]
    for lado in LADOS:
        alertas += _alertas_indicadores(ind[lado], lado, linhas, tri)
    alertas += _alertas_indisponiveis(linhas, empresas)
    negocios = _alerta_negocios(segmentos, linhas, empresas)
    if negocios:
        alertas.append(negocios)

    def comum(campo: str) -> Any:
        va, vb = ind_a.get(campo), ind_b.get(campo)
        return va if va == vb else {"a": va, "b": vb}

    return {
        "periodo": tri,
        "criterio_ebitda": criterio,
        "empresas": empresas,
        "metodologia": {
            "unidade_monetaria": ind_a.get("unidade_monetaria"),
            "anualizacao": comum("anualizacao"),
            "saldos_medios": comum("saldos_medios"),
            "politica_tributaria": {"a": ind_a.get("politica_tributaria"), "b": ind_b.get("politica_tributaria")},
        },
        "linhas": linhas,
        "segmentos": segmentos,
        "insights": insights,
        "alertas": alertas,
        "graficos": [],
        "verificacao": None,
    }


# --------------------------------------------------------------------------- saída

def _tabela(comp: dict) -> tuple[list[str], list[list[str]]]:
    na, nb = comp["empresas"]["a"]["nome"], comp["empresas"]["b"]["nome"]
    cab = ["Indicador", "Unidade", "Período", na, f"{na} A/A", f"{na} T/T",
           nb, f"{nb} A/A", f"{nb} T/T", "Vencedor", "Fontes"]
    linhas = []
    for l in comp["linhas"]:
        venc = comp["empresas"][l["vencedor"]]["nome"] if l.get("vencedor") in LADOS else "—"
        fontes = "; ".join(f"{comp['empresas'][x]['nome']}: {', '.join(l[x].get('fontes') or []) or '—'}"
                           for x in LADOS)
        linhas.append([l["nome"], l.get("unidade") or "", l.get("periodo") or comp["periodo"],
                       l["a"].get("texto", ""), l["a"].get("texto_var_aa", "—"), l["a"].get("texto_var_tt", "—"),
                       l["b"].get("texto", ""), l["b"].get("texto_var_aa", "—"), l["b"].get("texto_var_tt", "—"),
                       venc, fontes])
    return cab, linhas


def escrever_saida(comp: dict, pasta: Path) -> None:
    """Grava comparativo.json, tabela.csv (separador ';') e tabela.md em `pasta`."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "comparativo.json").write_text(json.dumps(comp, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    cab, linhas = _tabela(comp)
    with (pasta / "tabela.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cab)
        w.writerows(linhas)

    def cel(x: str) -> str:
        return str(x).replace("|", "\\|")

    na, nb = comp["empresas"]["a"]["nome"], comp["empresas"]["b"]["nome"]
    criterio = comp.get("criterio_ebitda")
    md = [f"# {na} × {nb} — {comp['periodo']}", "",
          "| " + " | ".join(cel(c) for c in cab) + " |",
          "|" + "---|" * len(cab)]
    md += ["| " + " | ".join(cel(c) for c in l) + " |" for l in linhas]
    md += ["",
           f"Critério de EBITDA: {criterio} (o mesmo para as duas empresas)." if criterio else
           "Critério de EBITDA: sem critério comum às duas empresas; linhas com EBITDA ficam N/C.",
           "A/A = 3T26 × 3T25 (mesmo trimestre do ano anterior); T/T = contra o trimestre anterior."
           .replace("3T26", comp["periodo"]).replace("3T25", _base_aa(comp["periodo"]) or "ano anterior"),
           "Fontes: páginas na numeração do PDF (índice a partir de 1), não o número impresso na folha.",
           "N/D = não disponível; N/C = não comparável; N/A = não se aplica.",
           "",
           "Não constitui recomendação de investimento.", ""]
    (pasta / "tabela.md").write_text("\n".join(md), encoding="utf-8")


# --------------------------------------------------------------------------- CLI

def _ler_indicadores(pasta: Path, slug: str, tri: str) -> dict | None:
    caminho = Path(pasta) / f"{slug}_{tri}_indicadores.json"
    dica = f"rode `python src/indicadores.py --empresa {slug} --tri {tri}`"
    if not caminho.is_file():
        print(f"ERRO: indicadores não encontrados: {caminho}; {dica}", file=sys.stderr)
        return None
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"ERRO: indicadores ilegíveis em {caminho} ({e}); {dica}", file=sys.stderr)
        return None
    if not isinstance(dados, dict) or not isinstance(dados.get("indicadores"), list):
        print(f"ERRO: {caminho} não tem a lista 'indicadores'; {dica}", file=sys.stderr)
        return None
    return dados


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="comparar.py",
                                 description="Comparativo entre duas empresas a partir dos indicadores do CASE-04.")
    ap.add_argument("--a", required=True, help="slug da empresa A (ex.: gerdau)")
    ap.add_argument("--b", required=True, help="slug da empresa B (ex.: usiminas)")
    ap.add_argument("--tri", required=True, help="trimestre, ex.: 3T26")
    ap.add_argument("--metricas", default=str(RAIZ / "metricas"), help="pasta dos *_indicadores.json")
    ap.add_argument("--config", default=str(RAIZ / "config" / "empresas.toml"))
    ap.add_argument("--saida", default=str(RAIZ / "saida" / "comparativo"))
    ap.add_argument("--sem-graficos", action="store_true", help="não gera graficos/*.png")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)

    if args.a == args.b:
        print(f"ERRO: --a e --b são a mesma empresa ({args.a!r})", file=sys.stderr)
        return 2
    ind_a = _ler_indicadores(Path(args.metricas), args.a, args.tri)
    ind_b = _ler_indicadores(Path(args.metricas), args.b, args.tri)
    if ind_a is None or ind_b is None:
        return 1
    # O slug do arquivo manda (o do conteúdo pode faltar).
    ind_a.setdefault("empresa", args.a)
    ind_b.setdefault("empresa", args.b)

    alertas, erros = validar_compatibilidade(ind_a, ind_b, args.tri)
    if erros:
        for e in erros:
            print(f"ERRO: {e}", file=sys.stderr)
        return 2
    comp = montar_comparativo(ind_a, ind_b, carregar_config(Path(args.config)), args.tri,
                              carregar_rotulos_segmentos(Path(args.config)))
    pasta = Path(args.saida) / f"{args.a}_x_{args.b}_{args.tri}"
    pasta.mkdir(parents=True, exist_ok=True)

    if not args.sem_graficos:
        import graficos  # só aqui: com --sem-graficos o comparativo não depende do matplotlib
        comp["graficos"] = graficos.gerar_graficos(comp, pasta)

    erros_contrato = contrato.validar(comp, "comparativo")
    if erros_contrato:
        print(f"ERRO: comparativo fora do contrato ({len(erros_contrato)} erro(s)):", file=sys.stderr)
        for e in erros_contrato[:contrato.LIMITE_LINHAS]:
            print(f"  {e}", file=sys.stderr)
        return 2
    escrever_saida(comp, pasta)

    vencedores = sum(1 for l in comp["linhas"] if l["vencedor"])
    print(f"{comp['empresas']['a']['nome']} × {comp['empresas']['b']['nome']} {args.tri}: "
          f"critério de EBITDA {comp['criterio_ebitda'] or 'sem critério comum'}, "
          f"{len(comp['linhas'])} linhas ({vencedores} com vencedor), {len(comp['insights'])} insights, "
          f"{len(comp['alertas'])} alertas, {len(comp['graficos'])} gráficos -> {pasta}")
    for a in comp["alertas"]:
        quem = comp["empresas"][a["empresa"]]["nome"] if a.get("empresa") in LADOS else "ambas"
        print(f"  [{a['tipo']}] {quem}: {a['texto']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
