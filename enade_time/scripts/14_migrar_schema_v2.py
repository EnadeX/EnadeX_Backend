"""
Migração ADITIVA do schema local — nomes da convenção do ecossistema (D12) e v2 do
benchmark (campanhas, suítes, ordem de submissão e instrumentação da máquina) —
SEM apagar nada.

Nomes (D12)
-----------
O banco local nasceu com fato_enade, dim_*, benchmark_execucao, benchmark_etapa,
v_benchmark_metricas e v_benchmark_resumo. O ecossistema EnadeX nomeia por estudo
(tbl_<estudo>_*, v_<estudo>_*), e o Supabase usa esses nomes; para a API poder ler
do banco local ou do Supabase trocando só o DSN, o local passa a usar os mesmos.
O renome é só de metadados (ALTER ... RENAME): nenhuma linha é copiada, as views e
as FKs acompanham, e é reversível com --desfazer-renome. Idempotente.

Substitui o `05_criar_schema_postgres.py --reset` em bancos que já têm dados:
o --reset dropa tbl_enade_time_benchmark_execucao/tbl_enade_time_benchmark_etapa (incidente D9 do DESIGN_LOG).
Aqui só há ALTER TABLE ... ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS
e CREATE OR REPLACE VIEW. Pode rodar quantas vezes for preciso (idempotente).

O que muda
----------
tbl_enade_time_benchmark_execucao  + campanha_id, suite_id, oficial, execucao_uid,
                      ordem_submissao, cpu_fisicos, cpu_logicos,
                      cpu_percent_medio, disco_bytes_lidos, cache_quente,
                      aquecimento
tbl_enade_time_benchmark_etapa     + etapa_uid
v_enade_time_benchmark_metricas  passa a parear cada execução paralela com o sequencial
                      da MESMA suíte. Linhas antigas (suite_id NULL) mantêm o
                      pareamento temporal (sequencial imediatamente anterior),
                      então os ids 1–6 continuam devolvendo os mesmos números.
                      Colunas novas só no FIM (exigência do CREATE OR REPLACE).
v_enade_time_benchmark_resumo    (nova) mediana / mín / máx / IQR / n por
                      (campanha, workers, ordem de submissão); o sequencial
                      entra como configuração (1, NULL) com speedup 1.
tbl_enade_time_publicacao (nova) log das publicações no Supabase (script 12).

Backfill — fatos, não suposições
--------------------------------
ordem_submissao = 'crescente' nas paralelas antigas: era a única ordem que o
script 09 conhecia (submissão de ANOS em ordem crescente, confirmada pelos pids
das etapas). cpu_logicos = cpu_count_maquina: o valor gravado era
os.cpu_count(), que é o número LÓGICO. cpu_fisicos fica NULL nas antigas — não
foi medido na época e não se inventa dado.

Uso
---
  python scripts/14_migrar_schema_v2.py            # aplica (transação única)
  python scripts/14_migrar_schema_v2.py --status   # só mostra o que existe
  python scripts/14_migrar_schema_v2.py --dry-run  # imprime o SQL, não executa

O script 05 importa `aplicar()` daqui para que instalações novas nasçam com o
mesmo schema — a definição vive em um único lugar.
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg2

DB_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname":   os.environ.get("POSTGRES_DB", "enade_db"),
    "user":     os.environ.get("POSTGRES_USER", "enade_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "enade_password"),
}

# ---------------------------------------------------------------------------
# Renome para a convenção do ecossistema (D12) — (nome antigo, nome novo)
# ---------------------------------------------------------------------------

RENOMES_TABELAS = [
    ("fato_enade", "tbl_enade_time_fato"),
    ("dim_regiao", "tbl_enade_time_dim_regiao"),
    ("dim_uf", "tbl_enade_time_dim_uf"),
    ("dim_grupo", "tbl_enade_time_dim_grupo"),
    ("dim_categoria_adm", "tbl_enade_time_dim_categoria_adm"),
    ("dim_organizacao_acad", "tbl_enade_time_dim_organizacao_acad"),
    ("dim_modalidade", "tbl_enade_time_dim_modalidade"),
    ("dim_ano", "tbl_enade_time_dim_ano"),
    ("benchmark_execucao", "tbl_enade_time_benchmark_execucao"),
    ("benchmark_etapa", "tbl_enade_time_benchmark_etapa"),
]
RENOMES_VIEWS = [
    ("v_benchmark_metricas", "v_enade_time_benchmark_metricas"),
    ("v_benchmark_resumo", "v_enade_time_benchmark_resumo"),
]


def _existe(cur, nome: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{nome}",))
    return cur.fetchone()[0]


def renomear(cur, verbose: bool = True, inverso: bool = False) -> int:
    """Renomeia tabelas e views para a convenção (ou de volta, com `inverso`).

    Idempotente: só age quando o nome de origem existe e o de destino não. Se os
    dois existirem, aborta — seria sinal de duas cópias e não se adivinha qual vale.
    Devolve quantos objetos foram renomeados.
    """
    feitos = 0
    for tipo, pares in (("TABLE", RENOMES_TABELAS), ("VIEW", RENOMES_VIEWS)):
        for antigo, novo in pares:
            origem, destino = (novo, antigo) if inverso else (antigo, novo)
            if not _existe(cur, origem):
                continue
            if _existe(cur, destino):
                raise RuntimeError(f"{origem} e {destino} existem ao mesmo tempo; resolva à mão")
            cur.execute(f'ALTER {tipo} "{origem}" RENAME TO "{destino}"')
            feitos += 1
            if verbose:
                print(f"  {origem} -> {destino}")
    return feitos


# ---------------------------------------------------------------------------
# Colunas (todas IF NOT EXISTS; nada é removido ou alterado)
# ---------------------------------------------------------------------------

SQL_COLUNAS = """
ALTER TABLE tbl_enade_time_benchmark_execucao
    ADD COLUMN IF NOT EXISTS campanha_id       UUID          NULL,
    ADD COLUMN IF NOT EXISTS suite_id          UUID          NULL,
    ADD COLUMN IF NOT EXISTS oficial           BOOLEAN       NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS execucao_uid      UUID          NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS ordem_submissao   TEXT          NULL,
    ADD COLUMN IF NOT EXISTS cpu_fisicos       SMALLINT      NULL,
    ADD COLUMN IF NOT EXISTS cpu_logicos       SMALLINT      NULL,
    ADD COLUMN IF NOT EXISTS cpu_percent_medio NUMERIC(5,2)  NULL,
    ADD COLUMN IF NOT EXISTS disco_bytes_lidos BIGINT        NULL,
    ADD COLUMN IF NOT EXISTS cache_quente      BOOLEAN       NULL,
    ADD COLUMN IF NOT EXISTS aquecimento       BOOLEAN       NOT NULL DEFAULT FALSE;

