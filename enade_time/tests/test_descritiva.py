"""
`GET /analises/descritiva`: estatística descritiva por edição com o **curso-ano** como unidade.

O problema que a rota resolve: cada linha de `tbl_enade_time_fato` é uma inscrição e repete a média do
curso (as 24.967 linhas são 582 pares curso-ano). `STDDEV`/`MIN`/`MAX` sobre as linhas pesam cada curso
pelo número de inscritos e só existiam para a NT_FG. Aqui as medidas saem de uma observação por curso-ano
e para as três notas.

Três camadas, da que não precisa de banco para a que precisa:

1. forma da resposta e repasse dos filtros (rota montada com o repositório trocado; roda em qualquer máquina);
2. **dados sintéticos**: a SQL contra um cálculo em Python (`statistics`) sobre uma tabela temporária que
   sombreia a fato, cobrindo os casos de borda (n = 1, nota nula, média zero, pesos de inscrição);
3. **aceitação**: sem filtros, a rota reproduz os valores calculados de forma independente a partir da base
   publicada (`dados/curso_ano_api_2026-11-25.csv`, uma linha por curso-ano, extraída da API em 25/11/2026,
   sha256 09db79fc...e95c) e a prévia do trabalho (`previa_descritiva_2026-11-25.txt`).

As camadas 2 e 3 são puladas (não falham) sem o Postgres local, como o resto da suíte.
"""

from __future__ import annotations

import csv
import random
import statistics
from collections import defaultdict
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from enade_time.api.dependencies import FiltrosAnalise, get_db_cursor
from enade_time.api.repositories import analises_repo
from enade_time.api.routers import analises

PREFIXO = "/api"
ROTA = PREFIXO + "/analises/descritiva"
CSV_CURSO_ANO = Path(__file__).parent / "dados" / "curso_ano_api_2026-11-25.csv"

NOTAS = ("nt_ger", "nt_fg", "nt_ce")
CSV_COLUNA = {"nt_ger": "ger", "nt_fg": "fg", "nt_ce": "ce"}
MEDIDAS = ("n", "media", "desvio_padrao", "variancia", "coef_variacao", "minimo", "q1", "mediana", "q3", "maximo")
ANOS = (2005, 2008, 2011, 2014, 2017, 2021)


# ---------------------------------------------------------------------------
# Cálculo independente (Python puro): nada daqui passa pela SQL do repositório
# ---------------------------------------------------------------------------

def descrever(valores: list[float]) -> dict:
    """Mesmas medidas da rota, em Python. Quartis por interpolação linear (= PERCENTILE_CONT)."""
    n = len(valores)
    if n == 0:
        return {m: (0 if m == "n" else None) for m in MEDIDAS}
    media = statistics.fmean(valores)
    if n == 1:
        q1 = mediana = q3 = valores[0]
        dp = variancia = None
    else:
        q1, mediana, q3 = statistics.quantiles(valores, n=4, method="inclusive")
        dp = statistics.stdev(valores)
        variancia = statistics.variance(valores)
    cv = 100 * dp / media if dp is not None and media != 0 else None
    return {
        "n": n, "media": media, "desvio_padrao": dp, "variancia": variancia, "coef_variacao": cv,
        "minimo": min(valores), "q1": q1, "mediana": mediana, "q3": q3, "maximo": max(valores),
    }


def esperado_por_ano(linhas: list[dict]) -> dict[int, dict]:
    """`linhas`: uma por curso-ano, com `ano` e as notas `ger`/`fg`/`ce` (None se ausente)."""
    por_ano: dict[int, list[dict]] = defaultdict(list)
    for linha in linhas:
        por_ano[linha["ano"]].append(linha)
    resultado = {}
    for ano, grupo in por_ano.items():
        item = {"cursos": len(grupo)}
        for nota in NOTAS:
            valores = [l[CSV_COLUNA[nota]] for l in grupo if l[CSV_COLUNA[nota]] is not None]
            item[nota] = descrever(valores)
        resultado[ano] = item
    return resultado


