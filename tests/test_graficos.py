"""Testes de src/graficos.py (CASE-05) com o comparativo fictício de tests/fixtures_comparar."""
import copy
import json
import sys
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import graficos  # noqa: E402
from graficos import gerar_graficos, periodo_anterior_aa  # noqa: E402

FIXTURE = RAIZ / "tests" / "fixtures_comparar" / "comparativo_exemplo.json"
IDS = ["receita_ebitda", "margens", "dl_ebitda", "volume_rpt", "mix_segmentos"]


@pytest.fixture
def comp():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _linha(comp, chave):
    return next(l for l in comp["linhas"] if l["chave"] == chave)


def _confere_pngs(pasta: Path, entradas):
    assert [e["id"] for e in entradas] == IDS
    for e in entradas:
        assert e["arquivo"] == f"graficos/{e['id']}.png"
        caminho = pasta / e["arquivo"]
        assert caminho.is_file() and caminho.stat().st_size > 0
        img = mpimg.imread(caminho)
        altura, largura = img.shape[:2]
        assert (largura, altura) == (1920, 1080)  # 12,8 × 7,2 in a 150 dpi = 16:9
        assert set(e) == {"id", "arquivo", "descricao", "fontes"}
        assert e["descricao"]
        assert set(e["fontes"]) == {"a", "b"}


def test_gera_cinco_pngs_16x9(comp, tmp_path):
    entradas = gerar_graficos(comp, tmp_path)
    _confere_pngs(tmp_path, entradas)
    assert sorted(p.name for p in (tmp_path / "graficos").iterdir()) == sorted(f"{i}.png" for i in IDS)


def test_fontes_vem_das_linhas_usadas(comp, tmp_path):
    entradas = {e["id"]: e for e in gerar_graficos(comp, tmp_path)}
    rec = _linha(comp, "receita_liquida")
    ebt = _linha(comp, f"ebitda_{comp['criterio_ebitda']}")
    for x in ("a", "b"):
        esperadas = set(rec[x]["fontes"]) | set(ebt[x]["fontes"])
        assert esperadas and set(entradas["receita_ebitda"]["fontes"][x]) == esperadas
        assert entradas["margens"]["fontes"][x]
        assert entradas["dl_ebitda"]["fontes"][x]
        assert entradas["mix_segmentos"]["fontes"][x] == comp["segmentos"][x][0]["fontes"]
    # receita_por_t da B é N/C (sem fontes), mas volume tem
    assert entradas["volume_rpt"]["fontes"]["b"] == _linha(comp, "volume_vendas")["b"]["fontes"]


def test_descricao_com_aa(comp, tmp_path):
    entradas = {e["id"]: e for e in gerar_graficos(comp, tmp_path)}
    assert "3T26 × 3T25 (A/A)" in entradas["receita_ebitda"]["descricao"]
    assert "ajustado" in entradas["receita_ebitda"]["descricao"]


def test_rodape_lista_fontes_e_aviso_pdf(comp):
    fontes = {"a": ["ITR p.29", "ITR p.71"], "b": ["ITR p.14", "Apresentação p.9"]}
    rod = graficos._rodape(comp, fontes)
    assert rod == ("Fontes — Empresa A: ITR p.29, p.71 · Empresa B: ITR p.14; Apresentação p.9"
                   " · páginas na numeração do PDF")


@pytest.mark.parametrize("atual, anterior", [
    ("3T26", "3T25"), ("1T27", "1T26"), ("9M26", "9M25"), ("2T10", "2T09"), ("4T2026", "4T2025"),
    ("", None), ("abc", None),
])
def test_periodo_anterior_aa(atual, anterior):
    assert periodo_anterior_aa(atual) == anterior


