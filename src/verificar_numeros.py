"""
Case 3 — Comparativo de resultados · o VERIFICADOR.

A ideia: o Claude extrai os números do release para um JSON (ver
metricas_exemplo.json), e este script confere cada um contra o PDF antes que
qualquer número entre na apresentação. É o passo "verificar" do loop agêntico.

    python src/verificar_numeros.py saida/<nome_do_pdf> metricas/metricas_EMPRESA.json

Para cada métrica, confere:
  1. se o trecho citado existe na página indicada;
  2. se o valor aparece na página exatamente como no PDF (valor_como_aparece);
  3. se o valor numérico bate com o texto (pega erro de unidade e vírgula);
  4. se a variação informada bate com a recalculada a partir dos dois períodos.
"""
import json
import re
import sys
from pathlib import Path

TOLERANCIA_VAR_PP = 0.5


def normalizar(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()


def br_para_float(s: str) -> float:
    """'1.234,5' -> 1234.5 ; '(123,4)' -> -123.4 ; '12,3%' -> 12.3"""
    s = s.strip().replace("%", "").replace("R$", "").strip()
    negativo = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()-").replace(".", "").replace(",", ".")
    return -float(s) if negativo else float(s)


def checar(m: dict, pasta: Path) -> list[str]:
    problemas = []
    pag = pasta / f"pagina_{int(m['pagina']):02d}.txt"
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


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    pasta, arquivo = Path(sys.argv[1]), Path(sys.argv[2])
    metricas = json.loads(arquivo.read_text(encoding="utf-8"))
    falhas = 0
    for m in metricas:
        probs = checar(m, pasta)
        falhas += bool(probs)
        status = "OK " if not probs else "ERRO"
        print(f"[{status}] {m['metrica']} ({m.get('periodo', '')}): " + ("; ".join(probs) or "confere com o PDF"))
    print(f"\n{len(metricas) - falhas}/{len(metricas)} métricas conferem.")
    sys.exit(1 if falhas else 0)
