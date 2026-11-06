"""Gera as fixtures FICTÍCIAS do CASE-01 (fatos de empresa_a, empresa_b e empresa_c).

    python tests/fixtures_ficticias/gerar.py          # regrava os JSONs
    python tests/fixtures_ficticias/gerar.py --check  # código 1 se algum JSON está desatualizado

Valores redondos e claramente falsos, para nunca vazarem para a apresentação real.
- empresa_a: todas as chaves do catálogo; ITR em R$ mil, release em R$ milhões; segmentos brasil/exterior.
- empresa_b: todas as chaves; segmentos siderurgia/mineracao; prejuízo no 3T25 e efeito pontual.
- comparativo/empresa_a_x_empresa_b_3T26/: `comparativo.json` A × B (base: fixtures_comparar/
  comparativo_exemplo.json) com 2 PNGs placeholder em `graficos/`.
- empresa_c: dados INCOMPLETOS (só DRE e balanço do ITR, sem EBITDA, sem operacionais), para testar
  generalização sem nomes fixos e ausência que nunca vira zero.
`pagina` e `trecho` são inventados: não existe `saida/` para essas empresas.
"""
from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PASTA = AQUI / "metricas"
# comparativo A × B completo (CASE-05) com 2 PNGs placeholder, para o CASE-06 desenvolver sem o 05
BASE_COMPARATIVO = AQUI.parent / "fixtures_comparar" / "comparativo_exemplo.json"
PASTA_COMPARATIVO = AQUI / "comparativo" / "empresa_a_x_empresa_b_3T26"
GRAFICOS_PLACEHOLDER = (("receita_ebitda", "Receita e EBITDA ajustado, 3T26 × 3T25 (A/A) — PLACEHOLDER"),
                        ("margens", "Margens no 3T26 — PLACEHOLDER"))
TRI = "3T26"
FLUXO_TRI = ("3T26", "3T25", "2T26")
FLUXO_ACUM = ("9M26", "9M25")
SALDOS = ("3T26", "4T25")
# fator por período: 3T26 = 1, 3T25 = 0,9, 2T26 = 0,95; acumulados ≈ 3 trimestres
FATOR = {"3T26": 1.0, "3T25": 0.9, "2T26": 0.95, "9M26": 2.9, "9M25": 2.7, "4T25": 0.95}


def _br(valor: float, casas: int = 0) -> str:
    texto = f"{abs(valor):,.{casas}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"({texto})" if valor < 0 else texto


def _fato(empresa: str, documento: str, chave: str, metrica: str, periodo: str, valor: float,
          unidade: str, pagina: int, escopo: str = "consolidado", casas: int = 0, **extra) -> dict:
    como = _br(valor, casas)
    d = {"chave": chave, "metrica": metrica, "empresa": empresa, "documento": documento,
         "documento_id": f"{empresa}_{documento.upper()}_{TRI}", "escopo": escopo,
         "periodo": periodo, "unidade": unidade, "valor": valor, "valor_como_aparece": como,
         "pagina": pagina, "trecho": f"{metrica} {periodo} {como} (FICTÍCIO)"}
    d.update(extra)
    return d


