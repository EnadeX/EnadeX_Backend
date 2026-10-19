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
import hmac
import logging
import math
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, List, Optional, Tuple

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from config.variable_map import CURSO_OPTS, IES_OPTS, X_CATEGORIAS, X_OPTS, Y_OPTS
from modules import etl, loader
from modules.explainability import compute_shap, get_shap_summary
from modules.hypothesis import avisos_amostra, build_hypothesis, center_for_interactions
from modules.interpretation import (
    interpretar_modelo, interpretar_ponderacao, interpretar_residuos,
    interpretar_sensibilidade, interpretar_shap, interpretar_vif, label,
)
from modules.modeling import (
    COV_TYPE_ROBUSTO, fit_variants, get_coefficients_table, get_comparison_table,
    get_model_metrics,
)
from modules.multicollinearity import compute_vif
from modules.report import generate_report
from modules.reprodutibilidade import descrever_aleatoriedade, hash_dataframe, versoes
from modules.residuals import (
    diagnose_weighting, get_qqplot_data, get_residuals_plot_data, run_diagnostics,
)

router = APIRouter(prefix="/api/e-xplainenade", tags=["E-XplainENADE"])
logger = logging.getLogger("e_xplainenade")

# Variável de ambiente (ou .env) que habilita POST /dataset/refresh. Sem ela o endpoint fica
# desligado: ele força as 13 consultas ao Supabase (~10 s) e, aberto, qualquer visitante poderia
# repeti-las à vontade.
_TOKEN_REFRESH_ENV = "EXPLAINENADE_REFRESH_TOKEN"


class HipoteseRequest(BaseModel):
    y: str = Field(min_length=1)
    x_vars: List[str] = Field(min_length=1)
    interactions: List[Tuple[str, str]] = []
    grupos: Optional[List[int]] = None
    ies_filter: Optional[List[int]] = None
    # Corte opcional de nº mínimo de presentes por curso (sem corte por padrão).
    min_alunos: Optional[int] = Field(default=None, ge=1)