def ler_csv() -> list[dict]:
    def num(texto: str) -> float | None:
        return float(texto) if texto != "" else None

    with CSV_CURSO_ANO.open(encoding="utf-8", newline="") as arq:
        return [
            {
                "ano": int(r["ano"]), "curso": int(r["curso"]), "inscricoes": int(r["inscricoes"]),
                "regiao": int(r["regiao"]), "uf": int(r["uf"]), "categad": int(r["categad"]),
                "orgacad": int(r["orgacad"]),
                "ger": num(r["ger"]), "fg": num(r["fg"]), "ce": num(r["ce"]),
            }
            for r in csv.DictReader(arq)
        ]


# A base publicada (CSV extraído da API em produção) e o Postgres local têm uma única diferença de 1e-4:
# NT_CE do curso 20239 em 2008 (28,6938 na base publicada, 28,6937 no banco local, um empate de
# arredondamento do NUMERIC(7,4)). Contra a base publicada, as medidas coincidem a menos de 2e-4.
TOL_BASE_PUBLICADA = 2e-4


def conferir(obtido: list[dict], esperado: dict[int, dict], tol: float = 1e-9) -> None:
    """A resposta (lista de itens) bate com o cálculo independente, ano a ano e medida a medida."""
    assert [i["nu_ano"] for i in obtido] == sorted(esperado)
    for item in obtido:
        ref = esperado[item["nu_ano"]]
        assert item["cursos"] == ref["cursos"], item["nu_ano"]
        for nota in NOTAS:
            assert set(item[nota]) == set(MEDIDAS)
            for medida in MEDIDAS:
                valor, esperada = item[nota][medida], ref[nota][medida]
                contexto = f"{item['nu_ano']} {nota} {medida}"
                if esperada is None:
                    assert valor is None, contexto
                else:
                    assert valor == pytest.approx(esperada, rel=1e-9, abs=tol), contexto


# ---------------------------------------------------------------------------
# 1) Forma da resposta e filtros (sem banco)
# ---------------------------------------------------------------------------

def _estatistica(**extra) -> dict:
    base = {m: 1.0 for m in MEDIDAS}
    base["n"] = 3
    return {**base, **extra}


@pytest.fixture()
def cliente_sem_banco(monkeypatch):
    """Rota montada num app mínimo: o cursor é um dublê e o repositório devolve um item fixo."""
    capturado: dict = {}

    def falso(cursor, filtros):
        capturado["filtros"] = filtros
        return [{"nu_ano": 2021, "cursos": 4, "nt_ger": _estatistica(n=3), "nt_fg": _estatistica(),
                 "nt_ce": _estatistica(desvio_padrao=None, variancia=None, coef_variacao=None, n=1)}]

    monkeypatch.setattr(analises_repo, "descritiva", falso)
    app = FastAPI()
    app.include_router(analises.router, prefix=PREFIXO)
    app.dependency_overrides[get_db_cursor] = lambda: object()
    return TestClient(app), capturado


def test_forma_da_resposta(cliente_sem_banco):
    client, _ = cliente_sem_banco
    r = client.get(ROTA)
    assert r.status_code == 200, r.text
    (item,) = r.json()
    assert set(item) == {"nu_ano", "cursos", "nt_ger", "nt_fg", "nt_ce"}
    for nota in NOTAS:
        assert set(item[nota]) == set(MEDIDAS)
    assert item["nt_ce"]["desvio_padrao"] is None  # medida indefinida volta null, não zero


def test_repassa_os_mesmos_filtros_do_resumo_anual(cliente_sem_banco):
    client, capturado = cliente_sem_banco
    consulta = {"nu_ano": 2017, "co_regiao": 2, "co_uf": 23, "co_ies": 1, "co_grupo": 4004,
                "co_modalidade": 1, "co_categad": 1, "co_orgacad": 10028}
    assert client.get(ROTA, params=consulta).status_code == 200
    assert capturado["filtros"] == FiltrosAnalise(**consulta)
    client.get(ROTA)
    assert capturado["filtros"] == FiltrosAnalise()


def test_filtro_invalido_e_422(cliente_sem_banco):
    client, _ = cliente_sem_banco
    assert client.get(ROTA, params={"nu_ano": "abc"}).status_code == 422


