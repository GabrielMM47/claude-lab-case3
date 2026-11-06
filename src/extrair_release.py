"""
Case 3 — Comparativo de resultados · extrai texto e tabelas de um release em PDF.

Rode da raiz do repositório:
    python src/extrair_release.py data/itrs/EMPRESA_ITR_3T26.pdf

Saídas em saida/<nome_do_pdf>/ (na raiz do repositório):
    texto_completo.txt        o texto de todas as páginas, com marcadores de página
    pagina_NN.txt             o texto de cada página (usado pelo verificar_numeros.py)
    tabela_pNN_K.csv          cada tabela que o pdfplumber conseguiu reconhecer
"""
import sys
from pathlib import Path

import pandas as pd
import pdfplumber

SAIDA = Path(__file__).resolve().parent.parent / "saida"


def extrair(pdf_path: Path) -> Path:
    destino = SAIDA / pdf_path.stem
    destino.mkdir(parents=True, exist_ok=True)
    completo, n_tabelas = [], 0
    with pdfplumber.open(pdf_path) as pdf:
        for n, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text() or ""
            (destino / f"pagina_{n:02d}.txt").write_text(texto, encoding="utf-8")
            completo.append(f"\n===== PÁGINA {n} =====\n{texto}")
            for k, tabela in enumerate(pagina.extract_tables(), start=1):
                if tabela and len(tabela) > 1:
                    pd.DataFrame(tabela[1:], columns=tabela[0]).to_csv(
                        destino / f"tabela_p{n:02d}_{k}.csv", index=False)
                    n_tabelas += 1
        n_paginas = len(pdf.pages)
    (destino / "texto_completo.txt").write_text("".join(completo), encoding="utf-8")
    print(f"{pdf_path.name}: {n_paginas} páginas, {n_tabelas} tabelas → {destino}")
    return destino


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python extrair_release.py <arquivo.pdf> [outro.pdf ...]")
    for arg in sys.argv[1:]:
        extrair(Path(arg))
