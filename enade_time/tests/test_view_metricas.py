"""
Contrato das views de benchmark (schema v2, `scripts/14_migrar_schema_v2.py`):

  * `v_enade_time_benchmark_metricas` pareia cada execução paralela com o sequencial da
    PRÓPRIA suíte; linhas sem `suite_id` (legado) usam o sequencial
    imediatamente anterior no tempo. Sequenciais nunca aparecem na view;
    aquecimento nunca serve de baseline.
  * `v_enade_time_benchmark_resumo` agrega por (campanha, workers, ordem) com n, mediana,
    mín, máx, IQR — e a mediana bate com numpy (percentile_cont = linear).

Os valores dos ids 1–6 são fatos históricos (rodadas de 21/06 e 21/08) e
funcionam como teste de regressão do pareamento temporal.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

LEGADO = {
    # execucao_id: (baseline, speedup, eficiencia)
    2: (1, Decimal("1.3096"), Decimal("0.6548")),
    3: (1, Decimal("2.0749"), Decimal("0.5187")),
    5: (4, Decimal("1.5165"), Decimal("0.7582")),
    6: (4, Decimal("2.4632"), Decimal("0.6158")),
}


def _rows(cur, sql, params=None):
    cur.execute(sql, params or {})
    return cur.fetchall()


def test_view_nao_contem_sequenciais(cur):
    rows = _rows(cur, """
        SELECT COUNT(*) AS n FROM v_enade_time_benchmark_metricas m
        JOIN tbl_enade_time_benchmark_execucao e ON e.id = m.execucao_id
        WHERE e.modo <> 'paralelo'
    """)
    assert rows[0]["n"] == 0


def test_pareamento_temporal_das_linhas_legadas(cur):
    rows = _rows(cur, """
        SELECT execucao_id, baseline_execucao_id, speedup, eficiencia, pareamento, ordem_submissao
        FROM v_enade_time_benchmark_metricas WHERE execucao_id = ANY(%(ids)s) ORDER BY execucao_id
    """, {"ids": list(LEGADO)})
    if len(rows) != len(LEGADO):
        pytest.skip("banco sem as execuções legadas 2,3,5,6")
    for r in rows:
        base, s, e = LEGADO[r["execucao_id"]]
        assert r["baseline_execucao_id"] == base
        assert r["speedup"] == s
        assert r["eficiencia"] == e
        assert r["pareamento"] == "temporal"
        assert r["ordem_submissao"] == "crescente"  # backfill factual


def test_pareamento_por_suite_usa_o_sequencial_da_propria_suite(cur):
    rows = _rows(cur, """
        SELECT m.execucao_id, m.suite_id, m.baseline_execucao_id, m.pareamento,
               b.suite_id AS suite_base, b.modo AS modo_base, b.aquecimento AS aquec_base
        FROM v_enade_time_benchmark_metricas m
        LEFT JOIN tbl_enade_time_benchmark_execucao b ON b.id = m.baseline_execucao_id
        WHERE m.suite_id IS NOT NULL
    """)
    if not rows:
        pytest.skip("nenhuma execução com suite_id no banco")
    for r in rows:
        assert r["pareamento"] == "suite"
        assert r["baseline_execucao_id"] is not None, f"exec {r['execucao_id']} sem baseline na suíte"
        assert r["suite_base"] == r["suite_id"]
        assert r["modo_base"] == "sequencial"
        assert r["aquec_base"] is False


def test_aquecimento_nunca_e_baseline(cur):
    rows = _rows(cur, """
        SELECT COUNT(*) AS n FROM v_enade_time_benchmark_metricas m
        JOIN tbl_enade_time_benchmark_execucao b ON b.id = m.baseline_execucao_id
        WHERE b.aquecimento
    """)
    assert rows[0]["n"] == 0


def test_speedup_e_eficiencia_sao_t_seq_sobre_t_par(cur):
    rows = _rows(cur, """
        SELECT m.execucao_id, m.num_workers, m.speedup, m.eficiencia,
               s.tempo_total_seg AS t_seq, p.tempo_total_seg AS t_par
        FROM v_enade_time_benchmark_metricas m
        JOIN tbl_enade_time_benchmark_execucao p ON p.id = m.execucao_id
        JOIN tbl_enade_time_benchmark_execucao s ON s.id = m.baseline_execucao_id
    """)
    assert rows, "view vazia"
    for r in rows:
        s = (r["t_seq"] / r["t_par"]).quantize(Decimal("0.0001"))
        e = (r["t_seq"] / r["t_par"] / r["num_workers"]).quantize(Decimal("0.0001"))
        assert r["speedup"] == s, r["execucao_id"]
        assert r["eficiencia"] == e, r["execucao_id"]


def test_resumo_n_e_mediana_batem_com_numpy(cur):
    resumo = _rows(cur, """
        SELECT campanha_id::text AS campanha_id, modo, num_workers, ordem_submissao, n,
               tempo_mediana, tempo_min, tempo_max, tempo_iqr, speedup_mediana
        FROM v_enade_time_benchmark_resumo
    """)
    if not resumo:
        pytest.skip("sem campanhas no banco")
    for r in resumo:
        execs = _rows(cur, """
            SELECT e.id, e.tempo_total_seg, m.speedup
            FROM tbl_enade_time_benchmark_execucao e
            LEFT JOIN v_enade_time_benchmark_metricas m ON m.execucao_id = e.id
            WHERE e.campanha_id = %(c)s AND e.modo = %(modo)s AND e.num_workers = %(w)s
              AND e.aquecimento = FALSE
              AND (e.modo = 'sequencial' OR e.ordem_submissao = %(o)s)
        """, {"c": r["campanha_id"], "modo": r["modo"], "w": r["num_workers"], "o": r["ordem_submissao"]})
        assert r["n"] == len(execs)
        t = np.array([float(x["tempo_total_seg"]) for x in execs])
        assert float(r["tempo_mediana"]) == pytest.approx(float(np.percentile(t, 50)), abs=1e-4)
        assert float(r["tempo_min"]) == pytest.approx(t.min(), abs=1e-9)
        assert float(r["tempo_max"]) == pytest.approx(t.max(), abs=1e-9)
        assert float(r["tempo_iqr"]) == pytest.approx(float(np.percentile(t, 75) - np.percentile(t, 25)), abs=1e-4)
        if r["modo"] == "sequencial":
            assert float(r["speedup_mediana"]) == 1.0
        else:
            s = np.array([float(x["speedup"]) for x in execs])
            assert float(r["speedup_mediana"]) == pytest.approx(float(np.percentile(s, 50)), abs=1e-4)


def test_campanha_oficial_estrutura_e_instrumentacao(cur):
    """9 configurações; cada suíte tem exatamente 1 sequencial; toda suíte
    completa cobre as 8 paralelas; instrumentação preenchida em 100% das
    linhas. Tolera suítes PARCIAIS (interrupção real — DESIGN_LOG D13):
    nada é apagado, e o n varia por configuração."""
    camp = _rows(cur, """
        SELECT campanha_id::text AS c FROM tbl_enade_time_benchmark_execucao
        WHERE oficial AND NOT aquecimento GROUP BY campanha_id
        ORDER BY MIN(timestamp_inicio) DESC LIMIT 1
    """)
    if not camp:
        pytest.skip("nenhuma campanha oficial ainda")
    c = camp[0]["c"]

    suites = _rows(cur, """
        SELECT suite_id::text AS s, COUNT(*) AS n,
               COUNT(*) FILTER (WHERE modo = 'sequencial') AS seqs
        FROM tbl_enade_time_benchmark_execucao WHERE campanha_id = %(c)s AND NOT aquecimento
        GROUP BY suite_id
    """, {"c": c})
    assert suites
    for s_ in suites:
        assert s_["seqs"] == 1, f"suíte {s_['s']} com {s_['seqs']} sequenciais"
    n_por_suite_completa = 9  # 1 sequencial + 4 workers × 2 ordens
    completas = [s_ for s_ in suites if s_["n"] == n_por_suite_completa]
    assert len(completas) >= 3, "menos de 3 suítes completas"

    for s_ in completas:
        cobertura = _rows(cur, """
            SELECT num_workers, ordem_submissao FROM tbl_enade_time_benchmark_execucao
            WHERE suite_id = %(s)s AND modo = 'paralelo'
        """, {"s": s_["s"]})
        assert {(x["num_workers"], x["ordem_submissao"]) for x in cobertura} == {
            (2, "crescente"), (2, "lpt"), (3, "crescente"), (3, "lpt"),
            (4, "crescente"), (4, "lpt"), (6, "crescente"), (6, "lpt"),
        }

    cfg = _rows(cur, "SELECT modo, num_workers, ordem_submissao, n "
                     "FROM v_enade_time_benchmark_resumo WHERE campanha_id = %(c)s", {"c": c})
    assert {(x["num_workers"], x["ordem_submissao"]) for x in cfg} == {
        (1, None), (2, "crescente"), (2, "lpt"), (3, "crescente"), (3, "lpt"),
        (4, "crescente"), (4, "lpt"), (6, "crescente"), (6, "lpt"),
    }
    for x in cfg:
        assert len(completas) <= x["n"] <= len(suites)
    seq_n = next(x["n"] for x in cfg if x["num_workers"] == 1)
    assert seq_n == len(suites)  # toda suíte (mesmo parcial) tem o seu sequencial
    assert sum(x["n"] for x in cfg) == sum(s_["n"] for s_ in suites)

    instr = _rows(cur, """
        SELECT COUNT(*) FILTER (WHERE cpu_fisicos = 4 AND cpu_logicos = 8) AS maq,
               COUNT(*) FILTER (WHERE cpu_percent_medio IS NOT NULL
                                  AND disco_bytes_lidos IS NOT NULL) AS inst,
               COUNT(*) FILTER (WHERE cache_quente) AS quente, COUNT(*) AS n
        FROM tbl_enade_time_benchmark_execucao WHERE campanha_id = %(c)s AND NOT aquecimento
    """, {"c": c})[0]
    assert instr["maq"] == instr["n"]
    assert instr["inst"] == instr["n"]
    assert instr["quente"] == instr["n"]
