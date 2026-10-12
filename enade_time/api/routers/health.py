import psycopg2
from fastapi import APIRouter, HTTPException
from psycopg2.pool import PoolError

from enade_time.api.database import get_pool, registrar_falha
from enade_time.api.dependencies import devolver_conexao

router = APIRouter(tags=["health"])

VERSAO = "0.2.0"


@router.get("/health")
def health() -> dict:
    """Status da API e do banco. Não usa `get_db_cursor` de propósito: a checagem
    do banco é o próprio objetivo, então uma falha vira 503 estruturado e o erro
    original (que inclui host e usuário do banco) nunca vai para a resposta."""
    conn = None
    pool = None
    try:
        pool = get_pool()
        conn = pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
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
    return {"status": "ok", "database": "ok", "version": VERSAO}