ALTER TABLE tbl_enade_time_benchmark_etapa
    ADD COLUMN IF NOT EXISTS etapa_uid UUID NOT NULL DEFAULT gen_random_uuid();

-- CHECK não tem IF NOT EXISTS: protege via catálogo.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_bench_ordem_submissao'
          AND conrelid = 'tbl_enade_time_benchmark_execucao'::regclass
    ) THEN
        ALTER TABLE tbl_enade_time_benchmark_execucao
            ADD CONSTRAINT chk_bench_ordem_submissao
            CHECK (ordem_submissao IS NULL OR ordem_submissao IN ('crescente', 'lpt'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_bench_exec_uid       ON tbl_enade_time_benchmark_execucao(execucao_uid);
CREATE INDEX        IF NOT EXISTS idx_bench_exec_campanha ON tbl_enade_time_benchmark_execucao(campanha_id);
CREATE INDEX        IF NOT EXISTS idx_bench_exec_suite    ON tbl_enade_time_benchmark_execucao(suite_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_bench_etapa_uid      ON tbl_enade_time_benchmark_etapa(etapa_uid);
"""

SQL_BACKFILL = """
UPDATE tbl_enade_time_benchmark_execucao
   SET ordem_submissao = 'crescente'
 WHERE modo = 'paralelo' AND ordem_submissao IS NULL;

UPDATE tbl_enade_time_benchmark_execucao
   SET cpu_logicos = cpu_count_maquina
 WHERE cpu_logicos IS NULL;
"""

# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

# Colunas 1–10 idênticas à view original (nome, tipo e posição) — o CREATE OR
# REPLACE exige isso. As novas vêm depois.
SQL_VIEW_METRICAS = """
CREATE OR REPLACE VIEW v_enade_time_benchmark_metricas AS
SELECT
    p.id                 AS execucao_id,
    p.timestamp_inicio,
    p.num_workers,
    s.tempo_total_seg    AS tempo_sequencial,
    p.tempo_total_seg    AS tempo_paralelo,
    ROUND((s.tempo_total_seg / p.tempo_total_seg)::NUMERIC, 4) AS speedup,
    ROUND(((s.tempo_total_seg / p.tempo_total_seg) / p.num_workers)::NUMERIC, 4)
        AS eficiencia,
    p.throughput_lps     AS throughput_paralelo,
    s.throughput_lps     AS throughput_sequencial,
    p.cpu_count_maquina,
    p.suite_id,
    p.campanha_id,
    p.ordem_submissao,
    p.oficial,
    s.id                 AS baseline_execucao_id,
    CASE WHEN p.suite_id IS NULL THEN 'temporal' ELSE 'suite' END AS pareamento
FROM tbl_enade_time_benchmark_execucao p
LEFT JOIN LATERAL (
    SELECT b.* FROM tbl_enade_time_benchmark_execucao b
    WHERE b.modo = 'sequencial'
      AND b.aquecimento = FALSE
      AND (
            (p.suite_id IS NOT NULL AND b.suite_id = p.suite_id)
         OR (p.suite_id IS NULL     AND b.timestamp_inicio < p.timestamp_inicio)
      )
    ORDER BY b.timestamp_inicio DESC
    LIMIT 1
) s ON TRUE
WHERE p.modo = 'paralelo';
"""

SQL_VIEW_RESUMO = """
CREATE OR REPLACE VIEW v_enade_time_benchmark_resumo AS
WITH base AS (
    SELECT
        e.campanha_id,
        e.modo,
        e.num_workers,
        CASE WHEN e.modo = 'sequencial' THEN NULL ELSE e.ordem_submissao END AS ordem_submissao,
        e.tempo_total_seg,
        e.throughput_lps,
        e.oficial,
        e.cpu_fisicos,
        e.cpu_logicos,
        e.cache_quente,
        CASE WHEN e.modo = 'sequencial' THEN 1.0::NUMERIC ELSE m.speedup    END AS speedup,
        CASE WHEN e.modo = 'sequencial' THEN 1.0::NUMERIC ELSE m.eficiencia END AS eficiencia
    FROM tbl_enade_time_benchmark_execucao e
    LEFT JOIN v_enade_time_benchmark_metricas m ON m.execucao_id = e.id
    WHERE e.campanha_id IS NOT NULL
      AND e.aquecimento = FALSE
)
SELECT
    campanha_id,
    modo,
    num_workers,
    ordem_submissao,
    COUNT(*)::INT                                                     AS n,
    ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY tempo_total_seg))::NUMERIC, 4) AS tempo_mediana,
    MIN(tempo_total_seg)                                              AS tempo_min,
    MAX(tempo_total_seg)                                              AS tempo_max,
    ROUND((percentile_cont(0.75) WITHIN GROUP (ORDER BY tempo_total_seg)
         - percentile_cont(0.25) WITHIN GROUP (ORDER BY tempo_total_seg))::NUMERIC, 4) AS tempo_iqr,
    ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY throughput_lps))::NUMERIC, 2)   AS throughput_mediana,
    ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY speedup))::NUMERIC, 4)          AS speedup_mediana,
    MIN(speedup)                                                      AS speedup_min,
    MAX(speedup)                                                      AS speedup_max,
    ROUND((percentile_cont(0.5) WITHIN GROUP (ORDER BY eficiencia))::NUMERIC, 4)       AS eficiencia_mediana,
    MIN(eficiencia)                                                   AS eficiencia_min,
    MAX(eficiencia)                                                   AS eficiencia_max,
    bool_and(oficial)                                                 AS oficial,
    MIN(cpu_fisicos)                                                  AS cpu_fisicos,
    MIN(cpu_logicos)                                                  AS cpu_logicos,
    bool_and(cache_quente)                                            AS cache_quente
