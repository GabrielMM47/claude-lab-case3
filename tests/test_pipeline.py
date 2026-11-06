"""Testes do pipeline "um comando" (CASE-07).

Empresas FICTÍCIAS (`empresa_c`, `empresa_d`), montadas num diretório temporário com
--raiz: o código do pipeline não sabe nada delas (critério "terceira empresa sem alterar
o código"). Comparativo e apresentação são stubs mínimos com as CLIs do contrato, até o
CASE-05/06 entrarem no main.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pipeline  # noqa: E402
from verificar_numeros import br_para_float  # noqa: E402

TRI = "3T26"

PAGINA_ITR = """DFs Consolidadas / Demonstração do Resultado
(Reais Mil)
Descrição da Conta 01/07/2026 à 30/09/2026
Receita de Venda de Bens e/ou Serviços {receita}
Lucro/Prejuízo Consolidado do Período {lucro}
EBITDA ajustado {ebitda}
Vendas de aço (mil t) {volume}
"""

PAGINA_APRES = """Destaques do trimestre
Estratégia: foco em produtos de maior valor agregado e redução de custos.
"""

STUB_COMPARAR = '''import argparse, json
from pathlib import Path
ap = argparse.ArgumentParser()
for opt in ("--a", "--b", "--tri", "--metricas", "--saida"):
    ap.add_argument(opt)
a = ap.parse_args()
pasta = Path(a.saida) / f"{a.a}_x_{a.b}_{a.tri}"
pasta.mkdir(parents=True, exist_ok=True)
for s in (a.a, a.b):  # consome os indicadores gerados pelo pipeline
    json.loads((Path(a.metricas) / f"{s}_{a.tri}_indicadores.json").read_text(encoding="utf-8"))
(pasta / "comparativo.json").write_text(json.dumps(
    {"periodo": a.tri, "empresas": {"a": {"slug": a.a}, "b": {"slug": a.b}}, "linhas": [],
     "verificacao": None}, indent=2), encoding="utf-8")
'''

STUB_APRESENTACAO = '''import argparse, json
from pathlib import Path
ap = argparse.ArgumentParser()
for opt in ("--comparativo", "--narrativa", "--metricas", "--saida"):
    ap.add_argument(opt)
a = ap.parse_args()
comp = json.loads((Path(a.comparativo) / "comparativo.json").read_text(encoding="utf-8"))
quali = sorted(p.name for p in Path(a.metricas).glob("*_qualitativo.json"))
destino = Path(a.saida)
destino.parent.mkdir(parents=True, exist_ok=True)
v = comp["verificacao"]
destino.write_text(f"<html>{v['ok']}/{v['total']} verificados · {v['status']} · {len(quali)} quali</html>",
                   encoding="utf-8")
'''


def fato(slug, chave, valor_txt, linha, documento="itr", unidade="R$ mil", escopo="consolidado"):
    return {"chave": chave, "metrica": chave, "empresa": slug, "documento": documento, "escopo": escopo,
            "periodo": TRI, "unidade": unidade,
            "valor": br_para_float(valor_txt),
            "valor_como_aparece": valor_txt, "pagina": 1, "trecho": linha,
            "evidencia": {"escopo": "DFs Consolidadas", "unidade": "(Reais Mil)",
                          "periodo": "01/07/2026 à 30/09/2026"}}


def montar_empresa(raiz: Path, slug: str, receita="1.000", lucro="100", ebitda="250", volume="500"):
    itr = raiz / "saida" / f"{slug}_ITR_{TRI}"
    itr.mkdir(parents=True)
    texto = PAGINA_ITR.format(receita=receita, lucro=lucro, ebitda=ebitda, volume=volume)
    (itr / "pagina_01.txt").write_text(texto, encoding="utf-8")
    apres = raiz / "saida" / f"{slug}_APRESENTACAO_{TRI}"
    apres.mkdir(parents=True)
    (apres / "pagina_01.txt").write_text(PAGINA_APRES, encoding="utf-8")

    linhas = texto.splitlines()
    met = raiz / "metricas"
    met.mkdir(exist_ok=True)
    arquivos = {
        "itr_dfs": [fato(slug, "receita_liquida", receita, linhas[3]),
                    fato(slug, "lucro_liquido", lucro, linhas[4])],
        "itr_complementar": [fato(slug, "ebitda_ajustado", ebitda, linhas[5])],
        "itr_operacional": [fato(slug, "volume_vendas", volume, linhas[6], unidade="mil t")],
        "apresentacao_qualitativo": [{"chave": "qualitativo", "metrica": "estrategia", "tema": "estrategia",
                                      "empresa": slug, "documento": "apresentacao", "resumo": "valor agregado",
                                      "pagina": 1, "trecho": PAGINA_APRES.splitlines()[1]}],
    }
    for nome, fatos in arquivos.items():
        (met / f"{slug}_{TRI}_{nome}.json").write_text(json.dumps(fatos, ensure_ascii=False, indent=2),
                                                       encoding="utf-8")


@pytest.fixture
def raiz(tmp_path):
    montar_empresa(tmp_path, "empresa_c")
    montar_empresa(tmp_path, "empresa_d", receita="2.000", lucro="(50)", ebitda="300", volume="800")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "comparar.py").write_text(STUB_COMPARAR, encoding="utf-8")
    (tmp_path / "src" / "apresentacao.py").write_text(STUB_APRESENTACAO, encoding="utf-8")
    return tmp_path


def rodar(raiz, a="empresa_c", b="empresa_d", *extra):
    return pipeline.main(["--a", a, "--b", b, "--tri", TRI, "--raiz", str(raiz), *extra])


def ler(caminho: Path):
    return json.loads(caminho.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- fluxo completo

def test_ponta_a_ponta_gera_entrega_e_relatorio(raiz, capsys):
    assert rodar(raiz) == pipeline.SAIDA_OK
    rel = ler(raiz / "saida" / "verificacao_empresa_c_x_empresa_d_3T26.json")
    assert rel["status"] == "aprovado" and rel["erro"] == 0 and rel["total"] == 10
    assert set(rel["por_arquivo"]) == {f"metricas/{s}_3T26_{n}.json" for s in ("empresa_c", "empresa_d")
                                       for n in ("itr_dfs", "itr_complementar", "itr_operacional",
                                                 "apresentacao_qualitativo")}
    # cada arquivo verificado na pasta do seu documento
    assert rel["por_arquivo"]["metricas/empresa_c_3T26_apresentacao_qualitativo.json"]["pasta"] == \
        "saida/empresa_c_APRESENTACAO_3T26"
    comp = ler(raiz / "saida" / "comparativo" / "empresa_c_x_empresa_d_3T26" / "comparativo.json")
    assert comp["verificacao"]["total"] == 10 and comp["verificacao"]["status"] == "aprovado"
    entrega = raiz / "entrega" / "apresentacao_empresa_c_x_empresa_d_3T26.html"
    assert "10/10 verificados" in entrega.read_text(encoding="utf-8")
    assert "ENTREGUE" in capsys.readouterr().out


def test_a_b_invertidos(raiz):
    assert rodar(raiz, "empresa_d", "empresa_c") == pipeline.SAIDA_OK
    rel = ler(raiz / "saida" / "verificacao_empresa_d_x_empresa_c_3T26.json")
    assert (rel["a"], rel["b"], rel["status"]) == ("empresa_d", "empresa_c", "aprovado")
    assert (raiz / "entrega" / "apresentacao_empresa_d_x_empresa_c_3T26.html").exists()


def test_idempotente_com_indicadores_antigos_presentes(raiz):
    # indicadores antigos e inválidos: não podem ser verificados nem lidos como fatos
    antigo = raiz / "metricas" / "empresa_c_3T26_indicadores.json"
    antigo.write_text('{"lixo": "de uma rodada antiga"}', encoding="utf-8")
    assert rodar(raiz) == pipeline.SAIDA_OK
    rel = ler(raiz / "saida" / "verificacao_empresa_c_x_empresa_d_3T26.json")
    assert not any("indicadores" in n for n in rel["por_arquivo"])
    assert ler(antigo)["empresa"] == "empresa_c"  # recalculado a partir dos fatos

    gerados = [raiz / "saida" / "verificacao_empresa_c_x_empresa_d_3T26.json", antigo,
               raiz / "metricas" / "empresa_d_3T26_indicadores.json",
               raiz / "entrega" / "apresentacao_empresa_c_x_empresa_d_3T26.html"]
    antes = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in gerados}
    assert rodar(raiz) == pipeline.SAIDA_OK
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in gerados} == antes


# --------------------------------------------------------------------------- bloqueios

def reprovar_receita(raiz, slug="empresa_c"):
    arq = raiz / "metricas" / f"{slug}_3T26_itr_dfs.json"
    fatos = ler(arq)
    fatos[0]["valor_como_aparece"] = "9.999"  # não está na página
    fatos[0]["valor"] = 9999.0
    arq.write_text(json.dumps(fatos, ensure_ascii=False), encoding="utf-8")


def test_fato_reprovado_bloqueia_com_mensagem_util(raiz, capsys):
    reprovar_receita(raiz)
    assert rodar(raiz) == pipeline.SAIDA_ERRO
    saida = capsys.readouterr()
    assert "metricas/empresa_c_3T26_itr_dfs.json (saida/empresa_c_ITR_3T26): 1 fato(s) com erro" in saida.out
    assert "- receita_liquida (3T26), p. 1:" in saida.out
    assert "9.999" in saida.out and "PAROU em [5/8 verificação]" in saida.err
    rel = ler(raiz / "saida" / "verificacao_empresa_c_x_empresa_d_3T26.json")
    assert rel["status"] == "bloqueado" and rel["arquivos_com_erro"] == ["metricas/empresa_c_3T26_itr_dfs.json"]
    assert not (raiz / "metricas" / "empresa_c_3T26_indicadores.json").exists()
    assert not (raiz / "entrega").exists()


def test_fato_reprovado_com_permitir_pendencias_vira_rascunho_sem_o_fato(raiz, capsys):
    reprovar_receita(raiz)
    assert rodar(raiz, "empresa_c", "empresa_d", "--permitir-pendencias") == pipeline.SAIDA_OK
    assert "RASCUNHO (não entregar)" in capsys.readouterr().out
    assert ler(raiz / "saida" / "verificacao_empresa_c_x_empresa_d_3T26.json")["status"] == "rascunho"
    ind = ler(raiz / "saida" / "rascunho" / "empresa_c_x_empresa_d_3T26" / "metricas" /
              "empresa_c_3T26_indicadores.json")
    assert ind["verificacao_status"] == "rascunho"
    insumos = [i["chave"] for x in ind["indicadores"] for i in x.get("insumos", [])]
    assert "receita_liquida" not in insumos  # fato reprovado fora dos cálculos
    assert (raiz / "saida" / "rascunho" / "empresa_c_x_empresa_d_3T26" /
            "RASCUNHO_empresa_c_x_empresa_d_3T26.html").exists()
    assert not (raiz / "entrega").exists()


def test_json_assistido_ausente_imprime_prompt_com_paginas(raiz, capsys):
    (raiz / "metricas" / "empresa_d_3T26_itr_operacional.json").unlink()
    assert rodar(raiz) == pipeline.SAIDA_ASSISTIDO
    out = capsys.readouterr().out
    assert "FALTA metricas/empresa_d_3T26_itr_operacional.json" in out
    assert "Páginas candidatas (saida/empresa_d_ITR_3T26)" in out and "- p. 1 (" in out
    salvo = raiz / "saida" / "prompts" / "empresa_d_3T26_itr_operacional.md"
    assert "empresa_d" in salvo.read_text(encoding="utf-8")
    assert not (raiz / "saida" / "verificacao_empresa_c_x_empresa_d_3T26.json").exists()


def test_prompt_usa_arquivo_de_prompts_quando_existe(raiz, capsys):
    (raiz / "prompts").mkdir()
    (raiz / "prompts" / "extracao_operacional.md").write_text(
        "Gere metricas/<slug>_<tri>_itr_operacional.json", encoding="utf-8")
    (raiz / "metricas" / "empresa_c_3T26_itr_operacional.json").unlink()
    assert rodar(raiz) == pipeline.SAIDA_ASSISTIDO
    assert "Gere metricas/empresa_c_3T26_itr_operacional.json" in capsys.readouterr().out


def test_operacional_da_apresentacao_tambem_vale(raiz):
    met = raiz / "metricas"
    (met / "empresa_c_3T26_itr_operacional.json").rename(met / "empresa_c_3T26_apresentacao_operacional.json")
    # o fato continua apontando para a página do ITR: na pasta da apresentação ele reprova
    assert rodar(raiz) == pipeline.SAIDA_ERRO


def test_itr_ausente(raiz, capsys):
    import shutil
    shutil.rmtree(raiz / "saida" / "empresa_d_ITR_3T26")
    assert rodar(raiz) == pipeline.SAIDA_INSUMO
    assert "data/itrs/empresa_d_ITR_3T26.pdf" in capsys.readouterr().err


def test_apresentacao_ausente_fica_pendente(raiz, capsys):
    import shutil
    shutil.rmtree(raiz / "saida" / "empresa_c_APRESENTACAO_3T26")
    (raiz / "metricas" / "empresa_c_3T26_apresentacao_qualitativo.json").unlink()
    assert rodar(raiz) == pipeline.SAIDA_INSUMO
    assert "data/apresentacoes/empresa_c_APRESENTACAO_3T26.pdf" in capsys.readouterr().out
    assert rodar(raiz, "empresa_c", "empresa_d", "--permitir-pendencias") == pipeline.SAIDA_OK
    rel = ler(raiz / "saida" / "verificacao_empresa_c_x_empresa_d_3T26.json")
    assert rel["status"] == "rascunho" and rel["pendencias"][0]["tipo"] == "documento_ausente"


def test_arquivo_fora_da_convencao_reprova(raiz):
    met = raiz / "metricas"
    (met / "empresa_c_3T26_release_extra.json").write_text("[]", encoding="utf-8")
    assert rodar(raiz) == pipeline.SAIDA_ERRO


def test_sem_comparar_para_depois_dos_indicadores(raiz, capsys):
    (raiz / "src" / "comparar.py").unlink()
    assert rodar(raiz) == pipeline.SAIDA_AGUARDANDO
    assert "aguardando CASE-05" in capsys.readouterr().err
    assert (raiz / "metricas" / "empresa_d_3T26_indicadores.json").exists()


def test_rascunho_nao_toca_arquivos_oficiais(raiz):
    """Indicadores/comparativo oficiais (versionados pelo CASE-04/05) ficam intactos num rascunho."""
    oficiais = {raiz / "metricas" / "empresa_c_3T26_indicadores.json": '{"oficial": "case-04"}',
                raiz / "saida" / "comparativo" / "empresa_c_x_empresa_d_3T26" / "comparativo.json": "{}",
                raiz / "entrega" / "apresentacao_empresa_c_x_empresa_d_3T26.html": "<html>oficial</html>"}
    for p, conteudo in oficiais.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(conteudo, encoding="utf-8")
    reprovar_receita(raiz)
    assert rodar(raiz, "empresa_c", "empresa_d", "--permitir-pendencias") == pipeline.SAIDA_OK
    for p, conteudo in oficiais.items():
        assert p.read_text(encoding="utf-8") == conteudo, p
    html = (raiz / "saida" / "rascunho" / "empresa_c_x_empresa_d_3T26" /
            "RASCUNHO_empresa_c_x_empresa_d_3T26.html").read_text(encoding="utf-8")
    assert "rascunho" in html and "2 quali" in html  # slides leem o qualitativo aprovado do rascunho


def test_indicadores_aprovados_saem_iguais_ao_cli_do_case04(raiz):
    import indicadores
    assert rodar(raiz) == pipeline.SAIDA_OK
    gerado = (raiz / "metricas" / "empresa_c_3T26_indicadores.json").read_bytes()
    cli = raiz / "cli.json"
    indicadores.main(["--empresa", "empresa_c", "--tri", TRI, "--metricas", str(raiz / "metricas"),
                      "--saida", str(cli)])
    assert cli.read_bytes() == gerado


def test_pdf_trocado_reextrai_e_refaz_dfs(raiz, monkeypatch, capsys):
    import types
    pdf = raiz / "data" / "itrs" / "empresa_c_ITR_3T26.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"versao 1")
    chamadas = {"extrair": [], "dfs": []}

    def extrair(caminho):
        chamadas["extrair"].append(caminho.name)
        destino = raiz / "saida" / caminho.stem
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "pagina_01.txt").write_text(caminho.read_bytes().decode(), encoding="utf-8")
        return destino

    monkeypatch.setitem(sys.modules, "extrair_release", types.SimpleNamespace(extrair=extrair, SAIDA=None))
    import dfs_cvm
    monkeypatch.setattr(dfs_cvm, "main", lambda args: chamadas["dfs"].append(args[0]) or 0)

    rodar(raiz)  # 1ª vez: pasta sem carimbo → re-extrai e grava o carimbo
    assert chamadas["extrair"] == ["empresa_c_ITR_3T26.pdf"]
    carimbo = raiz / "saida" / "empresa_c_ITR_3T26" / pipeline.CARIMBO
    assert carimbo.read_text().strip() == pipeline.sha256(pdf)

    chamadas["extrair"].clear(); chamadas["dfs"].clear()
    rodar(raiz)  # mesmo PDF: nada a refazer
    assert chamadas == {"extrair": [], "dfs": []}

    pdf.write_bytes(b"versao 2 republicada")
    capsys.readouterr()
    rodar(raiz)  # PDF trocado com o mesmo nome: re-extrai e refaz o dfs_cvm
    assert chamadas["extrair"] == ["empresa_c_ITR_3T26.pdf"] and len(chamadas["dfs"]) == 1
    assert "mudou desde a última extração" in capsys.readouterr().out
    assert (raiz / "saida" / "empresa_c_ITR_3T26" / "pagina_01.txt").read_text() == "versao 2 republicada"


def test_prompt_qualitativo_aceita_os_dois_nomes(raiz, capsys):
    (raiz / "prompts").mkdir()
    (raiz / "prompts" / "extracao_qualitativo.md").write_text("PROMPT QUALI <slug>", encoding="utf-8")
    (raiz / "metricas" / "empresa_c_3T26_apresentacao_qualitativo.json").unlink()
    assert rodar(raiz) == pipeline.SAIDA_ASSISTIDO
    assert "PROMPT QUALI empresa_c" in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--a", "Gerdau", "--b", "x"], ["--a", "x", "--b", "x"],
                                  ["--a", "x", "--b", "y", "--tri", "T326"]])
def test_argumentos_invalidos(args):
    base = {"--tri": TRI}
    argv = args + ([] if "--tri" in args else ["--tri", base["--tri"]])
    with pytest.raises(SystemExit):
        pipeline.main(argv)