# chave, nome, código CVM, valor base em R$ mil no 3T26 (empresa_a), página
DRE = [
    ("receita_liquida", "Receita de Venda de Bens e/ou Serviços", "3.01", 10_000_000, 21),
    ("cpv", "Custo dos Bens e/ou Serviços Vendidos", "3.02", -8_000_000, 21),
    ("lucro_bruto", "Resultado Bruto", "3.03", 2_000_000, 21),
    ("despesas_receitas_operacionais", "Despesas/Receitas Operacionais", "3.04", -500_000, 21),
    ("ebit", "Resultado Antes do Resultado Financeiro e dos Tributos", "3.05", 1_500_000, 21),
    ("resultado_financeiro", "Resultado Financeiro", "3.06", -300_000, 21),
    ("lair", "Resultado Antes dos Tributos sobre o Lucro", "3.07", 1_200_000, 21),
    ("ir_csll", "Imposto de Renda e Contribuição Social sobre o Lucro", "3.08", -300_000, 21),
    ("lucro_liquido", "Lucro/Prejuízo Consolidado do Período", "3.11", 900_000, 22),
    ("lucro_liquido_controladores", "Atribuído a Sócios da Empresa Controladora", "3.11.01", 850_000, 22),
]
BALANCO = [
    ("ativo_total", "Ativo Total", "1", 60_000_000, 18),
    ("passivo_total", "Passivo Total", "2", 60_000_000, 19),
    ("caixa_equivalentes", "Caixa e Equivalentes de Caixa", "1.01.01", 4_000_000, 18),
    ("aplicacoes_financeiras", "Aplicações Financeiras", "1.01.02", 1_000_000, 18),
    ("emprestimos_cp", "Empréstimos e Financiamentos", "2.01.04", 2_000_000, 19),
    ("emprestimos_lp", "Empréstimos e Financiamentos", "2.02.01", 10_000_000, 20),
    ("pl_total", "Patrimônio Líquido Consolidado", "2.03", 30_000_000, 20),
    ("pl_nao_controladores", "Participação dos Acionistas Não Controladores", "2.03.09", 1_000_000, 20),
]
DFC = [
    ("depreciacao_amortizacao", "Depreciação e amortização", "6.01.01.02", 400_000, 25),
    ("fco", "Caixa Líquido Atividades Operacionais", "6.01", 1_500_000, 25),
    ("capex", "Aquisição de imobilizado", "6.02.01", -800_000, 26),
]


def _dfs(empresa: str, escala: float, so_basico: bool = False) -> list[dict]:
    fatos = []
    for chave, nome, cod, base, pag in DRE:
        for per in FLUXO_TRI + FLUXO_ACUM:
            valor = round(base * escala * FATOR[per] / 1000) * 1000
            fatos.append(_fato(empresa, "itr", chave, nome, per, valor, "R$ mil", pag,
                               tipo="fluxo", codigo_cvm=cod, moeda="BRL"))
    for chave, nome, cod, base, pag in BALANCO:
        for per in SALDOS:
            valor = round(base * escala * FATOR[per] / 1000) * 1000
            fatos.append(_fato(empresa, "itr", chave, nome, per, valor, "R$ mil", pag,
                               tipo="saldo", codigo_cvm=cod, moeda="BRL"))
    if not so_basico:
        for chave, nome, cod, base, pag in DFC:
            for per in FLUXO_ACUM:
                valor = round(base * escala * FATOR[per] / 1000) * 1000
                fatos.append(_fato(empresa, "itr", chave, nome, per, valor, "R$ mil", pag,
                                   tipo="fluxo", codigo_cvm=cod, moeda="BRL"))
    return fatos


