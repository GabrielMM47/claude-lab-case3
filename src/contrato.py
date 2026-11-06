"""
Case 3 — CONTRATO de dados dos JSONs de métricas.

Valida um JSON contra os schemas de `schemas/` (JSON Schema 2020-12) e devolve
os erros em português, com o caminho do campo (`$[3].pagina`). O schema confere
forma e tipos; a literalidade do trecho e a conta dos números ficam com o
`gerar_catalogo.py` e pela CLI abaixo (o verificar_numeros.py é do CASE-02 e não o chama).

    python src/contrato.py ARQUIVO [ARQUIVO ...] [--schema {auto,metricas,balanco,balanco_meta,fato,comparativo,indicadores}]

Com `auto` (padrão), `*.meta.json` usa `balanco_meta`; os demais usam
`escolher_schema` (dict com `linhas` e `empresas` → `comparativo`; dict com `indicadores` →
`indicadores`; item com `chave` → `fato`;
com `demonstracao` → `balanco`; senão `metricas`).

Também expõe `fmt_br` e `fmt_var`, a formatação pt-BR de valores e variações usada pelo
comparativo (CASE-05) e pelos gráficos.
Código de saída: 0 = todos válidos; 2 = algum inválido, ilegível ou uso inválido.
Os schemas são resolvidos localmente (sem rede).
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import referencing

RAIZ = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = RAIZ / "schemas"
SCHEMAS: dict[str, str] = {
    "metricas": "metricas.schema.json",
    "balanco": "balanco.schema.json",
    "balanco_meta": "balanco_meta.schema.json",
    "fato": "fato.schema.json",
    "comparativo": "comparativo.schema.json",
    "indicadores": "indicadores.schema.json",
}
LIMITE_LINHAS = 50

_NOMES_TIPO = {
    "number": "número",
    "integer": "inteiro",
    "string": "texto",
    "boolean": "booleano",
    "array": "lista",
    "object": "objeto",
    "null": "null",
}


@dataclass(frozen=True)
class ErroContrato:
    caminho: str
    mensagem: str

    def __str__(self) -> str:
        return f"{self.caminho}: {self.mensagem}"


class ErroLeitura(Exception):
    """Arquivo ausente ou JSON sintaticamente inválido (mensagem pronta, pt-BR)."""


# --------------------------------------------------------------------------- schemas

def carregar_schema(nome: str) -> dict:
    """Lê schemas/<nome>.schema.json. KeyError se o nome não é conhecido."""
    arquivo = SCHEMAS[nome]
    return json.loads((SCHEMAS_DIR / arquivo).read_text(encoding="utf-8"))


@functools.cache
def _registry() -> referencing.Registry:
    recursos = []
    for nome in SCHEMAS:
        schema = carregar_schema(nome)
        recursos.append((schema["$id"], referencing.Resource.from_contents(schema)))
    return referencing.Registry().with_resources(recursos)


@functools.cache
def validador(nome: str) -> jsonschema.Draft202012Validator:
    """Validador (com cache) do schema `nome`, com os 3 schemas num registry local."""
    schema = carregar_schema(nome)
    return jsonschema.Draft202012Validator(schema, registry=_registry())


def escolher_schema(dados: Any) -> str:
    """'comparativo' se é um dict com 'linhas' e 'empresas' (saída do CASE-05); 'indicadores' se é
    um dict com 'indicadores' (saída do CASE-04); 'fato' se algum item tem 'chave' (contrato do
    time, docs/TAREFAS.md); 'balanco' se algum item tem 'demonstracao'; senão 'metricas'."""
    if isinstance(dados, dict) and "linhas" in dados and "empresas" in dados:
        return "comparativo"
    if isinstance(dados, dict) and "indicadores" in dados:
        return "indicadores"
    if isinstance(dados, list) and any(isinstance(m, dict) and "chave" in m for m in dados):
        return "fato"
    if isinstance(dados, list) and any(isinstance(m, dict) and "demonstracao" in m for m in dados):
        return "balanco"
    return "metricas"


# --------------------------------------------------------------------------- formatação pt-BR

# status (legenda do CASE-04) -> texto exibido no lugar do número
TEXTO_STATUS = {"ausente": "N/D", "nao_comparavel": "N/C", "nao_aplicavel": "N/A"}

# unidade -> (casas padrão, prefixo, sufixo)
_FORMATOS: dict[str, tuple[int, str, str]] = {
    "R$ milhões": (1, "R$ ", " mi"),
    "R$ mil": (0, "R$ ", " mil"),
    "%": (1, "", "%"),
    "p.p.": (1, "", " p.p."),
    "x": (2, "", "x"),
    "mil t": (0, "", " mil t"),
    "mil t/ano": (0, "", " mil t/ano"),
    "R$/t": (0, "R$ ", "/t"),
    "US$/t": (0, "US$ ", "/t"),
}


def _numero_br(valor: float, casas: int) -> str:
    """Módulo do número com milhar '.' e decimal ',' (sem sinal)."""
    texto = f"{abs(valor):,.{casas}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _invalido(valor: Any) -> bool:
    return valor is None or isinstance(valor, bool) or not math.isfinite(float(valor))


def fmt_br(valor: float | None, unidade: str | None, casas: int | None = None, status: str = "ok") -> str:
    """Valor formatado em pt-BR conforme a unidade (`R$ 15.000,0 mi`, `16,0%`, `0,57x`...).

    status != "ok" -> "N/D"/"N/C"/"N/A" (status desconhecido -> "N/D"); valor None/NaN -> "N/D".
    Negativo leva '-' ASCII antes de tudo (`-R$ 300,0 mi`); zero arredondado nunca vira '-0'.
    """
    if status != "ok":
        return TEXTO_STATUS.get(status, "N/D")
    if _invalido(valor):
        return "N/D"
    padrao, prefixo, sufixo = _FORMATOS.get(unidade or "", (1, "", f" {unidade}" if unidade else ""))
    casas = padrao if casas is None else casas
    numero = _numero_br(valor, casas)
    sinal = "-" if valor < 0 and round(abs(valor), casas) != 0 else ""
    return f"{sinal}{prefixo}{numero}{sufixo}"


def fmt_var(valor: float | None, unidade_var: str | None, casas: int = 1) -> str:
    """Variação com sinal explícito (`+5,6%`, `-4,8%`, `+6,0 p.p.`); None/NaN -> "—".

    Zero arredondado sai sem sinal (`0,0%`). `x` cola no número; outras unidades vão após espaço.
    """
    if _invalido(valor):
        return "—"
    numero = _numero_br(valor, casas)
    if round(abs(valor), casas) == 0:
        sinal = ""
    else:
        sinal = "+" if valor > 0 else "-"
    if unidade_var in ("%", "x"):
        sufixo = unidade_var
    elif unidade_var:
        sufixo = f" {unidade_var}"
    else:
        sufixo = ""
    return f"{sinal}{numero}{sufixo}"


# --------------------------------------------------------------------------- catálogo de fatos

# chave -> {nome, tipo (fluxo|saldo|None = depende do fato), codigo_cvm (None quando não há
# código fixo), origem (card dono)}. Fonte: docs/TAREFAS.md, "Catálogo de chaves de fatos".
# Chave nova entra aqui no PR de quem precisa dela (único ponto de conflito previsto).
def _f(nome: str, tipo: str | None, codigo: str | None, origem: str) -> dict:
    return {"nome": nome, "tipo": tipo, "codigo_cvm": codigo, "origem": origem}


CATALOGO_FATOS: dict[str, dict] = {
    # DFs padronizadas CVM, consolidado (CASE-02, *_itr_dfs.json)
    "receita_liquida": _f("Receita líquida", "fluxo", "3.01", "CASE-02"),
    "cpv": _f("Custo dos produtos vendidos", "fluxo", "3.02", "CASE-02"),
    "lucro_bruto": _f("Lucro bruto", "fluxo", "3.03", "CASE-02"),
    "despesas_receitas_operacionais": _f("Despesas/receitas operacionais", "fluxo", "3.04", "CASE-02"),
    "ebit": _f("EBIT", "fluxo", "3.05", "CASE-02"),
    "resultado_financeiro": _f("Resultado financeiro", "fluxo", "3.06", "CASE-02"),
    "lair": _f("Lucro antes do IR/CSLL", "fluxo", "3.07", "CASE-02"),
    "ir_csll": _f("IR e CSLL", "fluxo", "3.08", "CASE-02"),
    "lucro_liquido": _f("Lucro líquido consolidado", "fluxo", "3.11", "CASE-02"),
    "lucro_liquido_controladores": _f("Lucro líquido dos controladores", "fluxo", "3.11.01", "CASE-02"),
    "ativo_total": _f("Ativo total", "saldo", "1", "CASE-02"),
    "passivo_total": _f("Passivo total", "saldo", "2", "CASE-02"),
    "caixa_equivalentes": _f("Caixa e equivalentes", "saldo", "1.01.01", "CASE-02"),
    "aplicacoes_financeiras": _f("Aplicações financeiras", "saldo", "1.01.02", "CASE-02"),
    "emprestimos_cp": _f("Empréstimos e financiamentos CP", "saldo", "2.01.04", "CASE-02"),
    "emprestimos_lp": _f("Empréstimos e financiamentos LP", "saldo", "2.02.01", "CASE-02"),
    "pl_total": _f("Patrimônio líquido consolidado", "saldo", "2.03", "CASE-02"),
    "pl_nao_controladores": _f("PL de não controladores", "saldo", None, "CASE-02"),
    "depreciacao_amortizacao": _f("Depreciação e amortização (DFC)", "fluxo", None, "CASE-02"),
    "fco": _f("Fluxo de caixa operacional", "fluxo", "6.01", "CASE-02"),
    "capex": _f("Capex (imobilizado)", "fluxo", None, "CASE-02"),
    # Complementares do ITR/release (CASE-02, *_itr_complementar.json)
    "ebitda_contabil": _f("EBITDA contábil (Res. CVM 156)", "fluxo", None, "CASE-02"),
    "ebitda_ajustado": _f("EBITDA ajustado", "fluxo", None, "CASE-02"),
    "ajuste_ebitda": _f("Ajuste do EBITDA", "fluxo", None, "CASE-02"),
    "depreciacao_amortizacao_tri": _f("D&A do trimestre", "fluxo", None, "CASE-02"),
    "divida_bruta_reportada": _f("Dívida bruta reportada", "saldo", None, "CASE-02"),
    "divida_liquida_reportada": _f("Dívida líquida reportada", "saldo", None, "CASE-02"),
    "dl_ebitda_reportado": _f("Dívida líquida/EBITDA reportado", "saldo", None, "CASE-02"),
    # Operacionais e por segmento (CASE-03, *_operacional.json)
    "volume_vendas": _f("Volume de vendas", "fluxo", None, "CASE-03"),
    "volume_producao": _f("Volume de produção de aço bruto", "fluxo", None, "CASE-03"),
    "capacidade_instalada": _f("Capacidade instalada", "saldo", None, "CASE-03"),
    "receita_por_t_reportada": _f("Receita por tonelada reportada", "fluxo", None, "CASE-03"),
    "custo_por_t_reportado": _f("Custo por tonelada reportado", "fluxo", None, "CASE-03"),
    "ebitda_por_t_reportado": _f("EBITDA por tonelada reportado", "fluxo", None, "CASE-03"),
    "volume_minerio": _f("Volume de minério", "fluxo", None, "CASE-03"),
    "participacao_exportacao": _f("Participação da exportação", "fluxo", None, "CASE-03"),
    # Qualitativo (CASE-03, *_apresentacao_qualitativo.json)
    "qualitativo": _f("Tema qualitativo", None, None, "CASE-03"),
    # Contexto macro e setorial citado pela própria empresa (*_<doc>_macro.json): importações,
    # defesa comercial, tarifas, demanda, preços de insumos. Número com `id` estável, que a
    # narrativa cita como {a.macro.<id>}. Afirmação sem número vai como `qualitativo` com tema
    # `contexto_macro` no mesmo arquivo. Fica fora dos indicadores (não é resultado da empresa).
    "contexto_macro": _f("Contexto macro/setorial citado pela empresa", None, None, "macro"),
}

DOCUMENTOS = ("itr", "apresentacao")
TEMAS_QUALITATIVOS = ("perfil", "capacidade_footprint", "mercados_produtos", "estrategia",
                      "capex_investimentos", "guidance_perspectivas", "riscos", "esg",
                      "destaques_trimestre", "contexto_macro")
# chaves que só alimentam os slides (texto e contexto); os indicadores (CASE-04) ignoram
CHAVES_SO_CONTEXTO = ("qualitativo", "contexto_macro")
RE_PERIODO = re.compile(r"^(?:([1-4])T|(\d{1,2})M)(\d{2})$")

_FATOR_MILHOES = {"r$ mil": 1e-3, "r$ milhões": 1.0, "r$ milhoes": 1.0, "r$ milhão": 1.0,
                  "r$ milhao": 1.0, "r$ bilhões": 1e3, "r$ bilhoes": 1e3, "r$ bilhão": 1e3,
                  "r$ bilhao": 1e3}


def validar_fato(d: Any) -> list[str]:
    """Erros de um fato do contrato (docs/TAREFAS.md); [] = válido.

    Confere a forma pelo schema `fato` (campos obrigatórios, tipos, `pagina` >= 1, `trecho`...)
    e acrescenta o que o schema não sabe: chave no catálogo, período e escopo válidos, tema
    qualitativo conhecido. Mensagens em pt-BR com o caminho do campo (`$.pagina: ...`).
    """
    if not isinstance(d, dict):
        return [f"$: esperado objeto, veio {_tipo_py(d)}"]
    erros = [str(e) for e in validar([d], "fato")]
    erros = [e.replace("$[0]", "$", 1) for e in erros]
    chave = d.get("chave")
    if isinstance(chave, str) and chave not in CATALOGO_FATOS:
        erros.append(f"$.chave: {_json(chave)} fora do catálogo (contrato.CATALOGO_FATOS)")
    # padrão de `periodo` e `escopo` já vem do schema; aqui só o que regex não cobre
    periodo = d.get("periodo")
    m = RE_PERIODO.match(periodo) if isinstance(periodo, str) else None
    if m and m.group(2) and not 1 <= int(m.group(2)) <= 12:
        erros.append(f"$.periodo: {_json(periodo)} com meses fora de 1..12")
    if chave == "qualitativo" and d.get("tema") not in TEMAS_QUALITATIVOS:
        erros.append(f"$.tema: {_json(d.get('tema'))} fora da lista: {', '.join(TEMAS_QUALITATIVOS)}")
    return sorted(dict.fromkeys(erros))


def carregar_fatos(slug: str, tri: str, pasta: str | Path = "metricas") -> list[dict]:
    """Junta os fatos de todos os `{pasta}/{slug}_{tri}_*.json`, menos o `_indicadores`.

    Ordem estável (nome do arquivo). Não valida: rode `validar_fato` ou a CLI antes do uso.
    """
    fatos: list[dict] = []
    for arquivo in sorted(Path(pasta).glob(f"{slug}_{tri}_*.json")):
        if arquivo.stem.endswith("_indicadores"):
            continue
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        if not isinstance(dados, list):
            raise ValueError(f"{arquivo}: esperado lista de fatos, veio {_tipo_py(dados)}")
        fatos.extend(dados)
    return fatos


def para_milhoes(valor: float, unidade: str) -> float:
    """Valor monetário em R$ milhões: `R$ mil` ÷1000, `R$ milhões` ×1, `R$ bilhões` ×1000.

    Unidade desconhecida (inclusive não monetária) → ValueError; nunca adivinhar escala.
    """
    chave = " ".join(str(unidade or "").lower().split())
    if chave not in _FATOR_MILHOES:
        raise ValueError(f"unidade monetária desconhecida: {unidade!r}")
    return valor * _FATOR_MILHOES[chave]


def periodo_comparavel(tri: str, base: str) -> str:
    """Período de comparação: `aa` (A/A) → mesmo período do ano anterior; `tt` (T/T) → trimestre
    anterior. `3T26` → `3T25` / `2T26`; `1T26` tt → `4T25`; `9M26` aa → `9M25` (tt não existe)."""
    m = RE_PERIODO.match(tri or "")
    if not m:
        raise ValueError(f"período inválido: {tri!r}")
    trimestre, meses, ano = m.group(1), m.group(2), int(m.group(3))
    if base == "aa":
        return f"{trimestre}T{ano - 1:02d}" if trimestre else f"{meses}M{ano - 1:02d}"
    if base == "tt":
        if not trimestre:
            raise ValueError(f"T/T só existe para trimestres, não para {tri!r}")
        t = int(trimestre)
        return f"{t - 1}T{ano:02d}" if t > 1 else f"4T{ano - 1:02d}"
    raise ValueError(f"base de comparação inválida: {base!r} (use 'aa' ou 'tt')")


def pasta_saida(slug: str, tri: str, documento: str, raiz: str | Path = "saida") -> Path:
    """Pasta com os `pagina_NN.txt` do documento: `saida/<slug>_ITR_<tri>` ou
    `saida/<slug>_APRESENTACAO_<tri>`."""
    if documento not in DOCUMENTOS:
        raise ValueError(f"documento inválido: {documento!r} (use {' ou '.join(DOCUMENTOS)})")
    return Path(raiz) / f"{slug}_{documento.upper()}_{tri}"


# --------------------------------------------------------------------------- mensagens

def _json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False)


def _tipo_py(valor: Any) -> str:
    if valor is None:
        return "null"
    if isinstance(valor, bool):
        return "booleano"
    if isinstance(valor, int):
        return "inteiro"
    if isinstance(valor, float):
        return "número"
    if isinstance(valor, str):
        return "texto"
    if isinstance(valor, list):
        return "lista"
    if isinstance(valor, dict):
        return "objeto"
    return type(valor).__name__


def _caminho(partes: list) -> str:
    return "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in partes)


def _traduzir(e: jsonschema.ValidationError) -> list[tuple[list, str]]:
    """Converte um ValidationError em pares (partes do caminho, mensagem pt-BR)."""
    partes = list(e.absolute_path)
    v, valor, regra = e.validator, e.instance, e.validator_value

    if v == "required":
        saida = []
        for campo in regra:
            if isinstance(valor, dict) and campo in valor:
                continue
            if campo == "criterio_ebitda":
                msg = "métrica de EBITDA exige 'criterio_ebitda' (\"contábil\" ou \"ajustado\")"
            else:
                msg = "campo obrigatório ausente"
            saida.append((partes + [campo], msg))
        return saida
    if v == "dependentRequired":
        saida = []
        if isinstance(valor, dict):
            for campo, deps in regra.items():
                if campo not in valor:
                    continue
                for dep in deps:
                    if dep not in valor:
                        saida.append((partes + [dep], f"campo obrigatório quando '{campo}' está presente"))
        return saida
    if v == "type":
        tipos = [regra] if isinstance(regra, str) else list(regra)
        nomes = " ou ".join(_NOMES_TIPO.get(t, t) for t in tipos)
        return [(partes, f"esperado {nomes}, veio {_tipo_py(valor)} ({_json(valor)})")]
    if v == "minimum":
        return [(partes, f"{_json(valor)} é menor que o mínimo {_json(regra)}")]
    if v == "enum":
        return [(partes, f"valor {_json(valor)} fora da lista permitida: {', '.join(_json(x) for x in regra)}")]
    if v == "const":
        return [(partes, f"valor {_json(valor)} deveria ser {_json(regra)}")]
    if v == "minLength":
        return [(partes, f"texto curto demais ({len(valor)} caractere(s); mínimo {regra})")]
    if v == "minItems":
        return [(partes, f"lista com {len(valor)} item(ns); mínimo {regra}")]
    if v == "pattern":
        return [(partes, f"valor {_json(valor)} não segue o padrão {regra}")]
    if v in ("additionalProperties", "unevaluatedProperties"):
        campos = re.findall(r"'([^']+)'", e.message)
        if not campos:
            return [(partes, e.message)]
        return [(partes + [c], "campo não previsto no contrato") for c in campos]
    if v == "not":
        return [(partes, "campo não permitido neste contrato")]
    return [(partes, e.message)]


def _chave(partes: list) -> tuple:
    return tuple((0, p, "") if isinstance(p, int) else (1, 0, str(p)) for p in partes)


# --------------------------------------------------------------------------- API

def validar(dados: Any, nome: str | None = None) -> list[ErroContrato]:
    """Erros de contrato, ordenados e sem duplicatas; [] = válido."""
    nome = nome or escolher_schema(dados)
    pares: dict[tuple[str, str], tuple] = {}
    for e in validador(nome).iter_errors(dados):
        for partes, msg in _traduzir(e):
            par = (_caminho(partes), msg)
            if par not in pares:
                pares[par] = (_chave(partes), msg)
    ordenados = sorted(pares.items(), key=lambda kv: kv[1])
    return [ErroContrato(caminho, msg) for (caminho, msg), _ in ordenados]


def ler_json(caminho: Path | str) -> Any:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroLeitura(f"arquivo não encontrado: {caminho}")
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErroLeitura(f"JSON inválido em {caminho}: linha {e.lineno}, coluna {e.colno}: {e.msg}") from e
    except UnicodeDecodeError as e:
        raise ErroLeitura(f"JSON inválido em {caminho}: não é UTF-8 ({e.reason})") from e


def validar_arquivo(caminho: Path | str, nome: str | None = None) -> list[ErroContrato]:
    return validar(ler_json(caminho), nome)


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="contrato.py",
        description="Valida JSONs de métricas/balanço/meta contra os schemas de schemas/.",
    )
    parser.add_argument("arquivos", nargs="+", metavar="ARQUIVO")
    parser.add_argument("--schema", choices=["auto", *SCHEMAS], default="auto")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)

    codigo = 0
    for arq in args.arquivos:
        if args.schema == "auto" and Path(arq).name == "catalogo.json":
            print(f"{arq}: ignorado (catálogo gerado por src/gerar_catalogo.py, sem schema)")
            continue
        try:
            dados = ler_json(arq)
        except ErroLeitura as e:
            print(f"ERRO: {e}", file=sys.stderr)
            codigo = 2
            continue
        if args.schema != "auto":
            nome = args.schema
        elif str(arq).endswith(".meta.json"):
            nome = "balanco_meta"
        else:
            nome = escolher_schema(dados)
        erros = validar(dados, nome)
        if not erros:
            print(f"{arq}: válido ({nome})")
            continue
        codigo = 2
        print(f"{arq}: {len(erros)} erro(s) ({nome})")
        for erro in erros:
            print(f"  {erro}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
