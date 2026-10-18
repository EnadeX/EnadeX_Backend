"""
Repositório do benchmark — SQL explícito, sem ORM.

Regra de auditabilidade (DESIGN_LOG D13): speedup e eficiência têm UMA
definição, em `v_enade_time_benchmark_metricas` (pareamento de cada execução paralela com
o sequencial da própria suíte). Este módulo NÃO recalcula nada em Python — só
lê as views e monta a resposta. A checagem cruzada em Python fica em
`scripts/13_validar_metricas.py` e nos testes.
"""

from psycopg2.extensions import cursor as PgCursor


def _filtro_validas(
    apenas_validas: bool,
    ids_excluir: list[int],
    coluna: str = "id",
) -> tuple[str, dict]:
    """Filtro seguro para excluir ids inválidos.

    Usa `coluna <> ALL(%(ids_excluir)s)` em vez de NOT IN, que é a forma
    nativa de psycopg2 para passar listas como array Postgres com
    placeholders parametrizados.
    """
    if apenas_validas and ids_excluir:
        return (f"AND {coluna} <> ALL(%(ids_excluir)s)", {"ids_excluir": ids_excluir})
    return ("", {})


# Colunas de tbl_enade_time_benchmark_execucao expostas pela API (as da v2 são aditivas).
_COLS_EXECUCAO = """
    id, timestamp_inicio, modo, num_workers,
    tempo_total_seg::float AS tempo_total_seg,
    linhas_processadas, throughput_lps::float AS throughput_lps,
    cpu_count_maquina, cpu_modelo,
    memoria_pico_mb::float AS memoria_pico_mb,
    observacoes,
    campanha_id::text AS campanha_id,
    suite_id::text    AS suite_id,
    oficial, ordem_submissao,
    cpu_fisicos, cpu_logicos,
    cpu_percent_medio::float AS cpu_percent_medio,
    disco_bytes_lidos, cache_quente, aquecimento
"""


# ---------------------------------------------------------------------------
# Execuções e etapas
# ---------------------------------------------------------------------------

def listar_execucoes(
    cursor: PgCursor,
    apenas_validas: bool,
    ids_excluir: list[int],
    campanha_id: str | None = None,
) -> list[dict]:
    where, params = _filtro_validas(apenas_validas, ids_excluir, coluna="id")
    if campanha_id:
        where += " AND campanha_id = %(campanha_id)s"
        params["campanha_id"] = campanha_id
    cursor.execute(
        f"""
        SELECT {_COLS_EXECUCAO}
        FROM tbl_enade_time_benchmark_execucao
        WHERE 1=1 {where}
        ORDER BY id
        """,
        params,
    )
    return list(cursor.fetchall())


