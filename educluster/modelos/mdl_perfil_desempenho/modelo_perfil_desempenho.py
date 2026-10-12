import os

import joblib
import matplotlib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from educluster.educluster_config import (
    ORIGEM_PADRAO,
    AMOSTRA_SILHOUETTE,
    ESPACOS_PERFIL_DESEMPENHO,
    K_MAXIMO,
    K_MINIMO,
    MODELO_GEMINI,
    N_INIT,
    RANDOM_STATE,
)
from educluster.educluster_dados import carregar_arq3

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DIRETORIO_MODELO = os.path.dirname(os.path.abspath(__file__))
ARQ_SCALER = "scaler_perfil_desempenho.joblib"
ARQ_KMEANS = "kmeans_perfil_desempenho.joblib"
ARQ_PCA = "pca_perfil_desempenho.joblib"


def preparar_dados_perfil_desempenho(origem: str = ORIGEM_PADRAO, espaco: str = "objetivo_discursivo") -> pd.DataFrame:
    colunas = ESPACOS_PERFIL_DESEMPENHO[espaco]
    df = carregar_arq3(origem)
    base = df[colunas].dropna(subset=colunas)
    print(f"[educluster] espaco '{espaco}' {colunas}")
    print(f"[educluster] {len(df)} inscritos, {len(base)} com as notas necessarias")
    return base


def escolher_k_por_silhouette(dados_padronizados, k_minimo: int = K_MINIMO, k_maximo: int = K_MAXIMO):
    resultados = []
    for k in range(k_minimo, k_maximo + 1):
        kmeans = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=N_INIT)
        rotulos = kmeans.fit_predict(dados_padronizados)
        score = silhouette_score(
            dados_padronizados, rotulos, sample_size=AMOSTRA_SILHOUETTE, random_state=RANDOM_STATE
        )
        resultados.append({"k": k, "silhouette": round(float(score), 4)})
        print(f"[educluster]   k={k} -> silhouette {score:.4f}")

    tabela = pd.DataFrame(resultados)
    melhor_k = int(tabela.loc[tabela["silhouette"].idxmax(), "k"])
    print(f"[educluster] melhor k por silhouette: {melhor_k}")
    return melhor_k, tabela


def treinar_e_salvar_perfil(df_base: pd.DataFrame, espaco: str, num_clusters: int = None, diretorio_modelos: str = DIRETORIO_MODELO):
    colunas = ESPACOS_PERFIL_DESEMPENHO[espaco]

    scaler = StandardScaler()
    dados_padronizados = scaler.fit_transform(df_base[colunas])

    if num_clusters is None:
        print("[educluster] buscando k automaticamente")
        num_clusters, tabela_k = escolher_k_por_silhouette(dados_padronizados)
        tabela_k.to_csv(os.path.join(diretorio_modelos, f"escolha_de_k_{espaco}.csv"), index=False)

    kmeans = KMeans(n_clusters=num_clusters, random_state=RANDOM_STATE, n_init=N_INIT)
    kmeans.fit(dados_padronizados)

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    pca.fit(dados_padronizados)

    os.makedirs(diretorio_modelos, exist_ok=True)
    joblib.dump(scaler, os.path.join(diretorio_modelos, ARQ_SCALER))
    joblib.dump(kmeans, os.path.join(diretorio_modelos, ARQ_KMEANS))
    joblib.dump(pca, os.path.join(diretorio_modelos, ARQ_PCA))
    print(f"[educluster] modelos salvos em {diretorio_modelos}")
    return scaler, kmeans, pca


def aplicar_perfil(df_base: pd.DataFrame, espaco: str, diretorio_modelos: str = DIRETORIO_MODELO) -> pd.DataFrame:
    colunas = ESPACOS_PERFIL_DESEMPENHO[espaco]
    scaler = joblib.load(os.path.join(diretorio_modelos, ARQ_SCALER))
    kmeans = joblib.load(os.path.join(diretorio_modelos, ARQ_KMEANS))
    pca = joblib.load(os.path.join(diretorio_modelos, ARQ_PCA))

    dados_padronizados = scaler.transform(df_base[colunas])
    coordenadas = pca.transform(dados_padronizados)

    df_resultado = df_base.copy()
    df_resultado["Cluster_ID"] = kmeans.predict(dados_padronizados)
    df_resultado["PCA_X"] = coordenadas[:, 0]
    df_resultado["PCA_Y"] = coordenadas[:, 1]

    print(f"\n[educluster] variancia explicada em 2D: {pca.explained_variance_ratio_.sum():.4f} {pca.explained_variance_ratio_.round(4)}")
    print("[educluster] estudantes por cluster:")
    print(df_resultado["Cluster_ID"].value_counts().sort_index().to_string())
    return df_resultado


def perfilar_desempenho(df_resultado: pd.DataFrame, espaco: str) -> pd.DataFrame:
    colunas = ESPACOS_PERFIL_DESEMPENHO[espaco]
    perfil = df_resultado.groupby("Cluster_ID")[colunas].mean().round(2)
    perfil["estudantes"] = df_resultado.groupby("Cluster_ID").size()
    print("\n[educluster] PERFIL DOS CLUSTERS")
    print(perfil.to_string())
    return perfil


