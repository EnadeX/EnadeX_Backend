"""
Carrega o consolidado validado (CSV) para tbl_enade_time_fato no Supabase.

LEGADO: para publicar o ENADE-Time use o `12_publicar_supabase.py`, que copia do banco
local (dimensões, fato e benchmark), preserva os ids, confere md5 linha a linha e é
atômico. Este script segue válido como a estratégia "COPY via Session Pooler a partir do
CSV" e como referência da conexão. Ele não preserva os ids do fato (a identity gera novos).

Desde o D12 a tabela tem o mesmo nome nos dois bancos (tbl_enade_time_fato); o nome antigo
no Supabase (enade_time_distribuido) foi renomeado pelo script 12. Override: SUPABASE_TABELA.

Entrada (NÃO modificada):
  dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv

É o mesmo dataset e o mesmo método do script 06 (COPY FROM STDIN), só que
apontando para o Postgres gerenciado do Supabase em vez do container local.
A preparação do buffer é IMPORTADA do script 06 — nada é duplicado, então as
duas cargas produzem exatamente os mesmos bytes.

Credenciais (nunca hardcoded — leia do ambiente ou do .env):
  SUPABASE_DB_URL       connection string completa (tem precedência), ou
  SUPABASE_DB_HOST      default: aws-0-us-east-2.pooler.supabase.com
  SUPABASE_DB_PORT      default: 5432   (Session Pooler)
  SUPABASE_DB_NAME      default: postgres
  SUPABASE_DB_USER      default: postgres.<SUPABASE_PROJECT_REF>
  SUPABASE_DB_PASSWORD  obrigatória
  SUPABASE_PROJECT_REF  default: yghryywuxfwzvfjknpgk

A senha está no dashboard: Project Settings → Database → Database password.

Por que a Session Pooler e não o host direto (db.<ref>.supabase.co): o host
direto só atende em IPv6, o que costuma falhar em rede doméstica/corporativa.
A pooler atende em IPv4 e suporta COPY (a Transaction Pooler, porta 6543, não
suporta — não troque a porta sem testar).

Idempotência: por padrão faz TRUNCATE na tabela antes da carga, então
rodar várias vezes produz o mesmo resultado (24.967 linhas). Use --append
para concatenar (não recomendado).

Uso:
  python scripts/11_carregar_supabase.py
  python scripts/11_carregar_supabase.py --dry-run   # valida sem gravar
  python scripts/11_carregar_supabase.py --append
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Carrega .env da raiz se existir, para a senha não precisar ir no terminal.
# O .env é ignorado pelo git; o .env.example documenta as chaves.
try:
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
except ImportError:
    pass  # python-dotenv é opcional: sem ele, use variáveis de ambiente

# Reaproveita a preparação do buffer do script 06: é ela que converte as
# colunas inteiras para Int64 (evitando o bug do "2806701.000000") e formata
# as notas com 4 casas, alinhadas ao NUMERIC(7,4) do schema.
# Carregado por caminho porque o nome do módulo começa com dígito ("06_..."),
# o que impede um import normal. O main() do script 06 não roda: só dispara
# sob __name__ == "__main__".
_spec06 = importlib.util.spec_from_file_location(
    "carregar_dados_postgres", RAIZ / "scripts" / "06_carregar_dados_postgres.py"
)
_mod06 = importlib.util.module_from_spec(_spec06)
_spec06.loader.exec_module(_mod06)

preparar_buffer = _mod06.preparar_buffer
COLUNAS_DESTINO = _mod06.COLUNAS_DESTINO
COLUNAS_ORIGEM = _mod06.COLUNAS_ORIGEM
LINHAS_ESPERADAS = _mod06.LINHAS_ESPERADAS

ARQ_CONS = RAIZ / "dados_processados" / "microdados_enade_2005_2021_filtrado_consolidado.csv"

PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "yghryywuxfwzvfjknpgk")

# Mesmo nome nos dois bancos (D12). Antes do renome o Supabase usava enade_time_distribuido.
TABELA_DESTINO = os.environ.get("SUPABASE_TABELA", "tbl_enade_time_fato")


REGIAO = os.environ.get("SUPABASE_REGION", "us-east-2")


def candidatos_conexao(senha: str, dbname: str, port: int) -> list[tuple[str, dict]]:
    """Rotas a tentar, em ordem, quando o host não é fixado no ambiente.

    O prefixo do cluster da pooler (aws-0/aws-1/...) varia por projeto e não é
    derivável da região — chutar errado dá `FATAL (ENOTFOUND) tenant/user ...
    not found`. Por isso tentamos os clusters conhecidos e, por último, o host
    direto, que é IPv6-only e só funciona em rede com IPv6.
    """
    base = {"dbname": dbname, "password": senha, "sslmode": "require",
            "connect_timeout": 20}
    usuario_pooler = f"postgres.{PROJECT_REF}"
    rotas = []
    for cluster in ("aws-1", "aws-0"):
        host = f"{cluster}-{REGIAO}.pooler.supabase.com"
        rotas.append((
            f"postgresql://{usuario_pooler}@{host}:{port}/{dbname}",
            {**base, "host": host, "port": port, "user": usuario_pooler},
        ))
    host_direto = f"db.{PROJECT_REF}.supabase.co"
    rotas.append((
        f"postgresql://postgres@{host_direto}:5432/{dbname} (IPv6)",
        {**base, "host": host_direto, "port": 5432, "user": "postgres"},
    ))
    return rotas


def montar_conexao() -> tuple[str, list[tuple[str, dict]] | None]:
    """Retorna (descricao, [rotas]) ou (msg_erro, None). Nunca loga a senha."""
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if url:
        return ("SUPABASE_DB_URL", [("SUPABASE_DB_URL (host omitido do log)",
                                     {"dsn": url})])

    senha = os.environ.get("SUPABASE_DB_PASSWORD", "").strip()
    if not senha:
        achou_dotenv = (RAIZ / ".env").exists()
        detalhe = (
            "  O arquivo .env existe, mas a chave está vazia — preencha e salve."
            if achou_dotenv else
            "  Não há .env na raiz. Crie com:  copy .env.example .env"
        )
        return (
            "ERRO: defina SUPABASE_DB_PASSWORD (ou SUPABASE_DB_URL).\n"
            f"{detalhe}\n"
            "  A senha esta em: Supabase > Project Settings > Database.\n"
            "  Alternativa (PowerShell):  $env:SUPABASE_DB_PASSWORD='...'",
            None,
        )

    dbname = os.environ.get("SUPABASE_DB_NAME", "postgres")
    port = int(os.environ.get("SUPABASE_DB_PORT", "5432"))

    host_fixo = os.environ.get("SUPABASE_DB_HOST", "").strip()
    if host_fixo:
        user = os.environ.get("SUPABASE_DB_USER", f"postgres.{PROJECT_REF}")
        return ("host fixado no ambiente", [(
            f"postgresql://{user}@{host_fixo}:{port}/{dbname}",
            {"host": host_fixo, "port": port, "dbname": dbname, "user": user,
             "password": senha, "sslmode": "require", "connect_timeout": 20},
        )])

    return ("autodetecção", candidatos_conexao(senha, dbname, port))


def conectar(rotas: list[tuple[str, dict]]):
    """Tenta as rotas em ordem; devolve a primeira que autenticar."""
    erros = []
    for descricao, kwargs in rotas:
        try:
            conn = psycopg2.connect(**kwargs)
            print(f"  conectado: {descricao}")
            return conn
        except psycopg2.OperationalError as e:
            erros.append(f"  - {descricao.split('@')[-1]}: "
                         f"{str(e).strip().splitlines()[0][:110]}")
    raise psycopg2.OperationalError(
        "nenhuma rota de conexão funcionou:\n" + "\n".join(erros)
    )


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--append", action="store_true",
        help="Não trunca a tabela antes de inserir (default: trunca)."
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Lê e prepara o buffer, mas não conecta nem grava."
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    if not ARQ_CONS.exists():
        print(f"ERRO: arquivo não encontrado: {ARQ_CONS}", file=sys.stderr)
        return 1

    print(f"Lendo: {ARQ_CONS.relative_to(RAIZ).as_posix()}")
    t0 = time.perf_counter()
    df = pd.read_csv(ARQ_CONS, sep=";", encoding="utf-8-sig")
    print(f"  {len(df)} linhas, {len(df.columns)} colunas em "
          f"{time.perf_counter()-t0:.2f}s")

    if len(df) != LINHAS_ESPERADAS:
        print(f"AVISO: esperava {LINHAS_ESPERADAS} linhas, encontrei {len(df)}. "
              f"Vou prosseguir, mas confira o consolidado.")

    faltando = [c for c in COLUNAS_ORIGEM if c not in df.columns]
    if faltando:
        print(f"ERRO: colunas ausentes no CSV: {faltando}", file=sys.stderr)
        return 1

    print("\nPreparando buffer CSV (mesma função do script 06)...")
    buf = preparar_buffer(df)

    if args.dry_run:
        amostra = buf.getvalue()[:200].replace("\r\n", " | ")
        buf.seek(0)
        print(f"  primeiras linhas: {amostra}")
        print("\n[--dry-run] Nada foi enviado ao Supabase.")
        return 0

    descricao, rotas = montar_conexao()
    if rotas is None:
        print(f"\n{descricao}", file=sys.stderr)
        return 1

    print(f"\nConectando ({descricao})...")
    try:
        conn = conectar(rotas)
    except psycopg2.OperationalError as e:
        print(f"\nERRO ao conectar: {e}", file=sys.stderr)
        print("\nChecklist:", file=sys.stderr)
        print("  - senha correta (Project Settings > Database)", file=sys.stderr)
        print("  - projeto ativo (o plano free pausa após 7 dias ociosos)",
              file=sys.stderr)
        print("  - 'tenant/user not found' = cluster da pooler errado; fixe o "
              "host certo em SUPABASE_DB_HOST (veja o botão Connect no "
              "dashboard)", file=sys.stderr)
        print("  - use a Session Pooler (porta 5432); a Transaction Pooler "
              "(6543) não suporta COPY", file=sys.stderr)
        return 1

    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {TABELA_DESTINO};")
            antes = cur.fetchone()[0]
            print(f"\n{TABELA_DESTINO} atual: {antes} linhas")

            if not args.append and antes > 0:
                print(f"Truncando {TABELA_DESTINO} (use --append para preservar).")
                cur.execute(f"TRUNCATE TABLE {TABELA_DESTINO} RESTART IDENTITY;")

            print("Executando COPY FROM STDIN...")
            t1 = time.perf_counter()
            copy_sql = (
                f"COPY {TABELA_DESTINO} ({', '.join(COLUNAS_DESTINO)}) "
                f"FROM STDIN WITH (FORMAT csv, DELIMITER ';', NULL '')"
            )
            cur.copy_expert(copy_sql, buf)
            dt_copy = time.perf_counter() - t1
            inseridas = cur.rowcount

            cur.execute(f"SELECT COUNT(*) FROM {TABELA_DESTINO};")
            depois = cur.fetchone()[0]

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\nCOPY concluído em {dt_copy:.2f}s")
    print(f"  inseridas: {inseridas}")
    print(f"  {TABELA_DESTINO} total: {depois} linhas "
          f"({'+' if depois > antes else ''}{depois - antes})")

    if depois == LINHAS_ESPERADAS:
        print(f"\nOK — contagem bate com o esperado ({LINHAS_ESPERADAS}).")
    else:
        print(f"\nATENÇÃO — esperado {LINHAS_ESPERADAS}, obtido {depois}.")

    throughput = inseridas / dt_copy if dt_copy > 0 else float("inf")
    print(f"Throughput: {throughput:,.0f} linhas/s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
