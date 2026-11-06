"""
Case 3 — Catálogo de dados: gera docs/CATALOGO_DADOS.md e metricas/catalogo.json.

    python src/gerar_catalogo.py [--raiz DIR] [--check]

Fatos derivados vêm de data/itrs/, metricas/ (JSON, .meta.json, .csv), do
contrato (schemas/) e do verificador (saida/<stem>/). O cadastro manual fica em
catalogo/fontes.toml. Sem --check, grava os dois arquivos; com --check, só
compara e retorna 1 se algum estiver defasado.

Códigos de saída: 0 gravou ou --check em dia · 1 --check divergente ·
2 fontes.toml inválido, JSON ilegível em metricas/ ou uso inválido.
"""
import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import contrato  # noqa: E402
import verificar_numeros  # noqa: E402
from contrato import ErroLeitura  # noqa: E402

SAIDA_MD = "docs/CATALOGO_DADOS.md"
SAIDA_JSON = "metricas/catalogo.json"
VERSAO_CATALOGO = 1
GERADO_POR = "src/gerar_catalogo.py"
AVISO_JSON = "Gerado automaticamente; não edite à mão. Fonte manual: catalogo/fontes.toml."
GERADO_POR_SEM_META = "sem meta (JSON do time/Claude)"

CAMPOS_FONTE = ("stem", "pdf", "empresa", "nome", "tipo", "periodo",
                "data_referencia", "url_origem", "descricao")
CAMPOS_ESPERADO = ("artefato", "fonte", "descricao")
RE_DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_EBITDA = re.compile(r"[Ee][Bb][Ii][Tt][Dd][Aa]")
TIPOS_VERIFICAVEIS = ("balanco", "metricas")
PLACEHOLDER = "(a preencher)"


class ErroFontes(Exception):
    """catalogo/fontes.toml ausente ou fora do formato (código 2)."""


# ---------------------------------------------------------------- cadastro

def _validar_tabelas(lista, nome_tabela: str, campos: tuple, extra_ok: bool = False) -> None:
    for i, item in enumerate(lista, 1):
        rotulo = f"[[{nome_tabela}]] #{i}"
        if not isinstance(item, dict):
            raise ErroFontes(f"{rotulo} não é uma tabela")
        for c in campos:
            if c not in item:
                raise ErroFontes(f"{rotulo}: chave '{c}' ausente")
            if not isinstance(item[c], str):
                raise ErroFontes(f"{rotulo}: '{c}' deve ser texto")
        if not extra_ok:
            for c in item:
                if c not in campos:
                    raise ErroFontes(f"{rotulo}: chave desconhecida '{c}'")


def _validar_cadastro(dados: dict) -> tuple[list[dict], list[dict]]:
    if type(dados.get("versao")) is not int or dados["versao"] != VERSAO_CATALOGO:
        raise ErroFontes(f"'versao' deve ser {VERSAO_CATALOGO}")
    fontes = dados.get("fonte")
    if not isinstance(fontes, list) or not fontes:
        raise ErroFontes("nenhum [[fonte]] cadastrado")
    _validar_tabelas(fontes, "fonte", CAMPOS_FONTE)
    stems = [f["stem"] for f in fontes]
    for s in stems:
        if stems.count(s) > 1:
            raise ErroFontes(f"stem duplicado: '{s}'")
    for f in fontes:
        if not RE_DATA_ISO.match(f["data_referencia"]):
            raise ErroFontes(f"[[fonte]] {f['stem']}: data_referencia deve ser AAAA-MM-DD")
    esperados = dados.get("esperado", [])
    if not isinstance(esperados, list):
        raise ErroFontes("[[esperado]] mal formado")
    _validar_tabelas(esperados, "esperado", CAMPOS_ESPERADO)
    for e in esperados:
        if e["fonte"] not in stems:
            raise ErroFontes(f"[[esperado]] {e['artefato']}: fonte '{e['fonte']}' não está em [[fonte]]")
    return (sorted(fontes, key=lambda f: f["stem"]),
            sorted(esperados, key=lambda e: e["artefato"]))


