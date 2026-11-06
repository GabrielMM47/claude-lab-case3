"""Testes do extrator do Balanço Patrimonial (SPEC §11).

Rode da raiz:  pytest tests/test_extrair_balanco.py
Os testes de integração usam saida/<stem>/pagina_NN.txt se existir; senão
geram os textos em pasta temporária com pdfplumber (como o extrair_release).
Os valores esperados vêm das linhas literais do PDF (SPEC §10), convertidos com br_para_int.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import extrair_balanco as eb  # noqa: E402
import verificar_numeros as vn  # noqa: E402

ITRS = RAIZ / "data" / "itrs"


# ---------------------------------------------------------------------------
# Helpers sintéticos
# ---------------------------------------------------------------------------
def pagina_bp(visao: str, tipo: str, linhas: list[str], escala: str = "Reais Mil",
              datas: str = "Conta 30/09/2026 31/12/2025") -> str:
    cab = [f"DFs {visao} / Balanço Patrimonial {tipo}", f"({escala})",
           "Código da Descrição da Conta Trimestre Atual Exercício Anterior", datas]
    return "\n".join(cab + linhas)


def paginas(*textos: str) -> list[eb.PaginaTexto]:
    return [eb.PaginaTexto(n, t) for n, t in enumerate(textos, start=1)]


def cabecalhos_de(pags: list[eb.PaginaTexto]) -> dict[int, eb.Cabecalho]:
    return {p.numero: eb.ler_cabecalho(p.texto, p.numero) for p in pags}


ATIVO_MIN = ["1 Ativo Total 100 90", "1.01 Ativo Circulante 40 30", "1.02 Ativo Não Circulante 60 60"]
PASSIVO_MIN = ["2 Passivo Total 100 90", "2.01 Passivo Circulante 20 15",
               "2.02 Passivo Não Circulante 30 25", "2.03 Patrimônio Líquido Consolidado 50 50"]


def balanco_sintetico(ativo=ATIVO_MIN, passivo=PASSIVO_MIN) -> eb.Resultado:
    pags = paginas(pagina_bp("Consolidadas", "Ativo", list(ativo)),
                   pagina_bp("Consolidadas", "Passivo", list(passivo)))
    return eb.extrair_balanco(pags, "consolidado")


def falhas(res: eb.Resultado, vid: str) -> list[eb.Validacao]:
    return [v for v in res.validacoes if v.id == vid and not v.ok]


# ---------------------------------------------------------------------------
# 11.1 Unitários
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("lit, esperado", [
    ("83.945.525", 83945525), ("-395.736", -395736), ("(1.234)", -1234), ("0", 0), ("586", 586)])
def test_br_para_int(lit, esperado):
    assert eb.br_para_int(lit) == esperado


@pytest.mark.parametrize("lit", ["1,5", "12.34", ""])
def test_br_para_int_invalido(lit):
    with pytest.raises(ValueError):
        eb.br_para_int(lit)


@pytest.mark.parametrize("linha, codigo, descricao, atual, anterior", [
    ("2.03.02 Reservas de Capital -395.736 -508.470", "2.03.02", "Reservas de Capital", "-395.736", "-508.470"),
    ("2.01.05.02.09 Títulos a pagar - Forfaiting 0 570.111", "2.01.05.02.09", "Títulos a pagar - Forfaiting",
     "0", "570.111"),
    ("1.02.03.02.01 Arrendamento mercantil - direito de uso de ativos 1.612.352 1.271.462", "1.02.03.02.01",
     "Arrendamento mercantil - direito de uso de ativos", "1.612.352", "1.271.462"),
    ("2.03.05 Lucros/Prejuízos Acumulados 3.204.533 0", "2.03.05", "Lucros/Prejuízos Acumulados",
     "3.204.533", "0"),
])
def test_re_conta_casa(linha, codigo, descricao, atual, anterior):
    m = eb.RE_CONTA.match(linha)
    assert m is not None
    assert (m["codigo"], m["descricao"], m["atual"], m["anterior"]) == (codigo, descricao, atual, anterior)


@pytest.mark.parametrize("linha", [
    "PÁGINA: 13 de 65", "Conta 30/09/2026 31/12/2025",
    "ITR - InfoDrmFsa çCõoens sTorilmideasdtraasis / -B 3a0l/a0n9ç/2o0 P26a t-r iGmEoRnDiaAlU A St.iAvo. 21",
    "10 11"])
def test_re_conta_nao_casa(linha):
    assert eb.RE_CONTA.match(linha) is None


def test_classificar_pagina():
    assert eb.classificar_pagina(
        "DFs Individuais / Balanço Patrimonial DFs Individuais / Balanço Patrimonial\nalgo 1 2") is None
    assert eb.classificar_pagina("Balanço Patrimonial Ativo 2\nDemonstração do Resultado 4") is None
    assert eb.classificar_pagina(pagina_bp("Consolidadas", "Ativo", ["1 Ativo Total 10 10"])) == \
        ("Consolidadas", "Ativo")
    assert eb.classificar_pagina(pagina_bp("Consolidadas", "Ativo", [])) is None


def _cinco_paginas():
    return paginas(
        pagina_bp("Individuais", "Ativo", ["1 Ativo Total 10 10"]),
        pagina_bp("Individuais", "Passivo", ["2 Passivo Total 10 10"]),
        pagina_bp("Consolidadas", "Ativo", ["1 Ativo Total 20 20"]),
        pagina_bp("Consolidadas", "Passivo", ["2 Passivo Total 20 20"]),
        pagina_bp("Consolidadas", "Passivo", ["2.03.01 Capital Social 5 5"]))


def test_localizar_blocos():
    pags = _cinco_paginas()
    cons = eb.localizar_blocos(pags, "consolidado")
    assert cons["Ativo"].paginas == [3] and cons["Passivo"].paginas == [4, 5]
    ctrl = eb.localizar_blocos(pags, "controladora")
    assert ctrl["Ativo"].paginas == [1] and ctrl["Passivo"].paginas == [2]
    with pytest.raises(eb.ErroExtracao, match="não encontrado"):
        eb.localizar_blocos(pags[:3], "consolidado")


def test_localizar_blocos_duplicado():
    pags = _cinco_paginas()
    extra = pags + [eb.PaginaTexto(6, pags[2].texto)]
    with pytest.raises(eb.ErroExtracao, match="Mais de um bloco Ativo"):
        eb.localizar_blocos(extra, "consolidado")


def _parse(*corpos: list[str], tipo="Ativo"):
    pags = paginas(*(pagina_bp("Consolidadas", tipo, c) for c in corpos))
    return eb.parsear_bloco(pags, cabecalhos_de(pags), tipo), pags


def test_parser_rodape():
    rodape = "ITR - InfoDrmFsa çCõoens sTorilmideasdtraasis / -B 3a0l/a0n9ç/2o0 P26a t-r iGmEoRnDiaAlU A St.iAvo. 21"
    (contas, avisos), _ = _parse(["1.01.04 Estoques 10 20", rodape])
    assert len(contas) == 1 and contas[0].descricao == "Estoques" and avisos == []


def test_parser_descricao_quebrada_mesma_pagina():
    (contas, avisos), pags = _parse(["1.02.01.10.06 Gastos antecipados com plano", "de pensão 9.326 9.328"])
    assert len(contas) == 1
    c = contas[0]
    assert c.descricao == "Gastos antecipados com plano de pensão"
    assert c.trecho == "1.02.01.10.06 Gastos antecipados com plano de pensão 9.326 9.328"
    assert eb.normalizar(c.trecho) in eb.normalizar(pags[0].texto)
    assert (c.valor, c.anterior) == (eb.br_para_int("9.326"), eb.br_para_int("9.328"))
    assert [a.id for a in avisos] == ["A05"]


def test_parser_continuacao_apos_valores():
    (contas, avisos), _ = _parse(["2.01.05 Outras 10 20", "Obrigações"], tipo="Passivo")
    assert contas[0].descricao == "Outras Obrigações"
    assert contas[0].trecho == "2.01.05 Outras 10 20"
    assert [a.id for a in avisos] == ["A05"]


def test_parser_quebra_entre_paginas():
    (contas, avisos), _ = _parse(["1 Ativo Total 10 10", "1.01 Ativo Circulante muito"],
                                 ["longo 10 10", "1.02 Ativo Não Circulante 0 0"])
    c = [x for x in contas if x.codigo == "1.01"][0]
    assert c.pagina == 2 and c.trecho == "longo 10 10" and c.descricao == "Ativo Circulante muito longo"
    assert any(a.id == "A05" and "quebrada entre as págs. 1 e 2" in a.mensagem for a in avisos)


@pytest.mark.parametrize("corpo, msg", [
    (["1.01 Ativo Circulante", "1.02 Ativo Não Circulante 1 1"], "sem valores antes da conta seguinte"),
    (["1 Ativo Total 1 1", "1.01 Ativo Circulante"], "sem valores no fim do bloco"),
    (["1.01 Ativo Circulante", "texto 12 com dígito"], "linha não reconhecida"),
])
def test_parser_erros(corpo, msg):
    with pytest.raises(eb.ErroExtracao, match=msg):
        _parse(corpo)


@pytest.mark.parametrize("escala", ["Reais", "Reais Milhões"])
def test_ler_cabecalho_escala(escala):
    with pytest.raises(eb.ErroExtracao, match="não suportada"):
        eb.ler_cabecalho(pagina_bp("Consolidadas", "Ativo", [], escala=escala), 1)


def test_ler_cabecalho_sem_datas():
    with pytest.raises(eb.ErroExtracao, match="linha de datas"):
        eb.ler_cabecalho(pagina_bp("Consolidadas", "Ativo", [], datas="Conta Atual Anterior"), 1)


def test_ler_cabecalho_ok():
    cab = eb.ler_cabecalho(pagina_bp("Consolidadas", "Ativo", []), 1)
    assert (cab.escala, cab.data_atual, cab.data_anterior, cab.linha_datas) == \
        ("Reais Mil", "30/09/2026", "31/12/2025", 3)


def test_validar_balanco_consistente():
    res = balanco_sintetico()
    assert all(v.ok for v in res.validacoes if v.severidade == "erro")
    assert res.aprovado


def test_validar_altera_1_01():
    ativo = ["1 Ativo Total 100 90", "1.01 Ativo Circulante 41 30", "1.02 Ativo Não Circulante 60 60"]
    res = balanco_sintetico(ativo=ativo)
    assert falhas(res, "V05") and not falhas(res, "V04")
    assert {v.coluna for v in falhas(res, "V05")} == {"atual"}
    assert not res.aprovado


def test_validar_altera_1():
    ativo = ["1 Ativo Total 101 90"] + ATIVO_MIN[1:]
    res = balanco_sintetico(ativo=ativo)
    assert falhas(res, "V04") and falhas(res, "V05")


def test_validar_duplicado():
    res = balanco_sintetico(ativo=ATIVO_MIN + ["1.02 Ativo Não Circulante 60 60"])
    assert falhas(res, "V02")


def test_validar_filho_sem_pai():
    res = balanco_sintetico(ativo=ATIVO_MIN + ["1.02.07.01 Órfã 0 0"])
    assert falhas(res, "A02")
    assert res.aprovado


def test_validar_filhos_nao_somam():
    res = balanco_sintetico(ativo=ATIVO_MIN + ["1.01.01 Caixa 10 10", "1.01.02 Aplicações 5 5"])
    assert falhas(res, "A01")
    assert all(v.severidade == "aviso" for v in falhas(res, "A01"))
    assert res.aprovado is True


def test_validar_v03_codigo_fora_do_bloco():
    res = balanco_sintetico(ativo=ATIVO_MIN + ["2.09 Intrusa 0 0"])
    assert falhas(res, "V03")


def test_contar_ocorrencias():
    assert eb.contar_ocorrencias("0", "… 3.204.533 0 … 10 0") == 2
    assert eb.contar_ocorrencias("586", "586 1.586 586,1") == 1


def test_parse_paginas():
    b = eb.parse_paginas("26:27-28", 80)
    assert b["Ativo"].paginas == [26] and b["Passivo"].paginas == [27, 28]
    for ruim in ("27-26:1", "90:91", "26", "a:b"):
        with pytest.raises(eb.ErroExtracao):
            eb.parse_paginas(ruim, 80)


def test_montar_registros():
    ativo = ATIVO_MIN + ["1.01.04 Estoques 40 30"]
    passivo = PASSIVO_MIN + ["2.03.05 Lucros/Prejuízos Acumulados 50 50"]
    res = balanco_sintetico(ativo, passivo)
    regs = eb.montar_registros(res, "teste", "consolidado")
    chaves = ["metrica", "periodo", "unidade", "valor", "valor_como_aparece", "anterior",
              "anterior_como_aparece", "pagina", "trecho", "codigo_conta", "descricao", "codigo_pai", "nivel",
              "demonstracao", "visao", "empresa", "data_atual", "data_anterior", "ambiguo"]
    assert all(list(r) == chaves for r in regs)
    assert not any("variacao_pct" in r for r in regs)
    assert len({r["metrica"] for r in regs}) == len(regs)
    por = {r["codigo_conta"]: r for r in regs}
    assert (por["1"]["nivel"], por["1"]["codigo_pai"], por["1"]["demonstracao"]) == (1, None, "BPA")
    assert (por["1.01.04"]["nivel"], por["1.01.04"]["codigo_pai"], por["1.01.04"]["demonstracao"]) == \
        (3, "1.01", "BPA")
    assert (por["2.03.05"]["nivel"], por["2.03.05"]["codigo_pai"], por["2.03.05"]["demonstracao"]) == \
        (3, "2.03", "BPP")
    assert por["1"]["periodo"] == "30/09/2026 vs 31/12/2025"
    assert (por["1"]["data_atual"], por["1"]["data_anterior"]) == ("2026-09-30", "2025-12-31")


def test_paginas_override_gera_a07():
    pags = _cinco_paginas()
    # Ativo da controladora pedido como consolidado → A07, não erro
    blocos = {"Ativo": eb.Bloco("Ativo", [1]), "Passivo": eb.Bloco("Passivo", [4, 5])}
    res = eb.extrair_balanco(pags, "consolidado", blocos)
    assert res.localizacao == "--paginas"
    assert [a.pagina for a in res.avisos if a.id == "A07"] == [1]


# ---------------------------------------------------------------------------
# 11.2 Integração (PDFs reais)
# ---------------------------------------------------------------------------
CASOS = {
    ("gerdau_ITR_3T26", "consolidado"): {"ativo": [26], "passivo": [27, 28],
                                          "por_pagina": {26: 33, 27: 45, 28: 16}, "ap": (33, 61)},
    ("gerdau_ITR_3T26", "controladora"): {"ativo": [15], "passivo": [16, 17],
                                           "por_pagina": {15: 33, 16: 45, 17: 10}, "ap": (33, 55)},
    ("usiminas_ITR_3T26", "consolidado"): {"ativo": [12], "passivo": [13],
                                            "por_pagina": {12: 36, 13: 45}, "ap": (36, 45)},
    ("usiminas_ITR_3T26", "controladora"): {"ativo": [3], "passivo": [4],
                                             "por_pagina": {3: 35, 4: 43}, "ap": (35, 43)},
}

LINHAS_LITERAIS = {
    ("gerdau_ITR_3T26", "consolidado"): [
        (26, "1 Ativo Total 83.945.525 81.688.175"),
        (26, "1.01 Ativo Circulante 30.645.669 28.605.081"),
        (26, "1.02 Ativo Não Circulante 53.299.856 53.083.094"),
        (26, "1.01.01 Caixa e Equivalentes de Caixa 5.695.892 5.929.170"),
        (26, "1.01.04 Estoques 16.490.132 14.731.081"),
        (26, "1.02.03.02.01 Arrendamento mercantil - direito de uso de ativos 1.612.352 1.271.462"),
        (27, "2 Passivo Total 83.945.525 81.688.175"),
        (27, "2.01 Passivo Circulante 10.573.919 9.887.420"),
        (27, "2.02 Passivo Não Circulante 18.523.362 18.002.266"),
        (27, "2.01.04 Empréstimos e Financiamentos 554.745 941.904"),
        (27, "2.02.01 Empréstimos e Financiamentos 13.174.481 13.240.247"),
        (27, "2.01.05.02.06 Beneficios a empregados 586 594"),
        (28, "2.03 Patrimônio Líquido Consolidado 54.848.244 53.798.489"),
        (28, "2.03.02 Reservas de Capital -395.736 -508.470"),
        (28, "2.03.05 Lucros/Prejuízos Acumulados 3.204.533 0"),
    ],
    ("gerdau_ITR_3T26", "controladora"): [
        (15, "1 Ativo Total 61.544.961 60.465.956"),
        (16, "2 Passivo Total 61.544.961 60.465.956"),
        (16, "2.03 Patrimônio Líquido 54.655.020 53.585.393"),
    ],
    ("usiminas_ITR_3T26", "consolidado"): [
        (12, "1 Ativo Total 34.836.026 35.684.766"),
        (12, "1.01 Ativo Circulante 16.594.884 16.801.273"),
        (12, "1.02 Ativo Não Circulante 18.241.142 18.883.493"),
        (12, "1.01.01 Caixa e Equivalentes de Caixa 4.071.514 5.141.617"),
        (12, "1.01.08.03.05 Instrumentos financeiros 8.331 0"),
        (13, "2 Passivo Total 34.836.026 35.684.766"),
        (13, "2.01 Passivo Circulante 3.212.685 4.078.513"),
        (13, "2.02 Passivo Não Circulante 7.652.715 7.904.872"),
        (13, "2.01.04 Empréstimos e Financiamentos 127.408 184.291"),
        (13, "2.02.01 Empréstimos e Financiamentos 6.053.758 6.205.848"),
        (13, "2.01.05.02.09 Títulos a pagar - Forfaiting 0 570.111"),
        (13, "2.03 Patrimônio Líquido Consolidado 23.970.626 23.701.381"),
        (13, "2.03.06 Ajustes de Avaliação Patrimonial -1.261.596 -113.628"),
    ],
    ("usiminas_ITR_3T26", "controladora"): [
        (3, "1 Ativo Total 30.968.623 31.624.842"),
        (4, "2 Passivo Total 30.968.623 31.624.842"),
        (4, "2.03 Patrimônio Líquido 21.054.251 20.813.879"),
    ],
}


def _gerar_textos(pdf: Path, destino: Path) -> None:
    import pdfplumber
    destino.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(pdf) as doc:
        for n, pagina in enumerate(doc.pages, start=1):
            (destino / f"pagina_{n:02d}.txt").write_text(pagina.extract_text() or "", encoding="utf-8")


@pytest.fixture(scope="session")
def textos(tmp_path_factory):
    cache: dict[str, Path] = {}

    def obter(stem: str) -> Path:
        pdf = ITRS / f"{stem}.pdf"
        if not pdf.exists():
            pytest.skip(f"PDF ausente: {pdf}")
        if stem not in cache:
            pasta = RAIZ / "saida" / stem
            n = eb.contar_paginas_pdf(pdf)
            if not eb._textos_completos(pasta, n):
                pasta = tmp_path_factory.mktemp("textos") / stem
                _gerar_textos(pdf, pasta)
            cache[stem] = pasta
        return cache[stem]
    return obter


@pytest.fixture(scope="session")
def resultados(textos):
    cache = {}

    def obter(stem: str, visao: str) -> tuple[eb.Resultado, Path]:
        if (stem, visao) not in cache:
            pasta = textos(stem)
            n = eb.contar_paginas_pdf(ITRS / f"{stem}.pdf")
            cache[(stem, visao)] = (eb.extrair_balanco(eb.carregar_textos(pasta, n), visao, stem=stem), pasta)
        return cache[(stem, visao)]
    return obter


PARAMS = list(CASOS)


@pytest.mark.parametrize("stem, visao", PARAMS)
def test_paginas_localizadas(resultados, stem, visao):
    res, _ = resultados(stem, visao)
    esp = CASOS[(stem, visao)]
    assert res.blocos["Ativo"].paginas == esp["ativo"]
    assert res.blocos["Passivo"].paginas == esp["passivo"]


@pytest.mark.parametrize("stem, visao", PARAMS)
def test_contagens(resultados, stem, visao):
    res, _ = resultados(stem, visao)
    esp = CASOS[(stem, visao)]
    por_pagina: dict[int, int] = {}
    for c in res.contas:
        por_pagina[c.pagina] = por_pagina.get(c.pagina, 0) + 1
    assert por_pagina == esp["por_pagina"]
    n_ativo = sum(1 for c in res.contas if c.tipo == "Ativo")
    assert (n_ativo, len(res.contas) - n_ativo) == esp["ap"]
    assert len({c.codigo for c in res.contas}) == len(res.contas)


@pytest.mark.parametrize("stem, visao", PARAMS)
def test_linhas_literais(resultados, stem, visao):
    res, _ = resultados(stem, visao)
    for pagina, linha in LINHAS_LITERAIS[(stem, visao)]:
        m = eb.RE_CONTA.match(linha)
        achados = [c for c in res.contas if c.trecho == linha and c.pagina == pagina]
        assert len(achados) == 1, linha
        c = achados[0]
        assert c.valor == eb.br_para_int(m["atual"]) and c.anterior == eb.br_para_int(m["anterior"])


@pytest.mark.parametrize("stem, visao", PARAMS)
def test_validacoes_reais(resultados, stem, visao):
    res, _ = resultados(stem, visao)
    for vid in ("V01", "V02", "V03", "V04", "V05", "V06", "V07", "V08"):
        vs = [v for v in res.validacoes if v.id == vid]
        assert vs and all(v.ok for v in vs), vid
    assert not falhas(res, "A01")
    assert not [a for a in res.avisos if a.id == "A06"]
    assert res.aprovado is True


@pytest.mark.parametrize("stem, visao", PARAMS)
def test_verificador_aprova_todos(resultados, stem, visao):
    res, pasta = resultados(stem, visao)
    for r in eb.montar_registros(res, stem.split("_")[0], visao):
        assert vn.checar(r, pasta) == [], r["metrica"]


def _cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "src/extrair_balanco.py", *map(str, args)],
                          cwd=RAIZ, capture_output=True, text=True)


@pytest.mark.parametrize("stem", ["gerdau_ITR_3T26", "usiminas_ITR_3T26"])
def test_cli_ambas_e_verificador(textos, tmp_path, stem):
    pasta = textos(stem)
    empresa = stem.split("_")[0]
    pdf = ITRS / f"{stem}.pdf"
    proc = _cli(pdf, "--textos", pasta, "--saida", tmp_path, "--visao", "ambas", "--csv")
    assert proc.returncode == 0, proc.stderr
    nomes = [f"balanco_{empresa}", f"balanco_{empresa}_controladora"]
    for nome in nomes:
        for ext in (".json", ".meta.json", ".csv"):
            assert (tmp_path / f"{nome}{ext}").exists(), nome + ext
    cons = json.loads((tmp_path / f"{nomes[0]}.json").read_text(encoding="utf-8"))
    ctrl = json.loads((tmp_path / f"{nomes[1]}.json").read_text(encoding="utf-8"))
    assert {r["visao"] for r in cons} == {"consolidado"}
    assert {r["visao"] for r in ctrl} == {"controladora"}
    assert not {r["pagina"] for r in cons} & {r["pagina"] for r in ctrl}
    meta = json.loads((tmp_path / f"{nomes[0]}.meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "aprovado" and meta["n_contas"]["total"] == len(cons)

    for nome in nomes:
        v = subprocess.run([sys.executable, "src/verificar_numeros.py", str(pasta), str(tmp_path / f"{nome}.json")],
                           cwd=RAIZ, capture_output=True, text=True)
        assert v.returncode == 0 and "[ERRO]" not in v.stdout, v.stdout[-2000:]


def test_determinismo(textos, tmp_path):
    pasta = textos("gerdau_ITR_3T26")
    pdf = ITRS / "gerdau_ITR_3T26.pdf"
    bytes_ = []
    for i in range(2):
        out = tmp_path / str(i)
        assert _cli(pdf, "--textos", pasta, "--saida", out).returncode == 0
        bytes_.append((out / "balanco_gerdau.json").read_bytes())
    assert bytes_[0] == bytes_[1]


def _copiar_textos(origem: Path, destino: Path) -> Path:
    destino.mkdir(parents=True)
    for f in origem.glob("pagina_*.txt"):
        shutil.copy(f, destino / f.name)
    return destino


def test_negativo_um_digito(textos, tmp_path):
    copia = _copiar_textos(textos("gerdau_ITR_3T26"), tmp_path / "textos")
    p26 = copia / "pagina_26.txt"
    original = p26.read_text(encoding="utf-8")
    assert "1 Ativo Total 83.945.525" in original
    p26.write_text(original.replace("1 Ativo Total 83.945.525", "1 Ativo Total 83.945.526", 1), encoding="utf-8")
    saida = tmp_path / "out"
    proc = _cli(ITRS / "gerdau_ITR_3T26.pdf", "--textos", copia, "--saida", saida)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    meta = json.loads((saida / "balanco_gerdau.meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "reprovado"
    falhou = {(v["id"], v["coluna"]) for v in meta["validacoes"] if not v["ok"] and v["severidade"] == "erro"}
    assert {("V04", "atual"), ("V05", "atual")} <= falhou
    assert not (saida / "balanco_gerdau.json").exists()


def test_negativo_titulo(textos, tmp_path):
    copia = _copiar_textos(textos("usiminas_ITR_3T26"), tmp_path / "textos")
    p13 = copia / "pagina_13.txt"
    texto = p13.read_text(encoding="utf-8")
    assert "DFs Consolidadas / Balanço Patrimonial Passivo" in texto
    p13.write_text(texto.replace("DFs Consolidadas / Balanço Patrimonial Passivo", "DFs Consolidadas / Outro"),
                   encoding="utf-8")
    saida = tmp_path / "out"
    proc = _cli(ITRS / "usiminas_ITR_3T26.pdf", "--textos", copia, "--saida", saida)
    assert proc.returncode == 2
    assert "não encontrado" in proc.stderr
    assert not saida.exists() or not any(saida.iterdir())


def test_paginas_override_real(textos, tmp_path):
    pasta = textos("gerdau_ITR_3T26")
    proc = _cli(ITRS / "gerdau_ITR_3T26.pdf", "--textos", pasta, "--saida", tmp_path, "--paginas", "26:27-28")
    assert proc.returncode == 0, proc.stderr
    meta = json.loads((tmp_path / "balanco_gerdau.meta.json").read_text(encoding="utf-8"))
    assert meta["localizacao"] == "--paginas" and meta["paginas"] == {"ativo": [26], "passivo": [27, 28]}


def test_cli_restricoes(tmp_path):
    pdfs = [ITRS / "gerdau_ITR_3T26.pdf", ITRS / "usiminas_ITR_3T26.pdf"]
    assert _cli(*pdfs, "--empresa", "x").returncode == 2
    assert _cli(pdfs[0], "--paginas", "26:27", "--visao", "ambas").returncode == 2
    assert _cli(pdfs[0], "--empresa", "Nome Com Espaço").returncode == 2
    proc = _cli(tmp_path / "nao_existe.pdf", "--saida", tmp_path)
    assert proc.returncode == 2 and "PDF não encontrado" in proc.stderr


@pytest.mark.parametrize("stem", ["gerdau_ITR_3T26", "usiminas_ITR_3T26"])
def test_desempenho(textos, tmp_path, stem):
    pasta = textos(stem)
    t0 = time.perf_counter()
    codigo = eb.processar(ITRS / f"{stem}.pdf", "consolidado", stem.split("_")[0], tmp_path, pasta, None, False)
    dt = time.perf_counter() - t0
    assert codigo == 0
    assert dt < 10, f"{stem}: {dt:.1f}s"
