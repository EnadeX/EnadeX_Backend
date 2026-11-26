from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

# Os campos `media_geral`, `media_min`, `media_max` e `desvio_padrao` dos resumos são LEGADOS:
# saem das linhas de inscrição (a média do curso é repetida uma vez por aluno, então os cursos
# com mais inscrições pesam mais) e só existem para a NT_FG. A unidade de análise do trabalho é
# o curso-ano: as medidas por curso-ano estão em `GET /analises/descritiva` (três notas, por
# edição) e nos campos `desvio_padrao_*_curso_ano` dos resumos por região e UF. Os campos
# legados continuam na resposta por compatibilidade.
_LEGADO = (
    "LEGADO: calculado sobre as linhas de inscrição (a média de cada curso repetida uma vez por "
    "aluno), só para a NT_FG. Para a estatística por curso-ano, use GET /analises/descritiva."
)
_LEGADO_MIN_MAX = (
    "LEGADO: só para a NT_FG. Como a média do curso se repete em todas as suas linhas, coincide com o "
    "mínimo/máximo por curso-ano; para as três notas, use GET /analises/descritiva."
)
_DP_CURSO_ANO = "Desvio-padrão amostral (n-1) entre as médias de curso do grupo; unidade: curso-ano."


def _legado(descricao: str = _LEGADO) -> dict:
    return {"description": descricao, "json_schema_extra": {"deprecated": True}}


class EstatisticaNota(BaseModel):
    """Medidas descritivas de uma nota sobre as médias de curso (uma observação por curso-ano)."""

    model_config = ConfigDict(from_attributes=True)

    n: int = Field(description="Curso-ano com a nota válida (não nula) no recorte.")
    media: float | None = Field(None, description="Média simples das médias de curso (sem ponderar por inscrições).")
    desvio_padrao: float | None = Field(None, description="Desvio-padrão amostral (n-1); nulo com n < 2.")
    variancia: float | None = Field(None, description="Variância amostral (n-1); nula com n < 2.")
    coef_variacao: float | None = Field(None, description="Coeficiente de variação em %: 100 * desvio_padrao / media.")
    minimo: float | None = None
    q1: float | None = Field(None, description="Primeiro quartil (percentil 25, interpolação linear).")
    mediana: float | None = Field(None, description="Mediana (percentil 50, interpolação linear).")
    q3: float | None = Field(None, description="Terceiro quartil (percentil 75, interpolação linear).")
    maximo: float | None = None


class DescritivaAnual(BaseModel):
    """Estatística descritiva de uma edição do ENADE, com o curso-ano como unidade de análise."""

    model_config = ConfigDict(from_attributes=True)

    nu_ano: int
    cursos: int = Field(description="Pares curso-ano (nu_ano, co_curso) no recorte, tenham ou não nota.")
    nt_ger: EstatisticaNota
    nt_fg: EstatisticaNota
    nt_ce: EstatisticaNota


class ResumoAnual(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nu_ano: int
    total_registros: int
    total_cursos: int  # cursos distintos: a unidade analítica é o curso-ano (D16)
    media_geral: float | None = Field(None, **_legado())
    media_min: float | None = Field(None, **_legado(_LEGADO_MIN_MAX))
    media_max: float | None = Field(None, **_legado(_LEGADO_MIN_MAX))
    desvio_padrao: float | None = Field(None, **_legado())
    media_geral_ger: float | None = None
    media_geral_ce: float | None = None


class ResumoRegiao(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_regiao: int
    nome: str
    total_registros: int
    total_cursos: int  # cursos distintos: a unidade analítica é o curso-ano (D16)
    media_geral: float | None = Field(None, **_legado())
    media_min: float | None = Field(None, **_legado(_LEGADO_MIN_MAX))
    media_max: float | None = Field(None, **_legado(_LEGADO_MIN_MAX))
    desvio_padrao: float | None = Field(None, **_legado())
    media_geral_ger: float | None = None
    media_geral_ce: float | None = None
    desvio_padrao_ger_curso_ano: float | None = Field(None, description=_DP_CURSO_ANO)
    desvio_padrao_fg_curso_ano: float | None = Field(None, description=_DP_CURSO_ANO)
    desvio_padrao_ce_curso_ano: float | None = Field(None, description=_DP_CURSO_ANO)


class ResumoUF(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_uf: int
    sigla: str
    nome: str
    co_regiao: int
    total_registros: int
    total_cursos: int  # cursos distintos: a unidade analítica é o curso-ano (D16)
    media_geral: float | None = Field(None, **_legado())
    media_min: float | None = Field(None, **_legado(_LEGADO_MIN_MAX))
    media_max: float | None = Field(None, **_legado(_LEGADO_MIN_MAX))
    desvio_padrao: float | None = Field(None, **_legado())
    media_geral_ger: float | None = None
    media_geral_ce: float | None = None
    desvio_padrao_ger_curso_ano: float | None = Field(None, description=_DP_CURSO_ANO)
    desvio_padrao_fg_curso_ano: float | None = Field(None, description=_DP_CURSO_ANO)
    desvio_padrao_ce_curso_ano: float | None = Field(None, description=_DP_CURSO_ANO)


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