def get_execucao(
    cursor: PgCursor,
    execucao_id: int,
    apenas_validas: bool,
    ids_excluir: list[int],
) -> dict | None:
    if apenas_validas and execucao_id in ids_excluir:
        return None
    cursor.execute(
        f"""
        SELECT {_COLS_EXECUCAO}
        FROM tbl_enade_time_benchmark_execucao
        WHERE id = %(id)s
        """,
        {"id": execucao_id},
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def listar_etapas(
    cursor: PgCursor,
    execucao_id: int,
    apenas_validas: bool,
    ids_excluir: list[int],
) -> list[dict] | None:
    if apenas_validas and execucao_id in ids_excluir:
        return None
    cursor.execute(
        "SELECT 1 FROM tbl_enade_time_benchmark_execucao WHERE id = %(id)s",
        {"id": execucao_id},
    )
    if cursor.fetchone() is None:
        return None

    cursor.execute(
        """
        SELECT
            id, execucao_id, ano,
            tempo_seg::float AS tempo_seg,
            linhas_arq3, worker_pid,
            timestamp_inicio, timestamp_fim
        FROM tbl_enade_time_benchmark_etapa
        WHERE execucao_id = %(execucao_id)s
        ORDER BY ano
        """,
        {"execucao_id": execucao_id},
    )
    return list(cursor.fetchall())


# ---------------------------------------------------------------------------
# Métricas (view) e campanhas
# ---------------------------------------------------------------------------

def listar_metricas(
    cursor: PgCursor,
    apenas_validas: bool,
    ids_excluir: list[int],
    campanha_id: str | None = None,
) -> list[dict]:
    where, params = _filtro_validas(apenas_validas, ids_excluir, coluna="execucao_id")
    if campanha_id:
        where += " AND campanha_id = %(campanha_id)s"
        params["campanha_id"] = campanha_id
    cursor.execute(
        f"""
        SELECT
            execucao_id, timestamp_inicio, num_workers,
            tempo_sequencial::float AS tempo_sequencial,
            tempo_paralelo::float AS tempo_paralelo,
            speedup::float AS speedup,
            eficiencia::float AS eficiencia,
            throughput_sequencial::float AS throughput_sequencial,
            throughput_paralelo::float AS throughput_paralelo,
            cpu_count_maquina,
            ordem_submissao,
            suite_id::text    AS suite_id,
            campanha_id::text AS campanha_id,
            oficial, baseline_execucao_id, pareamento
        FROM v_enade_time_benchmark_metricas
        WHERE 1=1 {where}
        ORDER BY execucao_id
        """,
        params,
    )
    return list(cursor.fetchall())


def listar_campanhas(cursor: PgCursor) -> list[dict]:
    """Uma linha por campanha (aquecimento não conta)."""
    cursor.execute(
        """
        SELECT
            campanha_id::text AS campanha_id,
            MIN(timestamp_inicio) AS inicio,
            MAX(timestamp_inicio) AS fim,
            COUNT(*) FILTER (WHERE NOT aquecimento)::int AS n_execucoes,
            COUNT(DISTINCT suite_id) FILTER (WHERE NOT aquecimento)::int AS n_suites,
            COALESCE(bool_and(oficial) FILTER (WHERE NOT aquecimento), FALSE) AS oficial,
            MIN(cpu_fisicos) AS cpu_fisicos,
            MIN(cpu_logicos) AS cpu_logicos,
            MIN(cpu_modelo)  AS cpu_modelo,
            MIN(observacoes) AS observacoes
        FROM tbl_enade_time_benchmark_execucao
        WHERE campanha_id IS NOT NULL
        GROUP BY campanha_id
        ORDER BY MIN(timestamp_inicio) DESC
        """
    )
    return list(cursor.fetchall())


def campanha_oficial_mais_recente(cursor: PgCursor) -> str | None:
    cursor.execute(
        """
        SELECT campanha_id::text AS campanha_id
        FROM tbl_enade_time_benchmark_execucao
        WHERE oficial AND campanha_id IS NOT NULL AND NOT aquecimento
        GROUP BY campanha_id
        ORDER BY MIN(timestamp_inicio) DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return row["campanha_id"] if row else None


def resumo_campanha(cursor: PgCursor, campanha_id: str) -> list[dict]:
    cursor.execute(
        """
        SELECT
            modo, num_workers, ordem_submissao, n,
            tempo_mediana::float AS tempo_mediana,
            tempo_min::float     AS tempo_min,
            tempo_max::float     AS tempo_max,
            tempo_iqr::float     AS tempo_iqr,
            throughput_mediana::float AS throughput_mediana,
            speedup_mediana::float    AS speedup_mediana,
            speedup_min::float        AS speedup_min,
            speedup_max::float        AS speedup_max,
            eficiencia_mediana::float AS eficiencia_mediana,
            eficiencia_min::float     AS eficiencia_min,
            eficiencia_max::float     AS eficiencia_max,
            oficial, cpu_fisicos, cpu_logicos, cache_quente
        FROM v_enade_time_benchmark_resumo
        WHERE campanha_id = %(campanha_id)s
        ORDER BY num_workers, ordem_submissao NULLS FIRST
        """,
        {"campanha_id": campanha_id},
    )
    return list(cursor.fetchall())


def _maquina_da_campanha(cursor: PgCursor, campanha_id: str) -> dict | None:
    cursor.execute(
        """
        SELECT MIN(cpu_fisicos) AS cpu_fisicos, MIN(cpu_logicos) AS cpu_logicos,
               MIN(cpu_modelo) AS cpu_modelo,
               bool_and(cache_quente) AS cache_quente,
               COUNT(DISTINCT suite_id)::int AS n_suites
        FROM tbl_enade_time_benchmark_execucao
        WHERE campanha_id = %(campanha_id)s AND NOT aquecimento
        """,
        {"campanha_id": campanha_id},
    )
    row = cursor.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Comparativo
# ---------------------------------------------------------------------------

def comparativo(
    cursor: PgCursor,
    apenas_validas: bool,
    ids_excluir: list[int],
    campanha_id: str | None = None,
    suite_id: str | None = None,
) -> dict:
    """Comparativo sequencial × paralelo.

    Semântica (retrocompatível com a resposta antiga):
      * `itens[]`   — execuções individuais. Speedup/eficiência vêm SEMPRE de
        `v_enade_time_benchmark_metricas` (paralela pareada com o sequencial da própria
        suíte; nas linhas antigas, com o sequencial imediatamente anterior).
        Sequenciais recebem 1,0 por definição.
      * `resumo[]`  — `v_enade_time_benchmark_resumo` da campanha: mediana/mín/máx/IQR/n
        por (workers, ordem de submissão). Vazio quando não há campanha.
      * Seleção: `campanha_id` explícito > campanha oficial mais recente >
        (banco legado, sem campanha) todas as execuções. `suite_id` restringe
        `itens[]` a uma suíte. `apenas_validas=false` devolve o histórico
        inteiro em `itens[]` (o `resumo[]` continua sendo o da campanha).
      * Baseline: numa suíte, o sequencial dela; numa campanha, a MEDIANA dos
        sequenciais (por isso `baseline_sequencial_id` é null); no legado, o
        sequencial mais recente.
    """
    if campanha_id is None and suite_id is None:
        campanha_id = campanha_oficial_mais_recente(cursor)

    if suite_id is not None and campanha_id is None:
        cursor.execute(
            "SELECT campanha_id::text AS c FROM tbl_enade_time_benchmark_execucao WHERE suite_id = %(s)s LIMIT 1",
            {"s": suite_id},
        )
        row = cursor.fetchone()
        campanha_id = row["c"] if row else None

    where, params = _filtro_validas(apenas_validas, ids_excluir, coluna="e.id")
    if suite_id is not None:
        where += " AND e.suite_id = %(suite_id)s"
        params["suite_id"] = suite_id
    elif campanha_id is not None and apenas_validas:
        where += " AND e.campanha_id = %(campanha_id)s"
        params["campanha_id"] = campanha_id

    cursor.execute(
        f"""
        SELECT
            e.id, e.modo, e.num_workers,
            e.tempo_total_seg::float AS tempo_total_seg,
            e.throughput_lps::float  AS throughput_lps,
            e.cpu_count_maquina,
            e.suite_id::text    AS suite_id,
            e.campanha_id::text AS campanha_id,
            e.ordem_submissao, e.oficial, e.timestamp_inicio,
            CASE WHEN e.modo = 'sequencial' THEN 1.0 ELSE m.speedup::float    END AS speedup,
            CASE WHEN e.modo = 'sequencial' THEN 1.0 ELSE m.eficiencia::float END AS eficiencia,
            m.baseline_execucao_id, m.pareamento
        FROM tbl_enade_time_benchmark_execucao e
        LEFT JOIN v_enade_time_benchmark_metricas m ON m.execucao_id = e.id
        WHERE e.aquecimento = FALSE {where}
        ORDER BY e.modo, e.num_workers, e.ordem_submissao NULLS FIRST, e.id
        """,
        params,
    )
    execucoes = list(cursor.fetchall())

    itens: list[dict] = []
    for ex in execucoes:
        itens.append(
            {
                "execucao_id": int(ex["id"]),
                "modo": ex["modo"],
                "num_workers": int(ex["num_workers"]),
                "tempo_total_seg": float(ex["tempo_total_seg"]),
                "throughput_lps": float(ex["throughput_lps"]),
                "speedup": None if ex["speedup"] is None else float(ex["speedup"]),
                "eficiencia": None if ex["eficiencia"] is None else float(ex["eficiencia"]),
                "suite_id": ex["suite_id"],
                "campanha_id": ex["campanha_id"],
                "ordem_submissao": ex["ordem_submissao"],
                "oficial": bool(ex["oficial"]),
                "baseline_execucao_id": ex["baseline_execucao_id"],
                "pareamento": ex["pareamento"],
            }
        )

    # ----- baseline -----
    baseline_id = None
    tempo_base = None
    thr_base = None
    cpu_count = None
    resumo: list[dict] = []
    maquina = None
    n_suites = None

    if suite_id is not None:
        seq = [i for i in itens if i["modo"] == "sequencial" and i["suite_id"] == suite_id]
        if seq:
            baseline_id = seq[0]["execucao_id"]
            tempo_base = seq[0]["tempo_total_seg"]
            thr_base = seq[0]["throughput_lps"]

    if campanha_id is not None:
        resumo = resumo_campanha(cursor, campanha_id)
        maq = _maquina_da_campanha(cursor, campanha_id)
        if maq:
            n_suites = maq.pop("n_suites", None)
            maquina = maq
        if suite_id is None:
            seq_res = [r for r in resumo if r["modo"] == "sequencial"]
            if seq_res:
                tempo_base = seq_res[0]["tempo_mediana"]
                thr_base = seq_res[0]["throughput_mediana"]

    if campanha_id is None and suite_id is None:
        # banco legado: sequencial mais recente, como na versão anterior da API
        where_b, params_b = _filtro_validas(apenas_validas, ids_excluir, coluna="id")
        cursor.execute(
            f"""
            SELECT id, tempo_total_seg::float AS t, throughput_lps::float AS thr,
                   cpu_count_maquina
            FROM tbl_enade_time_benchmark_execucao
            WHERE modo = 'sequencial' AND NOT aquecimento {where_b}
            ORDER BY timestamp_inicio DESC
            LIMIT 1
            """,
            params_b,
        )
        b = cursor.fetchone()
        if b:
            baseline_id = int(b["id"])
            tempo_base = float(b["t"])
            thr_base = float(b["thr"])
            cpu_count = int(b["cpu_count_maquina"])

    if cpu_count is None and execucoes:
        cpu_count = int(execucoes[0]["cpu_count_maquina"])

    return {
        "baseline_sequencial_id": baseline_id,
        "tempo_baseline_seg": tempo_base,
        "throughput_baseline_lps": thr_base,
        "cpu_count_maquina": cpu_count,
        "campanha_id": campanha_id,
        "suite_id": suite_id,
        "n_suites": n_suites,
        "maquina": maquina,
        "itens": itens,
        "resumo": resumo,
    }


def carga(cursor: PgCursor, carga_id: str | None = None) -> dict:
    """Eixo de carga: a medição pedida (ou a mais recente). Bancos antigos, sem a tabela,
    devolvem uma resposta vazia em vez de erro."""
    vazio = {"carga_id": None, "resumo": [], "repeticoes": []}
    cursor.execute("SELECT to_regclass('public.v_enade_time_benchmark_carga_resumo') IS NOT NULL AS existe")
    if not cursor.fetchone()["existe"]:
        return vazio
    if carga_id is None:
        cursor.execute(
            """SELECT carga_id::text AS carga_id FROM v_enade_time_benchmark_carga_resumo
               GROUP BY carga_id ORDER BY MAX(fim) DESC LIMIT 1"""
        )
        linha = cursor.fetchone()
        if linha is None:
            return vazio
        carga_id = linha["carga_id"]
    cursor.execute(
        """
        SELECT estrategia, n, tempo_mediana::float AS tempo_mediana, tempo_min::float AS tempo_min,
               tempo_max::float AS tempo_max, tempo_iqr::float AS tempo_iqr,
               throughput_mediana::float AS throughput_mediana, rtt_mediana_ms::float AS rtt_mediana_ms,
               bytes_payload, linhas_destino, md5_confere, host_destino, rede, inicio, fim
        FROM v_enade_time_benchmark_carga_resumo WHERE carga_id = %(c)s ORDER BY tempo_mediana
        """,
        {"c": carga_id},
    )
    resumo = list(cursor.fetchall())
    cursor.execute(
        """SELECT estrategia, repeticao::int AS repeticao, tempo_seg::float AS tempo_seg, rtt_ms::float AS rtt_ms
           FROM tbl_enade_time_benchmark_carga WHERE carga_id = %(c)s ORDER BY estrategia, repeticao""",
        {"c": carga_id},
    )
    repeticoes = list(cursor.fetchall())
    cursor.execute(
        """SELECT carga_id::text AS carga_id, estrategia, tempo_mediana::float AS tempo_mediana
           FROM v_enade_time_benchmark_carga_resumo WHERE carga_id::text <> %(c)s ORDER BY fim DESC""",
        {"c": carga_id},
    )
    por_rodada: dict[str, dict[str, float]] = {}
    for r in cursor.fetchall():
        por_rodada.setdefault(r["carga_id"], {})[r["estrategia"]] = r["tempo_mediana"]
    return {"carga_id": carga_id if resumo else None, "resumo": resumo, "repeticoes": repeticoes, "anteriores": list(por_rodada.values())}
