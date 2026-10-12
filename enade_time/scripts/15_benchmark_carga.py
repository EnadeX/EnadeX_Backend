"""
Eixo de carga: o custo de PUBLICAR a base no destino, local × nuvem (DESIGN_LOG D17).

O experimento de SPD mede o ETL num Postgres local controlado. Mover a persistência para um
serviço de rede trocaria uma variável que o experimento controla por uma que ele não controla
(o erro do OneDrive). Este script mede o custo dessa troca, separado do speedup: é CUSTO DE
PUBLICAÇÃO (mediana e IQR), nunca speedup, e vale para as condições registradas (rede, RTT,
host) — uma medição situada, não uma propriedade do Supabase.

Estratégias (cada repetição carrega as 24.967 linhas numa tabela VAZIA e dedicada):
  copy_local        COPY FROM STDIN no Postgres local (o instrumento)
  copy_pooler       o mesmo COPY pelo Session Pooler do Supabase (conexão + COPY + commit)
  upsert_postgrest  upsert em lotes de 2.000 pelo PostgREST, com o util_db do grupo; precisa de
                    SUPABASE_URL (referência) e SUPABASE_KEY (chave pública). Sem elas a
                    estratégia é pulada e o resumo diz que ela não foi medida.

Controles (explicam as medidas acima: de onde vem o custo?):
  controle_local_sem_estrutura    COPY local numa tabela temporária sem índices, FKs nem checks
  controle_pooler_sem_estrutura   o mesmo pelo Session Pooler: a diferença para o anterior é o
                                  custo de rede/TLS/servidor, sem a estrutura da fato
  controle_local_so_indices       COPY local com a PK e os 10 índices, sem FKs
  controle_local_so_fks           COPY local com a PK e as 7 FKs, sem os índices secundários

Protocolo
  * As estratégias são INTERCALADAS dentro de cada repetição (rep 1: local, pooler, postgrest;
    rep 2: ...), para a deriva da rede não cair toda sobre uma delas.
  * Destino dedicado (tbl_enade_time_fato_bench, mesma estrutura da fato com FKs e índices):
    a fato publicada NUNCA é truncada pelo experimento. O TRUNCATE antes de cada repetição é
    por conexão direta (nunca pela RPC truncar_tabela) e fica fora do tempo medido: toda carga
    é "carga em tabela vazia".
  * Mesmos bytes nas três estratégias: o buffer vem do script 06 e o id de cada linha é o
    ordinal dela no CSV v1.1 (determinístico, o mesmo id da fato publicada). Depois de cada
    carga, contagem e md5 do destino precisam bater com os da fato (fora do tempo medido).
  * RTT medido NO CANAL testado, antes de cada carga: 5 × SELECT 1 (local e pooler) ou 5 × GET
    pequeno no PostgREST; guarda-se a mediana. Também ficam a rede (cabo/wi-fi), o host de
    destino e o tamanho do payload.
  * O upsert pelo PostgREST exige que o papel `anon` escreva na tabela dedicada. A permissão é
    aberta só durante a medição e fechada no fim, mesmo se der erro (`--limpar-permissoes`
    refaz o fechamento).

Uso
  python scripts/15_benchmark_carga.py --preparar              # cria o destino dedicado na nuvem
  python scripts/15_benchmark_carga.py --dry-run               # mostra o que mediria
  python scripts/15_benchmark_carga.py --reps 10 --rede cabo   # mede (mediana/IQR de 10)
  python scripts/15_benchmark_carga.py --limpar-permissoes

Credenciais: SUPABASE_DB_PASSWORD (+ SUPABASE_PROJECT_REF) para as estratégias de COPY;
SUPABASE_URL e SUPABASE_KEY para o PostgREST. Ambiente ou enade_time/.env; nunca no git.
Depois de medir, `12_publicar_supabase.py` publica o resultado (tbl_enade_time_benchmark_carga).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2 import sql

RAIZ = Path(__file__).resolve().parent.parent  # enade_time/
if str(RAIZ.parent) not in sys.path:
    sys.path.insert(0, str(RAIZ.parent))


def _carregar(nome: str, arquivo: str):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_m06 = _carregar("carregar_dados_postgres", "06_carregar_dados_postgres.py")
_m11 = _carregar("carregar_supabase", "11_carregar_supabase.py")
_m12 = _carregar("publicar_supabase", "12_publicar_supabase.py")

TABELA_BENCH = "tbl_enade_time_fato_bench"
TABELA_CARGA = "tbl_enade_time_benchmark_carga"
PRINCIPAIS = ("copy_local", "copy_pooler", "upsert_postgrest")
CONTROLES = ("controle_local_sem_estrutura", "controle_pooler_sem_estrutura",
             "controle_local_so_indices", "controle_local_so_fks")
ESTRATEGIAS = PRINCIPAIS + CONTROLES
TABELA_CTL = "tbl_enade_time_fato_ctl"  # descartável: só existe durante um controle local com estrutura
COLUNAS = ["id"] + _m06.COLUNAS_DESTINO
LINHAS = _m06.LINHAS_ESPERADAS
POLITICA_TEMPORARIA = "bench temporario"

def copy_sql(tabela: str) -> str:
    return f"COPY {tabela} ({', '.join(COLUNAS)}) FROM STDIN WITH (FORMAT csv, DELIMITER ';', NULL '')"


_COPY_SQL = copy_sql(TABELA_BENCH)

_FKS = [("nu_ano", "tbl_enade_time_dim_ano(co_ano)"), ("co_categad", "tbl_enade_time_dim_categoria_adm(co_categad)"),
        ("co_orgacad", "tbl_enade_time_dim_organizacao_acad(co_orgacad)"), ("co_grupo", "tbl_enade_time_dim_grupo(co_grupo)"),
        ("co_modalidade", "tbl_enade_time_dim_modalidade(co_modalidade)"), ("co_uf_curso", "tbl_enade_time_dim_uf(co_uf)"),
        ("co_regiao_curso", "tbl_enade_time_dim_regiao(co_regiao)")]


# ---------------------------------------------------------------------------
# Dados: os mesmos bytes para todas as estratégias
# ---------------------------------------------------------------------------

def preparar_dados() -> tuple[str, pd.DataFrame]:
    """(texto do COPY com id, DataFrame para o upsert). id = ordinal da linha no CSV."""
    df = pd.read_csv(_m06.ARQ_CONS, sep=";", encoding="utf-8-sig")
    linhas = _m06.preparar_buffer(df).getvalue().splitlines()
    texto = "\n".join(f"{i};{linha}" for i, linha in enumerate(linhas, start=1)) + "\n"
    df_up = df[_m06.COLUNAS_ORIGEM].copy()
    df_up.columns = _m06.COLUNAS_DESTINO
    df_up.insert(0, "id", range(1, len(df_up) + 1))
    return texto, df_up


def md5_tabela(cur, tabela: str) -> tuple[int, str]:
    cur.execute(sql.SQL(
        "SELECT count(*), coalesce(md5(string_agg(t::text, '|' ORDER BY t.id)), '') FROM {} t"
    ).format(sql.Identifier(tabela)))
    n, h = cur.fetchone()
    return n, h


def rtt_sql(conn, n: int = 5) -> float:
    """Mediana (ms) de n idas e voltas de um SELECT 1 pelo canal já aberto."""
    medidas = []
    with conn.cursor() as cur:
        for _ in range(n):
            t0 = time.perf_counter()
            cur.execute("SELECT 1")
            cur.fetchone()
            medidas.append((time.perf_counter() - t0) * 1000)
    conn.rollback()
    return statistics.median(medidas)


def rtt_http(url: str, chave: str, n: int = 5) -> float:
    """Mediana (ms) de n GETs pequenos ao PostgREST (uma linha de uma dimensão pública)."""
    alvo = f"{url}/rest/v1/tbl_enade_time_dim_ano?select=co_ano&limit=1"
    pedido = urllib.request.Request(alvo, headers={"apikey": chave, "Authorization": f"Bearer {chave}"})
    medidas = []
    for _ in range(n):
        t0 = time.perf_counter()
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            resposta.read()
        medidas.append((time.perf_counter() - t0) * 1000)
    return statistics.median(medidas)


def detectar_rede() -> str:
    """Melhor esforço no Windows: 'cabo', 'wifi', 'wifi+cabo' ou 'desconhecida'. Use --rede para fixar."""
    try:
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object -ExpandProperty InterfaceDescription"],
            capture_output=True, text=True, timeout=15,
        ).stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return "desconhecida"
    wifi = "wi-fi" in saida or "wireless" in saida or "wlan" in saida
    cabo = "ethernet" in saida or "gbe" in saida or "realtek pcie" in saida
    return "wifi+cabo" if wifi and cabo else "wifi" if wifi else "cabo" if cabo else "desconhecida"


# ---------------------------------------------------------------------------
# As três estratégias. Cada uma devolve (tempo_seg, rtt_ms, bytes_payload, host_destino)
# ---------------------------------------------------------------------------

def truncar(conn) -> None:
    """TRUNCATE por conexão direta, fora do tempo medido. Nunca pela RPC truncar_tabela."""
    with conn.cursor() as cur:
        cur.execute(sql.SQL("TRUNCATE {}").format(sql.Identifier(TABELA_BENCH)))
    conn.commit()


def carregar_copy_local(ctl, texto: str) -> tuple[float, float, int, str]:
    truncar(ctl)
    rtt = rtt_sql(ctl)
    t0 = time.perf_counter()
    conn = psycopg2.connect(**_m12.DB_LOCAL)
    with conn.cursor() as cur:
        cur.copy_expert(_COPY_SQL, io.StringIO(texto))
    conn.commit()
    dt = time.perf_counter() - t0
    conn.close()
    return dt, rtt, len(texto.encode("utf-8")), f"{_m12.DB_LOCAL['host']}:{_m12.DB_LOCAL['port']} (docker)"


def carregar_copy_pooler(ctl, texto: str) -> tuple[float, float, int, str]:
    truncar(ctl)
    rtt = rtt_sql(ctl)
    _, rotas = _m11.montar_conexao()
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        conn = _m11.conectar(rotas)
    with conn.cursor() as cur:
        cur.copy_expert(_COPY_SQL, io.StringIO(texto))
    conn.commit()
    dt = time.perf_counter() - t0
    host = f"{conn.info.host}:{conn.info.port}"
    conn.close()
    return dt, rtt, len(texto.encode("utf-8")), host


def carregar_upsert_postgrest(ctl, df_up: pd.DataFrame, url: str, chave: str) -> tuple[float, float, int, str]:
    from enade_time import enade_time_dados as dados

    truncar(ctl)
    rtt = rtt_http(url, chave)
    payload = len(df_up.to_json(orient="records"))
    t0 = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):  # o util_db imprime uma linha por lote
        dados.upsert_lotes(df_up, TABELA_BENCH, colunas_inteiras=dados.COLUNAS_INTEIRAS_FATO)
    dt = time.perf_counter() - t0
    return dt, rtt, payload, url.replace("https://", "")


def preparar_destino_controle(cur, estrategia: str) -> str:
    """Cria (fora do tempo medido) o destino do controle e devolve o nome da tabela."""
    if estrategia in ("controle_local_sem_estrutura", "controle_pooler_sem_estrutura"):
        cur.execute(f"CREATE TEMP TABLE {TABELA_CTL} (LIKE {TABELA_BENCH})")
    elif estrategia == "controle_local_so_indices":
        cur.execute(f"DROP TABLE IF EXISTS {TABELA_CTL}")
        cur.execute(f"CREATE TABLE {TABELA_CTL} (LIKE {TABELA_BENCH} INCLUDING INDEXES)")
    else:  # controle_local_so_fks
        cur.execute(f"DROP TABLE IF EXISTS {TABELA_CTL}")
        cur.execute(f"CREATE TABLE {TABELA_CTL} (LIKE {TABELA_BENCH})")
        cur.execute(f"ALTER TABLE {TABELA_CTL} ADD PRIMARY KEY (id)")
        for coluna, ref in _FKS:
            cur.execute(f"ALTER TABLE {TABELA_CTL} ADD FOREIGN KEY ({coluna}) REFERENCES {ref}")
    return TABELA_CTL


def carregar_controle(estrategia: str, ctl, texto: str) -> tuple[float, float, int, str, tuple[int, str]]:
    """Mede o COPY num destino com menos estrutura. `ctl` é a conexão de controle do canal
    (local ou pooler), usada só para o RTT. Devolve também (linhas, md5) lidos na MESMA sessão,
    porque a tabela temporária só existe nela."""
    pooler = estrategia.startswith("controle_pooler")
    rtt = rtt_sql(ctl)
    _, rotas = _m11.montar_conexao()
    t0 = time.perf_counter()
    if pooler:
        with contextlib.redirect_stdout(io.StringIO()):
            conn = _m11.conectar(rotas)
    else:
        conn = psycopg2.connect(**_m12.DB_LOCAL)
    t_conexao = time.perf_counter() - t0
    try:
        cur = conn.cursor()
        destino = preparar_destino_controle(cur, estrategia)  # fora do tempo medido
        t1 = time.perf_counter()
        cur.copy_expert(copy_sql(destino), io.StringIO(texto))
        conn.commit()
        dt = t_conexao + (time.perf_counter() - t1)
        verificacao = md5_tabela(cur, destino)
        conn.rollback()
        host = f"{conn.info.host}:{conn.info.port}" + ("" if pooler else " (docker)")
        if destino == TABELA_CTL and not estrategia.endswith("sem_estrutura"):
            cur.execute(f"DROP TABLE IF EXISTS {TABELA_CTL}")
            conn.commit()
    finally:
        conn.close()
    return dt, rtt, len(texto.encode("utf-8")), host, verificacao


# ---------------------------------------------------------------------------
# Permissão temporária do PostgREST na tabela dedicada
# ---------------------------------------------------------------------------

def abrir_permissao_postgrest(cur) -> None:
    ident = sql.Identifier("public", TABELA_BENCH)
    cur.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(ident))
    cur.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(sql.Identifier(POLITICA_TEMPORARIA), ident))
    cur.execute(sql.SQL("CREATE POLICY {} ON {} FOR ALL TO anon USING (true) WITH CHECK (true)").format(
        sql.Identifier(POLITICA_TEMPORARIA), ident))
    cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE ON {} TO anon").format(ident))


def fechar_permissao_postgrest(cur) -> None:
    ident = sql.Identifier("public", TABELA_BENCH)
    cur.execute(sql.SQL("DROP POLICY IF EXISTS {} ON {}").format(sql.Identifier(POLITICA_TEMPORARIA), ident))
    cur.execute(sql.SQL("REVOKE ALL ON {} FROM anon, authenticated").format(ident))


def preparar_destino_remoto(remoto) -> None:
    """Cria o destino dedicado na nuvem (mesma estrutura da fato) sem exposição pública."""
    with remoto.cursor() as cur:
        cur.execute(_m12._m14.SQL_FATO_BENCH)
        cur.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(sql.Identifier("public", TABELA_BENCH)))
        cur.execute(sql.SQL("REVOKE ALL ON {} FROM anon, authenticated").format(sql.Identifier("public", TABELA_BENCH)))
    remoto.commit()


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def registrar(local, carga_id, estrategia, repeticao, linhas, tempo, rtt, payload, md5_ok, host_destino, rede):
    with local.cursor() as cur:
        cur.execute(sql.SQL("""INSERT INTO {} (carga_id, estrategia, repeticao, linhas_destino, tempo_seg,
                      throughput_lps, rtt_ms, bytes_payload, md5_confere, host_origem, host_destino, rede, observacoes)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""").format(sql.Identifier(TABELA_CARGA)),
                    (str(carga_id), estrategia, repeticao, linhas, round(tempo, 4), round(linhas / tempo, 2),
                     round(rtt, 3), payload, md5_ok, socket.gethostname(), host_destino, rede,
                     "carga em tabela vazia; destino dedicado; TRUNCATE por DSN fora do tempo medido"))
    local.commit()


def credenciais_postgrest() -> tuple[str, str] | None:
    try:
        from enade_time import enade_time_dados as dados

        return dados.credenciais()
    except Exception:  # noqa: BLE001 — qualquer problema de credencial = estratégia não medida
        return None


def resumo(local, carga_id) -> None:
    with local.cursor() as cur:
        cur.execute("""SELECT estrategia, n, tempo_mediana, tempo_min, tempo_max, tempo_iqr,
                              throughput_mediana, rtt_mediana_ms, md5_confere
                       FROM v_enade_time_benchmark_carga_resumo WHERE carga_id = %s ORDER BY tempo_mediana""",
                    (str(carga_id),))
        linhas = cur.fetchall()
    print("\nCusto de publicação (carga em tabela vazia; mediana, mín–máx e IQR entre repetições):")
    print(f"  {'estratégia':<32}{'n':>3} {'mediana(s)':>11} {'mín–máx(s)':>16} {'IQR(s)':>8} {'linhas/s':>10} {'RTT(ms)':>9}  md5")
    for est, n, med, mn, mx, iqr, thr, rtt, md5 in linhas:
        print(f"  {est:<32}{n:>3} {med:>11} {f'{mn}–{mx}':>16} {iqr:>8} {thr:>10} {rtt:>9}  {'ok' if md5 else 'DIVERGE'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=10, help="Repetições por estratégia (padrão 10).")
    ap.add_argument("--estrategias", default=",".join(ESTRATEGIAS),
                    help="Subconjunto, separado por vírgula (padrão: as 3 principais e os 4 controles).")
    ap.add_argument("--rede", choices=["cabo", "wifi", "wifi+cabo", "desconhecida"], default=None,
                    help="Tipo de rede durante a medição (padrão: detecta).")
    ap.add_argument("--preparar", action="store_true", help="Só cria o destino dedicado na nuvem.")
    ap.add_argument("--dry-run", action="store_true", help="Mostra o que seria medido, sem carregar nada.")
    ap.add_argument("--limpar-permissoes", action="store_true", help="Fecha a permissão temporária do anon.")
    args = ap.parse_args()
    escolhidas = [e.strip() for e in args.estrategias.split(",") if e.strip()]
    invalidas = [e for e in escolhidas if e not in ESTRATEGIAS]
    if invalidas:
        raise SystemExit(f"estratégias desconhecidas: {invalidas}; válidas: {list(ESTRATEGIAS)}")

    precisa_nuvem = args.preparar or args.limpar_permissoes or any(
        e not in ("copy_local", "controle_local_sem_estrutura", "controle_local_so_indices", "controle_local_so_fks")
        for e in escolhidas)
    local = _m12.conectar_local()
    remoto = _m12.conectar_remoto() if precisa_nuvem else None
    try:
        if args.preparar:
            preparar_destino_remoto(remoto)
            print("Destino dedicado criado na nuvem (sem exposição pública).")
            return 0
        if args.limpar_permissoes:
            with remoto.cursor() as cur:
                fechar_permissao_postgrest(cur)
            remoto.commit()
            print("Permissão temporária do anon fechada.")
            return 0

        http = credenciais_postgrest() if "upsert_postgrest" in escolhidas else None
        medir = [e for e in escolhidas if e != "upsert_postgrest" or http]
        if "upsert_postgrest" in escolhidas and not http:
            print("AVISO: upsert_postgrest NÃO será medida (defina SUPABASE_URL e SUPABASE_KEY públicas).")
        rede = args.rede or detectar_rede()
        texto, df_up = preparar_dados()
        with local.cursor() as cur:
            n_fato, md5_fato = md5_tabela(cur, "tbl_enade_time_fato")
        print(f"Fato local: {n_fato} linhas · md5 {md5_fato[:10]} · payload COPY {len(texto.encode('utf-8')):,} bytes · rede: {rede}")
        if n_fato != LINHAS or len(df_up) != LINHAS:
            raise SystemExit(f"base inesperada: fato {n_fato}, CSV {len(df_up)}, esperado {LINHAS}")
        if args.dry_run:
            print(f"DRY-RUN: mediria {medir} × {args.reps} repetições, intercaladas, sem carregar nada.")
            return 0

        carga_id = uuid.uuid4()
        permissao_aberta = False
        if "upsert_postgrest" in medir:
            with remoto.cursor() as cur:
                abrir_permissao_postgrest(cur)
            remoto.commit()
            permissao_aberta = True
        print(f"\ncarga_id {carga_id}\n")
        try:
            for rep in range(1, args.reps + 1):
                for estrategia in medir:
                    verificacao = None
                    if estrategia == "copy_local":
                        dt, rtt, payload, host = carregar_copy_local(local, texto)
                        destino = local
                    elif estrategia == "copy_pooler":
                        dt, rtt, payload, host = carregar_copy_pooler(remoto, texto)
                        destino = remoto
                    elif estrategia == "upsert_postgrest":
                        dt, rtt, payload, host = carregar_upsert_postgrest(remoto, df_up, *http)
                        destino = remoto
                    else:  # controles
                        canal = remoto if estrategia.startswith("controle_pooler") else local
                        dt, rtt, payload, host, verificacao = carregar_controle(estrategia, canal, texto)
                    if verificacao is None:
                        with destino.cursor() as cur:
                            n, h = md5_tabela(cur, TABELA_BENCH)
                        destino.rollback()
                    else:
                        n, h = verificacao
                    ok = n == LINHAS and h == md5_fato
                    registrar(local, carga_id, estrategia, rep, n, dt, rtt, payload, ok, host, rede)
                    print(f"  rep {rep:>2} {estrategia:<30} {dt:7.3f} s · RTT {rtt:6.1f} ms · {n} linhas · md5 {'ok' if ok else 'DIVERGE'}")
                    if not ok:
                        raise RuntimeError(f"{estrategia} rep {rep}: destino com {n} linhas / md5 diferente da fato")
        finally:
            if permissao_aberta:
                with remoto.cursor() as cur:
                    fechar_permissao_postgrest(cur)
                remoto.commit()
                print("\nPermissão temporária do anon fechada.")
        resumo(local, carga_id)
    finally:
        local.close()
        if remoto is not None:
            remoto.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