def test_documenta_que_a_unidade_e_o_curso_ano(cliente_sem_banco):
    client, _ = cliente_sem_banco
    operacao = client.get("/openapi.json").json()["paths"][PREFIXO + "/analises/descritiva"]["get"]
    assert "curso-ano" in operacao["summary"] and "curso-ano" in operacao["description"]


def test_sql_reduz_a_curso_ano_antes_de_agregar_e_aplica_os_filtros():
    sqls: list[tuple[str, dict]] = []

    class CursorFalso:
        def execute(self, sql, params):
            sqls.append((sql, params))

        def fetchall(self):
            return []

    assert analises_repo.descritiva(CursorFalso(), FiltrosAnalise(nu_ano=2014, co_regiao=1)) == []
    sql, params = sqls[0]
    assert "GROUP BY f.nu_ano, f.co_curso" in sql
    assert "AND f.nu_ano = %(nu_ano)s AND f.co_regiao_curso = %(co_regiao)s" in sql
    assert params == {"nu_ano": 2014, "co_regiao": 1}
    for medida in ("STDDEV_SAMP", "VAR_SAMP", "PERCENTILE_CONT(0.25)", "PERCENTILE_CONT(0.5)", "PERCENTILE_CONT(0.75)"):
        assert sql.count(medida) >= len(NOTAS), medida  # STDDEV_SAMP também entra no CV


# ---------------------------------------------------------------------------
# 2) Dados sintéticos: SQL x Python (tabela temporária que sombreia a fato)
# ---------------------------------------------------------------------------

@pytest.fixture()
def fato_sintetica(cur):
    """Esvazia a fato *só nesta transação* (tabela temporária com o mesmo nome, vista antes da real)."""
    cur.execute("CREATE TEMP TABLE tbl_enade_time_fato (LIKE tbl_enade_time_fato INCLUDING DEFAULTS)")

    def inserir(ano, curso, ger, fg, ce, inscricoes=1, regiao=2, uf=29, categad=1, orgacad=10028):
        for _ in range(inscricoes):
            cur.execute(
                """INSERT INTO tbl_enade_time_fato
                   (nu_ano, co_curso, co_ies, co_categad, co_orgacad, co_grupo, co_modalidade,
                    co_uf_curso, co_regiao_curso, media_nt_ger, media_nt_fg, media_nt_ce)
                   VALUES (%s, %s, 1, %s, %s, 40, 1, %s, %s, %s, %s, %s)""",
                (ano, curso, categad, orgacad, uf, regiao, ger, fg, ce),
            )

    return inserir


def test_cada_curso_ano_conta_uma_vez_seja_qual_for_o_numero_de_inscricoes(cur, fato_sintetica):
    # Curso 1 tem 50 inscrições com média 10; curso 2 tem 1 com média 20. Por inscrição a média seria
    # ~10,2; por curso-ano é 15, e o desvio-padrão amostral de {10, 20} é 7,0711.
    fato_sintetica(2005, 1, 10, 10, 10, inscricoes=50)
    fato_sintetica(2005, 2, 20, 20, 20, inscricoes=1)
    (item,) = analises_repo.descritiva(cur, FiltrosAnalise())
    assert item["cursos"] == 2
    ger = item["nt_ger"]
    assert ger["n"] == 2
    assert ger["media"] == pytest.approx(15.0)
    assert ger["desvio_padrao"] == pytest.approx(7.0710678118654755)
    assert ger["variancia"] == pytest.approx(50.0)
    assert ger["coef_variacao"] == pytest.approx(100 * 7.0710678118654755 / 15)
    assert (ger["minimo"], ger["q1"], ger["mediana"], ger["q3"], ger["maximo"]) == (10, 12.5, 15, 17.5, 20)


def test_nota_nula_nao_entra_no_n_mas_o_curso_entra_em_cursos(cur, fato_sintetica):
    fato_sintetica(2008, 1, 30, 40, 20)
    fato_sintetica(2008, 2, 50, None, 20, inscricoes=3)   # sem NT_FG
    fato_sintetica(2008, 3, None, None, None)             # sem nenhuma nota
    (item,) = analises_repo.descritiva(cur, FiltrosAnalise())
    assert item["cursos"] == 3
    assert (item["nt_ger"]["n"], item["nt_fg"]["n"], item["nt_ce"]["n"]) == (2, 1, 2)
    assert item["nt_ger"]["media"] == pytest.approx(40.0)
    assert item["nt_fg"]["media"] == pytest.approx(40.0)


