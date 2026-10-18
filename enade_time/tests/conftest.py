"""
Fixtures compartilhadas. Os testes que precisam do Postgres local são pulados
(não falham) quando o container não está no ar — assim a suíte roda em
qualquer máquina e só a parte de banco depende do `docker compose up`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]  # raiz do EnadeX
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DB_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname":   os.environ.get("POSTGRES_DB", "enade_db"),
    "user":     os.environ.get("POSTGRES_USER", "enade_user"),
    "password": os.environ.get("POSTGRES_PASSWORD", "enade_password"),
    "connect_timeout": 3,
}


def _conectar():
    import psycopg2
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError:
        return None


@pytest.fixture(scope="session")
def conn():
    c = _conectar()
    if c is None:
        pytest.skip("Postgres local indisponível (docker compose up -d postgres)")
    yield c
    c.close()


@pytest.fixture()
def cur(conn):
    from psycopg2.extras import RealDictCursor
    with conn.cursor(cursor_factory=RealDictCursor) as c:
        yield c
    conn.rollback()


@pytest.fixture(scope="session")
def client():
    c = _conectar()
    if c is None:
        pytest.skip("Postgres local indisponível — TestClient precisa do banco")
    c.close()
    from fastapi.testclient import TestClient
    from enade_time.api.main import app
    with TestClient(app) as tc:
        yield tc