def plotar_perfil(df_resultado: pd.DataFrame, nome_arquivo: str = "clusters_pca.png", diretorio: str = DIRETORIO_MODELO):
    caminho = os.path.join(diretorio, nome_arquivo)
    plt.figure(figsize=(8, 6))
    dispersao = plt.scatter(
        df_resultado["PCA_X"], df_resultado["PCA_Y"],
        c=df_resultado["Cluster_ID"], cmap="viridis", s=10, alpha=0.5
    )
    plt.xlabel("Componente 1")
    plt.ylabel("Componente 2")
    plt.title("Perfis de desempenho, ENADE 2021 (base nacional)")
    plt.colorbar(dispersao, label="cluster")
    plt.tight_layout()
    plt.savefig(caminho, dpi=150)
    plt.close()
    print(f"[educluster] grafico salvo em {caminho}")
    return caminho


def descrever_perfis_com_ia(perfil: pd.DataFrame) -> str:
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        print("[educluster] GEMINI_API_KEY ausente, descricao automatica ignorada")
        return ""

    try:
        import google.generativeai as genai
    except ImportError:
        print("[educluster] google-generativeai nao instalado, descricao automatica ignorada")
        return ""

    genai.configure(api_key=chave)
    prompt = (
        "Voce e um pesquisador em educacao superior. Analise os seguintes perfis de desempenho "
        "obtidos por clusterizacao sobre a base nacional completa de concluintes do ENADE 2021, "
        "sem recorte de curso ou regiao. As notas vao de 0 a 100. Descreva cada perfil em ate 3 "
        "linhas, com linguagem simples e academica. Compare o desempenho nas partes objetiva e "
        "discursiva quando disponivel. Nao afirme causalidade.\n\n"
        + perfil.to_string()
    )

    try:
        modelo = genai.GenerativeModel(MODELO_GEMINI)
        resposta = modelo.generate_content(prompt).text
        print("\n[educluster] DESCRICAO DOS PERFIS (Gemini)")
        print(resposta)
        return resposta
    except Exception as erro:
        print(f"[educluster] falha na descricao automatica: {erro}")
        return ""


def avaliar_perfil(df_resultado: pd.DataFrame, espaco: str, diretorio_modelos: str = DIRETORIO_MODELO) -> dict:
    colunas = ESPACOS_PERFIL_DESEMPENHO[espaco]
    scaler = joblib.load(os.path.join(diretorio_modelos, ARQ_SCALER))
    dados_padronizados = scaler.transform(df_resultado[colunas])

    pca_completo = PCA(random_state=RANDOM_STATE)
    pca_completo.fit(dados_padronizados)

    score = silhouette_score(
        dados_padronizados, df_resultado["Cluster_ID"],
        sample_size=AMOSTRA_SILHOUETTE, random_state=RANDOM_STATE,
    )
    return {
        "espaco": espaco,
        "variaveis": colunas,
        "n_estudantes": int(len(df_resultado)),
        "k": int(df_resultado["Cluster_ID"].nunique()),
        "silhouette": round(float(score), 4),
        "silhouette_amostra": AMOSTRA_SILHOUETTE,
        "variancia_explicada_2d": round(float(pca_completo.explained_variance_ratio_[:2].sum()), 4),
        "variancia_por_componente": [round(float(v), 4) for v in pca_completo.explained_variance_ratio_],
    }


def amostrar_para_plotagem(df_resultado: pd.DataFrame, n: int = 5000) -> pd.DataFrame:
    if n >= len(df_resultado):
        return df_resultado
    return df_resultado.sample(n=n, random_state=RANDOM_STATE)


def educluster_modelo_perfil_desempenho(
    origem: str = ORIGEM_PADRAO,
    espaco: str = "objetivo_discursivo",
    num_clusters: int = None,
    flag_exe_treino: bool = False,
    flag_descrever: bool = False,
) -> pd.DataFrame:
    print("[educluster] A1: perfis de desempenho no nivel do estudante")
    df_base = preparar_dados_perfil_desempenho(origem, espaco)

    caminho_scaler = os.path.join(DIRETORIO_MODELO, ARQ_SCALER)
    if flag_exe_treino or not os.path.exists(caminho_scaler):
        treinar_e_salvar_perfil(df_base, espaco, num_clusters)

    df_resultado = aplicar_perfil(df_base, espaco)
    perfil = perfilar_desempenho(df_resultado, espaco)
    plotar_perfil(df_resultado)

    if flag_descrever:
        descrever_perfis_com_ia(perfil)

    perfil.to_csv(os.path.join(DIRETORIO_MODELO, f"perfil_{espaco}.csv"))
    return df_resultado


if __name__ == "__main__":
    educluster_modelo_perfil_desempenho(flag_exe_treino=True)
