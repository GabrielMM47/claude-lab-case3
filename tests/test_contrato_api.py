"""CASE-01: APIs do contrato (catálogo de fatos, validar_fato, conversões, períodos, pastas)
e as fixtures fictícias de tests/fixtures_ficticias/."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import contrato  # noqa: E402
import indicadores  # noqa: E402

FICTICIAS = RAIZ / "tests" / "fixtures_ficticias"
METRICAS_FICT = FICTICIAS / "metricas"
ARQUIVOS_FATOS = sorted(METRICAS_FICT.glob("*.json"))
FATOS = [(arq.name, i, f) for arq in ARQUIVOS_FATOS
         for i, f in enumerate(json.loads(arq.read_text(encoding="utf-8")))]


def _fato(**mudancas) -> dict:
    base = {"chave": "receita_liquida", "metrica": "Receita", "empresa": "empresa_a",
            "documento": "itr", "escopo": "consolidado", "periodo": "3T26", "unidade": "R$ mil",
            "valor": 1000.0, "valor_como_aparece": "1.000", "pagina": 21, "trecho": "Receita 1.000"}
    base.update(mudancas)
    return {k: v for k, v in base.items() if v is not ...}


# ------------------------------------------------------------------ fixtures fictícias

def test_fixtures_ficticias_em_dia():
    r = subprocess.run([sys.executable, str(FICTICIAS / "gerar.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_fixtures_so_de_empresas_ficticias():
    assert ARQUIVOS_FATOS
    assert {f["empresa"] for _, _, f in FATOS} == {"empresa_a", "empresa_b", "empresa_c"}


@pytest.mark.parametrize("nome,i,fato", FATOS, ids=[f"{n}[{i}]" for n, i, _ in FATOS])
def test_validar_fato_aceita_todas_as_fixtures(nome, i, fato):
    assert contrato.validar_fato(fato) == []


@pytest.mark.parametrize("empresa", ["empresa_a", "empresa_b"])
def test_fixtures_cobrem_todo_o_catalogo(empresa):
    chaves = {f["chave"] for f in contrato.carregar_fatos(empresa, "3T26", METRICAS_FICT)}
    faltam = set(contrato.CATALOGO_FATOS) - chaves
    # ajuste_ebitda só existe onde há efeito pontual (empresa_b)
    assert faltam <= ({"ajuste_ebitda"} if empresa == "empresa_a" else set())


@pytest.mark.parametrize("empresa", ["empresa_a", "empresa_b"])
def test_fixtures_tem_periodos_do_contrato(empresa):
    fatos = contrato.carregar_fatos(empresa, "3T26", METRICAS_FICT)
    fluxo = {f["periodo"] for f in fatos if f.get("tipo") == "fluxo"}
    saldo = {f["periodo"] for f in fatos if f.get("tipo") == "saldo"}
    assert {"3T26", "3T25", "9M26", "9M25"} <= fluxo
    assert {"3T26", "4T25"} <= saldo


def test_empresa_c_incompleta():
    chaves = {f["chave"] for f in contrato.carregar_fatos("empresa_c", "3T26", METRICAS_FICT)}
    assert "receita_liquida" in chaves
    assert not chaves & {"ebitda_ajustado", "ebitda_contabil", "volume_vendas", "fco"}


@pytest.mark.parametrize("empresa", ["empresa_a", "empresa_b", "empresa_c"])
def test_indicadores_rodam_nas_fixtures_e_seguem_o_contrato(empresa):
    """Integração CASE-01 → CASE-04: fatos fictícios → indicadores válidos no schema."""
    fatos = contrato.carregar_fatos(empresa, "3T26", METRICAS_FICT)
    resultado = indicadores.calcular(fatos, empresa, "3T26")
    assert contrato.escolher_schema(resultado) == "indicadores"
    assert contrato.validar(resultado) == []


def test_empresa_c_ausencia_nao_vira_zero():
    resultado = indicadores.calcular(contrato.carregar_fatos("empresa_c", "3T26", METRICAS_FICT),
                                     "empresa_c", "3T26")
    ausentes = [i for i in resultado["indicadores"] if i["status"] == "ausente"]
    assert ausentes
    assert all(i["valores"].get(i["periodo"]) is None for i in ausentes)


def test_comparativo_ficticio_com_pngs():
    pasta = FICTICIAS / "comparativo" / "empresa_a_x_empresa_b_3T26"
    comp = json.loads((pasta / "comparativo.json").read_text(encoding="utf-8"))
    assert contrato.validar(comp) == []
    assert len(comp["graficos"]) == 2
    for g in comp["graficos"]:
        assert (pasta / g["arquivo"]).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


# ------------------------------------------------------------------ validar_fato

def test_validar_fato_rejeita_sem_pagina():
    erros = contrato.validar_fato(_fato(pagina=...))
    assert erros == ["$.pagina: campo obrigatório ausente"]


@pytest.mark.parametrize("mudanca,trecho_do_erro", [
    ({"trecho": ...}, "$.trecho: campo obrigatório ausente"),
    ({"metrica": ...}, "$.metrica: campo obrigatório ausente"),
    ({"pagina": 0}, "$.pagina"),
    ({"chave": "ebitda_inventado"}, "fora do catálogo"),
    ({"periodo": "3T26 vs 2T26"}, "$.periodo"),
    ({"periodo": "13M26"}, "meses fora de 1..12"),
    ({"escopo": "controladora"}, "$.escopo"),
    ({"escopo": "segmento:mineração"}, "$.escopo"),
    ({"documento": "release"}, "$.documento"),
    ({"unidade": "kton"}, "$.unidade"),
])
def test_validar_fato_rejeita(mudanca, trecho_do_erro):
    erros = contrato.validar_fato(_fato(**mudanca))
    assert any(trecho_do_erro in e for e in erros), erros


def test_validar_fato_qualitativo():
    q = {"chave": "qualitativo", "metrica": "estrategia", "tema": "estrategia", "empresa": "empresa_a",
         "documento": "apresentacao", "resumo": "x", "pagina": 5, "trecho": "y"}
    assert contrato.validar_fato(q) == []
    assert any("$.tema" in e for e in contrato.validar_fato({**q, "tema": "fofoca"}))


def test_validar_fato_nao_objeto():
    assert contrato.validar_fato([1]) == ["$: esperado objeto, veio lista"]


def test_catalogo_tem_tipo_e_codigo():
    assert contrato.CATALOGO_FATOS["receita_liquida"]["codigo_cvm"] == "3.01"
    assert contrato.CATALOGO_FATOS["pl_total"]["tipo"] == "saldo"
    assert contrato.CATALOGO_FATOS["fco"]["tipo"] == "fluxo"
    assert all({"nome", "tipo", "codigo_cvm", "origem"} <= set(v) for v in contrato.CATALOGO_FATOS.values())


# ------------------------------------------------------------------ carregar_fatos

def test_carregar_fatos_ignora_indicadores_e_outras_empresas(tmp_path):
    (tmp_path / "x_3T26_itr_dfs.json").write_text(json.dumps([_fato(empresa="x")]), encoding="utf-8")
    (tmp_path / "x_3T26_indicadores.json").write_text(json.dumps({"indicadores": []}), encoding="utf-8")
    (tmp_path / "y_3T26_itr_dfs.json").write_text(json.dumps([_fato(empresa="y")]), encoding="utf-8")
    (tmp_path / "x_2T26_itr_dfs.json").write_text(json.dumps([_fato(empresa="x")]), encoding="utf-8")
    assert [f["empresa"] for f in contrato.carregar_fatos("x", "3T26", tmp_path)] == ["x"]


def test_carregar_fatos_rejeita_nao_lista(tmp_path):
    (tmp_path / "x_3T26_itr_dfs.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="esperado lista"):
        contrato.carregar_fatos("x", "3T26", tmp_path)


# ------------------------------------------------------------------ para_milhoes

@pytest.mark.parametrize("valor,unidade,esperado", [
    (12_345_000, "R$ mil", 12_345.0),
    (1_234.5, "R$ milhões", 1_234.5),
    (1_234.5, "R$ milhão", 1_234.5),
    (2.5, "R$ bilhões", 2_500.0),
    (-1_000, "r$  MIL", -1.0),
])
def test_para_milhoes(valor, unidade, esperado):
    assert contrato.para_milhoes(valor, unidade) == pytest.approx(esperado)


@pytest.mark.parametrize("unidade", ["mil t", "%", "US$ mil", "", None])
def test_para_milhoes_unidade_desconhecida(unidade):
    with pytest.raises(ValueError, match="unidade monetária desconhecida"):
        contrato.para_milhoes(1.0, unidade)


# ------------------------------------------------------------------ periodo_comparavel / pasta_saida

@pytest.mark.parametrize("tri,base,esperado", [
    ("3T26", "aa", "3T25"), ("3T26", "tt", "2T26"), ("1T26", "tt", "4T25"),
    ("9M26", "aa", "9M25"), ("4T25", "aa", "4T24"),
])
def test_periodo_comparavel(tri, base, esperado):
    assert contrato.periodo_comparavel(tri, base) == esperado


@pytest.mark.parametrize("tri,base", [("9M26", "tt"), ("3T26", "xx"), ("T326", "aa"), ("", "aa")])
def test_periodo_comparavel_invalido(tri, base):
    with pytest.raises(ValueError):
        contrato.periodo_comparavel(tri, base)


def test_pasta_saida():
    assert contrato.pasta_saida("gerdau", "3T26", "itr") == Path("saida/gerdau_ITR_3T26")
    assert contrato.pasta_saida("usiminas", "3T26", "apresentacao") == Path("saida/usiminas_APRESENTACAO_3T26")
    with pytest.raises(ValueError):
        contrato.pasta_saida("gerdau", "3T26", "release")


# ------------------------------------------------------------------ indicadores.json

def test_indicadores_json_nao_e_lista_de_fatos():
    """Bug: o indicadores.json (dict) caía no schema 'metricas' e saía 'esperado lista'."""
    arq = RAIZ / "tests" / "fixtures_comparar" / "indicadores" / "empresa_a_3T26_indicadores.json"
    dados = json.loads(arq.read_text(encoding="utf-8"))
    assert contrato.escolher_schema(dados) == "indicadores"
    assert contrato.validar(dados) == []
    assert contrato.main([str(arq)]) == 0


def test_indicadores_json_invalido():
    erros = [str(e) for e in contrato.validar({"indicadores": [{"chave": "roe"}]}, "indicadores")]
    assert "$.empresa: campo obrigatório ausente" in erros
    assert "$.indicadores[0].insumos: campo obrigatório ausente" in erros
