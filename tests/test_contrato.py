"""Testes do contrato de dados (src/contrato.py + schemas/*.schema.json).

Autocontido: não usa fixtures do conftest.py. Roda só sobre arquivos versionados
(templates/, metricas/, schemas/) e dados inline.
"""
import copy
import json
import socket
import sys
import time
from pathlib import Path

import jsonschema
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import contrato  # noqa: E402

TEMPLATE = RAIZ / "templates" / "metricas_exemplo.json"
BALANCOS = sorted((RAIZ / "metricas").glob("balanco_*.json"))
BALANCOS_DADOS = [p for p in BALANCOS if not p.name.endswith(".meta.json")]
METAS = [p for p in BALANCOS if p.name.endswith(".meta.json")]

# Registro-base R (1º item do template) e E (2º item), seção 8.4 do SPEC.
R = {"metrica": "Receita líquida", "periodo": "3T26 vs 3T25", "base_comparacao": "A/A", "visao": "consolidado",
     "unidade": "R$ milhões", "valor": 12345.6, "valor_como_aparece": "12.345,6", "anterior": 11020.0,
     "anterior_como_aparece": "11.020,0", "variacao_pct": 12.0, "pagina": 2,
     "trecho": "receita líquida atingiu R$ 12.345,6 milhões"}
E = {"metrica": "Margem EBITDA", "periodo": "3T26", "visao": "consolidado", "criterio_ebitda": "ajustado",
     "unidade": "%", "valor": 21.4, "valor_como_aparece": "21,4%", "pagina": 3, "trecho": "margem EBITDA de 21,4%"}

ENUM_UNIDADE = '"R$ mil", "R$ milhões", "%", "p.p.", "mil t", "R$/t", "x"'


def _sem(reg, campo):
    r = dict(reg)
    del r[campo]
    return r


def _com(reg, **kw):
    r = dict(reg)
    r.update(kw)
    return r


def _strs(dados, nome=None):
    return [str(e) for e in contrato.validar(dados, nome)]


