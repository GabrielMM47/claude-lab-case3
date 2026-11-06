"""
[CASE-02] Saída assistida: as escolhas de página/linha/coluna abaixo foram feitas com o Claude Code
seguindo prompts/extracao_financeira_complementar.md. O script só copia trecho e token literais.
Rode da raiz: python scripts/montar_complementar_3T26.py

Monta metricas/<slug>_3T26_itr_complementar.json copiando trecho e valor literais das páginas.
Cada spec diz: chave, metrica, página, início da linha, coluna, período e evidências."""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from verificar_numeros import RE_ROTULO, br_para_float, valores_finais  # noqa: E402

PER = {  # rótulo -> (inicio, fim, tipo)
    "3T26": ("2026-07-01", "2026-09-30"), "3T25": ("2025-07-01", "2025-09-30"),
    "2T26": ("2026-04-01", "2026-06-30"), "9M26": ("2026-01-01", "2026-09-30"),
    "9M25": ("2025-01-01", "2025-09-30"),
}


def linha(pasta, pagina, inicio):
    linhas = [l.strip() for l in (pasta / f"pagina_{pagina:02d}.txt").read_text().splitlines()]
    achadas = [l for l in linhas if l.startswith(inicio)]
    assert len(achadas) >= 1, (pagina, inicio)
    return achadas[0], len(achadas)


def fato(slug, doc_id, pasta, chave, metrica, pagina, inicio, cols, ev, tipo="fluxo", unidade="R$ mil",
         criterio=None, obs=None):
    trecho, repet = linha(pasta, pagina, inicio)
    toks = valores_finais(trecho)
    out = []
    for periodo, k in cols.items():
        cab = ev[periodo].get("cabecalho_colunas")
        if cab:  # número de colunas vem do cabeçalho, não dos tokens (a descrição pode terminar em número)
            rot = RE_ROTULO.findall(cab)
            toks = toks[-len(rot):]
            assert rot[k - 1] == periodo, (chave, periodo, rot)
        tok = toks[k - 1]
        assert tok not in ("-", "–", "—"), (chave, periodo, trecho)
        ini, fim = PER[periodo]
        f = {"chave": chave, "metrica": metrica, "empresa": slug, "documento": "itr", "documento_id": doc_id,
             "data_documento": "2026-09-30", "escopo": "consolidado", "tipo": tipo, "periodo": periodo,
             "periodo_inicio": None if tipo == "saldo" else ini, "periodo_fim": fim, "unidade": unidade}
        if unidade.startswith("R$"):
            f["moeda"] = "BRL"
        if criterio:
            f["criterio"] = criterio
        f |= {"valor": br_para_float(tok), "valor_como_aparece": tok, "pagina": pagina, "trecho": trecho,
              "evidencia": ev[periodo] | {"coluna": k, "n_colunas": len(toks)}}
        o = obs or ""
        if repet > 1:
            o = (o + " " if o else "") + f"A mesma linha aparece {repet}x na página (valores iguais)."
        if o:
            f["obs"] = o
        out.append(f)
    return out


