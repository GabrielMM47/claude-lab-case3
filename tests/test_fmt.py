"""Testes de contrato.fmt_br / contrato.fmt_var (formatação pt-BR do CASE-05)."""
import math
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from contrato import fmt_br, fmt_var  # noqa: E402


@pytest.mark.parametrize("valor, unidade, esperado", [
    (15000.0, "R$ milhões", "R$ 15.000,0 mi"),
    (1234.0, "R$ mil", "R$ 1.234 mil"),
    (16.0, "%", "16,0%"),
    (6.0, "p.p.", "6,0 p.p."),
    (0.57, "x", "0,57x"),
    (1034.0, "mil t", "1.034 mil t"),
    (6900.0, "mil t/ano", "6.900 mil t/ano"),
    (4849.0, "R$/t", "R$ 4.849/t"),
    (75.0, "US$/t", "US$ 75/t"),
    (1234.5, "kton", "1.234,5 kton"),
    (1234.5, None, "1.234,5"),
    (1234567.891, "R$ milhões", "R$ 1.234.567,9 mi"),
    (0.0, "%", "0,0%"),
])
def test_tabela_de_formatos(valor, unidade, esperado):
    assert fmt_br(valor, unidade) == esperado


@pytest.mark.parametrize("valor, unidade, esperado", [
    (-300.0, "R$ milhões", "-R$ 300,0 mi"),
    (-0.13, "x", "-0,13x"),
    (-4.8, "%", "-4,8%"),
    (-1034.0, "mil t", "-1.034 mil t"),
    (-1234.5, "kton", "-1.234,5 kton"),
])
def test_negativo_com_hifen_ascii(valor, unidade, esperado):
    texto = fmt_br(valor, unidade)
    assert texto == esperado
    assert "−" not in texto


def test_zero_arredondado_sem_sinal():
    assert fmt_br(-0.01, "%") == "0,0%"
    assert fmt_br(-0.4, "R$ mil") == "R$ 0 mil"


def test_casas_explicitas():
    assert fmt_br(16.04, "%", casas=2) == "16,04%"
    assert fmt_br(15000.0, "R$ milhões", casas=0) == "R$ 15.000 mi"
    assert fmt_br(0.5678, "x", 1) == "0,6x"


@pytest.mark.parametrize("status, esperado", [
    ("ausente", "N/D"),
    ("nao_comparavel", "N/C"),
    ("nao_aplicavel", "N/A"),
    ("desconhecido", "N/D"),
])
def test_status_diferente_de_ok_nao_vira_numero(status, esperado):
    assert fmt_br(123.0, "%", status=status) == esperado
    assert fmt_br(None, "R$ milhões", status=status) == esperado


@pytest.mark.parametrize("valor", [None, math.nan, math.inf])
def test_valor_ausente_com_ok_e_nd(valor):
    assert fmt_br(valor, "R$ milhões") == "N/D"
    assert fmt_br(valor, "R$ milhões", status="ok") == "N/D"


@pytest.mark.parametrize("valor, unidade_var, esperado", [
    (5.63, "%", "+5,6%"),
    (-4.76, "%", "-4,8%"),
    (6.0, "p.p.", "+6,0 p.p."),
    (-1.9, "p.p.", "-1,9 p.p."),
    (1234.56, "%", "+1.234,6%"),
    (0.5, None, "+0,5"),
    (0.0, "%", "0,0%"),
    (-0.01, "p.p.", "0,0 p.p."),
])
def test_fmt_var(valor, unidade_var, esperado):
    assert fmt_var(valor, unidade_var) == esperado


def test_fmt_var_casas_e_multiplo():
    assert fmt_var(0.02, "x", casas=2) == "+0,02x"
    assert fmt_var(-12.3456, "%", casas=2) == "-12,35%"
    assert fmt_var(3.0, "%", casas=0) == "+3%"


@pytest.mark.parametrize("valor", [None, math.nan])
def test_fmt_var_none_vira_travessao(valor):
    assert fmt_var(valor, "%") == "—"
    assert fmt_var(valor, None) == "—"
