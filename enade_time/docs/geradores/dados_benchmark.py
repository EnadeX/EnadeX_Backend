"""
Dados do benchmark para os geradores de documento e apresentação — TUDO lido
do banco (views `v_enade_time_benchmark_resumo` / `v_enade_time_benchmark_metricas` e tabelas), nada
digitado. `verificar_numeros.py` confere depois que cada número do .docx/.pptx
existe nas views.

Uso típico:
    from dados_benchmark import carregar, br, pct, sx, seg
    d = carregar()            # campanha oficial mais recente
    d["resumo"]               # lista de configurações (dicts com floats)
    d["melhor"]               # configuração paralela de maior speedup mediano
    d["escalonamento"]        # saída de analise_escalonamento.analisar()
    d["historico"]            # rodadas legadas (sem campanha) agrupadas por baseline
    d["bug_baseline"]         # execuções cujo speedup "contra o sequencial mais
                              # recente" difere do pareado (o erro de 21/08)
"""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]          # enade_time/
RAIZ_ECO = RAIZ.parent          # raiz do EnadeX
if str(RAIZ_ECO) not in sys.path:
    sys.path.insert(0, str(RAIZ_ECO))

from enade_time.etl.bench_db import conectar, ultima_campanha_oficial  # noqa: E402

_spec = importlib.util.spec_from_file_location("analise_escalonamento", AQUI / "analise_escalonamento.py")
analise = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analise)


# ---------------------------------------------------------------------------
# Formatação pt-BR
# ---------------------------------------------------------------------------

def br(v, casas: int = 2) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v, casas: int = 1) -> str:
    return "—" if v is None else f"{br(float(v) * 100, casas)} %"


def sx(v, casas: int = 4) -> str:
    return "—" if v is None else f"{br(v, casas)}×"


def seg(v, casas: int = 2) -> str:
    return "—" if v is None else f"{br(v, casas)} s"


def inteiro(v) -> str:
    return "—" if v is None else br(round(float(v)), 0)


