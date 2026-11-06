"""Testes do gerador de catálogo (SPEC §11.3, casos C-T1 a C-T15).

Rode da raiz:  pytest tests/test_catalogo.py
Cada teste monta um repositório falso em tmp_path (metricas/ copiada, PDFs
falsos, fontes.toml copiado), então não toca o repo real, exceto C-T15.
"""
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import contrato  # noqa: E402
import gerar_catalogo as gc  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures"
STEMS = ("gerdau_ITR_3T26", "usiminas_ITR_3T26")
PDF_FALSO = {s: f"%PDF-falso {s}".encode() for s in STEMS}
HASH_FALSO = {s: hashlib.sha256(b).hexdigest() for s, b in PDF_FALSO.items()}

ARTEFATOS_BALANCO = {
    "metricas/balanco_gerdau.json": "gerdau_ITR_3T26",
    "metricas/balanco_gerdau_controladora.json": "gerdau_ITR_3T26",
    "metricas/balanco_usiminas.json": "usiminas_ITR_3T26",
    "metricas/balanco_usiminas_controladora.json": "usiminas_ITR_3T26",
}
CONFERIDOS = {
    "metricas/balanco_gerdau.json": "94/94 conferem",
    "metricas/balanco_gerdau_controladora.json": "88/88 conferem",
    "metricas/balanco_usiminas.json": "81/81 conferem",
    "metricas/balanco_usiminas_controladora.json": "78/78 conferem",
}
SEM_SAIDA = "não verificado (saida/ ausente)"


def _reescrever_hash_meta(caminho: Path, sha: str) -> None:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["pdf_sha256"] = sha
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def montar_raiz(base: Path, *, hash_em_dia: bool = True) -> Path:
    """Repositório falso: metricas/ copiada, fontes.toml copiado, PDFs falsos em data/itrs/."""
    raiz = base / "raiz"
    (raiz / "metricas").mkdir(parents=True)
    (raiz / "catalogo").mkdir()
    (raiz / "docs").mkdir()
    (raiz / "data" / "itrs").mkdir(parents=True)
    for arq in (RAIZ / "metricas").iterdir():
        if arq.is_file() and arq.name not in ("catalogo.json",):
            shutil.copy2(arq, raiz / "metricas" / arq.name)
    shutil.copy2(RAIZ / "catalogo" / "fontes.toml", raiz / "catalogo" / "fontes.toml")
    for stem in STEMS:
        (raiz / "data" / "itrs" / f"{stem}.pdf").write_bytes(PDF_FALSO[stem])
    if hash_em_dia:
        for meta in (raiz / "metricas").glob("*.meta.json"):
            stem = Path(json.loads(meta.read_text(encoding="utf-8"))["pdf"]).stem
            _reescrever_hash_meta(meta, HASH_FALSO[stem])
    return raiz


def copiar_saida(raiz: Path) -> None:
    """saida/<stem> com as páginas de fixture do B (só as páginas do balanço)."""
    for stem in STEMS:
        destino = raiz / "saida" / stem
        destino.mkdir(parents=True, exist_ok=True)
        for pag in (FIXTURES / stem).glob("pagina_*.txt"):
            shutil.copy2(pag, destino / pag.name)


def _catalogo(raiz: Path) -> dict:
    return json.loads((raiz / "metricas" / "catalogo.json").read_text(encoding="utf-8"))


def _artefato(cat: dict, caminho: str) -> dict:
    return next(a for a in cat["artefatos"] if a["caminho"] == caminho)


def _gerar(raiz: Path) -> int:
    return gc.main(["--raiz", str(raiz)])


@pytest.fixture
def raiz(tmp_path):
    return montar_raiz(tmp_path)


def _precisa_fixtures():
    if not (FIXTURES / "gerdau_ITR_3T26").is_dir() or not (FIXTURES / "usiminas_ITR_3T26").is_dir():
        pytest.skip("fixtures do B ausentes (tests/fixtures/<stem>/)")


# C-T1 ----------------------------------------------------------------------

def test_c_t1_duas_execucoes_bytes_identicos(raiz):
    assert _gerar(raiz) == 0
    primeiro = {r: (raiz / r).read_bytes() for r in (gc.SAIDA_MD, gc.SAIDA_JSON)}
    assert _gerar(raiz) == 0
    for r, conteudo in primeiro.items():
        assert (raiz / r).read_bytes() == conteudo


# C-T2 ----------------------------------------------------------------------

