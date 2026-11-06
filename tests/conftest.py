"""Configuração compartilhada dos testes: marcador `pdf` e fixtures de texto.

A suíte padrão é hermética: usa só tests/fixtures/ (10 páginas de texto) e não abre PDFs.
Testes marcados com `@pytest.mark.pdf` usam data/itrs/*.pdf e só rodam com `pytest --com-pdf`.
"""
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

FIXTURES = RAIZ / "tests" / "fixtures"
STEMS = ("gerdau_ITR_3T26", "usiminas_ITR_3T26")
PDF_FALSO = b"%PDF-1.4 fixture de teste\n"


def pytest_addoption(parser):
    parser.addoption("--com-pdf", action="store_true", default=False,
                     help="roda também os testes que usam data/itrs/*.pdf (marcador 'pdf')")


def pytest_configure(config):
    import importlib.util
    faltando = [m for m in ("jsonschema", "referencing", "matplotlib", "pdfplumber")
                if importlib.util.find_spec(m) is None]
    if faltando:
        raise pytest.UsageError(
            f"dependências ausentes neste Python ({sys.executable}): {', '.join(faltando)}. "
            "Rode `pip install -r requirements.txt` ou use o venv: `.venv/bin/python -m pytest`.")
    config.addinivalue_line("markers", "pdf: usa data/itrs/*.pdf; só roda com --com-pdf")


def pytest_collection_modifyitems(config, items):
    com_pdf = config.getoption("--com-pdf")
    for item in items:
        if item.get_closest_marker("pdf") is None:
            continue
        if not com_pdf:
            item.add_marker(pytest.mark.skip(reason="use --com-pdf"))
            continue
        for stem in STEMS:
            pdf = RAIZ / "data" / "itrs" / f"{stem}.pdf"
            if not pdf.is_file():
                item.add_marker(pytest.mark.skip(reason=f"PDF ausente: {pdf}"))
                break


@pytest.fixture(scope="session")
def manifesto() -> dict:
    return json.loads((FIXTURES / "MANIFEST.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def n_paginas(manifesto):
    def obter(stem: str) -> int:
        return manifesto["fontes"][stem]["n_paginas_pdf"]
    return obter


@pytest.fixture(scope="session")
def pasta_fixture():
    def obter(stem: str) -> Path:
        return FIXTURES / stem
    return obter


@pytest.fixture(scope="session")
def textos(tmp_path_factory, n_paginas):
    """stem -> pasta COMPLETA em tmp: fixtures copiadas byte a byte e páginas ausentes vazias."""
    cache: dict[str, Path] = {}

    def obter(stem: str) -> Path:
        if stem not in cache:
            pasta = tmp_path_factory.mktemp("textos") / stem
            pasta.mkdir()
            for n in range(1, n_paginas(stem) + 1):
                origem = FIXTURES / stem / f"pagina_{n:02d}.txt"
                dados = origem.read_bytes() if origem.is_file() else b""
                (pasta / origem.name).write_bytes(dados)
            cache[stem] = pasta
        return cache[stem]
    return obter


@pytest.fixture
def pdf_falso(tmp_path, monkeypatch, n_paginas):
    import extrair_balanco

    def criar(stem: str) -> Path:
        pdf = tmp_path / "pdf" / f"{stem}.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(PDF_FALSO)
        return pdf

    monkeypatch.setattr(extrair_balanco, "contar_paginas_pdf", lambda p: n_paginas(Path(p).stem))
    return criar
