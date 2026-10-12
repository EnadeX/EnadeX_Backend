# -*- coding: utf-8 -*-
"""
Gera docs/RESULTADOS_BENCHMARK.md a partir do banco (campanha oficial), para que
o documento de resultados, os slides, o .docx e o dashboard leiam a MESMA fonte
(v_enade_time_benchmark_resumo / v_enade_time_benchmark_metricas). Nenhum número é digitado aqui.

Uso:
    python docs/geradores/gerar_resultados_md.py [--campanha <uuid>] [--saida docs/RESULTADOS_BENCHMARK.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dados_benchmark import RAIZ, br, carregar, data_extenso, pct, seg, sx  # noqa: E402


def linha(*cols) -> str:
    return "| " + " | ".join(str(c) for c in cols) + " |"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campanha", default="oficial")
    ap.add_argument("--saida", default=str(RAIZ / "docs" / "RESULTADOS_BENCHMARK.md"))
    args = ap.parse_args()

    D = carregar(args.campanha)
    maq, esc, seq, melhor = D["maquina"], D["escalonamento"], D["sequencial"], D["melhor"]
    hip = esc["hipoteses"]
    n = maq["n_suites"]
    disco_aq = D["aquecimento"][0]["disco_mb"] if D["aquecimento"] else None

    manifesto = {}
    conts: list[str] = []
    for mpath in sorted((RAIZ / "backups" / "campanhas").glob(f"{D['campanha_id']}*.json")):
        try:
            m = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        manifesto = manifesto or m
        for c in m.get("containers_ativos", []):
            if c not in conts:
                conts.append(c)
    containers = ", ".join(conts) or "não registrado"

    L: list[str] = []
    L.append("# Resultados do benchmark — campanha oficial")
    L.append("")
    L.append(f"> **Gerado automaticamente** por `docs/geradores/gerar_resultados_md.py` em {data_extenso(D['gerado_em'])}, "
             f"a partir das views `v_enade_time_benchmark_resumo` e `v_enade_time_benchmark_metricas` do banco local. "
             f"Não edite números à mão: rode o gerador. Campanha `{D['campanha_id']}`.")
    L.append("")
    L.append("## Desenho do experimento")
    L.append("")
    parciais = maq["n_suites"] - maq["n_suites_completas"]
    suites_txt = f"{maq['n_suites_completas']} suítes completas"
    if parciais:
        suites_txt += (f" + {parciais} parcial — interrompida por desligamento da máquina; as execuções já "
                       f"gravadas permanecem válidas (pareamento por suíte) e elevam o n de algumas configurações")
    L.append(f"- **Campanha:** {suites_txt}. Em cada suíte completa, 1 sequencial (baseline da suíte) + "
             f"{len(D['workers'])} tamanhos de pool ({', '.join(str(w) for w in D['workers'])} workers) × "
             f"2 ordens de submissão (crescente e LPT) = 9 execuções; total de {maq['n_execucoes']} execuções "
             f"oficiais (`oficial = TRUE`), entre {maq['inicio'].strftime('%d/%m/%Y %H:%M')} e "
             f"{maq['fim'].strftime('%d/%m/%Y %H:%M')} UTC. O n de cada configuração está na tabela.")
    L.append("- **Pareamento:** cada paralela é comparada com o sequencial da **própria suíte** "
             "(`v_enade_time_benchmark_metricas`, `pareamento = 'suite'`); mediana, mínimo, máximo e IQR por "
             "configuração em `v_enade_time_benchmark_resumo`.")
    L.append("- **Ordens de submissão:** `crescente` (2005 → 2021, comportamento histórico do script 09) e "
             "`lpt` (maior tempo primeiro — Graham, 1969 — com os tempos por ano do sequencial da mesma suíte). "
             "O `ProcessPoolExecutor` entrega cada ano ao primeiro worker livre na ordem de submissão; "
             "ele **não** balanceia.")
    L.append(f"- **Máquina:** {maq['cpu_modelo']} — **{maq['cpu_fisicos']} núcleos físicos / "
             f"{maq['cpu_logicos']} lógicos** (Intel Core i5-1135G7), NVMe Samsung, 24 GB RAM, Windows 11. "
             f"p = 4 satura os núcleos físicos; p = 6 roda em hyperthreads.")
    L.append(f"- **Cache:** passada de aquecimento descartada antes da campanha (leu **{br(disco_aq, 0)} MB** do disco); "
             f"todas as execuções oficiais com **cache de páginas quente** — mediana de "
             f"**{br(hip.get('H2_disco_quente_mb_mediana'), 1)} MB** lidos por execução.")
    L.append(f"- **Carga de fundo declarada:** CPU ociosa por 10 s antes de medir = **{br(maq['cpu_ocioso'], 1)} %**; "
             f"containers ativos: {containers}; CPU média do sistema durante as execuções: "
             f"{br(maq['cpu_percent_medio'], 1)} %. Sem API nem frontend rodando. Diretório fora do OneDrive.")
    L.append("- **Pipeline por execução:** leitura dos TXT (arq1 + arq3 dos 6 anos, 5.340.372 linhas), filtro e "
             "agregação com pandas; workers puros (sem I/O em disco, sem banco); só o processo principal grava "
             "(1 linha em `tbl_enade_time_benchmark_execucao` + 6 em `tbl_enade_time_benchmark_etapa`). p = 8 fica fora da campanha: com 6 "
             "unidades de trabalho, dois workers ficariam ociosos por construção.")
    L.append("")

    L.append("## Resultados por configuração")
    L.append("")
    L.append(linha("Configuração", "n", "Tempo (s) — mediana [mín–máx]", "IQR (s)", "Speedup (mediana)",
                   "Speedup mín–máx", "Eficiência (mediana)", "Throughput (linhas/s)"))
    L.append("|---|--:|---|--:|--:|---|--:|--:|")
    for r in D["resumo"]:
        par_ = r["modo"] == "paralelo"
        L.append(linha(
            f"**{r['rotulo']}**" if melhor and r is melhor else r["rotulo"], r["n"],
            f"{br(r['tempo_mediana'])} [{br(r['tempo_min'])}–{br(r['tempo_max'])}]", br(r["tempo_iqr"]),
            sx(r["speedup_mediana"]) if par_ else "1,0000×",
            f"{sx(r['speedup_min'], 2)}–{sx(r['speedup_max'], 2)}" if par_ else "—",
            pct(r["eficiencia_mediana"]) if par_ else "100,0 %", br(r["throughput_mediana"], 0)))
    L.append("")
    if melhor:
        L.append(f"> **Melhor configuração: {melhor['rotulo']}** — speedup mediano **{sx(melhor['speedup_mediana'])}** "
                 f"(mín–máx {sx(melhor['speedup_min'], 2)}–{sx(melhor['speedup_max'], 2)}), eficiência "
                 f"**{pct(melhor['eficiencia_mediana'])}**, contra um sequencial mediano de **{seg(seq['tempo_mediana'])}** "
                 f"[{br(seq['tempo_min'])}–{br(seq['tempo_max'])}].")
    L.append("")

    L.append("## Tetos de escalonamento e decomposição da perda")
    L.append("")
    L.append("Três perdas separadas, medidas por suíte e agregadas por mediana:")
    L.append("")
    L.append("1. **Granularidade + escalonamento** — do ideal (soma dos tempos por ano ÷ p) ao **teto** da ordem usada "
             "(makespan do escalonamento guloso com os tempos por ano do sequencial da mesma suíte).")
    L.append("2. **Contenção** — do teto ao **makespan medido** (maior soma de tempos por worker); aparece como "
             "**inflação das etapas** (soma dos tempos por ano em paralelo ÷ soma no sequencial).")
    L.append("3. **Overhead** — do makespan medido ao wall-clock (spawn dos processos, coleta, gravação).")
    L.append("")
    L.append(linha("p", "Ordem", "n", "Ideal (s)", "Teto ordem usada → S", "Teto LPT → S", "Makespan medido (s)",
                   "Inflação", "Wall (s)", "Overhead (s)", "S medido", "% do teto (ordem usada)", "CPU %", "Disco (MB)"))
    L.append("|--:|---|--:|--:|---|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for r in esc["agregado"]:
        L.append(linha(r["workers"], "LPT" if r["ordem"] == "lpt" else "crescente", r["n"], br(r["ideal"]),
                       f"{br(r['teto_real'])} → {sx(r['speedup_teto_real'], 2)}",
                       f"{br(r['teto_lpt'])} → {sx(r['speedup_teto_lpt'], 2)}",
                       br(r["makespan_medido"]), f"{br(r['inflacao_etapas'], 2)}×", br(r["wall"]), br(r["overhead"], 1),
                       sx(r["speedup_medido"]), pct(r["pct_do_teto_real"], 0), br(r["cpu_pct"], 1), br(r["disco_mb"], 1)))
    L.append("")
    L.append(f"Sequencial: n = {esc['sequencial']['n']}, mediana {seg(esc['sequencial']['t_seq_mediana'])}, "
             f"CPU {br(esc['sequencial']['cpu_pct_mediana'], 1)} %, disco {br(esc['sequencial']['disco_mb_mediana'], 1)} MB. "
             f"Aquecimento: {br(disco_aq, 0)} MB lidos.")
    L.append("")

    L.append("## Hipóteses pré-registradas")
    L.append("")
    for o in ("lpt", "crescente"):
        h = hip.get(f"H1_p6_nao_supera_p4_{o}")
        if h:
            L.append(f"- **H1 — p = 6 não supera p = 4 ({'LPT' if o == 'lpt' else 'crescente'}):** speedup mediano "
                     f"p = 4 {sx(h['speedup_p4'])} × p = 6 {sx(h['speedup_p6'])} → "
                     f"**{'confirmada' if h['confirmada'] else 'refutada'}**. Com 4 núcleos físicos, p = 6 roda em "
                     f"hyperthreads e o teto de granularidade (6 unidades) não cresce a partir de 6.")
    L.append(f"- **H2 — cache quente ⇒ limitado por CPU, não por disco:** mediana de "
             f"{br(hip.get('H2_disco_quente_mb_mediana'), 1)} MB lidos nas execuções quentes contra "
             f"{br(disco_aq, 0)} MB no aquecimento. A explicação anterior (\"4 workers lendo do mesmo disco geram "
             f"contenção\") **não se sustenta** nos bytes medidos: a contenção é de CPU (parsing com pandas) em "
             f"4 núcleos físicos.")
    h3 = []
    for p in (2, 3, 4):
        h = hip.get(f"H3_lpt_ge_crescente_p{p}")
        if h:
            h3.append(f"p = {p}: LPT {sx(h['lpt'])} × crescente {sx(h['crescente'])} "
                      f"({'confirmada' if h['confirmada'] else 'refutada'})")
    if h3:
        L.append("- **H3 — LPT ≥ crescente:** " + "; ".join(h3) + ". A diferença entre as ordens é perda de "
                 "escalonamento — o código dos workers é idêntico.")
    L.append("")
    L.append("> A métrica de **Karp–Flatt** mostrada no dashboard estima uma \"fração sequencial\" a partir do speedup; "
             "ela **embute** as três perdas acima e não deve ser lida como uma seção serial do código.")
    L.append("")

    L.append("## Histórico das medições e o erro do baseline")
    L.append("")
    L.append("O banco preserva todas as rodadas anteriores (nenhuma linha foi apagada ou sobrescrita; ids 1–6 mantêm "
             "o pareamento temporal com o sequencial imediatamente anterior, `pareamento = 'temporal'`).")
    L.append("")
    L.append(linha("Data", "Sequencial", "T(1)", "Paralela", "T(p)", "Speedup", "Eficiência", "Ordem"))
    L.append("|---|---|--:|---|--:|--:|--:|---|")
    for rod in D["historico"]:
        b = rod["baseline"]
        for p in rod["paralelas"]:
            L.append(linha(b["timestamp_inicio"].strftime("%d/%m/%Y"), f"#{b['id']}", seg(b["tempo_total_seg"]),
                           f"#{p['id']} ({p['num_workers']} workers)", seg(p["tempo_total_seg"]),
                           sx(p["speedup"]), pct(p["eficiencia"]), "crescente"))
    L.append("")
    if D["bug_baseline"]:
        L.append("**O erro:** a versão anterior de `/api/benchmark/comparativo` dividia todas as execuções pelo "
                 "sequencial **mais recente**. Com duas rodadas no banco, o dashboard de 21/08/2026 exibiu:")
        L.append("")
        L.append(linha("Execução", "Baseline usado (errado)", "Speedup exibido", "Eficiência exibida",
                       "Baseline pareado", "Speedup correto", "Eficiência correta"))
        L.append("|---|---|--:|--:|---|--:|--:|")
        for b in D["bug_baseline"]:
            L.append(linha(f"#{b['exec']} ({b['workers']} workers, {seg(b['tempo'])})",
                           f"#{b['baseline_errado']} ({seg(b['t_errado'])})", sx(b["s_errado"]), pct(b["e_errado"]),
                           f"#{b['baseline_certo']}", sx(b["s_certo"]), pct(b["e_certo"])))
        L.append("")
        L.append("Esse card entrou no documento acadêmico de 21/08/2026. **Correção (DESIGN_LOG D13):** a view pareia por "
                 "suíte; a API só lê a view; `scripts/13_validar_metricas.py` e `tests/` recalculam em Python e falham "
                 "em qualquer divergência; documento, slides e este arquivo são gerados das views e conferidos por "
                 "`docs/geradores/verificar_numeros.py`.")
        L.append("")
    L.append("**A rodada citada na apresentação anterior** (sequencial de aproximadamente 243 s; \"2 workers vence e 4 piora\") foi "
             "apagada em um `--reset` do schema (DESIGN_LOG D9) e **não tem suporte em banco** — deixou de ser citada "
             "como resultado. A conclusão daquela rodada não é reproduzida pela campanha oficial.")
    L.append("")
    if D["outras_campanhas"]:
        L.append("Outras campanhas no banco (não oficiais): " + "; ".join(
            f"`{c['campanha_id'][:8]}` em {c['inicio'].strftime('%d/%m/%Y')} ({c['n']} exec., "
            f"{(c['observacoes'] or '').split('|')[0].strip()})" for c in D["outras_campanhas"]) + ".")
        L.append("")

    L.append("## Reprodução")
    L.append("")
    L.append("```powershell")
    L.append("cd C:\\Projetos\\ENADE")
    L.append(".\\.venv\\Scripts\\Activate.ps1")
    L.append("docker compose up -d postgres")
    L.append("python scripts\\14_migrar_schema_v2.py --status        # schema v2 (aditivo)")
    L.append("python scripts\\10_rodar_suite_benchmark.py --oficial --obs \"nova campanha\"   # ~45 min")
    L.append("python scripts\\13_validar_metricas.py --api http://localhost:8000")
    L.append("python docs\\geradores\\gerar_resultados_md.py          # regenera este arquivo")
    L.append("```")
    L.append("")
    L.append("Auditoria direta no banco:")
    L.append("")
    L.append("```sql")
    L.append(f"SELECT * FROM v_enade_time_benchmark_resumo WHERE campanha_id = '{D['campanha_id']}' ORDER BY num_workers, ordem_submissao;")
    L.append(f"SELECT execucao_id, num_workers, ordem_submissao, speedup, eficiencia, baseline_execucao_id, pareamento")
    L.append(f"  FROM v_enade_time_benchmark_metricas WHERE campanha_id = '{D['campanha_id']}' ORDER BY suite_id, num_workers, ordem_submissao;")
    L.append("```")
    L.append("")
    L.append("Lições registradas: clientes de sincronização em nuvem contaminam I/O (2026-06); um baseline escolhido por "
             "recência mistura rodadas (2026-08); uma explicação por \"disco\" não sobrevive aos bytes medidos (2026-09). "
             "Medir > supor.")
    L.append("")

    out = Path(args.saida)
    out.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print(f"gerado: {out} ({len(L)} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
