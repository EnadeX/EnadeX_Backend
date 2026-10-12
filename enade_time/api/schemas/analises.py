from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ResumoAnual(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nu_ano: int
    total_registros: int
    total_cursos: int  # cursos distintos: a unidade analítica é o curso-ano (D16)
    media_geral: float | None = None
    media_min: float | None = None
    media_max: float | None = None
    desvio_padrao: float | None = None
    media_geral_ger: float | None = None
    media_geral_ce: float | None = None


class ResumoRegiao(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_regiao: int
    nome: str
    total_registros: int
    total_cursos: int  # cursos distintos: a unidade analítica é o curso-ano (D16)
    media_geral: float | None = None
    media_min: float | None = None
    media_max: float | None = None
    desvio_padrao: float | None = None
    media_geral_ger: float | None = None
    media_geral_ce: float | None = None


class ResumoUF(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_uf: int
    sigla: str
    nome: str
    co_regiao: int
    total_registros: int
    total_cursos: int  # cursos distintos: a unidade analítica é o curso-ano (D16)
    media_geral: float | None = None
    media_min: float | None = None
    media_max: float | None = None
    desvio_padrao: float | None = None
    media_geral_ger: float | None = None
    media_geral_ce: float | None = None


class ResumoIES(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_ies: int
    co_categad: int
    co_orgacad: int
    co_uf_curso: int
    total_registros: int
    total_cursos: int  # cursos distintos: a unidade analítica é o curso-ano (D16)
    media_geral: float | None = None
    media_geral_ger: float | None = None
    media_geral_ce: float | None = None


class Registro(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nu_ano: int
    co_curso: int
    co_ies: int
    co_categad: int
    co_orgacad: int
    co_grupo: int
    co_modalidade: int | None = None
    co_munic_curso: int | None = None
    co_uf_curso: int
    co_regiao_curso: int
    media_nt_fg: float | None = None
    media_nt_ger: float | None = None
    media_nt_ce: float | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    page: int
    page_size: int
    total: int
    total_pages: int
    items: list[T]
