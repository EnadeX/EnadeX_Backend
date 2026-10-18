from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from educluster.educluster_config import (
    CORS_ORIGENS,
    DIMENSOES_ARQ4,
    ESPACOS_PERFIL_DESEMPENHO,
    K_MAXIMO,
    K_MINIMO,
    N_MINIMO_RESPONDENTES,
    ORIGEM_PADRAO,
    ROTULOS_DIMENSAO,
)
from educluster.educluster_interpretacao import descrever
from educluster.modelos.mdl_curso_percepcao.modelo_curso_percepcao import (
    aplicar_clusters,
    avaliar_clusters,
    clusterizar_em_memoria,
    comparar_estabilidade_por_k,
    identificar_discrepantes,
    medir_estabilidade,
    perfilar_clusters,
    preparar_dados_curso_percepcao,
)
from educluster.modelos.mdl_calibracao_prova.modelo_calibracao_prova import (
    classificar_calibracao,
    medir_calibracao,
    perfilar_calibracao,
    preparar_dados_calibracao,
)
from educluster.modelos.mdl_comparacao_tradicional.modelo_comparacao_tradicional import (
    educluster_modelo_comparacao_tradicional,
)
from educluster.modelos.mdl_dimensao_desempenho.modelo_dimensao_desempenho import (
    educluster_modelo_dimensao_desempenho,
)
from educluster.modelos.mdl_situacao_discursiva.modelo_situacao_discursiva import (
    classificar_perfis_discursivos,
    distribuir_situacoes,
    medir_situacao,
    perfilar_situacao,
    preparar_dados_situacao,
)
from educluster.modelos.mdl_perfil_desempenho.modelo_perfil_desempenho import (
    amostrar_para_plotagem,
    aplicar_perfil,
    avaliar_perfil,
    perfilar_desempenho,
    preparar_dados_perfil_desempenho,
)

VERSAO = "0.2.0"

router = APIRouter(prefix="/api/educluster")

_cache_cursos = {}
_cache_estudantes = {}
_cache_calibracao = {}
_cache_discursiva = {}

ORIGEM = Query(ORIGEM_PADRAO, pattern="^(local|supabase)$", description="Fonte dos dados")
N_MINIMO = Query(N_MINIMO_RESPONDENTES, ge=1, le=500, description="Respondentes minimos por curso")
K_OPCIONAL = Query(None, ge=K_MINIMO, le=K_MAXIMO, description="Reclusteriza em memoria com este k")


def _traduzir_erro(erro: Exception):
    if isinstance(erro, (ModuleNotFoundError, FileNotFoundError, ConnectionError)):
        raise HTTPException(
            status_code=503,
            detail=(
                f"Fonte de dados indisponivel: {erro}. "
                "Para origem=supabase instale as dependencias e configure o .env na raiz do repositorio EnadeX "
                "(SUPABASE_URL e SUPABASE_KEY). Para origem=local confira a pasta microdados/."
            ),
        )
    raise HTTPException(status_code=500, detail=f"{type(erro).__name__}: {erro}")


def obter_cursos(origem: str, n_minimo: int, k: int = None):
    chave = (origem, n_minimo)
    if chave not in _cache_cursos:
        _cache_cursos[chave] = preparar_dados_curso_percepcao(origem, n_minimo)
    base = _cache_cursos[chave]
    return clusterizar_em_memoria(base, k) if k else aplicar_clusters(base)


def obter_calibracao(origem: str):
    if origem not in _cache_calibracao:
        _cache_calibracao[origem] = classificar_calibracao(preparar_dados_calibracao(origem))
    return _cache_calibracao[origem]


def obter_discursiva(origem: str):
    if origem not in _cache_discursiva:
        _cache_discursiva[origem] = classificar_perfis_discursivos(preparar_dados_situacao(origem))
    return _cache_discursiva[origem]


def obter_estudantes(origem: str, espaco: str):
    chave = (origem, espaco)
    if chave not in _cache_estudantes:
        base = preparar_dados_perfil_desempenho(origem, espaco)
        _cache_estudantes[chave] = aplicar_perfil(base, espaco)
    return _cache_estudantes[chave]


