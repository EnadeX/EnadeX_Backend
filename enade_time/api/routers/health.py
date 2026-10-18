import psycopg2
from fastapi import APIRouter, HTTPException
from psycopg2.pool import PoolError

from enade_time.api.database import get_pool, registrar_falha
from enade_time.api.dependencies import devolver_conexao
from enade_time.api.settings import fonte_dos_dados, get_settings

router = APIRouter(tags=["health"])

VERSAO = "0.2.0"


def _ultima_publicacao(cur) -> dict:
    """Quando e com que versão os dados foram publicados no Supabase. A tabela pode não existir
    (bancos antigos): nesse caso devolve None, sem derrubar o health."""
    cur.execute("SELECT to_regclass('public.tbl_enade_time_publicacao') IS NOT NULL")
    if not cur.fetchone()[0]:
        return {"ultima_publicacao": None, "versao_dataset": None}
    cur.execute(
        "SELECT publicado_em, versao_dataset FROM tbl_enade_time_publicacao ORDER BY id DESC LIMIT 1"
    )
    linha = cur.fetchone()
    if linha is None:
        return {"ultima_publicacao": None, "versao_dataset": None}
    return {"ultima_publicacao": linha[0].isoformat(), "versao_dataset": linha[1]}


@router.get("/health")
def health() -> dict:
    """Status da API e do banco. Não usa `get_db_cursor` de propósito: a checagem
    do banco é o próprio objetivo, então uma falha vira 503 estruturado e o erro
    original (que inclui host e usuário do banco) nunca vai para a resposta.

    `fonte` diz de onde a API está lendo (local ou supabase); `ultima_publicacao` e
    `versao_dataset` vêm do log de publicações (script 12)."""
    conn = None
    pool = None
    try:
        pool = get_pool()
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
            publicacao = _ultima_publicacao(cur)
        conn.rollback()
    except (psycopg2.Error, PoolError) as exc:
        if isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError)):
            registrar_falha()
        raise HTTPException(
            status_code=503,
            detail={"status": "degraded", "database": "unreachable", "version": VERSAO},
        ) from exc
    finally:
        if conn is not None:
            devolver_conexao(pool, conn)
    return {
        "status": "ok",
        "database": "ok",
        "version": VERSAO,
        "fonte": fonte_dos_dados(get_settings()),
        **publicacao,
    }
