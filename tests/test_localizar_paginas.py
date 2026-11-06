import subprocess
import sys
from pathlib import Path

import pytest

from src.localizar_paginas import localizar, normalizar


def test_normalizar_remove_acentos_e_case():
    assert normalizar("Exportação de AÇO — capacidade") == "exportacao de aco — capacidade"


def test_localizar_ignora_paginas_vazias_e_aplica_top(tmp_path: Path):
    (tmp_path / "pagina_01.txt").write_text(
        "Vendas de toneladas", encoding="utf-8"
    )
    (tmp_path / "pagina_02.txt").write_text(
        "Toneladas toneladas capacidade", encoding="utf-8"
    )
    (tmp_path / "pagina_03.txt").write_text("", encoding="utf-8")
    (tmp_path / "notas.txt").write_text("toneladas", encoding="utf-8")

    resultado = localizar(tmp_path, "operacional", top=1)

    assert len(resultado) == 1
    assert resultado[0]["pagina"] == 2
    assert resultado[0]["pontuacao"] == 3
    assert resultado[0]["termos"] == ["toneladas", "capacidade"]


def test_localizar_desempata_por_numero_da_pagina(tmp_path: Path):
    (tmp_path / "pagina_02.txt").write_text("capacidade", encoding="utf-8")
    (tmp_path / "pagina_01.txt").write_text("capacidade", encoding="utf-8")

    resultado = localizar(tmp_path, "operacional", top=10)

    assert [item["pagina"] for item in resultado] == [1, 2]


def test_cli_rejeita_tema_invalido(tmp_path: Path):
    processo = subprocess.run(
        [
            sys.executable,
            "src/localizar_paginas.py",
            str(tmp_path),
            "--tema",
            "financeiro",
        ],
        capture_output=True,
        text=True,
    )

    assert processo.returncode != 0
    assert "tema" in (processo.stderr + processo.stdout).lower()