def gerdau():
    slug, doc = "gerdau", "gerdau_ITR_3T26"
    pasta = RAIZ / "saida" / doc
    un = "(Valores expressos em milhares de reais, exceto quando especificado)"
    ev3 = {"escopo": "C onsolidado", "unidade": un, "periodo": "P eríodos de 3 m eses findos em :"}
    ev9 = {"escopo": "lim inações e ajustes C onsolidado", "unidade": un,
           "periodo": "P eríodos de 9 m eses findos em :"}
    E3 = {"3T26": ev3, "3T25": ev3}
    E9 = {"9M26": ev9, "9M25": ev9}
    nota = "Nota 22, informações por segmento, coluna Consolidado."
    F = []
    F += fato(slug, doc, pasta, "ebitda_ajustado", "EBITDA ajustado", 72, "3.770.176 ", {"3T26": 1, "3T25": 2},
              E3, criterio="ajustado", obs=nota)
    F += fato(slug, doc, pasta, "ebitda_ajustado", "EBITDA ajustado", 73, "(260.691) 10.158.058",
              {"9M26": 2, "9M25": 3}, E9, criterio="ajustado",
              obs=nota + " A coluna 1 da linha é 'Eliminações e ajustes' 9M25.")
    F += fato(slug, doc, pasta, "depreciacao_amortizacao_tri", "Depreciação e amortização", 72, "937.901 ",
              {"3T26": 1, "3T25": 2}, E3, obs=nota)
    F += fato(slug, doc, pasta, "ajuste_ebitda", "Recuperação de créditos / provisões (itens não recorrentes)",
              72, "(60.412) -", {"3T26": 1}, E3, criterio="ajustado",
              obs=nota + " Sem valor no 3T25 ('-'). Inclui itens não recorrentes, segundo a nota.")
    F += fato(slug, doc, pasta, "ajuste_ebitda", "EBITDA ajustado proporcional das controladas em conjunto e coligadas",
              72, "193.594 229.349", {"3T26": 1, "3T25": 2}, E3, criterio="ajustado",
              obs=nota + " Ajuste recorrente (critério), não efeito pontual.")
    cob = [
        {"chave": "ebitda_contabil", "periodo": p, "status": "ausente",
         "motivo": "ITR não divulga o EBITDA CVM 156 consolidado; calculável como ebit + depreciacao_amortizacao_tri"}
        for p in ("3T26", "3T25")]
    cob += [{"chave": k, "periodo": p, "status": "ausente",
             "motivo": "não divulgado em número no ITR (a nota 22 de risco de capital só cita o indicador)"}
            for k in ("divida_bruta_reportada", "divida_liquida_reportada", "dl_ebitda_reportado")
            for p in ("3T26", "3T25")]
    cob += [{"chave": "*", "periodo": "2T26", "status": "ausente",
             "motivo": "o ITR do 3T26 da Gerdau só traz 3T26 × 3T25 e 9M26 × 9M25"}]
    cob += [{"chave": "ajuste_ebitda:recuperacao_creditos_provisoes", "periodo": "3T25", "status": "ausente",
             "motivo": "célula '-' na p. 72: sem ajuste no 3T25"}]
    return slug, F, cob