def _complementar(empresa: str, escala: float, efeito_pontual: bool) -> list[dict]:
    """Release em R$ milhões (de propósito: o código tem de converter)."""
    fatos = []
    for per in FLUXO_TRI + FLUXO_ACUM:
        f = FATOR[per]
        contabil = round(1_800 * escala * f, 1)
        ajustado = round(1_900 * escala * f, 1)
        if efeito_pontual and per == "3T25":
            contabil = round(contabil - 500 * escala, 1)  # impairment fictício só no 3T25
        fatos.append(_fato(empresa, "itr", "ebitda_contabil", "EBITDA (Res. CVM 156)", per, contabil,
                           "R$ milhões", 40, casas=1, tipo="fluxo", criterio="contabil", moeda="BRL"))
        fatos.append(_fato(empresa, "itr", "ebitda_ajustado", "EBITDA ajustado", per, ajustado,
                           "R$ milhões", 40, casas=1, tipo="fluxo", criterio="ajustado", moeda="BRL"))
        fatos.append(_fato(empresa, "itr", "depreciacao_amortizacao_tri", "Depreciação e amortização",
                           per, round(130 * escala * f, 1), "R$ milhões", 40, casas=1, tipo="fluxo",
                           moeda="BRL"))
    if efeito_pontual:
        fatos.append(_fato(empresa, "itr", "ajuste_ebitda", "Impairment de ativos (FICTÍCIO)", "3T25",
                           round(500 * escala, 1), "R$ milhões", 40, casas=1, tipo="fluxo", moeda="BRL"))
    for per in SALDOS:
        f = FATOR[per]
        fatos.append(_fato(empresa, "itr", "divida_bruta_reportada", "Dívida bruta", per,
                           round(12_000 * escala * f, 1), "R$ milhões", 42, casas=1, tipo="saldo", moeda="BRL"))
        fatos.append(_fato(empresa, "itr", "divida_liquida_reportada", "Dívida líquida", per,
                           round(7_000 * escala * f, 1), "R$ milhões", 42, casas=1, tipo="saldo", moeda="BRL"))
        fatos.append(_fato(empresa, "itr", "dl_ebitda_reportado", "Dívida líquida/EBITDA", per,
                           1.0, "x", 42, casas=2, tipo="saldo"))
    return fatos


def _operacional(empresa: str, escala: float, segmentos: tuple[str, str], documento: str) -> list[dict]:
    pag = 30 if documento == "itr" else 12
    fatos = []
    for per in FLUXO_TRI:
        f = FATOR[per]
        fatos.append(_fato(empresa, documento, "volume_vendas", "Vendas de aço", per,
                           round(2_000 * escala * f), "mil t", pag, tipo="fluxo"))
        fatos.append(_fato(empresa, documento, "volume_producao", "Produção de aço bruto", per,
                           round(2_100 * escala * f), "mil t", pag, tipo="fluxo"))
        if documento == "itr":
            for chave, base in (("receita_por_t_reportada", 5_000), ("custo_por_t_reportado", 4_000),
                                ("ebitda_por_t_reportado", 950)):
                fatos.append(_fato(empresa, documento, chave, chave.replace("_", " "), per,
                                   round(base * f), "R$/t", pag, tipo="fluxo"))
            fatos.append(_fato(empresa, documento, "volume_minerio", "Vendas de minério", per,
                               round(1_000 * escala * f), "mil t", pag, tipo="fluxo"))
            fatos.append(_fato(empresa, documento, "participacao_exportacao", "Exportação", per,
                               20.0, "%", pag, casas=1, tipo="fluxo"))
            for seg, peso in zip(segmentos, (0.6, 0.4)):
                esc = f"segmento:{seg}"
                fatos.append(_fato(empresa, documento, "receita_liquida", f"Receita líquida {seg}", per,
                                   round(10_000 * escala * f * peso, 1), "R$ milhões", pag + 1, escopo=esc,
                                   casas=1, tipo="fluxo", moeda="BRL"))
                fatos.append(_fato(empresa, documento, "ebitda_ajustado", f"EBITDA ajustado {seg}", per,
                                   round(1_900 * escala * f * peso, 1), "R$ milhões", pag + 1, escopo=esc,
                                   casas=1, tipo="fluxo", criterio="ajustado", moeda="BRL"))
                fatos.append(_fato(empresa, documento, "volume_vendas", f"Vendas {seg}", per,
                                   round(2_000 * escala * f * peso), "mil t", pag + 1, escopo=esc,
                                   tipo="fluxo"))
    for per in SALDOS:
        fatos.append(_fato(empresa, documento, "capacidade_instalada", "Capacidade instalada", per,
                           round(10_000 * escala), "mil t/ano", pag, tipo="saldo"))
    return fatos