def _ler(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ A-T1

def test_template_e_registros_versionados():
    """A-T1: os 4 JSONs de balanço precisam existir para o teste ter sentido."""
    assert len(BALANCOS_DADOS) == 4 and len(METAS) == 4
    assert R == _ler(TEMPLATE)[0] and E == _ler(TEMPLATE)[1]


@pytest.mark.parametrize("arquivo", [TEMPLATE, *BALANCOS], ids=lambda p: p.name)
def test_arquivos_versionados_validos(arquivo):
    """A-T1 / CA-A1."""
    nome = "balanco_meta" if arquivo.name.endswith(".meta.json") else contrato.escolher_schema(_ler(arquivo))
    assert contrato.validar_arquivo(arquivo, nome) == []


def test_balanco_tambem_valido_no_base():
    assert contrato.validar_arquivo(RAIZ / "metricas" / "balanco_gerdau.json", "metricas") == []


# ------------------------------------------------------------------ A-T2 / A-T3

@pytest.mark.parametrize("nome", sorted(contrato.SCHEMAS))
def test_schemas_bem_formados(nome):
    """A-T2."""
    schema = contrato.carregar_schema(nome)
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("/" + contrato.SCHEMAS[nome])
    assert schema["title"]


def test_carregar_schema_desconhecido():
    with pytest.raises(KeyError):
        contrato.carregar_schema("dre")


def test_registro_base_documentado():
    """A-T3: toda propriedade do registro-base tem description."""
    props = contrato.carregar_schema("metricas")["$defs"]["registro"]["properties"]
    sem = [k for k, v in props.items() if not v.get("description")]
    assert sem == []


# ------------------------------------------------------------------ A-T4

MUTACOES = [
    ("sem_pagina", _sem(R, "pagina"), "$[0].pagina: campo obrigatório ausente"),
    ("pagina_zero", _com(R, pagina=0), "$[0].pagina: 0 é menor que o mínimo 1"),
    ("unidade_invalida", _com(R, unidade="R$ MM"),
     f'$[0].unidade: valor "R$ MM" fora da lista permitida: {ENUM_UNIDADE}'),
    ("valor_string", _com(R, valor="12345.6"), '$[0].valor: esperado número, veio texto ("12345.6")'),
    ("sem_trecho", _sem(R, "trecho"), "$[0].trecho: campo obrigatório ausente"),
    ("ebitda_sem_criterio", _sem(E, "criterio_ebitda"),
     "$[0].criterio_ebitda: métrica de EBITDA exige 'criterio_ebitda' (\"contábil\" ou \"ajustado\")"),
    ("base_comparacao_invalida", _com(R, base_comparacao="3T26 vs 3T25"),
     '$[0].base_comparacao: valor "3T26 vs 3T25" fora da lista permitida: "A/A", "T/T", "posição"'),
    ("anterior_sem_literal", _sem(R, "anterior_como_aparece"),
     "$[0].anterior_como_aparece: campo obrigatório quando 'anterior' está presente"),
]


@pytest.mark.parametrize("reg,esperado", [(r, e) for _, r, e in MUTACOES], ids=[n for n, _, _ in MUTACOES])
def test_mutacoes_do_template(reg, esperado):
    """A-T4: as 8 mutações da tabela 8.4 dão exatamente uma mensagem."""
    assert _strs([reg]) == [esperado]


# ------------------------------------------------------------------ A-T5

@pytest.mark.parametrize("metrica", ["EBITDA ajustado", "Margem Ebitda", "ebitda"])
def test_ebitda_exige_criterio_em_qualquer_caixa(metrica):
    """A-T5 / CA-A4."""
    reg = _com(_sem(E, "criterio_ebitda"), metrica=metrica)
    erros = contrato.validar([reg])
    assert [e.caminho for e in erros] == ["$[0].criterio_ebitda"]
    assert contrato.validar([_com(reg, criterio_ebitda="contábil")]) == []


def test_receita_sem_criterio_aceita():
    assert "criterio_ebitda" not in R
    assert contrato.validar([R]) == []


# ------------------------------------------------------------------ A-T6 (tabela 5.6)

def test_template_antigo_sem_criterio_ebitda():
    antigo = [_com(_sem(R, "base_comparacao"), periodo="2T26 vs 2T25"),
              _sem(_com(E, periodo="2T26"), "criterio_ebitda")]
    assert _strs(antigo) == ['$[1].criterio_ebitda: métrica de EBITDA exige \'criterio_ebitda\' ("contábil" ou "ajustado")']


@pytest.mark.parametrize("dados,esperado", [
    ({"a": 1}, ['$: esperado lista, veio objeto ({"a": 1})']),
    ([], ["$: lista com 0 item(ns); mínimo 1"]),
    ([1], ["$[0]: esperado objeto, veio inteiro (1)"]),
    ([_com(R, valor=True)], ["$[0].valor: esperado número, veio booleano (true)"]),
    ([_com(R, pagina=2.5)], ["$[0].pagina: esperado inteiro, veio número (2.5)"]),
], ids=["raiz_objeto", "lista_vazia", "item_inteiro", "valor_booleano", "pagina_float"])
def test_casos_simples(dados, esperado):
    assert _strs(dados) == esperado


def test_multi_erro_em_ordem():
    dados = [_sem(R, "pagina"), R, _com(R, unidade="t"), _sem(_sem(R, "pagina"), "trecho")]
    assert _strs(dados) == [
        "$[0].pagina: campo obrigatório ausente",
        f'$[2].unidade: valor "t" fora da lista permitida: {ENUM_UNIDADE}',
        "$[3].pagina: campo obrigatório ausente",
        "$[3].trecho: campo obrigatório ausente",
    ]


def _primeiro_balanco():
    return copy.deepcopy(_ler(RAIZ / "metricas" / "balanco_gerdau.json")[0])


def test_balanco_campos_proibidos():
    reg = _com(_primeiro_balanco(), variacao_pct=1.0, criterio_ebitda="contábil", base_comparacao="A/A")
    assert _strs([reg]) == [
        '$[0].base_comparacao: valor "A/A" deveria ser "posição"',
        "$[0].criterio_ebitda: campo não permitido neste contrato",
        "$[0].variacao_pct: campo não permitido neste contrato",
    ]


def test_balanco_campo_extra_tipo_e_padrao():
    reg = _com(_primeiro_balanco(), variacao_pct=1.0, criterio_ebitda="contábil", base_comparacao="A/A",
               foo=1, valor=1.5, codigo_pai="x")
    erros = _strs([reg])
    for msg in ("$[0].foo: campo não previsto no contrato",
                "$[0].valor: esperado inteiro, veio número (1.5)",
                r'$[0].codigo_pai: valor "x" não segue o padrão ^[12](\.\d{2})*$'):
        assert msg in erros
    assert len(erros) == len(set(erros))  # sem duplicatas


def test_balanco_base_comparacao_posicao_aceita():
    assert contrato.validar([_com(_primeiro_balanco(), base_comparacao="posição")]) == []


def test_balanco_forcado_sobre_registro_do_template():
    """O dedup base × balanço deixa uma só linha de 'pagina' e nenhum 'não previsto' de campo do base."""
    erros = _strs([_sem(R, "pagina")], "balanco")
    assert len(erros) == 14
    assert erros.count("$[0].pagina: campo obrigatório ausente") == 1
    assert '$[0].unidade: valor "R$ milhões" deveria ser "R$ mil"' in erros
    assert "$[0].variacao_pct: campo não permitido neste contrato" in erros
    assert not [e for e in erros if "não previsto" in e and any(f".{c}:" in e for c in ("metrica", "periodo", "trecho"))]


def test_meta_mutado():
    meta = _ler(RAIZ / "metricas" / "balanco_gerdau.meta.json")
    meta.update(status="ok", extra=1, pdf_sha256="abc")
    assert _strs(meta, "balanco_meta") == [
        "$.extra: campo não previsto no contrato",
        '$.pdf_sha256: valor "abc" não segue o padrão ^[0-9a-f]{64}$',
        '$.status: valor "ok" fora da lista permitida: "aprovado", "reprovado"',
    ]


def test_meta_caminho_aninhado():
    meta = _ler(RAIZ / "metricas" / "balanco_gerdau.meta.json")
    meta["paginas"]["ativo"] = [0]
    assert _strs(meta, "balanco_meta") == ["$.paginas.ativo[0]: 0 é menor que o mínimo 1"]


def test_texto_curto():
    assert _strs([_com(R, trecho="abc")]) == ["$[0].trecho: texto curto demais (3 caractere(s); mínimo 5)"]


def test_erro_contrato_str():
    e = contrato.ErroContrato("$[3].pagina", "campo obrigatório ausente")
    assert str(e) == "$[3].pagina: campo obrigatório ausente"


# ------------------------------------------------------------------ A-T7 / A-T8

def test_escolher_schema():
    """A-T7."""
    assert contrato.escolher_schema(_ler(RAIZ / "metricas" / "balanco_gerdau.json")) == "balanco"
    assert contrato.escolher_schema([1, {"demonstracao": "BPA"}]) == "balanco"
    assert contrato.escolher_schema(_ler(TEMPLATE)) == "metricas"
    assert contrato.escolher_schema({}) == "metricas"
    assert contrato.escolher_schema({"demonstracao": "BPA"}) == "metricas"


def test_ordem_numerica_dos_indices():
    """A-T8: $[2] antes de $[10]."""
    dados = [R] * 11
    dados[2] = _sem(R, "pagina")
    dados[10] = _sem(R, "pagina")
    assert [e.caminho for e in contrato.validar(dados)] == ["$[2].pagina", "$[10].pagina"]


# ------------------------------------------------------------------ A-T9

def test_ler_json_inexistente(tmp_path):
    caminho = tmp_path / "nao_existe.json"
    with pytest.raises(contrato.ErroLeitura) as exc:
        contrato.ler_json(caminho)
    assert str(exc.value) == f"arquivo não encontrado: {caminho}"


def test_ler_json_malformado(tmp_path):
    caminho = tmp_path / "ruim.json"
    caminho.write_text('[{"a":\n', encoding="utf-8")
    with pytest.raises(contrato.ErroLeitura) as exc:
        contrato.ler_json(caminho)
    assert str(exc.value) == f"JSON inválido em {caminho}: linha 2, coluna 1: Expecting value"


# ------------------------------------------------------------------ A-T10

def test_desempenho():
    contrato.validar([R])  # compila e aquece o cache
    t0 = time.perf_counter()
    assert contrato.validar([R] * 100) == []
    assert time.perf_counter() - t0 < 0.5


# ------------------------------------------------------------------ A-T11 (CLI)

def test_cli_validos(capsys):
    meta = RAIZ / "metricas" / "balanco_gerdau.meta.json"
    assert contrato.main([str(TEMPLATE), str(meta)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [f"{TEMPLATE}: válido (metricas)", f"{meta}: válido (balanco_meta)"]


def test_cli_invalido(tmp_path, capsys):
    ruim = tmp_path / "sem_pagina.json"
    ruim.write_text(json.dumps([_sem(R, "pagina")], ensure_ascii=False), encoding="utf-8")
    assert contrato.main([str(TEMPLATE), str(ruim)]) == 2
    out = capsys.readouterr().out.splitlines()
    assert out[1:] == [f"{ruim}: 1 erro(s) (metricas)", "  $[0].pagina: campo obrigatório ausente"]


def test_cli_schema_forcado_e_ilegivel(tmp_path, capsys):
    assert contrato.main([str(TEMPLATE), "--schema", "balanco"]) == 2
    assert "erro(s) (balanco)" in capsys.readouterr().out
    assert contrato.main([str(tmp_path / "x.json")]) == 2
    assert capsys.readouterr().err.startswith("ERRO: arquivo não encontrado: ")


def test_cli_uso_invalido(capsys):
    assert contrato.main([]) == 2
    assert contrato.main([str(TEMPLATE), "--schema", "dre"]) == 2


# ------------------------------------------------------------------ A-T12

def test_sem_rede(monkeypatch):
    def bloqueado(*a, **k):
        raise OSError("rede bloqueada no teste")

    monkeypatch.setattr(socket, "socket", bloqueado)
    contrato.validador.cache_clear()
    contrato._registry.cache_clear()
    try:
        assert contrato.validar_arquivo(RAIZ / "metricas" / "balanco_gerdau.json", "balanco") == []
    finally:
        contrato.validador.cache_clear()
        contrato._registry.cache_clear()
