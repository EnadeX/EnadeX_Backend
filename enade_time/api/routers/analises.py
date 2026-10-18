import math

from fastapi import APIRouter, Depends, Query
from psycopg2.extensions import cursor as PgCursor

from enade_time.api.dependencies import (
    FiltrosAnalise,
    PaginationParams,
    filtros_analise,
    get_db_cursor,
    pagination_params,
)
from enade_time.api.repositories import analises_repo
from enade_time.api.schemas.analises import (
    PaginatedResponse,
    Registro,
    ResumoAnual,
    ResumoIES,
    ResumoRegiao,
    ResumoUF,
)

router = APIRouter(prefix="/analises", tags=["analises"])


@router.get("/resumo-anual", response_model=list[ResumoAnual])
def resumo_anual(
    filtros: FiltrosAnalise = Depends(filtros_analise),
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    return analises_repo.resumo_anual(cursor, filtros)


@router.get("/resumo-regiao", response_model=list[ResumoRegiao])
def resumo_regiao(
    filtros: FiltrosAnalise = Depends(filtros_analise),
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    return analises_repo.resumo_regiao(cursor, filtros)


@router.get("/resumo-uf", response_model=list[ResumoUF])
def resumo_uf(
    filtros: FiltrosAnalise = Depends(filtros_analise),
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    return analises_repo.resumo_uf(cursor, filtros)


@router.get("/resumo-ies", response_model=list[ResumoIES])
def resumo_ies(
    limit: int = Query(20, ge=1, le=1000),
    min_cursos: int = Query(1, ge=1),
    filtros: FiltrosAnalise = Depends(filtros_analise),
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    return analises_repo.resumo_ies(cursor, filtros, limit=limit, min_cursos=min_cursos)


@router.get("/registros", response_model=PaginatedResponse[Registro])
def registros(
    filtros: FiltrosAnalise = Depends(filtros_analise),
    pag: PaginationParams = Depends(pagination_params),
    cursor: PgCursor = Depends(get_db_cursor),
) -> dict:
    total = analises_repo.contar_registros(cursor, filtros)
    items = analises_repo.listar_registros(cursor, filtros, pag.limit, pag.offset)
    total_pages = math.ceil(total / pag.page_size) if pag.page_size else 0
    return {
        "page": pag.page,
        "page_size": pag.page_size,
        "total": total,
        "total_pages": total_pages,
        "items": items,
    }
