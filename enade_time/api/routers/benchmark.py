from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extensions import cursor as PgCursor

from enade_time.api.dependencies import get_db_cursor
from enade_time.api.repositories import benchmark_repo
from enade_time.api.schemas.benchmark import (
    BenchmarkComparativo,
    BenchmarkEtapa,
    BenchmarkExecucao,
    BenchmarkMetrica,
    CargaResposta,
    Campanha,
)
from enade_time.api.settings import Settings, get_settings

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


def _uuid_str(valor: UUID | None) -> str | None:
    return str(valor) if valor is not None else None


@router.get("/execucoes", response_model=list[BenchmarkExecucao])
def execucoes(
    apenas_validas: bool = Query(True),
    campanha_id: UUID | None = Query(None, description="Restringe a uma campanha"),
    cursor: PgCursor = Depends(get_db_cursor),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    return benchmark_repo.listar_execucoes(
        cursor,
        apenas_validas=apenas_validas,
        ids_excluir=settings.benchmark_ids_excluir,
        campanha_id=_uuid_str(campanha_id),
    )


@router.get("/execucoes/{execucao_id}", response_model=BenchmarkExecucao)
def execucao_por_id(
    execucao_id: int,
    apenas_validas: bool = Query(True),
    cursor: PgCursor = Depends(get_db_cursor),
    settings: Settings = Depends(get_settings),
) -> dict:
    row = benchmark_repo.get_execucao(
        cursor,
        execucao_id=execucao_id,
        apenas_validas=apenas_validas,
        ids_excluir=settings.benchmark_ids_excluir,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    return row


@router.get("/etapas/{execucao_id}", response_model=list[BenchmarkEtapa])
def etapas(
    execucao_id: int,
    apenas_validas: bool = Query(True),
    cursor: PgCursor = Depends(get_db_cursor),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    rows = benchmark_repo.listar_etapas(
        cursor,
        execucao_id=execucao_id,
        apenas_validas=apenas_validas,
        ids_excluir=settings.benchmark_ids_excluir,
    )
    if rows is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    return rows


@router.get("/metricas", response_model=list[BenchmarkMetrica])
def metricas(
    apenas_validas: bool = Query(True),
    campanha_id: UUID | None = Query(None, description="Restringe a uma campanha"),
    cursor: PgCursor = Depends(get_db_cursor),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    return benchmark_repo.listar_metricas(
        cursor,
        apenas_validas=apenas_validas,
        ids_excluir=settings.benchmark_ids_excluir,
        campanha_id=_uuid_str(campanha_id),
    )


@router.get("/campanhas", response_model=list[Campanha])
def campanhas(cursor: PgCursor = Depends(get_db_cursor)) -> list[dict]:
    """Campanhas de benchmark (grupos de suítes), da mais recente para a mais antiga."""
    return benchmark_repo.listar_campanhas(cursor)


@router.get("/comparativo", response_model=BenchmarkComparativo)
def comparativo(
    apenas_validas: bool = Query(True),
    campanha_id: UUID | None = Query(
        None, description="Campanha a comparar (padrão: a oficial mais recente)"),
    suite_id: UUID | None = Query(None, description="Drill-down em uma suíte"),
    cursor: PgCursor = Depends(get_db_cursor),
    settings: Settings = Depends(get_settings),
) -> dict:
    return benchmark_repo.comparativo(
        cursor,
        apenas_validas=apenas_validas,
        ids_excluir=settings.benchmark_ids_excluir,
        campanha_id=_uuid_str(campanha_id),
        suite_id=_uuid_str(suite_id),
    )


@router.get("/carga", response_model=CargaResposta)
def carga(
    carga_id: UUID | None = Query(None, description="Medição do eixo de carga (padrão: a mais recente)"),
    cursor: PgCursor = Depends(get_db_cursor),
) -> dict:
    """Custo de publicar a base (COPY local, COPY pelo pooler, upsert pelo PostgREST e controles).
    Custo de publicação com mediana e IQR — nunca speedup (DESIGN_LOG D17)."""
    return benchmark_repo.carga(cursor, _uuid_str(carga_id))
