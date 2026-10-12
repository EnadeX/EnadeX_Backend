"""
Rotas do E-XplainENADE — APIRouter (não uma instância própria de FastAPI),
pronto para ser incluído num api_main.py central quando o grupo montar a API
única do ecossistema EnadeX (ver docs/EnadeX - Diagrama de pastas.pdf).

Resolve a pendência P1 da reunião de arquitetura do grupo (registrada no
DEVELOPMENT.md): diferente dos outros estudos (modelo treinado uma vez,
serializado em .joblib, API só consulta o banco), o E-XplainENADE testa uma
hipótese estatística definida pelo usuário na hora — não há nada para
pré-treinar. O endpoint POST /hipotese calcula tudo sob demanda a cada
chamada, chamando diretamente os módulos de modelagem (modules/*), os mesmos
que app.py (Streamlit) já usa.

Rodar sozinho para teste local (sem esperar um api_main.py central):
    python e_xplainenade_rotas.py
"""
import math
import uuid
from typing import Any, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config.variable_map import CURSO_OPTS, IES_OPTS, X_CATEGORIAS, X_OPTS, Y_OPTS
from modules import loader
from modules.explainability import compute_shap, get_shap_summary
from modules.hypothesis import build_hypothesis
from modules.interpretation import (
    interpretar_modelo, interpretar_residuos, interpretar_shap, interpretar_vif, label,
)
from modules.modeling import fit_ols, get_coefficients_table, get_model_metrics
from modules.multicollinearity import compute_vif
from modules.report import generate_report
from modules.residuals import get_qqplot_data, get_residuals_plot_data, run_diagnostics

router = APIRouter(prefix="/api/e-xplainenade", tags=["E-XplainENADE"])


class HipoteseRequest(BaseModel):
    y: str = Field(min_length=1)
    x_vars: List[str] = Field(min_length=1)
    interactions: List[Tuple[str, str]] = []
    grupos: Optional[List[int]] = None
    ies_filter: Optional[List[int]] = None


