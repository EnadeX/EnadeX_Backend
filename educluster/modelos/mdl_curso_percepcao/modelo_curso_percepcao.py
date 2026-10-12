import os

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from educluster.educluster_config import (
    ORIGEM_PADRAO,
    FEATURES_A6,
    K_MAXIMO,
    K_MINIMO,
    N_INIT,
    N_MINIMO_RESPONDENTES,
    RANDOM_STATE,
    ROTULOS_DIMENSAO,
)
from educluster.educluster_dados import carregar_arq3, carregar_arq4
from educluster.educluster_preparo import montar_base_curso, padronizar_por_area

DIRETORIO_MODELO = os.path.dirname(os.path.abspath(__file__))
ARQ_SCALER = "scaler_curso_percepcao.joblib"
ARQ_KMEANS = "kmeans_curso_percepcao.joblib"
ARQ_PCA = "pca_curso_percepcao.joblib"


def preparar_dados_curso_percepcao(origem: str = ORIGEM_PADRAO, n_minimo: int = N_MINIMO_RESPONDENTES) -> pd.DataFrame:
    return montar_base_curso(carregar_arq3(origem), carregar_arq4(origem), n_minimo)


def escolher_k_por_silhouette(dados_padronizados, k_minimo: int = K_MINIMO, k_maximo: int = K_MAXIMO):
    resultados = []
    for k in range(k_minimo, k_maximo + 1):
        kmeans = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=N_INIT)
        rotulos = kmeans.fit_predict(dados_padronizados)
        score = silhouette_score(dados_padronizados, rotulos, random_state=RANDOM_STATE)
        resultados.append({"k": k, "silhouette": round(float(score), 4), "inercia": round(float(kmeans.inertia_), 2)})
        print(f"[educluster]   k={k} -> silhouette {score:.4f}")

    tabela = pd.DataFrame(resultados)
    melhor_k = int(tabela.loc[tabela["silhouette"].idxmax(), "k"])
    print(f"[educluster] melhor k por silhouette: {melhor_k}")
    return melhor_k, tabela


def treinar_e_salvar_clusters(df_base: pd.DataFrame, num_clusters: int = None, diretorio_modelos: str = DIRETORIO_MODELO):
    matriz = df_base[FEATURES_A6]

    scaler = StandardScaler()
    dados_padronizados = scaler.fit_transform(matriz)

    if num_clusters is None:
        print("[educluster] buscando k automaticamente")
        num_clusters, tabela_k = escolher_k_por_silhouette(dados_padronizados)
    else:
        tabela_k = None

    kmeans = KMeans(n_clusters=num_clusters, random_state=RANDOM_STATE, n_init=N_INIT)
    kmeans.fit(dados_padronizados)

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    pca.fit(dados_padronizados)

    os.makedirs(diretorio_modelos, exist_ok=True)
    joblib.dump(scaler, os.path.join(diretorio_modelos, ARQ_SCALER))
    joblib.dump(kmeans, os.path.join(diretorio_modelos, ARQ_KMEANS))
    joblib.dump(pca, os.path.join(diretorio_modelos, ARQ_PCA))
    print(f"[educluster] modelos salvos em {diretorio_modelos}")

    if tabela_k is not None:
        tabela_k.to_csv(os.path.join(diretorio_modelos, "escolha_de_k.csv"), index=False)

    return scaler, kmeans, pca


def aplicar_clusters(df_base: pd.DataFrame, diretorio_modelos: str = DIRETORIO_MODELO) -> pd.DataFrame:
    scaler = joblib.load(os.path.join(diretorio_modelos, ARQ_SCALER))
    kmeans = joblib.load(os.path.join(diretorio_modelos, ARQ_KMEANS))
    pca = joblib.load(os.path.join(diretorio_modelos, ARQ_PCA))

    dados_padronizados = scaler.transform(df_base[FEATURES_A6])
    coordenadas = pca.transform(dados_padronizados)

    df_resultado = df_base.copy()
    df_resultado["Cluster_ID"] = kmeans.predict(dados_padronizados)
    df_resultado["PCA_X"] = coordenadas[:, 0]
    df_resultado["PCA_Y"] = coordenadas[:, 1]
    return df_resultado


