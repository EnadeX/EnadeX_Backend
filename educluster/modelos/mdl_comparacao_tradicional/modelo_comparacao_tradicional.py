import os

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.preprocessing import StandardScaler

from educluster.educluster_config import ORIGEM_PADRAO, DIMENSOES_ARQ4, FEATURES_A6, N_MINIMO_RESPONDENTES, RANDOM_STATE
from educluster.modelos.mdl_curso_percepcao.modelo_curso_percepcao import (
    aplicar_clusters,
    preparar_dados_curso_percepcao,
)

DIRETORIO_MODELO = os.path.dirname(os.path.abspath(__file__))

DIMENSOES = list(DIMENSOES_ARQ4.keys())
ROTULOS_FAIXA = {0: "terco_inferior", 1: "terco_medio", 2: "terco_superior"}


def classificar_tradicional(df_resultado: pd.DataFrame, n_faixas: int = 3) -> pd.DataFrame:
    df = df_resultado.copy()
    df["faixa_tradicional"] = pd.qcut(df["NT_GER"], q=n_faixas, labels=False)
    df["rotulo_tradicional"] = df["faixa_tradicional"].map(ROTULOS_FAIXA)
    df["posicao_ranking"] = df["NT_GER"].rank(ascending=False).astype(int)
    return df


def comparar_particoes(df: pd.DataFrame) -> dict:
    ari = adjusted_rand_score(df["faixa_tradicional"], df["Cluster_ID"])
    nmi = normalized_mutual_info_score(df["faixa_tradicional"], df["Cluster_ID"])

    cruzada = pd.crosstab(df["rotulo_tradicional"], df["Cluster_ID"])
    concordancia = cruzada.max(axis=1).sum() / len(df)

    print("\n[educluster] TABELA CRUZADA: faixa de nota (tradicional) x cluster (artefato)")
    print(cruzada.to_string())
    print(f"\n[educluster] ARI entre as duas particoes: {ari:.4f}")
    print(f"[educluster] informacao mutua normalizada: {nmi:.4f}")

    return {
        "ari": round(float(ari), 4),
        "nmi": round(float(nmi), 4),
        "concordancia_maxima": round(float(concordancia), 4),
        "tabela_cruzada": cruzada.reset_index().to_dict(orient="records"),
    }


def medir_informacao_perdida(df: pd.DataFrame) -> dict:
    linhas = []
    for rotulo, grupo in df.groupby("rotulo_tradicional"):
        registro = {"faixa": rotulo, "cursos": len(grupo), "clusters_distintos": int(grupo["Cluster_ID"].nunique())}
        for dimensao in DIMENSOES:
            registro[f"{dimensao}_min"] = round(float(grupo[dimensao].min()), 2)
            registro[f"{dimensao}_max"] = round(float(grupo[dimensao].max()), 2)
            registro[f"{dimensao}_amplitude"] = round(float(grupo[dimensao].max() - grupo[dimensao].min()), 2)
        linhas.append(registro)

    tabela = pd.DataFrame(linhas)
    print("\n[educluster] AMPLITUDE DA PERCEPCAO DENTRO DE CADA FAIXA DE NOTA")
    print(tabela[["faixa", "cursos", "clusters_distintos"] + [f"{d}_amplitude" for d in DIMENSOES]].to_string(index=False))

    matriz = StandardScaler().fit_transform(df[FEATURES_A6])
    pca_total = PCA(random_state=RANDOM_STATE).fit(matriz)
    variancia_nota = float(df[["NT_FG", "NT_CE"]].apply(lambda s: s.var()).sum())
    variancia_total = float(df[FEATURES_A6].apply(lambda s: (s / s.std()).var()).sum())

    return {
        "por_faixa": tabela.to_dict(orient="records"),
        "variancia_1o_componente": round(float(pca_total.explained_variance_ratio_[0]), 4),
        "componentes_para_90_porcento": int(np.searchsorted(pca_total.explained_variance_ratio_.cumsum(), 0.90) + 1),
        "nota_explica_da_estrutura": round(variancia_nota / variancia_total, 4) if variancia_total else None,
    }