def rotulo(modo: str, workers: int, ordem: str | None) -> str:
    if modo == "sequencial":
        return "Sequencial (1)"
    return f"{workers} workers · {'LPT' if ordem == 'lpt' else 'crescente'}"


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def data_extenso(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def _dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _f(v):
    return None if v is None else float(v)


def carregar(campanha: str = "oficial") -> dict:
    conn = conectar()
    try:
        cid = ultima_campanha_oficial(conn) if campanha == "oficial" else campanha
        if cid is None:
            raise SystemExit("Nenhuma campanha oficial no banco — rode "
                             "`python scripts/10_rodar_suite_benchmark.py --oficial` primeiro.")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT modo, num_workers, ordem_submissao, n,
                       tempo_mediana, tempo_min, tempo_max, tempo_iqr, throughput_mediana,
                       speedup_mediana, speedup_min, speedup_max,
                       eficiencia_mediana, eficiencia_min, eficiencia_max
                FROM v_enade_time_benchmark_resumo WHERE campanha_id = %s
                ORDER BY num_workers, ordem_submissao NULLS FIRST
            """, (cid,))
            resumo = _dicts(cur)
            for r in resumo:
                for k, v in list(r.items()):
                    if k not in ("modo", "num_workers", "ordem_submissao", "n"):
                        r[k] = _f(v)
                r["rotulo"] = rotulo(r["modo"], r["num_workers"], r["ordem_submissao"])

            cur.execute("""
                SELECT MIN(cpu_fisicos) AS cpu_fisicos, MIN(cpu_logicos) AS cpu_logicos,
                       MIN(cpu_modelo) AS cpu_modelo, bool_and(cache_quente) AS cache_quente,
                       COUNT(DISTINCT suite_id) AS n_suites, COUNT(*) AS n_execucoes,
                       MIN(timestamp_inicio) AS inicio, MAX(timestamp_inicio) AS fim,
                       MIN(observacoes) AS observacoes,
                       ROUND(AVG(cpu_percent_medio), 1) AS cpu_percent_medio,
                       MIN(memoria_pico_mb) AS mem_min, MAX(memoria_pico_mb) AS mem_max
                FROM tbl_enade_time_benchmark_execucao WHERE campanha_id = %s AND NOT aquecimento
            """, (cid,))
            maquina = _dicts(cur)[0]
            m = re.search(r"cpu_ocioso=([\d.]+)%", maquina.get("observacoes") or "")
            maquina["cpu_ocioso"] = float(m.group(1)) if m else None

            # suítes completas × parciais: uma interrupção real (queda da
            # máquina) deixa uma suíte com menos execuções; as linhas gravadas
            # permanecem válidas (pareamento por suíte) e elevam o n de
            # algumas configurações.
            cur.execute("""
                SELECT suite_id::text AS suite_id, COUNT(*) AS n_execs,
                       MIN(timestamp_inicio) AS inicio
                FROM tbl_enade_time_benchmark_execucao
                WHERE campanha_id = %s AND NOT aquecimento
                GROUP BY suite_id ORDER BY MIN(timestamp_inicio)
            """, (cid,))
            suites_info = _dicts(cur)
            _n_cfg = max((int(s["n_execs"]) for s in suites_info), default=0)
            maquina["n_suites"] = len(suites_info)
            maquina["n_suites_completas"] = sum(
                1 for s in suites_info if int(s["n_execs"]) == _n_cfg)
            maquina["suites_parciais"] = [
                {"suite_id": s["suite_id"], "n_execs": int(s["n_execs"]), "inicio": s["inicio"]}
                for s in suites_info if int(s["n_execs"]) != _n_cfg
            ]

            cur.execute("""
                SELECT id, tempo_total_seg, disco_bytes_lidos, cpu_percent_medio
                FROM tbl_enade_time_benchmark_execucao WHERE campanha_id = %s AND aquecimento ORDER BY id
            """, (cid,))
            aquecimento = [{"id": r["id"], "tempo": _f(r["tempo_total_seg"]),
                            "disco_mb": (r["disco_bytes_lidos"] or 0) / 1e6,
                            "cpu": _f(r["cpu_percent_medio"])} for r in _dicts(cur)]

            # execuções quentes: disco e cpu por configuração
            cur.execute("""
                SELECT modo, num_workers, ordem_submissao,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY disco_bytes_lidos) AS disco_med,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY cpu_percent_medio) AS cpu_med
                FROM tbl_enade_time_benchmark_execucao WHERE campanha_id = %s AND NOT aquecimento
                GROUP BY modo, num_workers, ordem_submissao
            """, (cid,))
            instr = {(r["modo"], r["num_workers"], r["ordem_submissao"]):
                     {"disco_mb": (_f(r["disco_med"]) or 0) / 1e6, "cpu": _f(r["cpu_med"])}
                     for r in _dicts(cur)}
            for r in resumo:
                i = instr.get((r["modo"], r["num_workers"], r["ordem_submissao"]), {})
                r["disco_mb"] = i.get("disco_mb")
                r["cpu"] = i.get("cpu")

            # histórico: execuções sem campanha (rodadas de 21/06 e 21/08)
            cur.execute("""
                SELECT e.id, e.modo, e.num_workers, e.tempo_total_seg, e.throughput_lps,
                       e.timestamp_inicio, e.observacoes,
                       m.speedup, m.eficiencia, m.baseline_execucao_id
                FROM tbl_enade_time_benchmark_execucao e
                LEFT JOIN v_enade_time_benchmark_metricas m ON m.execucao_id = e.id
                WHERE e.campanha_id IS NULL ORDER BY e.id
            """)
            legado = _dicts(cur)
            for r in legado:
                for k in ("tempo_total_seg", "throughput_lps", "speedup", "eficiencia"):
                    r[k] = _f(r[k])
            rodadas: dict[int, dict] = {}
            for r in legado:
                if r["modo"] == "sequencial":
                    rodadas[r["id"]] = {"baseline": r, "paralelas": [], "data": r["timestamp_inicio"]}
            for r in legado:
                if r["modo"] == "paralelo" and r["baseline_execucao_id"] in rodadas:
                    rodadas[r["baseline_execucao_id"]]["paralelas"].append(r)
            historico = [rodadas[k] for k in sorted(rodadas)]

            # o erro de 21/08: speedup contra o sequencial mais recente × pareado
            seqs = [r for r in legado if r["modo"] == "sequencial"]
            mais_recente = max(seqs, key=lambda r: r["timestamp_inicio"]) if seqs else None
            bug = []
            if mais_recente:
                for r in legado:
                    if r["modo"] == "paralelo" and r["speedup"] is not None:
                        s_err = mais_recente["tempo_total_seg"] / r["tempo_total_seg"]
                        if abs(s_err - r["speedup"]) > 0.01:
                            bug.append({"exec": r["id"], "workers": r["num_workers"],
                                        "tempo": r["tempo_total_seg"],
                                        "baseline_errado": mais_recente["id"],
                                        "t_errado": mais_recente["tempo_total_seg"],
                                        "s_errado": s_err, "e_errado": s_err / r["num_workers"],
                                        "baseline_certo": r["baseline_execucao_id"],
                                        "s_certo": r["speedup"], "e_certo": r["eficiencia"]})

            cur.execute("""
                SELECT campanha_id::text AS campanha_id, MIN(timestamp_inicio) AS inicio,
                       COUNT(*) FILTER (WHERE NOT aquecimento) AS n, bool_and(oficial) AS oficial,
                       MIN(observacoes) AS observacoes
                FROM tbl_enade_time_benchmark_execucao WHERE campanha_id IS NOT NULL AND campanha_id <> %s
                GROUP BY campanha_id ORDER BY 2
            """, (cid,))
            outras = _dicts(cur)

        execs, etapas = analise.carregar(conn, cid, None)
        esc = analise.analisar(execs, etapas)
    finally:
        conn.close()

    paralelos = [r for r in resumo if r["modo"] == "paralelo" and r["speedup_mediana"] is not None]
    melhor = max(paralelos, key=lambda r: r["speedup_mediana"]) if paralelos else None
    seq_row = next((r for r in resumo if r["modo"] == "sequencial"), None)

    def cfg(w, o):
        return next((r for r in resumo if r["modo"] == "paralelo" and r["num_workers"] == w
                     and r["ordem_submissao"] == o), None)

    def esc_cfg(w, o):
        return next((r for r in esc["agregado"] if r["workers"] == w and r["ordem"] == o), None)

    workers = sorted({r["num_workers"] for r in paralelos})
    ordens = [o for o in ("crescente", "lpt") if any(r["ordem_submissao"] == o for r in paralelos)]

    return {
        "campanha_id": cid,
        "resumo": resumo,
        "sequencial": seq_row,
        "paralelos": paralelos,
        "melhor": melhor,
        "workers": workers,
        "ordens": ordens,
        "cfg": cfg,
        "esc_cfg": esc_cfg,
        "maquina": maquina,
        "aquecimento": aquecimento,
        "escalonamento": esc,
        "historico": historico,
        "bug_baseline": bug,
        "outras_campanhas": outras,
        "gerado_em": datetime.now(),
    }


if __name__ == "__main__":
    d = carregar()
    print("campanha", d["campanha_id"], "suítes", d["maquina"]["n_suites"], "execuções", d["maquina"]["n_execucoes"])
    for r in d["resumo"]:
        print(f"  {r['rotulo']:<22} n={r['n']} t={seg(r['tempo_mediana'])} [{seg(r['tempo_min'])}–{seg(r['tempo_max'])}] "
              f"S={sx(r['speedup_mediana'])} E={pct(r['eficiencia_mediana'])} disco={br(r['disco_mb'], 1)} MB cpu={br(r['cpu'], 1)} %")
    print("melhor:", d["melhor"] and d["melhor"]["rotulo"])
    print("hipóteses:", d["escalonamento"]["hipoteses"])
    print("bug baseline:", [(b["exec"], round(b["s_errado"], 4), b["s_certo"]) for b in d["bug_baseline"]])
