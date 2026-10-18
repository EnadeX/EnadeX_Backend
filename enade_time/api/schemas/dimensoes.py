from pydantic import BaseModel, ConfigDict


class Regiao(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_regiao: int
    nome: str


class UF(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_uf: int
    sigla: str
    nome: str
    co_regiao: int


class Ano(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_ano: int
    edicao: str | None = None


class Grupo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_grupo: int
    nome: str


class Modalidade(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_modalidade: int
    nome: str


class CategoriaAdm(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_categad: int
    nome: str


class OrganizacaoAcademica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    co_orgacad: int
    nome: str