def test_n_igual_a_um_deixa_dispersao_indefinida_e_quartis_iguais_ao_valor(cur, fato_sintetica):
    fato_sintetica(2011, 1, 33.3333, 44.4444, 22.2222, inscricoes=7)
    (item,) = analises_repo.descritiva(cur, FiltrosAnalise())
    ger = item["nt_ger"]
    assert ger["n"] == 1
    assert ger["desvio_padrao"] is None and ger["variancia"] is None and ger["coef_variacao"] is None
    assert ger["media"] == pytest.approx(33.3333)
    assert ger["minimo"] == ger["q1"] == ger["mediana"] == ger["q3"] == ger["maximo"] == pytest.approx(33.3333)


def test_edicao_sem_nenhuma_nota_valida_devolve_n_zero_e_medidas_nulas(cur, fato_sintetica):
    fato_sintetica(2014, 1, None, None, None, inscricoes=2)
    (item,) = analises_repo.descritiva(cur, FiltrosAnalise())
    assert item["cursos"] == 1
    for nota in NOTAS:
        assert item[nota] == {m: (0 if m == "n" else None) for m in MEDIDAS}


def test_media_zero_nao_divide_por_zero_no_coeficiente_de_variacao(cur, fato_sintetica):
    fato_sintetica(2017, 1, 0, 0, 0)
    fato_sintetica(2017, 2, 0, 0, 0)
    (item,) = analises_repo.descritiva(cur, FiltrosAnalise())
    assert item["nt_ger"]["desvio_padrao"] == 0
    assert item["nt_ger"]["coef_variacao"] is None


def test_edicoes_nao_se_misturam_e_saem_em_ordem_de_ano(cur, fato_sintetica):
    fato_sintetica(2021, 1, 50, 50, 50)
    fato_sintetica(2005, 1, 10, 10, 10)
    fato_sintetica(2005, 2, 30, 30, 30)
    itens = analises_repo.descritiva(cur, FiltrosAnalise())
    assert [(i["nu_ano"], i["cursos"], i["nt_ger"]["media"]) for i in itens] == [(2005, 2, 20.0), (2021, 1, 50.0)]


def test_mesmo_codigo_de_curso_em_edicoes_diferentes_sao_pares_distintos(cur, fato_sintetica):
    fato_sintetica(2005, 99, 10, 10, 10)
    fato_sintetica(2008, 99, 20, 20, 20)
    itens = analises_repo.descritiva(cur, FiltrosAnalise())
    assert [(i["nu_ano"], i["cursos"]) for i in itens] == [(2005, 1), (2008, 1)]


def test_sql_confere_com_python_em_dados_aleatorios_e_com_filtros(cur, fato_sintetica):
    rng = random.Random(20261125)
    linhas = []  # uma por curso-ano, no formato de `esperado_por_ano`
    curso = 0
    for ano in (2005, 2011, 2021):
        for _ in range(rng.randint(30, 60)):
            curso += 1
            regiao, uf = rng.choice([(1, 12), (2, 29), (2, 23)])
            notas = {n: (None if rng.random() < 0.08 else round(rng.uniform(0, 100), 4)) for n in ("ger", "fg", "ce")}
            linha = {"ano": ano, "curso": curso, "regiao": regiao, "uf": uf, "categad": rng.choice([1, 4]), **notas}
            linhas.append(linha)
            fato_sintetica(ano, curso, notas["ger"], notas["fg"], notas["ce"], inscricoes=rng.randint(1, 12),
                           regiao=regiao, uf=uf, categad=linha["categad"])

    conferir(analises_repo.descritiva(cur, FiltrosAnalise()), esperado_por_ano(linhas))
    conferir(analises_repo.descritiva(cur, FiltrosAnalise(co_regiao=2)),
             esperado_por_ano([l for l in linhas if l["regiao"] == 2]))
    conferir(analises_repo.descritiva(cur, FiltrosAnalise(co_uf=29, co_categad=4)),
             esperado_por_ano([l for l in linhas if l["uf"] == 29 and l["categad"] == 4]))
    conferir(analises_repo.descritiva(cur, FiltrosAnalise(nu_ano=2011)),
             esperado_por_ano([l for l in linhas if l["ano"] == 2011]))
    assert analises_repo.descritiva(cur, FiltrosAnalise(nu_ano=1999)) == []


