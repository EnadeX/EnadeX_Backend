from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
# app.include_router(enade_time_router)

@app.get("/api/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=True)