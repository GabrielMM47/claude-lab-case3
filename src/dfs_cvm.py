"""
Case 3 — CASE-02 · Parser determinístico das DFs consolidadas no formato padrão da CVM.

Lê os pagina_NN.txt gerados por src/extrair_release.py, acha as páginas
"DFs Consolidadas / Balanço Patrimonial Ativo|Passivo", "/ Demonstração do Resultado"
e "/ Demonstração do Fluxo de Caixa", lê cada linha pelo código de conta CVM e grava
os fatos do catálogo no formato do contrato (docs/TAREFAS.md, "Contrato de dados").

Nada é específico de empresa: as colunas são lidas pelas datas do cabeçalho, e as
contas sem código fixo (D&A, capex, não controladores) são achadas pela descrição
dentro do grupo certo.

Rode da raiz do repositório:
    python src/dfs_cvm.py saida/gerdau_ITR_3T26 --empresa gerdau --tri 3T26

Saídas:
    metricas/<slug>_<tri>_itr_dfs.json            fatos (lista; lida pelo verificar_numeros.py)
    metricas/cobertura/<slug>_<tri>_itr_dfs.json  chaves × períodos: presente / ausente / nao_comparavel
    metricas/manifesto/<documento_id>.json        PDF de origem: caminho, sha256, páginas usadas

Códigos de saída: 0 = ok; 1 = checagem de consistência falhou (nada é gravado);
2 = não foi possível extrair (layout não suportado ou PDF sem texto; nada é gravado).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- catálogo
# chave -> (código CVM fixo | None, tipo, demonstração). As de código variável estão em BUSCA_POR_DESCRICAO.
CATALOGO: dict[str, tuple[str | None, str, str]] = {
    "receita_liquida": ("3.01", "fluxo", "DRE"),
    "cpv": ("3.02", "fluxo", "DRE"),
    "lucro_bruto": ("3.03", "fluxo", "DRE"),
    "despesas_receitas_operacionais": ("3.04", "fluxo", "DRE"),
    "ebit": ("3.05", "fluxo", "DRE"),
    "resultado_financeiro": ("3.06", "fluxo", "DRE"),
    "lair": ("3.07", "fluxo", "DRE"),
    "ir_csll": ("3.08", "fluxo", "DRE"),
    "lucro_liquido": ("3.11", "fluxo", "DRE"),
    "lucro_liquido_controladores": ("3.11.01", "fluxo", "DRE"),
    "ativo_total": ("1", "saldo", "BP"),
    "passivo_total": ("2", "saldo", "BP"),
    "caixa_equivalentes": ("1.01.01", "saldo", "BP"),
    "aplicacoes_financeiras": ("1.01.02", "saldo", "BP"),
    "emprestimos_cp": ("2.01.04", "saldo", "BP"),
    "emprestimos_lp": ("2.02.01", "saldo", "BP"),
    "pl_total": ("2.03", "saldo", "BP"),
    "pl_nao_controladores": (None, "saldo", "BP"),
    "depreciacao_amortizacao": (None, "fluxo", "DFC"),
    "fco": ("6.01", "fluxo", "DFC"),
    "capex": (None, "fluxo", "DFC"),
}

# chave -> (prefixo do grupo, regex que a descrição precisa casar, regex que NÃO pode casar)
BUSCA_POR_DESCRICAO: dict[str, tuple[str, re.Pattern, re.Pattern | None]] = {
    "pl_nao_controladores": ("2.03.", re.compile(r"n[ãa]o\s+controlador", re.I), None),
    "depreciacao_amortizacao": ("6.01.01.", re.compile(r"deprecia", re.I), None),
    "capex": ("6.02.", re.compile(r"(adi[çc][õo]es|compras?|aquisi[çc][ãa]o).*imobilizado", re.I),
              re.compile(r"venda|aliena|recebi", re.I)),
}

# --------------------------------------------------------------------------- regex de layout
RE_TITULO = re.compile(r"^DFs (?P<visao>Consolidadas|Individuais) / (?P<titulo>.+?)\s*$")
TITULOS = {  # título exato (ou prefixo, p/ DFC) -> demonstração
    "Balanço Patrimonial Ativo": "BP",
    "Balanço Patrimonial Passivo": "BP",
    "Demonstração do Resultado": "DRE",
}
PREFIXO_DFC = "Demonstração do Fluxo de Caixa"
RE_ESCALA = re.compile(r"^\((?P<escala>Reais(?: Mil| Milhões)?)\)\s*$")
UNIDADES = {"Reais": "R$", "Reais Mil": "R$ mil", "Reais Milhões": "R$ milhões"}
RE_INTERVALO = re.compile(r"(\d{2}/\d{2}/\d{4})\s+à\s+(\d{2}/\d{2}/\d{4})")
RE_DATA = re.compile(r"\d{2}/\d{2}/\d{4}")
RE_CODIGO = re.compile(r"^(?P<codigo>\d(?:\.\d{2})*)\s+(?P<resto>\S.*)$")
RE_VALOR = re.compile(r"^(?:-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|\(\d{1,3}(?:\.\d{3})*(?:,\d+)?\))$")


class ErroExtracao(Exception):
    """Layout não suportado ou PDF sem texto: pede etapa assistida."""


# --------------------------------------------------------------------------- estruturas
@dataclass
class Coluna:
    rotulo: str          # 3T26, 9M26, 4T25...
    inicio: date | None  # None para saldo
    fim: date
    cabecalho: str       # literal do cabeçalho ("01/07/2026 à 30/09/2026" ou "30/09/2026")


@dataclass
class Linha:
    codigo: str
    descricao: str
    tokens: list[str]    # valores como aparecem, na ordem das colunas
    trecho: str          # linha(s) literais da página
    pagina: int
    demonstracao: str
    titulo: str
    escala: str
    colunas: list[Coluna]
    cabecalho: str = ""  # cabeçalho literal das colunas (linhas entre a escala e a 1ª conta)


@dataclass
class Extracao:
    linhas: list[Linha] = field(default_factory=list)
    paginas: dict[str, list[int]] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- utilidades
def br_para_float(s: str) -> float:
    s = s.strip()
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("()-").replace(".", "").replace(",", ".")
    return -float(s) if neg else float(s)


def _data(s: str) -> date:
    return datetime.strptime(s, "%d/%m/%Y").date()


def rotulo_saldo(d: date) -> str:
    if (d.month, d.day) not in {(3, 31), (6, 30), (9, 30), (12, 31)}:
        raise ErroExtracao(f"data de saldo {d:%d/%m/%Y} não é fim de trimestre")
    return f"{d.month // 3}T{d.year % 100:02d}"


def rotulo_fluxo(ini: date, fim: date) -> str:
    meses = (fim.year - ini.year) * 12 + fim.month - ini.month + 1
    if ini.day != 1 or fim.month % 3 or meses % 3:
        raise ErroExtracao(f"período {ini:%d/%m/%Y}–{fim:%d/%m/%Y} não é trimestre nem acumulado do ano")
    if meses == 3:
        return f"{fim.month // 3}T{fim.year % 100:02d}"
    if ini.month == 1:
        return f"{meses}M{fim.year % 100:02d}"
    raise ErroExtracao(f"período {ini:%d/%m/%Y}–{fim:%d/%m/%Y} não reconhecido")


def fim_do_tri(tri: str) -> date:
    m = re.fullmatch(r"([1-4])T(\d{2})", tri)
    if not m:
        raise SystemExit(f"--tri inválido: {tri!r} (use, por ex., 3T26)")
    q, a = int(m[1]), 2000 + int(m[2])
    return date(a, q * 3, 31 if q in (1, 4) else 30)


def ler_colunas(cabecalho: list[str]) -> list[Coluna]:
    """Colunas na ordem em que as datas aparecem no cabeçalho (não por posição fixa)."""
    texto = "\n".join(cabecalho)
    intervalos = RE_INTERVALO.findall(texto)
    if intervalos:
        return [Coluna(rotulo_fluxo(_data(i), _data(f)), _data(i), _data(f), f"{i} à {f}")
                for i, f in intervalos]
    return [Coluna(rotulo_saldo(_data(d)), None, _data(d), d) for d in RE_DATA.findall(texto)]


def separar_valores(resto: str, n: int) -> tuple[str, list[str]] | None:
    """'Descrição 1.234 -5.678' -> ('Descrição', ['1.234', '-5.678']) se os n últimos tokens forem valores."""
    partes = resto.split()
    if len(partes) <= n or not all(RE_VALOR.match(t) for t in partes[-n:]):
        return None
    return " ".join(partes[:-n]), partes[-n:]


# --------------------------------------------------------------------------- leitura das páginas
def ler_pagina(texto: str, n_pagina: int, ext: Extracao) -> None:
    linhas = texto.splitlines()
    i_titulo = next((i for i, l in enumerate(linhas) if RE_TITULO.match(l.strip())), None)
    if i_titulo is None:
        return
    m = RE_TITULO.match(linhas[i_titulo].strip())
    titulo = m["titulo"]
    demo = TITULOS.get(titulo) or ("DFC" if titulo.startswith(PREFIXO_DFC) else None)
    if m["visao"] != "Consolidadas" or demo is None:
        return

    i_escala = next((i for i in range(i_titulo + 1, min(i_titulo + 4, len(linhas)))
                     if RE_ESCALA.match(linhas[i].strip())), None)
    i_primeira = next((i for i in range(i_titulo + 1, len(linhas)) if RE_CODIGO.match(linhas[i].strip())), None)
    if i_primeira is None:  # página de índice/sumário: título sem linhas de conta
        return
    if i_escala is None:
        raise ErroExtracao(f"p.{n_pagina}: '{titulo}' sem linha de escala '(Reais Mil)' logo abaixo do título")
    escala = RE_ESCALA.match(linhas[i_escala].strip())["escala"]
    colunas = ler_colunas(linhas[i_escala + 1:i_primeira])
    cabecalho = " ".join(l.strip() for l in linhas[i_escala + 1:i_primeira])
    if not colunas:
        raise ErroExtracao(f"p.{n_pagina}: '{titulo}' sem datas no cabeçalho das colunas")

    ext.paginas.setdefault(demo, []).append(n_pagina)
    n = len(colunas)
    i = i_primeira
    while i < len(linhas):
        bruto = linhas[i].strip()
        mc = RE_CODIGO.match(bruto)
        if not mc:
            i += 1
            continue
        partes, j = [bruto], i
        sep = separar_valores(mc["resto"], n)
        # descrição quebrada em mais de uma linha: valores só aparecem na linha seguinte
        while sep is None and j + 1 < len(linhas) and not RE_CODIGO.match(linhas[j + 1].strip()) \
                and len(partes) < 3:
            j += 1
            partes.append(linhas[j].strip())
            sep = separar_valores(" ".join(partes)[len(mc["codigo"]):].strip(), n)
        if sep is None:  # conta sem valores (ex.: 3.99 Lucro por Ação) ou rodapé
            i += 1
            continue
        descricao, tokens = sep
        ext.linhas.append(Linha(mc["codigo"], descricao, tokens, " ".join(partes), n_pagina,
                                demo, titulo, escala, colunas, cabecalho))
        i = j + 1


def extrair(pasta: Path) -> Extracao:
    arquivos = sorted(pasta.glob("pagina_*.txt"))
    if not arquivos:
        raise ErroExtracao(f"{pasta} não tem pagina_NN.txt: rode antes "
                           f"python src/extrair_release.py data/itrs/{pasta.name}.pdf")
    ext = Extracao()
    vazias = 0
    for arq in arquivos:
        texto = arq.read_text(encoding="utf-8")
        vazias += not texto.strip()
        ler_pagina(texto, int(arq.stem.split("_")[1]), ext)
    if not ext.linhas:
        dica = (f"{vazias} de {len(arquivos)} páginas sem texto: o PDF parece escaneado (sem camada de texto). "
                "Use a etapa assistida (Claude lendo as páginas como imagem) ou um OCR."
                if vazias > len(arquivos) / 2 else
                "Nenhuma página 'DFs Consolidadas / ...' com linhas de conta: layout fora do padrão CVM. "
                "Use a etapa assistida e registre o caso em docs/registro/.")
        raise ErroExtracao(dica)
    for demo in ("BP", "DRE", "DFC"):
        if demo not in ext.paginas:
            ext.avisos.append(f"demonstração {demo} consolidada não encontrada")
    return ext


# --------------------------------------------------------------------------- mapeamento -> fatos
def localizar(ext: Extracao) -> dict[str, Linha]:
    por_codigo: dict[tuple[str, str], Linha] = {}
    for l in ext.linhas:
        por_codigo.setdefault((l.demonstracao, l.codigo), l)
    achadas: dict[str, Linha] = {}
    for chave, (codigo, _tipo, demo) in CATALOGO.items():
        if codigo is not None:
            if (demo, codigo) in por_codigo:
                achadas[chave] = por_codigo[(demo, codigo)]
            continue
        prefixo, casa, exclui = BUSCA_POR_DESCRICAO[chave]
        candidatas = [l for l in ext.linhas if l.demonstracao == demo and l.codigo.startswith(prefixo)
                      and casa.search(l.descricao) and not (exclui and exclui.search(l.descricao))]
        if candidatas:
            achadas[chave] = candidatas[0]
            if len(candidatas) > 1:
                ext.avisos.append(f"{chave}: {len(candidatas)} contas candidatas "
                                  f"({', '.join(c.codigo for c in candidatas)}); usada {candidatas[0].codigo}")
    return achadas


def checar_consistencia(ext: Extracao) -> list[str]:
    """Identidades contábeis, por período. Usa todas as linhas lidas (inclusive fora do catálogo)."""
    def valores(demo: str, codigo: str) -> dict[str, float]:
        l = next((x for x in ext.linhas if x.demonstracao == demo and x.codigo == codigo), None)
        return {} if l is None else {c.rotulo: br_para_float(t) for c, t in zip(l.colunas, l.tokens)}

    erros = []
    regras = [
        ("lucro_bruto = receita_liquida + cpv", "DRE", "3.03", ["3.01", "3.02"]),
        ("ativo_total = passivo_total", "BP", "1", ["2"]),
        ("lucro_liquido = controladores + não controladores", "DRE", "3.11", ["3.11.01", "3.11.02"]),
    ]
    for nome, demo, total, partes in regras:
        vt, vps = valores(demo, total), [valores(demo, p) for p in partes]
        if not vt or not all(vps):
            erros.append(f"{nome}: contas ausentes, não deu para checar")
            continue
        for per, v in vt.items():
            soma = sum(vp.get(per, float("nan")) for vp in vps)
            if abs(v - soma) > 1:  # tolerância de arredondamento: R$ 1 mil
                erros.append(f"{nome} [{per}]: {v:,.0f} ≠ {soma:,.0f}")
    return erros


def periodos_esperados(tri: str) -> dict[str, list[str]]:
    q, a = int(tri[0]), int(tri[2:])
    tri_ant, acum, acum_ant = f"{q}T{a - 1:02d}", f"{q * 3}M{a:02d}", f"{q * 3}M{a - 1:02d}"
    fluxo_tri = [tri, tri_ant]
    fluxo_acum = [] if q == 1 else [acum, acum_ant]   # no 1T o acumulado é o próprio trimestre
    return {"DRE": fluxo_tri + fluxo_acum, "DFC": fluxo_acum or fluxo_tri, "DFC_tri": [] if q == 1 else fluxo_tri,
            "BP": [tri, "4T" + f"{a - 1:02d}"]}


def montar(ext: Extracao, slug: str, tri: str, documento_id: str) -> tuple[list[dict], list[dict]]:
    achadas = localizar(ext)
    esperados = periodos_esperados(tri)
    fatos, cobertura = [], []
    for chave, (_cod, tipo, demo) in CATALOGO.items():
        l = achadas.get(chave)
        presentes = set()
        if l is not None:
            for k, (col, tok) in enumerate(zip(l.colunas, l.tokens), start=1):
                presentes.add(col.rotulo)
                fatos.append({
                    "chave": chave,
                    "metrica": l.descricao,
                    "empresa": slug,
                    "documento": "itr",
                    "documento_id": documento_id,
                    "data_documento": fim_do_tri(tri).isoformat(),
                    "escopo": "consolidado",
                    "demonstracao": demo,
                    "tipo": tipo,
                    "periodo": col.rotulo,
                    "periodo_inicio": col.inicio.isoformat() if col.inicio else None,
                    "periodo_fim": col.fim.isoformat(),
                    "unidade": UNIDADES[l.escala],
                    "moeda": "BRL",
                    "criterio": "contabil",
                    "valor": br_para_float(tok),
                    "valor_como_aparece": tok,
                    "pagina": l.pagina,
                    "trecho": l.trecho,
                    "codigo_cvm": l.codigo,
                    "evidencia": {
                        "escopo": f"DFs Consolidadas / {l.titulo}",
                        "unidade": f"({l.escala})",
                        "periodo": col.cabecalho,
                        "coluna": k,
                        "n_colunas": len(l.colunas),
                        "cabecalho_colunas": l.cabecalho,
                    },
                })
        for per in esperados[demo]:
            if per not in presentes:
                cobertura.append({"chave": chave, "periodo": per, "status": "ausente",
                                  "motivo": "conta não encontrada nas DFs consolidadas" if l is None
                                  else "coluna do período não divulgada"})
            else:
                cobertura.append({"chave": chave, "periodo": per, "status": "presente",
                                  "pagina": l.pagina, "codigo_cvm": l.codigo})
        if demo == "DFC":
            for per in esperados["DFC_tri"]:
                cobertura.append({"chave": chave, "periodo": per, "status": "nao_comparavel",
                                  "motivo": "a DFC do ITR só traz o acumulado do ano; o trimestral exigiria "
                                            "o acumulado do trimestre anterior (outro documento)"})
    return fatos, cobertura


def conferir_trimestre(ext: Extracao, tri: str) -> None:
    fim = fim_do_tri(tri)
    fins = {c.fim for l in ext.linhas for c in l.colunas}
    if fim not in fins:
        raise ErroExtracao(f"nenhuma coluna termina em {fim:%d/%m/%Y}: o documento não é do {tri}? "
                           f"(datas encontradas: {', '.join(sorted(d.strftime('%d/%m/%Y') for d in fins))})")


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta_saida", type=Path, help="pasta com pagina_NN.txt (ex.: saida/gerdau_ITR_3T26)")
    ap.add_argument("--empresa", required=True, help="slug: minúsculo, sem acento (ex.: gerdau)")
    ap.add_argument("--tri", required=True, help="trimestre de referência (ex.: 3T26)")
    ap.add_argument("--pdf", type=Path, help="PDF de origem (padrão: data/itrs/<pasta>.pdf)")
    ap.add_argument("--metricas", type=Path, default=RAIZ / "metricas", help="pasta de saída")
    a = ap.parse_args(argv)

    try:
        ext = extrair(a.pasta_saida)
        conferir_trimestre(ext, a.tri)
    except ErroExtracao as e:
        print(f"[ERRO] não foi possível extrair: {e}", file=sys.stderr)
        return 2

    erros = checar_consistencia(ext)
    if erros:
        print("[ERRO] checagens de consistência falharam; nada foi gravado:", file=sys.stderr)
        for e in erros:
            print(f"  - {e}", file=sys.stderr)
        return 1

    documento_id = a.pasta_saida.name
    fatos, cobertura = montar(ext, a.empresa, a.tri, documento_id)

    pdf = a.pdf or RAIZ / "data" / "itrs" / f"{documento_id}.pdf"
    manifesto = {
        "documento_id": documento_id, "empresa": a.empresa, "tipo": "itr",
        "caminho": str(pdf.relative_to(RAIZ)) if pdf.is_relative_to(RAIZ) else str(pdf),
        "sha256": sha256(pdf) if pdf.exists() else None,
        "data_referencia": fim_do_tri(a.tri).isoformat(),
        "paginas_usadas": ext.paginas,
        "gerado_por": "src/dfs_cvm.py",
    }
    if manifesto["sha256"] is None:
        ext.avisos.append(f"PDF {pdf} não encontrado: manifesto sem sha256")

    base = f"{a.empresa}_{a.tri}_itr_dfs.json"
    (a.metricas / "cobertura").mkdir(parents=True, exist_ok=True)
    (a.metricas / "manifesto").mkdir(parents=True, exist_ok=True)
    dump = lambda obj: json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    (a.metricas / base).write_text(dump(fatos), encoding="utf-8")
    (a.metricas / "cobertura" / base).write_text(dump(
        {"documento_id": documento_id, "consistencia": "ok", "avisos": ext.avisos, "itens": cobertura}),
        encoding="utf-8")
    (a.metricas / "manifesto" / f"{documento_id}.json").write_text(dump(manifesto), encoding="utf-8")

    contagem = {s: sum(c["status"] == s for c in cobertura) for s in ("presente", "ausente", "nao_comparavel")}
    print(f"{documento_id}: {len(fatos)} fatos → metricas/{base} | cobertura {contagem} | "
          f"páginas {ext.paginas}")
    for av in ext.avisos:
        print(f"  [aviso] {av}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