def test_desvio_padrao_curso_ano_de_regiao_e_uf_ignora_o_peso_das_inscricoes(cur, fato_sintetica):
    # Região 2: curso 1 (50 inscrições, média 10) e curso 2 (1 inscrição, média 20), mesma edição.
    fato_sintetica(2005, 1, 10, 10, 10, inscricoes=50, regiao=2, uf=29)
    fato_sintetica(2005, 2, 20, 30, 40, inscricoes=1, regiao=2, uf=29)
    fato_sintetica(2008, 3, 30, 50, 70, inscricoes=2, regiao=2, uf=23)  # outra edição, outra UF, mesma região
    fato_sintetica(2005, 4, 55, 55, 55, inscricoes=1, regiao=1, uf=12)  # região com um único curso-ano

    por_regiao = {r["co_regiao"]: r for r in analises_repo.resumo_regiao(cur, FiltrosAnalise())}
    ger2 = [10, 20, 30]
    assert por_regiao[2]["desvio_padrao_ger_curso_ano"] == pytest.approx(statistics.stdev(ger2))
    assert por_regiao[2]["desvio_padrao_fg_curso_ano"] == pytest.approx(statistics.stdev([10, 30, 50]))
    assert por_regiao[2]["desvio_padrao_ce_curso_ano"] == pytest.approx(statistics.stdev([10, 40, 70]))
    assert por_regiao[1]["desvio_padrao_ger_curso_ano"] is None  # n = 1: desvio-padrão indefinido
    assert por_regiao[2]["total_registros"] == 53  # os campos legados continuam sobre as inscrições

    por_uf = {u["co_uf"]: u for u in analises_repo.resumo_uf(cur, FiltrosAnalise())}
    assert por_uf[29]["desvio_padrao_ger_curso_ano"] == pytest.approx(statistics.stdev([10, 20]))
    assert por_uf[23]["desvio_padrao_ger_curso_ano"] is None

    so_2005 = {r["co_regiao"]: r for r in analises_repo.resumo_regiao(cur, FiltrosAnalise(nu_ano=2005))}
    assert so_2005[2]["desvio_padrao_ger_curso_ano"] == pytest.approx(statistics.stdev([10, 20]))


# ---------------------------------------------------------------------------
# 3) Aceitação: a base publicada (582 curso-ano) e a prévia do trabalho
# ---------------------------------------------------------------------------

# Prévia do trabalho (previa_descritiva_2026-11-25.txt), NT_GER por edição:
# ano: (n, média, DP, variância, CV %, mín, Q1, mediana, Q3, máx), arredondados como no texto.
PREVIA_NT_GER = {
    2005: (110, 33.11, 6.93, 48.08, 20.9, 0.99, 29.09, 33.03, 37.87, 49.25),
    2008: (165, 31.48, 5.26, 27.69, 16.7, 7.59, 28.23, 31.78, 34.44, 50.72),
    2011: (79, 32.48, 7.04, 49.63, 21.7, 21.42, 26.60, 31.72, 37.34, 51.46),
    2014: (66, 43.59, 8.84, 78.17, 20.3, 27.88, 37.17, 40.75, 50.48, 62.74),
    2017: (72, 40.97, 7.46, 55.69, 18.2, 26.26, 35.83, 40.98, 46.65, 57.50),
    2021: (76, 36.19, 7.54, 56.88, 20.8, 24.53, 31.00, 34.78, 40.95, 54.97),
}
# NT_FG e NT_CE por edição: (n, média, DP, CV %).
PREVIA_NT_FG = {
    2005: (110, 54.85, 8.73, 15.9), 2008: (165, 47.53, 6.93, 14.6), 2011: (79, 51.70, 6.26, 12.1),
    2014: (66, 60.07, 6.90, 11.5), 2017: (72, 53.48, 6.83, 12.8), 2021: (76, 38.21, 6.41, 16.8),
}
PREVIA_NT_CE = {
    2005: (110, 25.87, 7.28, 28.2), 2008: (165, 26.12, 5.50, 21.1), 2011: (79, 26.06, 8.62, 33.1),
    2014: (66, 38.08, 10.10, 26.5), 2017: (72, 36.79, 8.36, 22.7), 2021: (76, 35.51, 8.48, 23.9),
}
# NT_GER por região e edição: (n, média, DP). Norte = 1, Nordeste = 2.
PREVIA_REGIAO = {
    (2005, 1): (32, 32.19, 6.20), (2005, 2): (78, 33.49, 7.22),
    (2008, 1): (46, 30.12, 4.27), (2008, 2): (119, 32.00, 5.53),
    (2011, 1): (21, 30.49, 6.88), (2011, 2): (58, 33.21, 7.02),
    (2014, 1): (15, 40.75, 7.70), (2014, 2): (51, 44.43, 9.05),
    (2017, 1): (18, 37.42, 7.06), (2017, 2): (54, 42.16, 7.27),
    (2021, 1): (14, 31.98, 6.85), (2021, 2): (62, 37.15, 7.41),
}
MEIO_CENTESIMO = 0.005 + 1e-9  # os valores da prévia estão arredondados em 2 casas
MEIO_DECIMO = 0.05 + 1e-9      # e o CV em 1 casa


