# -*- coding: utf-8 -*-
"""
Tetos de escalonamento e decomposição das perdas de paralelismo, calculados a
partir de `tbl_enade_time_benchmark_etapa` (tempos por ano) e `tbl_enade_time_benchmark_execucao`.

Para cada execução paralela da campanha:
  * **ideal**            = soma dos tempos por ano do sequencial da MESMA suíte ÷ p;
  * **teto (ordem usada)** = makespan do escalonamento guloso ("primeiro worker
    livre", exatamente o que o ProcessPoolExecutor faz) com os tempos por ano do
    sequencial da suíte, na ordem de submissão registrada na execução;
  * **teto LPT / crescente** = idem, nas duas ordens (para comparar);
  * **makespan medido**  = maior soma de tempos de etapa por worker_pid;
  * **inflação das etapas** = soma dos tempos por ano em paralelo ÷ soma no
    sequencial (contenção: cada etapa fica mais lenta);
  * **overhead**         = wall-clock − makespan medido (spawn, coleta, gravação);
  * **speedup medido**   = t_seq da suíte ÷ wall-clock (igual à view, sem arredondar).

Agregados por (workers, ordem) = MEDIANAS sobre as suítes. Hipóteses
pré-registradas (H1, H2, H3) avaliadas a partir dos agregados.

Uso:
  python docs/geradores/analise_escalonamento.py                       # campanha oficial, tabela no stdout
  python docs/geradores/analise_escalonamento.py --json docs/geradores/out/escalonamento.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[2]))  # raiz do EnadeX

from enade_time.etl.bench_db import conectar, ultima_campanha_oficial  # noqa: E402

ANOS = (2005, 2008, 2011, 2014, 2017, 2021)


# ---------------------------------------------------------------------------
# Escalonamento
# ---------------------------------------------------------------------------

def ordem_anos(ordem: str, tempos: dict[int, float]) -> list[int]:
    if ordem == "crescente":
        return sorted(ANOS)
    return sorted(ANOS, key=lambda a: (-tempos.get(a, 0.0), a))  # lpt


def makespan_guloso(tempos: dict[int, float], anos: list[int], p: int) -> float:
    cargas = [0.0] * p
    for a in anos:
        i = cargas.index(min(cargas))
        cargas[i] += tempos.get(a, 0.0)
    return max(cargas)


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def carregar(conn, campanha: str, _reservado=None):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, modo, num_workers, ordem_submissao, suite_id::text AS suite_id,
                   tempo_total_seg::float AS wall,
                   cpu_percent_medio::float AS cpu_pct,
                   disco_bytes_lidos, aquecimento
            FROM tbl_enade_time_benchmark_execucao
            WHERE campanha_id = %s
            ORDER BY id
        """, (campanha,))
        cols = [d[0] for d in cur.description]
        execs = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.execute("""
            SELECT e.execucao_id, e.ano, e.tempo_seg::float AS t, e.worker_pid
            FROM tbl_enade_time_benchmark_etapa e
            JOIN tbl_enade_time_benchmark_execucao x ON x.id = e.execucao_id
            WHERE x.campanha_id = %s
        """, (campanha,))
        etapas: dict[int, list[tuple[int, float, int | None]]] = {}
        for eid, ano, t, pid in cur.fetchall():
            etapas.setdefault(eid, []).append((int(ano), float(t), pid))
    return execs, etapas


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------

