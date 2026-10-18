"""
api_main.py de referência com o ENADE-Time incluído — PROPOSTA ao líder, não aplicada.

É o `api_main.py` do `main` (CORS para o Next em :3000, GET e POST) mais 2 linhas para o
router do ENADE-Time. O router é autocontido: pool de conexões na primeira requisição, sem
lifespan, e 503 com CORS se o Postgres do ENADE-Time estiver fora — a API central nunca deixa
de subir por causa dele.

Dependências a acrescentar ao requirements.txt da raiz: psycopg2-binary, pydantic-settings, uvicorn.

Teste feito no repositório do ENADE-Time com um FastAPI() equivalente a este arquivo:
enade_time/tests/test_router_ecossistema.py.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from enade_time.enade_time_rotas import router as enade_time_router  # + ENADE-Time
from multi_enade.multi_enade_endpoints import router as multi_enade_router

app = FastAPI(title="EnadeX API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        # "https://seu-dominio-de-producao.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(multi_enade_router)
# app.include_router(explain_enade_router)
# app.include_router(edu_cluster_router)
app.include_router(enade_time_router)  # + ENADE-Time: 20 rotas GET em /api/enade-time/*


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=True)
