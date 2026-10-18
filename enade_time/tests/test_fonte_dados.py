"""
A mesma API lê do Postgres local (o instrumento do experimento) ou do Supabase (onde os
resultados são publicados), trocando só o DSN. Estes testes não precisam de banco, exceto o
do /health, que é pulado sem o Postgres local.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from enade_time.api import database
from enade_time.api.settings import Settings, fonte_dos_dados
from enade_time.enade_time_rotas import router


def _settings(**kw) -> Settings:
    # _env_file=None: o teste não pode depender do enade_time/.env de quem roda
    return Settings(_env_file=None, **kw)


def test_sem_dsn_a_fonte_e_o_postgres_local():
    assert fonte_dos_dados(_settings()) == "local"


@pytest.mark.parametrize("url,esperada", [
    ("postgresql://enade_time_reader.abc@aws-1-us-east-2.pooler.supabase.com:5432/postgres", "supabase"),
    ("postgresql://u:p@db.abc.supabase.co:5432/postgres", "supabase"),
    ("postgresql://u:p@outro-servidor.exemplo.com:5432/enade", "externo"),
])
def test_dsn_classifica_a_fonte(url, esperada):
    assert fonte_dos_dados(_settings(enade_time_db_url=url)) == esperada


def test_dsn_tem_precedencia_sobre_postgres_host(monkeypatch):
    capturado = {}

    def pool_falso(*args, **kwargs):
        capturado["args"], capturado["kwargs"] = args, kwargs
        raise RuntimeError("não conecta de verdade")

    monkeypatch.setattr(database, "ThreadedConnectionPool", pool_falso)
    cfg = _settings(enade_time_db_url="postgresql://u:p@nuvem.exemplo:5432/x", postgres_host="localhost")
    database.close_pool()
    with pytest.raises(RuntimeError):
        database.init_pool(cfg)
    assert capturado["kwargs"]["dsn"] == "postgresql://u:p@nuvem.exemplo:5432/x"
    assert "host" not in capturado["kwargs"]
    assert capturado["kwargs"]["connect_timeout"] == cfg.db_connect_timeout


def test_sem_dsn_usa_os_parametros_do_postgres_local(monkeypatch):
    capturado = {}

    def pool_falso(*args, **kwargs):
        capturado.update(kwargs)
        raise RuntimeError("não conecta de verdade")

    monkeypatch.setattr(database, "ThreadedConnectionPool", pool_falso)
    database.close_pool()
    with pytest.raises(RuntimeError):
        database.init_pool(_settings(postgres_host="meu-host"))
    assert capturado["host"] == "meu-host" and "dsn" not in capturado


def test_health_informa_fonte_e_publicacao(conn):
    database.close_pool()
    app = FastAPI()
    app.include_router(router)
    try:
        corpo = TestClient(app).get("/api/enade-time/health").json()
    finally:
        database.close_pool()
    assert corpo["status"] == "ok" and corpo["database"] == "ok"
    assert corpo["fonte"] in {"local", "supabase", "externo"}
    assert "ultima_publicacao" in corpo and "versao_dataset" in corpo