def carregar_fontes(raiz: Path) -> tuple[list[dict], list[dict]]:
    caminho = raiz / "catalogo" / "fontes.toml"
    try:
        with open(caminho, "rb") as fh:
            dados = tomllib.load(fh)
    except FileNotFoundError:
        raise ErroFontes("arquivo ausente")
    except tomllib.TOMLDecodeError as e:
        raise ErroFontes(f"TOML inválido: {e}")
    return _validar_cadastro(dados)


# ---------------------------------------------------------------- utilidades

class _Hashes:
    """SHA-256 de arquivos, calculado uma vez por caminho."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def de(self, caminho: Path) -> str:
        chave = str(caminho)
        if chave not in self._cache:
            self._cache[chave] = hashlib.sha256(caminho.read_bytes()).hexdigest()
        return self._cache[chave]


def _contrato_res(erros) -> dict:
    return {"valido": not erros, "n_erros": len(erros)}


def _distintos(registros: list, campo: str) -> list:
    valores = {r[campo] for r in registros
               if isinstance(r, dict) and r.get(campo) not in (None, "")}
    return sorted(valores, key=lambda v: (isinstance(v, str), v))


def _lista(valor) -> list:
    return [] if valor is None else [valor]


def _ler_anteriores(raiz: Path) -> dict[str, dict]:
    """Artefatos do catalogo.json em disco (para herdar o status do verificador)."""
    caminho = raiz / SAIDA_JSON
    if not caminho.is_file():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {a["caminho"]: a for a in dados.get("artefatos", []) if isinstance(a, dict) and "caminho" in a}


def _resumo_saida(raiz: Path, stem: str) -> str:
    pasta = raiz / "saida" / stem
    if not pasta.is_dir():
        return f"saida/{stem}: ausente"
    paginas = [p for p in pasta.glob("pagina_*.txt") if re.fullmatch(r"pagina_\d+\.txt", p.name)]
    tabelas = list(pasta.glob("tabela_*.csv"))
    return f"saida/{stem}: {len(paginas)} páginas de texto, {len(tabelas)} tabelas"


# ---------------------------------------------------------------- coleta

def _fontes(raiz: Path, fontes_toml: list[dict], hashes: _Hashes) -> list[dict]:
    saida = []
    for f in fontes_toml:
        pdf = raiz / f["pdf"]
        presente = pdf.is_file()
        registro = {k: f[k] for k in CAMPOS_FONTE}
        registro["presente"] = presente
        registro["sha256"] = hashes.de(pdf) if presente else None
        registro["bytes"] = pdf.stat().st_size if presente else None
        saida.append(registro)
    return saida


def _ler_meta(raiz: Path, nome_json: str) -> tuple[dict | None, str | None]:
    """Meta do JSON principal (balanco_x.json -> balanco_x.meta.json), ou (None, None)."""
    nome_meta = nome_json[:-len(".json")] + ".meta.json"
    if not (raiz / "metricas" / nome_meta).is_file():
        return None, None
    return contrato.ler_json(raiz / "metricas" / nome_meta), f"metricas/{nome_meta}"


def _falhas(meta: dict) -> list[str]:
    return sorted({v["id"] for v in meta.get("validacoes", [])
                   if isinstance(v, dict) and v.get("severidade") == "erro" and v.get("ok") is False})


def _art_meta(raiz: Path, nome: str) -> dict:
    caminho = raiz / "metricas" / nome
    erros = contrato.validar_arquivo(caminho, "balanco_meta")
    return {
        "caminho": f"metricas/{nome}",
        "tipo": "meta",
        "schema": "balanco_meta",
        "derivado_de": f"metricas/{nome[:-len('.meta.json')]}.json",
        "contrato": _contrato_res(erros),
    }


def _art_csv(raiz: Path, nome: str, hashes: _Hashes) -> dict:
    return {
        "caminho": f"metricas/{nome}",
        "tipo": "csv",
        "derivado_de": f"metricas/{nome[:-len('.csv')]}.json",
        "sha256": hashes.de(raiz / "metricas" / nome),
    }


def _fonte_do_json(nome: str, meta: dict | None, caminho: str, esperados: list[dict],
                   fontes_toml: list[dict]) -> str | None:
    if meta and meta.get("pdf"):
        return Path(meta["pdf"]).stem
    for e in esperados:
        if e["artefato"] == caminho:
            return e["fonte"]
    for f in fontes_toml:
        if f["empresa"] and f["empresa"] in nome:
            return f["stem"]
    return None


def _verificador(raiz: Path, caminho: str, arquivo: Path, fonte: str | None, sha: str,
                 anteriores: dict, info: dict) -> tuple[dict, str]:
    """Retorna (registro do verificador, origem: calculado | herdado | não verificado)."""
    if fonte is None:
        return ({"status": "não verificado (fonte desconhecida)", "ok": None, "total": None,
                 "texto": None, "json_sha256": sha}, "não verificado")
    pasta = raiz / "saida" / fonte
    texto = f"saida/{fonte}"
    if pasta.is_dir():
        try:
            r = verificar_numeros.verificar(pasta, arquivo)
        except verificar_numeros.ErroEntrada as e:
            info["mensagens"][caminho] = str(e)
            return ({"status": "erro de entrada (ver terminal)", "ok": None, "total": None,
                     "texto": texto, "json_sha256": sha}, "calculado")
        if r.erros_contrato:
            status, ok, total = f"fora do contrato ({len(r.erros_contrato)} erro(s))", None, None
        else:
            status = f"{r.n_ok}/{r.n_total} conferem"
            if r.n_avisos:
                status += f", {r.n_avisos} aviso(s)"
            ok, total = r.n_ok, r.n_total
        return ({"status": status, "ok": ok, "total": total, "texto": texto,
                 "json_sha256": sha}, "calculado")
    anterior = anteriores.get(caminho)
    if anterior and isinstance(anterior.get("verificador"), dict) \
            and anterior["verificador"].get("json_sha256") == sha:
        return dict(anterior["verificador"]), "herdado"
    return ({"status": "não verificado (saida/ ausente)", "ok": None, "total": None,
             "texto": None, "json_sha256": sha}, "não verificado")


def _art_json(raiz: Path, nome: str, esperados: list[dict], fontes_toml: list[dict],
              hashes: _Hashes, anteriores: dict, info: dict) -> dict:
    caminho_abs = raiz / "metricas" / nome
    caminho = f"metricas/{nome}"
    dados = contrato.ler_json(caminho_abs)
    schema = contrato.escolher_schema(dados)
    erros = contrato.validar(dados, schema)
    sha = hashes.de(caminho_abs)
    meta, caminho_meta = _ler_meta(raiz, nome)
    registros = dados if isinstance(dados, list) else []
    fonte = _fonte_do_json(nome, meta, caminho, esperados, fontes_toml)

    defasada = None
    if meta:
        pdf_meta = raiz / meta["pdf"] if meta.get("pdf") else None
        if pdf_meta is not None and pdf_meta.is_file():
            defasada = meta.get("pdf_sha256") != hashes.de(pdf_meta)
        registro = {
            "gerado_por": f"{meta.get('script')} {meta.get('versao_script')}",
            "empresa": meta.get("empresa"),
            "visao": _lista(meta.get("visao")),
            "unidade": _lista(meta.get("unidade")),
            "escala_original": meta.get("escala_original"),
            "paginas": meta.get("paginas"),
            "data_atual": meta.get("data_atual"),
            "data_anterior": meta.get("data_anterior"),
            "n_contas": meta.get("n_contas"),
            "n_ambiguos": meta.get("n_ambiguos"),
            "autovalidacao": {"status": meta.get("status"), "falhas": _falhas(meta)},
        }
    else:
        registro = {
            "gerado_por": GERADO_POR_SEM_META,
            "empresa": None,
            "visao": _distintos(registros, "visao"),
            "unidade": _distintos(registros, "unidade"),
            "escala_original": None,
            "paginas": _distintos(registros, "pagina"),
            "data_atual": None,
            "data_anterior": None,
            "n_contas": None,
            "n_ambiguos": None,
            "autovalidacao": None,
        }

    if schema == "balanco":
        criterio = "n/a"
    else:
        ebitda = [r for r in registros
                  if isinstance(r, dict) and isinstance(r.get("metrica"), str)
                  and RE_EBITDA.search(r["metrica"])]
        valores = _distintos(ebitda, "criterio_ebitda")
        criterio = valores if valores else "não informado"

    verificador, origem = _verificador(raiz, caminho, caminho_abs, fonte, sha, anteriores, info)
    info["origens"][caminho] = origem

    return {
        "caminho": caminho,
        "tipo": schema,
        "schema": schema,
        "contrato": _contrato_res(erros),
        "sha256": sha,
        "n_registros": len(dados) if isinstance(dados, list) else None,
        "fonte": fonte,
        "fonte_defasada": defasada,
        "meta": caminho_meta,
        "gerado_por": registro["gerado_por"],
        "empresa": registro["empresa"],
        "visao": registro["visao"],
        "unidade": registro["unidade"],
        "escala_original": registro["escala_original"],
        "paginas": registro["paginas"],
        "data_atual": registro["data_atual"],
        "data_anterior": registro["data_anterior"],
        "base_comparacao": _distintos(registros, "base_comparacao"),
        "n_contas": registro["n_contas"],
        "n_ambiguos": registro["n_ambiguos"],
        "autovalidacao": registro["autovalidacao"],
        "verificador": verificador,
        "criterio_ebitda": criterio,
    }


def _artefatos(raiz: Path, esperados: list[dict], fontes_toml: list[dict],
               hashes: _Hashes, anteriores: dict, info: dict) -> list[dict]:
    pasta = raiz / "metricas"
    if not pasta.is_dir():
        return []
    saida = []
    for nome in sorted(p.name for p in pasta.iterdir() if p.is_file()):
        if nome in (".gitkeep", "catalogo.json"):
            continue
        if nome.endswith(".meta.json"):
            saida.append(_art_meta(raiz, nome))
        elif nome.endswith(".csv"):
            saida.append(_art_csv(raiz, nome, hashes))
        elif nome.endswith(".json"):
            saida.append(_art_json(raiz, nome, esperados, fontes_toml,
                                   hashes, anteriores, info))
    return saida


def _pendentes(raiz: Path, esperados: list[dict]) -> list[dict]:
    return [{"artefato": e["artefato"], "fonte": e["fonte"], "descricao": e["descricao"],
             "status": "pendente"}
            for e in esperados if not (raiz / e["artefato"]).exists()]


def _coletar(raiz: Path) -> tuple[dict, dict]:
    fontes_toml, esperados = carregar_fontes(raiz)
    hashes = _Hashes()
    fontes = _fontes(raiz, fontes_toml, hashes)
    anteriores = _ler_anteriores(raiz)
    info = {"origens": {}, "mensagens": {}}
    artefatos = _artefatos(raiz, esperados, fontes_toml, hashes, anteriores, info)
    cat = {
        "versao_catalogo": VERSAO_CATALOGO,
        "gerado_por": GERADO_POR,
        "aviso": AVISO_JSON,
        "fontes": fontes,
        "artefatos": artefatos,
        "pendentes": _pendentes(raiz, esperados),
    }
    return cat, info


def coletar(raiz: Path) -> dict:
    """Estrutura do catálogo (SPEC §10.4). Determinística: nada de data, hora ou caminho absoluto."""
    return _coletar(Path(raiz))[0]


# ---------------------------------------------------------------- renderização

def render_json(cat: dict) -> str:
    return json.dumps(cat, ensure_ascii=False, indent=2) + "\n"


def _c(valor) -> str:
    """Célula de tabela: escapa '|' e trata vazio."""
    if valor is None or valor == "":
        return PLACEHOLDER
    return str(valor).replace("|", "\\|")


def _data(iso: str | None) -> str:
    if not iso:
        return PLACEHOLDER
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


def _autovalidacao(av: dict | None) -> str:
    if av is None:
        return "—"
    if av.get("falhas"):
        return f"reprovado ({', '.join(av['falhas'])})"
    return str(av.get("status"))


def _paginas(p) -> str:
    if isinstance(p, dict):
        return "; ".join(", ".join(str(x) for x in v) for v in p.values())
    if isinstance(p, list):
        return ", ".join(str(x) for x in p)
    return PLACEHOLDER


def _celula_fonte(stem: str | None, defasada, fontes_por_stem: dict) -> str:
    if stem is None:
        return PLACEHOLDER
    f = fontes_por_stem.get(stem)
    if defasada is True:
        return f"{stem} — DEFASADO (meta aponta outro PDF)"
    if f is not None and not f["presente"]:
        return f"{stem} — PDF ausente"
    return stem


def _celula_contrato(c: dict) -> str:
    return "válido" if c["valido"] else f"fora do contrato ({c['n_erros']})"


def render_markdown(cat: dict) -> str:
    fontes_por_stem = {f["stem"]: f for f in cat["fontes"]}
    L: list[str] = []
    L.append("# Catálogo de dados — Case 3 (Gerdau × Usiminas, 3T26)")
    L.append("")
    L.append("> Gerado por `python src/gerar_catalogo.py`. Não edite à mão; `python src/gerar_catalogo.py --check` diz se está em dia.")
    L.append("> Versão estruturada: [`metricas/catalogo.json`](../metricas/catalogo.json). Cadastro manual: [`catalogo/fontes.toml`](../catalogo/fontes.toml).")
    L.append("> **Autovalidação do extrator** (V01–V08, `status` do `.meta.json`) ≠ **verificador** (`verificar_numeros.py`: contrato + conferência contra `saida/<pdf>/`).")
    L.append("")

    L.append("## Fontes")
    L.append("| PDF | Empresa | Tipo | Período | Data-base | SHA-256 | Tamanho | Origem |")
    L.append("|---|---|---|---|---|---|---|---|")
    for f in cat["fontes"]:
        sha = f["sha256"][:12] if f["sha256"] else "ausente"
        tamanho = (f"{f['bytes'] / 1_000_000:.1f}".replace(".", ",")
                   if f["bytes"] is not None else "ausente")
        L.append(f"| {_c(f['pdf'])} | {_c(f['nome'])} | {_c(f['tipo'])} | {_c(f['periodo'])} "
                 f"| {_data(f['data_referencia'])} | {sha} | {tamanho} | {_c(f['url_origem'])} |")
    L.append("")

    L.append("## Artefatos verificáveis")
    L.append("| Artefato | Visão | Unidade (escala original) | Páginas (Ativo; Passivo) | Registros (ambíguos) | Datas | Gerado por | Contrato | Autovalidação do extrator | Verificador | EBITDA | Fonte |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for a in cat["artefatos"]:
        if a["tipo"] not in TIPOS_VERIFICAVEIS:
            continue
        unidade = ", ".join(a["unidade"])
        if a["escala_original"]:
            unidade = f"{unidade} ({a['escala_original']})" if unidade else a["escala_original"]
        if a["n_registros"] is None:
            registros = PLACEHOLDER
        elif a["n_ambiguos"] is not None:
            registros = f"{a['n_registros']} ({a['n_ambiguos']})"
        else:
            registros = str(a["n_registros"])
        datas = (f"{_data(a['data_atual'])} × {_data(a['data_anterior'])}"
                 if a["data_atual"] else PLACEHOLDER)
        ebitda = a["criterio_ebitda"]
        ebitda = ebitda if isinstance(ebitda, str) else (", ".join(ebitda) or PLACEHOLDER)
        L.append(f"| {_c(a['caminho'])} | {_c(', '.join(a['visao']))} | {_c(unidade)} "
                 f"| {_c(_paginas(a['paginas']))} | {registros} | {datas} | {_c(a['gerado_por'])} "
                 f"| {_celula_contrato(a['contrato'])} | {_c(_autovalidacao(a['autovalidacao']))} "
                 f"| {_c(a['verificador']['status'])} | {_c(ebitda)} "
                 f"| {_c(_celula_fonte(a['fonte'], a['fonte_defasada'], fontes_por_stem))} |")
    L.append("")

    L.append("## Arquivos auxiliares")
    L.append("| Arquivo | Tipo | Derivado de | Contrato |")
    L.append("|---|---|---|---|")
    for a in cat["artefatos"]:
        if a["tipo"] == "meta":
            L.append(f"| {_c(a['caminho'])} | meta | {_c(a['derivado_de'])} | {_celula_contrato(a['contrato'])} |")
        elif a["tipo"] == "csv":
            L.append(f"| {_c(a['caminho'])} | csv | {_c(a['derivado_de'])} | — |")
    L.append("")

    L.append("## Pendentes")
    if cat["pendentes"]:
        L.append("| Artefato esperado | Fonte | Descrição | Status |")
        L.append("|---|---|---|---|")
        for p in cat["pendentes"]:
            L.append(f"| {_c(p['artefato'])} | {_c(p['fonte'])} | {_c(p['descricao'])} | {p['status']} |")
    else:
        L.append("Nenhum.")
    L.append("")

    L.append("## Intermediários não versionados")
    L.append("- `saida/<stem>/`: texto por página (`pagina_NN.txt`) e tabelas, gerados por `src/extrair_release.py`; ficam fora do Git e por isso fora deste catálogo (o gerador mostra a contagem no terminal).")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- CLI

def _checar(raiz: Path, cat: dict) -> list[str]:
    desatualizados = []
    for rel, texto in ((SAIDA_MD, render_markdown(cat)), (SAIDA_JSON, render_json(cat))):
        alvo = raiz / rel
        if not alvo.is_file():
            desatualizados.append(rel)
            continue
        with open(alvo, encoding="utf-8", newline="") as fh:
            if fh.read() != texto:
                desatualizados.append(rel)
    return desatualizados


def _gravar(raiz: Path, cat: dict) -> None:
    for rel, texto in ((SAIDA_MD, render_markdown(cat)), (SAIDA_JSON, render_json(cat))):
        alvo = raiz / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with open(alvo, "w", encoding="utf-8", newline="") as fh:
            fh.write(texto)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gerar_catalogo.py",
                                 description="Gera docs/CATALOGO_DADOS.md e metricas/catalogo.json.")
    ap.add_argument("--raiz", type=Path, default=RAIZ,
                    help="raiz do repositório (padrão: a deste script; usado pelos testes)")
    ap.add_argument("--check", action="store_true",
                    help="não grava; retorna 1 se os arquivos gerados estiverem defasados")
    args = ap.parse_args(argv)
    raiz = args.raiz.resolve()

    try:
        cat, info = _coletar(raiz)
    except ErroFontes as e:
        print(f"ERRO: catalogo/fontes.toml: {e}", file=sys.stderr)
        return 2
    except ErroLeitura as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2

    if args.check:
        desatualizados = _checar(raiz, cat)
        for rel in desatualizados:
            print(f"desatualizado: {rel} (rode: python src/gerar_catalogo.py)")
        if desatualizados:
            return 1
        print("catálogo em dia")
        return 0

    _gravar(raiz, cat)
    print(f"→ {SAIDA_MD} · {SAIDA_JSON}")
    for f in cat["fontes"]:
        print(_resumo_saida(raiz, f["stem"]))
    for a in cat["artefatos"]:
        if a["tipo"] in TIPOS_VERIFICAVEIS:
            print(f"  {a['caminho']}: {a['verificador']['status']} [{info['origens'][a['caminho']]}]")
    for caminho, msg in info["mensagens"].items():
        print(f"  {caminho}: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
