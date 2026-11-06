"""
CASE-07 · Pipeline "um comando": dois PDFs de ITR (+ apresentações) → apresentação comparativa.

Rode da raiz do repositório:
    python src/pipeline.py --a gerdau --b usiminas --tri 3T26 [--forcar] [--permitir-pendencias]

Etapas (para no primeiro bloqueio, com mensagem dizendo o que fazer):
  1. insumos       data/itrs/<slug>_ITR_<tri>.pdf e data/apresentacoes/<slug>_APRESENTACAO_<tri>.pdf
  2. extração      saida/<pdf>/pagina_NN.txt (só se a pasta não existir, ou com --forcar)
  3. dfs_cvm       metricas/<slug>_<tri>_itr_dfs.json (só se não existir, ou com --forcar)
  4. assistidos    complementar, operacional, qualitativo: se faltar, imprime o prompt pronto
                   (prompts/) com as páginas candidatas e para
  5. verificação   contrato + verificar_numeros.avaliar em cada arquivo de fatos de entrada,
                   na pasta do documento certo → saida/verificacao_<a>_x_<b>_<tri>.json
                   Um ERRO bloqueia. --permitir-pendencias segue como RASCUNHO, sem os fatos reprovados.
  6. indicadores   indicadores.calcular só com os fatos aprovados → metricas/<slug>_<tri>_indicadores.json
  7. comparativo   src/comparar.py (CASE-05), preenchendo "verificacao" no comparativo.json
  8. apresentação  src/apresentacao.py (CASE-06)

Códigos de saída: 0 entregue · 1 verificação reprovada · 2 insumo ausente ·
                  3 aguardando extração assistida · 4 etapa de outro card ainda não disponível.
Idempotente: arquivos só são regravados quando o conteúdo muda; nada leva data/hora.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

CODIGO = Path(__file__).resolve().parent
sys.path.insert(0, str(CODIGO))

from verificar_numeros import avaliar  # noqa: E402

try:  # CASE-01; até entrar no main, só a checagem mínima de formato
    from contrato import validar as _validar_contrato  # type: ignore[import-not-found]
except ImportError:
    _validar_contrato = None

RAIZ_PADRAO = CODIGO.parent

SAIDA_OK, SAIDA_ERRO, SAIDA_INSUMO, SAIDA_ASSISTIDO, SAIDA_AGUARDANDO = 0, 1, 2, 3, 4

# documento → (pasta dos PDFs, rótulo no nome do PDF)
DOCUMENTOS = {"itr": ("data/itrs", "ITR"), "apresentacao": ("data/apresentacoes", "APRESENTACAO")}


@dataclass(frozen=True)
class Assistido:
    """Um JSON preenchido com o Claude. `opcoes` = (documento, tipo) aceitos, em ordem de preferência."""
    nome: str
    tema: str        # tema do localizar_paginas.py
    prompts: tuple[str, ...]  # arquivos em prompts/, o primeiro que existir
    card: str
    opcoes: tuple[tuple[str, str], ...]


ASSISTIDOS = (
    Assistido("complementar", "ebitda", ("extracao_financeira_complementar.md",), "CASE-02",
              (("itr", "complementar"),)),
    Assistido("operacional", "operacional", ("extracao_operacional.md",), "CASE-03",
              (("itr", "operacional"), ("apresentacao", "operacional"))),
    Assistido("qualitativo", "qualitativo", ("extracao_qualitativo.md", "extracao_qualitativa.md"), "CASE-03",
              (("apresentacao", "qualitativo"),)),
)

# Busca provisória de páginas candidatas (até o localizar_paginas.py do CASE-03 entrar).
PALAVRAS_TEMA = {
    "ebitda": ["ebitda", "lajida", "ajustado", "cvm 156", "impairment", "divida liquida", "divida bruta",
               "depreciacao", "amortizacao", "reconciliacao"],
    "operacional": ["toneladas", "mil t", "r$/t", "capacidade", "embarques", "vendas", "exportacao",
                    "segmento", "producao", "minerio"],
    "qualitativo": ["estrategia", "perspectivas", "guidance", "capex", "investimentos", "riscos",
                    "esg", "destaques", "mercado"],
}


# --------------------------------------------------------------------------- utilidades

def _sem_acento(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def gravar_se_mudou(caminho: Path, conteudo: str) -> bool:
    """Grava só se o conteúdo mudou (idempotência). Devolve True se gravou."""
    if caminho.exists() and caminho.read_text(encoding="utf-8") == conteudo:
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    return True


def _rel(caminho: Path, raiz: Path) -> str:
    try:
        return caminho.resolve().relative_to(raiz.resolve()).as_posix()
    except ValueError:
        return caminho.as_posix()


@dataclass
class Contexto:
    a: str
    b: str
    tri: str
    raiz: Path
    forcar: bool = False
    permitir_pendencias: bool = False
    pendencias: list[dict] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    pdf_mudou: set[tuple[str, str]] = field(default_factory=set)

    @property
    def empresas(self) -> tuple[str, str]:
        return (self.a, self.b)

    @property
    def par(self) -> str:
        return f"{self.a}_x_{self.b}_{self.tri}"

    def pdf(self, slug: str, documento: str) -> Path:
        pasta, rotulo = DOCUMENTOS[documento]
        return self.raiz / pasta / f"{slug}_{rotulo}_{self.tri}.pdf"

    def pasta_paginas(self, slug: str, documento: str) -> Path:
        return self.raiz / "saida" / self.pdf(slug, documento).stem

    def metricas(self) -> Path:
        return self.raiz / "metricas"

    def diz(self, msg: str) -> None:
        print(msg, flush=True)
        self.log.append(msg)


class Parada(Exception):
    """Interrompe o pipeline com código de saída e mensagem para o usuário."""

    def __init__(self, codigo: int, mensagem: str):
        super().__init__(mensagem)
        self.codigo = codigo


# --------------------------------------------------------------------------- 1–3: insumos, extração, DFs

def conferir_insumos(ctx: Contexto) -> None:
    faltando = []
    for slug in ctx.empresas:
        pdf, pasta = ctx.pdf(slug, "itr"), ctx.pasta_paginas(slug, "itr")
        if not pdf.exists() and not pasta.is_dir():
            faltando.append(_rel(pdf, ctx.raiz))
        elif not pdf.exists():
            ctx.diz(f"  [aviso] {_rel(pdf, ctx.raiz)} não encontrado; usando as páginas já extraídas em "
                    f"{_rel(pasta, ctx.raiz)}")
        apres = ctx.pdf(slug, "apresentacao")
        if not apres.exists() and not ctx.pasta_paginas(slug, "apresentacao").is_dir():
            ctx.diz(f"  [aviso] {_rel(apres, ctx.raiz)} não encontrado: os JSONs que dependem da "
                    f"apresentação ficam pendentes")
    if faltando:
        raise Parada(SAIDA_INSUMO, "Faltam os ITRs: " + ", ".join(faltando) +
                     "\n  Coloque o PDF com esse nome exato (slug minúsculo, sem acento) e rode de novo.")


CARIMBO = "_origem.sha256"  # sha256 do PDF de onde vieram os pagina_NN.txt


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _sha_conhecido(ctx: Contexto, slug: str, documento: str) -> str | None:
    """sha256 do PDF que gerou as páginas: carimbo da pasta ou, para o ITR, o manifesto do dfs_cvm."""
    pasta = ctx.pasta_paginas(slug, documento)
    if (pasta / CARIMBO).exists():
        return (pasta / CARIMBO).read_text(encoding="utf-8").strip()
    manifesto = ctx.metricas() / "manifesto" / f"{pasta.name}.json"
    if documento == "itr" and manifesto.exists():
        return json.loads(manifesto.read_text(encoding="utf-8")).get("sha256")
    return None


def extrair_paginas(ctx: Contexto) -> None:
    """Extrai se a pasta não existe, com --forcar, ou se o PDF mudou desde a última extração."""
    for slug in ctx.empresas:
        for documento in DOCUMENTOS:
            pdf, pasta = ctx.pdf(slug, documento), ctx.pasta_paginas(slug, documento)
            if not pdf.exists():
                continue
            atual, conhecido = sha256(pdf), _sha_conhecido(ctx, slug, documento)
            if pasta.is_dir() and not ctx.forcar:
                if conhecido == atual:
                    gravar_se_mudou(pasta / CARIMBO, atual + "\n")
                    continue
                if conhecido is None:  # extração antiga sem carimbo: não dá para provar a origem
                    ctx.diz(f"  [aviso] {_rel(pasta, ctx.raiz)} sem carimbo de origem: re-extraindo")
                else:
                    ctx.diz(f"  [aviso] {_rel(pdf, ctx.raiz)} mudou desde a última extração: re-extraindo. "
                            f"Os JSONs assistidos de {slug} ({documento}) podem estar desatualizados; "
                            f"a verificação vai dizer.")
                    ctx.pdf_mudou.add((slug, documento))
            import extrair_release  # pdfplumber/pandas: só carrega se precisar extrair

            for velho in pasta.glob("pagina_*.txt"):  # PDF novo pode ter menos páginas
                velho.unlink()
            extrair_release.SAIDA = ctx.raiz / "saida"
            extrair_release.extrair(pdf)
            gravar_se_mudou(pasta / CARIMBO, atual + "\n")


def rodar_dfs(ctx: Contexto) -> None:
    import dfs_cvm

    for slug in ctx.empresas:
        destino = ctx.metricas() / f"{slug}_{ctx.tri}_itr_dfs.json"
        if destino.exists() and not ctx.forcar and (slug, "itr") not in ctx.pdf_mudou:
            continue
        pasta = ctx.pasta_paginas(slug, "itr")
        args = [str(pasta), "--empresa", slug, "--tri", ctx.tri,
                "--pdf", str(ctx.pdf(slug, "itr")), "--metricas", str(ctx.metricas())]
        if dfs_cvm.main(args) != 0:
            raise Parada(SAIDA_ERRO, f"dfs_cvm falhou para {slug} (mensagem acima). Confira as páginas em "
                                     f"{_rel(pasta, ctx.raiz)} antes de seguir.")


# --------------------------------------------------------------------------- 4: JSONs assistidos

def paginas_candidatas(ctx: Contexto, pasta: Path, tema: str, top: int = 10) -> tuple[str, str]:
    """(origem, texto) com o ranking de páginas. Usa o localizar_paginas.py do CASE-03 se existir."""
    script = ctx.raiz / "src" / "localizar_paginas.py"
    if script.exists():
        r = subprocess.run([sys.executable, str(script), str(pasta), "--tema", tema, "--top", str(top)],
                           cwd=ctx.raiz, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return "src/localizar_paginas.py", r.stdout.strip()
    palavras = PALAVRAS_TEMA.get(tema, [])
    pontos = []
    for arq in sorted(pasta.glob("pagina_*.txt")):
        texto = _sem_acento(arq.read_text(encoding="utf-8"))
        n = sum(texto.count(p) for p in palavras)
        if n:
            pontos.append((-n, int(arq.stem.split("_")[1]), n))
    linhas = [f"- p. {pag} ({n} ocorrências)" for _, pag, n in sorted(pontos)[:top]]
    return ("busca provisória por palavras-chave (localizar_paginas.py do CASE-03 ainda não existe)",
            "\n".join(linhas) or "- nenhuma página com as palavras-chave do tema")


def montar_prompt(ctx: Contexto, slug: str, item: Assistido, documento: str, tipo: str) -> str:
    pasta = ctx.pasta_paginas(slug, documento)
    origem, ranking = paginas_candidatas(ctx, pasta, item.tema)
    arq_prompt = next((ctx.raiz / "prompts" / n for n in item.prompts if (ctx.raiz / "prompts" / n).exists()), None)
    if arq_prompt is not None:
        corpo = arq_prompt.read_text(encoding="utf-8")
    else:
        corpo = (f"(prompts/{item.prompts[0]} ainda não existe — {item.card}.)\n\n"
                 f"Leia `docs/TAREFAS.md` (\"Contrato de dados\" e o card {item.card}) e os arquivos "
                 f"`{_rel(pasta, ctx.raiz)}/pagina_NN.txt` das páginas candidatas abaixo. Gere "
                 f"`metricas/<slug>_<tri>_{documento}_{tipo}.json` no contrato: lista JSON de fatos, "
                 f"`pagina` = índice do PDF, `trecho` e `valor_como_aparece` copiados literalmente, unidade "
                 f"como aparece, só consolidado ou `segmento:<segmento>`. Depois rode o verificador.")
    rotulo = DOCUMENTOS[documento][1]
    corpo = (corpo.replace("<slug>", slug).replace("<tri>", ctx.tri)
             .replace(f"{slug}_ITR_{ctx.tri}", f"{slug}_{rotulo}_{ctx.tri}"))
    return (f"{corpo.rstrip()}\n\n## Páginas candidatas ({_rel(pasta, ctx.raiz)})\n"
            f"Origem: {origem}. Números = índice do PDF (o mesmo de pagina_NN.txt).\n{ranking}\n")


def conferir_assistidos(ctx: Contexto) -> None:
    prompts = []
    for slug in ctx.empresas:
        for item in ASSISTIDOS:
            existentes = [ctx.metricas() / f"{slug}_{ctx.tri}_{d}_{t}.json" for d, t in item.opcoes]
            if any(p.exists() for p in existentes):
                continue
            possiveis = [(d, t) for d, t in item.opcoes if ctx.pasta_paginas(slug, d).is_dir()]
            esperado = " ou ".join(_rel(p, ctx.raiz) for p in existentes)
            if not possiveis:
                pdfs = " ou ".join(sorted({_rel(ctx.pdf(slug, d), ctx.raiz) for d, _ in item.opcoes}))
                motivo = f"falta {esperado}; antes, falta o PDF-fonte {pdfs}"
                ctx.pendencias.append({"tipo": "documento_ausente", "empresa": slug, "item": item.nome,
                                       "motivo": motivo})
                ctx.diz(f"  [pendente] {slug} · {item.nome}: {motivo}")
                continue
            documento, tipo = possiveis[0]
            texto = montar_prompt(ctx, slug, item, documento, tipo)
            destino = ctx.raiz / "saida" / "prompts" / f"{slug}_{ctx.tri}_{documento}_{tipo}.md"
            gravar_se_mudou(destino, texto)
            ctx.pendencias.append({"tipo": "json_assistido_ausente", "empresa": slug, "item": item.nome,
                                   "esperado": esperado, "prompt": _rel(destino, ctx.raiz)})
            prompts.append((slug, item, esperado, destino, texto))
    if not ctx.pendencias:
        return
    for slug, item, esperado, destino, texto in prompts:
        print(f"\n{'=' * 78}\nFALTA {esperado} ({item.card}). Cole no Claude Code o prompt abaixo "
              f"(também salvo em {_rel(destino, ctx.raiz)}):\n{'-' * 78}\n{texto}{'=' * 78}")
    n = len(ctx.pendencias)
    if not ctx.permitir_pendencias:
        if prompts:
            raise Parada(SAIDA_ASSISTIDO,
                         f"{n} JSON(s) assistido(s) faltando ({len(prompts)} com prompt acima). Gere, verifique "
                         f"e rode o mesmo comando de novo. Para seguir só com rascunho: --permitir-pendencias.")
        raise Parada(SAIDA_INSUMO, f"{n} JSON(s) assistido(s) sem documento-fonte (ver [pendente] acima). "
                                   f"Para seguir só com rascunho: --permitir-pendencias.")
    ctx.diz(f"  [rascunho] seguindo sem {n} JSON(s) assistido(s)")


# --------------------------------------------------------------------------- 5: verificação

_NOME_FATOS = re.compile(r"^(?P<slug>[a-z0-9_]+?)_(?P<tri>\dT\d\d)_(?P<doc>[a-z]+)_(?P<tipo>[a-z0-9_]+)$")


def arquivos_de_fatos(ctx: Contexto, slug: str) -> list[Path]:
    """Só os arquivos de fatos de entrada: <slug>_<tri>_*.json, sem indicadores nem relatórios derivados."""
    return sorted(p for p in ctx.metricas().glob(f"{slug}_{ctx.tri}_*.json")
                  if not p.stem.endswith("_indicadores"))


def _checar_formato(dados) -> list[str]:
    if _validar_contrato is not None:
        return [str(e) for e in _validar_contrato(dados)]
    if not isinstance(dados, list) or not dados:
        return ["esperado uma lista de fatos não vazia"]
    return [f"[{i}]: fato não é um objeto" for i, m in enumerate(dados) if not isinstance(m, dict)]


def verificar_arquivo(ctx: Contexto, slug: str, arquivo: Path) -> tuple[dict, list[dict]]:
    """(resumo do arquivo, fatos aprovados). Fato com ERRO não entra nos aprovados."""
    resumo = {"pasta": None, "total": 0, "ok": 0, "revisar": 0, "erro": 0,
              "erros_arquivo": [], "falhas": []}
    m = _NOME_FATOS.match(arquivo.stem)
    if not m or m["slug"] != slug or m["doc"] not in DOCUMENTOS:
        resumo["erros_arquivo"].append(
            f"nome fora da convenção <slug>_<tri>_<itr|apresentacao>_<tipo>.json: {arquivo.name}")
        return resumo, []
    pasta = ctx.pasta_paginas(slug, m["doc"])
    resumo["pasta"] = _rel(pasta, ctx.raiz)
    if not pasta.is_dir():
        resumo["erros_arquivo"].append(f"pasta do documento não existe: {resumo['pasta']}")
        return resumo, []
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        resumo["erros_arquivo"].append(f"JSON inválido: linha {e.lineno}, coluna {e.colno}: {e.msg}")
        return resumo, []
    erros_contrato = _checar_formato(dados)
    if erros_contrato:
        resumo["erros_arquivo"] += [f"contrato: {e}" for e in erros_contrato]
    if not isinstance(dados, list):
        return resumo, []
    aprovados = []
    for i, fato in enumerate(dados):
        if not isinstance(fato, dict):
            continue
        status, erros, pend = avaliar(fato, pasta)
        resumo["total"] += 1
        resumo[status.lower()] += 1
        if status == "ERRO":
            resumo["falhas"].append({"indice": i, "chave": fato.get("chave"), "metrica": fato.get("metrica"),
                                     "periodo": fato.get("periodo"), "pagina": fato.get("pagina"),
                                     "status": status, "erros": erros, "pendencias": pend})
        else:
            aprovados.append(fato)
    if erros_contrato:  # arquivo fora do contrato: nenhum fato dele segue adiante
        return resumo, []
    return resumo, aprovados


def verificar(ctx: Contexto) -> tuple[dict, dict[str, list[dict]]]:
    por_arquivo, aprovados = {}, {}
    for slug in ctx.empresas:
        aprovados[slug] = []
        arquivos = arquivos_de_fatos(ctx, slug)
        if not arquivos:
            raise Parada(SAIDA_INSUMO, f"Nenhum arquivo de fatos em metricas/{slug}_{ctx.tri}_*.json")
        for arq in arquivos:
            resumo, ok = verificar_arquivo(ctx, slug, arq)
            por_arquivo[_rel(arq, ctx.raiz)] = resumo
            aprovados[slug] += ok
    tot = {k: sum(r[k] for r in por_arquivo.values()) for k in ("total", "ok", "revisar", "erro")}
    arquivos_com_erro = sorted(n for n, r in por_arquivo.items() if r["erro"] or r["erros_arquivo"])
    if arquivos_com_erro or ctx.pendencias:
        status = "rascunho" if ctx.permitir_pendencias else "bloqueado"
    else:
        status = "aprovado"
    relatorio = {
        "a": ctx.a, "b": ctx.b, "periodo": ctx.tri, "status": status, **tot,
        "contrato": "src/contrato.py" if _validar_contrato else "checagem mínima (contrato.py do CASE-01 ausente)",
        "arquivos_com_erro": arquivos_com_erro,
        "pendencias": ctx.pendencias,
        "por_arquivo": por_arquivo,
    }
    return relatorio, aprovados


def imprimir_reprovacoes(relatorio: dict, por_arquivo: int = 3) -> None:
    """Resumo por arquivo + os primeiros problemas; a lista completa fica no relatório JSON."""
    for nome, r in relatorio["por_arquivo"].items():
        problemas = [f"contrato: {e[len('contrato: '):]}" if e.startswith("contrato: ") else e
                     for e in r["erros_arquivo"]]
        problemas += [f"{f['metrica']} ({f['periodo']}), p. {f['pagina']}: {'; '.join(f['erros'])}"
                      for f in r["falhas"]]
        if not problemas:
            continue
        print(f"  [ERRO] {nome} ({r['pasta']}): {r['erro']} fato(s) com erro, "
              f"{len(r['erros_arquivo'])} problema(s) de contrato/arquivo")
        for p in problemas[:por_arquivo]:
            print(f"         - {p}")
        if len(problemas) > por_arquivo:
            print(f"         ... e mais {len(problemas) - por_arquivo} (ver o relatório)")


# --------------------------------------------------------------------------- 6–8: indicadores, comparativo, apresentação

@dataclass(frozen=True)
class Destinos:
    """Onde cada etapa derivada grava. Rascunho nunca toca metricas/, saida/comparativo/ nem entrega/."""
    metricas: Path
    comparativo: Path   # pasta-base passada ao comparar.py --saida
    html: Path
    final: Path | None  # cópia para entrega/ (só aprovado)


def destinos(ctx: Contexto, status: str) -> Destinos:
    if status == "aprovado":
        return Destinos(ctx.metricas(), ctx.raiz / "saida" / "comparativo",
                        ctx.raiz / "saida" / "apresentacao" / f"{ctx.par}.html",
                        ctx.raiz / "entrega" / f"apresentacao_{ctx.par}.html")
    base = ctx.raiz / "saida" / "rascunho" / ctx.par
    return Destinos(base / "metricas", base / "comparativo", base / f"RASCUNHO_{ctx.par}.html", None)


def _setor(ctx: Contexto, slug: str) -> str | None:
    cfg = ctx.raiz / "config" / "empresas.toml"
    if not cfg.exists():
        return None
    import tomllib
    return tomllib.loads(cfg.read_text(encoding="utf-8")).get(slug, {}).get("setor")


def calcular_indicadores(ctx: Contexto, aprovados: dict[str, list[dict]], dest: Destinos, status: str) -> None:
    import indicadores

    for slug in ctx.empresas:
        setor = _setor(ctx, slug) or indicadores.SETOR_SIDERURGIA
        resultado = indicadores.calcular(aprovados[slug], slug, ctx.tri, setor=setor)
        if status != "aprovado":
            resultado["verificacao_status"] = status
            # o slide de perfil/riscos lê o qualitativo de --metricas: só os fatos aprovados
            quali = [f for f in aprovados[slug] if f.get("chave") == "qualitativo"]
            gravar_se_mudou(dest.metricas / f"{slug}_{ctx.tri}_apresentacao_qualitativo.json",
                            json.dumps(quali, ensure_ascii=False, indent=2) + "\n")
        destino = dest.metricas / f"{slug}_{ctx.tri}_indicadores.json"
        # mesma serialização do CLI do CASE-04: com os mesmos fatos, o arquivo sai byte a byte igual
        gravou = gravar_se_mudou(destino, json.dumps(resultado, ensure_ascii=False, indent=2))
        c = resultado.get("cobertura", {})
        ctx.diz(f"  {slug}: {c.get('ok', '?')}/{len(resultado['indicadores'])} indicadores com valor → "
                f"{_rel(destino, ctx.raiz)}{'' if gravou else ' (sem mudança)'}")


def _rodar_script(ctx: Contexto, nome: str, args: list[str], card: str) -> None:
    script = ctx.raiz / "src" / nome
    if not script.exists():
        raise Parada(SAIDA_AGUARDANDO, f"src/{nome} ainda não existe (aguardando {card}). "
                                       f"O pipeline chegou até aqui; o resto roda quando o card entrar.")
    r = subprocess.run([sys.executable, str(script), *args], cwd=ctx.raiz)
    if r.returncode != 0:
        raise Parada(SAIDA_ERRO, f"src/{nome} terminou com código {r.returncode} (mensagem acima).")


def rodar_comparativo(ctx: Contexto, relatorio: dict, dest: Destinos) -> Path:
    _rodar_script(ctx, "comparar.py", ["--a", ctx.a, "--b", ctx.b, "--tri", ctx.tri,
                                       "--metricas", str(dest.metricas), "--saida", str(dest.comparativo)],
                  "CASE-05")
    pasta = dest.comparativo / ctx.par
    arq = pasta / "comparativo.json"
    if not arq.exists():
        raise Parada(SAIDA_ERRO, f"comparar.py não gerou {_rel(arq, ctx.raiz)}")
    comp = json.loads(arq.read_text(encoding="utf-8"))
    comp["verificacao"] = {
        "status": relatorio["status"], "total": relatorio["total"], "ok": relatorio["ok"],
        "revisar": relatorio["revisar"], "erro": relatorio["erro"],
        "relatorio": f"saida/verificacao_{ctx.par}.json",
        "por_arquivo": {n: {k: r[k] for k in ("total", "ok", "revisar", "erro")}
                        for n, r in relatorio["por_arquivo"].items()},
    }
    gravar_se_mudou(arq, json.dumps(comp, ensure_ascii=False, indent=2) + "\n")
    return pasta


def marcar_rascunho(html: str, relatorio: dict) -> str:
    """Faixa fixa e visível em todos os slides: o rascunho não pode ser confundido com a entrega."""
    if 'id="faixa-rascunho"' in html:
        return html
    motivo = (f"RASCUNHO — NÃO ENTREGAR · {relatorio['erro']} fato(s) reprovado(s) fora dos cálculos · "
              f"{len(relatorio['pendencias'])} pendência(s) · ver saida/verificacao_*.json")
    faixa = ('<div id="faixa-rascunho" style="position:fixed;top:0;left:0;right:0;z-index:99999;'
             'background:#b00020;color:#fff;font:bold 14px/2 sans-serif;text-align:center;'
             f'letter-spacing:.04em">{motivo}</div>')
    m = re.search(r"<body[^>]*>", html, re.I)
    return html[:m.end()] + faixa + html[m.end():] if m else faixa + html


def rodar_apresentacao(ctx: Contexto, pasta_comp: Path, dest: Destinos, relatorio: dict) -> Path:
    args = ["--comparativo", str(pasta_comp), "--metricas", str(dest.metricas), "--saida", str(dest.html)]
    narrativa = ctx.raiz / "narrativa" / f"{ctx.par}.json"
    if narrativa.exists():
        args += ["--narrativa", str(narrativa)]
    _rodar_script(ctx, "apresentacao.py", args, "CASE-06")
    if not dest.html.exists():
        raise Parada(SAIDA_ERRO, f"apresentacao.py não gerou {_rel(dest.html, ctx.raiz)}")
    if dest.final is None:
        gravar_se_mudou(dest.html, marcar_rascunho(dest.html.read_text(encoding="utf-8"), relatorio))
        return dest.html
    if not dest.final.exists() or dest.final.read_bytes() != dest.html.read_bytes():
        dest.final.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dest.html, dest.final)
    return dest.final


# --------------------------------------------------------------------------- orquestração

def executar(ctx: Contexto) -> int:
    etapa = "?"
    try:
        etapa = "1/8 insumos"
        ctx.diz(f"[{etapa}]")
        conferir_insumos(ctx)
        etapa = "2/8 extração de páginas"
        ctx.diz(f"[{etapa}]")
        extrair_paginas(ctx)
        etapa = "3/8 dfs_cvm"
        ctx.diz(f"[{etapa}]")
        rodar_dfs(ctx)
        etapa = "4/8 JSONs assistidos"
        ctx.diz(f"[{etapa}]")
        conferir_assistidos(ctx)

        etapa = "5/8 verificação"
        ctx.diz(f"[{etapa}]")
        relatorio, aprovados = verificar(ctx)
        destino = ctx.raiz / "saida" / f"verificacao_{ctx.par}.json"
        gravar_se_mudou(destino, _dump(relatorio))
        ctx.diz(f"  {relatorio['ok']}/{relatorio['total']} OK · {relatorio['revisar']} revisar · "
                f"{relatorio['erro']} erro · status {relatorio['status'].upper()} → {_rel(destino, ctx.raiz)}")
        if relatorio["arquivos_com_erro"]:
            imprimir_reprovacoes(relatorio)
        if relatorio["status"] == "bloqueado":
            raise Parada(SAIDA_ERRO, "Verificação reprovada: corrija os itens com ERRO olhando a página "
                                     "indicada e rode de novo. Para gerar só um rascunho (sem os fatos "
                                     "reprovados): --permitir-pendencias.")
        status = relatorio["status"]
        dest = destinos(ctx, status)
        if status != "aprovado":
            ctx.diz(f"  [rascunho] derivados vão para {_rel(dest.metricas.parent, ctx.raiz)}/ "
                    f"(metricas/, saida/comparativo/ e entrega/ não são tocados)")

        etapa = "6/8 indicadores"
        ctx.diz(f"[{etapa}]")
        calcular_indicadores(ctx, aprovados, dest, status)
        etapa = "7/8 comparativo"
        ctx.diz(f"[{etapa}]")
        pasta_comp = rodar_comparativo(ctx, relatorio, dest)
        etapa = "8/8 apresentação"
        ctx.diz(f"[{etapa}]")
        final = rodar_apresentacao(ctx, pasta_comp, dest, relatorio)
    except Parada as p:
        sys.stdout.flush()
        print(f"\nPAROU em [{etapa}]: {p}", file=sys.stderr)
        return p.codigo
    if status == "aprovado":
        print(f"\nENTREGUE: {_rel(final, ctx.raiz)}")
    else:
        print(f"\nRASCUNHO (não entregar): {_rel(final, ctx.raiz)} — pendências em "
              f"saida/verificacao_{ctx.par}.json")
    return SAIDA_OK


_SLUG = re.compile(r"^[a-z0-9_]+$")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, help="slug da empresa A (minúsculo, sem acento)")
    ap.add_argument("--b", required=True, help="slug da empresa B")
    ap.add_argument("--tri", required=True, help="trimestre, ex.: 3T26")
    ap.add_argument("--forcar", action="store_true", help="refaz extração de páginas e dfs_cvm")
    ap.add_argument("--permitir-pendencias", action="store_true",
                    help="segue com pendências/erros e gera apenas um RASCUNHO identificado")
    ap.add_argument("--raiz", type=Path, default=RAIZ_PADRAO, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    for s in (a.a, a.b):
        if not _SLUG.match(s):
            ap.error(f"slug inválido: {s!r} (use minúsculo, sem acento, ex.: gerdau)")
    if a.a == a.b:
        ap.error("--a e --b precisam ser empresas diferentes")
    if not re.match(r"^[1-4]T\d\d$", a.tri):
        ap.error(f"trimestre inválido: {a.tri!r} (ex.: 3T26)")
    ctx = Contexto(a.a, a.b, a.tri, a.raiz.resolve(), a.forcar, a.permitir_pendencias)
    return executar(ctx)


if __name__ == "__main__":
    sys.exit(main())
