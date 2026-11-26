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
    DescritivaAnual,
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


@router.get(
    "/descritiva",
    response_model=list[DescritivaAnual],
    summary="Estatística descritiva por edição (unidade: curso-ano)",
)
def descritiva(
    filtros: FiltrosAnalise = Depends(filtros_analise),
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    """Um item por `nu_ano` com as medidas descritivas de NT_GER, NT_FG e NT_CE.

    **A unidade de análise é o curso-ano** (par `nu_ano`, `co_curso`), não a inscrição: a tabela
    fato repete a média do curso em cada linha de aluno, então primeiro ela é reduzida a uma
    observação por curso-ano e só depois agregada por edição. Em cada nota: `n` (curso-ano com
    nota válida), `media`, `desvio_padrao` e `variancia` (amostrais, n-1), `coef_variacao` (%),
    `minimo`, `q1`, `mediana`, `q3` (interpolação linear) e `maximo`. Medidas indefinidas (por
    exemplo, desvio-padrão com n < 2) voltam `null`. Aceita os mesmos filtros de `resumo-anual`.

    As edições não são diretamente comparáveis entre si (o INEP não garante comparabilidade; 2005
    e 2008 ainda misturam ingressantes): por isso a rota não agrega entre edições.
    """
    return analises_repo.descritiva(cursor, filtros)


@router.get("/resumo-regiao", response_model=list[ResumoRegiao])
def resumo_regiao(
    filtros: FiltrosAnalise = Depends(filtros_analise),
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    """Resumo por região.

    `media_geral*`, `media_min/max` e `desvio_padrao` (legados) saem das linhas de inscrição.
    Os campos `desvio_padrao_{ger,fg,ce}_curso_ano` têm o **curso-ano** como unidade: desvio-padrão
    amostral entre as médias de curso da região (sem filtro de ano, reúne edições não comparáveis).
    """
    return analises_repo.resumo_regiao(cursor, filtros)


@router.get("/resumo-uf", response_model=list[ResumoUF])
def resumo_uf(
    filtros: FiltrosAnalise = Depends(filtros_analise),
    cursor: PgCursor = Depends(get_db_cursor),
) -> list[dict]:
    """Resumo por UF. Mesma convenção de `resumo-regiao`: os campos `desvio_padrao_*_curso_ano`
    têm o **curso-ano** como unidade; `desvio_padrao`, `media_min` e `media_max` são legados."""
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
