"""CASE-06 · entradas da apresentação executiva.

Por enquanto confere que a fixture fictícia (tests/fixtures_apresentacao/) segue o contrato de
docs/TAREFAS.md e as regras que a apresentação depende: todo número com página, N/D e N/C com
motivo, vencedor só quando faz sentido, narrativa sem número escrito à mão.
Quando o CASE-01/05 publicarem a fixture oficial, acrescentar o caminho dela em PASTAS_COMPARATIVO.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import apresentacao as ap  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures_apresentacao"
PASTAS_COMPARATIVO = [FIXTURE / "comparativo" / "empresa_a_x_empresa_b_3T26"]
NARRATIVA = FIXTURE / "narrativa" / "empresa_a_x_empresa_b_3T26.json"
QUALITATIVOS = sorted((FIXTURE / "metricas").glob("*_apresentacao_qualitativo.json"))

IDS_SLIDES = {"capa", "resumo", "perfil", "comparativo", "graficos", "setor", "destaques_riscos", "metodologia"}
STATUS_INDISPONIVEL = {"ausente": "N/D", "nao_comparavel": "N/C", "nao_aplicavel": "N/A"}
TEMAS = {"perfil", "capacidade_footprint", "mercados_produtos", "estrategia", "capex_investimentos",
         "guidance_perspectivas", "riscos", "esg", "destaques_trimestre"}
FONTE = re.compile(r"^(ITR|Apresentação) p\.\d+$")
ROTULO_PERIODO = re.compile(r"\b\d[TM]\d{2}\b")
PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def ler(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


def tem_numero(texto: str) -> bool:
    """Há dígito fora dos rótulos de período (3T26, 9M26)?"""
    return bool(re.search(r"\d", ROTULO_PERIODO.sub("", texto)))


def br_para_float(s: str) -> tuple[float, int]:
    """Primeiro número pt-BR do texto e quantas casas decimais ele tem."""
    m = re.search(r"-?\d[\d.]*(,\d+)?", s)
    bruto = m.group(0)
    casas = len(m.group(1)) - 1 if m.group(1) else 0
    return float(bruto.replace(".", "").replace(",", ".")), casas


@pytest.fixture(params=PASTAS_COMPARATIVO, ids=lambda p: p.name)
def pasta(request) -> Path:
    return request.param


@pytest.fixture
def comp(pasta) -> dict:
    return ler(pasta / "comparativo.json")


def lados(comp):
    for linha in comp["linhas"]:
        for e in ("a", "b"):
            yield linha, e, linha[e]


# ---------------------------------------------------------------- comparativo.json
def test_campos_do_contrato(comp):
    for campo in ("periodo", "criterio_ebitda", "empresas", "linhas", "segmentos", "insights",
                  "alertas", "graficos", "verificacao"):
        assert campo in comp, campo
    assert comp["criterio_ebitda"] in ("ajustado", "contabil")
    for e in ("a", "b"):
        assert set(comp["empresas"][e]) >= {"slug", "nome", "ticker", "cor"}
    for linha in comp["linhas"]:
        assert set(linha) >= {"chave", "nome", "grupo", "unidade", "melhor", "vencedor", "a", "b"}
        for e in ("a", "b"):
            assert set(linha[e]) >= {"valor", "texto", "var_aa", "var_tt", "unidade_var", "fontes",
                                     "disponivel"}, (linha["chave"], e)


def test_todo_numero_disponivel_tem_fonte_com_pagina(comp):
    for linha, e, lado in lados(comp):
        if lado["disponivel"]:
            assert lado["fontes"], f"{linha['chave']} ({e}) sem fonte"
        for f in lado["fontes"]:
            assert FONTE.match(f), f"{linha['chave']} ({e}): fonte fora do padrão '{f}'"
    for e, segs in comp["segmentos"].items():
        for s in segs:
            assert s.get("fontes") and all(FONTE.match(f) for f in s["fontes"]), (e, s["segmento"])
    for alerta in comp["alertas"]:
        if tem_numero(alerta["texto"]):
            assert alerta.get("fontes"), f"alerta com número e sem fonte: {alerta['texto']}"
    for g in comp["graficos"]:
        assert g.get("fontes"), f"gráfico sem fonte: {g['id']}"


def test_texto_bate_com_valor(comp):
    for linha, e, lado in lados(comp):
        if not lado["disponivel"]:
            continue
        lido, casas = br_para_float(lado["texto"])
        if lado["texto"].lstrip().startswith("-"):
            lido = -abs(lido)
        assert abs(lido - lado["valor"]) <= 0.5 * 10 ** -casas + 1e-9, (linha["chave"], e, lado["texto"])


def test_indisponivel_tem_status_e_motivo(comp):
    for linha, e, lado in lados(comp):
        if lado["disponivel"]:
            assert lado["valor"] is not None, (linha["chave"], e)
            continue
        assert lado["valor"] is None and lado["var_aa"] is None and lado["var_tt"] is None
        assert lado.get("status") in STATUS_INDISPONIVEL, (linha["chave"], e)
        assert lado["texto"] == STATUS_INDISPONIVEL[lado["status"]]
        assert lado.get("obs"), f"{linha['chave']} ({e}) indisponível sem motivo"


def test_vencedor_segue_a_regra(comp):
    for linha in comp["linhas"]:
        a, b, v = linha["a"], linha["b"], linha["vencedor"]
        if linha["melhor"] is None or not (a["disponivel"] and b["disponivel"]):
            assert v is None, f"{linha['chave']}: vencedor sem regra ou com lado indisponível"
            continue
        assert linha["melhor"] in ("maior", "menor")
        if a["valor"] != b["valor"]:
            esperado = "a" if (a["valor"] > b["valor"]) == (linha["melhor"] == "maior") else "b"
            assert v == esperado, linha["chave"]


def test_variacao_em_pp_para_percentual(comp):
    for linha, e, lado in lados(comp):
        if linha["unidade"] == "%" and (lado["var_aa"] is not None or lado["var_tt"] is not None):
            assert lado["unidade_var"] == "p.p.", (linha["chave"], e)


def test_graficos_existem(comp, pasta):
    for g in comp["graficos"]:
        assert (pasta / g["arquivo"]).is_file(), g["arquivo"]


# ---------------------------------------------------------------- qualitativo (CASE-03)
@pytest.mark.parametrize("arquivo", QUALITATIVOS, ids=lambda p: p.name)
def test_qualitativo_tem_pagina_trecho_e_resumo_curto(arquivo):
    fatos = ler(arquivo)
    assert fatos
    for f in fatos:
        assert f["chave"] == "qualitativo" and f["tema"] in TEMAS, f
        assert isinstance(f["pagina"], int) and f["pagina"] >= 1, f
        assert f["trecho"].strip(), f
        assert len(f["resumo"].split()) <= 30, f["resumo"]


# ---------------------------------------------------------------- narrativa (CASE-06)
def textos_da_narrativa(narrativa: dict):
    for slide in narrativa["slides"]:
        for campo in ("titulo", "subtitulo"):
            if slide.get(campo):
                yield slide["id"], slide[campo]
        for bullet in slide.get("bullets", []):
            yield slide["id"], bullet


def test_narrativa_tem_os_slides_do_roteiro():
    ids = [s["id"] for s in ler(NARRATIVA)["slides"]]
    assert set(ids) == IDS_SLIDES and len(ids) == len(IDS_SLIDES)


def test_narrativa_sem_numero_escrito_a_mao():
    for sid, texto in textos_da_narrativa(ler(NARRATIVA)):
        assert not tem_numero(PLACEHOLDER.sub("", texto)), f"[{sid}] número fora de placeholder: {texto}"


def test_placeholders_da_narrativa_existem():
    comp = ler(PASTAS_COMPARATIVO[0] / "comparativo.json")
    chaves = {linha["chave"] for linha in comp["linhas"]}
    for sid, texto in textos_da_narrativa(ler(NARRATIVA)):
        for nome in PLACEHOLDER.findall(texto):
            partes = nome.split(".")
            if partes[0] in ("a", "b"):
                assert partes[1] == "nome" or partes[1] in chaves, f"[{sid}] {{{nome}}}"
                assert len(partes) == 2 or partes[2] in ("var_aa", "var_tt"), f"[{sid}] {{{nome}}}"
            else:
                assert nome in ("periodo", "criterio_ebitda"), f"[{sid}] {{{nome}}}"


# ---------------------------------------------------------------- gerador (src/apresentacao.py)
@pytest.fixture
def dados():
    return ap.carregar(PASTAS_COMPARATIVO[0], FIXTURE / "metricas")


def secoes(html_: str) -> list[str]:
    return re.findall(r'<section class="slide".*?</section>', html_, flags=re.S)


@pytest.mark.parametrize("com_narrativa", [True, False], ids=["narrativa", "insights"])
def test_gera_8_slides_com_fonte_e_aviso_em_todos(dados, com_narrativa):
    html_ = ap.gerar_html(dados, ler(NARRATIVA) if com_narrativa else None)
    slides = secoes(html_)
    assert [re.search(r'id="(\w+)"', s).group(1) for s in slides] == ap.IDS_SLIDES
    for s in slides:
        assert ap.AVISO in s
        assert 'data-fontes="sim"' in s, f"slide sem fonte: {s[:80]}"
        assert re.search(r"(ITR|Apresentação) p\. \d", s)
    assert "{" not in "".join(re.sub(r"<style>.*?</style>|<script>.*?</script>", "", html_, flags=re.S))
    assert html_.count("data:image/png;base64,") >= 4  # gráficos embutidos: arquivo único


def test_tabela_mostra_nd_e_nc_com_motivo(dados):
    html_ = ap.gerar_html(dados, None)
    comparativo = next(s for s in secoes(html_) if 'id="comparativo"' in s)
    assert "N/D" in comparativo and "falta ir_csll" in comparativo
    setor = next(s for s in secoes(html_) if 'id="setor"' in s)
    assert "N/C" in setor and "mineração" in setor


def test_metodologia_traz_verificacao_e_numeracao_do_pdf(dados):
    metodologia = next(s for s in secoes(ap.gerar_html(dados, None)) if 'id="metodologia"' in s)
    assert "52 de 52" in metodologia and "numeração do PDF" in metodologia
    sem = copy.deepcopy(dados)
    sem.comp["verificacao"] = None
    metodologia = next(s for s in secoes(ap.gerar_html(sem, None)) if 'id="metodologia"' in s)
    assert "ainda não rodou" in metodologia


def test_destaque_ignora_variacao_com_efeito_pontual(dados):
    pos, neg, _ = ap.destaques_numericos(dados, "b")
    assert pos is None or "Margem líquida" not in pos  # 3T25 com impairment: A/A engana
    assert neg and neg.startswith("Margem EBITDA ajustada")


def test_resolver_formata_e_registra_fonte(dados):
    fontes = ap.Fontes()
    texto = ap.resolver("{a.nome}: {a.margem_ebitda} ({a.margem_ebitda.var_aa} A/A), {b.dl_ebitda}", dados, fontes)
    assert texto == "Empresa A: 16,0% (+2,6 p.p. A/A), -0,13x"
    assert fontes.texto(dados.nomes) == "Empresa A — ITR p. 29, 71 · Empresa B — ITR p. 11, 12, 24"


def test_narrativa_da_fixture_passa_no_verificador(dados):
    assert ap.verificar_narrativa(ler(NARRATIVA), dados) == []


@pytest.mark.parametrize("texto, trecho_do_erro", [
    ("Margem de 16,0% na {a.nome}", "número escrito à mão"),
    ("{a.margem_bruta} na {a.nome}", "não existe"),
    ("ROIC de {b.roic}", "indisponível"),
    ("Lucro {b.lucro_liquido.var_aa} A/A", "variação indisponível"),
    ("Receita do 1T24: {a.receita_liquida}", "período 1T24"),
    ("{c.receita_liquida}", "desconhecido"),
])
def test_verificador_reprova_narrativa_errada(dados, texto, trecho_do_erro):
    narrativa = {"slides": [{"id": "resumo", "titulo": "ok", "bullets": [texto]}]}
    problemas = ap.verificar_narrativa(narrativa, dados)
    assert any(trecho_do_erro in p for p in problemas), problemas


def test_cli_recusa_narrativa_reprovada(tmp_path, capsys):
    ruim = tmp_path / "narrativa.json"
    ruim.write_text(json.dumps({"slides": [{"id": "capa", "titulo": "Margem de 16,0%"}]}), encoding="utf-8")
    saida = tmp_path / "deck.html"
    codigo = ap.main(["--comparativo", str(PASTAS_COMPARATIVO[0]), "--narrativa", str(ruim),
                      "--metricas", str(FIXTURE / "metricas"), "--saida", str(saida)])
    assert codigo == 1 and not saida.exists()
    assert "reprovada" in capsys.readouterr().err


def test_cli_gera_arquivo(tmp_path):
    saida = tmp_path / "deck.html"
    codigo = ap.main(["--comparativo", str(PASTAS_COMPARATIVO[0]), "--narrativa", str(NARRATIVA),
                      "--metricas", str(FIXTURE / "metricas"), "--saida", str(saida)])
    assert codigo == 0 and len(secoes(saida.read_text(encoding="utf-8"))) == 8
