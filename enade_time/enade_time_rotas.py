"""
Rotas do ENADE-Time no padrão do ecossistema EnadeX.

Expõe `router` — um único `APIRouter(prefix="/api/enade-time")` agregando os
quatro grupos do subprojeto (health, dim, analises, benchmark; 19 endpoints,
todos read-only) — pronto para ser incluído pelo `api_main.py` central:

    from enade_time.enade_time_rotas import router as enade_time_router
    app.include_router(enade_time_router)

Composição central: o router é autocontido. O pool psycopg2 é criado na
primeira requisição (sem lifespan) e, se o Postgres do ENADE-Time estiver fora,
as rotas respondem 503 com os cabeçalhos CORS — a API central continua de pé e
as demais rotas dela não são afetadas. Basta o import + `include_router` acima
(e `psycopg2-binary` + `pydantic-settings` no requirements da raiz).

Banco: PostgreSQL local do subprojeto (docker compose up -d postgres, dentro
de enade_time/) — configuração via enade_time/.env ou EnadeX/.env
(POSTGRES_HOST/PORT/DB/USER/PASSWORD; defaults casam com o docker-compose).

Standalone (porta 8002, sem esperar o api_main.py central):

    # da raiz do EnadeX
    python enade_time/enade_time_rotas.py
    # Swagger: http://localhost:8002/docs
    # ex.:     http://localhost:8002/api/enade-time/health
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite rodar como script de qualquer CWD e ser importado da raiz do EnadeX.
_RAIZ_ECO = Path(__file__).resolve().parents[1]
if str(_RAIZ_ECO) not in sys.path:
    sys.path.insert(0, str(_RAIZ_ECO))

from fastapi import APIRouter  # noqa: E402

from enade_time.api.routers import analises, benchmark, dimensoes, health  # noqa: E402

PORTA_STANDALONE = 8002  # 8000 = api_main · 8001 = educluster · 8002 = enade_time · 8003 = e_xplainenade

router = APIRouter(prefix="/api/enade-time", tags=["ENADE-Time"])
for _sub in (health.router, dimensoes.router, analises.router, benchmark.router):
    router.include_router(_sub)


def criar_app():
    """FastAPI standalone (porta 8002). O pool é preguiçoso; o lifespan só o fecha."""
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from enade_time.api.database import close_pool
    from enade_time.api.settings import get_settings

    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        close_pool()

    app = FastAPI(
        title="ENADE-Time Distribuído (EnadeX)",
        description="Base longitudinal ENADE 2005–2021 (Computação, Norte/Nordeste) "
                    "e benchmark de processamento paralelo — read-only.",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(criar_app(), host="0.0.0.0", port=PORTA_STANDALONE)