@router.get("/cursos", tags=["cursos"], summary="A6: colecao de cursos com cluster e coordenadas PCA")
def educluster_cursos(
    origem: str = ORIGEM,
    n_minimo: int = N_MINIMO,
    k: int = K_OPCIONAL,
    area: str = Query(None, description="Filtra por codigo de area, exemplo A07"),
    cluster: int = Query(None, ge=0, description="Filtra por cluster"),
):
    try:
        df = obter_cursos(origem, n_minimo, k)
        if area:
            df = df[df["area"] == area]
        if cluster is not None:
            df = df[df["Cluster_ID"] == cluster]
        return {"total": len(df), "cursos": df.reset_index().to_dict(orient="records")}
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/cursos/clusters", tags=["cursos"], summary="A6: perfil de cada cluster e metricas de validacao")
def educluster_cursos_clusters(origem: str = ORIGEM, n_minimo: int = N_MINIMO, k: int = K_OPCIONAL):
    try:
        df = obter_cursos(origem, n_minimo, k)
        return {
            "perfis": perfilar_clusters(df).reset_index().to_dict(orient="records"),
            "metricas": avaliar_clusters(df) if k is None else {"k": int(k), "modo": "reclusterizado_em_memoria"},
            "dimensoes": ROTULOS_DIMENSAO,
        }
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/cursos/discrepantes", tags=["cursos"], summary="A7: cursos que destoam dos pares da propria area")
def educluster_cursos_discrepantes(
    origem: str = ORIGEM,
    n_minimo: int = N_MINIMO,
    limiar: float = Query(1.0, ge=0.0, le=5.0, description="Tensao minima em desvios padrao"),
    quadrante: str = Query(None, pattern="^(coerente_alto|coerente_baixo|entrega_sem_reconhecimento|reconhecimento_sem_entrega)$"),
    limite: int = Query(100, ge=1, le=4000),
):
    try:
        df = identificar_discrepantes(obter_cursos(origem, n_minimo), limiar)
        if quadrante:
            df = df[df["quadrante"] == quadrante]
        return {
            "total": len(df),
            "limiar": limiar,
            "por_quadrante": df["quadrante"].value_counts().to_dict(),
            "cursos": df.head(limite).reset_index().to_dict(orient="records"),
        }
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/cursos/clusters/estabilidade", tags=["cursos"], summary="Estabilidade dos clusters por reamostragem")
def educluster_cursos_estabilidade(
    origem: str = ORIGEM,
    n_minimo: int = N_MINIMO,
    k: int = K_OPCIONAL,
    rodadas: int = Query(20, ge=5, le=100, description="Numero de reamostragens"),
):
    try:
        chave = (origem, n_minimo)
        if chave not in _cache_cursos:
            _cache_cursos[chave] = preparar_dados_curso_percepcao(origem, n_minimo)
        base = _cache_cursos[chave]
        if k:
            return medir_estabilidade(base, k, rodadas)
        return {
            "metodo": "reamostragem de 80% da base, ARI contra a particao de referencia",
            "por_k": comparar_estabilidade_por_k(base, rodadas=rodadas).to_dict(orient="records"),
        }
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/cursos/clusters/descricao", tags=["cursos"], summary="Descricao automatica dos perfis, gerada por IA no backend")
def educluster_cursos_descricao(
    origem: str = ORIGEM,
    n_minimo: int = N_MINIMO,
    k: int = K_OPCIONAL,
    forcar: bool = Query(False, description="Ignora o cache e gera novamente"),
):
    try:
        df = obter_cursos(origem, n_minimo, k)
        contexto = {
            "perfis": perfilar_clusters(df).reset_index().to_dict(orient="records"),
            "metricas": avaliar_clusters(df) if k is None else {"k": int(k)},
            "dimensoes": ROTULOS_DIMENSAO,
        }
        return descrever(contexto, tipo="cursos", forcar=forcar)
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/cursos/dimensoes-desempenho", tags=["cursos"], summary="A8: qual dimensao percebida mais se associa ao desempenho")
def educluster_dimensoes_desempenho(
    origem: str = ORIGEM,
    n_minimo: int = N_MINIMO,
    alvo: str = Query("NT_CE", pattern="^(NT_FG|NT_CE)$"),
):
    try:
        return educluster_modelo_dimensao_desempenho(origem, n_minimo, alvo)
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/estudantes/calibracao", tags=["estudantes"], summary="A3: percepcao da prova versus desempenho real")
def educluster_estudantes_calibracao(origem: str = ORIGEM):
    try:
        df = obter_calibracao(origem)
        return {
            "perfis": perfilar_calibracao(df).reset_index().to_dict(orient="records"),
            "metricas": medir_calibracao(df),
            "nota_por_dificuldade": df.groupby("dificuldade_percebida")["NT_GER"].agg(["size", "mean"]).round(2).reset_index().to_dict(orient="records"),
        }
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/estudantes/discursivas", tags=["estudantes"], summary="A4: desistencia versus erro conceitual nas discursivas")
def educluster_estudantes_discursivas(origem: str = ORIGEM):
    try:
        df = obter_discursiva(origem)
        return {
            "perfis": perfilar_situacao(df).reset_index().to_dict(orient="records"),
            "metricas": medir_situacao(df),
            "situacao_por_questao": distribuir_situacoes(df).to_dict(orient="records"),
        }
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/estudantes/clusters/descricao", tags=["estudantes"], summary="Descricao automatica dos perfis de desempenho")
def educluster_estudantes_descricao(
    origem: str = ORIGEM,
    espaco: str = Query("objetivo_discursivo", pattern="^(trio|par|objetivo_discursivo)$"),
    forcar: bool = Query(False),
):
    try:
        df = obter_estudantes(origem, espaco)
        contexto = {
            "perfis": perfilar_desempenho(df, espaco).reset_index().to_dict(orient="records"),
            "metricas": avaliar_perfil(df, espaco),
        }
        return descrever(contexto, tipo="estudantes", forcar=forcar)
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/cursos/comparacao-tradicional", tags=["cursos"], summary="Fase 6: o artefato versus o ranking por nota media")
def educluster_comparacao_tradicional(
    origem: str = ORIGEM,
    n_minimo: int = N_MINIMO,
    tolerancia: float = Query(0.5, ge=0.01, le=5.0, description="Diferenca maxima de NT_GER para considerar dois cursos gemeos"),
):
    try:
        return educluster_modelo_comparacao_tradicional(origem, n_minimo, tolerancia)
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/cursos/{co_curso}", tags=["cursos"], summary="A6: detalhe de um curso")
def educluster_curso_detalhe(co_curso: int, origem: str = ORIGEM, n_minimo: int = N_MINIMO):
    try:
        df = obter_cursos(origem, n_minimo)
    except Exception as erro:
        _traduzir_erro(erro)
    if co_curso not in df.index:
        raise HTTPException(status_code=404, detail=f"Curso {co_curso} fora da base analitica (n_minimo={n_minimo})")
    return df.loc[co_curso].to_dict()


