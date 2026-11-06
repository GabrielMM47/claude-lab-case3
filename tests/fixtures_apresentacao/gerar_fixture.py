"""Gera a fixture FICTÍCIA do CASE-06 (apresentação executiva).

Provisória até o CASE-01 publicar as fixtures oficiais. Segue o contrato de docs/TAREFAS.md
(comparativo.json, *_apresentacao_qualitativo.json e narrativa). Empresas, números e páginas
são inventados: nada daqui pode ir para a apresentação real.

    python tests/fixtures_apresentacao/gerar_fixture.py

Os números saem de BASE e todo o resto (margens, variações, textos, vencedor, gráficos) é
calculado aqui, para a fixture ser coerente consigo mesma.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parent
TRI, TRI_AA, TRI_TT = "3T26", "3T25", "2T26"
PAR = f"empresa_a_x_empresa_b_{TRI}"
PASTA_COMP = RAIZ / "comparativo" / PAR  # fora de "saida/", que o .gitignore ignora

EMPRESAS = {
    "a": {"slug": "empresa_a", "nome": "Empresa A", "ticker": "FCTA3", "cor": "#1f5fa8"},
    "b": {"slug": "empresa_b", "nome": "Empresa B", "ticker": "FCTB3", "cor": "#d9822b"},
}

# Fatos inventados (R$ milhões, mil t). A é maior e tem operação no exterior; B tem mineração,
# caixa líquido, prejuízo no 3T25 (impairment) e não tem IR/CSLL do 9M26 (ROIC N/D).
BASE = {
    "a": {
        "receita": {TRI: 15000.0, TRI_AA: 14200.0, TRI_TT: 14800.0},
        "ebitda": {TRI: 2400.0, TRI_AA: 1900.0, TRI_TT: 2300.0},
        "lucro": {TRI: 1200.0, TRI_AA: 800.0, TRI_TT: 1100.0},
        "volume": {TRI: 3000.0, TRI_AA: 2950.0, TRI_TT: 2980.0},
        "divida_liquida": 9000.0, "ebitda_9m": 6900.0, "roe": 12.5, "roic": 10.1,
        "mineracao": False,
        "pag": {"dre": "ITR p.29", "lucro": "ITR p.30", "ebitda": "ITR p.71", "ativo": "ITR p.25",
                "passivo": "ITR p.26", "volume": "Apresentação p.12", "segmentos": "ITR p.72"},
    },
    "b": {
        "receita": {TRI: 6000.0, TRI_AA: 6300.0, TRI_TT: 5900.0},
        "ebitda": {TRI: 600.0, TRI_AA: 750.0, TRI_TT: 570.0},
        "lucro": {TRI: 150.0, TRI_AA: -400.0, TRI_TT: 120.0},
        "volume": {TRI: 1000.0, TRI_AA: 1050.0, TRI_TT: 980.0},
        "divida_liquida": -300.0, "ebitda_9m": 1740.0, "roe": 4.0, "roic": None,
        "mineracao": True,
        "pag": {"dre": "ITR p.14", "lucro": "ITR p.14", "ebitda": "ITR p.24", "ativo": "ITR p.11",
                "passivo": "ITR p.12", "volume": "ITR p.27", "segmentos": "ITR p.31"},
    },
}

SEGMENTOS = {
    "a": [("brasil", 60.0, 55.0), ("exterior", 40.0, 45.0)],
    "b": [("siderurgia", 85.0, 70.0), ("mineracao", 15.0, 30.0)],
}

ROTULO_STATUS = {"ausente": "N/D", "nao_comparavel": "N/C", "nao_aplicavel": "N/A"}


# ---------------------------------------------------------------- formatação (pt-BR)
def fmt_br(x: float, casas: int = 1) -> str:
    s = f"{abs(x):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if x < 0 else "") + s


def texto(v: float, unidade: str) -> str:
    sinal = "-" if v < 0 else ""
    return {
        "R$ milhões": f"{sinal}R$ {fmt_br(abs(v))} mi",
        "%": f"{fmt_br(v)}%",
        "x": f"{fmt_br(v, 2)}x",
        "mil t": f"{fmt_br(v, 0)} mil t",
        "R$/t": f"{sinal}R$ {fmt_br(abs(v), 0)}/t",
    }[unidade]


def variacao(atual, base, unidade):
    """(valor, unidade_var, motivo): p.p. para %, diferença para x, % para o resto."""
    if atual is None or base is None:
        return None, None, None
    if unidade == "%":
        return round(atual - base, 2), "p.p.", None
    if unidade == "x":
        return round(atual - base, 2), "x", None
    if base <= 0:
        return None, "%", f"variação omitida: base {texto(base, unidade)} negativa ou zero"
    return round((atual / base - 1) * 100, 2), "%", None


# ---------------------------------------------------------------- linhas do comparativo
def lado(unidade, serie=None, fontes=(), status="ok", obs=None):
    if status != "ok":
        return {"valor": None, "texto": ROTULO_STATUS[status], "var_aa": None, "var_tt": None,
                "unidade_var": None, "fontes": list(fontes), "disponivel": False,
                "status": status, "obs": obs}
    atual = round(serie[TRI], 2)
    var_aa, u_aa, motivo_aa = variacao(atual, serie.get(TRI_AA), unidade)
    var_tt, u_tt, motivo_tt = variacao(atual, serie.get(TRI_TT), unidade)
    motivos = [m for m in (obs, motivo_aa and f"A/A: {motivo_aa}", motivo_tt and f"T/T: {motivo_tt}") if m]
    return {"valor": atual, "texto": texto(atual, unidade), "var_aa": var_aa, "var_tt": var_tt,
            "unidade_var": u_aa or u_tt, "fontes": list(fontes), "disponivel": True,
            "status": "ok", "obs": "; ".join(motivos) or None}


def razao(num: dict, den: dict, fator: float = 1.0) -> dict:
    return {p: num[p] / den[p] * fator for p in num if p in den and den[p]}


def montar_lados(e: str) -> dict:
    b, pg = BASE[e], BASE[e]["pag"]
    margem_ebitda = razao(b["ebitda"], b["receita"], 100)
    margem_liq = razao(b["lucro"], b["receita"], 100)
    dl_ebitda = {TRI: b["divida_liquida"] / (b["ebitda_9m"] * 4 / 3)}
    def nc_t(o_que: str) -> dict:
        return {"status": "nao_comparavel", "obs": f"{o_que} consolidado inclui mineração e o volume é só "
                                                   "de aço; usar o indicador do segmento siderúrgico"}
    L = {
        "receita_liquida": lado("R$ milhões", b["receita"], [pg["dre"]]),
        "ebitda_ajustado": lado("R$ milhões", b["ebitda"], [pg["ebitda"]]),
        "margem_ebitda": lado("%", margem_ebitda, [pg["dre"], pg["ebitda"]]),
        "lucro_liquido": lado("R$ milhões", b["lucro"], [pg["lucro"]]),
        "margem_liquida": lado("%", margem_liq, [pg["dre"], pg["lucro"]]),
        "divida_liquida": lado("R$ milhões", {TRI: b["divida_liquida"]}, [pg["ativo"], pg["passivo"]],
                               obs="negativa = caixa líquido" if b["divida_liquida"] < 0 else None),
        "dl_ebitda": lado("x", dl_ebitda, [pg["ativo"], pg["passivo"], pg["ebitda"]],
                          obs="EBITDA ajustado 9M26 anualizado (× 4/3)"),
        "roe": lado("%", {TRI: b["roe"]}, [pg["passivo"], pg["lucro"]],
                    obs="9M26 anualizado; PL médio 4T25–3T26"),
        "roic": (lado("%", {TRI: b["roic"]}, [pg["ativo"], pg["passivo"], pg["dre"]],
                      obs="9M26 anualizado; alíquota efetiva limitada a 34%") if b["roic"] is not None
                 else lado("%", status="ausente", obs="falta ir_csll 9M26 (consolidado)")),
        "volume_vendas": lado("mil t", b["volume"], [pg["volume"]]),
    }
    if b["mineracao"]:
        L["receita_por_t"] = lado("R$/t", fontes=[pg["dre"], pg["volume"]], **nc_t("valor da receita"))
        L["ebitda_por_t"] = lado("R$/t", fontes=[pg["ebitda"], pg["volume"]], **nc_t("valor do EBITDA"))
    else:
        L["receita_por_t"] = lado("R$/t", razao(b["receita"], b["volume"], 1000), [pg["dre"], pg["volume"]])
        L["ebitda_por_t"] = lado("R$/t", razao(b["ebitda"], b["volume"], 1000), [pg["ebitda"], pg["volume"]])
    return L


# chave, nome, grupo, unidade, melhor (None = sem vencedor), período do valor
LINHAS = [
    ("receita_liquida", "Receita líquida", "escala", "R$ milhões", None, TRI),
    ("ebitda_ajustado", "EBITDA ajustado", "escala", "R$ milhões", None, TRI),
    ("margem_ebitda", "Margem EBITDA ajustada", "margens", "%", "maior", TRI),
    ("lucro_liquido", "Lucro líquido", "escala", "R$ milhões", None, TRI),
    ("margem_liquida", "Margem líquida", "margens", "%", "maior", TRI),
    ("divida_liquida", "Dívida líquida", "endividamento", "R$ milhões", None, TRI),
    ("dl_ebitda", "Dívida líquida / EBITDA ajustado", "endividamento", "x", "menor", TRI),
    ("roe", "ROE", "rentabilidade", "%", "maior", "9M26"),
    ("roic", "ROIC", "rentabilidade", "%", "maior", "9M26"),
    ("volume_vendas", "Volume vendido de aço", "setor", "mil t", None, TRI),
    ("receita_por_t", "Receita por tonelada", "setor", "R$/t", "maior", TRI),
    ("ebitda_por_t", "EBITDA ajustado por tonelada", "setor", "R$/t", "maior", TRI),
]


def vencedor(melhor, a, b):
    if melhor is None or not (a["disponivel"] and b["disponivel"]) or a["valor"] == b["valor"]:
        return None
    a_maior = a["valor"] > b["valor"]
    return "a" if a_maior == (melhor == "maior") else "b"


# ---------------------------------------------------------------- gráficos
def fontes_de(*chaves: str) -> dict:
    """Fontes por empresa, no formato do comparativo: {"a": ["ITR p.29", ...], "b": [...]}."""
    return {e: [BASE[e]["pag"][k] for k in chaves] for e in "ab"}


def legenda(fontes: dict) -> str:
    return "; ".join(f"{EMPRESAS[e]['nome']} — {', '.join(v)}" for e, v in fontes.items())


def _rodape(fig, texto_fonte: str):
    fig.text(0.01, 0.01, f"Fonte: {texto_fonte} · DADOS FICTÍCIOS", fontsize=7, color="#555")
    fig.text(0.5, 0.5, "FICTÍCIO", fontsize=48, color="#000", alpha=0.06, ha="center",
             va="center", rotation=20)


def gerar_graficos(linhas: dict) -> list[dict]:
    pasta = PASTA_COMP / "graficos"
    pasta.mkdir(parents=True, exist_ok=True)
    nomes = [EMPRESAS[e]["nome"] for e in "ab"]
    cores = [EMPRESAS[e]["cor"] for e in "ab"]
    graficos = []

    def salvar(fig, gid, descricao, fontes):
        fig.savefig(pasta / f"{gid}.png", dpi=80)
        plt.close(fig)
        graficos.append({"id": gid, "arquivo": f"graficos/{gid}.png", "descricao": descricao,
                         "fontes": fontes})

    # 1. Receita e EBITDA, 3T26 × 3T25
    fig, axs = plt.subplots(1, 2, figsize=(8, 4.5))
    for ax, chave, titulo in ((axs[0], "receita", "Receita líquida"), (axs[1], "ebitda", "EBITDA ajustado")):
        for i, e in enumerate("ab"):
            ax.bar([i - 0.2, i + 0.2], [BASE[e][chave][TRI_AA], BASE[e][chave][TRI]],
                   width=0.4, color=[cores[i] + "80", cores[i]])
        ax.set_xticks([0, 1], nomes)
        ax.set_title(f"{titulo} (R$ mi): {TRI_AA} × {TRI}", fontsize=10)
    fontes = fontes_de("dre", "ebitda")
    _rodape(fig, legenda(fontes))
    salvar(fig, "receita_ebitda", f"Receita e EBITDA ajustado, {TRI} × {TRI_AA} (A/A)", fontes)

    # 2. Margens lado a lado
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for j, chave in enumerate(("margem_ebitda", "margem_liquida")):
        ax.bar([j - 0.2, j + 0.2], [linhas[chave]["a"]["valor"], linhas[chave]["b"]["valor"]],
               width=0.4, color=cores)
    ax.set_xticks([0, 1], ["Margem EBITDA ajustada", "Margem líquida"])
    ax.set_title(f"Margens no {TRI} (%)", fontsize=10)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in cores], labels=nomes)
    fontes = fontes_de("dre", "ebitda")
    _rodape(fig, legenda(fontes))
    salvar(fig, "margens", f"Margem EBITDA ajustada e margem líquida, {TRI}", fontes)

    # 3. DL/EBITDA
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar([0, 1], [linhas["dl_ebitda"][e]["valor"] for e in "ab"], color=cores)
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xticks([0, 1], nomes)
    ax.set_title("Dívida líquida / EBITDA ajustado (x; negativo = caixa líquido)", fontsize=10)
    fontes = fontes_de("passivo", "ebitda")
    _rodape(fig, legenda(fontes))
    salvar(fig, "dl_ebitda", f"Alavancagem em 30/09 ({TRI})", fontes)

    # 4. Volume e R$/t
    fig, axs = plt.subplots(1, 2, figsize=(8, 4.5))
    axs[0].bar([0, 1], [BASE[e]["volume"][TRI] for e in "ab"], color=cores)
    axs[0].set_xticks([0, 1], nomes)
    axs[0].set_title(f"Volume vendido de aço, {TRI} (mil t)", fontsize=10)
    for i, e in enumerate("ab"):
        lado_rt = linhas["receita_por_t"][e]
        if lado_rt["disponivel"]:
            axs[1].bar(i, lado_rt["valor"], color=cores[i])
        else:
            axs[1].text(i, 0.5, lado_rt["texto"], ha="center", transform=axs[1].get_xaxis_transform())
    axs[1].set_xticks([0, 1], nomes)
    axs[1].set_xlim(-0.6, 1.6)
    axs[1].set_title(f"Receita por tonelada, {TRI} (R$/t)", fontsize=10)
    fontes = fontes_de("volume", "dre")
    _rodape(fig, legenda(fontes))
    salvar(fig, "volume_rpt", f"Volume e receita por tonelada, {TRI}", fontes)

    # 5. Mix de segmentos (% do EBITDA)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, e in enumerate("ab"):
        base = 0.0
        for k, (seg, _, pct_ebitda) in enumerate(SEGMENTOS[e]):
            ax.barh(i, pct_ebitda, left=base, color=cores[i], alpha=1 - 0.45 * k)
            ax.text(base + pct_ebitda / 2, i, f"{seg} {fmt_br(pct_ebitda, 0)}%", ha="center",
                    va="center", color="white", fontsize=9)
            base += pct_ebitda
    ax.set_yticks([0, 1], nomes)
    ax.set_title(f"Mix do EBITDA por segmento, {TRI} (%)", fontsize=10)
    fontes = fontes_de("segmentos")
    _rodape(fig, legenda(fontes))
    salvar(fig, "mix_segmentos", f"Participação de cada segmento no EBITDA, {TRI}", fontes)
    return graficos


# ---------------------------------------------------------------- comparativo.json
def gerar_comparativo() -> dict:
    lados = {e: montar_lados(e) for e in "ab"}
    linhas, por_chave = [], {}
    for chave, nome, grupo, unidade, melhor, periodo in LINHAS:
        a, b = lados["a"][chave], lados["b"][chave]
        linha = {"chave": chave, "nome": nome, "grupo": grupo, "unidade": unidade, "periodo": periodo,
                 "melhor": melhor, "vencedor": vencedor(melhor, a, b), "a": a, "b": b}
        linhas.append(linha)
        por_chave[chave] = linha

    m, r = por_chave["margem_ebitda"], por_chave["receita_liquida"]
    dif_margem = m["a"]["valor"] - m["b"]["valor"]
    insights = [
        {"id": "margem", "chaves": ["margem_ebitda"],
         "texto": f"Empresa A tem margem EBITDA ajustada {fmt_br(dif_margem)} p.p. acima da Empresa B "
                  f"({m['a']['texto']} × {m['b']['texto']})"},
        {"id": "crescimento", "chaves": ["receita_liquida"],
         "texto": f"Receita da Empresa A varia {fmt_br(r['a']['var_aa'])}% A/A; a da Empresa B, "
                  f"{fmt_br(r['b']['var_aa'])}%"},
        {"id": "alavancagem", "chaves": ["dl_ebitda", "divida_liquida"],
         "texto": f"Empresa B tem caixa líquido (DL/EBITDA {por_chave['dl_ebitda']['b']['texto']}); "
                  f"Empresa A, {por_chave['dl_ebitda']['a']['texto']}"},
        {"id": "mineracao", "chaves": [], "fontes": {"b": [BASE["b"]["pag"]["segmentos"]]},
         "texto": f"Mineração responde por {fmt_br(SEGMENTOS['b'][1][2], 0)}% do EBITDA da Empresa B"},
    ]
    alertas = [
        {"tipo": "efeito_pontual", "empresa": "b", "fontes": ["ITR p.33"],
         "chaves": ["lucro_liquido", "margem_liquida"],
         "texto": "Prejuízo de R$ 400,0 mi no 3T25 inclui impairment de R$ 500,0 mi: a variação A/A "
                  "do lucro da Empresa B engana"},
        {"tipo": "negocios_diferentes", "empresa": "b", "fontes": [BASE["b"]["pag"]["segmentos"]],
         "texto": "Empresa B tem mineração (15% da receita): receita e EBITDA por tonelada consolidados "
                  "não são comparáveis"},
        {"tipo": "indisponivel", "empresa": "b", "fontes": [],
         "texto": "ROIC da Empresa B indisponível: falta IR/CSLL do 9M26"},
        {"tipo": "divergencia_definicao", "empresa": "a", "fontes": ["ITR p.26", "Apresentação p.18"],
         "texto": "Dívida líquida calculada (R$ 9.000,0 mi) difere da reportada (R$ 8.200,0 mi) em "
                  "9,8%: a reportada exclui arrendamentos"},
    ]
    segmentos = {e: [{"segmento": s, "pct_receita": pr, "pct_ebitda": pe,
                      "fontes": [BASE[e]["pag"]["segmentos"]]} for s, pr, pe in SEGMENTOS[e]]
                 for e in "ab"}
    return {
        "_ficticio": "Fixture provisória do CASE-06. Empresas, números e páginas inventados.",
        "periodo": TRI, "criterio_ebitda": "ajustado", "empresas": EMPRESAS, "linhas": linhas,
        "segmentos": segmentos, "insights": insights, "alertas": alertas,
        "graficos": gerar_graficos(por_chave),
        "verificacao": {"total": 52, "ok": 52, "por_arquivo": {
            "empresa_a_3T26_itr_dfs.json": {"total": 20, "ok": 20},
            "empresa_a_3T26_itr_complementar.json": {"total": 6, "ok": 6},
            "empresa_b_3T26_itr_dfs.json": {"total": 20, "ok": 20},
            "empresa_b_3T26_itr_complementar.json": {"total": 6, "ok": 6}}},
    }


# ---------------------------------------------------------------- qualitativo (CASE-03)
QUALITATIVO = {
    "a": [
        ("perfil", 3, "Siderúrgica com usinas no Brasil e no exterior, foco em aços longos.",
         "Somos uma produtora de aços longos com usinas no Brasil e no exterior"),
        ("capacidade_footprint", 4, "Doze usinas em três países.",
         "12 usinas em 3 países"),
        ("mercados_produtos", 5, "Atende construção civil, indústria e agronegócio.",
         "construção civil, indústria e agronegócio"),
        ("estrategia", 6, "Prioriza disciplina de capital e aço de menor emissão.",
         "disciplina na alocação de capital e aço de baixa emissão"),
        ("guidance_perspectivas", 15, "Espera demanda estável no Brasil e mais fraca no exterior no 4T.",
         "demanda estável no Brasil e mais fraca no exterior no 4T26"),
        ("riscos", 16, "Importações de aço e câmbio pressionam preços.",
         "importações de aço e volatilidade cambial"),
        ("destaques_trimestre", 2, "Margem cresce com custo menor de sucata.",
         "redução do custo de sucata"),
    ],
    "b": [
        ("perfil", 3, "Siderúrgica de aços planos com operação própria de minério de ferro.",
         "produtora de aços planos com mineração própria"),
        ("capacidade_footprint", 4, "Duas usinas e uma mina no Brasil.",
         "2 usinas e 1 mina"),
        ("mercados_produtos", 5, "Vende para automotivo, linha branca e distribuição.",
         "automotivo, linha branca e distribuição"),
        ("estrategia", 7, "Foco em eficiência de custos e mix de maior valor agregado.",
         "eficiência de custos e mix de maior valor agregado"),
        ("guidance_perspectivas", 20, "Espera volumes de aço estáveis e minério mais fraco no 4T.",
         "volumes de aço estáveis e preço do minério mais fraco"),
        ("riscos", 21, "Preço do minério e importações de aço afetam resultado.",
         "preço do minério de ferro e importações de aço"),
        ("destaques_trimestre", 2, "Volume menor e minério mais barato reduzem margem.",
         "queda de volume e do preço do minério"),
    ],
}


def gerar_qualitativo(e: str) -> list[dict]:
    slug = EMPRESAS[e]["slug"]
    return [{"chave": "qualitativo", "metrica": tema, "tema": tema, "empresa": slug,
             "documento": "apresentacao", "data_documento": "2026-10-30", "periodo": TRI,
             "resumo": resumo, "pagina": pagina, "trecho": trecho}
            for tema, pagina, resumo, trecho in QUALITATIVO[e]]


# ---------------------------------------------------------------- narrativa (CASE-06)
# Proposta: nenhum número escrito à mão. Placeholders {a.<chave>}, {b.<chave>.var_aa|var_tt},
# {a.nome}, {b.nome}, {periodo}, {criterio_ebitda} são resolvidos pelo código a partir do
# comparativo.json; o verificador de narrativa reprova qualquer dígito fora deles.
NARRATIVA = {"slides": [
    {"id": "capa", "titulo": "{a.nome} amplia margem para {a.margem_ebitda} enquanto {b.nome} recua "
                             "para {b.margem_ebitda}",
     "subtitulo": "Siderurgia no {periodo}: comparação de resultados"},
    {"id": "resumo", "titulo": "Três coisas que o comitê precisa saber", "bullets": [
        "Margem EBITDA {criterio_ebitda}: {a.margem_ebitda} na {a.nome} ({a.margem_ebitda.var_aa} A/A) "
        "contra {b.margem_ebitda} na {b.nome} ({b.margem_ebitda.var_aa} A/A)",
        "{b.nome} tem caixa líquido ({b.dl_ebitda} de DL/EBITDA); {a.nome}, {a.dl_ebitda}",
        "Lucro da {b.nome} ({b.lucro_liquido}) volta ao azul, mas a base do 3T25 tem impairment",
    ]},
    {"id": "perfil", "titulo": "{a.nome} é maior e tem operação fora do Brasil; {b.nome} combina aço e "
                               "mineração"},
    {"id": "comparativo", "titulo": "{a.nome} lidera em margem; {b.nome}, em alavancagem"},
    {"id": "graficos", "titulo": "Receita da {a.nome} cresce {a.receita_liquida.var_aa} A/A; a da "
                                 "{b.nome} varia {b.receita_liquida.var_aa}"},
    {"id": "setor", "titulo": "Por tonelada, só a {a.nome} é comparável: {a.receita_por_t}"},
    {"id": "destaques_riscos", "titulo": "Minério e importações são os riscos do próximo trimestre"},
    {"id": "metodologia", "titulo": "Como chegamos aos números"},
]}


def salvar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    salvar_json(PASTA_COMP / "comparativo.json", gerar_comparativo())
    for e in "ab":
        salvar_json(RAIZ / "metricas" / f"{EMPRESAS[e]['slug']}_{TRI}_apresentacao_qualitativo.json",
                    gerar_qualitativo(e))
    salvar_json(RAIZ / "narrativa" / f"{PAR}.json", NARRATIVA)
    print(f"fixture gerada em {RAIZ}")


if __name__ == "__main__":
    main()