def avaliar_clusters(df_resultado: pd.DataFrame, diretorio_modelos: str = DIRETORIO_MODELO) -> dict:
    scaler = joblib.load(os.path.join(diretorio_modelos, ARQ_SCALER))
    pca_completo = PCA(random_state=RANDOM_STATE)
    dados_padronizados = scaler.transform(df_resultado[FEATURES_A6])
    pca_completo.fit(dados_padronizados)

    metricas = {
        "n_cursos": int(len(df_resultado)),
        "n_estudantes": int(df_resultado["n_notas"].sum()),
        "k": int(df_resultado["Cluster_ID"].nunique()),
        "silhouette": round(float(silhouette_score(dados_padronizados, df_resultado["Cluster_ID"], random_state=RANDOM_STATE)), 4),
        "variancia_explicada_2d": round(float(pca_completo.explained_variance_ratio_[:2].sum()), 4),
        "variancia_por_componente": [round(float(v), 4) for v in pca_completo.explained_variance_ratio_],
        "ari_contra_area": round(float(adjusted_rand_score(df_resultado["area"], df_resultado["Cluster_ID"])), 4),
    }

    print("\n[educluster] METRICAS DE VALIDACAO")
    print(f"  cursos: {metricas['n_cursos']} | estudantes representados: {metricas['n_estudantes']}")
    print(f"  k: {metricas['k']} | silhouette: {metricas['silhouette']}")
    print(f"  variancia explicada em 2D: {metricas['variancia_explicada_2d']}")
    print(f"  ARI contra a area do curso: {metricas['ari_contra_area']} (perto de 0 indica que os clusters nao sao um espelho da area)")
    return metricas


def perfilar_clusters(df_resultado: pd.DataFrame) -> pd.DataFrame:
    perfil = df_resultado.groupby("Cluster_ID")[FEATURES_A6].mean().round(2)
    perfil["cursos"] = df_resultado.groupby("Cluster_ID").size()
    perfil["estudantes"] = df_resultado.groupby("Cluster_ID")["n_notas"].sum()

    print("\n[educluster] PERFIL DOS CLUSTERS")
    print(perfil.to_string())
    print("\n  legenda das dimensoes percebidas (escala 1 a 6):")
    for sigla, rotulo in ROTULOS_DIMENSAO.items():
        print(f"    {sigla}: {rotulo}")
    return perfil


def clusterizar_em_memoria(df_base: pd.DataFrame, num_clusters: int) -> pd.DataFrame:
    matriz = df_base[FEATURES_A6]
    scaler = StandardScaler()
    dados_padronizados = scaler.fit_transform(matriz)

    kmeans = KMeans(n_clusters=num_clusters, random_state=RANDOM_STATE, n_init=N_INIT)
    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    coordenadas = pca.fit_transform(dados_padronizados)

    df_resultado = df_base.copy()
    df_resultado["Cluster_ID"] = kmeans.fit_predict(dados_padronizados)
    df_resultado["PCA_X"] = coordenadas[:, 0]
    df_resultado["PCA_Y"] = coordenadas[:, 1]
    return df_resultado


def identificar_discrepantes(df_resultado: pd.DataFrame, limiar: float = 1.0) -> pd.DataFrame:
    df = padronizar_por_area(df_resultado, ["NT_FG", "NT_CE", "ODP"])
    df["desempenho_relativo"] = df[["NT_FG_z", "NT_CE_z"]].mean(axis=1)
    df["percepcao_relativa"] = df["ODP_z"]
    df["tensao"] = df["percepcao_relativa"] - df["desempenho_relativo"]

    acima_desempenho = df["desempenho_relativo"] > 0
    acima_percepcao = df["percepcao_relativa"] > 0
    df["quadrante"] = "coerente_baixo"
    df.loc[acima_desempenho & acima_percepcao, "quadrante"] = "coerente_alto"
    df.loc[acima_desempenho & ~acima_percepcao, "quadrante"] = "entrega_sem_reconhecimento"
    df.loc[~acima_desempenho & acima_percepcao, "quadrante"] = "reconhecimento_sem_entrega"

    discrepantes = df[df["tensao"].abs() >= limiar].copy()
    discrepantes = discrepantes.sort_values("tensao", ascending=False)

    print(f"\n[educluster] A7: {len(discrepantes)} cursos discrepantes de {len(df)} (limiar |tensao| >= {limiar})")
    print(discrepantes["quadrante"].value_counts().to_string())
    return discrepantes


