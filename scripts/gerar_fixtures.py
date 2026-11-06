"""Gera as fixtures de teste (páginas do Balanço Patrimonial) a partir dos ITRs em data/itrs/.

Uso:
    python scripts/gerar_fixtures.py [--check] [--destino DIR]

Extrai o texto direto do PDF com pdfplumber (page.extract_text() or "", o mesmo critério de
src/extrair_release.py), sem ler saida/. Grava tests/fixtures/<stem>/pagina_NN.txt (NN = índice
da página no PDF, base 1), MANIFEST.json, .gitattributes e README.md. Não toca em invalidos/.
Nunca edite as fixtures à mão: o conteúdo é cópia mecânica do PDF.

--check reextrai em memória e compara com os arquivos e o manifesto em disco
(código 1 se divergir; 2 se o PDF estiver ausente).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAGINAS = {"gerdau_ITR_3T26": (15, 16, 17, 26, 27, 28), "usiminas_ITR_3T26": (3, 4, 12, 13)}
EXTRACAO = 'pdfplumber: page.extract_text() or "" (mesmo critério de src/extrair_release.py)'

README = """# Fixtures de teste

Páginas do Balanço Patrimonial (consolidado e controladora) do ITR do 3T26 da Gerdau e da Usiminas,
em texto, usadas pelos testes para rodar sem os PDFs inteiros.

- **Fonte:** documentos públicos publicados pelas empresas e na CVM, os mesmos PDFs versionados em
  `data/itrs/`. Uso exclusivo de teste: cópia verbatim e mínima (10 páginas). Ver `docs/USO-DOS-DADOS.md`.
- **Nomes:** `pagina_NN.txt` usa o índice da página no PDF (base 1), o mesmo de `saida/<pdf>/pagina_NN.txt`.
  Só existem as páginas do Balanço; as demais ficam ausentes (os testes completam com páginas vazias).
- **Regenerar / conferir:** `python scripts/gerar_fixtures.py` e `python scripts/gerar_fixtures.py --check`
  (precisa dos PDFs em `data/itrs/`). O `MANIFEST.json` guarda bytes e SHA-256 de cada página e o SHA-256 dos PDFs.
- **Nunca edite à mão:** o teste de hash (`tests/test_fixtures.py`) pega qualquer alteração.
- **`invalidos/`:** JSONs fora do contrato (estáticos), usados pelos testes do verificador.
- **Fixtures negativas de texto** (dígito trocado, título alterado) são derivadas por mutação em `tmp_path`,
  dentro dos testes, e não ficam salvas aqui.
"""


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def extrair(raiz: Path = RAIZ) -> tuple[dict[str, dict[int, str]], dict[str, dict]]:
    import pdfplumber
    textos: dict[str, dict[int, str]] = {}
    fontes: dict[str, dict] = {}
    for stem, paginas in PAGINAS.items():
        pdf = raiz / "data" / "itrs" / f"{stem}.pdf"
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        with pdfplumber.open(pdf) as doc:
            textos[stem] = {n: (doc.pages[n - 1].extract_text() or "") for n in paginas}
            n_total = len(doc.pages)
        fontes[stem] = {"pdf": f"data/itrs/{stem}.pdf", "pdf_sha256": _sha(pdf.read_bytes()),
                        "n_paginas_pdf": n_total}
    return textos, fontes


def montar_manifesto(textos: dict[str, dict[int, str]], fontes: dict[str, dict]) -> dict:
    import pdfplumber
    arquivos = []
    for stem, pags in textos.items():
        for n, t in pags.items():
            b = t.encode("utf-8")
            arquivos.append({"arquivo": f"{stem}/pagina_{n:02d}.txt", "stem": stem, "pagina": n,
                             "bytes": len(b), "sha256": _sha(b)})
    arquivos.sort(key=lambda a: a["arquivo"])
    return {"versao": 1, "gerado_por": "scripts/gerar_fixtures.py", "extracao": EXTRACAO,
            "pdfplumber_versao": pdfplumber.__version__, "fontes": fontes, "arquivos": arquivos}


def _escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8", newline="")


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def gravar(destino: Path, textos, manifesto) -> None:
    for stem, pags in textos.items():
        for n, t in pags.items():
            _escrever(destino / stem / f"pagina_{n:02d}.txt", t)
    _escrever(destino / "MANIFEST.json", _json(manifesto))
    _escrever(destino / ".gitattributes", "* -text\n")
    _escrever(destino / "README.md", README)


def conferir(destino: Path, textos, manifesto) -> list[str]:
    divergentes = []
    for stem, pags in textos.items():
        for n, t in pags.items():
            arq = destino / stem / f"pagina_{n:02d}.txt"
            if not arq.is_file() or arq.read_bytes() != t.encode("utf-8"):
                divergentes.append(f"{stem}/pagina_{n:02d}.txt")
    mf = destino / "MANIFEST.json"
    if not mf.is_file():
        divergentes.append("MANIFEST.json")
    else:
        try:
            em_disco = json.loads(mf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            em_disco = None
        if (em_disco is None or em_disco.get("arquivos") != manifesto["arquivos"]
                or em_disco.get("fontes") != manifesto["fontes"]):
            divergentes.append("MANIFEST.json")
    return divergentes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gerar_fixtures.py", description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="só confere, não grava")
    ap.add_argument("--destino", type=Path, default=RAIZ / "tests" / "fixtures")
    args = ap.parse_args(argv)
    try:
        textos, fontes = extrair()
    except FileNotFoundError as e:
        print(f"ERRO: PDF não encontrado: {e}", file=sys.stderr)
        return 2
    manifesto = montar_manifesto(textos, fontes)
    if args.check:
        div = conferir(args.destino, textos, manifesto)
        for d in div:
            print(f"divergente: {d}")
        return 1 if div else 0
    gravar(args.destino, textos, manifesto)
    n = sum(len(p) for p in textos.values())
    print(f"→ {n} páginas e MANIFEST.json em {args.destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
