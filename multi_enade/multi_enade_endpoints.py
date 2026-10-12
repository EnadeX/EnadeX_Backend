import os

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from util.util_db import consultar_dados, credenciais_banco
from multi_enade.modelos.mdl_regressao.modelo_regressao import multi_enade_modelo_regressao
from multi_enade.modelos.mdl_clusters.modelo_clusters import multi_enade_modelo_clusters, nomear_clusters
from multi_enade.modelos.mdl_associacao.modelo_associacao import multi_enade_modelo_associacao
from multi_enade.refinamento_dados.util_etl import obter_cursos_recorte
from multi_enade.refinamento_dados.refino_arq2 import main_refino_arq2
from multi_enade.refinamento_dados.refino_arq3 import main_refino_arq3
from multi_enade.refinamento_dados.refino_arq4 import main_refino_arq4
from multi_enade.refinamento_dados.refino_arq10 import main_refino_arq10
from multi_enade.refinamento_dados.refino_arq14 import main_refino_arq14
from multi_enade.refinamento_dados.refino_arq15 import main_refino_arq15
from multi_enade.refinamento_dados.refino_arq16 import main_refino_arq16
from multi_enade.refinamento_dados.refino_arq17 import main_refino_arq17
from multi_enade.refinamento_dados.refino_arq18 import main_refino_arq18
from multi_enade.refinamento_dados.refino_arq19 import main_refino_arq19
from multi_enade.refinamento_dados.refino_arq21 import main_refino_arq21
from multi_enade.refinamento_dados.refino_arq25 import main_refino_arq25
from multi_enade.refinamento_dados.refino_arq30 import main_refino_arq30

router = APIRouter(prefix="/api/multienade", tags=["MultiENADE"])

_PASTA_DADOS_BRUTOS_PADRAO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_brutos")


def _base_dados_brutos() -> str:
    """Pasta onde estão os .txt brutos do INEP. Configurável via
    ENADE_DADOS_BRUTOS; por padrão, multi_enade/dados_brutos/."""
    return os.environ.get("ENADE_DADOS_BRUTOS", _PASTA_DADOS_BRUTOS_PADRAO)


def _credenciais_ou_erro() -> dict:
    """Valida as credenciais do Supabase antes de agendar o reprocessamento em
    background — assim um erro de configuração vira um 503 imediato, em vez de
    falhar silenciosamente dentro da BackgroundTask."""
    dic_credenciais = credenciais_banco()
    if not dic_credenciais.get("key_banco") or "None" in dic_credenciais.get("url_banco", ""):
        raise HTTPException(status_code=503, detail="Credenciais do Supabase não configuradas.")
    return dic_credenciais

@router.get("/relatorio-regressao")
def multi_enade_relatorio_regressao():
    try:
        dic_credenciais = credenciais_banco()
        df_regressao = consultar_dados(
            "tbl_multi_enade_regressao",
            dic_credenciais["url_banco"],
            dic_credenciais["key_banco"],
        )
        return df_regressao.to_dict(orient="records")
    except Exception as e:
        return {"erro": f"Falha ao consultar regressão: {str(e)}"}

@router.get("/relatorio-cluster")
def multi_enade_relatorio_cluster():
    """
    tbl_multi_enade_clusters não guarda um nome legível por cluster (só
    Cluster_ID, que é um índice arbitrário do KMeans). O nome é recalculado
    aqui a partir do NT_GER médio de cada grupo, sem precisar de coluna nova
    no Supabase — ver modelo_clusters.nomear_clusters.
    """
    try:
        dic_credenciais = credenciais_banco()
        df_cluster = consultar_dados(
            "tbl_multi_enade_clusters",
            dic_credenciais["url_banco"],
            dic_credenciais["key_banco"],
        )
        if not df_cluster.empty and "Cluster_ID" in df_cluster.columns and "NT_GER" in df_cluster.columns:
            df_cluster["NT_GER"] = pd.to_numeric(df_cluster["NT_GER"], errors="coerce")
            perfil = df_cluster.groupby("Cluster_ID")["NT_GER"].mean().to_frame()
            nomes = nomear_clusters(perfil)
            df_cluster["Cluster_Nome"] = df_cluster["Cluster_ID"].map(nomes)
        return df_cluster.to_dict(orient="records")
    except Exception as e:
        return {"erro": f"Falha ao consultar clusters: {str(e)}"}