def usiminas():
    slug, doc = "usiminas", "usiminas_ITR_3T26"
    pasta = RAIZ / "saida" / doc
    e28 = {"escopo": "EBITDA e Margem EBITDA Ajustados Consolidado", "unidade": "R$ mil",
           "periodo": "R$ mil 3T26 2T26 3T25", "cabecalho_colunas": "R$ mil 3T26 2T26 3T25"}
    E28 = {p: e28 for p in ("3T26", "2T26", "3T25")}
    e45 = {"escopo": "DEMONSTRAÇÃO DO RESULTADO ACUMULADO CONSOLIDADO", "unidade": "R$ mil",
           "periodo": "R$ mil 9M26 9M25 ∆", "cabecalho_colunas": "R$ mil 9M26 9M25 ∆"}
    E45 = {p: e45 for p in ("9M26", "9M25")}
    e24 = {"escopo": "Valores Consolidados", "periodo": "em R$ milhões 3T26 2T26 ∆ 3T25 ∆",
           "cabecalho_colunas": "em R$ milhões 3T26 2T26 ∆ 3T25 ∆"}
    E24 = {p: e24 for p in ("3T26", "2T26", "3T25")}
    e32 = {"unidade": "R$ mil"}
    E32 = {"3T26": e32 | {"periodo": "30-set-26"}, "2T26": e32 | {"periodo": "30-jun-26"},
           "3T25": e32 | {"periodo": "30-set-25"}}
    c3 = {"3T26": 1, "2T26": 2, "3T25": 3}
    rel = "Release de resultados dentro do ITR, tabela 'EBITDA AJUSTADO' (reconciliação)."
    F = []
    F += fato(slug, doc, pasta, "ebitda_contabil", "EBITDA Instrução CVM 156", 28, "EBITDA Instrução CVM 156", c3,
              E28, criterio="contabil", obs=rel)
    F += fato(slug, doc, pasta, "ebitda_ajustado", "EBITDA Ajustado", 28, "EBITDA Ajustado ", c3, E28,
              criterio="ajustado", obs=rel)
    F += fato(slug, doc, pasta, "depreciacao_amortizacao_tri", "Depreciação, amortização e exaustão", 28,
              "Depreciação, amortização e exaustão", c3, E28, obs=rel)
    F += fato(slug, doc, pasta, "ajuste_ebitda", "(-) Participação no resultado de controladas, controladas em conjunto e coligadas",
              28, "(-) Participação no resultado", c3, E28, criterio="ajustado", obs=rel + " Ajuste recorrente.")
    F += fato(slug, doc, pasta, "ajuste_ebitda", "(+) EBITDA proporcional de controladas em conjunto", 28,
              "(+) EBITDA proporcional", c3, E28, criterio="ajustado", obs=rel + " Ajuste recorrente.")
    F += fato(slug, doc, pasta, "ajuste_ebitda", "(-) Impairment de ativos não financeiros líquido de realização",
              28, "(-) Impairment de ativos", {"3T25": 3}, E28, criterio="ajustado",
              obs=rel + " EFEITO PONTUAL do 3T25: distorce a comparação A/A de EBITDA contábil e de lucro líquido.")
    F += fato(slug, doc, pasta, "ebitda_contabil", "EBITDA (Instrução CVM 156)", 45, "EBITDA (Instrução CVM 156)",
              {"9M26": 1, "9M25": 2}, E45, criterio="contabil", obs="Release, DRE acumulada consolidada.")
    F += fato(slug, doc, pasta, "ebitda_ajustado", "EBITDA Ajustado", 45, "EBITDA Ajustado ", {"9M26": 1, "9M25": 2},
              E45, criterio="ajustado", obs="Release, DRE acumulada consolidada.")
    F += fato(slug, doc, pasta, "divida_bruta_reportada", "Dívida Bruta", 32, "Dívida Bruta 162.073",
              {"3T26": 3, "2T26": 5, "3T25": 7}, E32, tipo="saldo",
              obs="Release, tabela 'Endividamento'. Inclui tributos parcelados (por isso difere da soma de "
                  "emprestimos_cp + emprestimos_lp das DFs). A página não traz a palavra 'consolidado'.")
    F += fato(slug, doc, pasta, "divida_liquida_reportada", "Dívida Líquida", 32, "Dívida Líquida - -",
              {"3T26": 3, "2T26": 5, "3T25": 7}, E32, tipo="saldo",
              obs="Release, tabela 'Endividamento'. Negativa = caixa maior que a dívida.")
    F += fato(slug, doc, pasta, "dl_ebitda_reportado", "Dívida Líquida/EBITDA Ajustado", 24,
              "Dívida Líquida/EBITDA Ajustado", {"3T26": 1, "2T26": 2, "3T25": 4}, E24, tipo="saldo", unidade="x",
              obs="Release, quadro de destaques. Critério da empresa (EBITDA ajustado dos últimos 12 meses).")
    cob = [{"chave": "ajuste_ebitda:impairment", "periodo": p, "status": "ausente",
            "motivo": "célula '-' na p. 28: sem impairment no período"} for p in ("3T26", "2T26")]
    return slug, F, cob


for slug, F, cob in (gerdau(), usiminas()):
    base = f"{slug}_3T26_itr_complementar.json"
    (RAIZ / "metricas" / base).write_text(json.dumps(F, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RAIZ / "metricas" / "cobertura" / base).write_text(json.dumps(
        {"documento_id": f"{slug}_ITR_3T26", "itens": cob}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(slug, len(F), "fatos")