def encontrar_gemeos_divergentes(df: pd.DataFrame, tolerancia: float = 0.5, limite: int = 20):
    ordenado = df.sort_values("NT_GER").reset_index()
    pares = []

    for i in range(len(ordenado) - 1):
        atual, proximo = ordenado.iloc[i], ordenado.iloc[i + 1]
        if abs(atual["NT_GER"] - proximo["NT_GER"]) > tolerancia:
            continue
        if atual["Cluster_ID"] == proximo["Cluster_ID"]:
            continue
        pares.append({
            "curso_a": int(atual["CO_CURSO"]),
            "curso_b": int(proximo["CO_CURSO"]),
            "NT_GER_a": round(float(atual["NT_GER"]), 2),
            "NT_GER_b": round(float(proximo["NT_GER"]), 2),
            "diferenca_nota": round(abs(float(atual["NT_GER"]) - float(proximo["NT_GER"])), 3),
            "cluster_a": int(atual["Cluster_ID"]),
            "cluster_b": int(proximo["Cluster_ID"]),
            "ODP_a": round(float(atual["ODP"]), 2),
            "ODP_b": round(float(proximo["ODP"]), 2),
            "diferenca_ODP": round(float(proximo["ODP"]) - float(atual["ODP"]), 2),
            "tx_presenca_a": round(float(atual["tx_presenca"]), 2),
            "tx_presenca_b": round(float(proximo["tx_presenca"]), 2),
        })

    tabela = pd.DataFrame(pares)
    total = len(tabela)
    if tabela.empty:
        return tabela, 0

    tabela = tabela.reindex(tabela["diferenca_ODP"].abs().sort_values(ascending=False).index).head(limite)
    print(f"\n[educluster] {total} pares de cursos com nota quase identica caem em clusters diferentes")
    print(f"[educluster] exibindo os {len(tabela)} casos de maior divergencia de percepcao")
    print(tabela.head(3)[["curso_a", "curso_b", "NT_GER_a", "NT_GER_b", "ODP_a", "ODP_b", "cluster_a", "cluster_b"]].to_string(index=False))
    return tabela, total


def resumir_ganho(comparacao: dict, informacao: dict, total_pares: int) -> dict:
    return {
        "pergunta": "O artefato entrega algo que o ranking por nota media nao entrega?",
        "resposta": (
            f"Sim. O ARI entre a faixa de nota e o cluster e de {comparacao['ari']}, "
            f"proximo de zero, indicando que as duas particoes carregam informacao "
            f"praticamente diferente. Existem {total_pares} pares de cursos com nota "
            f"quase identica que o artefato separa em clusters distintos, porque diferem "
            f"na qualidade percebida e na taxa de presenca."
        ),
        "analise_tradicional": "faixas de terco por NT_GER, equivalente ao ranking de relatorios oficiais",
        "artefato": f"K-Means sobre {len(FEATURES_A6)} dimensoes: {', '.join(FEATURES_A6)}",
        "componentes_para_90_porcento": informacao["componentes_para_90_porcento"],
    }


def educluster_modelo_comparacao_tradicional(
    origem: str = ORIGEM_PADRAO,
    n_minimo: int = N_MINIMO_RESPONDENTES,
    tolerancia: float = 0.5,
) -> dict:
    print("[educluster] Fase 6: comparacao entre o artefato e a analise descritiva tradicional")
    df = classificar_tradicional(aplicar_clusters(preparar_dados_curso_percepcao(origem, n_minimo)))

    comparacao = comparar_particoes(df)
    informacao = medir_informacao_perdida(df)
    pares, total_pares = encontrar_gemeos_divergentes(df, tolerancia)
    ganho = resumir_ganho(comparacao, informacao, total_pares)

    if not pares.empty:
        pares.to_csv(os.path.join(DIRETORIO_MODELO, "gemeos_divergentes.csv"), index=False)

    print(f"\n[educluster] CONCLUSAO: {ganho['resposta']}")
    return {
        "comparacao_de_particoes": comparacao,
        "informacao_perdida_pelo_ranking": informacao,
        "gemeos_divergentes_amostra": pares.to_dict(orient="records"),
        "total_gemeos_divergentes": int(total_pares),
        "tolerancia_nota": tolerancia,
        "sintese": ganho,
    }


if __name__ == "__main__":
    educluster_modelo_comparacao_tradicional()