def _qualitativo(empresa: str) -> list[dict]:
    return [{"chave": "qualitativo", "metrica": tema, "tema": tema, "empresa": empresa,
             "documento": "apresentacao", "documento_id": f"{empresa}_APRESENTACAO_{TRI}",
             "resumo": f"Texto fictício sobre {tema} da {empresa}.", "pagina": 5 + i,
             "trecho": f"{tema} (FICTÍCIO)"}
            for i, tema in enumerate(("perfil", "estrategia", "riscos"))]


def png_placeholder(largura: int = 160, altura: int = 90, cinza: int = 200) -> bytes:
    """PNG 16:9 cinza, sem metadados (bytes determinísticos)."""
    def bloco(tipo: bytes, dados: bytes) -> bytes:
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))
    linhas = b"".join(b"\x00" + bytes([cinza]) * largura for _ in range(altura))
    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", largura, altura, 8, 0, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(linhas, 9)) + bloco(b"IEND", b""))


def comparativo() -> dict[str, bytes]:
    """Arquivos da pasta de saída fictícia do CASE-05: comparativo.json + graficos/*.png."""
    comp = json.loads(BASE_COMPARATIVO.read_text(encoding="utf-8"))
    comp["_ficticio"] = "Empresas FICTÍCIAS; números, páginas e gráficos inventados (PNG = placeholder cinza)."
    comp["graficos"] = [{"id": gid, "arquivo": f"graficos/{gid}.png", "descricao": desc,
                         "fontes": {"a": ["ITR p.21", "ITR p.40"], "b": ["ITR p.21", "ITR p.40"]}}
                        for gid, desc in GRAFICOS_PLACEHOLDER]
    saida = {"comparativo.json": (json.dumps(comp, ensure_ascii=False, indent=2) + "\n").encode("utf-8")}
    for gid, _ in GRAFICOS_PLACEHOLDER:
        saida[f"graficos/{gid}.png"] = png_placeholder()
    return saida


def montar() -> dict[str, list[dict]]:
    arquivos: dict[str, list[dict]] = {}
    for empresa, escala, segmentos, pontual in (("empresa_a", 1.0, ("brasil", "exterior"), False),
                                                ("empresa_b", 0.5, ("siderurgia", "mineracao"), True)):
        arquivos[f"{empresa}_{TRI}_itr_dfs.json"] = _dfs(empresa, escala)
        arquivos[f"{empresa}_{TRI}_itr_complementar.json"] = _complementar(empresa, escala, pontual)
        arquivos[f"{empresa}_{TRI}_itr_operacional.json"] = _operacional(empresa, escala, segmentos, "itr")
        arquivos[f"{empresa}_{TRI}_apresentacao_operacional.json"] = _operacional(
            empresa, escala, segmentos, "apresentacao")
        arquivos[f"{empresa}_{TRI}_apresentacao_qualitativo.json"] = _qualitativo(empresa)
    # empresa_c: incompleta de propósito (sem EBITDA, DFC, operacionais nem apresentação)
    arquivos[f"empresa_c_{TRI}_itr_dfs.json"] = _dfs("empresa_c", 0.2, so_basico=True)
    return arquivos


def main(argv: list[str] | None = None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    PASTA.mkdir(exist_ok=True)
    desatualizados = []
    for nome, fatos in montar().items():
        texto = "[\n" + ",\n".join(json.dumps(f, ensure_ascii=False) for f in fatos) + "\n]\n"
        destino = PASTA / nome
        if check:
            if not destino.is_file() or destino.read_text(encoding="utf-8") != texto:
                desatualizados.append(nome)
        else:
            destino.write_text(texto, encoding="utf-8")
    for nome, dados in comparativo().items():
        destino = PASTA_COMPARATIVO / nome
        if check:
            if not destino.is_file() or destino.read_bytes() != dados:
                desatualizados.append(f"comparativo/{nome}")
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(dados)
    for nome in desatualizados:
        print(f"desatualizado: {nome} (rode: python tests/fixtures_ficticias/gerar.py)")
    return 1 if desatualizados else 0


if __name__ == "__main__":
    sys.exit(main())
