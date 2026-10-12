"""
Publica o ENADE-Time no Supabase do ecossistema (D11/D12): banco local -> nuvem.

O Postgres local é o instrumento (onde o experimento é medido); o Supabase é onde os
resultados vivem para o resto do EnadeX. Este script copia, do local para a nuvem, com os
MESMOS nomes nos dois bancos:

  tbl_enade_time_dim_* (7) · tbl_enade_time_fato · tbl_enade_time_benchmark_execucao/_etapa
  v_enade_time_benchmark_metricas · v_enade_time_benchmark_resumo · v_enade_time_curso_ano
  tbl_enade_time_publicacao (log: quem publicou, quando, md5 e versão)

Como
----
COPY via Session Pooler (a Transaction Pooler, porta 6543, não suporta COPY), com a senha
do banco — nunca a chave de serviço do grupo. Tudo em UMA transação: TRUNCATE das tabelas do
ENADE-Time, COPY na ordem das FKs, conferência de md5 linha a linha contra o local; se algo
divergir, ROLLBACK e o Supabase fica como estava. Só toca em objetos tbl_enade_time_* /
v_enade_time_* (e nos nomes antigos do próprio ENADE-Time, que renomeia). Nunca usa a RPC
`truncar_tabela`: o TRUNCATE é por conexão direta.

Primeira publicação: as tabelas antigas do ENADE-Time no Supabase (enade_time_distribuido e
dim_*) são RENOMEADAS para a convenção (ALTER ... RENAME, sem copiar), depois de checar que
nenhuma tabela de outro subprojeto depende delas.

Segurança do que é criado: RLS ligada; leitura pública só de SELECT (anon/authenticated)
nas tabelas e views de dados; o log de publicação só o papel leitor enxerga; views com
security_invoker. Papel `enade_time_reader` (LOGIN, só SELECT, somente leitura): é o usuário
do DSN da API composta (ENADE_TIME_DB_URL_SUPABASE; `--fonte supabase` na API). Alcance real: protege o caminho por DSN; o
PostgREST segue pelas chaves do projeto, por isso o `13 --cruzado` e a republicação
idempotente existem.

Credenciais (ambiente ou enade_time/.env; nunca no git):
  SUPABASE_DB_PASSWORD  obrigatória · SUPABASE_PROJECT_REF · SUPABASE_DB_HOST/PORT/USER/NAME
  (os mesmos do script 11). Banco local: POSTGRES_* (defaults do docker-compose).

Uso
---
  python scripts/12_publicar_supabase.py --status              # só lê: o que há na nuvem
  python scripts/12_publicar_supabase.py --dry-run             # mostra o plano, não grava
  python scripts/12_publicar_supabase.py --preparar            # só schema/políticas/papel
  python scripts/12_publicar_supabase.py                       # prepara + publica (idempotente)
  python scripts/12_publicar_supabase.py --rotacionar-leitor   # nova senha do papel leitor
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import os
import secrets
import socket
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2 import sql

RAIZ = Path(__file__).resolve().parent.parent  # enade_time/
if str(RAIZ.parent) not in sys.path:
    sys.path.insert(0, str(RAIZ.parent))

try:
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
except ImportError:
    pass


def _carregar(nome: str, arquivo: str):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_m14 = _carregar("migrar_schema_v2", "14_migrar_schema_v2.py")  # definição única das views/log
_m11 = _carregar("carregar_supabase", "11_carregar_supabase.py")  # conexão com a pooler

DB_LOCAL = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname": os.environ.get("POSTGRES_DB", "enade_db"),
    "user": os.environ.get("POSTGRES_USER", "enade_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "enade_password"),
}

PAPEL_LEITOR = "enade_time_reader"
VERSAO_DATASET = "v1.1"

# ---------------------------------------------------------------------------
# O que é publicado: (tabela, colunas, chave de ordenação) na ordem das FKs
# ---------------------------------------------------------------------------

_DIMS = [
    ("tbl_enade_time_dim_regiao", ["co_regiao", "nome"]),
    ("tbl_enade_time_dim_uf", ["co_uf", "sigla", "nome", "co_regiao"]),
    ("tbl_enade_time_dim_grupo", ["co_grupo", "nome"]),
    ("tbl_enade_time_dim_categoria_adm", ["co_categad", "nome"]),
    ("tbl_enade_time_dim_organizacao_acad", ["co_orgacad", "nome"]),
    ("tbl_enade_time_dim_modalidade", ["co_modalidade", "nome"]),
    ("tbl_enade_time_dim_ano", ["co_ano", "edicao"]),
]
_FATO = (
    "tbl_enade_time_fato",
    ["id", "nu_ano", "co_curso", "co_ies", "co_categad", "co_orgacad", "co_grupo", "co_modalidade",
     "co_munic_curso", "co_uf_curso", "co_regiao_curso", "media_nt_fg", "media_nt_ger", "media_nt_ce"],
)
_EXEC = (
    "tbl_enade_time_benchmark_execucao",
    ["id", "timestamp_inicio", "modo", "num_workers", "tempo_total_seg", "linhas_processadas",
     "throughput_lps", "cpu_count_maquina", "cpu_modelo", "memoria_pico_mb", "observacoes",
     "campanha_id", "suite_id", "oficial", "execucao_uid", "ordem_submissao", "cpu_fisicos",
     "cpu_logicos", "cpu_percent_medio", "disco_bytes_lidos", "cache_quente", "aquecimento"],
)
_ETAPA = (
    "tbl_enade_time_benchmark_etapa",
    ["id", "execucao_id", "ano", "tempo_seg", "linhas_arq3", "worker_pid", "timestamp_inicio",
     "timestamp_fim", "etapa_uid"],
)
PUBLICADAS = [*_DIMS, _FATO, _EXEC, _ETAPA]  # ordem de carga
CHAVE_ORDEM = {t: c[0] for t, c in PUBLICADAS}
VIEWS = [
    ("v_enade_time_benchmark_metricas", _m14.SQL_VIEW_METRICAS),
    ("v_enade_time_benchmark_resumo", _m14.SQL_VIEW_RESUMO),
    ("v_enade_time_curso_ano", _m14.SQL_VIEW_CURSO_ANO),
]
TABELA_LOG = "tbl_enade_time_publicacao"

# Nomes que o ENADE-Time já tinha no Supabase (migrações de 06/08/2026) -> convenção.
RENOMES_REMOTOS = [("enade_time_distribuido", "tbl_enade_time_fato")] + [
    (antigo, novo) for antigo, novo in _m14.RENOMES_TABELAS if antigo.startswith("dim_")
]

# ---------------------------------------------------------------------------
# DDL remoto (colunas e restrições idênticas às locais; ids vêm do local, sem identity)
# ---------------------------------------------------------------------------

SQL_TABELAS_BENCHMARK = """
CREATE TABLE IF NOT EXISTS public.tbl_enade_time_benchmark_execucao (
    id                 BIGINT PRIMARY KEY,
    timestamp_inicio   TIMESTAMPTZ   NOT NULL,
    modo               VARCHAR(20)   NOT NULL CHECK (modo IN ('sequencial','paralelo')),
    num_workers        SMALLINT      NOT NULL,
    tempo_total_seg    NUMERIC(10,4) NOT NULL,
    linhas_processadas BIGINT        NOT NULL,
    throughput_lps     NUMERIC(12,2) NOT NULL,
    cpu_count_maquina  SMALLINT      NOT NULL,
    cpu_modelo         TEXT          NULL,
    memoria_pico_mb    NUMERIC(10,2) NULL,
    observacoes        TEXT          NULL,
    campanha_id        UUID          NULL,
    suite_id           UUID          NULL,
    oficial            BOOLEAN       NOT NULL DEFAULT FALSE,
    execucao_uid       UUID          NOT NULL,
    ordem_submissao    TEXT          NULL CHECK (ordem_submissao IS NULL OR ordem_submissao IN ('crescente','lpt')),
    cpu_fisicos        SMALLINT      NULL,
    cpu_logicos        SMALLINT      NULL,
    cpu_percent_medio  NUMERIC(5,2)  NULL,
    disco_bytes_lidos  BIGINT        NULL,
    cache_quente       BOOLEAN       NULL,
    aquecimento        BOOLEAN       NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_bench_exec_uid       ON public.tbl_enade_time_benchmark_execucao(execucao_uid);
CREATE INDEX        IF NOT EXISTS idx_bench_exec_campanha ON public.tbl_enade_time_benchmark_execucao(campanha_id);
CREATE INDEX        IF NOT EXISTS idx_bench_exec_suite    ON public.tbl_enade_time_benchmark_execucao(suite_id);

CREATE TABLE IF NOT EXISTS public.tbl_enade_time_benchmark_etapa (
    id               BIGINT PRIMARY KEY,
    execucao_id      BIGINT        NOT NULL REFERENCES public.tbl_enade_time_benchmark_execucao(id) ON DELETE CASCADE,
    ano              SMALLINT      NOT NULL,
    tempo_seg        NUMERIC(10,4) NOT NULL,
    linhas_arq3      BIGINT        NOT NULL,
    worker_pid       INTEGER       NULL,
    timestamp_inicio TIMESTAMPTZ   NOT NULL,
    timestamp_fim    TIMESTAMPTZ   NOT NULL,
    etapa_uid        UUID          NOT NULL
);
CREATE INDEX        IF NOT EXISTS idx_bench_etapa_exec ON public.tbl_enade_time_benchmark_etapa(execucao_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_bench_etapa_uid   ON public.tbl_enade_time_benchmark_etapa(etapa_uid);
"""


def _view_remota(sql_view: str) -> str:
    """A mesma view do script 14, mas com security_invoker (a RLS das tabelas vale para quem consulta)."""
    nome = sql_view.split("CREATE OR REPLACE VIEW ", 1)[1].split(" AS", 1)[0].strip()
    return sql_view.replace(
        f"CREATE OR REPLACE VIEW {nome} AS",
        f"CREATE OR REPLACE VIEW public.{nome} WITH (security_invoker = true) AS",
        1,
    )


# ---------------------------------------------------------------------------
# Conexões
# ---------------------------------------------------------------------------

def conectar_local():
    conn = psycopg2.connect(**DB_LOCAL)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'UTC'")
    return conn


def conectar_remoto():
    if not os.environ.get("SUPABASE_DB_PASSWORD") and not os.environ.get("SUPABASE_DB_URL"):
        raise SystemExit("Defina SUPABASE_DB_PASSWORD (ou SUPABASE_DB_URL) no ambiente ou em enade_time/.env.")
    origem, rotas = _m11.montar_conexao()
    conn = _m11.conectar(rotas)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'UTC'")
    return conn


def _existe(cur, nome: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{nome}",))
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Schema remoto
# ---------------------------------------------------------------------------

def checar_dependentes(cur) -> None:
    """Antes de renomear: nenhuma tabela de FORA do ENADE-Time pode depender das antigas."""
    nossas = {a for a, _ in RENOMES_REMOTOS} | {n for _, n in RENOMES_REMOTOS} | {
        t for t, _ in PUBLICADAS
    }
    cur.execute(
        """SELECT conrelid::regclass::text, confrelid::regclass::text
           FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace"""
    )
    for filha, mae in cur.fetchall():
        filha, mae = filha.replace("public.", ""), mae.replace("public.", "")
        if mae in nossas and filha not in nossas:
            raise RuntimeError(f"{filha} referencia {mae}: não é do ENADE-Time; abortando o renome")
    cur.execute(
        """SELECT DISTINCT dependente.relname
           FROM pg_depend d
           JOIN pg_rewrite r ON r.oid = d.objid
           JOIN pg_class dependente ON dependente.oid = r.ev_class
           JOIN pg_class fonte ON fonte.oid = d.refobjid
           WHERE fonte.relname = ANY(%s) AND dependente.relname <> fonte.relname""",
        (sorted(nossas),),
    )
    for (view,) in cur.fetchall():
        if view not in {v for v, _ in VIEWS}:
            raise RuntimeError(f"a view {view} depende de tabelas do ENADE-Time; não é nossa; abortando")


def renomear_remoto(cur) -> int:
    n = 0
    for antigo, novo in RENOMES_REMOTOS:
        if _existe(cur, antigo) and not _existe(cur, novo):
            cur.execute(sql.SQL("ALTER TABLE public.{} RENAME TO {}").format(
                sql.Identifier(antigo), sql.Identifier(novo)))
            print(f"  renomeada: {antigo} -> {novo}")
            n += 1
    return n


def _politicas(cur, relacao: str, publica: bool) -> None:
    ident = sql.Identifier("public", relacao)
    cur.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(ident))
    cur.execute(sql.SQL('DROP POLICY IF EXISTS "leitura publica" ON {}').format(ident))
    cur.execute(sql.SQL("REVOKE ALL ON {} FROM anon, authenticated").format(ident))
    if publica:
        cur.execute(sql.SQL(
            'CREATE POLICY "leitura publica" ON {} FOR SELECT TO anon, authenticated USING (true)'
        ).format(ident))
        cur.execute(sql.SQL("GRANT SELECT ON {} TO anon, authenticated").format(ident))


def preparar_remoto(cur) -> None:
    print("\n[1/5] Verificando dependências e renomeando para a convenção:")
    checar_dependentes(cur)
    if renomear_remoto(cur) == 0:
        print("  (nada a renomear)")

    print("[2/5] Tabelas de benchmark e log de publicação:")
    cur.execute(SQL_TABELAS_BENCHMARK)
    cur.execute(_m14.SQL_PUBLICACAO.replace("CREATE TABLE IF NOT EXISTS ", "CREATE TABLE IF NOT EXISTS public."))

    print("[3/5] Views (security_invoker):")
    for nome, sql_view in VIEWS:
        cur.execute(_view_remota(sql_view))
        cur.execute(sql.SQL("REVOKE ALL ON {} FROM anon, authenticated").format(sql.Identifier("public", nome)))
        cur.execute(sql.SQL("GRANT SELECT ON {} TO anon, authenticated").format(sql.Identifier("public", nome)))
        print(f"  {nome}")

    print("[4/5] RLS e permissões mínimas (leitura pública só de SELECT):")
    for tabela, _ in PUBLICADAS:
        _politicas(cur, tabela, publica=True)
    _politicas(cur, TABELA_LOG, publica=False)


def garantir_papel_leitor(cur, rotacionar: bool = False) -> str | None:
    """Cria o papel só-leitura. Devolve a senha SÓ quando ela é definida agora (senão None)."""
    print("[5/5] Papel leitor da API composta (somente leitura):")
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (PAPEL_LEITOR,))
    existe = cur.fetchone() is not None
    senha = None
    if not existe:
        senha = secrets.token_urlsafe(24)
        cur.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}").format(
            sql.Identifier(PAPEL_LEITOR), sql.Literal(senha)))
        print(f"  papel {PAPEL_LEITOR} criado")
    elif rotacionar:
        senha = secrets.token_urlsafe(24)
        cur.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(PAPEL_LEITOR), sql.Literal(senha)))
        print(f"  senha do papel {PAPEL_LEITOR} rotacionada")
    else:
        print(f"  papel {PAPEL_LEITOR} já existe (senha mantida)")
    leitor = sql.Identifier(PAPEL_LEITOR)
    cur.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(leitor))
    cur.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = '30s'").format(leitor))
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(leitor))
    for relacao in [t for t, _ in PUBLICADAS] + [v for v, _ in VIEWS] + [TABELA_LOG]:
        cur.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier("public", relacao), leitor))
    for relacao in [t for t, _ in PUBLICADAS] + [TABELA_LOG]:
        ident = sql.Identifier("public", relacao)
        cur.execute(sql.SQL('DROP POLICY IF EXISTS "leitura enade_time_reader" ON {}').format(ident))
        cur.execute(sql.SQL(
            'CREATE POLICY "leitura enade_time_reader" ON {} FOR SELECT TO {} USING (true)'
        ).format(ident, leitor))
    return senha


def gravar_dsn_leitor(senha: str, destino: tuple[str, str, str]) -> Path:
    """Escreve ENADE_TIME_DB_URL_SUPABASE em enade_time/.env (ignorado pelo git). A senha nunca é impressa.

    A chave NÃO é a ENADE_TIME_DB_URL: esta aponta a API para outro banco e, se ficasse ativa, a
    API desta máquina passaria a ler da nuvem sem ninguém pedir (o local é o instrumento do
    experimento). Para usar a nuvem: `python enade_time/enade_time_rotas.py --fonte supabase`.
    """
    host, porta, dbname = destino  # da conexão que de fato autenticou (a pooler tem mais de um cluster)
    ref = os.environ.get("SUPABASE_PROJECT_REF", _m11.PROJECT_REF)
    usuario = f"{PAPEL_LEITOR}.{ref}" if "pooler" in host else PAPEL_LEITOR
    dsn = f"postgresql://{usuario}:{senha}@{host}:{porta}/{dbname}?sslmode=require"
    env = RAIZ / ".env"
    linhas = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    linhas = [l for l in linhas if not l.startswith("ENADE_TIME_DB_URL_SUPABASE=")]
    linhas.append(f"ENADE_TIME_DB_URL_SUPABASE={dsn}")
    env.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return env


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------

def _md5_tabela(cur, tabela: str) -> tuple[int, str]:
    chave = CHAVE_ORDEM[tabela]
    cur.execute(sql.SQL(
        "SELECT count(*), coalesce(md5(string_agg(t::text, '|' ORDER BY t.{})), '') FROM {} t"
    ).format(sql.Identifier(chave), sql.Identifier("public", tabela)))
    n, md5 = cur.fetchone()
    return n, md5


def publicar_dados(local, remoto) -> dict[str, tuple[int, str]]:
    """TRUNCATE + COPY de todas as tabelas, e conferência de md5 contra o local."""
    lc, rc = local.cursor(), remoto.cursor()
    nomes = [sql.Identifier("public", t) for t, _ in PUBLICADAS]
    print("\nPublicando dados (uma transação):")
    rc.execute(sql.SQL("TRUNCATE {}").format(sql.SQL(", ").join(nomes)))
    for tabela, colunas in PUBLICADAS:
        cols = sql.SQL(", ").join(sql.Identifier(c) for c in colunas)
        buf = io.StringIO()
        lc.copy_expert(sql.SQL("COPY (SELECT {} FROM {} ORDER BY {}) TO STDOUT WITH (FORMAT csv)").format(
            cols, sql.Identifier(tabela), sql.Identifier(CHAVE_ORDEM[tabela])).as_string(local), buf)
        buf.seek(0)
        rc.copy_expert(sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv)").format(
            sql.Identifier("public", tabela), cols).as_string(remoto), buf)
        print(f"  {tabela}: {rc.rowcount} linhas")
    # a sequência da identity do fato acompanha o maior id publicado
    rc.execute("SELECT coalesce(max(id), 0) + 1 FROM public.tbl_enade_time_fato")
    proximo = rc.fetchone()[0]
    rc.execute(sql.SQL("ALTER TABLE public.tbl_enade_time_fato ALTER COLUMN id RESTART WITH {}").format(
        sql.Literal(proximo)))

    print("\nConferindo md5 linha a linha (local × nuvem):")
    resultado: dict[str, tuple[int, str]] = {}
    for tabela, _ in PUBLICADAS:
        n_l, h_l = _md5_tabela(lc, tabela)
        n_r, h_r = _md5_tabela(rc, tabela)
        ok = (n_l, h_l) == (n_r, h_r)
        print(f"  {'OK  ' if ok else 'FAIL'} {tabela}: {n_l} × {n_r} linhas · md5 {h_l[:10]} × {h_r[:10]}")
        if not ok:
            raise RuntimeError(f"divergência em {tabela}; transação revertida, nada foi alterado na nuvem")
        resultado[tabela] = (n_l, h_l)
    return resultado


def registrar_log(local, remoto, resultado, duracao: float) -> None:
    lc = local.cursor()
    lc.execute("""SELECT campanha_id FROM tbl_enade_time_benchmark_execucao
                  WHERE oficial ORDER BY timestamp_inicio DESC LIMIT 1""")
    linha = lc.fetchone()
    versao = f"{VERSAO_DATASET}; campanha {str(linha[0])[:8]}" if linha else VERSAO_DATASET
    n_total = sum(n for n, _ in resultado.values())
    md5_fato = resultado[_FATO[0]][1]
    valores = ("supabase", "copy", n_total, md5_fato, versao, socket.gethostname(), round(duracao, 3),
               f"{len(resultado)} tabelas; views: " + ", ".join(v for v, _ in VIEWS))
    insert = sql.SQL("""INSERT INTO {} (alvo, metodo, linhas, md5_origem, versao_dataset, host_origem,
                        duracao_seg, observacoes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""")
    remoto.cursor().execute(insert.format(sql.Identifier("public", TABELA_LOG)), valores)
    lc.execute(insert.format(sql.Identifier(TABELA_LOG)), valores)
    local.commit()


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_status() -> int:
    remoto = conectar_remoto()
    cur = remoto.cursor()
    print("Estado do ENADE-Time no Supabase (somente leitura):")
    pend = [a for a, n in RENOMES_REMOTOS if _existe(cur, a) and not _existe(cur, n)]
    if pend:
        print("  renome pendente:", ", ".join(pend))
    for tabela, _ in PUBLICADAS:
        if _existe(cur, tabela):
            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier("public", tabela)))
            print(f"  {tabela}: {cur.fetchone()[0]} linhas")
        else:
            print(f"  {tabela}: ausente")
    for nome, _ in VIEWS:
        print(f"  {nome}: {'existe' if _existe(cur, nome) else 'ausente'}")
    if _existe(cur, TABELA_LOG):
        cur.execute(sql.SQL("SELECT publicado_em, linhas, versao_dataset FROM {} ORDER BY id DESC LIMIT 1").format(
            sql.Identifier("public", TABELA_LOG)))
        print("  última publicação:", cur.fetchone() or "nenhuma")
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    print("  tamanho do banco:", cur.fetchone()[0])
    remoto.rollback()
    remoto.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true", help="Só lê: mostra o que há na nuvem.")
    ap.add_argument("--dry-run", action="store_true", help="Mostra o plano e as checagens, sem gravar.")
    ap.add_argument("--preparar", action="store_true", help="Só schema, políticas e papel (sem dados).")
    ap.add_argument("--sem-leitor", action="store_true", help="Não cria/atualiza o papel enade_time_reader.")
    ap.add_argument("--rotacionar-leitor", action="store_true", help="Nova senha do papel leitor.")
    args = ap.parse_args()

    if args.status:
        return cmd_status()

    inicio = time.monotonic()
    local, remoto = conectar_local(), conectar_remoto()
    destino = (remoto.info.host, remoto.info.port, remoto.info.dbname)
    senha = None
    try:
        rc = remoto.cursor()
        checar_dependentes(rc)
        if args.dry_run:
            print("DRY-RUN: nenhuma alteração será feita.")
            print("  renomear:", [f"{a} -> {n}" for a, n in RENOMES_REMOTOS if _existe(rc, a) and not _existe(rc, n)] or "nada")
            lc = local.cursor()
            for tabela, _ in PUBLICADAS:
                lc.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabela)))
                print(f"  publicaria {tabela}: {lc.fetchone()[0]} linhas")
            remoto.rollback()
            return 0
        preparar_remoto(rc)
        if not args.sem_leitor:
            senha = garantir_papel_leitor(rc, rotacionar=args.rotacionar_leitor)
        if not args.preparar:
            resultado = publicar_dados(local, remoto)
            registrar_log(local, remoto, resultado, time.monotonic() - inicio)
        remoto.commit()
    except Exception:
        remoto.rollback()
        local.rollback()
        raise
    finally:
        local.close()
        remoto.close()

    if senha:
        env = gravar_dsn_leitor(senha, destino)
        print(f"\nENADE_TIME_DB_URL_SUPABASE do papel {PAPEL_LEITOR} gravada em {env} (ignorado pelo git; a senha não é exibida).")
        print("Para a API ler da nuvem: python enade_time/enade_time_rotas.py --fonte supabase")
    print("\nPublicação concluída." if not args.preparar else "\nSchema remoto preparado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
