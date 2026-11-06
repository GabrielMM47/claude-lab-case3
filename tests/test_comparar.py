"""Testes do comparativo (CASE-05, src/comparar.py).

Usa só as empresas FICTÍCIAS de tests/fixtures_comparar/indicadores/ (empresa_a, empresa_b,
empresa_c); nenhum número real aparece aqui.
"""
import copy
import csv
import json
from pathlib import Path

import pytest

import comparar
import contrato

RAIZ = Path(__file__).resolve().parent.parent
PASTA_IND = RAIZ / "tests" / "fixtures_comparar" / "indicadores"
CONFIG = RAIZ / "config" / "empresas.toml"
TRI = "3T26"


def _ind(slug: str) -> dict:
    return json.loads((PASTA_IND / f"{slug}_{TRI}_indicadores.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cfg() -> dict:
    return comparar.carregar_config(CONFIG)


@pytest.fixture(scope="module")
def comp_ab(cfg) -> dict:
    return comparar.montar_comparativo(_ind("empresa_a"), _ind("empresa_b"), cfg, TRI)


@pytest.fixture(scope="module")
def comp_ba(cfg) -> dict:
    return comparar.montar_comparativo(_ind("empresa_b"), _ind("empresa_a"), cfg, TRI)


def _linha(comp: dict, chave: str) -> dict:
    return next(l for l in comp["linhas"] if l["chave"] == chave)


def _sem_ebitda_ajustado(ind: dict) -> dict:
    """Variante só com EBITDA ajustado (sem contábil): força 'sem critério comum' contra empresa_c."""
    ind = copy.deepcopy(ind)
    ind["criterios_ebitda"] = ["ajustado"]
    ind["indicadores"] = [i for i in ind["indicadores"] if not i["chave"].endswith("_contabil")]
    return ind


# --------------------------------------------------------------------------- config

def test_carregar_config_le_toml(cfg):
    assert cfg["empresa_a"]["nome"] == "Empresa A"
    assert cfg["empresa_a"]["ticker"] == "FCTA3"
    assert cfg["empresa_a"]["cor"].startswith("#")
    assert "empresa_c" not in cfg


def test_carregar_config_arquivo_ausente(tmp_path):
    assert comparar.carregar_config(tmp_path / "nao_existe.toml") == {}


def test_slug_fora_do_toml_usa_reserva_e_alerta_config(cfg):
    comp = comparar.montar_comparativo(_ind("empresa_c"), _ind("empresa_a"), cfg, TRI)
    emp_c = comp["empresas"]["a"]
    assert emp_c["slug"] == "empresa_c"
    assert emp_c["ticker"] is None
    assert emp_c["cor"] in comparar.CORES_RESERVA
    assert emp_c["nome"]
    alertas = [a for a in comp["alertas"] if a["tipo"] == "config"]
    assert len(alertas) == 1 and alertas[0]["empresa"] == "a"
    assert comp["empresas"]["b"]["cor"] == cfg["empresa_a"]["cor"]


def test_cor_repetida_b_usa_reserva(cfg):
    cfg2 = copy.deepcopy(cfg)
    cfg2["empresa_b"]["cor"] = cfg2["empresa_a"]["cor"]
    comp = comparar.montar_comparativo(_ind("empresa_a"), _ind("empresa_b"), cfg2, TRI)
    assert comp["empresas"]["a"]["cor"] == cfg["empresa_a"]["cor"]
    assert comp["empresas"]["b"]["cor"] in comparar.CORES_RESERVA


# --------------------------------------------------------------------------- compatibilidade e critério

def test_compatibilidade_ok(comp_ab):
    alertas, erros = comparar.validar_compatibilidade(_ind("empresa_a"), _ind("empresa_b"), TRI)
    assert erros == []
    assert not any(a["tipo"] == "metodologia" for a in alertas)


@pytest.mark.parametrize("alteracao", [
    lambda a, b: a.update(periodo="2T26"),
    lambda a, b: b.update(periodo="2T26"),
    lambda a, b: b.update(unidade_monetaria="R$ mil"),
    lambda a, b: b.update(empresa=a["empresa"]),
])
def test_compatibilidade_erros_fatais(alteracao):
    a, b = _ind("empresa_a"), _ind("empresa_b")
    alteracao(a, b)
    _, erros = comparar.validar_compatibilidade(a, b, TRI)
    assert erros
    with pytest.raises(ValueError):
        comparar.montar_comparativo(a, b, {}, TRI)


def test_escolher_criterio():
    a, b, c = _ind("empresa_a"), _ind("empresa_b"), _ind("empresa_c")
    assert comparar.escolher_criterio(a, b) == "ajustado"
    assert comparar.escolher_criterio(c, a) == "contabil"
    assert comparar.escolher_criterio(_sem_ebitda_ajustado(a), c) is None


def test_empresa_c_usa_criterio_contabil(cfg):
    comp = comparar.montar_comparativo(_ind("empresa_a"), _ind("empresa_c"), cfg, TRI)
    assert comp["criterio_ebitda"] == "contabil"
    chaves = [l["chave"] for l in comp["linhas"]]
    assert "ebitda_contabil" in chaves and "ebitda_ajustado" not in chaves
    assert _linha(comp, "margem_ebitda")["b"]["status"] == "ok"


def test_sem_criterio_comum_vira_nc_com_motivo(cfg):
    a = _sem_ebitda_ajustado(_ind("empresa_a"))
    comp = comparar.montar_comparativo(a, _ind("empresa_c"), cfg, TRI)
    assert comp["criterio_ebitda"] is None
    chaves = [l["chave"] for l in comp["linhas"]]
    assert "ebitda" in chaves
    for chave in ("ebitda", "margem_ebitda", "dl_ebitda", "ebitda_por_t"):
        linha = _linha(comp, chave)
        for lado in ("a", "b"):
            assert linha[lado]["status"] == "nao_comparavel"
            assert linha[lado]["valor"] is None
            assert linha[lado]["texto"] == "N/C"
            assert linha[lado]["obs"] == comparar.OBS_SEM_CRITERIO
        assert linha["vencedor"] is None
    assert contrato.validar(comp, "comparativo") == []


def test_metodologia_diferente_nc_em_rentabilidade(cfg):
    comp = comparar.montar_comparativo(_ind("empresa_a"), _ind("empresa_c"), cfg, TRI)
    assert any(a["tipo"] == "metodologia" for a in comp["alertas"])
    assert isinstance(comp["metodologia"]["anualizacao"], dict)
    for chave in ("roe", "roa", "roic", "dl_ebitda"):
        linha = _linha(comp, chave)
        assert linha["a"]["status"] == linha["b"]["status"] == "nao_comparavel"
        assert linha["a"]["valor"] is None and linha["b"]["valor"] is None
        assert linha["vencedor"] is None


# --------------------------------------------------------------------------- linhas

def test_catalogo_e_ordem(comp_ab):
    chaves = [l["chave"] for l in comp_ab["linhas"]]
    assert chaves[:3] == ["receita_liquida", "ebitda_ajustado", "lucro_liquido"]
    assert chaves.index("dl_ebitda_reportado") == chaves.index("dl_ebitda") + 1
    assert len(chaves) == len(set(chaves))


def test_so_escopo_consolidado(comp_ab):
    a = _ind("empresa_a")
    receita = next(i for i in a["indicadores"] if i["chave"] == "receita_liquida")
    linha = _linha(comp_ab, "receita_liquida")
    assert linha["a"]["valor"] == receita["valores"][TRI]
    assert linha["a"]["fontes"] == comparar.fontes_de(receita["insumos"])


def test_fontes_formatadas_e_ordenadas():
    insumos = [{"documento": "itr", "pagina": 29}, {"documento": "apresentacao", "pagina": 12},
               {"documento": "itr", "pagina": 29}, {"documento": "itr", "pagina": 3},
               {"documento": "release", "pagina": 5}]
    assert comparar.fontes_de(insumos) == ["Apresentação p.12", "ITR p.3", "ITR p.29", "Release p.5"]


def test_texto_e_variacoes_formatados(comp_ab):
    linha = _linha(comp_ab, "margem_bruta")
    lado = linha["a"]
    assert lado["texto"] == contrato.fmt_br(lado["valor"], "%")
    assert lado["texto_var_aa"] == contrato.fmt_var(lado["var_aa"], "p.p.")
    assert linha["periodo"] == TRI
    assert _linha(comp_ab, "roe")["periodo"] != TRI   # rentabilidade usa o acumulado do indicador


def test_status_diferente_de_ok_nunca_vira_zero(comp_ab, cfg):
    comp_ac = comparar.montar_comparativo(_ind("empresa_a"), _ind("empresa_c"), cfg, TRI)
    vistos = 0
    for comp in (comp_ab, comp_ac):
        for linha in comp["linhas"]:
            for lado in ("a", "b"):
                s = linha[lado]
                if s["status"] == "ok":
                    continue
                vistos += 1
                assert s["valor"] is None
                assert s["texto"] in ("N/D", "N/C", "N/A")
                assert all(v is None for v in s["valores"].values())
                assert s["var_aa"] is None and s["var_tt"] is None
                assert s["obs"]
                assert s["disponivel"] is False
    assert vistos >= 3
    roic_b = _linha(comp_ab, "roic")["b"]
    assert roic_b["status"] == "ausente" and roic_b["texto"] == "N/D"
    rpt_b = _linha(comp_ab, "receita_por_t")["b"]
    assert rpt_b["status"] == "nao_comparavel" and rpt_b["texto"] == "N/C"


def test_indicador_inexistente_vira_ausente(cfg):
    b = _ind("empresa_b")
    b["indicadores"] = [i for i in b["indicadores"] if i["chave"] != "margem_bruta"]
    comp = comparar.montar_comparativo(_ind("empresa_a"), b, cfg, TRI)
    lado = _linha(comp, "margem_bruta")["b"]
    assert lado["status"] == "ausente" and lado["valor"] is None
    assert lado["obs"] == comparar.OBS_INEXISTENTE


# --------------------------------------------------------------------------- vencedor

@pytest.mark.parametrize("chave", ["receita_liquida", "volume_vendas", "divida_liquida",
                                   "ebitda_ajustado", "fco", "fcl", "capex_receita"])
def test_sem_vencedor_em_escala(comp_ab, chave):
    linha = _linha(comp_ab, chave)
    assert linha["melhor"] is None
    assert linha["vencedor"] is None
    assert linha["motivo_sem_vencedor"]


def test_dl_ebitda_sem_vencedor_com_ebitda_negativo(comp_ab):
    linha = _linha(comp_ab, "dl_ebitda")
    assert linha["melhor"] == "menor"
    assert linha["a"]["status"] == linha["b"]["status"] == "ok"
    assert linha["vencedor"] is None
    assert "EBITDA" in linha["motivo_sem_vencedor"]


def test_vencedor_respeita_melhor(comp_ab):
    for linha in comp_ab["linhas"]:
        if linha["vencedor"] is None:
            assert linha["motivo_sem_vencedor"]
            continue
        assert linha["motivo_sem_vencedor"] is None
        va, vb = linha["a"]["valor"], linha["b"]["valor"]
        esperado = "a" if (va > vb) == (linha["melhor"] == "maior") else "b"
        assert linha["vencedor"] == esperado
    assert _linha(comp_ab, "margem_bruta")["vencedor"] is not None


def test_sem_vencedor_com_lado_indisponivel(comp_ab):
    linha = _linha(comp_ab, "roic")
    assert linha["vencedor"] is None and linha["motivo_sem_vencedor"] == comparar.MOTIVO_INDISPONIVEL


def test_pl_negativo_sem_vencedor(cfg):
    b = _ind("empresa_b")
    for i in b["indicadores"]:
        if i["chave"] == "divida_liquida_pl" and i["escopo"] == "consolidado":
            i["valores"][TRI] = -abs(i["valores"][TRI])   # DL > 0 e DL/PL < 0 -> PL < 0
    comp = comparar.montar_comparativo(_ind("empresa_a"), b, cfg, TRI)
    for chave in ("divida_liquida_pl", "roe"):
        linha = _linha(comp, chave)
        assert linha["vencedor"] is None
        assert linha["motivo_sem_vencedor"] == comparar.MOTIVO_PL


def test_inverter_a_b(comp_ab, comp_ba):
    assert [l["chave"] for l in comp_ab["linhas"]] == [l["chave"] for l in comp_ba["linhas"]]
    troca = {"a": "b", "b": "a", None: None}
    for la, lb in zip(comp_ab["linhas"], comp_ba["linhas"]):
        assert la["a"] == lb["b"] and la["b"] == lb["a"]
        assert la["vencedor"] == troca[lb["vencedor"]]
        assert la["motivo_sem_vencedor"] == lb["motivo_sem_vencedor"]
    assert comp_ab["segmentos"]["a"] == comp_ba["segmentos"]["b"]
    assert comp_ab["empresas"]["a"] == comp_ba["empresas"]["b"]


# --------------------------------------------------------------------------- segmentos

def test_segmentos(comp_ab):
    segs_b = comp_ab["segmentos"]["b"]
    pcts = [s["pct_receita"] for s in segs_b]
    assert len(pcts) >= 2 and pcts == sorted(pcts, reverse=True)
    for s in segs_b + comp_ab["segmentos"]["a"]:
        assert s["pct_receita"] is not None and s["pct_ebitda"] is not None
        assert s["fontes"]


def test_segmento_so_com_receita(cfg):
    b = _ind("empresa_b")
    escopo = next(i["escopo"] for i in b["indicadores"] if i["chave"] == "participacao_ebitda")
    b["indicadores"] = [i for i in b["indicadores"]
                        if not (i["chave"] == "participacao_ebitda" and i["escopo"] == escopo)]
    comp = comparar.montar_comparativo(_ind("empresa_a"), b, cfg, TRI)
    seg = next(s for s in comp["segmentos"]["b"] if s["segmento"] == escopo.split(":", 1)[1])
    assert seg["pct_ebitda"] is None and seg["pct_receita"] is not None


# --------------------------------------------------------------------------- insights

def test_insights(comp_ab, cfg):
    ids = [i["id"] for i in comp_ab["insights"]]
    assert ids == ["margem", "crescimento", "alavancagem", "por_tonelada", "mix"]
    textos = {i["id"]: i["texto"] for i in comp_ab["insights"]}
    nome_a, nome_b = cfg["empresa_a"]["nome"], cfg["empresa_b"]["nome"]
    for t in textos.values():
        assert nome_a in t or nome_b in t
    assert "p.p." in textos["margem"]
    assert "A/A" in textos["crescimento"]
    rpt_b = _linha(comp_ab, "receita_por_t")["b"]
    assert rpt_b["obs"] in textos["por_tonelada"]
    # a margem escolhida é a de maior diferença absoluta
    margem = next(i for i in comp_ab["insights"] if i["id"] == "margem")
    difs = {l["chave"]: abs(l["a"]["valor"] - l["b"]["valor"]) for l in comp_ab["linhas"]
            if l["chave"].startswith("margem_") and l["a"]["valor"] is not None and l["b"]["valor"] is not None}
    assert margem["chaves"] == [max(difs, key=difs.get)]


# --------------------------------------------------------------------------- alertas

def test_alerta_efeito_pontual_3t25(comp_ab):
    ef = [a for a in comp_ab["alertas"] if a["tipo"] == "efeito_pontual" and a["empresa"] == "a"]
    assert ef and "3T25" in ef[0]["texto"]
    assert "margem_ebitda" in ef[0]["chaves"]
    assert "ebitda_ajustado" in ef[0]["chaves"]


def test_alerta_efeito_pontual_2t26(comp_ab):
    ef = [a for a in comp_ab["alertas"] if a["tipo"] == "efeito_pontual" and a["empresa"] == "b"]
    assert ef and "margem_ebitda" in ef[0]["chaves"]


def test_alertas_repassados_e_resumo_unidade(comp_ab):
    tipos_b = {a["tipo"] for a in comp_ab["alertas"] if a["empresa"] == "b"}
    assert {"divergencia", "efeito_pontual", "divergencia_definicao", "indisponivel"} <= tipos_b
    unidade_a = [a for a in comp_ab["alertas"] if a["tipo"] == "unidade" and a["empresa"] == "a"]
    assert len(unidade_a) == 1
    div = next(a for a in comp_ab["alertas"] if a["tipo"] == "divergencia")
    assert div["chaves"] == ["volume_vendas"]
    assert div["fontes"]


def test_alertas_indisponivel_e_negocios(comp_ab):
    indisp = [a for a in comp_ab["alertas"] if a["tipo"] == "indisponivel"]
    nao_ok = [(l["chave"], lado) for l in comp_ab["linhas"] for lado in ("a", "b") if l[lado]["status"] != "ok"]
    assert sorted((a["chaves"][0], a["empresa"]) for a in indisp) == sorted(nao_ok)
    neg = [a for a in comp_ab["alertas"] if a["tipo"] == "negocios_diferentes"]
    assert len(neg) == 1 and neg[0]["empresa"] is None
    assert "receita_por_t" in neg[0]["chaves"]


# --------------------------------------------------------------------------- contrato e saída

def test_comparativo_passa_no_contrato(comp_ab, comp_ba, cfg):
    comp_ca = comparar.montar_comparativo(_ind("empresa_c"), _ind("empresa_a"), cfg, TRI)
    for comp in (comp_ab, comp_ba, comp_ca):
        assert contrato.validar(comp, "comparativo") == []
        assert contrato.escolher_schema(comp) == "comparativo"
        assert comp["graficos"] == [] and comp["verificacao"] is None


def test_escrever_saida(comp_ab, tmp_path):
    comparar.escrever_saida(comp_ab, tmp_path)
    dados = json.loads((tmp_path / "comparativo.json").read_text(encoding="utf-8"))
    assert dados == comp_ab
    with (tmp_path / "tabela.csv").open(encoding="utf-8", newline="") as f:
        linhas = list(csv.reader(f, delimiter=";"))
    assert len(linhas) == len(comp_ab["linhas"]) + 1
    assert len(linhas[0]) == 11 and linhas[0][0] == "Indicador"
    assert linhas[1][3] == comp_ab["linhas"][0]["a"]["texto"]
    md = (tmp_path / "tabela.md").read_text(encoding="utf-8")
    assert "Não constitui recomendação de investimento" in md
    assert "numeração do PDF" in md
    assert "Critério de EBITDA: ajustado" in md


# --------------------------------------------------------------------------- CLI

def _argv(tmp_path, a="empresa_a", b="empresa_b", metricas=PASTA_IND, *extra):
    return ["--a", a, "--b", b, "--tri", TRI, "--metricas", str(metricas), "--config", str(CONFIG),
            "--saida", str(tmp_path / "saida"), "--sem-graficos", *extra]


def test_main_ok(tmp_path):
    assert comparar.main(_argv(tmp_path)) == 0
    pasta = tmp_path / "saida" / f"empresa_a_x_empresa_b_{TRI}"
    for nome in ("comparativo.json", "tabela.csv", "tabela.md"):
        assert (pasta / nome).is_file()
    assert contrato.main([str(pasta / "comparativo.json")]) == 0


def test_main_indicadores_ausentes(tmp_path, capsys):
    assert comparar.main(_argv(tmp_path, b="empresa_x")) == 1
    assert "python src/indicadores.py --empresa empresa_x --tri 3T26" in capsys.readouterr().err


def test_main_periodo_diferente(tmp_path):
    pasta = tmp_path / "ind"
    pasta.mkdir()
    for slug in ("empresa_a", "empresa_b"):
        dados = _ind(slug)
        if slug == "empresa_b":
            dados["periodo"] = "2T26"
        (pasta / f"{slug}_{TRI}_indicadores.json").write_text(json.dumps(dados), encoding="utf-8")
    assert comparar.main(_argv(tmp_path, metricas=pasta)) == 2
    assert not (tmp_path / "saida" / f"empresa_a_x_empresa_b_{TRI}" / "comparativo.json").exists()


def test_main_mesma_empresa(tmp_path):
    assert comparar.main(_argv(tmp_path, b="empresa_a")) == 2


def test_main_chama_graficos(tmp_path, monkeypatch):
    import sys
    import types

    chamadas = []

    def falso(comp, pasta):
        chamadas.append(Path(pasta))
        return [{"id": "teste", "arquivo": "graficos/teste.png", "descricao": "x", "fontes": {"a": [], "b": []}}]

    monkeypatch.setitem(sys.modules, "graficos", types.SimpleNamespace(gerar_graficos=falso))
    argv = [x for x in _argv(tmp_path) if x != "--sem-graficos"]
    assert comparar.main(argv) == 0
    pasta = tmp_path / "saida" / f"empresa_a_x_empresa_b_{TRI}"
    assert chamadas == [pasta]
    dados = json.loads((pasta / "comparativo.json").read_text(encoding="utf-8"))
    assert [g["id"] for g in dados["graficos"]] == ["teste"]


def test_rotulo_segmento_da_config_e_fallback(tmp_path):
    cfg = tmp_path / "e.toml"
    cfg.write_text('[segmentos]\nexterior = "Exterior (config)"\n', encoding="utf-8")
    rot = comparar.carregar_rotulos_segmentos(cfg)
    assert comparar.rotulo_segmento("exterior", rot) == "Exterior (config)"
    assert comparar.rotulo_segmento("america_do_norte", rot) == "America do norte"
    assert comparar.carregar_rotulos_segmentos(tmp_path / "nao_existe.toml") == {}


def test_usiminas_por_tonelada_usa_indicador_de_siderurgia_com_observacao():
    usiminas = json.loads((RAIZ / "metricas" / "usiminas_3T26_indicadores.json").read_text(encoding="utf-8"))
    gerdau = json.loads((RAIZ / "metricas" / "gerdau_3T26_indicadores.json").read_text(encoding="utf-8"))
    comp = comparar.montar_comparativo(gerdau, usiminas, comparar.carregar_config(CONFIG), TRI)

    rpt = _linha(comp, "receita_por_t")["b"]
    ebt = _linha(comp, "ebitda_por_t")["b"]
    assert rpt["status"] == ebt["status"] == "ok"
    assert rpt["valor"] == pytest.approx(5425.5319)
    assert ebt["valor"] == pytest.approx(520.3095)
    assert "consolidado inclui mineração" in rpt["obs"]
    assert "volume é de aço" in rpt["obs"]
