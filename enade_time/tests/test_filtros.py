"""
`FiltrosAnalise.to_where` monta o WHERE dinâmico da API. A segurança vem da
construção: os nomes de coluna saem de um dicionário fixo (`_FILTRO_COLUNAS`)
e os valores viajam como placeholders nomeados do psycopg2 — nunca
interpolados. Estes testes fixam esse contrato.
"""

from __future__ import annotations

import re

import pytest

from enade_time.api.dependencies import FiltrosAnalise, PaginationParams, _FILTRO_COLUNAS

PLACEHOLDER = re.compile(r"%\((\w+)\)s")


def test_sem_filtros_gera_where_vazio():
    where, params = FiltrosAnalise().to_where()
    assert where == ""
    assert params == {}


def test_um_filtro_gera_fragmento_parametrizado():
    where, params = FiltrosAnalise(nu_ano=2021).to_where()
    assert where == "AND nu_ano = %(nu_ano)s"
    assert params == {"nu_ano": 2021}


def test_alias_prefixa_a_coluna_e_nao_o_placeholder():
    where, params = FiltrosAnalise(co_regiao=1).to_where(alias="f")
    assert where == "AND f.co_regiao_curso = %(co_regiao)s"
    assert params == {"co_regiao": 1}


def test_mapeamento_de_nomes_publicos_para_colunas_reais():
    # nomes expostos na API != nomes das colunas em tbl_enade_time_fato
    assert _FILTRO_COLUNAS["co_regiao"] == "co_regiao_curso"
    assert _FILTRO_COLUNAS["co_uf"] == "co_uf_curso"
    assert set(_FILTRO_COLUNAS) == {
        "nu_ano", "co_regiao", "co_uf", "co_ies", "co_grupo",
        "co_modalidade", "co_categad", "co_orgacad",
    }


def test_todos_os_filtros_combinados_com_and():
    f = FiltrosAnalise(nu_ano=2021, co_regiao=2, co_uf=23, co_ies=1, co_grupo=4004,
                       co_modalidade=1, co_categad=1, co_orgacad=10028)
    where, params = f.to_where()
    fragmentos = [x for x in where.split("AND ") if x.strip()]
    assert len(fragmentos) == 8
    assert set(params) == set(_FILTRO_COLUNAS)
    # cada placeholder corresponde exatamente a uma chave de params
    assert sorted(PLACEHOLDER.findall(where)) == sorted(params)


def test_zero_e_valor_valido_e_nao_e_descartado():
    where, params = FiltrosAnalise(co_modalidade=0).to_where()
    assert "co_modalidade" in where
    assert params == {"co_modalidade": 0}


def test_fragmento_so_contem_colunas_da_lista_branca():
    f = FiltrosAnalise(nu_ano=2021, co_uf=23)
    where, _ = f.to_where(alias="x")
    colunas_no_sql = re.findall(r"AND x\.(\w+) = %\(", where)
    assert colunas_no_sql
    assert set(colunas_no_sql) <= set(_FILTRO_COLUNAS.values())


def test_atributo_estranho_nao_vaza_para_o_sql():
    """Injeção por atributo: to_where itera o dicionário fixo, não o objeto."""
    f = FiltrosAnalise(nu_ano=2021)
    f.__dict__["nu_ano; DROP TABLE tbl_enade_time_fato; --"] = 1
    where, params = f.to_where()
    assert "DROP" not in where
    assert params == {"nu_ano": 2021}


def test_valor_malicioso_fica_no_dicionario_de_parametros():
    """Mesmo um valor textual não entra no SQL: vai para params (psycopg2 escapa)."""
    f = FiltrosAnalise(nu_ano="2021 OR 1=1")  # type: ignore[arg-type]
    where, params = f.to_where()
    assert where == "AND nu_ano = %(nu_ano)s"
    assert params["nu_ano"] == "2021 OR 1=1"


@pytest.mark.parametrize("page,page_size,offset", [(1, 100, 0), (2, 100, 100), (3, 25, 50)])
def test_paginacao_offset_e_limit(page, page_size, offset):
    p = PaginationParams(page=page, page_size=page_size)
    assert p.offset == offset
    assert p.limit == page_size