def test_c_t2_check_em_dia_e_defasado(raiz, capsys):
    assert _gerar(raiz) == 0
    assert gc.main(["--raiz", str(raiz), "--check"]) == 0
    capsys.readouterr()

    meta = raiz / "metricas" / "balanco_gerdau.meta.json"
    dados = json.loads(meta.read_text(encoding="utf-8"))
    dados["n_ambiguos"] += 1
    meta.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert gc.main(["--raiz", str(raiz), "--check"]) == 1
    assert "desatualizado: docs/CATALOGO_DADOS.md" in capsys.readouterr().out

    (raiz / "metricas" / "catalogo.json").unlink()
    assert gc.main(["--raiz", str(raiz), "--check"]) == 1
    assert "desatualizado: metricas/catalogo.json" in capsys.readouterr().out


# C-T3 ----------------------------------------------------------------------

def test_c_t3_doze_artefatos_por_tipo(raiz):
    assert _gerar(raiz) == 0
    cat = _catalogo(raiz)
    tipos = [a["tipo"] for a in cat["artefatos"]]
    assert len(cat["artefatos"]) == 12
    assert tipos.count("balanco") == 4
    assert tipos.count("meta") == 4
    assert tipos.count("csv") == 4
    assert not any(a["caminho"].endswith("catalogo.json") for a in cat["artefatos"])


# C-T4 ----------------------------------------------------------------------

def test_c_t4_gerdau_consolidado(raiz):
    assert _gerar(raiz) == 0
    meta = json.loads((RAIZ / "metricas" / "balanco_gerdau.meta.json").read_text(encoding="utf-8"))
    a = _artefato(_catalogo(raiz), "metricas/balanco_gerdau.json")
    assert a["visao"] == [meta["visao"]] == ["consolidado"]
    assert a["paginas"] == meta["paginas"] == {"ativo": [26], "passivo": [27, 28]}
    assert a["n_contas"]["total"] == meta["n_contas"]["total"] == 94
    assert a["n_ambiguos"] == meta["n_ambiguos"] == 32
    assert a["autovalidacao"] == {"status": "aprovado", "falhas": []}
    assert a["criterio_ebitda"] == "n/a"
    assert a["unidade"] == [meta["unidade"]]
    assert a["escala_original"] == meta["escala_original"] == "Reais Mil"


# C-T5 ----------------------------------------------------------------------

def test_c_t5_sem_saida_nao_verificado(raiz):
    assert _gerar(raiz) == 0
    cat = _catalogo(raiz)
    for caminho in ARTEFATOS_BALANCO:
        assert _artefato(cat, caminho)["verificador"]["status"] == SEM_SAIDA


# C-T6 ----------------------------------------------------------------------

def test_c_t6_com_saida_confere(raiz):
    _precisa_fixtures()
    copiar_saida(raiz)
    assert _gerar(raiz) == 0
    cat = _catalogo(raiz)
    for caminho, esperado in CONFERIDOS.items():
        assert _artefato(cat, caminho)["verificador"]["status"] == esperado


# C-T7 ----------------------------------------------------------------------

def test_c_t7_heranca_sem_saida(raiz):
    _precisa_fixtures()
    copiar_saida(raiz)
    assert _gerar(raiz) == 0
    com_saida = {c: _artefato(_catalogo(raiz), c)["verificador"] for c in CONFERIDOS}

    shutil.rmtree(raiz / "saida")
    assert _gerar(raiz) == 0
    assert gc.main(["--raiz", str(raiz), "--check"]) == 0
    sem_saida = {c: _artefato(_catalogo(raiz), c)["verificador"] for c in CONFERIDOS}
    assert {c: v["status"] for c, v in sem_saida.items()} == {c: v["status"] for c, v in com_saida.items()}
    assert {c: v["status"] for c, v in sem_saida.items()} == CONFERIDOS

    # Um byte alterado no JSON: o hash deixa de bater, então não há herança.
    alvo = raiz / "metricas" / "balanco_gerdau.json"
    dados = bytearray(alvo.read_bytes())
    dados[dados.index(b"\n")] = ord(" ")
    alvo.write_bytes(bytes(dados))
    assert _gerar(raiz) == 0
    cat = _catalogo(raiz)
    a = _artefato(cat, "metricas/balanco_gerdau.json")
    assert a["verificador"]["status"] == SEM_SAIDA
    assert a["contrato"]["valido"] is True


