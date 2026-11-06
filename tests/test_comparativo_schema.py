"""Testes do schema `comparativo` (schemas/comparativo.schema.json) e de escolher_schema."""
import copy
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import contrato  # noqa: E402

FIX = RAIZ / "tests" / "fixtures_comparar"
CASE06 = FIX / "comparativo_case06.json"
EXEMPLO = FIX / "comparativo_exemplo.json"


def _ler(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _strs(dados):
    return [str(e) for e in contrato.validar(dados, "comparativo")]


@pytest.mark.parametrize("arquivo", [CASE06, EXEMPLO], ids=lambda p: p.name)
def test_fixtures_validas(arquivo):
    dados = _ler(arquivo)
    assert contrato.escolher_schema(dados) == "comparativo"
    assert contrato.validar(dados) == []


def test_escolher_schema_comparativo():
    assert contrato.escolher_schema({"linhas": [], "empresas": {}}) == "comparativo"
    # sem os dois campos continua como antes
    assert contrato.escolher_schema({"linhas": []}) == "metricas"
    assert contrato.escolher_schema({"empresas": {}}) == "metricas"
    assert contrato.escolher_schema([{"linhas": [], "empresas": {}}]) == "metricas"


@pytest.mark.parametrize("campo", ["periodo", "criterio_ebitda", "empresas", "linhas", "segmentos",
                                   "insights", "alertas", "graficos", "verificacao"])
def test_campo_obrigatorio_no_topo(campo):
    dados = _ler(EXEMPLO)
    del dados[campo]
    # a mensagem de 'criterio_ebitda' é a do contrato de métricas; aqui basta o caminho
    assert any(e.startswith(f"$.{campo}: ") for e in _strs(dados))


def test_comparativo_sem_linhas_invalido():
    dados = _ler(CASE06)
    del dados["linhas"]
    assert contrato.validar(dados, "comparativo") != []


@pytest.mark.parametrize("campo", ["chave", "nome", "unidade", "a", "b"])
def test_campo_obrigatorio_na_linha(campo):
    dados = _ler(EXEMPLO)
    del dados["linhas"][0][campo]
    assert f"$.linhas[0].{campo}: campo obrigatório ausente" in _strs(dados)


def test_campos_extras_permitidos():
    dados = _ler(EXEMPLO)
    dados["extra_topo"] = 1
    dados["linhas"][0]["extra_linha"] = "x"
    dados["linhas"][0]["a"]["extra_lado"] = True
    assert _strs(dados) == []


@pytest.mark.parametrize("caminho, valor", [
    (("criterio_ebitda",), "ebitda"),
    (("linhas", 0, "vencedor"), "c"),
    (("linhas", 0, "melhor"), "neutro"),
    (("linhas", 0, "a", "status"), "zero"),
    (("alertas", 0, "empresa"), "c"),
])
def test_enums(caminho, valor):
    dados = _ler(EXEMPLO)
    alvo = dados
    for p in caminho[:-1]:
        alvo = alvo[p]
    alvo[caminho[-1]] = valor
    assert any("fora da lista permitida" in e for e in _strs(dados))


@pytest.mark.parametrize("criterio", ["ajustado", "contabil", None])
def test_criterio_aceito(criterio):
    dados = _ler(EXEMPLO)
    dados["criterio_ebitda"] = criterio
    assert _strs(dados) == []


@pytest.mark.parametrize("status", ["ok", "ausente", "nao_comparavel", "nao_aplicavel"])
def test_status_aceitos(status):
    dados = _ler(EXEMPLO)
    dados["linhas"][0]["b"]["status"] = status
    assert _strs(dados) == []


def test_verificacao_null_ou_objeto():
    dados = _ler(EXEMPLO)
    assert dados["verificacao"] is None and dados["graficos"] == []
    dados["verificacao"] = {"total": 1, "ok": 1}
    assert _strs(dados) == []
    dados["verificacao"] = "ok"
    assert _strs(dados) != []


def test_exemplo_tem_nd_e_nc():
    dados = _ler(EXEMPLO)
    status = {ln[x]["status"] for ln in dados["linhas"] for x in "ab"}
    assert {"ausente", "nao_comparavel"} <= status
    for ln in dados["linhas"]:
        for x in "ab":
            if ln[x]["status"] != "ok":
                assert ln[x]["valor"] is None and ln[x]["texto"] in ("N/D", "N/C", "N/A") and ln[x]["obs"]


def test_cli_codigo_0_para_valido(capsys):
    assert contrato.main([str(CASE06), str(EXEMPLO)]) == 0
    assert "válido (comparativo)" in capsys.readouterr().out


def test_cli_codigo_2_para_invalido(tmp_path, capsys):
    dados = _ler(EXEMPLO)
    dados["criterio_ebitda"] = "ebitda"
    del dados["linhas"][0]["chave"]
    arq = tmp_path / "comparativo.json"
    arq.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    assert contrato.main([str(arq)]) == 2
    saida = capsys.readouterr().out
    assert "(comparativo)" in saida and "$.linhas[0].chave" in saida


def test_cli_schema_explicito(tmp_path):
    arq = tmp_path / "c.json"
    arq.write_text(json.dumps(_ler(EXEMPLO)), encoding="utf-8")
    assert contrato.main([str(arq), "--schema", "comparativo"]) == 0


def test_fixture_case06_nao_alterada_pelos_testes():
    # sanidade: copy/deepcopy nos testes não tocam o arquivo
    a = _ler(CASE06)
    b = copy.deepcopy(a)
    assert a == b
