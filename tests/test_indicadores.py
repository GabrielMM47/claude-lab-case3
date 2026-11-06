"""Testes do motor de indicadores (CASE-04).

Os números abaixo são de uma empresa FICTÍCIA, redondos para dar para conferir à
mão. Os dados de teste compartilhados (tests/fixtures/) são do CASE-01; estes
ficam aqui dentro para o card andar sem depender dele.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import indicadores as ind  # noqa: E402


def fato(chave, periodo, valor, unidade="R$ mil", documento="itr", escopo="consolidado", pagina=1):
    return {"chave": chave, "metrica": chave, "empresa": "empresa_teste", "documento": documento,
            "escopo": escopo, "periodo": periodo, "unidade": unidade, "valor": valor,
            "valor_como_aparece": str(valor), "pagina": pagina, "trecho": chave}


# DFs em R$ mil, como no ITR
DRE_DFC = {
    "3T26": dict(receita_liquida=10_000_000, cpv=-7_000_000, lucro_bruto=3_000_000, ebit=2_000_000,
                 lair=1_600_000, ir_csll=-400_000, lucro_liquido=1_200_000,
                 lucro_liquido_controladores=1_100_000),
    "3T25": dict(receita_liquida=8_000_000, cpv=-6_000_000, lucro_bruto=2_000_000, ebit=1_000_000,
                 lair=800_000, ir_csll=-200_000, lucro_liquido=600_000,
                 lucro_liquido_controladores=550_000),
    "9M26": dict(receita_liquida=30_000_000, ebit=6_000_000, lair=4_800_000, ir_csll=-1_200_000,
                 lucro_liquido=3_600_000, lucro_liquido_controladores=3_300_000,
                 depreciacao_amortizacao=1_500_000, fco=5_000_000, capex=-2_000_000),
    "9M25": dict(receita_liquida=24_000_000, fco=4_000_000, capex=-1_500_000),
}
BALANCO = {
    "3T26": dict(ativo_total=50_000_000, caixa_equivalentes=3_000_000, aplicacoes_financeiras=1_000_000,
                 emprestimos_cp=2_000_000, emprestimos_lp=10_000_000, pl_total=25_000_000,
                 pl_nao_controladores=1_000_000),
    "4T25": dict(ativo_total=46_000_000, caixa_equivalentes=4_000_000, aplicacoes_financeiras=1_000_000,
                 emprestimos_cp=1_000_000, emprestimos_lp=11_000_000, pl_total=23_000_000,
                 pl_nao_controladores=1_000_000),
}


def fatos_base():
    fatos = [fato(c, p, v, pagina=29) for bloco in (DRE_DFC, BALANCO)
             for p, contas in bloco.items() for c, v in contas.items()]
    # complementar em R$ milhões (o release mistura unidades)
    fatos += [fato("ebitda_ajustado", "3T26", 2600.0, "R$ milhões", pagina=71),
              fato("ebitda_ajustado", "3T25", 1500.0, "R$ milhões", pagina=71),
              fato("ebitda_ajustado", "9M26", 7800.0, "R$ milhões", pagina=71),
              fato("ebitda_contabil", "3T26", 2500.0, "R$ milhões", pagina=71)]
    fatos += [fato("volume_vendas", "3T26", 2000, "mil t", "apresentacao", pagina=8),
              fato("volume_vendas", "3T25", 1800, "mil t", "apresentacao", pagina=8)]
    return fatos


def calcular(fatos=None):
    return ind.calcular(fatos if fatos is not None else fatos_base(), "empresa_teste", "3T26")


def pegar(res, chave, escopo="consolidado"):
    return next(i for i in res["indicadores"] if i["chave"] == chave and i["escopo"] == escopo)


# --- períodos e unidades --------------------------------------------------------
def test_periodos():
    assert ind.periodo_aa("3T26") == "3T25"
    assert ind.periodo_tt("3T26") == "2T26"
    assert ind.periodo_tt("1T26") == "4T25"
    assert ind.acumulado("3T26") == "9M26"
    assert ind.acumulado("1T26") == "1T26"
    assert ind.fim_exercicio_anterior("3T26") == "4T25"
    assert ind.fator_anualizacao("3T26") == pytest.approx(4 / 3)
    with pytest.raises(ValueError):
        ind.acumulado("2026")


def test_unidades():
    assert ind.normalizar(1500, "R$ mil") == (1.5, "R$ milhões")
    assert ind.normalizar(2.0, "R$ bilhões") == (2000.0, "R$ milhões")
    assert ind.normalizar(2.5, "milhões de t") == (2500.0, "mil t")
    assert ind.normalizar(12_000, "mil t/ano") == (12_000, "mil t/ano")
    assert ind.normalizar(18.2, "%") == (18.2, "%")
    with pytest.raises(ValueError):
        ind.normalizar(10, "US$ milhões")


def test_unidade_nao_suportada_vira_alerta_e_nao_derruba():
    res = calcular(fatos_base() + [fato("receita_liquida", "3T26", 900, "US$ milhões", escopo="segmento:eua")])
    assert any(a["tipo"] == "unidade" for a in res["alertas"])
    assert pegar(res, "receita_liquida")["valores"]["3T26"] == 10_000


# --- margens --------------------------------------------------------------------
def test_margem_em_pontos_percentuais():
    m = pegar(calcular(), "margem_bruta")
    assert m["valores"]["3T26"] == pytest.approx(30)
    assert m["valores"]["3T25"] == pytest.approx(25)
    assert m["var_aa"] == pytest.approx(5)
    assert m["unidade_var"] == "p.p."
    assert m["var_tt"] is None and m["valores"]["2T26"] is None  # sem dado de 2T26: nunca estimar


def test_ebitda_em_milhoes_e_receita_em_mil_na_mesma_conta():
    m = pegar(calcular(), "margem_ebitda_ajustado")
    assert m["valores"]["3T26"] == pytest.approx(26)       # 2.600 / 10.000
    assert m["valores"]["3T25"] == pytest.approx(18.75)    # 1.500 / 8.000
    assert m["var_aa"] == pytest.approx(7.25)


def test_ebitda_contabil_sem_da_trimestral_fica_indisponivel():
    m = pegar(calcular(), "margem_ebitda_contabil")
    assert m["valores"]["3T26"] == pytest.approx(25)       # reportado
    assert m["valores"]["3T25"] is None                    # sem reportado e sem D&A do trimestre
    assert m["var_aa"] is None


# --- endividamento ----------------------------------------------------------------
def test_divida_liquida_e_alavancagem():
    res = calcular()
    dl = pegar(res, "divida_liquida")
    assert dl["valores"]["3T26"] == pytest.approx(8000)    # 2.000 + 10.000 - 3.000 - 1.000
    assert dl["valores"]["4T25"] == pytest.approx(7000)
    assert dl["var_ano"] == pytest.approx(100 / 7, abs=1e-3)   # valores gravados com 4 casas
    assert pegar(res, "dl_ebitda_ajustado")["valores"]["3T26"] == pytest.approx(8000 / (7800 * 4 / 3), abs=1e-4)
    # contábil 9M = EBIT 6.000 + D&A 1.500 = 7.500; anualizado 10.000
    assert pegar(res, "dl_ebitda_contabil")["valores"]["3T26"] == pytest.approx(0.8)
    assert pegar(res, "divida_liquida_pl")["valores"]["3T26"] == pytest.approx(0.32)


# --- rentabilidade -----------------------------------------------------------------
def test_rentabilidade_anualizada_com_saldo_medio():
    res = calcular()
    roe = pegar(res, "roe")
    assert roe["periodo"] == "9M26"
    assert roe["valores"]["9M26"] == pytest.approx(4400 / 23000 * 100, abs=1e-3)   # 3.300 × 4/3 ÷ média(22.000, 24.000)
    assert roe["valores"]["9M25"] is None                                            # sem balanços de 2025 no ITR
    assert pegar(res, "roa")["valores"]["9M26"] == pytest.approx(10)                 # 4.800 ÷ 48.000
    assert pegar(res, "roi")["valores"]["9M26"] == pytest.approx(8000 / 31500 * 100, abs=1e-3)
    # alíquota efetiva 1.200 / 4.800 = 25%  -> NOPAT 6.000
    assert pegar(res, "roic")["valores"]["9M26"] == pytest.approx(6000 / 31500 * 100, abs=1e-3)


def test_aliquota_limitada_e_lair_negativo():
    fatos = [f for f in fatos_base() if not (f["periodo"] == "9M26" and f["chave"] in ("lair", "ir_csll"))]
    fatos += [fato("lair", "9M26", -100_000), fato("ir_csll", "9M26", 50_000)]
    roic = pegar(calcular(fatos), "roic")
    assert roic["valores"]["9M26"] == pytest.approx(8000 * 0.66 / 31500 * 100, abs=1e-3)
    assert "hipótese metodológica" in roic["obs"]


def test_aliquota_nominal_parametrizada():
    fatos = [f for f in fatos_base() if not (f["periodo"] == "9M26" and f["chave"] in ("lair", "ir_csll"))]
    fatos += [fato("lair", "9M26", -100_000), fato("ir_csll", "9M26", 50_000)]
    res = ind.calcular(fatos, "empresa_teste", "3T26", aliquota_nominal=0.25)
    assert pegar(res, "roic")["valores"]["9M26"] == pytest.approx(8000 * 0.75 / 31500 * 100, abs=1e-3)
    assert "25%" in res["politica_tributaria"]
    with pytest.raises(ValueError):
        ind.calcular(fatos, "empresa_teste", "3T26", aliquota_nominal=1.5)


def test_retorno_aa_usa_saldo_inicial_do_ano_anterior():
    fatos = fatos_base() + [
        fato("lucro_liquido_controladores", "9M25", 2_400_000),
        fato("pl_total", "3T25", 21_000_000), fato("pl_nao_controladores", "3T25", 1_000_000),
        fato("pl_total", "4T24", 19_000_000), fato("pl_nao_controladores", "4T24", 1_000_000),
    ]
    roe = pegar(calcular(fatos), "roe")
    # 9M25: 2.400 × 4/3 = 3.200 ÷ média(18.000; 20.000) = 16,84%
    assert roe["valores"]["9M25"] == pytest.approx(3200 / 19000 * 100, abs=1e-3)
    assert roe["var_aa"] == pytest.approx(4400 / 23000 * 100 - 3200 / 19000 * 100, abs=1e-3)
    assert roe["unidade_var"] == "p.p."


# --- caixa e setor --------------------------------------------------------------------
def test_caixa_acumulado():
    res = calcular()
    fcl = pegar(res, "fcl")
    assert fcl["valores"] == {"9M26": pytest.approx(3000), "9M25": pytest.approx(2500)}
    assert fcl["var_aa"] == pytest.approx(20)
    assert pegar(res, "capex")["valores"]["9M26"] == pytest.approx(2000)
    assert pegar(res, "capex_receita")["valores"]["9M26"] == pytest.approx(2000 / 30000 * 100, abs=1e-4)


def test_metricas_por_tonelada():
    res = calcular()
    receita_t = pegar(res, "receita_por_t")
    assert receita_t["unidade"] == "R$/t"
    assert receita_t["valores"]["3T26"] == pytest.approx(5000)          # 10.000 mi ÷ 2.000 mil t
    assert receita_t["valores"]["3T25"] == pytest.approx(8000 * 1000 / 1800, abs=1e-3)
    assert receita_t["var_aa"] == pytest.approx(12.5)
    assert pegar(res, "custo_por_t")["valores"]["3T26"] == pytest.approx(3500)
    assert pegar(res, "ebitda_por_t_ajustado")["valores"]["3T26"] == pytest.approx(1300)


def test_segmentos_mix_e_por_tonelada_so_no_mesmo_negocio():
    fatos = fatos_base() + [
        fato("receita_liquida", "3T26", 6000, "R$ milhões", escopo="segmento:siderurgia"),
        fato("receita_liquida", "3T26", 4000, "R$ milhões", escopo="segmento:mineracao"),
        fato("volume_vendas", "3T26", 1500, "mil t", "apresentacao", escopo="segmento:siderurgia"),
    ]
    res = calcular(fatos)
    assert pegar(res, "participacao_receita", "segmento:siderurgia")["valores"]["3T26"] == pytest.approx(60)
    assert pegar(res, "receita_por_t", "segmento:siderurgia")["valores"]["3T26"] == pytest.approx(4000)
    # receita consolidada com mineração não pode ser dividida pelo volume de aço
    consolidado = pegar(res, "receita_por_t")
    assert consolidado["status"] == "nao_comparavel" and consolidado["valores"]["3T26"] is None
    assert "mineração" in consolidado["obs"]
    assert pegar(res, "volume_vendas")["status"] == "ok"
    # segmento sem dado nenhum não gera linha vazia
    assert not any(i["escopo"] == "segmento:siderurgia" and i["chave"] == "custo_por_t" for i in res["indicadores"])


def test_setor_fora_de_siderurgia_fica_nao_aplicavel():
    res = ind.calcular(fatos_base(), "empresa_teste", "3T26", setor="varejo")
    assert pegar(res, "receita_por_t")["status"] == "nao_aplicavel"
    assert pegar(res, "volume_vendas")["status"] == "nao_aplicavel"
    assert pegar(res, "margem_bruta")["status"] == "ok"
    assert res["cobertura"]["nao_aplicavel"] >= 1


def test_status_e_cobertura():
    fatos = [f for f in fatos_base() if f["chave"] != "pl_nao_controladores"]
    res = calcular(fatos)
    assert pegar(res, "roe")["status"] == "ausente"
    assert pegar(res, "margem_bruta")["status"] == "ok"
    assert sum(res["cobertura"].values()) == len(res["indicadores"])
    assert all(i["status"] in ind.STATUS for i in res["indicadores"])


# --- regras de rigor ---------------------------------------------------------------------
def test_variacao_com_base_negativa_e_omitida():
    fatos = [f for f in fatos_base() if not (f["chave"] == "lucro_liquido" and f["periodo"] == "3T25")]
    fatos.append(fato("lucro_liquido", "3T25", -600_000))
    ll = pegar(calcular(fatos), "lucro_liquido")
    assert ll["var_aa"] is None
    assert "base negativa" in ll["obs"]


def test_duplicata_divergente_gera_alerta_e_itr_prevalece():
    fatos = fatos_base() + [fato("receita_liquida", "3T26", 10_500, "R$ milhões", "apresentacao", pagina=5)]
    res = calcular(fatos)
    alerta = next(a for a in res["alertas"] if a["tipo"] == "divergencia")
    assert {v["pagina"] for v in alerta["valores"]} == {29, 5}   # os dois valores, com referência
    assert alerta["mantido"] == "itr"
    assert pegar(res, "receita_liquida")["valores"]["3T26"] == pytest.approx(10_000)


def test_prioridade_nao_mistura_criterio_de_ebitda():
    # contábil e ajustado são fatos distintos: um não substitui o outro
    res = calcular()
    assert pegar(res, "ebitda_ajustado")["valores"]["3T26"] == pytest.approx(2600)
    assert pegar(res, "ebitda_contabil")["valores"]["3T26"] == pytest.approx(2500)


def test_duplicata_igual_nao_gera_alerta():
    fatos = fatos_base() + [fato("receita_liquida", "3T26", 10_000, "R$ milhões", "apresentacao")]
    assert not any(a["tipo"] == "divergencia" for a in calcular(fatos)["alertas"])


def test_dado_faltante_fica_indisponivel_com_motivo():
    fatos = [f for f in fatos_base() if f["chave"] != "pl_nao_controladores"]
    roe = pegar(calcular(fatos), "roe")
    assert roe["disponivel"] is False
    assert "pl_nao_controladores" in roe["obs"]


def test_efeito_pontual_e_divergencia_de_definicao():
    fatos = fatos_base() + [
        {**fato("ajuste_ebitda", "3T25", 300.0, "R$ milhões", pagina=72), "metrica": "Impairment"},
        fato("divida_liquida_reportada", "3T26", 9000.0, "R$ milhões", pagina=73),
    ]
    res = calcular(fatos)
    pontual = [a for a in res["alertas"] if a["tipo"] == "efeito_pontual"]
    assert pontual and pontual[0]["periodo"] == "3T25" and "Impairment" in pontual[0]["texto"]
    assert any(a["tipo"] == "divergencia_definicao" for a in res["alertas"])
    assert res["ajustes_ebitda"]["3T25"][0]["valor"] == pytest.approx(300)
    assert pegar(res, "divida_liquida_reportada")["valores"]["3T26"] == pytest.approx(9000)


def test_todo_indicador_disponivel_e_rastreavel():
    for item in calcular()["indicadores"]:
        if item["disponivel"]:
            assert item["insumos"], item["chave"]
            assert all(i["pagina"] and i["documento"] for i in item["insumos"]), item["chave"]


def test_qualitativo_e_ignorado():
    fatos = fatos_base() + [{"chave": "qualitativo", "metrica": "estrategia", "tema": "estrategia",
                             "documento": "apresentacao", "resumo": "x", "pagina": 3, "trecho": "x"}]
    assert pegar(calcular(fatos), "receita_liquida")["disponivel"]


# --- linha de comando ---------------------------------------------------------------------
def test_cli_grava_json(tmp_path):
    fatos = fatos_base()
    itr = [f for f in fatos if f["documento"] == "itr"]
    apres = [f for f in fatos if f["documento"] == "apresentacao"]
    (tmp_path / "empresa_teste_3T26_itr_dfs.json").write_text(json.dumps(itr), encoding="utf-8")
    (tmp_path / "empresa_teste_3T26_apresentacao_operacional.json").write_text(json.dumps(apres), encoding="utf-8")
    ind.main(["--empresa", "empresa_teste", "--tri", "3T26", "--metricas", str(tmp_path)])
    saida = json.loads((tmp_path / "empresa_teste_3T26_indicadores.json").read_text(encoding="utf-8"))
    assert saida["empresa"] == "empresa_teste" and saida["anualizacao"] == "9M26 × 4/3"
    assert pegar(saida, "margem_bruta")["valores"]["3T26"] == pytest.approx(30)
    # rodar de novo não lê o próprio arquivo de saída como fato
    ind.main(["--empresa", "empresa_teste", "--tri", "3T26", "--metricas", str(tmp_path)])


# --- Integração com os JSONs reais do CASE-02/03 (06/11) ------------------------
@pytest.mark.parametrize("unidade, esperado", [
    ("1.000 toneladas", (1351.0, "mil t")), ("Mil toneladas", (1351.0, "mil t")),
    ("kton", (1351.0, "mil t")), ("milhões de toneladas/ano", (1_351_000.0, "mil t/ano")),
])
def test_variantes_de_unidade_de_volume(unidade, esperado):
    assert ind.normalizar(1351, unidade) == esperado


def test_r_milhao_no_singular():
    assert ind.normalizar(12.5, "R$ milhão") == (12.5, "R$ milhões")


@pytest.mark.parametrize("unidade", ["MT", "Mt"])
def test_mt_e_ambiguo_e_nao_e_adivinhado(unidade):
    # o mesmo arquivo trazia "6884 MT" (mil t) e "0,9 MT" (milhões de t)
    with pytest.raises(ValueError, match="ambígua"):
        ind.normalizar(6884, unidade)


def test_valores_diferentes_no_mesmo_documento_ficam_ambiguos():
    # aço e minério gravados como volume_vendas consolidado no mesmo ITR: nenhum é usado
    fatos = fatos_base() + [
        {**fato("volume_vendas", "3T26", 1034, "mil t", pagina=24), "metrica": "Volume de vendas de aço"},
        {**fato("volume_vendas", "3T26", 2014, "mil t", pagina=24), "metrica": "Volume de vendas de minério"},
    ]
    res = calcular(fatos)
    alerta = next(a for a in res["alertas"] if a["tipo"] == "ambiguo")
    assert {1034, 2014} <= {v["valor"] for v in alerta["valores"]}  # e o 2000 da apresentação
    item = pegar(res, "volume_vendas")
    assert item["status"] == "ausente" and "ambíguo" in item["obs"]


def test_documento_de_maior_prioridade_resolve_ambiguidade_da_apresentacao():
    fatos = fatos_base() + [
        fato("volume_vendas", "3T26", 1034, "mil t", "apresentacao", pagina=16),
        fato("volume_vendas", "3T26", 979, "mil t", "apresentacao", pagina=17),
        fato("volume_vendas", "3T26", 1034, "mil t", "itr", pagina=36),
    ]
    res = calcular(fatos)
    assert not any(a["tipo"] == "ambiguo" for a in res["alertas"])
    assert pegar(res, "volume_vendas")["valores"]["3T26"] == pytest.approx(1034)


def test_ajuste_recorrente_nao_conta_como_efeito_pontual():
    recorrente = {**fato("ajuste_ebitda", "3T25", 300.0, "R$ milhões", pagina=72),
                  "metrica": "EBITDA proporcional de controladas em conjunto", "natureza": "recorrente"}
    assert not any(a["tipo"] == "efeito_pontual" for a in calcular(fatos_base() + [recorrente])["alertas"])
    pontual = {**recorrente, "metrica": "Impairment", "natureza": "pontual"}
    alertas = calcular(fatos_base() + [recorrente, pontual])["alertas"]
    texto = next(a["texto"] for a in alertas if a["tipo"] == "efeito_pontual")
    assert "Impairment" in texto and "controladas" not in texto


def test_valor_absoluto_nao_tem_melhor():
    # tamanho não é desempenho: o comparativo não pode eleger vencedor por receita ou volume
    res = calcular()
    for chave in ("receita_liquida", "ebitda_ajustado", "lucro_liquido", "divida_liquida", "volume_vendas"):
        assert pegar(res, chave)["melhor"] == "neutro", chave
    assert pegar(res, "margem_ebitda_ajustado")["melhor"] == "maior"
    assert pegar(res, "dl_ebitda_ajustado")["melhor"] == "menor"