def medir_estabilidade(df_base: pd.DataFrame, num_clusters: int, rodadas: int = 20, fracao: float = 0.8) -> dict:
    matriz = StandardScaler().fit_transform(df_base[FEATURES_A6])
    referencia = KMeans(n_clusters=num_clusters, random_state=RANDOM_STATE, n_init=N_INIT).fit_predict(matriz)

    indices = list(range(len(df_base)))
    scores = []
    for rodada in range(rodadas):
        gerador = np.random.RandomState(RANDOM_STATE + rodada)
        amostra = gerador.choice(indices, size=int(len(indices) * fracao), replace=False)
        modelo = KMeans(n_clusters=num_clusters, random_state=RANDOM_STATE, n_init=N_INIT)
        modelo.fit(matriz[amostra])
        scores.append(adjusted_rand_score(referencia, modelo.predict(matriz)))

    scores = np.array(scores)
    resultado = {
        "k": int(num_clusters),
        "rodadas": int(rodadas),
        "fracao_amostrada": fracao,
        "ari_medio": round(float(scores.mean()), 4),
        "ari_desvio": round(float(scores.std()), 4),
        "ari_minimo": round(float(scores.min()), 4),
        "ari_maximo": round(float(scores.max()), 4),
        "interpretacao": _interpretar_estabilidade(float(scores.mean())),
    }
    print(f"[educluster] estabilidade k={num_clusters}: ARI medio {resultado['ari_medio']} "
          f"(desvio {resultado['ari_desvio']}, minimo {resultado['ari_minimo']}) -> {resultado['interpretacao']}")
    return resultado


def _interpretar_estabilidade(ari: float) -> str:
    if ari >= 0.90:
        return "muito estavel"
    if ari >= 0.75:
        return "estavel"
    if ari >= 0.60:
        return "moderadamente estavel"
    return "instavel"


def comparar_estabilidade_por_k(df_base: pd.DataFrame, k_minimo: int = K_MINIMO, k_maximo: int = K_MAXIMO, rodadas: int = 20) -> pd.DataFrame:
    print(f"\n[educluster] estabilidade por reamostragem ({rodadas} rodadas, 80% da base)")
    return pd.DataFrame([medir_estabilidade(df_base, k, rodadas) for k in range(k_minimo, k_maximo + 1)])


def educluster_modelo_curso_percepcao(
    origem: str = ORIGEM_PADRAO,
    n_minimo: int = N_MINIMO_RESPONDENTES,
    num_clusters: int = None,
    flag_exe_treino: bool = False,
) -> pd.DataFrame:
    print("[educluster] A6: perfis de curso por desempenho e percepcao de qualidade")
    df_base = preparar_dados_curso_percepcao(origem, n_minimo)

    caminho_scaler = os.path.join(DIRETORIO_MODELO, ARQ_SCALER)
    if flag_exe_treino or not os.path.exists(caminho_scaler):
        treinar_e_salvar_clusters(df_base, num_clusters)

    df_resultado = aplicar_clusters(df_base)
    perfilar_clusters(df_resultado)
    avaliar_clusters(df_resultado)

    df_resultado.to_csv(os.path.join(DIRETORIO_MODELO, "dados_curso_percepcao.csv"))
    return df_resultado


if __name__ == "__main__":
    educluster_modelo_curso_percepcao(flag_exe_treino=True)
