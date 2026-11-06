"""Fixtures de texto: integridade (hash/bytes), coerência com os metas e tamanho. Hermético."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

FIXTURES = RAIZ / "tests" / "fixtures"

# Tabela 8.1 do SPEC: bytes e SHA-256 do texto extraído com pdfplumber 0.11.10.
ESPERADO = {
    "gerdau_ITR_3T26/pagina_15.txt": (2119, "4325188da071c7e69250752daaf9922021e5bbd5c1bfba69b96552bab8eebabd"),
    "gerdau_ITR_3T26/pagina_16.txt": (2740, "c57efaf664cf0b8fc04e95da2c3668499de36945fd31a63c115d717b7cdc510a"),
    "gerdau_ITR_3T26/pagina_17.txt": (942, "8093a8cfb13b6388155fad749e57a62d43c0b550486550d1c363207b1f1adde3"),
    "gerdau_ITR_3T26/pagina_26.txt": (2165, "e0bedb0ede6c01b4cb73a5571e361dd0d226fc1a9d6bff43d236f1ba41865b8f"),
    "gerdau_ITR_3T26/pagina_27.txt": (2856, "8217dce6a946f2c117c8dc43ac76b003fafec2a666bde4330973c45bc12b9492"),
    "gerdau_ITR_3T26/pagina_28.txt": (1325, "bbb4b4a651cd1a4b7be172bf1504909082bf7ce416f862906fe490fd5d8721ab"),
    "usiminas_ITR_3T26/pagina_03.txt": (2075, "3d96e1ce4b982e05c9dd214df59c3a3e4a5a5fdfdbd060ed04cf88dd5481839f"),
    "usiminas_ITR_3T26/pagina_04.txt": (2436, "426ec9152027526905561c540fca97dd413b419eeee2574664197777edf9f9eb"),
    "usiminas_ITR_3T26/pagina_12.txt": (2159, "dd5af80dc5e49fc6a62eb00cf61c5eed1e003112ecef2e1b10c65eb6a1a22470"),
    "usiminas_ITR_3T26/pagina_13.txt": (2614, "9fc162781b1d93c40cce5154ed85ee6447522a196a813f34f446b6d855627928"),
}

PAGINAS_ESPERADAS = {"gerdau_ITR_3T26": [15, 16, 17, 26, 27, 28], "usiminas_ITR_3T26": [3, 4, 12, 13]}


def _metas_do_stem(stem):
    metas = []
    for f in sorted((RAIZ / "metricas").glob("balanco_*.meta.json")):
        meta = json.loads(f.read_text(encoding="utf-8"))
        if Path(meta["pdf"]).stem == stem:
            metas.append(meta)
    return metas


def test_b_f1_manifesto_lista_10_arquivos_e_bate(manifesto):
    arquivos = manifesto["arquivos"]
    assert len(arquivos) == 10
    for a in arquivos:
        dados = (FIXTURES / a["arquivo"]).read_bytes()
        assert len(dados) == a["bytes"], a["arquivo"]
        assert hashlib.sha256(dados).hexdigest() == a["sha256"], a["arquivo"]
    em_disco = {p.relative_to(FIXTURES).as_posix() for p in FIXTURES.glob("*/pagina_*.txt")}
    assert em_disco == {a["arquivo"] for a in arquivos}


def test_b_f2_valores_da_tabela_do_spec(manifesto):
    assert {a["arquivo"]: (a["bytes"], a["sha256"]) for a in manifesto["arquivos"]} == ESPERADO
    for arq, (n, h) in ESPERADO.items():
        dados = (FIXTURES / arq).read_bytes()
        assert (len(dados), hashlib.sha256(dados).hexdigest()) == (n, h), arq


@pytest.mark.parametrize("stem", sorted(PAGINAS_ESPERADAS))
def test_b_f3_paginas_do_manifesto_sao_as_dos_metas(manifesto, stem):
    do_manifesto = sorted(a["pagina"] for a in manifesto["arquivos"] if a["stem"] == stem)
    metas = _metas_do_stem(stem)
    assert metas, f"nenhum meta para {stem}"
    dos_metas = sorted({p for m in metas for p in m["paginas"]["ativo"] + m["paginas"]["passivo"]})
    assert do_manifesto == dos_metas == PAGINAS_ESPERADAS[stem]


@pytest.mark.parametrize("stem", sorted(PAGINAS_ESPERADAS))
def test_b_f4_hash_do_pdf_igual_ao_dos_metas(manifesto, stem):
    for meta in _metas_do_stem(stem):
        assert manifesto["fontes"][stem]["pdf_sha256"] == meta["pdf_sha256"]


def test_b_f5_tamanho_total_abaixo_de_50kb():
    total = sum(p.stat().st_size for p in FIXTURES.rglob("*") if p.is_file())
    assert total < 50 * 1024, total


def test_gitattributes_desliga_conversao_de_fim_de_linha():
    assert (FIXTURES / ".gitattributes").read_text(encoding="utf-8").strip() == "* -text"


def test_invalidos_sao_8_listas_de_um_registro():
    arquivos = sorted((FIXTURES / "invalidos").glob("*.json"))
    assert len(arquivos) == 8
    for f in arquivos:
        dados = json.loads(f.read_text(encoding="utf-8"))
        assert isinstance(dados, list) and len(dados) == 1, f.name


@pytest.mark.pdf
def test_b_f6_gerador_check_em_dia():
    spec = importlib.util.spec_from_file_location("gerar_fixtures", RAIZ / "scripts" / "gerar_fixtures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--check"]) == 0
