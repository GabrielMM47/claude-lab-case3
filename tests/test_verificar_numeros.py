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
                       "periodo": "01/07/2026 à 30/09/2026", "coluna": 1, "n_colunas": 4}}
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
