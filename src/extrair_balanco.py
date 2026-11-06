"""
Case 3 — Extrator do Balanço Patrimonial (BP) de ITR/DFP em PDF (padrão CVM).

Lê os pagina_NN.txt gerados por src/extrair_release.py, localiza as páginas do
BP (Ativo e Passivo) da visão pedida, lê cada linha pelo código de conta CVM e
grava um JSON no formato do verificar_numeros.py (valor_como_aparece, pagina,
trecho literal). Nenhum número é digitado: todos saem do texto do PDF.

Rode da raiz do repositório:
    python src/extrair_balanco.py data/itrs/*.pdf [--visao consolidado|controladora|ambas] [--csv]

Saídas em metricas/:
    balanco_<empresa>[_controladora].json       registros (lidos pelo verificador)
    balanco_<empresa>[_controladora].meta.json  metadados, validações e avisos
    balanco_<empresa>[_controladora].csv        opcional (--csv)

Códigos de saída: 0 = aprovado; 1 = alguma validação de severidade erro falhou
(só o .meta.json é gravado); 2 = não foi possível extrair (nada é gravado).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pdfplumber

VERSAO = "1.0.0"
RAIZ = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Regex (seção 5.1 do SPEC)
# ---------------------------------------------------------------------------
VAL = r"(?:-?\d{1,3}(?:\.\d{3})*|\(\d{1,3}(?:\.\d{3})*\))"

RE_TITULO = re.compile(
    r"^DFs (?P<visao>Consolidadas|Individuais) / Balanço Patrimonial (?P<tipo>Ativo|Passivo)\s*$",
    re.MULTILINE)
RE_ESCALA = re.compile(r"^\((?P<escala>Reais(?: Mil| Milhões)?)\)\s*$", re.MULTILINE)
RE_DATAS = re.compile(r"^Conta\s+(?P<atual>\d{2}/\d{2}/\d{4})\s+(?P<anterior>\d{2}/\d{2}/\d{4})\s*$")
RE_CONTA = re.compile(
    rf"^(?P<codigo>\d(?:\.\d{{2}})*)\s+(?P<descricao>\S.*?)\s+(?P<atual>{VAL})\s+(?P<anterior>{VAL})$")
RE_INICIO_CONTA = re.compile(r"^(?P<codigo>\d(?:\.\d{2})*)\s+(?P<resto>\S.*)$")
RE_FIM_VALORES = re.compile(rf"^(?P<texto>.*?)\s*(?P<atual>{VAL})\s+(?P<anterior>{VAL})$")
RE_RUIDO = re.compile(r"^(?:ITR - |PÁGINA: \d+ de \d+$|Docusign Envelope ID:)")
RE_PAGINAS = re.compile(r"^\s*[\d,\-\s]+:[\d,\-\s]+\s*$")

VISAO_ALVO = {"consolidado": "Consolidadas", "controladora": "Individuais"}
OBRIGATORIAS = {"Ativo": ("1", "1.01", "1.02"), "Passivo": ("2", "2.01", "2.02", "2.03")}
ESCALA_SUPORTADA = "Reais Mil"
LARGURA_CONTINUACAO = 80


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------
class ErroExtracao(Exception):
    """Falha que impede extrair (código de saída 2). Mensagem em português, pronta para o usuário."""


@dataclass(frozen=True)
class PaginaTexto:
    numero: int          # índice base 1
    texto: str


@dataclass(frozen=True)
class Cabecalho:
    escala: str          # "Reais Mil"
    data_atual: str      # "30/09/2026"
    data_anterior: str   # "31/12/2025"
    linha_datas: int     # índice (0-based) da linha "Conta …" em texto.splitlines()


@dataclass
class Bloco:
    tipo: str            # "Ativo" | "Passivo"
    paginas: list[int]


@dataclass
class Conta:
    codigo: str
    descricao: str
    atual_lit: str
    anterior_lit: str
    valor: int
    anterior: int
    pagina: int
    trecho: str
    tipo: str            # "Ativo" | "Passivo"


@dataclass
class Validacao:
    id: str
    descricao: str
    severidade: str      # "erro" | "aviso"
    ok: bool
    coluna: str | None = None
    esperado: int | None = None
    obtido: int | None = None
    detalhe: str = ""


@dataclass
class Aviso:
    id: str
    pagina: int | None
    mensagem: str


@dataclass
class Resultado:
    contas: list[Conta]
    blocos: dict[str, Bloco]
    cabecalho: Cabecalho
    validacoes: list[Validacao]
    avisos: list[Aviso]
    textos: dict[int, str] = field(default_factory=dict)
    localizacao: str = "automatica"

    @property
    def aprovado(self) -> bool:
        return all(v.ok for v in self.validacoes if v.severidade == "erro")


@dataclass
class _Pendente:
    codigo: str
    resto: str
    pagina: int
    linhas: list[str]


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def normalizar(t: str) -> str:
    """Cópia da normalização do verificar_numeros.py (não importar o verificador aqui)."""
    return re.sub(r"\s+", " ", t).strip().lower()


def br_para_int(lit: str) -> int:
    """'83.945.525' -> 83945525 ; '-395.736' -> -395736 ; '(1.234)' -> -1234 ; '0' -> 0."""
    if not re.fullmatch(VAL, lit):
        raise ValueError(f"literal numérico inválido: {lit!r}")
    negativo = lit.startswith("-") or lit.startswith("(")
    digitos = lit.strip("()-").replace(".", "")
    return -int(digitos) if negativo else int(digitos)


def contar_ocorrencias(literal: str, texto: str) -> int:
    t = normalizar(texto)
    return len(re.findall(rf"(?<![\d.,]){re.escape(literal.lower())}(?![\d.,])", t))


def _data_iso(d: str) -> str:
    dia, mes, ano = d.split("/")
    return f"{ano}-{mes}-{dia}"


def _chave_codigo(codigo: str) -> tuple[int, ...]:
    return tuple(int(s) for s in codigo.split("."))


def _codigo_pai(codigo: str) -> str | None:
    return codigo.rsplit(".", 1)[0] if "." in codigo else None


def _rel(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return str(p.relative_to(RAIZ))
    except ValueError:
        return str(p)


def _lista_paginas(paginas: list[int]) -> str:
    return ", ".join(str(p) for p in paginas)


# ---------------------------------------------------------------------------
# Fonte do texto (seção 4)
# ---------------------------------------------------------------------------
def contar_paginas_pdf(pdf: Path) -> int:
    with pdfplumber.open(pdf) as doc:
        return len(doc.pages)


def _textos_completos(pasta: Path, n_paginas: int) -> bool:
    return pasta.is_dir() and all((pasta / f"pagina_{n:02d}.txt").exists() for n in range(1, n_paginas + 1))


def garantir_textos(pdf: Path, textos: Path | None, n_paginas: int | None = None) -> Path:
    pdf = Path(pdf)
    if n_paginas is None:
        n_paginas = contar_paginas_pdf(pdf)
    pasta = Path(textos) if textos is not None else RAIZ / "saida" / pdf.stem
    if _textos_completos(pasta, n_paginas):
        return pasta
    if textos is not None:
        raise ErroExtracao(f"Pasta de textos incompleta: {pasta} (esperadas {n_paginas} páginas). "
                           f"Rode: python src/extrair_release.py {pdf}")
    print(f"textos de {pdf.stem} ausentes: rodando extrair_release.py (pode levar ~1 min)")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from extrair_release import extrair
    extrair(pdf)
    if not _textos_completos(pasta, n_paginas):
        raise ErroExtracao(f"Pasta de textos incompleta: {pasta} (esperadas {n_paginas} páginas). "
                           f"Rode: python src/extrair_release.py {pdf}")
    return pasta


def carregar_textos(pasta: Path, n_paginas: int) -> list[PaginaTexto]:
    return [PaginaTexto(n, (Path(pasta) / f"pagina_{n:02d}.txt").read_text(encoding="utf-8"))
            for n in range(1, n_paginas + 1)]


# ---------------------------------------------------------------------------
# Localização (seção 5.2)
# ---------------------------------------------------------------------------
def _codigos_conta(texto: str) -> list[str]:
    codigos = []
    for bruta in texto.splitlines():
        m = RE_CONTA.match(bruta.rstrip())
        if m:
            codigos.append(m["codigo"])
    return codigos


def classificar_pagina(texto: str) -> tuple[str, str] | None:
    m = RE_TITULO.search(texto)
    if not m or not _codigos_conta(texto):
        return None
    return m["visao"], m["tipo"]


def localizar_blocos(paginas: list[PaginaTexto], visao: str, stem: str | None = None) -> dict[str, Bloco]:
    alvo = VISAO_ALVO[visao]
    grupos: list[tuple[str, list[PaginaTexto]]] = []
    anterior: tuple[str, str] | None = None
    for pag in paginas:
        cls = classificar_pagina(pag.texto)
        if cls is not None and cls[0] == alvo:
            if cls == anterior and grupos and grupos[-1][1][-1].numero == pag.numero - 1:
                grupos[-1][1].append(pag)
            else:
                grupos.append((cls[1], [pag]))
        anterior = cls
    blocos: dict[str, Bloco] = {}
    for tipo, codigo_raiz in (("Ativo", "1"), ("Passivo", "2")):
        validos = [g for t, g in grupos if t == tipo and codigo_raiz in _codigos_conta(g[0].texto)]
        if not validos:
            raise ErroExtracao(f"Balanço Patrimonial {tipo} (DFs {alvo}) não encontrado"
                               + (f" em {stem}" if stem else ""))
        if len(validos) > 1:
            lista = "; ".join(_lista_paginas([p.numero for p in g]) for g in validos)
            raise ErroExtracao(f"Mais de um bloco {tipo} ({alvo})" + (f" em {stem}" if stem else "")
                               + f": págs. {lista}; use --paginas")
        blocos[tipo] = Bloco(tipo, [p.numero for p in validos[0]])
    return blocos


def parse_paginas(espec: str, n_paginas: int) -> dict[str, Bloco]:
    erro = ErroExtracao(f"--paginas inválido: '{espec}' (use ATIVO:PASSIVO, ex.: 26:27-28)")
    if not RE_PAGINAS.match(espec):
        raise erro
    blocos = {}
    for tipo, lado in zip(("Ativo", "Passivo"), espec.split(":")):
        nums: list[int] = []
        for item in lado.split(","):
            item = item.strip()
            m = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", item)
            if not m:
                raise erro
            ini = int(m[1])
            fim = int(m[2]) if m[2] else ini
            if fim < ini:
                raise erro
            for n in range(ini, fim + 1):
                if not 1 <= n <= n_paginas:
                    raise ErroExtracao(f"--paginas inválido: '{espec}' (página {n} fora de 1..{n_paginas})")
                nums.append(n)
        blocos[tipo] = Bloco(tipo, nums)
    return blocos


# ---------------------------------------------------------------------------
# Cabeçalho (seção 5.3)
# ---------------------------------------------------------------------------
def ler_cabecalho(texto: str, numero: int) -> Cabecalho:
    m = RE_ESCALA.search(texto)
    if not m:
        raise ErroExtracao(f"pág. {numero}: unidade '(Reais …)' não encontrada")
    escala = m["escala"]
    if escala != ESCALA_SUPORTADA:
        raise ErroExtracao(f"pág. {numero}: escala '{escala}' não suportada nesta versão (só Reais Mil)")
    for i, bruta in enumerate(texto.splitlines()):
        d = RE_DATAS.match(bruta.rstrip())
        if d:
            return Cabecalho(escala, d["atual"], d["anterior"], i)
    raise ErroExtracao(f"pág. {numero}: linha de datas 'Conta dd/mm/aaaa dd/mm/aaaa' não encontrada")


def _corpo(texto: str, cab: Cabecalho) -> list[str]:
    return texto.splitlines()[cab.linha_datas + 1:]


# ---------------------------------------------------------------------------
# Parser (seção 5.4)
# ---------------------------------------------------------------------------
def _nova_conta(codigo, descricao, atual_lit, anterior_lit, pagina, trecho, tipo) -> Conta:
    return Conta(codigo=codigo, descricao=descricao, atual_lit=atual_lit, anterior_lit=anterior_lit,
                 valor=br_para_int(atual_lit), anterior=br_para_int(anterior_lit),
                 pagina=pagina, trecho=trecho, tipo=tipo)


def parsear_bloco(paginas: list[PaginaTexto], cabecalhos: dict[int, Cabecalho],
                  tipo: str) -> tuple[list[Conta], list[Aviso]]:
    contas: list[Conta] = []
    avisos: list[Aviso] = []
    pendente: _Pendente | None = None
    ultima: Conta | None = None

    for pag in paginas:
        p = pag.numero
        for bruta in _corpo(pag.texto, cabecalhos[p]):
            linha = bruta.rstrip()
            if not linha.strip():
                continue
            if RE_RUIDO.match(linha):
                ultima = None
                continue
            m = RE_CONTA.match(linha)
            if m:
                if pendente is not None:
                    raise ErroExtracao(f"pág. {p}: conta {pendente.codigo} sem valores antes da conta seguinte")
                ultima = _nova_conta(m["codigo"], m["descricao"].strip(), m["atual"], m["anterior"],
                                     p, linha, tipo)
                contas.append(ultima)
                continue
            mi = RE_INICIO_CONTA.match(linha)
            if mi:
                if pendente is not None:
                    raise ErroExtracao(f"pág. {p}: conta {pendente.codigo} sem valores antes da conta seguinte")
                pendente = _Pendente(mi["codigo"], mi["resto"].strip(), p, [linha])
                ultima = None
                continue
            tem_digito = bool(re.search(r"\d", linha))
            if pendente is not None:
                mf = RE_FIM_VALORES.match(linha)
                if mf:
                    descricao = " ".join([pendente.resto, mf["texto"]]).strip()
                    if pendente.pagina == p:
                        trecho = " ".join(pendente.linhas + [linha])
                        avisos.append(Aviso("A05", p, f"conta {pendente.codigo}: descrição montada de "
                                                      f"{len(pendente.linhas) + 1} linhas"))
                    else:
                        trecho = linha
                        avisos.append(Aviso("A05", p, f"conta {pendente.codigo} quebrada entre as págs. "
                                                      f"{pendente.pagina} e {p}"))
                    ultima = _nova_conta(pendente.codigo, descricao, mf["atual"], mf["anterior"],
                                         p, trecho, tipo)
                    contas.append(ultima)
                    pendente = None
                elif not tem_digito:
                    pendente.resto = f"{pendente.resto} {linha.strip()}".strip()
                    if pendente.pagina == p:
                        pendente.linhas.append(linha)
                    else:  # descrição continua em outra página: o trecho fica só com a linha dos valores
                        pendente.linhas = [linha]
                        pendente.pagina = p
                else:
                    raise ErroExtracao(f"pág. {p}: linha não reconhecida na conta {pendente.codigo}: '{linha}'")
            elif (ultima is not None and ultima.pagina == p and not tem_digito
                  and len(linha) <= LARGURA_CONTINUACAO):
                ultima.descricao = f"{ultima.descricao} {linha.strip()}"
                avisos.append(Aviso("A05", p, f"conta {ultima.codigo}: descrição continuada na linha seguinte"))
            else:
                avisos.append(Aviso("A06", p, f"linha ignorada: '{linha[:60]}'"))
    if pendente is not None:
        raise ErroExtracao(f"conta {pendente.codigo} sem valores no fim do bloco {tipo}")
    return contas, avisos


# ---------------------------------------------------------------------------
# Validações (seção 6)
# ---------------------------------------------------------------------------
def validar(contas: list[Conta], paginas: dict[int, str], blocos: dict[str, Bloco],
            cabecalhos: dict[int, Cabecalho], visao: str | None = None) -> list[Validacao]:
    vs: list[Validacao] = []
    por_codigo: dict[str, Conta] = {}
    for c in contas:
        por_codigo.setdefault(c.codigo, c)
    colunas = (("atual", "valor"), ("anterior", "anterior"))

    # V01
    faltando = [c for tipo, cods in OBRIGATORIAS.items() for c in cods
                if not any(x.codigo == c and x.tipo == tipo for x in contas)]
    vs.append(Validacao("V01", "contas obrigatórias presentes", "erro", not faltando,
                        detalhe=("ausentes: " + ", ".join(faltando)) if faltando else ""))
    # V02
    vistos, dup = set(), []
    for c in contas:
        if c.codigo in vistos and c.codigo not in dup:
            dup.append(c.codigo)
        vistos.add(c.codigo)
    vs.append(Validacao("V02", "códigos únicos", "erro", not dup,
                        detalhe=("duplicados: " + ", ".join(dup)) if dup else ""))
    # V03
    fora = [c.codigo for c in contas if not c.codigo.startswith({"Ativo": "1", "Passivo": "2"}[c.tipo])]
    vs.append(Validacao("V03", "códigos do Ativo começam com 1 e do Passivo com 2", "erro", not fora,
                        detalhe=("fora do bloco: " + ", ".join(fora)) if fora else ""))

    # V04–V06
    equacoes = (("V04", "Ativo Total (1) = Passivo Total (2)", "1", ("2",)),
                ("V05", "Ativo Total (1) = 1.01 + 1.02", "1", ("1.01", "1.02")),
                ("V06", "Passivo Total (2) = 2.01 + 2.02 + 2.03", "2", ("2.01", "2.02", "2.03")))
    for vid, desc, lado_a, lado_b in equacoes:
        for coluna, attr in colunas:
            ausentes = [c for c in (lado_a, *lado_b) if c not in por_codigo]
            if ausentes:
                vs.append(Validacao(vid, desc, "erro", False, coluna,
                                    detalhe="conta ausente: " + ", ".join(ausentes)))
                continue
            a = getattr(por_codigo[lado_a], attr)
            b = sum(getattr(por_codigo[c], attr) for c in lado_b)
            vs.append(Validacao(vid, desc, "erro", a == b, coluna, esperado=a, obtido=b))

    # V07
    n_linhas = 0
    for bloco in blocos.values():
        for p in bloco.paginas:
            n_linhas += sum(1 for l in _corpo(paginas[p], cabecalhos[p]) if RE_INICIO_CONTA.match(l.rstrip()))
    vs.append(Validacao("V07", "nº de linhas com código = nº de contas extraídas", "erro",
                        n_linhas == len(contas), esperado=n_linhas, obtido=len(contas)))

    # V08 (espelha o verificar_numeros.py)
    falhas = []
    for c in contas:
        texto = normalizar(paginas.get(c.pagina, ""))
        ok = normalizar(c.trecho) in texto
        for lit, num in ((c.atual_lit, c.valor), (c.anterior_lit, c.anterior)):
            ok = ok and normalizar(lit) in texto and br_para_int(lit) == num
        if not ok:
            falhas.append(f"{c.codigo} (pág. {c.pagina})")
    vs.append(Validacao("V08", "autoverificação: trecho e literais na página, valores batem", "erro",
                        not falhas, detalhe=("falharam: " + ", ".join(falhas)) if falhas else ""))

    # A01 — soma dos filhos diretos
    filhos: dict[str, list[Conta]] = {}
    for c in contas:
        pai = _codigo_pai(c.codigo)
        if pai is not None:
            filhos.setdefault(pai, []).append(c)
    a01 = []
    for pai, fs in filhos.items():
        if pai not in por_codigo:
            continue
        for coluna, attr in colunas:
            esperado = getattr(por_codigo[pai], attr)
            obtido = sum(getattr(f, attr) for f in fs)
            if esperado != obtido:
                a01.append(Validacao("A01", f"soma dos filhos de {pai} = {pai}", "aviso", False, coluna,
                                     esperado=esperado, obtido=obtido))
    vs.extend(a01 or [Validacao("A01", "soma dos filhos diretos = conta pai", "aviso", True)])

    # A02 — pai ausente
    sem_pai = [c.codigo for c in contas if _codigo_pai(c.codigo) and _codigo_pai(c.codigo) not in por_codigo]
    vs.append(Validacao("A02", "toda conta tem o pai no bloco", "aviso", not sem_pai,
                        detalhe=("sem pai: " + ", ".join(sem_pai)) if sem_pai else ""))

    # A03 — ordem crescente dentro de cada bloco
    fora_ordem = []
    for tipo in ("Ativo", "Passivo"):
        seq = [c for c in contas if c.tipo == tipo]
        for ant, atu in zip(seq, seq[1:]):
            if _chave_codigo(atu.codigo) <= _chave_codigo(ant.codigo):
                fora_ordem.append(f"{ant.codigo} → {atu.codigo}")
    vs.append(Validacao("A03", "códigos em ordem crescente", "aviso", not fora_ordem,
                        detalhe=("fora de ordem: " + "; ".join(fora_ordem)) if fora_ordem else ""))

    # A08 — PL consolidado
    if visao == "consolidado" and "2.03" in por_codigo:
        desc = por_codigo["2.03"].descricao
        vs.append(Validacao("A08", "descrição de 2.03 contém 'Consolidado'", "aviso",
                            "Consolidado" in desc, detalhe="" if "Consolidado" in desc else f"2.03 = '{desc}'"))
    return vs


# ---------------------------------------------------------------------------
# Orquestração pura
# ---------------------------------------------------------------------------
def _ambiguo(c: Conta, textos: dict[int, str]) -> bool:
    t = textos.get(c.pagina, "")
    return contar_ocorrencias(c.atual_lit, t) > 1 or contar_ocorrencias(c.anterior_lit, t) > 1


def extrair_balanco(paginas: list[PaginaTexto], visao: str,
                    blocos: dict[str, Bloco] | None = None, stem: str | None = None) -> Resultado:
    textos = {p.numero: p.texto for p in paginas}
    avisos: list[Aviso] = []
    localizacao = "automatica"
    if blocos is None:
        blocos = localizar_blocos(paginas, visao, stem)
    else:
        localizacao = "--paginas"
        alvo = VISAO_ALVO[visao]
        for tipo, bloco in blocos.items():
            for n in bloco.paginas:
                m = RE_TITULO.search(textos[n])
                if not m or m["visao"] != alvo or m["tipo"] != tipo:
                    achado = f"'{m.group(0).strip()}'" if m else "sem título de BP"
                    avisos.append(Aviso("A07", n, f"título não confere com {tipo} (DFs {alvo}): {achado}"))

    numeros = [n for tipo in ("Ativo", "Passivo") for n in blocos[tipo].paginas]
    cabecalhos = {n: ler_cabecalho(textos[n], n) for n in numeros}
    if len({(c.escala, c.data_atual, c.data_anterior) for c in cabecalhos.values()}) > 1:
        raise ErroExtracao(f"datas/escala divergentes entre as págs. {_lista_paginas(numeros)}")

    contas: list[Conta] = []
    for tipo in ("Ativo", "Passivo"):
        cs, avs = parsear_bloco([PaginaTexto(n, textos[n]) for n in blocos[tipo].paginas], cabecalhos, tipo)
        contas.extend(cs)
        avisos.extend(avs)

    validacoes = validar(contas, textos, blocos, cabecalhos, visao)
    return Resultado(contas, blocos, cabecalhos[numeros[0]], validacoes, avisos, textos, localizacao)


def montar_registros(res: Resultado, empresa: str, visao: str) -> list[dict]:
    cab = res.cabecalho
    registros = []
    for c in res.contas:
        registros.append({
            "metrica": f"{c.codigo} {c.descricao}",
            "periodo": f"{cab.data_atual} vs {cab.data_anterior}",
            "unidade": "R$ mil",
            "valor": c.valor,
            "valor_como_aparece": c.atual_lit,
            "anterior": c.anterior,
            "anterior_como_aparece": c.anterior_lit,
            "pagina": c.pagina,
            "trecho": c.trecho,
            "codigo_conta": c.codigo,
            "descricao": c.descricao,
            "codigo_pai": _codigo_pai(c.codigo),
            "nivel": c.codigo.count(".") + 1,
            "demonstracao": "BPA" if c.codigo.startswith("1") else "BPP" if c.codigo.startswith("2") else None,
            "visao": visao,
            "empresa": empresa,
            "data_atual": _data_iso(cab.data_atual),
            "data_anterior": _data_iso(cab.data_anterior),
            "ambiguo": _ambiguo(c, res.textos),
        })
    return registros


def montar_meta(res: Resultado, empresa: str, visao: str, pdf: Path, textos_dir: Path) -> dict:
    n_ativo = sum(1 for c in res.contas if c.tipo == "Ativo")
    return {
        "script": "extrair_balanco.py",
        "versao_script": VERSAO,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "empresa": empresa,
        "pdf": _rel(pdf),
        "pdf_sha256": hashlib.sha256(Path(pdf).read_bytes()).hexdigest(),
        "textos_dir": _rel(textos_dir),
        "visao": visao,
        "paginas": {"ativo": res.blocos["Ativo"].paginas, "passivo": res.blocos["Passivo"].paginas},
        "localizacao": res.localizacao,
        "escala_original": res.cabecalho.escala,
        "unidade": "R$ mil",
        "data_atual": _data_iso(res.cabecalho.data_atual),
        "data_anterior": _data_iso(res.cabecalho.data_anterior),
        "n_contas": {"ativo": n_ativo, "passivo": len(res.contas) - n_ativo, "total": len(res.contas)},
        "n_ambiguos": sum(1 for c in res.contas if _ambiguo(c, res.textos)),
        "status": "aprovado" if res.aprovado else "reprovado",
        "validacoes": [{"id": v.id, "descricao": v.descricao, "severidade": v.severidade, "coluna": v.coluna,
                        "ok": v.ok, "esperado": v.esperado, "obtido": v.obtido, "detalhe": v.detalhe}
                       for v in res.validacoes],
        "avisos": [{"id": a.id, "pagina": a.pagina, "mensagem": a.mensagem} for a in res.avisos],
    }


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def gravar_saidas(registros: list[dict], meta: dict, saida: Path, nome_base: str,
                  csv: bool, aprovado: bool) -> list[Path]:
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    gravados = []
    if aprovado:
        principal = saida / f"{nome_base}.json"
        principal.write_text(_json(registros), encoding="utf-8")
        gravados.append(principal)
    caminho_meta = saida / f"{nome_base}.meta.json"
    caminho_meta.write_text(_json(meta), encoding="utf-8")
    gravados.append(caminho_meta)
    if aprovado and csv:
        caminho_csv = saida / f"{nome_base}.csv"
        campos = ["codigo_conta", "descricao", "nivel", "demonstracao", "valor", "anterior",
                  "pagina", "visao", "data_atual", "data_anterior"]
        with caminho_csv.open("w", encoding="utf-8", newline="") as f:
            w = _csv_writer(f)
            w.writerow(campos)
            for r in registros:
                w.writerow([r[c] for c in campos])
        gravados.append(caminho_csv)
    return gravados


_csv_writer = csv.writer  # o parâmetro `csv` de gravar_saidas sombreia o módulo


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------
def _linha_validacao(v: Validacao, cab: Cabecalho) -> str:
    rotulo = "OK  " if v.ok else ("ERRO" if v.severidade == "erro" else "AVISO")
    texto = v.descricao
    if v.coluna:
        data = cab.data_atual if v.coluna == "atual" else cab.data_anterior
        texto += f" em {data}"
        if not v.ok and v.esperado is not None:
            texto = texto.replace(" = ", " ≠ ", 1) + f": {v.esperado} × {v.obtido}"
    if not v.ok and v.detalhe:
        texto += f" ({v.detalhe})"
    elif v.ok and v.esperado is not None and not v.coluna:
        texto += f" ({v.obtido})"
    return f"  [{rotulo}] {v.id} {texto}"


def _imprimir_resumo(pdf: Path, visao: str, pasta: Path, reutilizados: bool, res: Resultado,
                     gravados: list[Path]) -> None:
    cab = res.cabecalho
    pa, pp = res.blocos["Ativo"].paginas, res.blocos["Passivo"].paginas
    rot = lambda ps: (f"pág. {ps[0]}" if len(ps) == 1 else f"págs. {_lista_paginas(ps)}")
    n_ativo = sum(1 for c in res.contas if c.tipo == "Ativo")
    n_amb = sum(1 for c in res.contas if _ambiguo(c, res.textos))
    print(f"{pdf.name} · visão {visao} · textos: {_rel(pasta)} ({'reutilizados' if reutilizados else 'gerados'})")
    print(f"  Ativo: {rot(pa)} · Passivo: {rot(pp)} · escala: {cab.escala} · "
          f"colunas: {cab.data_atual} e {cab.data_anterior}")
    print(f"  {len(res.contas)} contas (Ativo {n_ativo}, Passivo {len(res.contas) - n_ativo}) · "
          f"literais ambíguos: {n_amb}")
    for v in res.validacoes:
        if v.severidade == "erro" or not v.ok:
            print(_linha_validacao(v, cab))
    for a in res.avisos:
        print(f"  [AVISO] {a.id} " + (f"pág. {a.pagina}: " if a.pagina else "") + a.mensagem)
    print("  → " + " · ".join(_rel(p) for p in gravados))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def processar(pdf: Path, visao: str, empresa: str, saida: Path, textos: Path | None,
              paginas: str | None, csv: bool) -> int:
    pdf = Path(pdf)
    try:
        if not pdf.is_file():
            raise ErroExtracao(f"PDF não encontrado: {pdf}")
        n_paginas = contar_paginas_pdf(pdf)
        pasta_padrao = Path(textos) if textos is not None else RAIZ / "saida" / pdf.stem
        reutilizados = _textos_completos(pasta_padrao, n_paginas)
        pasta = garantir_textos(pdf, textos, n_paginas)
        lista = carregar_textos(pasta, n_paginas)
        blocos = parse_paginas(paginas, n_paginas) if paginas else None
        res = extrair_balanco(lista, visao, blocos, pdf.stem)
    except ErroExtracao as e:
        print(f"ERRO: {pdf.name} · visão {visao}: {e}", file=sys.stderr)
        return 2

    nome_base = f"balanco_{empresa}" + ("_controladora" if visao == "controladora" else "")
    registros = montar_registros(res, empresa, visao)
    meta = montar_meta(res, empresa, visao, pdf, pasta)
    gravados = gravar_saidas(registros, meta, saida, nome_base, csv, res.aprovado)
    _imprimir_resumo(pdf, visao, pasta, reutilizados, res, gravados)
    return 0 if res.aprovado else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extrair_balanco.py",
        description="Extrai o Balanço Patrimonial (Ativo/Passivo) de ITR/DFP em PDF para JSON verificável.")
    parser.add_argument("pdf", nargs="+", type=Path, help="ITR/DFP em PDF")
    parser.add_argument("--visao", choices=("consolidado", "controladora", "ambas"), default="consolidado")
    parser.add_argument("--empresa", help="identificador da empresa (só com 1 PDF)")
    parser.add_argument("--saida", type=Path, default=RAIZ / "metricas", help="diretório de saída")
    parser.add_argument("--textos", type=Path, help="pasta com pagina_NN.txt (só com 1 PDF)")
    parser.add_argument("--paginas", help="override ATIVO:PASSIVO, ex.: 26:27-28 (só com 1 PDF)")
    parser.add_argument("--csv", action="store_true", help="grava também o CSV plano")
    args = parser.parse_args(argv)

    if len(args.pdf) != 1:
        for opcao in ("empresa", "textos", "paginas"):
            if getattr(args, opcao) is not None:
                parser.error(f"--{opcao} exige exatamente 1 PDF")
    if args.paginas is not None and args.visao == "ambas":
        parser.error("--paginas não combina com --visao ambas")
    empresa_arg = None
    if args.empresa is not None:
        empresa_arg = args.empresa.strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]+", empresa_arg):
            parser.error(f"--empresa inválido: '{args.empresa}' (use letras minúsculas, dígitos, _ ou -)")

    visoes = ("consolidado", "controladora") if args.visao == "ambas" else (args.visao,)
    codigo = 0
    for pdf in args.pdf:
        empresa = empresa_arg or pdf.stem.split("_")[0].lower()
        if not re.fullmatch(r"[a-z0-9_-]+", empresa):
            print(f"ERRO: {pdf.name}: empresa '{empresa}' inválida; use --empresa", file=sys.stderr)
            codigo = max(codigo, 2)
            continue
        for visao in visoes:
            codigo = max(codigo, processar(pdf, visao, empresa, args.saida, args.textos, args.paginas, args.csv))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