@router.get("/relatorio-associacao")
def multi_enade_relatorio_associacao():
    try:
        dic_credenciais = credenciais_banco()
        df_regras = consultar_dados(
            "tbl_multi_enade_associacao",
            dic_credenciais["url_banco"],
            dic_credenciais["key_banco"],
        )
        return df_regras.to_dict(orient="records")
    except Exception as e:
        return {"erro": f"Falha ao consultar associação: {str(e)}"}

@router.get("/relatorio-shap")
def multi_enade_relatorio_shap():
    """
    Endpoint para obter a importância média absoluta (SHAP) de cada feature do modelo.
    """
    try:
        dic_credenciais = credenciais_banco()
        df_shap = consultar_dados("tbl_multi_enade_shap", dic_credenciais["url_banco"], dic_credenciais["key_banco"])
        return df_shap.to_dict(orient='records')
    except Exception as e:
        return {"erro": f"Falha ao consultar SHAP: {str(e)}"}


# ========== Reprocessamento (ETL) — um endpoint por modelo ==========
# Cada modelo é independente e pode ser reprocessado individualmente, conforme
# a necessidade (ex: só os dados de regressão mudaram, não precisa recalcular
# clusters e associação). A chamada dispara o pipeline em background e retorna
# imediatamente — o processamento (minutos, dado o volume de dados do ENADE)
# não acontece dentro do ciclo de request/response.

class ReprocessarRegressaoRequest(BaseModel):
    retreinar: bool = False


class ReprocessarClustersRequest(BaseModel):
    num_clusters: int = 3
    retreinar: bool = False


class ReprocessarAssociacaoRequest(BaseModel):
    # Validados em EXPLORACAO_MODELO_ASSOCIACAO.md: suporte 0,25/confiança 0,7
    # nunca encontra nenhuma regra ligada a desempenho (matematicamente
    # impossível); 0,03/0,5 foi a configuração validada por repetição em
    # duas amostras independentes.
    suporte_minimo: float = 0.03
    confianca_minima: float = 0.5


@router.post("/reprocessar/regressao")
def multi_enade_reprocessar_regressao(req: ReprocessarRegressaoRequest, background_tasks: BackgroundTasks):
    dic_credenciais = _credenciais_ou_erro()
    background_tasks.add_task(
        multi_enade_modelo_regressao,
        dic_credenciais["url_banco"],
        dic_credenciais["key_banco"],
        req.retreinar,
    )
    return {"status": "iniciado", "modelo": "regressao", "retreinar": req.retreinar}


@router.post("/reprocessar/clusters")
def multi_enade_reprocessar_clusters(req: ReprocessarClustersRequest, background_tasks: BackgroundTasks):
    dic_credenciais = _credenciais_ou_erro()
    background_tasks.add_task(
        multi_enade_modelo_clusters,
        req.num_clusters,
        dic_credenciais["url_banco"],
        dic_credenciais["key_banco"],
        req.retreinar,
    )
    return {"status": "iniciado", "modelo": "clusters", "num_clusters": req.num_clusters, "retreinar": req.retreinar}


@router.post("/reprocessar/associacao")
def multi_enade_reprocessar_associacao(req: ReprocessarAssociacaoRequest, background_tasks: BackgroundTasks):
    dic_credenciais = _credenciais_ou_erro()
    background_tasks.add_task(
        multi_enade_modelo_associacao,
        dic_credenciais["url_banco"],
        dic_credenciais["key_banco"],
        req.suporte_minimo,
        req.confianca_minima,
    )
    return {"status": "iniciado", "modelo": "associacao"}