def analisar(execs: list[dict], etapas: dict[int, list]) -> dict:
    oficiais = [e for e in execs if not e["aquecimento"]]
    seq_por_suite = {e["suite_id"]: e for e in oficiais if e["modo"] == "sequencial"}

    por_execucao: list[dict] = []
    for p in oficiais:
        if p["modo"] != "paralelo":
            continue
        seq = seq_por_suite.get(p["suite_id"])
        if seq is None or seq["id"] not in etapas:
            continue
        t_seq_anos = {a: t for a, t, _ in etapas[seq["id"]]}
        soma_seq = sum(t_seq_anos.values())
        w = int(p["num_workers"])
        ordem = p["ordem_submissao"] or "crescente"

        teto_c = makespan_guloso(t_seq_anos, ordem_anos("crescente", t_seq_anos), w)
        teto_l = makespan_guloso(t_seq_anos, ordem_anos("lpt", t_seq_anos), w)
        teto_real = teto_c if ordem == "crescente" else teto_l

        et_par = etapas.get(p["id"], [])
        soma_par = sum(t for _, t, _ in et_par)
        por_pid: dict = {}
        for _, t, pid in et_par:
            por_pid[pid] = por_pid.get(pid, 0.0) + t
        mk_medido = max(por_pid.values()) if por_pid else None

        wall = float(p["wall"])
        s_medido = float(seq["wall"]) / wall if wall else None
        linha = {
            "execucao_id": p["id"], "suite_id": p["suite_id"],
            "workers": w, "ordem": ordem,
            "ideal": soma_seq / w,
            "teto_crescente": teto_c, "speedup_teto_crescente": soma_seq / teto_c if teto_c else None,
            "teto_lpt": teto_l, "speedup_teto_lpt": soma_seq / teto_l if teto_l else None,
            "teto_real": teto_real, "speedup_teto_real": soma_seq / teto_real if teto_real else None,
            "makespan_medido": mk_medido,
            "inflacao_etapas": (soma_par / soma_seq) if soma_seq else None,
            "wall": wall,
            "overhead": (wall - mk_medido) if mk_medido is not None else None,
            "speedup_medido": s_medido,
            "pct_do_teto_real": (s_medido / (soma_seq / teto_real)) if (s_medido and teto_real) else None,
            "pct_do_teto_lpt": (s_medido / (soma_seq / teto_l)) if (s_medido and teto_l) else None,
            "cpu_pct": p["cpu_pct"],
            "disco_mb": (p["disco_bytes_lidos"] or 0) / 1e6 if p["disco_bytes_lidos"] is not None else None,
        }
        por_execucao.append(linha)

    def med(vals):
        vals = [v for v in vals if v is not None]
        return median(vals) if vals else None

    agregado: list[dict] = []
    chaves = sorted({(l["workers"], l["ordem"]) for l in por_execucao})
    for w, o in chaves:
        grupo = [l for l in por_execucao if l["workers"] == w and l["ordem"] == o]
        agregado.append({
            "workers": w, "ordem": o, "n": len(grupo),
            **{k: med(g[k] for g in grupo) for k in (
                "ideal", "teto_crescente", "speedup_teto_crescente",
                "teto_lpt", "speedup_teto_lpt", "teto_real", "speedup_teto_real",
                "makespan_medido", "inflacao_etapas", "wall", "overhead",
                "speedup_medido", "pct_do_teto_real", "pct_do_teto_lpt",
                "cpu_pct", "disco_mb")},
        })

    seqs = [e for e in oficiais if e["modo"] == "sequencial"]
    sequencial = {
        "n": len(seqs),
        "t_seq_mediana": med(float(s["wall"]) for s in seqs),
        "cpu_pct_mediana": med(s["cpu_pct"] for s in seqs),
        "disco_mb_mediana": med((s["disco_bytes_lidos"] or 0) / 1e6
                                for s in seqs if s["disco_bytes_lidos"] is not None),
    }

    def s_med(w, o):
        r = next((a for a in agregado if a["workers"] == w and a["ordem"] == o), None)
        return r["speedup_medido"] if r else None

    hipoteses: dict = {}
    for o in ("lpt", "crescente"):
        s4, s6 = s_med(4, o), s_med(6, o)
        if s4 is not None and s6 is not None:
            hipoteses[f"H1_p6_nao_supera_p4_{o}"] = {
                "speedup_p4": s4, "speedup_p6": s6, "confirmada": s6 <= s4}
    disco_all = [l["disco_mb"] for l in por_execucao if l["disco_mb"] is not None]
    disco_all += [(s["disco_bytes_lidos"] or 0) / 1e6 for s in seqs
                  if s["disco_bytes_lidos"] is not None]
    hipoteses["H2_disco_quente_mb_mediana"] = med(disco_all)
    for p_ in (2, 3, 4, 6):
        sl, sc = s_med(p_, "lpt"), s_med(p_, "crescente")
        if sl is not None and sc is not None:
            hipoteses[f"H3_lpt_ge_crescente_p{p_}"] = {
                "lpt": sl, "crescente": sc, "confirmada": sl >= sc}

    return {"por_execucao": por_execucao, "agregado": agregado,
            "sequencial": sequencial, "hipoteses": hipoteses}


def imprimir(res: dict) -> None:
    seqn = res["sequencial"]
    print(f"sequencial: n={seqn['n']} t_med={seqn['t_seq_mediana']:.2f}s "
          f"cpu={seqn['cpu_pct_mediana'] or 0:.1f}% disco={seqn['disco_mb_mediana'] or 0:.1f}MB")
    print(f"{'p':>2} {'ordem':>9} {'n':>2} {'ideal':>7} {'tetoUsd':>8} {'S_teto':>6} "
          f"{'mk_med':>7} {'infl':>5} {'wall':>7} {'ovh':>5} {'S_med':>6} {'%teto':>5} {'cpu%':>5} {'MB':>6}")
    for r in res["agregado"]:
        print(f"{r['workers']:>2} {r['ordem']:>9} {r['n']:>2} {r['ideal']:>7.2f} {r['teto_real']:>8.2f} "
              f"{r['speedup_teto_real']:>6.2f} {r['makespan_medido']:>7.2f} {r['inflacao_etapas']:>5.2f} "
              f"{r['wall']:>7.2f} {r['overhead']:>5.1f} {r['speedup_medido']:>6.3f} "
              f"{(r['pct_do_teto_real'] or 0) * 100:>4.0f}% {r['cpu_pct'] or 0:>5.1f} {r['disco_mb'] or 0:>6.1f}")
    print("hipóteses:")
    for k, v in res["hipoteses"].items():
        print(f"  {k}: {v}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campanha", default="oficial")
    ap.add_argument("--json", type=Path, default=None, help="grava o resultado em JSON")
    args = ap.parse_args()

    conn = conectar()
    try:
        cid = ultima_campanha_oficial(conn) if args.campanha == "oficial" else args.campanha
        if cid is None:
            print("Nenhuma campanha oficial no banco.", file=sys.stderr)
            return 1
        execs, etapas = carregar(conn, cid)
    finally:
        conn.close()

    res = analisar(execs, etapas)
    res["campanha_id"] = cid
    imprimir(res)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str),
                             encoding="utf-8")
        print(f"\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