def test_csv_publicado_tem_582_pares_curso_ano_e_568_com_nt_ger():
    linhas = ler_csv()
    assert len(linhas) == len({(l["ano"], l["curso"]) for l in linhas}) == 582
    assert sum(l["ger"] is not None for l in linhas) == 568
    assert sum(l["inscricoes"] for l in linhas) == 24_967


def test_repositorio_reproduz_a_base_publicada_sem_filtros(cur):
    conferir(analises_repo.descritiva(cur, FiltrosAnalise()), esperado_por_ano(ler_csv()), TOL_BASE_PUBLICADA)


def test_rota_reproduz_a_previa_do_trabalho_sem_filtros(client):
    itens = {i["nu_ano"]: i for i in client.get(ROTA).json()}
    assert sorted(itens) == list(ANOS)
    assert sum(i["cursos"] for i in itens.values()) == 582
    assert sum(i["nt_ger"]["n"] for i in itens.values()) == 568

    for ano, (n, media, dp, var, cv, mn, q1, med, q3, mx) in PREVIA_NT_GER.items():
        ger = itens[ano]["nt_ger"]
        assert ger["n"] == n, ano
        assert ger["media"] == pytest.approx(media, abs=MEIO_CENTESIMO), ano
        assert ger["desvio_padrao"] == pytest.approx(dp, abs=MEIO_CENTESIMO), ano
        assert ger["variancia"] == pytest.approx(var, abs=MEIO_CENTESIMO), ano
        assert ger["coef_variacao"] == pytest.approx(cv, abs=MEIO_DECIMO), ano
        assert ger["minimo"] == pytest.approx(mn, abs=MEIO_CENTESIMO), ano
        assert ger["q1"] == pytest.approx(q1, abs=MEIO_CENTESIMO), ano
        assert ger["mediana"] == pytest.approx(med, abs=MEIO_CENTESIMO), ano
        assert ger["q3"] == pytest.approx(q3, abs=MEIO_CENTESIMO), ano
        assert ger["maximo"] == pytest.approx(mx, abs=MEIO_CENTESIMO), ano

    for nota, previa in (("nt_fg", PREVIA_NT_FG), ("nt_ce", PREVIA_NT_CE)):
        for ano, (n, media, dp, cv) in previa.items():
            est = itens[ano][nota]
            assert est["n"] == n, (nota, ano)
            assert est["media"] == pytest.approx(media, abs=MEIO_CENTESIMO), (nota, ano)
            assert est["desvio_padrao"] == pytest.approx(dp, abs=MEIO_CENTESIMO), (nota, ano)
            assert est["coef_variacao"] == pytest.approx(cv, abs=MEIO_DECIMO), (nota, ano)