FROM base
GROUP BY campanha_id, modo, num_workers, ordem_submissao;
"""

SQL_PUBLICACAO = """
CREATE TABLE IF NOT EXISTS tbl_enade_time_publicacao (
    id              BIGSERIAL PRIMARY KEY,
    publicado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alvo            TEXT        NOT NULL,
    metodo          TEXT        NOT NULL,
    linhas          BIGINT      NULL,
    md5_origem      TEXT        NULL,
    versao_dataset  TEXT        NULL,
    host_origem     TEXT        NULL,
    duracao_seg     NUMERIC(10,3) NULL,
    observacoes     TEXT        NULL
);
"""

PASSOS = [
    ("colunas e índices (aditivo)", SQL_COLUNAS),
    ("backfill factual das linhas antigas", SQL_BACKFILL),
    ("v_enade_time_benchmark_metricas (pareamento por suíte)", SQL_VIEW_METRICAS),
    ("v_enade_time_benchmark_resumo (agregados por campanha)", SQL_VIEW_RESUMO),
    ("tbl_enade_time_publicacao", SQL_PUBLICACAO),
]


def aplicar(cur, verbose: bool = True) -> None:
    """Executa todos os passos no cursor recebido. Quem chama controla a transação."""
    if verbose:
        print("  - nomes da convenção do ecossistema (D12)")
    renomear(cur, verbose=verbose)
    for titulo, sql_txt in PASSOS:
        if verbose:
            print(f"  - {titulo}")
        cur.execute(sql_txt)


def status(cur) -> None:
    pendentes = [a for a, _ in RENOMES_TABELAS + RENOMES_VIEWS if _existe(cur, a)]
    if pendentes:
        print("renome D12 pendente (rode o script 14 sem --status):", ", ".join(pendentes))
    else:
        print("nomes: convenção tbl_enade_time_* / v_enade_time_* em dia")
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'tbl_enade_time_benchmark_execucao'
        ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    novas = ["campanha_id", "suite_id", "oficial", "execucao_uid", "ordem_submissao",
             "cpu_fisicos", "cpu_logicos", "cpu_percent_medio", "disco_bytes_lidos",
             "cache_quente", "aquecimento"]
    print("tbl_enade_time_benchmark_execucao:")
    for c in novas:
        print(f"  [{'x' if c in cols else ' '}] {c}")
    cur.execute("SELECT viewname FROM pg_views WHERE schemaname = 'public' ORDER BY 1")
    views = [r[0] for r in cur.fetchall()]
    print("views:", ", ".join(views) or "(nenhuma)")
    cur.execute("SELECT to_regclass('public.tbl_enade_time_publicacao') IS NOT NULL")
    print("tbl_enade_time_publicacao:", "existe" if cur.fetchone()[0] else "ausente")
    if "campanha_id" in cols and "oficial" in cols:
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE campanha_id IS NOT NULL),
                   COUNT(*) FILTER (WHERE oficial),
                   COUNT(*)
            FROM tbl_enade_time_benchmark_execucao
        """)
        com_campanha, oficiais, total = cur.fetchone()
        print(f"execuções: {total} no total, {com_campanha} com campanha, {oficiais} oficiais")
    else:
        cur.execute("SELECT COUNT(*) FROM tbl_enade_time_benchmark_execucao")
        print(f"execuções: {cur.fetchone()[0]} no total (schema ainda sem a v2)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true", help="Só mostra o estado atual.")
    ap.add_argument("--dry-run", action="store_true", help="Imprime o SQL e sai.")
    ap.add_argument("--desfazer-renome", action="store_true",
                    help="Volta aos nomes antigos (fato_enade, benchmark_*…) e sai.")
    args = ap.parse_args()

    if args.dry_run:
        print("-- ===== renome D12 =====")
        for antigo, novo in RENOMES_TABELAS:
            print(f'ALTER TABLE "{antigo}" RENAME TO "{novo}";')
        for antigo, novo in RENOMES_VIEWS:
            print(f'ALTER VIEW "{antigo}" RENAME TO "{novo}";')
        for titulo, sql_txt in PASSOS:
            print(f"-- ===== {titulo} =====\n{sql_txt}")
        return 0

    print(f"Conectando em postgresql://{DB_CONFIG['user']}@"
          f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        print(f"\nERRO ao conectar no PostgreSQL: {e}", file=sys.stderr)
        print("  docker compose up -d postgres", file=sys.stderr)
        return 1

    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if args.status:
                status(cur)
                conn.rollback()
                return 0
            if args.desfazer_renome:
                print("\nDesfazendo o renome D12:")
                n = renomear(cur, inverso=True)
                conn.commit()
                print(f"{n} objetos voltaram aos nomes antigos.")
                return 0
            print("\nRenomeando para a convenção do ecossistema (D12):")
            if renomear(cur) == 0:
                print("  (nada a renomear)")
            cur.execute("SELECT COUNT(*) FROM tbl_enade_time_benchmark_execucao")
            antes = cur.fetchone()[0]
            print("\nAplicando migração v2 (aditiva):")
            aplicar(cur)
            cur.execute("SELECT COUNT(*) FROM tbl_enade_time_benchmark_execucao")
            depois = cur.fetchone()[0]
            if antes != depois:  # nunca deve acontecer — proteção contra perda
                raise RuntimeError(f"contagem mudou ({antes} -> {depois}); abortando")
            print("\nEstado após a migração:")
            status(cur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("\nMigração aplicada. Nenhuma linha foi removida ou sobrescrita.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
