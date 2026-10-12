"""
Os três repositórios contra o banco local: contagens que a base v1.1 fixa e
um caso por filtro. Pulados sem Postgres.
"""

from __future__ import annotations

import pytest

from enade_time.api.dependencies import FiltrosAnalise
from enade_time.api.repositories import analises_repo, benchmark_repo, dimensoes_repo

TOTAL = 24_967
POR_ANO = {2005: 5748, 2008: 8740, 2011: 2463, 2014: 2388, 2017: 2537, 2021: 3091}
CURSOS_ANO = 582


def test_dimensoes_contagens(cur):
    assert len(dimensoes_repo.listar_regioes(cur)) == 2
    assert len(dimensoes_repo.listar_ufs(cur, None)) == 16
    assert len(dimensoes_repo.listar_ufs(cur, 1)) == 7
    assert len(dimensoes_repo.listar_anos(cur)) == 6
    assert {g["co_grupo"] for g in dimensoes_repo.listar_grupos(cur)} == {40, 4004}
    assert len(dimensoes_repo.listar_modalidades(cur)) == 2


def test_resumo_anual_total_e_por_ano(cur):
    rows = analises_repo.resumo_anual(cur, FiltrosAnalise())
    assert {r["nu_ano"]: r["total_registros"] for r in rows} == POR_ANO
    assert sum(r["total_registros"] for r in rows) == TOTAL


def test_total_cursos_e_a_unidade_analitica_curso_ano(cur):
    # 24.967 inscrições, mas só 582 cursos-ano (D16): somar os cursos distintos de cada ano dá 582.
    anual = analises_repo.resumo_anual(cur, FiltrosAnalise())
    assert sum(r["total_cursos"] for r in anual) == CURSOS_ANO
    assert all(0 < r["total_cursos"] <= r["total_registros"] for r in anual)
    # por região, os cursos de cada ano também fecham os 582 (um curso pertence a uma região)
    for ano in POR_ANO:
        regioes = analises_repo.resumo_regiao(cur, FiltrosAnalise(nu_ano=ano))
        ano_total = next(r for r in anual if r["nu_ano"] == ano)["total_cursos"]
        assert sum(r["total_cursos"] for r in regioes) == ano_total


@pytest.mark.parametrize("filtro,esperado", [
    (FiltrosAnalise(nu_ano=2021), {2021: 3091}),
    (FiltrosAnalise(co_grupo=40), {2005: 5748, 2008: 8740}),
    (FiltrosAnalise(co_grupo=4004), {2011: 2463, 2014: 2388, 2017: 2537, 2021: 3091}),
])
def test_resumo_anual_filtros(cur, filtro, esperado):
    rows = analises_repo.resumo_anual(cur, filtro)
    assert {r["nu_ano"]: r["total_registros"] for r in rows} == esperado


def test_resumo_regiao_e_uf_fecham_o_total(cur):
    reg = analises_repo.resumo_regiao(cur, FiltrosAnalise())
    assert {r["co_regiao"] for r in reg} == {1, 2}
    assert sum(r["total_registros"] for r in reg) == TOTAL
    uf = analises_repo.resumo_uf(cur, FiltrosAnalise())
    assert len(uf) == 16
    assert sum(r["total_registros"] for r in uf) == TOTAL
    uf_norte = analises_repo.resumo_uf(cur, FiltrosAnalise(co_regiao=1))
    assert {r["co_regiao"] for r in uf_norte} == {1}


def test_resumo_ies_respeita_limit_e_min_cursos(cur):
    rows = analises_repo.resumo_ies(cur, FiltrosAnalise(nu_ano=2021), limit=5, min_cursos=2)
    assert len(rows) <= 5
    assert all(r["total_cursos"] >= 2 for r in rows)  # "mín. cursos" conta cursos, não inscrições
    gers = [r["media_geral_ger"] for r in rows if r["media_geral_ger"] is not None]
    assert gers == sorted(gers, reverse=True)


def test_registros_paginados(cur):
    assert analises_repo.contar_registros(cur, FiltrosAnalise()) == TOTAL
    assert analises_repo.contar_registros(cur, FiltrosAnalise(nu_ano=2021, co_uf=23)) > 0
    pagina = analises_repo.listar_registros(cur, FiltrosAnalise(), 5, 0)
    assert len(pagina) == 5
    assert set(pagina[0]) >= {"id", "nu_ano", "co_curso", "media_nt_fg", "media_nt_ger", "media_nt_ce"}


def test_benchmark_execucoes_e_etapas(cur):
    execs = benchmark_repo.listar_execucoes(cur, apenas_validas=True, ids_excluir=[])
    assert len(execs) >= 6
    assert {e["id"] for e in execs} >= {1, 2, 3, 4, 5, 6}
    etapas = benchmark_repo.listar_etapas(cur, 1, apenas_validas=True, ids_excluir=[])
    assert etapas is not None and len(etapas) == 6
    assert [e["ano"] for e in etapas] == [2005, 2008, 2011, 2014, 2017, 2021]
    assert benchmark_repo.get_execucao(cur, 999999, apenas_validas=True, ids_excluir=[]) is None


def test_benchmark_ids_excluir_esconde_execucoes(cur):
    todos = benchmark_repo.listar_execucoes(cur, apenas_validas=True, ids_excluir=[])
    sem = benchmark_repo.listar_execucoes(cur, apenas_validas=True, ids_excluir=[1, 2, 3])
    assert len(sem) == len(todos) - 3
    assert benchmark_repo.get_execucao(cur, 1, apenas_validas=True, ids_excluir=[1]) is None
    assert benchmark_repo.get_execucao(cur, 1, apenas_validas=False, ids_excluir=[1]) is not None


def test_comparativo_legado_usa_view_e_nao_recalcula(cur):
    """No banco legado o #3 tem de aparecer com 2,0749× (baseline #1), nunca 2,6157×."""
    d = benchmark_repo.comparativo(cur, apenas_validas=False, ids_excluir=[])
    por_id = {i["execucao_id"]: i for i in d["itens"]}
    if 3 in por_id:
        assert por_id[3]["speedup"] == pytest.approx(2.0749)
        assert por_id[3]["baseline_execucao_id"] == 1
