from dataclasses import dataclass
from typing import Iterator

import psycopg2
from fastapi import HTTPException, Query
from psycopg2.extensions import cursor as PgCursor
from psycopg2.extras import RealDictCursor
from psycopg2.pool import PoolError

from enade_time.api.database import get_pool, registrar_falha

DETAIL_BANCO_INDISPONIVEL = "Banco do ENADE-Time indisponível"
DETAIL_ERRO_BANCO = "Erro de banco no ENADE-Time"

# Falhas de conexão/rede: o banco está fora ou a conexão do pool morreu.
_ERROS_DE_CONEXAO = (psycopg2.OperationalError, psycopg2.InterfaceError)


def get_db_cursor() -> Iterator[PgCursor]:
    """Entrega um cursor do pool e traduz falhas de banco em respostas HTTP.

    Falha de conexão vira 503 e demais erros do psycopg2 viram 500, sempre como
    `HTTPException`: assim passam pelo CORS e o navegador enxerga o status, em
    vez de um 500 sem cabeçalhos que parece erro de rede.
    """
    try:
        pool = get_pool()
        conn = pool.getconn()
    except _ERROS_DE_CONEXAO as exc:
        registrar_falha()
        raise HTTPException(status_code=503, detail=DETAIL_BANCO_INDISPONIVEL) from exc
    except PoolError as exc:  # pool esgotado: sobrecarga momentânea, não queda do banco
        raise HTTPException(status_code=503, detail=DETAIL_BANCO_INDISPONIVEL) from exc
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except _ERROS_DE_CONEXAO as exc:
        if conn.closed:
            registrar_falha()
        else:
            _desfazer(conn)
        raise HTTPException(status_code=503, detail=DETAIL_BANCO_INDISPONIVEL) from exc
    except psycopg2.Error as exc:
        _desfazer(conn)
        raise HTTPException(status_code=500, detail=DETAIL_ERRO_BANCO) from exc
    except Exception:
        _desfazer(conn)
        raise
    finally:
        devolver_conexao(pool, conn)


def devolver_conexao(pool, conn) -> None:
    """Devolve a conexão ao pool; conexão morta é descartada. Se o pool já foi
    fechado por `registrar_falha`, não há mais nada a devolver."""
    try:
        pool.putconn(conn, close=bool(conn.closed))
    except PoolError:
        pass


def _desfazer(conn) -> None:
    if not conn.closed:
        conn.rollback()


@dataclass
class PaginationParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination_params(
    page: int = Query(1, ge=1, description="Página (>=1)"),
    page_size: int = Query(100, ge=1, le=1000, description="Itens por página (1-1000)"),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


_FILTRO_COLUNAS = {
    "nu_ano": "nu_ano",
    "co_regiao": "co_regiao_curso",
    "co_uf": "co_uf_curso",
    "co_ies": "co_ies",
    "co_grupo": "co_grupo",
    "co_modalidade": "co_modalidade",
    "co_categad": "co_categad",
    "co_orgacad": "co_orgacad",
}


@dataclass
class FiltrosAnalise:
    nu_ano: int | None = None
    co_regiao: int | None = None
    co_uf: int | None = None
    co_ies: int | None = None
    co_grupo: int | None = None
    co_modalidade: int | None = None
    co_categad: int | None = None
    co_orgacad: int | None = None

    def to_where(self, alias: str | None = None) -> tuple[str, dict]:
        prefix = f"{alias}." if alias else ""
        fragments: list[str] = []
        params: dict = {}
        for key, col in _FILTRO_COLUNAS.items():
            value = getattr(self, key)
            if value is not None:
                fragments.append(f"AND {prefix}{col} = %({key})s")
                params[key] = value
        return (" ".join(fragments), params)


def filtros_analise(
    nu_ano: int | None = Query(None),
    co_regiao: int | None = Query(None),
    co_uf: int | None = Query(None),
    co_ies: int | None = Query(None),
    co_grupo: int | None = Query(None),
    co_modalidade: int | None = Query(None),
    co_categad: int | None = Query(None),
    co_orgacad: int | None = Query(None),
) -> FiltrosAnalise:
    return FiltrosAnalise(
        nu_ano=nu_ano,
        co_regiao=co_regiao,
        co_uf=co_uf,
        co_ies=co_ies,
        co_grupo=co_grupo,
        co_modalidade=co_modalidade,
        co_categad=co_categad,
        co_orgacad=co_orgacad,
    )
