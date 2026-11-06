"""
Case 3 — CONTRATO de dados dos JSONs de métricas.

Valida um JSON contra os schemas de `schemas/` (JSON Schema 2020-12) e devolve
os erros em português, com o caminho do campo (`$[3].pagina`). O schema confere
forma e tipos; a literalidade do trecho e a conta dos números ficam com o
`verificar_numeros.py`, que chama este módulo antes de conferir.

    python src/contrato.py ARQUIVO [ARQUIVO ...] [--schema {auto,metricas,balanco,balanco_meta}]

Com `auto` (padrão), `*.meta.json` usa `balanco_meta`; os demais usam
`escolher_schema` (lista com `demonstracao` → `balanco`; senão `metricas`).
Código de saída: 0 = todos válidos; 2 = algum inválido, ilegível ou uso inválido.
Os schemas são resolvidos localmente (sem rede).
"""
from __future__ import annotations

import argparse
import functools
import json
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
    """'balanco' se for lista com algum item dict que tenha 'demonstracao'; senão 'metricas'."""
    if isinstance(dados, list) and any(isinstance(m, dict) and "demonstracao" in m for m in dados):
        return "balanco"
    return "metricas"


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
