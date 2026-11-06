"""CASE-06 · entradas da apresentação executiva.

Por enquanto confere que a fixture fictícia (tests/fixtures_apresentacao/) segue o contrato de
docs/TAREFAS.md e as regras que a apresentação depende: todo número com página, N/D e N/C com
motivo, vencedor só quando faz sentido, narrativa sem número escrito à mão.
Quando o CASE-01/05 publicarem a fixture oficial, acrescentar o caminho dela em PASTAS_COMPARATIVO.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parent / "fixtures_apresentacao"
PASTAS_COMPARATIVO = [FIXTURE / "saida" / "comparativo" / "empresa_a_x_empresa_b_3T26"]
NARRATIVA = FIXTURE / "narrativa" / "empresa_a_x_empresa_b_3T26.json"
QUALITATIVOS = sorted((FIXTURE / "metricas").glob("*_apresentacao_qualitativo.json"))

IDS_SLIDES = {"capa", "resumo", "perfil", "comparativo", "graficos", "setor", "destaques_riscos", "metodologia"}
STATUS_INDISPONIVEL = {"ausente": "N/D", "nao_comparavel": "N/C", "nao_aplicavel": "N/A"}
TEMAS = {"perfil", "capacidade_footprint", "mercados_produtos", "estrategia", "capex_investimentos",
         "guidance_perspectivas", "riscos", "esg", "destaques_trimestre"}
FONTE = re.compile(r"^(ITR|Apresentação) p\.\d+$")
ROTULO_PERIODO = re.compile(r"\b\d[TM]\d{2}\b")
PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def ler(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def tem_numero(texto: str) -> bool:
    """Há dígito fora dos rótulos de período (3T26, 9M26)?"""
    return bool(re.search(r"\d", ROTULO_PERIODO.sub("", texto)))


def br_para_float(s: str) -> tuple[float, int]:
    """Primeiro número pt-BR do texto e quantas casas decimais ele tem."""
    m = re.search(r"-?\d[\d.]*(,\d+)?", s)
    bruto = m.group(0)
    casas = len(m.group(1)) - 1 if m.group(1) else 0
    return float(bruto.replace(".", "").replace(",", ".")), casas


@pytest.fixture(params=PASTAS_COMPARATIVO, ids=lambda p: p.name)
def pasta(request) -> Path:
    return request.param


@pytest.fixture
def comp(pasta) -> dict:
    return ler(pasta / "comparativo.json")


def lados(comp):
    for linha in comp["linhas"]:
        for e in ("a", "b"):
            yield linha, e, linha[e]


# ---------------------------------------------------------------- comparativo.json
def test_campos_do_contrato(comp):
    for campo in ("periodo", "criterio_ebitda", "empresas", "linhas", "segmentos", "insights",
                  "alertas", "graficos", "verificacao"):
        assert campo in comp, campo
    assert comp["criterio_ebitda"] in ("ajustado", "contabil")
    for e in ("a", "b"):
        assert set(comp["empresas"][e]) >= {"slug", "nome", "ticker", "cor"}
    for linha in comp["linhas"]:
        assert set(linha) >= {"chave", "nome", "grupo", "unidade", "melhor", "vencedor", "a", "b"}
        for e in ("a", "b"):
            assert set(linha[e]) >= {"valor", "texto", "var_aa", "var_tt", "unidade_var", "fontes",
                                     "disponivel"}, (linha["chave"], e)


def test_todo_numero_disponivel_tem_fonte_com_pagina(comp):
    for linha, e, lado in lados(comp):
        if lado["disponivel"]:
            assert lado["fontes"], f"{linha['chave']} ({e}) sem fonte"
        for f in lado["fontes"]:
            assert FONTE.match(f), f"{linha['chave']} ({e}): fonte fora do padrão '{f}'"
    for e, segs in comp["segmentos"].items():
        for s in segs:
            assert s.get("fontes") and all(FONTE.match(f) for f in s["fontes"]), (e, s["segmento"])
    for alerta in comp["alertas"]:
        if tem_numero(alerta["texto"]):
            assert alerta.get("fontes"), f"alerta com número e sem fonte: {alerta['texto']}"
    for g in comp["graficos"]:
        assert g.get("fontes"), f"gráfico sem fonte: {g['id']}"


def test_texto_bate_com_valor(comp):
    for linha, e, lado in lados(comp):
        if not lado["disponivel"]:
            continue
        lido, casas = br_para_float(lado["texto"])
        if lado["texto"].lstrip().startswith("-"):
            lido = -abs(lido)
        assert abs(lido - lado["valor"]) <= 0.5 * 10 ** -casas + 1e-9, (linha["chave"], e, lado["texto"])


def test_indisponivel_tem_status_e_motivo(comp):
    for linha, e, lado in lados(comp):
        if lado["disponivel"]:
            assert lado["valor"] is not None, (linha["chave"], e)
            continue
        assert lado["valor"] is None and lado["var_aa"] is None and lado["var_tt"] is None
        assert lado.get("status") in STATUS_INDISPONIVEL, (linha["chave"], e)
        assert lado["texto"] == STATUS_INDISPONIVEL[lado["status"]]
        assert lado.get("obs"), f"{linha['chave']} ({e}) indisponível sem motivo"


def test_vencedor_segue_a_regra(comp):
    for linha in comp["linhas"]:
        a, b, v = linha["a"], linha["b"], linha["vencedor"]
        if linha["melhor"] is None or not (a["disponivel"] and b["disponivel"]):
            assert v is None, f"{linha['chave']}: vencedor sem regra ou com lado indisponível"
            continue
        assert linha["melhor"] in ("maior", "menor")
        if a["valor"] != b["valor"]:
            esperado = "a" if (a["valor"] > b["valor"]) == (linha["melhor"] == "maior") else "b"
            assert v == esperado, linha["chave"]


def test_variacao_em_pp_para_percentual(comp):
    for linha, e, lado in lados(comp):
        if linha["unidade"] == "%" and (lado["var_aa"] is not None or lado["var_tt"] is not None):
            assert lado["unidade_var"] == "p.p.", (linha["chave"], e)


def test_graficos_existem(comp, pasta):
    for g in comp["graficos"]:
        assert (pasta / g["arquivo"]).is_file(), g["arquivo"]


# ---------------------------------------------------------------- qualitativo (CASE-03)
@pytest.mark.parametrize("arquivo", QUALITATIVOS, ids=lambda p: p.name)
def test_qualitativo_tem_pagina_trecho_e_resumo_curto(arquivo):
    fatos = ler(arquivo)
    assert fatos
    for f in fatos:
        assert f["chave"] == "qualitativo" and f["tema"] in TEMAS, f
        assert isinstance(f["pagina"], int) and f["pagina"] >= 1, f
        assert f["trecho"].strip(), f
        assert len(f["resumo"].split()) <= 30, f["resumo"]


# ---------------------------------------------------------------- narrativa (CASE-06)
def textos_da_narrativa(narrativa: dict):
    for slide in narrativa["slides"]:
        for campo in ("titulo", "subtitulo"):
            if slide.get(campo):
                yield slide["id"], slide[campo]
        for bullet in slide.get("bullets", []):
            yield slide["id"], bullet


def test_narrativa_tem_os_slides_do_roteiro():
    ids = [s["id"] for s in ler(NARRATIVA)["slides"]]
    assert set(ids) == IDS_SLIDES and len(ids) == len(IDS_SLIDES)


def test_narrativa_sem_numero_escrito_a_mao():
    for sid, texto in textos_da_narrativa(ler(NARRATIVA)):
        assert not tem_numero(PLACEHOLDER.sub("", texto)), f"[{sid}] número fora de placeholder: {texto}"


def test_placeholders_da_narrativa_existem():
    comp = ler(PASTAS_COMPARATIVO[0] / "comparativo.json")
    chaves = {linha["chave"] for linha in comp["linhas"]}
    for sid, texto in textos_da_narrativa(ler(NARRATIVA)):
        for nome in PLACEHOLDER.findall(texto):
            partes = nome.split(".")
            if partes[0] in ("a", "b"):
                assert partes[1] == "nome" or partes[1] in chaves, f"[{sid}] {{{nome}}}"
                assert len(partes) == 2 or partes[2] in ("var_aa", "var_tt"), f"[{sid}] {{{nome}}}"
            else:
                assert nome in ("periodo", "criterio_ebitda"), f"[{sid}] {{{nome}}}"
