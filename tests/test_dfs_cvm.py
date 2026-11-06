"""Testes do parser CVM com recortes pequenos de páginas reais dos ITRs 3T26."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import dfs_cvm  # noqa: E402

CAB_DRE = """DFs Consolidadas / Demonstração do Resultado
(Reais Mil)
Código da Descrição da Conta Trimestre Atual Acumulado do Atual Igual Trimestre do Acumulado do Exercício
Conta 01/07/2026 à 30/09/2026 Exercício Exercício Anterior Anterior
01/01/2026 à 30/09/2026 01/07/2025 à 30/09/2025 01/01/2025 à 30/09/2025
"""

# Gerdau, DRE consolidada em 2 páginas (p. 29 e 30 do PDF), recortada
GERDAU_DRE_P1 = "PÁGINA: 16 de 65\n" + CAB_DRE + """3.01 Receita de Venda de Bens e/ou Serviços 18.690.518 53.276.811 17.983.143 52.884.229
3.02 Custo dos Bens e/ou Serviços Vendidos -15.339.568 -44.802.806 -15.841.051 -46.765.037
3.03 Resultado Bruto 3.350.950 8.474.005 2.142.092 6.119.192
3.11 Lucro/Prejuízo Consolidado do Período 1.563.097 4.042.498 1.089.880 2.712.181
ITR - rodapé embaralhado 24
"""
GERDAU_DRE_P2 = "PÁGINA: 17 de 65\n" + CAB_DRE + """3.11.01 Atribuído a Sócios da Empresa Controladora 1.554.156 4.009.996 1.079.395 2.685.174
3.11.02 Atribuído a Sócios Não Controladores 8.941 32.502 10.485 27.007
3.99 Lucro por Ação - (Reais / Ação)
3.99.01.01 ON 0,79 2,04 0,54 1,33
"""
GERDAU_BP = """DFs Consolidadas / Balanço Patrimonial Ativo
(Reais Mil)
Código da Descrição da Conta Trimestre Atual Exercício Anterior
Conta 30/09/2026 31/12/2025
1 Ativo Total 83.945.525 81.688.175
1.01.01 Caixa e Equivalentes de Caixa 5.695.892 5.929.170
"""
GERDAU_BP_PASSIVO = """DFs Consolidadas / Balanço Patrimonial Passivo
(Reais Mil)
Código da Descrição da Conta Trimestre Atual Exercício Anterior
Conta 30/09/2026 31/12/2025
2 Passivo Total 83.945.525 81.688.175
2.03 Patrimônio Líquido Consolidado 54.848.244 53.798.489
2.03.09 Participação dos Acionistas Não Controladores 193.224 213.096
"""
CAB_DFC = """DFs Consolidadas / Demonstração do Fluxo de Caixa (Método Indireto)
(Reais Mil)
Código da Descrição da Conta Acumulado do Atual Acumulado do Exercício
Conta Exercício Anterior
01/01/2026 à 30/09/2026 01/01/2025 à 30/09/2025
"""
# D&A e capex com códigos e textos diferentes nas duas empresas
GERDAU_DFC = CAB_DFC + """6.01 Caixa Líquido Atividades Operacionais 5.741.240 4.840.380
6.01.01.02 Depreciação e amortização 2.761.070 2.747.933
6.01.01.11 Provisão de passivos tributários, cíveis, trabalhistas e
ambientais 120.627 1.756
6.02.01 Adições de imobilizado -3.333.013 -5.211.509
6.02.02 Recebimento pela venda de imobilizado, investimento e 17.755 65.719
"""
USIMINAS_DFC = CAB_DFC + """6.01 Caixa Líquido Atividades Operacionais 977.232 1.062.745
6.01.01.04 Depreciação e Amortização 735.386 949.904
6.02.01 Valor Recebido pela Alienação de Imobilizado 20.626 54.411
6.02.02 Compras de Imobilizado -783.303 -729.356
"""
INDIVIDUAL_DRE = CAB_DRE.replace("Consolidadas", "Individuais") + \
    "3.01 Receita de Venda de Bens e/ou Serviços 1.000 2.000 3.000 4.000\n"
INDICE = "DFs Consolidadas / Demonstração do Resultado 29\nDFs Consolidadas 06 Notas Explicativas 32\n"


def pasta_com(base: Path, paginas: dict[int, str]) -> Path:
    p = base / "empresa_x_ITR_3T26"
    p.mkdir(parents=True)
    for n, txt in paginas.items():
        (p / f"pagina_{n:02d}.txt").write_text(txt, encoding="utf-8")
    return p


def gerdau(tmp_path):
    return pasta_com(tmp_path, {7: INDICE, 20: INDIVIDUAL_DRE, 26: GERDAU_BP, 27: GERDAU_BP_PASSIVO,
                                29: GERDAU_DRE_P1, 30: GERDAU_DRE_P2, 32: GERDAU_DFC})


def fatos_por(fatos, chave, periodo):
    return next(f for f in fatos if f["chave"] == chave and f["periodo"] == periodo)


def test_rotulos_de_periodo():
    from datetime import date
    assert dfs_cvm.rotulo_fluxo(date(2026, 7, 1), date(2026, 9, 30)) == "3T26"
    assert dfs_cvm.rotulo_fluxo(date(2026, 1, 1), date(2026, 9, 30)) == "9M26"
    assert dfs_cvm.rotulo_fluxo(date(2026, 1, 1), date(2026, 3, 31)) == "1T26"
    assert dfs_cvm.rotulo_saldo(date(2025, 12, 31)) == "4T25"
    with pytest.raises(dfs_cvm.ErroExtracao):
        dfs_cvm.rotulo_saldo(date(2026, 8, 15))


def test_colunas_pelas_datas_do_cabecalho_e_1T_com_2_colunas():
    cab_1t = ["Conta 01/01/2026 à 31/03/2026 01/01/2025 à 31/03/2025"]
    assert [c.rotulo for c in dfs_cvm.ler_colunas(cab_1t)] == ["1T26", "1T25"]
    cab_3t = CAB_DRE.splitlines()[2:]
    assert [c.rotulo for c in dfs_cvm.ler_colunas(cab_3t)] == ["3T26", "9M26", "3T25", "9M25"]


def test_dre_em_duas_paginas_e_ignora_individuais_e_indice(tmp_path):
    ext = dfs_cvm.extrair(gerdau(tmp_path))
    assert ext.paginas["DRE"] == [29, 30]
    fatos, _ = dfs_cvm.montar(ext, "gerdau", "3T26", "x")
    rec = fatos_por(fatos, "receita_liquida", "9M26")
    assert (rec["valor"], rec["valor_como_aparece"], rec["pagina"]) == (53276811.0, "53.276.811", 29)
    assert rec["evidencia"]["periodo"] == "01/01/2026 à 30/09/2026"
    contr = fatos_por(fatos, "lucro_liquido_controladores", "3T25")
    assert (contr["valor"], contr["pagina"]) == (1079395.0, 30)
    assert all(f["pagina"] != 20 for f in fatos)  # DFs Individuais nunca entram


def test_subcontas_com_codigo_diferente_achadas_pela_descricao(tmp_path):
    g = dfs_cvm.montar(dfs_cvm.extrair(gerdau(tmp_path)), "gerdau", "3T26", "g")[0]
    u_pasta = pasta_com(tmp_path / "u", {16: USIMINAS_DFC})
    u = dfs_cvm.montar(dfs_cvm.extrair(u_pasta), "usiminas", "3T26", "u")[0]
    assert fatos_por(g, "depreciacao_amortizacao", "9M26")["codigo_cvm"] == "6.01.01.02"
    assert fatos_por(u, "depreciacao_amortizacao", "9M26")["codigo_cvm"] == "6.01.01.04"
    assert fatos_por(g, "capex", "9M26")["valor"] == -3333013.0
    # "Valor Recebido pela Alienação de Imobilizado" não é capex
    assert fatos_por(u, "capex", "9M26")["codigo_cvm"] == "6.02.02"
    assert fatos_por(g, "pl_nao_controladores", "4T25")["codigo_cvm"] == "2.03.09"


def test_descricao_quebrada_em_duas_linhas(tmp_path):
    ext = dfs_cvm.extrair(gerdau(tmp_path))
    l = next(x for x in ext.linhas if x.codigo == "6.01.01.11")
    assert l.tokens == ["120.627", "1.756"]
    assert l.trecho.endswith("ambientais 120.627 1.756")


def test_consistencia_ok_e_falha_explicita(tmp_path):
    assert dfs_cvm.checar_consistencia(dfs_cvm.extrair(gerdau(tmp_path))) == []
    quebrado = GERDAU_DRE_P1.replace("3.03 Resultado Bruto 3.350.950", "3.03 Resultado Bruto 3.360.950")
    p = pasta_com(tmp_path / "q", {26: GERDAU_BP, 27: GERDAU_BP_PASSIVO, 29: quebrado, 30: GERDAU_DRE_P2})
    erros = dfs_cvm.checar_consistencia(dfs_cvm.extrair(p))
    assert any("lucro_bruto" in e and "3T26" in e for e in erros)


def test_cobertura_dfc_trimestral_nao_comparavel(tmp_path):
    _, cob = dfs_cvm.montar(dfs_cvm.extrair(gerdau(tmp_path)), "gerdau", "3T26", "x")
    fco_3t = next(c for c in cob if c["chave"] == "fco" and c["periodo"] == "3T26")
    assert fco_3t["status"] == "nao_comparavel"
    # emprestimos_cp não está no recorte: aparece como ausente, sem fato de valor zero
    aus = [c for c in cob if c["chave"] == "emprestimos_cp"]
    assert aus and all(c["status"] == "ausente" for c in aus)


def test_pdf_sem_texto_gera_diagnostico(tmp_path):
    p = pasta_com(tmp_path, {i: "" for i in range(1, 6)})
    with pytest.raises(dfs_cvm.ErroExtracao, match="sem camada de texto"):
        dfs_cvm.extrair(p)


def test_trimestre_errado_e_recusado(tmp_path):
    ext = dfs_cvm.extrair(gerdau(tmp_path))
    with pytest.raises(dfs_cvm.ErroExtracao, match="não é do 2T26"):
        dfs_cvm.conferir_trimestre(ext, "2T26")


def test_cli_grava_fatos_cobertura_e_manifesto(tmp_path):
    pasta = gerdau(tmp_path)
    saida = tmp_path / "metricas"
    assert dfs_cvm.main([str(pasta), "--empresa", "empresa_x", "--tri", "3T26", "--metricas", str(saida)]) == 0
    fatos = json.loads((saida / "empresa_x_3T26_itr_dfs.json").read_text())
    assert isinstance(fatos, list) and fatos
    assert (saida / "cobertura" / "empresa_x_3T26_itr_dfs.json").exists()
    assert (saida / "manifesto" / "empresa_x_ITR_3T26.json").exists()


def test_cli_sem_texto_nao_grava_nada(tmp_path):
    pasta = pasta_com(tmp_path, {1: "", 2: ""})
    saida = tmp_path / "metricas"
    assert dfs_cvm.main([str(pasta), "--empresa", "x", "--tri", "3T26", "--metricas", str(saida)]) == 2
    assert not saida.exists()
