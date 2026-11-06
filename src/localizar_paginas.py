"""Rank pages extracted from PDFs by reusable topic keywords.

Usage::

    python src/localizar_paginas.py saida/empresa_APRESENTACAO_3T26 \
        --tema operacional --top 10
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path


TERMOS_POR_TEMA: dict[str, tuple[str, ...]] = {
    "operacional": (
        "toneladas",
        "mil t",
        "r$/t",
        "capacidade",
        "embarques",
        "vendas",
        "exportação",
        "segmento",
    ),
    "qualitativo": (
        "estratégia",
        "perspectivas",
        "guidance",
        "capex",
        "riscos",
    ),
    "ebitda": (
        "ebitda",
        "ebitda ajustado",
        "margem ebitda",
        "segmento",
    ),
}

_PAGINA_RE = re.compile(r"pagina_(\d+)\.txt$")


def normalizar(texto: str) -> str:
    """Return text suitable for case- and accent-insensitive matching."""

    decomposed = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(char for char in decomposed if not unicodedata.combining(char))
    return sem_acentos.casefold()


def pontuar_pagina(texto: str, termos: tuple[str, ...]) -> tuple[int, list[str]]:
    """Count keyword occurrences and return score plus terms present."""

    texto_normalizado = normalizar(texto)
    ocorrencias: list[str] = []
    pontuacao = 0
    for termo in termos:
        quantidade = texto_normalizado.count(normalizar(termo))
        if quantidade:
            pontuacao += quantidade
            ocorrencias.append(termo)
    return pontuacao, ocorrencias


def localizar(pasta: Path, tema: str, top: int = 10) -> list[dict[str, object]]:
    """Rank non-empty extracted pages for ``tema``.

    Results are deterministic: higher scores first, then lower page number.
    """

    if tema not in TERMOS_POR_TEMA:
        raise ValueError(f"tema inválido: {tema!r}; escolha entre {', '.join(TERMOS_POR_TEMA)}")
    if top <= 0:
        raise ValueError("top deve ser maior que zero")

    pasta = Path(pasta)
    if not pasta.is_dir():
        raise NotADirectoryError(pasta)

    resultados: list[dict[str, object]] = []
    for arquivo in pasta.glob("pagina_*.txt"):
        match = _PAGINA_RE.fullmatch(arquivo.name)
        if not match:
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if not texto.strip():
            continue
        pontuacao, termos = pontuar_pagina(texto, TERMOS_POR_TEMA[tema])
        if pontuacao:
            resultados.append(
                {"pagina": int(match.group(1)), "pontuacao": pontuacao, "termos": termos}
            )

    resultados.sort(key=lambda item: (-int(item["pontuacao"]), int(item["pagina"])))
    return resultados[:top]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pasta_saida", type=Path)
    parser.add_argument("--tema", choices=tuple(TERMOS_POR_TEMA), required=True)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args(argv)

    try:
        resultados = localizar(args.pasta_saida, args.tema, args.top)
    except (NotADirectoryError, ValueError) as exc:
        parser.error(str(exc))

    for item in resultados:
        termos = ", ".join(item["termos"])
        print(f"página {item['pagina']:02d} | pontuação {item['pontuacao']} | {termos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