# C-T8 ----------------------------------------------------------------------

def test_c_t8_pdf_diferente_marca_defasada(tmp_path):
    raiz = montar_raiz(tmp_path, hash_em_dia=False)
    assert _gerar(raiz) == 0
    cat = _catalogo(raiz)
    for caminho in ARTEFATOS_BALANCO:
        assert _artefato(cat, caminho)["fonte_defasada"] is True
    assert "DEFASADO" in (raiz / gc.SAIDA_MD).read_text(encoding="utf-8")


def test_c_t8_hash_em_dia_nao_defasa(raiz):
    assert _gerar(raiz) == 0
    for caminho in ARTEFATOS_BALANCO:
        assert _artefato(_catalogo(raiz), caminho)["fonte_defasada"] is False
    assert "DEFASADO" not in (raiz / gc.SAIDA_MD).read_text(encoding="utf-8")


# C-T9 ----------------------------------------------------------------------

def test_c_t9_pendentes(raiz):
    assert _gerar(raiz) == 0
    pend = _catalogo(raiz)["pendentes"]
    assert [p["artefato"] for p in pend] == ["metricas/metricas_gerdau.json",
                                             "metricas/metricas_usiminas.json"]
    assert all(p["status"] == "pendente" for p in pend)


# C-T10 ---------------------------------------------------------------------

def test_c_t10_sem_data_hora_nem_caminho_absoluto(raiz):
    _precisa_fixtures()
    copiar_saida(raiz)
    assert _gerar(raiz) == 0
    for rel in (gc.SAIDA_MD, gc.SAIDA_JSON):
        texto = (raiz / rel).read_text(encoding="utf-8")
        assert "gerado_em" not in texto
        assert str(raiz) not in texto
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", texto)


# C-T11 ---------------------------------------------------------------------

def test_c_t11_meta_mutado_fica_fora_do_contrato(raiz):
    meta = raiz / "metricas" / "balanco_gerdau.meta.json"
    dados = json.loads(meta.read_text(encoding="utf-8"))
    dados["status"] = "ok"
    meta.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert _gerar(raiz) == 0
    a = _artefato(_catalogo(raiz), "metricas/balanco_gerdau.meta.json")
    assert a["contrato"]["valido"] is False
    assert a["contrato"]["n_erros"] >= 1


# C-T12 ---------------------------------------------------------------------

def test_c_t12_fontes_sem_stem(raiz, capsys):
    toml = raiz / "catalogo" / "fontes.toml"
    texto = toml.read_text(encoding="utf-8")
    toml.write_text(texto.replace('stem = "gerdau_ITR_3T26"\n', "", 1), encoding="utf-8")
    assert _gerar(raiz) == 2
    err = capsys.readouterr().err
    assert err.startswith("ERRO: catalogo/fontes.toml: ")
    assert "stem" in err


def test_c_t12_fontes_toml_quebrado(raiz, capsys):
    (raiz / "catalogo" / "fontes.toml").write_text('versao = 1\n[[fonte]\nstem = "x"\n', encoding="utf-8")
    assert _gerar(raiz) == 2
    assert capsys.readouterr().err.startswith("ERRO: catalogo/fontes.toml: ")


# C-T13 ---------------------------------------------------------------------

def test_c_t13_json_de_metricas_sem_meta(raiz):
    shutil.copy2(RAIZ / "templates" / "metricas_exemplo.json", raiz / "metricas" / "metricas_gerdau.json")
    assert _gerar(raiz) == 0
    cat = _catalogo(raiz)
    a = _artefato(cat, "metricas/metricas_gerdau.json")
    assert a["tipo"] == "metricas"
    assert a["fonte"] == "gerdau_ITR_3T26"
    assert a["criterio_ebitda"] == ["ajustado"]
    assert a["gerado_por"] == "sem meta (JSON do time/Claude)"
    assert [p["artefato"] for p in cat["pendentes"]] == ["metricas/metricas_usiminas.json"]


# C-T14 ---------------------------------------------------------------------

def test_c_t14_coletar_rapido(raiz):
    inicio = time.perf_counter()
    gc.coletar(raiz)
    assert time.perf_counter() - inicio < 3


# C-T15 ---------------------------------------------------------------------

def test_c_t15_repo_real_em_dia():
    if not any((RAIZ / "data" / "itrs").glob("*.pdf")):
        pytest.skip("PDF ausente: data/itrs/*.pdf")
    assert gc.main(["--check"]) == 0