def test_exemplos_do_enunciado_2005_e_2014(client):
    itens = {i["nu_ano"]: i for i in client.get(ROTA).json()}
    ger = itens[2005]["nt_ger"]
    assert (ger["n"], round(ger["media"], 2), round(ger["desvio_padrao"], 2), round(ger["variancia"], 2)) == (
        110, 33.11, 6.93, 48.08)
    assert (round(ger["minimo"], 2), round(ger["q1"], 2), round(ger["mediana"], 2), round(ger["q3"], 2),
            round(ger["maximo"], 2)) == (0.99, 29.09, 33.03, 37.87, 49.25)
    ger14 = itens[2014]["nt_ger"]
    assert (ger14["n"], round(ger14["media"], 2), round(ger14["desvio_padrao"], 2)) == (66, 43.59, 8.84)


@pytest.mark.parametrize("filtro,campo,valor", [
    ({"nu_ano": 2014}, "ano", 2014),
    ({"co_regiao": 1}, "regiao", 1),
    ({"co_regiao": 2}, "regiao", 2),
    ({"co_categad": 4}, "categad", 4),
    ({"co_orgacad": 10022}, "orgacad", 10022),
    ({"co_uf": 23}, "uf", 23),
])
def test_rota_com_filtros_reproduz_a_base_publicada(client, filtro, campo, valor):
    linhas = [l for l in ler_csv() if l[campo] == valor]
    assert linhas
    conferir(client.get(ROTA, params=filtro).json(), esperado_por_ano(linhas), TOL_BASE_PUBLICADA)


def test_filtros_combinados_e_recorte_vazio(client):
    linhas = [l for l in ler_csv() if l["regiao"] == 1 and l["categad"] == 1 and l["ano"] >= 2011]
    assert linhas
    obtido = [i for i in client.get(ROTA, params={"co_regiao": 1, "co_categad": 1}).json() if i["nu_ano"] >= 2011]
    conferir(obtido, esperado_por_ano(linhas), TOL_BASE_PUBLICADA)
    assert client.get(ROTA, params={"nu_ano": 1999}).json() == []


@pytest.mark.parametrize("ano,regiao", sorted(PREVIA_REGIAO))
def test_previa_por_regiao_e_edicao_na_rota_descritiva_e_no_resumo_regiao(client, ano, regiao):
    n, media, dp = PREVIA_REGIAO[(ano, regiao)]
    (item,) = client.get(ROTA, params={"nu_ano": ano, "co_regiao": regiao}).json()
    assert item["nt_ger"]["n"] == n
    assert item["nt_ger"]["media"] == pytest.approx(media, abs=MEIO_CENTESIMO)
    assert item["nt_ger"]["desvio_padrao"] == pytest.approx(dp, abs=MEIO_CENTESIMO)
    # `resumo-regiao` traz o mesmo desvio-padrão (curso-ano) no campo novo
    regioes = client.get(PREFIXO + "/analises/resumo-regiao", params={"nu_ano": ano}).json()
    da_regiao = next(r for r in regioes if r["co_regiao"] == regiao)
    assert da_regiao["desvio_padrao_ger_curso_ano"] == pytest.approx(dp, abs=MEIO_CENTESIMO)


def test_resumos_por_regiao_e_uf_expoem_os_tres_desvios_por_curso_ano_e_mantem_os_legados(client):
    for rota in ("/analises/resumo-regiao", "/analises/resumo-uf"):
        linhas = client.get(PREFIXO + rota).json()
        assert linhas
        for linha in linhas:
            for campo in ("media_geral", "media_min", "media_max", "desvio_padrao",
                          "media_geral_ger", "media_geral_ce"):
                assert campo in linha, (rota, campo)
            for nota in ("ger", "fg", "ce"):
                assert linha[f"desvio_padrao_{nota}_curso_ano"] > 0, (rota, nota)


def test_desvio_por_curso_ano_da_uf_confere_com_a_base_publicada(client):
    linhas = ler_csv()
    ufs = client.get(PREFIXO + "/analises/resumo-uf").json()
    for uf in ufs:
        for nota, coluna in (("ger", "ger"), ("fg", "fg"), ("ce", "ce")):
            valores = [l[coluna] for l in linhas if l["uf"] == uf["co_uf"] and l[coluna] is not None]
            assert uf[f"desvio_padrao_{nota}_curso_ano"] == pytest.approx(statistics.stdev(valores), abs=TOL_BASE_PUBLICADA), (
                uf["sigla"], nota)