@router.get("/estudantes/clusters", tags=["estudantes"], summary="A1: perfil de cada cluster de desempenho")
def educluster_estudantes_clusters(
    origem: str = ORIGEM,
    espaco: str = Query("objetivo_discursivo", pattern="^(trio|par|objetivo_discursivo)$"),
):
    try:
        df = obter_estudantes(origem, espaco)
        return {
            "perfis": perfilar_desempenho(df, espaco).reset_index().to_dict(orient="records"),
            "metricas": avaliar_perfil(df, espaco),
        }
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/estudantes/amostra", tags=["estudantes"], summary="A1: amostra reprodutivel para plotagem")
def educluster_estudantes_amostra(
    origem: str = ORIGEM,
    espaco: str = Query("objetivo_discursivo", pattern="^(trio|par|objetivo_discursivo)$"),
    n: int = Query(5000, ge=100, le=50000, description="Tamanho da amostra"),
):
    try:
        df = obter_estudantes(origem, espaco)
        amostra = amostrar_para_plotagem(df, n)
        return {
            "populacao": len(df),
            "amostra": len(amostra),
            "random_state": 42,
            "pontos": amostra.to_dict(orient="records"),
        }
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/espacos-desempenho", tags=["catalogo"], summary="Espacos de variaveis disponiveis para A1")
def educluster_espacos_desempenho():
    return ESPACOS_PERFIL_DESEMPENHO


@router.get("/dimensoes", tags=["catalogo"], summary="Dimensoes percebidas do arq4 e seus itens")
def educluster_dimensoes():
    return {
        sigla: {"rotulo": ROTULOS_DIMENSAO[sigla], "itens": itens, "quantidade": len(itens)}
        for sigla, itens in DIMENSOES_ARQ4.items()
    }


@router.get("/areas", tags=["catalogo"], summary="Areas de avaliacao presentes na base")
def educluster_areas(origem: str = ORIGEM, n_minimo: int = N_MINIMO):
    try:
        df = obter_cursos(origem, n_minimo)
        resumo = df.groupby("area").agg(
            cursos=("n_notas", "size"), estudantes=("n_notas", "sum"),
            NT_FG=("NT_FG", "mean"), NT_CE=("NT_CE", "mean"), ODP=("ODP", "mean"),
        ).round(2).sort_values("estudantes", ascending=False)
        return {"total": len(resumo), "areas": resumo.reset_index().to_dict(orient="records")}
    except Exception as erro:
        _traduzir_erro(erro)


@router.get("/health", tags=["catalogo"], summary="Saude da API e estado da base em memoria")
def educluster_health():
    return {
        "status": "ok",
        "modulo": "educluster",
        "versao": VERSAO,
        "origem": ORIGEM_PADRAO,
        "base_cursos_em_memoria": bool(_cache_cursos),
    }


def criar_app() -> FastAPI:
    app = FastAPI(
        title="EduCluster",
        version=VERSAO,
        description="Perfis academicos latentes no ENADE 2021. Modulo do ecossistema EnadeX.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGENS,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = criar_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
