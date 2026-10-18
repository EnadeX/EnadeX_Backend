from fastapi import APIRouter, Depends, Query
from psycopg2.extensions import cursor as PgCursor

from enade_time.api.dependencies import get_db_cursor
from enade_time.api.repositories import dimensoes_repo
from enade_time.api.schemas.dimensoes import (
    Ano,
    CategoriaAdm,
    Grupo,
    Modalidade,
    OrganizacaoAcademica,
    Regiao,
    UF,
)

router = APIRouter(prefix="/dim", tags=["dimensoes"])


@router.get("/regioes", response_model=list[Regiao])
def regioes(cursor: PgCursor = Depends(get_db_cursor)) -> list[dict]:
    return dimensoes_repo.listar_regioes(cursor)


@router.get("/ufs", response_model=list[UF])
def ufs(
    co_regiao: int | None = Query(None, description="Filtrar UFs por região"),
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    return dimensoes_repo.listar_ufs(cursor, co_regiao)


@router.get("/anos", response_model=list[Ano])
def anos(cursor: PgCursor = Depends(get_db_cursor)) -> list[dict]:
    return dimensoes_repo.listar_anos(cursor)


@router.get("/grupos", response_model=list[Grupo])
def grupos(cursor: PgCursor = Depends(get_db_cursor)) -> list[dict]:
    return dimensoes_repo.listar_grupos(cursor)


@router.get("/modalidades", response_model=list[Modalidade])
def modalidades(cursor: PgCursor = Depends(get_db_cursor)) -> list[dict]:
    return dimensoes_repo.listar_modalidades(cursor)


@router.get("/categorias-adm", response_model=list[CategoriaAdm])
def categorias_adm(cursor: PgCursor = Depends(get_db_cursor)) -> list[dict]:
    return dimensoes_repo.listar_categorias_adm(cursor)


@router.get("/organizacoes-academicas", response_model=list[OrganizacaoAcademica])
def organizacoes_academicas(
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    return dimensoes_repo.listar_organizacoes_academicas(cursor)