def _clean_nans(obj: Any) -> Any:
    """Troca NaN/Infinity por None recursivamente, para gerar JSON estritamente válido."""
    if isinstance(obj, dict):
        return {k: _clean_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nans(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


# Valores aceitos de curso (CO_GRUPO) e de tipo de IES (TP_CATEGAD_BIN): os mesmos de /opcoes.
_GRUPOS_VALIDOS = sorted({g for v in CURSO_OPTS.values() if v for g in v})
_IES_VALIDOS = sorted({g for v in IES_OPTS.values() if v for g in v})


def _validar_recorte(grupos: Optional[List[int]], ies: Optional[List[int]]) -> None:
    """
    Recusa recorte inválido com 400 ANTES de consultar o Supabase. Sem isso, um `grupos`
    inexistente (ex: 9999) fazia as 13 consultas (~10 s) e voltava 503 "tabelas não
    populadas" — status e mensagem errados, e custo a cada tentativa.
    """
    ruins = [g for g in (grupos or []) if g not in _GRUPOS_VALIDOS]
    if ruins:
        raise HTTPException(status_code=400, detail=(
            f"Curso(s) inválido(s): {ruins}. Valores aceitos (CO_GRUPO): {_GRUPOS_VALIDOS} "
            f"— 4004 = Ciência da Computação, 4006 = Sistemas de Informação."))
    ruins = [g for g in (ies or []) if g not in _IES_VALIDOS]
    if ruins:
        raise HTTPException(status_code=400, detail=(
            f"Tipo(s) de IES inválido(s): {ruins}. Valores aceitos: {_IES_VALIDOS} "
            f"— 0 = Pública, 1 = Privada."))


def _erro_interno(acao: str) -> str:
    """
    Registra o traceback completo no log do servidor e devolve ao cliente só uma mensagem
    genérica com uma referência. Antes a resposta trazia `TipoDaExcecao: mensagem`, que expõe
    detalhes internos e não ajuda o usuário. Chamar DENTRO de um `except`.
    """
    ref = uuid.uuid4().hex[:8]
    logger.exception("[ref %s] falha ao %s", ref, acao)
    return f"Erro interno ao {acao} (ref. {ref}). O detalhe técnico está no log do servidor."


def _autorizar_refresh(token: Optional[str]) -> None:
    from modules.supabase_client import _ensure_env_loaded  # lê o .env da raiz do EnadeX

    _ensure_env_loaded()
    esperado = os.getenv(_TOKEN_REFRESH_ENV)
    if not esperado:
        raise HTTPException(status_code=403, detail=(
            f"Atualização manual da base desabilitada: defina {_TOKEN_REFRESH_ENV} no servidor "
            f"(ou no .env) e envie o mesmo valor no cabeçalho X-Refresh-Token."))
    if not token or not hmac.compare_digest(token.encode("utf-8"), esperado.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Token de atualização inválido.")


def _computar(req: HipoteseRequest) -> dict:
    """
    Mesma sequência que app.py já executa (build_hypothesis -> ajuste ->
    métricas/VIF/resíduos/SHAP), reaproveitada pelos endpoints /hipotese e
    /relatorio para não duplicar a orquestração duas vezes nesta API.

    Desde 2026-10-14 (ver DEVELOPMENT.md): as variáveis de interação são
    centradas antes do ajuste, e o WLS principal vem acompanhado do OLS sem
    pesos e das versões com erros-padrão robustos (análise de sensibilidade).

    Desde 2026-10-18 (F1): recorte e hipótese são validados ANTES da consulta ao Supabase
    (erro de entrada = 400 imediato, sem as 13 consultas), e a hipótese usada daí em diante é a
    NORMALIZADA (variáveis e interações sem repetição), não o que veio no corpo do pedido.
    """
    _validar_recorte(req.grupos, req.ies_filter)
    try:
        hyp0 = build_hypothesis(req.y, req.x_vars, req.interactions)  # só valida/normaliza
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        df = loader.get_dataset_from_supabase(
            grupos=req.grupos, ies_filter=req.ies_filter, min_alunos=req.min_alunos,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    funil = df.attrs.get("funil", {})

    try:
        hyp = build_hypothesis(hyp0.y, hyp0.x_vars, hyp0.interactions, df)
        hyp.avisos = hyp0.avisos
        avisos = hyp.avisos + avisos_amostra(hyp, df)
        df_fit, medias_centragem = center_for_interactions(hyp, df)
        variants = fit_variants(hyp, df_fit, cov_type=COV_TYPE_ROBUSTO)
        result = variants["wls"]
        metrics = get_model_metrics(result)
        coef_table = get_coefficients_table(result, robust_result=variants["wls_robust"])
        comparison_table = get_comparison_table(variants)
        vif_table = compute_vif(df_fit, hyp.x_vars, formula=hyp.to_formula())
        diag = run_diagnostics(result)
        diag_ols = diagnose_weighting(variants["ols"], df_fit)
        shap_vals, feat_names = compute_shap(result, df_fit, hyp.x_vars)
        shap_sum = get_shap_summary(shap_vals, feat_names)
    except ValueError as e:  # entrada inválida ou colinearidade perfeita (modules/modeling.py)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail=_erro_interno("calcular a hipótese"))

    reprodutibilidade = {
        "fonte_dados": _fonte_dados(),
        "filtros": {
            "grupos": req.grupos, "ies_filter": req.ies_filter, "min_alunos": req.min_alunos,
        },
        "funil_cursos": funil,
        "n_cursos_base": len(df),
        "n_obs_modelo": metrics["n_obs"],
        "hash_base_sha256": hash_dataframe(df_fit, hyp.variables() + ["QT_ALUNOS"]),
        "cov_type": COV_TYPE_ROBUSTO,
        "medias_centragem": medias_centragem,
        "aleatoriedade": descrever_aleatoriedade(metrics["n_obs"])
                         or "não aplicável (nenhuma etapa estocástica)",
        "versoes": versoes(),
    }

    return {
        "hyp": hyp, "result": result, "metrics": metrics,
        "coef_table": coef_table, "comparison_table": comparison_table,
        "vif_table": vif_table, "diag": diag, "diag_ols": diag_ols,
        "shap_sum": shap_sum, "y_label": label(hyp.y), "avisos": avisos,
        "medias_centragem": medias_centragem, "reprodutibilidade": reprodutibilidade,
    }


def _fonte_dados() -> str:
    tabelas = ", ".join(etl.table_name(n) for n in etl.ARQUIVOS_USADOS)
    return f"Supabase ({tabelas}; agregado por CO_CURSO)"


def _interpretacoes(c: dict) -> dict:
    return {
        "interpretacao_modelo": interpretar_modelo(
            c["coef_table"], c["metrics"], c["y_label"], c["medias_centragem"],
        ),
        "interpretacao_vif": interpretar_vif(c["vif_table"])[1],
        "interpretacao_residuos": interpretar_residuos(c["diag"]),
        "interpretacao_shap": interpretar_shap(c["shap_sum"], c["y_label"]),
        "interpretacao_sensibilidade": interpretar_sensibilidade(
            c["comparison_table"], COV_TYPE_ROBUSTO,
        ),
        "interpretacao_ponderacao": interpretar_ponderacao(c["diag_ols"]),
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
    min_alunos: Optional[int] = Query(None, ge=1),
):
    """Métricas resumidas da base agregada (equivalente à Etapa 1 do Streamlit)."""
    _validar_recorte(grupos, ies)
    try:
        df = loader.get_dataset_from_supabase(
            grupos=grupos, ies_filter=ies, min_alunos=min_alunos,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    total_alunos = int(df["QT_ALUNOS"].sum()) if "QT_ALUNOS" in df.columns else None
    nt_ger = df["NT_GER"].dropna() if "NT_GER" in df.columns else None
    funil = df.attrs.get("funil", {})
    return _clean_nans({
        "n_cursos": len(df),
        "n_cursos_excluidos": funil.get("cursos_excluidos_categad", 0),
        "motivo_exclusao": funil.get("motivo_exclusao_categad"),
        "funil_cursos": funil,
        "n_estudantes_representados": total_alunos,
        "media_nota_geral": float(nt_ger.mean()) if nt_ger is not None and len(nt_ger) else None,
        "desvio_padrao_nota_geral": float(nt_ger.std()) if nt_ger is not None and len(nt_ger) > 1 else None,
    })


class RefreshRequest(BaseModel):
    grupos: Optional[List[int]] = None


@router.post("/dataset/refresh")
def dataset_refresh(req: RefreshRequest, x_refresh_token: Optional[str] = Header(default=None)):
    """
    Força uma nova consulta ao Supabase, ignorando o cache em memória. Exige o cabeçalho
    X-Refresh-Token igual a EXPLAINENADE_REFRESH_TOKEN (desligado se a variável não existir).
    """
    _autorizar_refresh(x_refresh_token)
    _validar_recorte(req.grupos, None)
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
        "comparison_table": c["comparison_table"].to_dict(orient="records"),
        "cov_type": COV_TYPE_ROBUSTO,
        "vif_table": c["vif_table"].to_dict(orient="records"),
        "residuals_diag": c["diag"],
        "diagnostics_ols": c["diag_ols"],
        "shap_summary": c["shap_sum"].to_dict(orient="records"),
        "residuals_plot": get_residuals_plot_data(c["result"]).to_dict(orient="records"),
        "qqplot": get_qqplot_data(c["result"]).to_dict(orient="records"),
        "medias_centragem": c["medias_centragem"],
        "reprodutibilidade": c["reprodutibilidade"],
        # Avisos que NÃO bloqueiam: normalização da hipótese (repetições removidas) e amostra
        # pequena pela regra de Green (1991). Lista vazia = nada a avisar.
        "avisos": c["avisos"],
        **_interpretacoes(c),
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
            "y": c["hyp"].y,
            "x_vars": c["hyp"].x_vars,
            "interactions": [list(par) for par in c["hyp"].interactions],
            "formula": c["hyp"].to_formula(),
            "avisos": c["avisos"],
            **c["reprodutibilidade"],
        },
        "formula": c["hyp"].to_formula(),
        "y_label": c["y_label"],
        "model_metrics": c["metrics"],
        "coef_table": c["coef_table"],
        "comparison_table": c["comparison_table"],
        "vif_table": c["vif_table"],
        "residuals_diag": c["diag"],
        "diagnostics_ols": c["diag_ols"],
        "shap_summary": c["shap_sum"],
        "avisos": c["avisos"],
        "plot_data": get_residuals_plot_data(c["result"]),
        **_interpretacoes(c),
    }

    # PDF numa pasta temporária, apagada depois que a resposta é enviada (F3, 2026-10-19):
    # antes cada /relatorio deixava um arquivo para sempre em outputs/ (56 PDFs, 9 MB).
    pasta = Path(tempfile.mkdtemp(prefix="e_xplainenade_"))
    try:
        path = generate_report(session=session, filename=f"relatorio_api_{exec_id[:8]}.pdf",
                               output_dir=pasta)
    except Exception:
        shutil.rmtree(pasta, ignore_errors=True)
        raise HTTPException(status_code=500, detail=_erro_interno("gerar o relatório PDF"))
    return FileResponse(path, media_type="application/pdf", filename=path.name,
                        background=BackgroundTask(shutil.rmtree, pasta, ignore_errors=True))


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
        # Sem isto o navegador esconde o Content-Disposition do /relatorio e o
        # frontend baixa todo PDF com o nome genérico, perdendo o Exec-ID no nome.
        expose_headers=["Content-Disposition"],
    )

    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=8003)
