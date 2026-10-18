import threading
import time

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

from enade_time.api.settings import Settings, get_settings

# Depois de uma falha de conexão, as requisições seguintes recebem erro imediato
# durante este intervalo em vez de cada uma esperar o connect_timeout (uma página
# do dashboard dispara ~9 GETs em paralelo). Passado o intervalo, tenta de novo:
# a API se recupera sozinha quando o banco volta.
COOLDOWN_FALHA_SEG = 5.0
_MSG_COOLDOWN = "banco do ENADE-Time indisponível (nova tentativa em instantes)"

_pool: ThreadedConnectionPool | None = None
_lock = threading.Lock()
_falha_ate = 0.0


def init_pool(settings: Settings) -> None:
    global _pool
    if _pool is not None:
        return
    if settings.enade_time_db_url:
        _pool = ThreadedConnectionPool(
            settings.pool_minconn,
            settings.pool_maxconn,
            dsn=settings.enade_time_db_url,
            connect_timeout=settings.db_connect_timeout,
        )
        return
    _pool = ThreadedConnectionPool(
        minconn=settings.pool_minconn,
        maxconn=settings.pool_maxconn,
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        connect_timeout=settings.db_connect_timeout,
    )


def close_pool() -> None:
    global _pool, _falha_ate
    with _lock:
        pool, _pool = _pool, None
        _falha_ate = 0.0
    if pool is not None:
        pool.closeall()


def registrar_falha() -> None:
    """Marca o banco como fora do ar e descarta o pool.

    Chamado quando a conexão falha ou morre: depois de uma queda do Postgres
    todas as conexões ociosas do pool estão mortas, e tentar reaproveitá-las
    (ou reconectar uma a uma, já que o pool serializa as tentativas) faria cada
    requisição esperar o timeout. A próxima tentativa, após o cooldown, recria
    o pool do zero.
    """
    global _pool, _falha_ate
    with _lock:
        pool, _pool = _pool, None
        _falha_ate = time.monotonic() + COOLDOWN_FALHA_SEG
    if pool is not None:
        try:
            pool.closeall()
        except Exception:  # noqa: BLE001 — o pool já está inutilizável
            pass


def _em_cooldown() -> bool:
    return time.monotonic() < _falha_ate


def get_pool() -> ThreadedConnectionPool:
    """Pool preguiçoso: criado na primeira requisição, sem depender de lifespan.

    Assim o router pode ser incluído em qualquer app (inclusive o `api_main.py`
    central) sem que a API inteira falhe ao subir quando o Postgres está fora.
    Falha de conexão levanta `psycopg2.OperationalError`, que a dependência
    `get_db_cursor` converte em HTTP 503.
    """
    global _falha_ate
    if _em_cooldown():
        raise psycopg2.OperationalError(_MSG_COOLDOWN)
    if _pool is not None:
        return _pool
    with _lock:
        if _pool is not None:
            return _pool
        if _em_cooldown():
            raise psycopg2.OperationalError(_MSG_COOLDOWN)
        try:
            init_pool(get_settings())
        except psycopg2.Error:
            _falha_ate = time.monotonic() + COOLDOWN_FALHA_SEG
            raise
        return _pool
