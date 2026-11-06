"""Testes do verificador (verificar/main/Resultado/ErroEntrada, SPEC §3.2 e §6). Herméticos.

Usa só tests/fixtures/ e textos sintéticos em tmp_path; main() roda em processo.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import verificar_numeros as vn  # noqa: E402
from contrato import ErroContrato  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures"
METRICAS = RAIZ / "metricas"
GERDAU = FIXTURES / "gerdau_ITR_3T26"
USIMINAS = FIXTURES / "usiminas_ITR_3T26"

# (json, pasta, sha256 do stdout (§6.4), n)
BALANCOS = [
    ("balanco_gerdau", GERDAU, "db41625dddd6f5137f2ccdcab41f7df9c59f03771396294a2b082bbd42bbefe5", 94),
    ("balanco_gerdau_controladora", GERDAU, "a0f1d41cd30cfc7627710efa3046ded945ff8d6e3a4e3fca4260699b5be9bf35", 88),
    ("balanco_usiminas", USIMINAS, "7fd2162f1033894440a6467745e7cdf63b9cd2430a9fc820297ecf12493a607b", 81),
    ("balanco_usiminas_controladora", USIMINAS, "6d5536c115c0acfe427b4f0568de4db496f02357be65caecc63075640d6ccce2", 78),
]

ULTIMA_INVALIDO = "JSON fora do contrato (schemas/metricas.schema.json): 1 erro(s). Nenhuma métrica foi conferida."
LISTA_UNIDADES = '"R$ mil", "R$ milhões", "%", "p.p.", "mil t", "R$/t", "x"'
INVALIDOS = {
    "sem_pagina": "[CONTRATO] $[0].pagina: campo obrigatório ausente",
    "pagina_zero": "[CONTRATO] $[0].pagina: 0 é menor que o mínimo 1",
    "unidade_invalida": f'[CONTRATO] $[0].unidade: valor "R$ MM" fora da lista permitida: {LISTA_UNIDADES}',
    "valor_string": '[CONTRATO] $[0].valor: esperado número, veio texto ("12345.6")',
    "sem_trecho": "[CONTRATO] $[0].trecho: campo obrigatório ausente",
    "ebitda_sem_criterio": "[CONTRATO] $[0].criterio_ebitda: métrica de EBITDA exige 'criterio_ebitda' "
                           '("contábil" ou "ajustado")',
    "base_comparacao_invalida": '[CONTRATO] $[0].base_comparacao: valor "3T26 vs 3T25" fora da lista '
                                'permitida: "A/A", "T/T", "posição"',
    "anterior_sem_literal": "[CONTRATO] $[0].anterior_como_aparece: campo obrigatório quando 'anterior' "
                            "está presente",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def rodar(capsys, *args):
    rc = vn.main([str(a) for a in args])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def ultima(saida: str) -> str:
    return saida.rstrip("\n").splitlines()[-1]


def pasta_com(tmp_path: Path, paginas: dict[int, str]) -> Path:
    pasta = tmp_path / "pag"
    pasta.mkdir(exist_ok=True)
    for n, t in paginas.items():
        (pasta / f"pagina_{n:02d}.txt").write_text(t, encoding="utf-8")
    return pasta


def reg(**extra) -> dict:
    base = {"metrica": "Caixa", "periodo": "3T26", "unidade": "R$ mil", "valor": 1234,
            "valor_como_aparece": "1.234", "pagina": 1, "trecho": "Caixa 1.234"}
    base.update(extra)
    return base


def grava(tmp_path: Path, dados, nome="m.json") -> Path:
    arq = tmp_path / nome
    arq.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return arq


PAG_CURTO = "Caixa 1.234 5\nOutros 7 9\n(Reais Mil)\n"
PAG_RECEITA = "Receita líquida atingiu R$ 12.345,6 milhões, ante R$ 11.020,0 milhões.\n"
REG_RECEITA = {"metrica": "Receita líquida", "periodo": "3T26 vs 3T25", "unidade": "R$ milhões",
               "valor": 12345.6, "valor_como_aparece": "12.345,6", "anterior": 11020.0,
               "anterior_como_aparece": "11.020,0", "variacao_pct": 12.0, "pagina": 1,
               "trecho": "receita líquida atingiu R$ 12.345,6 milhões"}


# ---------------------------------------------------------------------------
# Balanços reais sobre as fixtures
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome, pasta, sha, n", BALANCOS)
def test_b_v1_balancos_saida_identica_ao_commit_base(capsys, nome, pasta, sha, n):
    rc, out, _ = rodar(capsys, pasta, METRICAS / f"{nome}.json")
    assert rc == 0
    assert hashlib.sha256(out.encode("utf-8")).hexdigest() == sha
    assert ultima(out) == f"{n}/{n} métricas conferem."


@pytest.mark.parametrize("nome, pasta, sha, n", BALANCOS)
def test_b_v2_verificar_balancos(nome, pasta, sha, n):
    res = vn.verificar(pasta, METRICAS / f"{nome}.json")
    assert res.codigo_saida == 0
    assert res.schema == "balanco"
    assert res.n_avisos == 0
    assert (res.n_ok, res.n_total, res.n_erro) == (n, n, 0)
    assert res.erros_contrato == ()


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome", sorted(INVALIDOS))
def test_b_v3_invalidos_param(capsys, nome):
    rc, out, _ = rodar(capsys, GERDAU, FIXTURES / "invalidos" / f"{nome}.json")
    linhas = out.splitlines()
    assert rc == 2
    assert linhas.count(INVALIDOS[nome]) == 1
    assert [l for l in linhas if l.startswith("[CONTRATO]")] == [INVALIDOS[nome]]
    assert not [l for l in linhas if l.startswith(("[OK ", "[ERRO]"))]
    assert ultima(out) == ULTIMA_INVALIDO


def test_b_v3_resultado_de_erro_de_contrato():
    res = vn.verificar(GERDAU, FIXTURES / "invalidos" / "sem_pagina.json")
    assert res.codigo_saida == 2 and res.schema == "metricas"
    assert len(res.erros_contrato) == 1 and res.conferencias == ()
    assert (res.n_total, res.n_ok, res.n_erro, res.n_avisos) == (0, 0, 0, 0)


@pytest.mark.parametrize("nome", sorted(INVALIDOS))
def test_b_v4_pasta_inexistente_nao_muda_saida(capsys, tmp_path, nome):
    arq = FIXTURES / "invalidos" / f"{nome}.json"
    rc1, out1, _ = rodar(capsys, GERDAU, arq)
    rc2, out2, err2 = rodar(capsys, tmp_path / "nao_existe", arq)
    assert (rc2, out2, err2) == (rc1, out1, "") and rc2 == 2


def test_b_v5_sem_contrato_pagina_ausente(capsys):
    rc, out, err = rodar(capsys, GERDAU, FIXTURES / "invalidos" / "sem_pagina.json", "--sem-contrato")
    assert rc == 1
    assert "[ERRO] Receita líquida (3T26 vs 3T25): campo 'pagina' ausente ou inválido" in out
    assert "aviso: --sem-contrato" in err
    assert "[CONTRATO]" not in out


def test_sem_contrato_stdout_igual_ao_com_contrato(capsys):
    arq = METRICAS / "balanco_gerdau.json"
    _, out1, err1 = rodar(capsys, GERDAU, arq)
    rc, out2, err2 = rodar(capsys, GERDAU, arq, "--sem-contrato")
    assert rc == 0 and out2 == out1
    assert err1 == "" and err2.startswith("aviso: --sem-contrato: o JSON não foi validado contra o schema")


def test_b_v25_schema_metricas_forcado_sobre_balanco(capsys):
    rc, out, _ = rodar(capsys, GERDAU, METRICAS / "balanco_gerdau.json", "--schema", "metricas")
    assert rc == 0 and ultima(out) == "94/94 métricas conferem."
    assert vn.verificar(GERDAU, METRICAS / "balanco_gerdau.json", schema="metricas").schema == "metricas"


def test_b_v26_schema_balanco_forcado_sobre_invalido(capsys):
    rc, out, _ = rodar(capsys, GERDAU, FIXTURES / "invalidos" / "sem_pagina.json", "--schema", "balanco")
    linhas = out.splitlines()
    assert rc == 2
    assert ultima(out) == ("JSON fora do contrato (schemas/balanco.schema.json): 14 erro(s). "
                           "Nenhuma métrica foi conferida.")
    assert '[CONTRATO] $[0].unidade: valor "R$ milhões" deveria ser "R$ mil"' in linhas
    assert "[CONTRATO] $[0].variacao_pct: campo não permitido neste contrato" in linhas
    assert linhas.count("[CONTRATO] $[0].pagina: campo obrigatório ausente") == 1
    previstos = [l for l in linhas if "campo não previsto" in l]
    for campo in ("metrica", "periodo", "trecho"):
        assert not [l for l in previstos if f"$[0].{campo}:" in l]


def test_erros_de_contrato_limitados_a_50_linhas(capsys, tmp_path):
    sem_pagina = {k: v for k, v in reg().items() if k != "pagina"}
    arq = grava(tmp_path, [sem_pagina] * 60)
    rc, out, _ = rodar(capsys, tmp_path, arq)
    linhas = out.splitlines()
    assert rc == 2
    assert len([l for l in linhas if l.startswith("[CONTRATO] $[")]) == 50
    assert "[CONTRATO] ... e mais 10 erro(s)" in linhas
    assert linhas[-2] == ""
    assert ultima(out) == ("JSON fora do contrato (schemas/metricas.schema.json): 60 erro(s). "
                           "Nenhuma métrica foi conferida.")


def test_uso_invalido_argparse_codigo_2(capsys):
    try:  # main não chama sys.exit; o argparse pode sair (SystemExit 2) ou main devolver 2
        rc = vn.main([])
    except SystemExit as e:
        rc = e.code
    assert rc == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_jsonschema_ausente_codigo_2(capsys, tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "contrato", None)  # `import contrato` passa a levantar ImportError
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    rc, out, err = rodar(capsys, pasta, grava(tmp_path, [reg()]))
    assert rc == 2 and out == ""
    assert err.strip() == ("ERRO: jsonschema não instalado: rode 'pip install -r requirements.txt' "
                           "(ou use --sem-contrato)")


# ---------------------------------------------------------------------------
# Negativo: dígito trocado
# ---------------------------------------------------------------------------
def test_b_v6_digito_trocado(capsys, tmp_path):
    copia = tmp_path / "gerdau"
    shutil.copytree(GERDAU, copia)
    p26 = copia / "pagina_26.txt"
    original = p26.read_text(encoding="utf-8")
    assert "1 Ativo Total 83.945.525" in original
    p26.write_text(original.replace("1 Ativo Total 83.945.525", "1 Ativo Total 83.945.526", 1), encoding="utf-8")
    rc, out, _ = rodar(capsys, copia, METRICAS / "balanco_gerdau.json")
    assert rc == 1
    nao_ok = [l for l in out.splitlines() if l.startswith("[") and not l.startswith("[OK ")]
    assert nao_ok == ["[ERRO] 1 Ativo Total (30/09/2026 vs 31/12/2025): trecho citado não encontrado na página; "
                      "valor_como_aparece '83.945.525' não aparece na página"]
    assert ultima(out) == "93/94 métricas conferem."


# ---------------------------------------------------------------------------
# checar(): casos sintéticos
# ---------------------------------------------------------------------------
def test_b_v7_registro_correto(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_RECEITA})
    assert vn.checar(dict(REG_RECEITA), pasta) == []
    assert vn.avisar(dict(REG_RECEITA), pasta) == []


def test_b_v8_trecho_ausente(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    assert "trecho citado não encontrado na página" in vn.checar(reg(trecho="Receita inexistente aqui"), pasta)


def test_b_v9_valor_ausente(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    probs = vn.checar(reg(valor=4321, valor_como_aparece="4.321"), pasta)
    assert "valor_como_aparece '4.321' não aparece na página" in probs


def test_b_v10_erro_de_unidade(tmp_path):
    pasta = pasta_com(tmp_path, {1: "Caixa 1.234\n(Reais Mil)\n"})
    assert vn.checar(reg(valor=1234000), pasta) == ["valor=1234000 não bate com '1.234'"]


@pytest.mark.parametrize("entrada, esperado", [
    ("(123,4)", -123.4), ("-395.736", -395736.0), ("12,3%", 12.3), ("R$ 1.234,5", 1234.5), ("0", 0.0)])
def test_b_v11_br_para_float(entrada, esperado):
    assert vn.br_para_float(entrada) == esperado


def test_normalizar():
    assert vn.normalizar("  Foo \n  BAR\t baz ") == "foo bar baz"


def test_b_v12_literal_ilegivel(tmp_path):
    pasta = pasta_com(tmp_path, {1: "Caixa abc\n"})
    probs = vn.checar(reg(valor_como_aparece="abc", trecho="Caixa abc"), pasta)
    assert "não consegui ler 'abc' como número" in probs


def test_b_v13_variacao(tmp_path):
    pasta = pasta_com(tmp_path, {1: "Receita 112 100\n"})
    base = reg(metrica="Receita", valor=112, valor_como_aparece="112", anterior=100,
               anterior_como_aparece="100", trecho="Receita 112 100")
    assert "variação informada 11.4% ≠ recalculada 12.0%" in vn.checar({**base, "variacao_pct": 11.4}, pasta)
    assert vn.checar({**base, "variacao_pct": 11.6}, pasta) == []


def test_b_v14_anterior_zero_com_variacao(tmp_path):
    pasta = pasta_com(tmp_path, {1: "Receita 5 0\n"})
    m = reg(metrica="Receita", valor=5, valor_como_aparece="5", anterior=0, anterior_como_aparece="0",
            variacao_pct=10.0, trecho="Receita 5 0")
    assert vn.checar(m, pasta) == []


def test_b_v15_pagina_inexistente(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    assert vn.checar(reg(pagina=99), pasta) == ["página 99 não existe"]


@pytest.mark.parametrize("pagina", [None, "x"])
def test_pagina_ausente_ou_invalida_em_checar(tmp_path, pagina):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    m = reg()
    if pagina is None:
        del m["pagina"]
    else:
        m["pagina"] = pagina
    assert vn.checar(m, pasta) == ["campo 'pagina' ausente ou inválido"]
    assert vn.avisar(m, pasta) == []


def test_avisar_sem_pagina_existente_retorna_vazio(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    assert vn.avisar(reg(pagina=99), pasta) == []


# ---------------------------------------------------------------------------
# Entrada inutilizável (código 2)
# ---------------------------------------------------------------------------
def test_b_v16_json_sintaticamente_invalido(capsys, tmp_path):
    arq = tmp_path / "ruim.json"
    arq.write_text('[{"a":\n', encoding="utf-8")
    rc, out, err = rodar(capsys, tmp_path, arq)
    assert rc == 2 and out == ""
    assert err.startswith("ERRO: JSON inválido em ")
    assert ": linha 2, coluna 1: Expecting value" in err


def test_b_v17_arquivo_e_pasta_inexistentes(capsys, tmp_path):
    rc, _, err = rodar(capsys, tmp_path, tmp_path / "nao_existe.json")
    assert rc == 2 and err.startswith("ERRO: arquivo não encontrado: ")
    arq = grava(tmp_path, [reg()])
    rc, _, err = rodar(capsys, tmp_path / "sem_pasta", arq)
    assert rc == 2 and err.startswith("ERRO: pasta de textos não encontrada: ")


def test_erro_entrada_levantado_por_verificar(tmp_path):
    with pytest.raises(vn.ErroEntrada, match="arquivo não encontrado"):
        vn.verificar(tmp_path, tmp_path / "x.json")
    with pytest.raises(vn.ErroEntrada, match="pasta de textos não encontrada"):
        vn.verificar(tmp_path / "x", grava(tmp_path, [reg()]))


def test_sem_contrato_nao_lista_e_registro_nao_objeto(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    with pytest.raises(vn.ErroEntrada, match="esperada uma lista de registros"):
        vn.verificar(pasta, grava(tmp_path, {"a": 1}), contrato=False)
    res = vn.verificar(pasta, grava(tmp_path, [1, reg()], "n.json"), contrato=False)
    assert res.schema is None and res.codigo_saida == 1
    assert res.conferencias[0].problemas == ("registro não é um objeto JSON",)
    assert res.conferencias[0].metrica == "registro 0"
    assert res.conferencias[1].ok


def test_conferencia_usa_defaults_de_metrica_e_periodo(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    res = vn.verificar(pasta, grava(tmp_path, [{"pagina": 1}]), contrato=False)
    c = res.conferencias[0]
    assert (c.indice, c.metrica, c.periodo) == (0, "registro 0", "")


def test_b_v18_codigo_saida():
    ok = vn.Conferencia(0, "a", "p", (), ())
    erro = vn.Conferencia(1, "b", "p", ("x",), ("y",))
    base = dict(arquivo=Path("a.json"), pasta=Path("p"), schema="metricas")
    r0 = vn.Resultado(**base, conferencias=(ok,))
    r1 = vn.Resultado(**base, conferencias=(ok, erro))
    r2 = vn.Resultado(**base, erros_contrato=(ErroContrato("$", "m"),))
    assert (r0.codigo_saida, r1.codigo_saida, r2.codigo_saida) == (0, 1, 2)
    assert (r1.n_total, r1.n_ok, r1.n_erro, r1.n_avisos) == (2, 1, 1, 1)
    assert ok.ok and not erro.ok


# ---------------------------------------------------------------------------
# Avisos (não mudam o código de saída)
# ---------------------------------------------------------------------------
def test_b_v19_aviso_valor_fora_do_trecho(capsys, tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    m = reg(trecho="Caixa 1.234 5", valor=9, valor_como_aparece="9")
    assert vn.checar(m, pasta) == []
    assert vn.avisar(m, pasta) == ["valor_como_aparece '9' está na página, mas fora do trecho citado"]
    rc, out, _ = rodar(capsys, pasta, grava(tmp_path, [m]))
    linhas = out.splitlines()
    assert rc == 0
    assert linhas[0] == "[OK ] Caixa (3T26): confere com o PDF"
    assert linhas[1] == "[AVISO] Caixa (3T26): valor_como_aparece '9' está na página, mas fora do trecho citado"
    assert ultima(out) == "1 aviso(s): revise as linhas [AVISO] (não mudam o código de saída)."
    assert "1/1 métricas conferem." in linhas


def test_b_v20_aviso_literal_curto(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    m = reg(anterior=7, anterior_como_aparece="7")
    assert vn.checar(m, pasta) == []
    assert vn.avisar(m, pasta) == [
        "anterior_como_aparece '7' é curto e foi achado fora do trecho; pode ter casado por acaso"]


def test_b_v21_aviso_unidade_nao_aparece(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    assert vn.avisar(reg(unidade="R$ milhões"), pasta) == [
        "unidade 'R$ milhões' não aparece no trecho nem na página"]
    assert vn.avisar(reg(unidade="R$ mil"), pasta) == []


def test_b_v22_sem_contrato_unidade_fora_da_lista(capsys, tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    m = reg(unidade="t")
    assert vn.avisar(m, pasta) == ["unidade 't' fora da lista do contrato"]
    rc, out, err = rodar(capsys, pasta, grava(tmp_path, [m]), "--sem-contrato")
    assert rc == 0 and "[AVISO] Caixa (3T26): unidade 't' fora da lista do contrato" in out
    assert "aviso: --sem-contrato" in err


def test_b_v23_sem_trecho_sem_contrato(tmp_path):
    pasta = pasta_com(tmp_path, {1: PAG_CURTO})
    m = {k: v for k, v in reg().items() if k != "trecho"}
    assert vn.checar(m, pasta) == []
    assert vn.avisar(m, pasta) == ["sem 'trecho': a citação não foi conferida"]
    res = vn.verificar(pasta, grava(tmp_path, [m]), contrato=False)
    assert res.codigo_saida == 0 and res.n_avisos == 1


def test_b_v24_caracterizacao_literal_curto_dentro_do_trecho():
    regs = json.loads((METRICAS / "balanco_gerdau.json").read_text(encoding="utf-8"))
    m = next(r for r in regs if r["codigo_conta"] == "2.03.05")
    assert m["trecho"] == "2.03.05 Lucros/Prejuízos Acumulados 3.204.533 0" and m["pagina"] == 28
    assert vn.checar(m, GERDAU) == []
    assert vn.avisar(m, GERDAU) == []


@pytest.mark.parametrize("unidade, texto", [
    ("%", "margem de 21,4%"), ("p.p.", "variação de 1,2 p.p."), ("mil t", "vendas de 1.200 mil t"),
    ("R$/t", "preço de R$ 3.500/t"), ("x", "alavancagem de 0,20x"), ("R$ mil", "valores em milhares")])
def test_marcadores_de_unidade_reconhecem_cada_unidade(tmp_path, unidade, texto):
    pasta = pasta_com(tmp_path, {1: texto + "\n"})
    m = reg(unidade=unidade, valor_como_aparece=texto[-4:], trecho=texto)
    assert not any(a.startswith("unidade ") for a in vn.avisar(m, pasta)), unidade
    assert set(vn.MARCADORES_UNIDADE) == {"R$ mil", "R$ milhões", "%", "p.p.", "mil t", "R$/t", "x"}
    assert vn.LIMITE_CURTO == 3
