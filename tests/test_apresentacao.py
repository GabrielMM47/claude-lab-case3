"""CASE-06 · entradas da apresentação executiva.

Por enquanto confere que a fixture fictícia (tests/fixtures_apresentacao/) segue o contrato de
docs/TAREFAS.md e as regras que a apresentação depende: todo número com página, N/D e N/C com
motivo, vencedor só quando faz sentido, narrativa sem número escrito à mão.
Quando o CASE-01/05 publicarem a fixture oficial, acrescentar o caminho dela em PASTAS_COMPARATIVO.
"""
from __future__ import annotations

import copy
import html
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


def test_efeito_pontual_citando_so_ebitda_tambem_tira_linhas_contabeis(dados):
    # Como o comparar.py real faz: o alerta cita só as linhas de EBITDA. O impairment do 3T25,
    # porém, está no lucro e na margem líquida (o EBITDA ajustado já o exclui).
    real = copy.deepcopy(dados)
    for alerta in real.comp["alertas"]:
        if alerta["tipo"] == "efeito_pontual":
            alerta["chaves"] = ["ebitda_ajustado", "margem_ebitda"]
    pos, neg, _ = ap.destaques_numericos(real, "b")
    assert pos is None or "Margem líquida" not in pos
    # sem margem que piorou fora das distorcidas: cai na pior linha financeira do trimestre
    assert neg and neg.startswith(("Receita líquida", "EBITDA")) and "A/A" in neg


def test_efeito_pontual_sem_linhas_nao_tira_nada(dados):
    # alerta de outro período (o comparativo não cita linhas): a margem líquida volta a valer
    sem = copy.deepcopy(dados)
    for alerta in sem.comp["alertas"]:
        if alerta["tipo"] == "efeito_pontual":
            alerta["chaves"] = []
    pos, _, _ = ap.destaques_numericos(sem, "b")
    assert pos and pos.startswith("Margem líquida")


def test_perfil_usa_rotulo_do_segmento(dados):
    com_rotulo = copy.deepcopy(dados)
    seg = com_rotulo.comp["segmentos"]["a"][0]
    seg["rotulo"] = "Rótulo Legível"
    perfil = next(s for s in secoes(ap.gerar_html(com_rotulo, None)) if 'id="perfil"' in s)
    assert "Segmentos: Rótulo Legível " in perfil and f"Segmentos: {seg['segmento']} " not in perfil


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


# ---------------------------------------------------------------- contexto macro e cenários
MACRO_A = {"chave": "contexto_macro", "id": "tarifa", "tema": "contexto_macro", "metrica": "Tarifa",
           "resumo": "Tarifa fictícia.", "empresa": "empresa_a", "documento": "apresentacao",
           "escopo": "consolidado", "periodo": "3T26", "unidade": "%", "valor": 50,
           "valor_como_aparece": "50%", "pagina": 9, "trecho": "Tarifa de 50% (FICTÍCIO)"}
QUALI_B = {"chave": "qualitativo", "id": "origens", "tema": "contexto_macro", "metrica": "Origens",
           "resumo": "Origens fictícias.", "empresa": "empresa_b", "documento": "itr", "pagina": 23,
           "trecho": "origens (FICTÍCIO)"}
POR_T = {"volume_vendas": {"valor": 1000.0, "texto": "1.000 mil t", "var_aa": -5.0, "unidade": "mil t",
                           "unidade_var": "%", "fontes": ["Apresentação p.18"]},
         "ebitda_por_t": {"valor": 500.0, "texto": "R$ 500/t", "var_aa": 10.0, "unidade": "R$/t",
                          "unidade_var": "%", "fontes": ["ITR p.72", "Apresentação p.18"]}}
CENARIO = {"nome": "Base", "gatilho": "tarifa mantida",
           "a": {"efeito": "++", "texto": "ganha com tarifa de {a.macro.tarifa}"},
           "b": {"efeito": "-", "texto": "sofre com importação", "cita": ["b.origens"]},
           "vantagem": "a", "nota": "na margem"}


@pytest.fixture
def com_macro(dados):
    d = copy.deepcopy(dados)
    d.macro = {"a": {"tarifa": copy.deepcopy(MACRO_A)}, "b": {"origens": copy.deepcopy(QUALI_B)}}
    d.comp["segmentos"]["a"][0]["por_t"] = copy.deepcopy(POR_T)
    return d


def narrativa_macro(**extra_destaques) -> dict:
    n = copy.deepcopy(ler(NARRATIVA))
    for s in n["slides"]:
        if s["id"] == "setor":
            s["contexto"] = [{"titulo": "EUA", "texto": "Seção 232 a {a.macro.tarifa}"},
                             {"titulo": "Brasil", "texto": "novas origens", "cita": ["b.origens"]}]
        if s["id"] == "destaques_riscos":
            s["cenarios"] = [copy.deepcopy(CENARIO)]
            s["monitorar"] = {"texto": "importações e tarifas", "cita": ["b.origens"]}
            s.update(extra_destaques)
    return n


