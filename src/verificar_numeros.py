"""
Case 3 — Comparativo de resultados · o VERIFICADOR.

O Claude (ou um parser) extrai os números para um JSON de fatos (contrato em
docs/TAREFAS.md) e este script confere cada um contra o texto do PDF antes que
qualquer número entre na apresentação.

    python src/verificar_numeros.py saida/<nome_do_pdf> metricas/<arquivo>.json [--estrito] [--relatorio r.json]

Para cada fato:
  1. campos obrigatórios presentes;
  2. o trecho citado existe na página indicada;
  3. o valor aparece como TOKEN inteiro (não pedaço de outro número) na página E dentro do trecho;
  4. o valor numérico bate com o texto (pega erro de unidade e vírgula); idem 'anterior';
  5. a variação informada bate com a recalculada;
  6. coluna: se o fato diz em que coluna do trecho está (evidencia.coluna/n_colunas), o token
     daquela coluna tem que ser o valor; trecho com vários números e sem coluna → REVISAR;
  7. período, unidade e escopo: as evidências literais (evidencia.periodo/unidade/escopo) têm que
     estar na página e ser coerentes com o fato (datas, mil × milhões, consolidado × individual).

Resultado por fato: OK, REVISAR (a automação não comprovou o vínculo: falta evidência) ou ERRO.
Um REVISAR vira OK só com "revisao_manual": {"por": "<pessoa>", "nota": "<o que conferiu>"} no fato.
"OK" quer dizer "conferido literalmente contra o PDF", não validação semântica completa.
Saída 1 se houver ERRO; com --estrito, também se houver REVISAR.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

TOLERANCIA_VAR_PP = 0.5

CAMPOS_BASE = ("metrica", "pagina", "trecho")
CAMPOS_CONTRATO = ("chave", "empresa", "documento")
CAMPOS_NUMERICOS = ("valor", "valor_como_aparece", "unidade", "periodo", "escopo")

_N = r"\d{1,3}(?:\.\d{3})*(?:,\d+)?"
RE_NUM = re.compile(rf"(?<![\w.,])(?:-?{_N}|\({_N}\))(?:%|x)?(?![\w)])")  # parênteses balanceados
# rótulos de coluna num cabeçalho: intervalo de datas, data, 3T26, 9M26 ou ∆
RE_ROTULO = re.compile(r"\d{2}/\d{2}/\d{4}\s+à\s+\d{2}/\d{2}/\d{4}|\d{2}/\d{2}/\d{4}|\b[1-4]T\d{2}\b|\b\d{1,2}M\d{2}\b|[∆Δ]")
VAZIO = {"-", "–", "—"}  # célula vazia numa linha de tabela
RE_MIL = re.compile(r"\bmil(hares)?\b")
RE_DATA = re.compile(r"\d{2}/\d{2}/\d{4}")
RE_INDIVIDUAL = re.compile(r"DFs Individuais|controladora\b|holding", re.I)


def normalizar(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()


def br_para_float(s: str) -> float:
    """'1.234,5' -> 1234.5 ; '(123,4)' -> -123.4 ; '12,3%' -> 12.3"""
    s = s.strip().replace("%", "").replace("R$", "").strip().removesuffix("x")
    negativo = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()-").replace(".", "").replace(",", ".")
    return -float(s) if negativo else float(s)


def tem_token(token: str, texto: str) -> bool:
    """O token aparece inteiro? ('1.554' não casa dentro de '11.554.156' nem de '1.554,2')."""
    padrao = r"(?<![\d.,])" + re.escape(normalizar(token)) + r"(?![\d]|[.,]\d)"
    return re.search(padrao, normalizar(texto)) is not None


def valores_finais(trecho: str) -> list[str]:
    """Tokens numéricos no fim da linha (as colunas de uma tabela)."""
    fim = []
    for p in reversed(trecho.split()):
        if not (RE_NUM.fullmatch(p) or p in VAZIO):
            break
        fim.append(p)
    return fim[::-1]


def _iso_para_br(s: str) -> str:
    return date.fromisoformat(s).strftime("%d/%m/%Y")


def checar_cabecalho(cab: str, texto_pagina: str, k: int, n: int, m: dict) -> list[str]:
    """O cabeçalho literal tem n colunas e a coluna k é o período do fato?"""
    if normalizar(cab) not in texto_pagina:
        return [f"cabecalho_colunas '{cab}' não está na página"]
    rotulos = RE_ROTULO.findall(cab)
    if len(rotulos) != n:
        return [f"cabeçalho tem {len(rotulos)} colunas ({' | '.join(rotulos)}); o fato diz {n}"]
    r = rotulos[k - 1]
    if r in ("∆", "Δ"):
        return [f"a coluna {k} é de variação (∆), não de valor"]
    datas = RE_DATA.findall(r)
    if datas:
        esperadas = [_iso_para_br(m[c]) for c in ("periodo_inicio", "periodo_fim") if m.get(c)]
        if esperadas and datas != esperadas[-len(datas):]:
            return [f"a coluna {k} é de {' à '.join(datas)}, não do período do fato ({m.get('periodo')})"]
    elif r != m.get("periodo"):
        return [f"a coluna {k} é '{r}', não '{m.get('periodo')}'"]
    return []


def avaliar(m: dict, pasta: Path) -> tuple[str, list[str], list[str]]:
    """Devolve (status, erros, pendencias). status ∈ {'OK', 'REVISAR', 'ERRO'}."""
    erros: list[str] = []
    pend: list[str] = []
    qualitativo = m.get("chave") == "qualitativo"

    # Fato do contrato (tem 'chave'): todos os campos são obrigatórios. Sem 'chave' é formato legado
    # (ex.: templates/metricas_exemplo.json, extrair_balanco.py): número e trecho são conferidos igual,
    # mas a falta dos campos de identificação vira pendência: o fato não entra no pipeline.
    contrato = "chave" in m
    obrigatorios = CAMPOS_BASE + (() if qualitativo else CAMPOS_NUMERICOS)
    if contrato:
        obrigatorios += CAMPOS_CONTRATO
    else:
        obrigatorios = tuple(c for c in obrigatorios if c != "escopo")
        sem = [c for c in CAMPOS_CONTRATO + ("escopo",) if m.get(c) in (None, "")]
        if sem:
            pend.append(f"fora do contrato (sem {', '.join(sem)}): não entra no pipeline")
    faltando = [c for c in obrigatorios if m.get(c) in (None, "")]
    if faltando:
        erros.append(f"campos obrigatórios ausentes: {', '.join(faltando)}")
    if m.get("pagina") in (None, ""):
        return "ERRO", erros, pend

    pag = pasta / f"pagina_{int(m['pagina']):02d}.txt"
    if not pag.exists():
        return "ERRO", erros + [f"página {m['pagina']} não existe em {pasta}"], pend
    bruto = pag.read_text(encoding="utf-8")
    texto = normalizar(bruto)
    trecho = m.get("trecho") or ""

    if trecho and normalizar(trecho) not in texto:
        erros.append("trecho citado não encontrado na página")

    # valores
    for campo, num in (("valor_como_aparece", "valor"), ("anterior_como_aparece", "anterior")):
        tok = m.get(campo)
        if not tok:
            continue
        if not tem_token(tok, bruto):
            erros.append(f"{campo} '{tok}' não aparece na página como número inteiro")
        elif trecho and not tem_token(tok, trecho):
            erros.append(f"{campo} '{tok}' existe na página, mas não no trecho citado")
        try:
            if m.get(num) is not None and abs(br_para_float(tok) - float(m[num])) > 1e-6:
                erros.append(f"{num}={m[num]} não bate com '{tok}'")
        except ValueError:
            erros.append(f"não consegui ler '{tok}' como número")
    if all(m.get(k) is not None for k in ("valor", "anterior", "variacao_pct")) and m["anterior"]:
        recalc = (m["valor"] / m["anterior"] - 1) * 100
        if abs(recalc - m["variacao_pct"]) > TOLERANCIA_VAR_PP:
            erros.append(f"variação informada {m['variacao_pct']}% ≠ recalculada {recalc:.1f}%")

    if qualitativo:
        return ("ERRO" if erros else "OK"), erros, pend

    ev = m.get("evidencia") or {}
    tok = m.get("valor_como_aparece")

    # coluna
    if tok and trecho:
        cols = valores_finais(trecho)
        if ev.get("coluna") and ev.get("n_colunas"):
            k, n = int(ev["coluna"]), int(ev["n_colunas"])
            if len(cols) < n:
                erros.append(f"trecho termina com {len(cols)} valores; a evidência diz {n} colunas")
            else:
                cols = cols[-n:]  # a descrição pode terminar em número ("Instrução CVM 156")
                if cols[k - 1] != tok:
                    onde = [i + 1 for i, c in enumerate(cols) if c == tok]
                    erros.append(f"coluna {k} do trecho é '{cols[k - 1]}', não '{tok}'"
                                 + (f" (o valor está na coluna {onde[0]})" if onde else ""))
            cab = ev.get("cabecalho_colunas")
            if cab:
                erros += checar_cabecalho(cab, texto, k, n, m)
            else:
                pend.append("sem cabecalho_colunas: a ordem das colunas (qual é qual período) não foi comprovada")
        elif len(RE_NUM.findall(trecho)) > 1:
            pend.append("trecho tem mais de um número e o fato não diz a coluna: período não comprovado")

    # período
    if ev.get("periodo"):
        if normalizar(ev["periodo"]) not in texto:
            erros.append(f"evidência de período '{ev['periodo']}' não está na página")
        datas = RE_DATA.findall(ev["periodo"])
        esperadas = [_iso_para_br(m[c]) for c in ("periodo_inicio", "periodo_fim") if m.get(c)]
        if datas and esperadas and datas != esperadas:
            erros.append(f"evidência de período {datas} ≠ período do fato {esperadas}")
    else:
        pend.append("sem evidência literal do período (evidencia.periodo)")

    # unidade
    un = (m.get("unidade") or "").lower()
    if ev.get("unidade"):
        eu = ev["unidade"].lower()
        if normalizar(ev["unidade"]) not in texto:
            erros.append(f"evidência de unidade '{ev['unidade']}' não está na página")
        elif ("milh" in un) != ("milhões" in eu or "milhoes" in eu) or bool(RE_MIL.search(un)) != bool(RE_MIL.search(eu)):
            erros.append(f"unidade '{m.get('unidade')}' incoerente com a evidência '{ev['unidade']}'")
    elif un not in ("%", "x"):
        pend.append("sem evidência literal da unidade (evidencia.unidade)")

    # escopo
    escopo = (m.get("escopo") or "").lower()
    if escopo in ("controladora", "individual", "holding"):
        erros.append(f"escopo '{m['escopo']}' não é permitido (use consolidado ou segmento:<nome>)")
    if ev.get("escopo"):
        if normalizar(ev["escopo"]) not in texto:
            erros.append(f"evidência de escopo '{ev['escopo']}' não está na página")
        if escopo == "consolidado" and RE_INDIVIDUAL.search(ev["escopo"]):
            erros.append(f"fato marcado consolidado, mas a evidência é '{ev['escopo']}'")
    else:
        pend.append("sem evidência literal do escopo (evidencia.escopo)")
    if escopo == "consolidado" and re.search(r"^DFs Individuais", bruto, re.M) \
            and not re.search(r"^DFs Consolidadas", bruto, re.M):
        erros.append("fato marcado consolidado, mas a página é das DFs Individuais (controladora)")

    rev = m.get("revisao_manual") or {}
    if pend and not erros and rev.get("por") and rev.get("nota"):
        # uma pessoa conferiu o que a automação não comprova: fica registrado, não some
        return "OK", erros, [f"revisão manual ({rev['por']}): {rev['nota']}"]
    status = "ERRO" if erros else ("REVISAR" if pend else "OK")
    return status, erros, pend


def checar(m: dict, pasta: Path) -> list[str]:
    """Compatibilidade: só a lista de erros (o pipeline do CASE-07 importa esta função)."""
    return avaliar(m, pasta)[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pasta", type=Path, help="saida/<nome_do_pdf> com os pagina_NN.txt")
    ap.add_argument("arquivo", type=Path, help="JSON de fatos (lista)")
    ap.add_argument("--estrito", action="store_true", help="REVISAR também reprova (saída 1)")
    ap.add_argument("--relatorio", type=Path, help="grava o resultado por fato em JSON")
    a = ap.parse_args(argv)

    metricas = json.loads(a.arquivo.read_text(encoding="utf-8"))
    if not isinstance(metricas, list) or not metricas:
        print(f"[ERRO] {a.arquivo}: esperado uma lista de fatos não vazia", file=sys.stderr)
        return 1
    contagem = {"OK": 0, "REVISAR": 0, "ERRO": 0}
    resultado = []
    for i, m in enumerate(metricas):
        status, erros, pend = avaliar(m, a.pasta)
        contagem[status] += 1
        rotulo = f"{m.get('metrica', f'item {i}')} ({m.get('periodo', '')})"
        print(f"[{status:<7}] {rotulo}: {'; '.join(erros + pend) or 'confere com o PDF'}")
        resultado.append({"indice": i, "chave": m.get("chave"), "periodo": m.get("periodo"),
                          "pagina": m.get("pagina"), "status": status, "erros": erros, "pendencias": pend})
    print(f"\n{contagem['OK']}/{len(metricas)} conferem · {contagem['REVISAR']} para revisar · "
          f"{contagem['ERRO']} com erro.")
    if a.relatorio:
        a.relatorio.parent.mkdir(parents=True, exist_ok=True)
        a.relatorio.write_text(json.dumps({"arquivo": str(a.arquivo), "pasta": str(a.pasta),
                                           "contagem": contagem, "fatos": resultado},
                                          ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if contagem["ERRO"] or (a.estrito and contagem["REVISAR"]) else 0


if __name__ == "__main__":
    sys.exit(main())
