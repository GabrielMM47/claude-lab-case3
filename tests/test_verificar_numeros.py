"""Testes do verificador endurecido: coluna errada, escopo errado, token parcial, campos ausentes."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from verificar_numeros import avaliar, checar, tem_token  # noqa: E402

PAG_CONSOLIDADA = """DFs Consolidadas / Demonstração do Resultado
(Reais Mil)
Conta 01/07/2026 à 30/09/2026 Exercício Exercício Anterior Anterior
01/01/2026 à 30/09/2026 01/07/2025 à 30/09/2025 01/01/2025 à 30/09/2025
3.01 Receita de Venda de Bens e/ou Serviços 6.202.422 18.204.789 6.604.238 20.088.363
3.11.01 Atribuído a Sócios da Empresa Controladora 229.193 1.383.002 -3.539.981 -3.143.946
"""
PAG_INDIVIDUAL = PAG_CONSOLIDADA.replace("DFs Consolidadas", "DFs Individuais")
CAB = ("Conta 01/07/2026 à 30/09/2026 Exercício Exercício Anterior Anterior 01/01/2026 à 30/09/2026 "
       "01/07/2025 à 30/09/2025 01/01/2025 à 30/09/2025")
LINHA = "3.01 Receita de Venda de Bens e/ou Serviços 6.202.422 18.204.789 6.604.238 20.088.363"


@pytest.fixture
def pasta(tmp_path):
    (tmp_path / "pagina_14.txt").write_text(PAG_CONSOLIDADA, encoding="utf-8")
    (tmp_path / "pagina_15.txt").write_text(PAG_INDIVIDUAL, encoding="utf-8")
    return tmp_path


def fato(**mudancas):
    f = {"chave": "receita_liquida", "metrica": "Receita", "empresa": "usiminas", "documento": "itr",
         "escopo": "consolidado", "periodo": "3T26", "periodo_inicio": "2026-07-01",
         "periodo_fim": "2026-09-30", "unidade": "R$ mil", "valor": 6202422.0,
         "valor_como_aparece": "6.202.422", "pagina": 14, "trecho": LINHA,
         "evidencia": {"escopo": "DFs Consolidadas / Demonstração do Resultado", "unidade": "(Reais Mil)",
                       "periodo": "01/07/2026 à 30/09/2026", "coluna": 1, "n_colunas": 4,
                       "cabecalho_colunas": CAB}}
    f.update(mudancas)
    return f


def test_fato_correto_ok(pasta):
    assert avaliar(fato(), pasta)[0] == "OK"


def test_numero_existe_na_pagina_mas_na_coluna_errada(pasta):
    # 6.604.238 está na linha, mas é o 3T25 (coluna 3), não o 3T26 (coluna 1)
    status, erros, _ = avaliar(fato(valor=6604238.0, valor_como_aparece="6.604.238"), pasta)
    assert status == "ERRO"
    assert any("coluna 1" in e and "coluna 3" in e for e in erros)


def test_periodo_da_evidencia_diferente_do_fato(pasta):
    ev = fato()["evidencia"] | {"periodo": "01/07/2025 à 30/09/2025", "coluna": 3}
    status, erros, _ = avaliar(fato(valor=6604238.0, valor_como_aparece="6.604.238", evidencia=ev), pasta)
    assert status == "ERRO" and any("período" in e for e in erros)


def test_escopo_errado_pagina_individual(pasta):
    status, erros, _ = avaliar(fato(pagina=15), pasta)
    assert status == "ERRO"
    assert any("DFs Individuais" in e or "evidência de escopo" in e for e in erros)


def test_escopo_controladora_proibido(pasta):
    assert avaliar(fato(escopo="controladora"), pasta)[0] == "ERRO"


def test_campos_obrigatorios_ausentes(pasta):
    f = fato()
    del f["pagina"]
    assert avaliar(f, pasta)[0] == "ERRO"
    f = fato()
    del f["unidade"]
    status, erros, _ = avaliar(f, pasta)
    assert status == "ERRO" and "unidade" in erros[0]


def test_token_parcial_nao_conta():
    assert tem_token("229.193", "controladora 229.193 1.383.002")
    assert not tem_token("383.002", "controladora 229.193 1.383.002")
    assert not tem_token("1.383", "controladora 229.193 1.383.002")
    assert not tem_token("6.202", "receita 6.202,4 mi")


def test_valor_na_pagina_mas_fora_do_trecho(pasta):
    status, erros, _ = avaliar(fato(valor=229193.0, valor_como_aparece="229.193",
                                    evidencia=fato()["evidencia"] | {"coluna": None}), pasta)
    assert status == "ERRO" and any("não no trecho" in e for e in erros)


def test_unidade_incoerente(pasta):
    ev = fato()["evidencia"]
    assert avaliar(fato(unidade="R$ milhões", evidencia=ev), pasta)[0] == "ERRO"


def test_sem_evidencia_fica_para_revisar(pasta):
    status, erros, pend = avaliar(fato(evidencia=None), pasta)
    assert status == "REVISAR" and not erros
    assert any("coluna" in p for p in pend) and any("unidade" in p for p in pend)


def test_valor_numerico_diferente_do_texto(pasta):
    status, erros, _ = avaliar(fato(valor=6202.422), pasta)  # erro clássico de unidade
    assert status == "ERRO" and any("não bate" in e for e in erros)


def test_checar_compativel_devolve_so_erros(pasta):
    assert checar(fato(), pasta) == []
    assert checar(fato(evidencia=None), pasta) == []  # pendência não é erro


PAG_RELEASE = """Valores Consolidados
em R$ milhões 3T26 2T26 ∆ 3T25 ∆
Dívida Líquida (471) (499) -6% 327 -
Dívida Líquida/EBITDA Ajustado -0,20x -0,22x 0,02x 0,16x -0,35x
(Valores expressos em milhares de reais, exceto quando especificado)
"""


def fato_release(**mudancas):
    f = {"chave": "dl_ebitda_reportado", "metrica": "DL/EBITDA", "empresa": "usiminas", "documento": "itr",
         "escopo": "consolidado", "periodo": "3T25", "unidade": "x", "valor": 0.16,
         "valor_como_aparece": "0,16x", "pagina": 24,
         "trecho": "Dívida Líquida/EBITDA Ajustado -0,20x -0,22x 0,02x 0,16x -0,35x",
         "evidencia": {"escopo": "Valores Consolidados", "periodo": "em R$ milhões 3T26 2T26 ∆ 3T25 ∆",
                       "coluna": 4, "n_colunas": 5, "cabecalho_colunas": "em R$ milhões 3T26 2T26 ∆ 3T25 ∆"}}
    f.update(mudancas)
    return f


@pytest.fixture
def pasta_release(tmp_path):
    (tmp_path / "pagina_24.txt").write_text(PAG_RELEASE, encoding="utf-8")
    return tmp_path


def test_multiplo_x_e_coluna_delta_nao_confunde(pasta_release):
    assert avaliar(fato_release(), pasta_release)[0] == "OK"
    # 0,02x é a coluna Δ (3), não o 3T25
    st, erros, _ = avaliar(fato_release(valor=0.02, valor_como_aparece="0,02x"), pasta_release)
    assert st == "ERRO" and any("coluna 4" in e for e in erros)


def test_celula_vazia_conta_como_coluna(pasta_release):
    f = fato_release(chave="divida_liquida_reportada", unidade="R$ milhões", valor=327.0,
                     valor_como_aparece="327", trecho="Dívida Líquida (471) (499) -6% 327 -")
    f["evidencia"] |= {"unidade": "em R$ milhões"}
    assert avaliar(f, pasta_release)[0] == "OK"


def test_milhares_de_reais_e_coerente_com_r_mil(pasta_release):
    f = fato_release(chave="divida_liquida_reportada", unidade="R$ mil", valor=327.0,
                     valor_como_aparece="327", trecho="Dívida Líquida (471) (499) -6% 327 -")
    f["evidencia"] |= {"unidade": "(Valores expressos em milhares de reais, exceto quando especificado)"}
    assert avaliar(f, pasta_release)[0] == "OK"
    f["unidade"] = "R$ milhões"
    assert avaliar(f, pasta_release)[0] == "ERRO"


def test_revisao_manual_registrada_vira_ok(pasta):
    f = fato(evidencia=None)
    assert avaliar(f, pasta)[0] == "REVISAR"
    f["revisao_manual"] = {"por": "Gabriel Martins", "nota": "conferi a coluna 3T26 na p. 14"}
    st, _, pend = avaliar(f, pasta)
    assert st == "OK" and "revisão manual" in pend[0]
    # revisão manual não apaga erro
    f["valor"] = 1.0
    assert avaliar(f, pasta)[0] == "ERRO"


PAG_EBITDA = """EBITDA AJUSTADO
R$ mil 3T26 2T26 3T25
EBITDA Instrução CVM 156 588.039 798.602 (1.747.170)
EBITDA (Instrução CVM 156) 2.041.362 (547.928) -
"""


def fato_ebitda(**mudancas):
    f = {"chave": "ebitda_contabil", "metrica": "EBITDA CVM 156", "empresa": "usiminas", "documento": "itr",
         "escopo": "consolidado", "periodo": "3T26", "unidade": "R$ mil", "valor": 588039.0,
         "valor_como_aparece": "588.039", "pagina": 28,
         "trecho": "EBITDA Instrução CVM 156 588.039 798.602 (1.747.170)",
         "evidencia": {"escopo": "EBITDA AJUSTADO", "unidade": "R$ mil", "periodo": "R$ mil 3T26 2T26 3T25",
                       "coluna": 1, "n_colunas": 3, "cabecalho_colunas": "R$ mil 3T26 2T26 3T25"}}
    f.update(mudancas)
    return f


@pytest.fixture
def pasta_ebitda(tmp_path):
    (tmp_path / "pagina_28.txt").write_text(PAG_EBITDA, encoding="utf-8")
    return tmp_path


def test_numero_no_nome_da_conta_nao_vira_coluna(pasta_ebitda):
    """Erro real: o '156' de 'Instrução CVM 156' foi lido como a coluna do 3T26."""
    assert avaliar(fato_ebitda(), pasta_ebitda)[0] == "OK"
    errado = fato_ebitda(valor=156.0, valor_como_aparece="156")
    errado["evidencia"] = errado["evidencia"] | {"n_colunas": 4}
    st, erros, _ = avaliar(errado, pasta_ebitda)
    assert st == "ERRO" and any("cabeçalho tem 3 colunas" in e for e in erros)


def test_parentese_sem_par_nao_e_numero():
    from verificar_numeros import valores_finais
    assert valores_finais("EBITDA (Instrução CVM 156) 2.041.362 (547.928) -") == ["2.041.362", "(547.928)", "-"]


def test_coluna_com_rotulo_de_outro_periodo(pasta_ebitda):
    # valor do 2T26 (coluna 2) etiquetado como 3T26
    f = fato_ebitda(valor=798602.0, valor_como_aparece="798.602")
    f["evidencia"] = f["evidencia"] | {"coluna": 2}
    st, erros, _ = avaliar(f, pasta_ebitda)
    assert st == "ERRO" and any("'2T26', não '3T26'" in e for e in erros)


def test_coluna_de_variacao_e_recusada(pasta_release):
    f = fato_release(periodo="3T26", valor=0.02, valor_como_aparece="0,02x")
    f["evidencia"] = f["evidencia"] | {"coluna": 3}
    st, erros, _ = avaliar(f, pasta_release)
    assert st == "ERRO" and any("variação" in e for e in erros)


def test_sem_cabecalho_fica_para_revisar(pasta):
    f = fato()
    del f["evidencia"]["cabecalho_colunas"]
    st, _, pend = avaliar(f, pasta)
    assert st == "REVISAR" and any("cabecalho_colunas" in p for p in pend)


def test_formato_legado_sem_chave_fica_para_revisar(pasta):
    """Fatos sem 'chave' (template antigo, extrair_balanco.py) não reprovam, mas não entram no pipeline."""
    f = fato()
    for c in ("chave", "documento", "escopo"):
        del f[c]
    st, erros, pend = avaliar(f, pasta)
    assert st == "REVISAR" and not erros and any("fora do contrato" in p for p in pend)
    f["valor"] = 1.0  # número errado continua sendo erro
    assert avaliar(f, pasta)[0] == "ERRO"


def test_fato_do_contrato_sem_escopo_e_erro(pasta):
    f = fato()
    del f["escopo"]
    assert avaliar(f, pasta)[0] == "ERRO"


def test_negrito_falso_triplicado_e_aceito_so_no_sentido_do_token():
    import verificar_numeros as vn
    pagina = "Volume de Vendas\n111...555888222 777...666999777 777666333 777444111\n"
    assert vn.tem_token("1.582", pagina) and vn.tem_token("741", pagina)
    assert not vn.tem_token("1.583", pagina)
    assert not vn.tem_token("1", "valor 111 legítimo")  # não desfaz triplicação no texto
