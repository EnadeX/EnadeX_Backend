"""
Carrega o consolidado validado para a tabela tbl_enade_time_fato no PostgreSQL.

Entrada (NÃO modificada):
  dados_processados/microdados_enade_2005_2021_filtrado_consolidado.csv

Método: COPY FROM STDIN (CSV) — caminho mais rápido do psycopg2 para carga
em lote. Limpa BOM do utf-8-sig e converte NaN em vazio para o COPY tratar
como NULL.

Idempotência: por padrão faz TRUNCATE em tbl_enade_time_fato antes da carga, então
rodar várias vezes produz o mesmo resultado (24.967 linhas). Use --append
para concatenar (não recomendado).

Uso:
  python scripts/06_carregar_dados_postgres.py
  python scripts/06_carregar_dados_postgres.py --append
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2


RAIZ = Path(__file__).resolve().parent.parent
ARQ_CONS = RAIZ / "dados_processados" / "microdados_enade_2005_2021_filtrado_consolidado.csv"

LINHAS_ESPERADAS = 24_967

DB_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname":   os.environ.get("POSTGRES_DB", "enade_db"),
    "user":     os.environ.get("POSTGRES_USER", "enade_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "enade_password"),
}

# Ordem das colunas no COPY (sem o id, que é BIGSERIAL e auto-gerado)
COLUNAS_DESTINO = [
    "nu_ano", "co_curso", "co_ies", "co_categad", "co_orgacad",
    "co_grupo", "co_modalidade", "co_munic_curso", "co_uf_curso",
    "co_regiao_curso", "media_nt_fg", "media_nt_ger", "media_nt_ce",
]

# Mapeamento CSV (upper) -> destino (lower). Schema do banco usa snake_case
# lowercase; o CSV usa UPPER. As ordens batem 1-pra-1.
COLUNAS_ORIGEM = [c.upper() for c in COLUNAS_DESTINO]

# Colunas que o schema declara como INTEGER/SMALLINT (não podem ter ".0").
# CO_MODALIDADE e CO_MUNIC_CURSO chegam como float64 no pandas porque têm
# nulos — precisam ser convertidas para Int64 (nullable integer) antes do
# COPY para não saírem como "1.000000" / "2806701.000000".
COLUNAS_INTEIRAS_ORIGEM = [
    "NU_ANO", "CO_CURSO", "CO_IES", "CO_CATEGAD", "CO_ORGACAD",
    "CO_GRUPO", "CO_MODALIDADE", "CO_MUNIC_CURSO", "CO_UF_CURSO",
    "CO_REGIAO_CURSO",
]

# Colunas de nota (float, escala 0-100, NUMERIC(7,4) no schema).
COLUNAS_NOTAS_ORIGEM = ["MEDIA_NT_FG", "MEDIA_NT_GER", "MEDIA_NT_CE"]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--append", action="store_true",
        help="Não trunca tbl_enade_time_fato antes de inserir (default: trunca)."
    )
    return ap.parse_args()


def preparar_buffer(df: pd.DataFrame) -> io.StringIO:
    """
    Converte o DataFrame em buffer CSV pronto pro COPY:
      - apenas as colunas de destino, na ordem do schema
      - colunas inteiras forçadas para Int64 (nullable integer):
        garante que nulos virem '' e valores nunca tenham '.0'/'.000000'
      - media_nt_fg fica como float com 4 casas (alinhado a NUMERIC(7,4))
      - sem header, sem aspas; delimitador ';' (não conflita com os dados)
    """
    out = df[COLUNAS_ORIGEM].copy()

    # ---- correção do bug "2806701.000000" ----
    # to_numeric tolera valores já int/float; astype('Int64') aceita NaN
    # e produz <NA> que to_csv com na_rep='' transforma em string vazia.
    for col in COLUNAS_INTEIRAS_ORIGEM:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    # notas permanecem float; o float_format abaixo só afeta floats,
    # e Int64 escreve como inteiro puro, ignorando float_format.
    for col in COLUNAS_NOTAS_ORIGEM:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    buf = io.StringIO()
    out.to_csv(
        buf,
        sep=";",
        header=False,
        index=False,
        na_rep="",        # <NA>/NaN -> '' (NULL no COPY CSV com NULL '')
        float_format="%.4f",
    )
    buf.seek(0)
    return buf


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
        print(f"AVISO: esperava {LINHAS_ESPERADAS} linhas, encontrei "
              f"{len(df)}. Vou prosseguir, mas confira o consolidado.")

    faltando = [c for c in COLUNAS_ORIGEM if c not in df.columns]
    if faltando:
        print(f"ERRO: colunas ausentes no CSV: {faltando}", file=sys.stderr)
        return 1

    print(f"\nConectando em postgresql://{DB_CONFIG['user']}@"
          f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        print(f"\nERRO ao conectar: {e}", file=sys.stderr)
        print("Sobe o container com:  docker compose up -d postgres",
              file=sys.stderr)
        return 1

    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tbl_enade_time_fato;")
            antes = cur.fetchone()[0]
            print(f"\nfato_enade atual: {antes} linhas")

            if not args.append and antes > 0:
                print(f"Truncando tbl_enade_time_fato (use --append para preservar).")
                cur.execute("TRUNCATE TABLE tbl_enade_time_fato RESTART IDENTITY;")

            print("\nPreparando buffer CSV...")
            buf = preparar_buffer(df)

            print("Executando COPY FROM STDIN...")
            t1 = time.perf_counter()
            copy_sql = (
                f"COPY tbl_enade_time_fato ({', '.join(COLUNAS_DESTINO)}) "
                f"FROM STDIN WITH (FORMAT csv, DELIMITER ';', NULL '')"
            )
            cur.copy_expert(copy_sql, buf)
            dt_copy = time.perf_counter() - t1
            inseridas = cur.rowcount

            cur.execute("SELECT COUNT(*) FROM tbl_enade_time_fato;")
            depois = cur.fetchone()[0]

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\nCOPY concluído em {dt_copy:.2f}s")
    print(f"  inseridas: {inseridas}")
    print(f"  tbl_enade_time_fato total: {depois} linhas "
          f"({'+' if depois > antes else ''}{depois - antes})")

    if depois == LINHAS_ESPERADAS:
        print(f"\nOK — contagem bate com o esperado ({LINHAS_ESPERADAS}).")
    else:
        print(f"\nATENÇÃO — esperado {LINHAS_ESPERADAS}, obtido {depois}.")

    throughput = inseridas / dt_copy if dt_copy > 0 else float("inf")
    print(f"Throughput: {throughput:,.0f} linhas/s")
    print("\nPróximo passo:")
    print("  python scripts/07_validar_banco.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
