"""
Case 3 — Comparativo de resultados · o VERIFICADOR.

A ideia: o Claude extrai os números do release para um JSON (ver
templates/metricas_exemplo.json), e este script confere cada um contra o PDF
antes que qualquer número entre na apresentação. É o passo "verificar" do loop
agêntico.

    python src/verificar_numeros.py saida/<nome_do_pdf> metricas/metricas_EMPRESA.json
        [--sem-contrato] [--schema {auto,metricas,balanco}]

Antes de conferir, valida o JSON contra o CONTRATO (schemas/*.schema.json, via
src/contrato.py). Fora do contrato: linhas [CONTRATO], nenhuma métrica é
conferida e o código de saída é 2. `--sem-contrato` pula essa etapa (só para
destravar a oficina; dispensa o jsonschema).

Para cada métrica, confere ([OK ] / [ERRO]):
  1. se o trecho citado existe na página indicada;
  2. se o valor aparece na página exatamente como no PDF (valor_como_aparece);
  3. se o valor numérico bate com o texto (pega erro de unidade e vírgula);
  4. se a variação informada bate com a recalculada a partir dos dois períodos.

Além disso, emite AVISOS ([AVISO], não mudam o código de saída): registro sem
trecho, valor_como_aparece achado na página mas fora do trecho, literal curto
de anterior_como_aparece fora do trecho, unidade fora da lista do contrato e
unidade que não aparece no trecho nem na página.

Códigos de saída: 0 = tudo confere (avisos permitidos); 1 = pelo menos um
[ERRO]; 2 = JSON fora do contrato, arquivo ausente, JSON inválido, pasta de
textos ausente, jsonschema ausente com contrato ligado ou uso inválido.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

TOLERANCIA_VAR_PP = 0.5
LIMITE_CURTO = 3
MARCADORES_UNIDADE: dict[str, str] = {
    "R$ mil": r"\bmil\b|milhares",
    "R$ milhões": r"milh",
    "%": r"%",
    "p.p.": r"\bp\.\s?p\b|pontos? percentua",
    "mil t": r"\bmil (?:t\b|ton)|\bkt\b",
    "R$/t": r"/\s?t\b|/ton|por tonelada",
    "x": r"\d\s?[x×]\b|\bvezes\b",
}


def normalizar(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()


def br_para_float(s: str) -> float:
    """'1.234,5' -> 1234.5 ; '(123,4)' -> -123.4 ; '12,3%' -> 12.3"""
    s = s.strip().replace("%", "").replace("R$", "").strip()
    negativo = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()-").replace(".", "").replace(",", ".")
    return -float(s) if negativo else float(s)


def _arquivo_pagina(m: dict, pasta: Path) -> Path | None:
    """Caminho de pagina_NN.txt; None se 'pagina' estiver ausente ou não for inteiro."""
    try:
        n = int(m["pagina"])
    except (KeyError, TypeError, ValueError):
        return None
    return pasta / f"pagina_{n:02d}.txt"


def checar(m: dict, pasta: Path) -> list[str]:
    problemas = []
    pag = _arquivo_pagina(m, pasta)
    if pag is None:
        return ["campo 'pagina' ausente ou inválido"]
    if not pag.exists():
        return [f"página {m['pagina']} não existe"]
    texto = normalizar(pag.read_text(encoding="utf-8"))

    if m.get("trecho") and normalizar(m["trecho"]) not in texto:
        problemas.append("trecho citado não encontrado na página")
    for campo, num in (("valor_como_aparece", "valor"), ("anterior_como_aparece", "anterior")):
        bruto = m.get(campo)
        if not bruto:
            continue
        if normalizar(bruto) not in texto:
            problemas.append(f"{campo} '{bruto}' não aparece na página")
        try:
            if num in m and abs(br_para_float(bruto) - float(m[num])) > 1e-6:
                problemas.append(f"{num}={m[num]} não bate com '{bruto}'")
        except ValueError:
            problemas.append(f"não consegui ler '{bruto}' como número")
    if all(k in m for k in ("valor", "anterior", "variacao_pct")) and m["anterior"]:
        recalc = (m["valor"] / m["anterior"] - 1) * 100
        if abs(recalc - m["variacao_pct"]) > TOLERANCIA_VAR_PP:
            problemas.append(f"variação informada {m['variacao_pct']}% ≠ recalculada {recalc:.1f}%")
    return problemas


def avisar(m: dict, pasta: Path) -> list[str]:
    """Avisos que não mudam o código de saída. [] se a página não puder ser lida (checar já reporta)."""
    pag = _arquivo_pagina(m, pasta)
    if pag is None or not pag.exists():
        return []
    texto = normalizar(pag.read_text(encoding="utf-8"))
    bruto_trecho = m.get("trecho")
    trecho = normalizar(bruto_trecho) if isinstance(bruto_trecho, str) and bruto_trecho else ""

    avisos = []
    if trecho == "":
        avisos.append("sem 'trecho': a citação não foi conferida")

    for campo in ("valor_como_aparece", "anterior_como_aparece"):
        lit = m.get(campo)
        if not (isinstance(lit, str) and lit) or trecho == "":
            continue
        norm = normalizar(lit)
        if norm not in texto or norm in trecho:
            continue
        if campo == "valor_como_aparece":
            avisos.append(f"valor_como_aparece '{lit}' está na página, mas fora do trecho citado")
        elif len(norm) <= LIMITE_CURTO:
            avisos.append(f"anterior_como_aparece '{lit}' é curto e foi achado fora do trecho; pode ter casado por acaso")

    unidade = m.get("unidade")
    if isinstance(unidade, str):
        if unidade not in MARCADORES_UNIDADE:
            avisos.append(f"unidade '{unidade}' fora da lista do contrato")
        else:
            alvo = " ".join([trecho, normalizar(str(m.get("valor_como_aparece", ""))), texto])
            if re.search(MARCADORES_UNIDADE[unidade], alvo) is None:
                avisos.append(f"unidade '{unidade}' não aparece no trecho nem na página")
    return avisos


# --------------------------------------------------------------------------- resultado

class ErroEntrada(Exception):
    """Entrada inutilizável (arquivo, JSON, pasta, jsonschema) → código 2."""


@dataclass(frozen=True)
class Conferencia:
    indice: int
    metrica: str
    periodo: str
    problemas: tuple[str, ...]
    avisos: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problemas


@dataclass(frozen=True)
class Resultado:
    arquivo: Path
    pasta: Path
    schema: str | None
    erros_contrato: tuple = ()
    conferencias: tuple[Conferencia, ...] = ()

    @property
    def n_total(self) -> int:
        return len(self.conferencias)

    @property
    def n_ok(self) -> int:
        return sum(c.ok for c in self.conferencias)

    @property
    def n_erro(self) -> int:
        return self.n_total - self.n_ok

    @property
    def n_avisos(self) -> int:
        return sum(len(c.avisos) for c in self.conferencias)

    @property
    def codigo_saida(self) -> int:
        if self.erros_contrato:
            return 2
        return 1 if self.n_erro else 0


def verificar(pasta: Path | str, arquivo: Path | str, *, contrato: bool = True,
              schema: str | None = None) -> Resultado:
    """Valida o contrato (se ligado) e confere cada registro. Sem saída de tela."""
    pasta, arquivo = Path(pasta), Path(arquivo)
    if not arquivo.is_file():
        raise ErroEntrada(f"arquivo não encontrado: {arquivo}")
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErroEntrada(f"JSON inválido em {arquivo}: linha {e.lineno}, coluna {e.colno}: {e.msg}") from e
    except UnicodeDecodeError as e:
        raise ErroEntrada(f"JSON inválido em {arquivo}: não é UTF-8 ({e.reason})") from e

    nome = None
    if contrato:
        src = str(Path(__file__).resolve().parent)
        if src not in sys.path:
            sys.path.insert(0, src)
        try:
            import contrato as _contrato
        except ImportError as e:
            raise ErroEntrada(
                "jsonschema não instalado: rode 'pip install -r requirements.txt' (ou use --sem-contrato)"
            ) from e
        nome = schema or _contrato.escolher_schema(dados)
        erros = _contrato.validar(dados, nome)
        if erros:
            return Resultado(arquivo, pasta, nome, tuple(erros), ())

    if not isinstance(dados, list):
        raise ErroEntrada(f"{arquivo}: esperada uma lista de registros")
    if not pasta.is_dir():
        raise ErroEntrada(f"pasta de textos não encontrada: {pasta}")

    conferencias = []
    for i, m in enumerate(dados):
        if not isinstance(m, dict):
            conferencias.append(Conferencia(i, f"registro {i}", "", ("registro não é um objeto JSON",), ()))
            continue
        conferencias.append(Conferencia(
            i,
            str(m.get("metrica", f"registro {i}")),
            str(m.get("periodo", "")),
            tuple(checar(m, pasta)),
            tuple(avisar(m, pasta)),
        ))
    return Resultado(arquivo, pasta, nome, (), tuple(conferencias))


def imprimir(res: Resultado) -> None:
    if res.erros_contrato:
        from contrato import LIMITE_LINHAS
        n = len(res.erros_contrato)
        for erro in res.erros_contrato[:LIMITE_LINHAS]:
            print(f"[CONTRATO] {erro}")
        if n > LIMITE_LINHAS:
            print(f"[CONTRATO] ... e mais {n - LIMITE_LINHAS} erro(s)")
        print(f"\nJSON fora do contrato (schemas/{res.schema}.schema.json): {n} erro(s). "
              "Nenhuma métrica foi conferida.")
        return
    for c in res.conferencias:
        status = "OK " if c.ok else "ERRO"
        print(f"[{status}] {c.metrica} ({c.periodo}): " + ("; ".join(c.problemas) or "confere com o PDF"))
        if c.avisos:
            print(f"[AVISO] {c.metrica} ({c.periodo}): " + "; ".join(c.avisos))
    print(f"\n{res.n_ok}/{res.n_total} métricas conferem.")
    if res.n_avisos:
        print(f"{res.n_avisos} aviso(s): revise as linhas [AVISO] (não mudam o código de saída).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verificar_numeros.py",
        description="Confere um JSON de métricas contra saida/<pdf>/pagina_NN.txt.",
    )
    parser.add_argument("pasta", help="pasta com pagina_NN.txt (saida/<nome_do_pdf>)")
    parser.add_argument("arquivo", help="JSON de métricas (metricas/*.json)")
    parser.add_argument("--sem-contrato", action="store_true",
                        help="não valida o JSON contra o schema (só para destravar a oficina)")
    parser.add_argument("--schema", choices=["auto", "metricas", "balanco"], default="auto",
                        help="schema do contrato (auto: balanco se houver 'demonstracao')")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)

    if args.sem_contrato:
        print("aviso: --sem-contrato: o JSON não foi validado contra o schema (use só para destravar a oficina)",
              file=sys.stderr)
    try:
        res = verificar(args.pasta, args.arquivo, contrato=not args.sem_contrato,
                        schema=None if args.schema == "auto" else args.schema)
    except ErroEntrada as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    imprimir(res)
    return res.codigo_saida


if __name__ == "__main__":
    sys.exit(main())