def test_lado_nd_nao_quebra_e_nao_vira_zero(comp, tmp_path):
    rec = _linha(comp, "receita_liquida")
    rec["a"].update(valor=None, status="ausente", obs="indicador não calculado", fontes=[], disponivel=False)
    rec["a"]["valores"] = {k: None for k in rec["a"]["valores"]}
    _linha(comp, "margem_bruta")["b"].update(valor=None, status="nao_comparavel", obs="teste")
    _linha(comp, "ebitda_ajustado")["b"]["valores"]["3T25"] = None  # só o período anterior falta
    entradas = gerar_graficos(comp, tmp_path)
    _confere_pngs(tmp_path, entradas)
    # valor indisponível vira texto, nunca 0
    assert graficos._valor(rec, "a") == (None, "N/D")
    assert graficos._valor(_linha(comp, "margem_bruta"), "b") == (None, "N/C")
    assert graficos._valor(_linha(comp, "ebitda_ajustado"), "b", "3T25") == (None, "N/D")


def test_linha_inexistente_nao_quebra(comp, tmp_path):
    comp["linhas"] = [l for l in comp["linhas"] if l["chave"] not in ("volume_vendas", "margem_ebit")]
    _confere_pngs(tmp_path, gerar_graficos(comp, tmp_path))


def _sem_dados(comp):
    for linha in comp["linhas"]:
        for x in ("a", "b"):
            linha[x].update(valor=None, status="ausente", disponivel=False, fontes=[], obs="sem dado")
            linha[x]["valores"] = {k: None for k in linha[x].get("valores") or {}}
    comp["segmentos"] = {"a": [], "b": []}
    return comp


def test_tudo_indisponivel_ainda_gera_os_cinco(comp, tmp_path):
    entradas = gerar_graficos(_sem_dados(comp), tmp_path)
    _confere_pngs(tmp_path, entradas)
    assert all(e["fontes"] == {"a": [], "b": []} for e in entradas)


def test_comparativo_vazio_gera_os_cinco(tmp_path):
    comp = {"periodo": "3T26", "criterio_ebitda": None, "empresas": {"a": {"nome": "X"}, "b": {"nome": "Y"}},
            "linhas": [], "segmentos": {"a": [], "b": []}}
    _confere_pngs(tmp_path, gerar_graficos(comp, tmp_path))


def test_ab_invertidos(comp, tmp_path):
    inv = copy.deepcopy(comp)
    inv["empresas"] = {"a": comp["empresas"]["b"], "b": comp["empresas"]["a"]}
    inv["segmentos"] = {"a": comp["segmentos"]["b"], "b": comp["segmentos"]["a"]}
    for linha in inv["linhas"]:
        linha["a"], linha["b"] = linha["b"], linha["a"]
    e1 = gerar_graficos(comp, tmp_path / "ab")
    e2 = gerar_graficos(inv, tmp_path / "ba")
    _confere_pngs(tmp_path / "ba", e2)
    for x, y in zip(e1, e2):
        assert x["fontes"]["a"] == y["fontes"]["b"] and x["fontes"]["b"] == y["fontes"]["a"]


def test_dl_ebitda_reportado_e_segmento_nulo(comp, tmp_path):
    rep = copy.deepcopy(_linha(comp, "dl_ebitda"))
    rep["chave"] = "dl_ebitda_reportado"
    rep["a"]["fontes"] = ["ITR p.99"]
    comp["linhas"].append(rep)
    comp["segmentos"]["a"][1]["pct_ebitda"] = None
    entradas = {e["id"]: e for e in gerar_graficos(comp, tmp_path)}
    assert "ITR p.99" in entradas["dl_ebitda"]["fontes"]["a"]


def test_sem_criterio_usa_linha_ebitda(comp, tmp_path):
    comp["criterio_ebitda"] = None
    for linha in comp["linhas"]:
        if linha["chave"] == "ebitda_ajustado":
            linha["chave"] = "ebitda"
    entradas = {e["id"]: e for e in gerar_graficos(comp, tmp_path)}
    assert "ITR p.55" in entradas["receita_ebitda"]["fontes"]["a"]


def test_fecha_as_figuras(comp, tmp_path):
    antes = len(plt.get_fignums())
    gerar_graficos(comp, tmp_path)
    assert len(plt.get_fignums()) == antes