def test_carregar_le_contexto_macro_pelo_id(tmp_path):
    (tmp_path / "empresa_a_3T26_apresentacao_macro.json").write_text(json.dumps([MACRO_A]), encoding="utf-8")
    (tmp_path / "empresa_b_3T26_itr_macro.json").write_text(json.dumps([QUALI_B]), encoding="utf-8")
    d = ap.carregar(PASTAS_COMPARATIVO[0], tmp_path)
    assert set(d.macro["a"]) == {"tarifa"} and set(d.macro["b"]) == {"origens"}


def test_resolver_macro_e_segmento(com_macro):
    fontes = ap.Fontes()
    texto = ap.resolver("{a.macro.tarifa}; {a.seg.brasil.ebitda_por_t} ({a.seg.brasil.ebitda_por_t.var_aa} A/A), "
                        "{a.seg.brasil.pct_ebitda} do EBITDA", com_macro, fontes)
    assert texto == "50%; R$ 500/t (+10,0% A/A), 55% do EBITDA"
    assert fontes.texto(com_macro.nomes) == "Empresa A — Apresentação p. 9, 18; ITR p. 72"


@pytest.mark.parametrize("item, trecho_do_erro", [
    ("{a.macro.nao_existe}", "não existe em metricas/*_macro.json"),
    ("{b.macro.origens}", "não tem número"),
    ("{a.seg.marte.pct_ebitda}", "segmento 'marte'"),
    ("{a.seg.brasil.receita_por_t}", "não tem receita_por_t"),
    ("{a.seg.brasil.lucro}", "campo 'lucro' inválido"),
    ({"texto": "sem número", "cita": ["b.nao_existe"]}, "cita 'b.nao_existe'"),
    ("Lei 123 em vigor", "número escrito à mão"),
])
def test_verificador_reprova_contexto_errado(com_macro, item, trecho_do_erro):
    narrativa = {"slides": [{"id": "resumo", "titulo": "ok", "bullets": [item]}]}
    problemas = ap.verificar_narrativa(narrativa, com_macro)
    assert any(trecho_do_erro in p for p in problemas), problemas


def test_narrativa_com_cenarios_passa_e_vira_slide(com_macro):
    narrativa = narrativa_macro()
    assert ap.verificar_narrativa(narrativa, com_macro) == []  # "Seção 232" é nome, não dado
    slides = {re.search(r'id="(\w+)"', s).group(1): s for s in secoes(ap.gerar_html(com_macro, narrativa))}
    setor, destaques = slides["setor"], slides["destaques_riscos"]
    assert 'class="tabela segs"' in setor and 'class="tiles"' not in setor  # por negócio substitui o consolidado
    assert "Seção 232 a 50%" in setor and 'class="contexto"' in setor
    assert "Apresentação p. 9" in setor and "Empresa B — ITR p. 23" in setor  # número e citação no rodapé
    assert 'class="cenarios"' in destaques and "▲▲" in destaques and "ganha com tarifa de 50%" in destaques
    assert "O que acompanhar:" in destaques and "Riscos:" not in destaques  # tabela no lugar do genérico
    assert re.search(r"Empresa B — ITR p\. [\d, ]*\b23\b", destaques)  # citação do cenário


def test_destaques_sem_alerta_de_indisponivel(com_macro):
    destaques = next(s for s in secoes(ap.gerar_html(com_macro, narrativa_macro())) if 'id="destaques_riscos"' in s)
    indisponivel = next(a for a in com_macro.comp["alertas"] if a["tipo"] == "indisponivel")
    pontual = next(a for a in com_macro.comp["alertas"] if a["tipo"] == "efeito_pontual")
    assert html.escape(indisponivel["texto"]) not in destaques
    assert html.escape(pontual["texto"]) in destaques


@pytest.mark.parametrize("mudanca, trecho_do_erro", [
    ({"a": {"efeito": "+++", "texto": "x"}}, "efeito de 'a'"),
    ({"vantagem": "c"}, "vantagem deve ser"),
])
def test_cenario_mal_formado_reprova(com_macro, mudanca, trecho_do_erro):
    narrativa = narrativa_macro()
    destaques = next(s for s in narrativa["slides"] if s["id"] == "destaques_riscos")
    destaques["cenarios"][0].update(mudanca)
    assert any(trecho_do_erro in p for p in ap.verificar_narrativa(narrativa, com_macro))


def test_cli_gera_arquivo(tmp_path):
    saida = tmp_path / "deck.html"
    codigo = ap.main(["--comparativo", str(PASTAS_COMPARATIVO[0]), "--narrativa", str(NARRATIVA),
                      "--metricas", str(FIXTURE / "metricas"), "--saida", str(saida)])
    assert codigo == 0 and len(secoes(saida.read_text(encoding="utf-8"))) == 8