def _clean_nans(obj: Any) -> Any:
    """Troca NaN/Infinity por None recursivamente, para gerar JSON estritamente válido."""
    if isinstance(obj, dict):
        return {k: _clean_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nans(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _computar(req: HipoteseRequest) -> dict:
    """
    Mesma sequência que app.py já executa (build_hypothesis -> fit_ols ->
    métricas/VIF/resíduos/SHAP), reaproveitada pelos endpoints /hipotese e
    /relatorio para não duplicar a orquestração duas vezes nesta API.
    """
    try:
        df = loader.get_dataset_from_supabase(grupos=req.grupos, ies_filter=req.ies_filter)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        hyp = build_hypothesis(req.y, req.x_vars, req.interactions, df)
        result = fit_ols(hyp, df)
        metrics = get_model_metrics(result)
        coef_table = get_coefficients_table(result)
        vif_table = compute_vif(df, req.x_vars, formula=hyp.to_formula())
        diag = run_diagnostics(result)
        shap_vals, feat_names = compute_shap(result, df, req.x_vars)
        shap_sum = get_shap_summary(shap_vals, feat_names)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")

    return {
        "hyp": hyp, "result": result, "metrics": metrics,
        "coef_table": coef_table, "vif_table": vif_table, "diag": diag,
        "shap_sum": shap_sum, "y_label": label(req.y),
    }


@router.get("/opcoes")
def opcoes():
    """Opções de Y/X/curso/IES para o frontend montar o formulário de hipótese."""
    return {
        "y": Y_OPTS,
        "x": X_OPTS,
        "x_categorias": X_CATEGORIAS,
        "curso": CURSO_OPTS,
        "ies": IES_OPTS,
    }


@router.get("/dataset/resumo")
def dataset_resumo(
    grupos: Optional[List[int]] = Query(None),
    ies: Optional[List[int]] = Query(None),
):
    """Métricas resumidas da base agregada (equivalente à Etapa 1 do Streamlit)."""
    try:
        df = loader.get_dataset_from_supabase(grupos=grupos, ies_filter=ies)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    total_alunos = int(df["QT_ALUNOS"].sum()) if "QT_ALUNOS" in df.columns else None
    nt_ger = df["NT_GER"].dropna() if "NT_GER" in df.columns else None
    return _clean_nans({
        "n_cursos": len(df),
        "n_estudantes_representados": total_alunos,
        "media_nota_geral": float(nt_ger.mean()) if nt_ger is not None and len(nt_ger) else None,
        "desvio_padrao_nota_geral": float(nt_ger.std()) if nt_ger is not None and len(nt_ger) > 1 else None,
    })


class RefreshRequest(BaseModel):
    grupos: Optional[List[int]] = None


@router.post("/dataset/refresh")
def dataset_refresh(req: RefreshRequest):
    """Força uma nova consulta ao Supabase, ignorando o cache em memória."""
    try:
        df = loader.get_dataset_from_supabase(grupos=req.grupos, force_refresh=True)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"n_cursos": len(df)}


@router.post("/hipotese")
def hipotese(req: HipoteseRequest):
    """
    Calcula uma hipótese sob demanda (WLS -> VIF -> resíduos -> SHAP) e devolve
    tudo em JSON. É o endpoint que resolve a pendência P1: não há modelo
    treinado para servir — cada chamada é um cálculo novo.
    """
    c = _computar(req)
    resp = {
        "formula": c["hyp"].to_formula(),
        "y_label": c["y_label"],
        "model_metrics": c["metrics"],
        "coef_table": c["coef_table"].to_dict(orient="records"),
        "vif_table": c["vif_table"].to_dict(orient="records"),
        "residuals_diag": c["diag"],
        "shap_summary": c["shap_sum"].to_dict(orient="records"),
        "residuals_plot": get_residuals_plot_data(c["result"]).to_dict(orient="records"),
        "qqplot": get_qqplot_data(c["result"]).to_dict(orient="records"),
        "interpretacao_modelo": interpretar_modelo(c["coef_table"], c["metrics"], c["y_label"]),
        "interpretacao_vif": interpretar_vif(c["vif_table"])[1],
        "interpretacao_residuos": interpretar_residuos(c["diag"]),
        "interpretacao_shap": interpretar_shap(c["shap_sum"], c["y_label"]),
    }
    return _clean_nans(resp)


@router.post("/relatorio")
def relatorio(req: HipoteseRequest):
    """Mesmo cálculo de /hipotese, devolvendo o PDF gerado por modules/report.py."""
    c = _computar(req)
    exec_id = str(uuid.uuid4())

    session = {
        "exec_id": exec_id,
        "config": {
            "exec_id": exec_id,
            "seed": 42,
            "fonte_dados": "Supabase (tbl_arq1_2021 ... tbl_arq29_2021, agregado por CO_CURSO)",
            "y": req.y,
            "x_vars": req.x_vars,
            "interactions": [list(par) for par in req.interactions],
            "formula": c["hyp"].to_formula(),
            "filtros": {"grupos": req.grupos, "ies_filter": req.ies_filter},
        },
        "formula": c["hyp"].to_formula(),
        "y_label": c["y_label"],
        "model_metrics": c["metrics"],
        "coef_table": c["coef_table"],
        "vif_table": c["vif_table"],
        "residuals_diag": c["diag"],
        "shap_summary": c["shap_sum"],
        "interpretacao_modelo": interpretar_modelo(c["coef_table"], c["metrics"], c["y_label"]),
        "interpretacao_vif": interpretar_vif(c["vif_table"])[1],
        "interpretacao_residuos": interpretar_residuos(c["diag"]),
        "interpretacao_shap": interpretar_shap(c["shap_sum"], c["y_label"]),
        "plot_data": get_residuals_plot_data(c["result"]),
    }

    path = generate_report(session=session, filename=f"relatorio_api_{exec_id[:8]}.pdf")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


if __name__ == "__main__":
    import uvicorn
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        # A primeira consulta ao Supabase é a mais cara (13 tabelas paginadas,
        # ~10s mesmo em paralelo — ver modules/etl.py). Aquecendo no startup,
        # o primeiro request de um usuário real não paga esse custo.
        from modules import loader
        try:
            loader.get_dataset_from_supabase()
        except RuntimeError:
            pass  # tabelas podem não estar prontas ainda — não impede o boot
        yield

    app = FastAPI(title="E-XplainENADE", lifespan=_lifespan)

    # CORS: sem isso, qualquer frontend rodando em outra origem (localhost:3000,
    # domínio de produção, etc.) tem as chamadas bloqueadas pelo navegador.
    # "*" é só para teste local — quando o frontend real existir, restringir
    # allow_origins à(s) origem(ns) dele. O mesmo precisa ser configurado no
    # api_main.py central quando ele existir (middleware é do FastAPI(), não
    # do APIRouter — incluir este router ali não herda esta configuração).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=8003)
