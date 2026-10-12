"""
Modo ecossistema: o router do ENADE-Time incluído num `FastAPI()` sem lifespan,
como o `api_main.py` central faria. Cobre o contrato com o frontend do grupo
(`EnadeX_Frontend/app/enade-time`): prefixo `/api/enade-time`, 20 rotas GET, e
falhas de banco devolvidas como 503/500 **com cabeçalhos CORS** — um 500 sem
CORS aparece no navegador como erro de rede e o dashboard não sabe o que houve.
"""

from __future__ import annotations

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from enade_time.api import database
from enade_time.enade_time_rotas import router

PREFIXO = "/api/enade-time"
ORIGEM = {"Origin": "http://localhost:3000"}


def _app_central() -> FastAPI:
    """Espelha o `api_main.py` do grupo: CORS para o Next em :3000 e include_router."""
    app = FastAPI(title="EnadeX API (simulada)")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


@pytest.fixture(autouse=True)
def pool_limpo():
    database.close_pool()
    yield
    database.close_pool()


@pytest.fixture()
def client_central():
    return TestClient(_app_central())  # sem `with`: lifespan não roda, como no api_main


def test_inventario_19_rotas_get_sob_o_prefixo():
    rotas = [r for r in _app_central().routes if isinstance(r, APIRoute) and r.path.startswith(PREFIXO)]
    assert len(rotas) == 20
    assert all(r.methods == {"GET"} for r in rotas)
    grupos = {r.path.split("/")[3] for r in rotas}
    assert grupos == {"health", "dim", "analises", "benchmark"}


def test_banco_fora_devolve_503_com_cors(monkeypatch, client_central):
    chamadas = []

    def pool_que_falha(*args, **kwargs):
        chamadas.append(1)
        raise psycopg2.OperationalError("connection refused: host=db.interno user=enade_user")

    monkeypatch.setattr(database, "ThreadedConnectionPool", pool_que_falha)

    r = client_central.get(f"{PREFIXO}/dim/regioes", headers=ORIGEM)
    assert r.status_code == 503
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert r.json()["detail"] == "Banco do ENADE-Time indisponível"
    assert "db.interno" not in r.text and "enade_user" not in r.text

    # Cooldown: enquanto o banco está fora, as demais requisições não tentam conectar de novo.
    r2 = client_central.get(f"{PREFIXO}/analises/resumo-anual", headers=ORIGEM)
    assert r2.status_code == 503
    assert len(chamadas) == 1


def test_health_com_banco_fora_nao_vaza_o_erro(monkeypatch, client_central):
    def pool_que_falha(*args, **kwargs):
        raise psycopg2.OperationalError("connection refused: host=db.interno user=enade_user")

    monkeypatch.setattr(database, "ThreadedConnectionPool", pool_que_falha)

    r = client_central.get(f"{PREFIXO}/health", headers=ORIGEM)
    assert r.status_code == 503
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert r.json()["detail"] == {"status": "degraded", "database": "unreachable", "version": "0.2.0"}
    assert "db.interno" not in r.text and "enade_user" not in r.text


class _ConexaoSaudavel:
    closed = 0

    def cursor(self, cursor_factory=None):
        return _CursorQuebrado(None)

    def commit(self):
        pass

    def rollback(self):
        pass


class _PoolSaudavel:
    def __init__(self, *args, **kwargs):
        self.conn = _ConexaoSaudavel()

    def getconn(self):
        return self.conn

    def putconn(self, conn, close=False):
        pass

    def closeall(self):
        pass


def test_banco_volta_sem_reiniciar_a_api(monkeypatch, client_central):
    def pool_que_falha(*args, **kwargs):
        raise psycopg2.OperationalError("refused")

    monkeypatch.setattr(database, "ThreadedConnectionPool", pool_que_falha)
    assert client_central.get(f"{PREFIXO}/dim/regioes").status_code == 503

    # O banco volta: passado o cooldown, a próxima requisição reconecta sozinha.
    monkeypatch.setattr(database, "ThreadedConnectionPool", _PoolSaudavel)
    database._falha_ate = 0.0
    assert client_central.get(f"{PREFIXO}/dim/regioes").status_code == 200


class _CursorQuebrado:
    def __init__(self, erro):
        self._erro = erro

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a, **k):
        if self._erro is not None:
            raise self._erro

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _ConexaoFalsa:
    def __init__(self, erro):
        self._erro = erro
        self.closed = 1  # conexão já morta, como depois de o Postgres cair
        self.rollbacks = 0

    def cursor(self, cursor_factory=None):
        return _CursorQuebrado(self._erro)

    def commit(self):
        raise psycopg2.InterfaceError("connection already closed")

    def rollback(self):
        self.rollbacks += 1
        raise psycopg2.InterfaceError("connection already closed")


class _PoolFalso:
    def __init__(self, erro):
        self.conn = _ConexaoFalsa(erro)
        self.devolvidas = []

    def getconn(self):
        return self.conn

    def putconn(self, conn, close=False):
        self.devolvidas.append((conn, close))

    def closeall(self):
        pass


def test_conexao_morta_no_pool_devolve_503_com_cors(client_central):
    pool = _PoolFalso(psycopg2.OperationalError("server closed the connection unexpectedly"))
    database._pool = pool

    r = client_central.get(f"{PREFIXO}/dim/regioes", headers=ORIGEM)

    assert r.status_code == 503
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert pool.conn.rollbacks == 0  # não faz rollback em conexão fechada
    assert pool.devolvidas == [(pool.conn, True)]  # conexão morta é descartada do pool
    assert database._pool is None  # as demais conexões ociosas também estão mortas: pool descartado

    # Cooldown: a requisição seguinte responde 503 na hora, sem tentar reconectar.
    database._pool = pool
    pool.devolvidas.clear()
    r2 = client_central.get(f"{PREFIXO}/analises/resumo-anual", headers=ORIGEM)
    assert r2.status_code == 503
    assert pool.devolvidas == []  # nem chegou a pegar conexão do pool


def test_erro_de_sql_devolve_500_com_cors(client_central):
    pool = _PoolFalso(psycopg2.ProgrammingError('relation "v_enade_time_benchmark_resumo" does not exist'))
    pool.conn.closed = 0
    pool.conn.rollback = lambda: None
    database._pool = pool

    r = client_central.get(f"{PREFIXO}/dim/regioes", headers=ORIGEM)

    assert r.status_code == 500
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert r.json()["detail"] == "Erro de banco no ENADE-Time"
    assert "v_enade_time_benchmark_resumo" not in r.text


ROTAS_COM_BANCO = [
    "/health",
    "/dim/regioes", "/dim/anos",
    "/analises/resumo-anual", "/analises/registros?page=1&page_size=5",
    "/benchmark/execucoes", "/benchmark/campanhas", "/benchmark/comparativo",
]


@pytest.mark.parametrize("rota", ROTAS_COM_BANCO)
def test_rotas_respondem_200_com_banco(conn, client_central, rota):
    r = client_central.get(PREFIXO + rota, headers=ORIGEM)
    assert r.status_code == 200, r.text
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