# ========== Reprocessamento desde as fontes brutas (.txt do INEP) ==========
# Todas as fontes dependem do mesmo recorte de cursos, calculado a partir do
# arq1 — por isso ficam atrás de um único endpoint, em vez de um por arquivo
# como os modelos: o arq1 é lido e filtrado uma única vez e reaproveitado por
# todas, evitando reler o mesmo .txt grande repetidamente.
#
# Esta lista precisa bater com as tabelas que modelo_regressao.py/
# modelo_clusters.py/modelo_associacao.py realmente consultam — revisar
# junto se algum modelo passar a usar (ou parar de usar) uma fonte nova.
# arq29 (QE_I23, horas de estudo) não está aqui porque nenhum modelo em
# produção usa mais essa variável (saiu na seleção de variáveis da
# regressão — ver EXPLORACAO_MODELO_REGRESSAO.md); o script
# refino_arq29.py continua disponível caso volte a ser usada.

def _reprocessar_fontes_brutas(url_conexao: str, key_conexao: str) -> dict:
    base_dados = _base_dados_brutos()
    caminho_arq_1 = os.path.join(base_dados, "microdados2021_arq1.txt")
    cursos_recorte = obter_cursos_recorte(caminho_arq_1)

    etapas = {
        "arq2": (main_refino_arq2, os.path.join(base_dados, "microdados2021_arq2.txt")),
        "arq3": (main_refino_arq3, os.path.join(base_dados, "microdados2021_arq3.txt")),
        "arq4": (main_refino_arq4, os.path.join(base_dados, "microdados2021_arq4.txt")),
        "arq10": (main_refino_arq10, os.path.join(base_dados, "microdados2021_arq10.txt")),
        "arq14": (main_refino_arq14, os.path.join(base_dados, "microdados2021_arq14.txt")),
        "arq15": (main_refino_arq15, os.path.join(base_dados, "microdados2021_arq15.txt")),
        "arq16": (main_refino_arq16, os.path.join(base_dados, "microdados2021_arq16.txt")),
        "arq17": (main_refino_arq17, os.path.join(base_dados, "microdados2021_arq17.txt")),
        "arq18": (main_refino_arq18, os.path.join(base_dados, "microdados2021_arq18.txt")),
        "arq19": (main_refino_arq19, os.path.join(base_dados, "microdados2021_arq19.txt")),
        "arq21": (main_refino_arq21, os.path.join(base_dados, "microdados2021_arq21.txt")),
        "arq25": (main_refino_arq25, os.path.join(base_dados, "microdados2021_arq25.txt")),
        "arq30": (main_refino_arq30, os.path.join(base_dados, "microdados2021_arq30.txt")),
    }

    relatorio = {}
    for nome, (funcao, caminho_arq) in etapas.items():
        try:
            df = funcao(caminho_arq, cursos_recorte, url_conexao, key_conexao)
            relatorio[nome] = f"ok ({len(df)} linhas)"
            print(f"[reprocessar/fontes] {nome}: ok ({len(df)} linhas)")
        except Exception as e:
            relatorio[nome] = f"erro: {e}"
            print(f"[reprocessar/fontes] {nome}: erro: {e}")
    return relatorio


@router.post("/reprocessar/fontes")
def multi_enade_reprocessar_fontes(background_tasks: BackgroundTasks):
    dic_credenciais = _credenciais_ou_erro()
    background_tasks.add_task(
        _reprocessar_fontes_brutas,
        dic_credenciais["url_banco"],
        dic_credenciais["key_banco"],
    )
    return {
        "status": "iniciado",
        "etapa": "fontes",
        "fontes": ["arq2", "arq3", "arq4", "arq10", "arq14", "arq15", "arq16",
                   "arq17", "arq18", "arq19", "arq21", "arq25", "arq30"],
    }