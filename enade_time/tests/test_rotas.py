"""
As rotas da API respondem sob o prefixo e com a forma esperada. O prefixo é
lido de `api.main` (hoje `/api`; na Fase 2 passa a `/api/enade-time`) para o
teste não precisar mudar quando o router entrar no ecossistema.
"""

from __future__ import annotations

import pytest

PREFIXO = "/api"

ROTAS_200 = [
    "/health",
    "/dim/regioes", "/dim/ufs", "/dim/ufs?co_regiao=1", "/dim/anos", "/dim/grupos",
    "/dim/modalidades", "/dim/categorias-adm", "/dim/organizacoes-academicas",
    "/analises/resumo-anual", "/analises/resumo-anual?co_regiao=1",
    "/analises/resumo-regiao", "/analises/resumo-uf",
    "/analises/resumo-ies?limit=5", "/analises/registros?page=1&page_size=5",
    "/benchmark/execucoes", "/benchmark/execucoes?apenas_validas=false",
    "/benchmark/execucoes/1", "/benchmark/etapas/1",
    "/benchmark/metricas", "/benchmark/campanhas", "/benchmark/comparativo",
    "/benchmark/comparativo?apenas_validas=false",
]


@pytest.mark.parametrize("rota", ROTAS_200)
def test_rota_responde_200(client, rota):
    r = client.get(PREFIXO + rota)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("rota", [
    "/analises/resumo-anual", "/analises/resumo-regiao", "/analises/resumo-uf",
    "/analises/resumo-ies?limit=5",
])
def test_resumos_expoem_total_cursos(client, rota):
    linhas = client.get(PREFIXO + rota).json()
    assert linhas
    for r in linhas:
        assert 0 < r["total_cursos"] <= r["total_registros"]


def test_execucao_inexistente_404(client):
    assert client.get(PREFIXO + "/benchmark/execucoes/999999").status_code == 404
    assert client.get(PREFIXO + "/benchmark/etapas/999999").status_code == 404


def test_uuid_invalido_422(client):
    assert client.get(PREFIXO + "/benchmark/comparativo", params={"campanha_id": "x"}).status_code == 422


def test_comparativo_tem_itens_e_resumo_e_e_retrocompativel(client):
    d = client.get(PREFIXO + "/benchmark/comparativo").json()
    for k in ("baseline_sequencial_id", "tempo_baseline_seg", "throughput_baseline_lps",
              "cpu_count_maquina", "itens", "resumo", "campanha_id", "maquina"):
        assert k in d
    assert isinstance(d["itens"], list) and isinstance(d["resumo"], list)
    for i in d["itens"]:
        for k in ("execucao_id", "modo", "num_workers", "tempo_total_seg", "throughput_lps",
                  "speedup", "eficiencia"):
            assert k in i
        if i["modo"] == "sequencial":
            assert i["speedup"] == 1.0 and i["eficiencia"] == 1.0
    if d["resumo"]:
        seq = [r for r in d["resumo"] if r["modo"] == "sequencial"]
        assert seq and seq[0]["speedup_mediana"] == 1.0
        assert d["baseline_sequencial_id"] is None  # mediana, não uma execução
        assert d["tempo_baseline_seg"] == pytest.approx(seq[0]["tempo_mediana"])


def test_comparativo_itens_iguais_a_view(client, cur):
    d = client.get(PREFIXO + "/benchmark/comparativo", params={"apenas_validas": "false"}).json()
    cur.execute("SELECT execucao_id, speedup::float AS s, eficiencia::float AS e FROM v_enade_time_benchmark_metricas")
    view = {r["execucao_id"]: (r["s"], r["e"]) for r in cur.fetchall()}
    paralelos = [i for i in d["itens"] if i["modo"] == "paralelo"]
    assert paralelos
    for i in paralelos:
        if i["execucao_id"] in view and view[i["execucao_id"]][0] is not None:
            assert i["speedup"] == pytest.approx(view[i["execucao_id"]][0], abs=1e-9)
            assert i["eficiencia"] == pytest.approx(view[i["execucao_id"]][1], abs=1e-9)


def test_metricas_expoem_pareamento(client):
    rows = client.get(PREFIXO + "/benchmark/metricas").json()
    assert rows
    for r in rows:
        assert r["pareamento"] in ("suite", "temporal")
        assert r["ordem_submissao"] in ("crescente", "lpt", None)


def test_campanhas_listam_oficial_e_smoke(client):
    rows = client.get(PREFIXO + "/benchmark/campanhas").json()
    for r in rows:
        assert set(r) >= {"campanha_id", "n_execucoes", "n_suites", "oficial"}
        assert r["n_execucoes"] >= 1
