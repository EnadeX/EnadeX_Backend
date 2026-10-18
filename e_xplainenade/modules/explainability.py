"""
Camada 7 — Explicabilidade via SHAP.

Calcula os valores SHAP usando shap.LinearExplainer aplicado ao modelo OLS.
Fundamentação: Corolário 1 de Lundberg e Lee (2017) — para modelos lineares
com features independentes, os valores SHAP equivalem aos coeficientes
ponderados pela diferença em relação à média das variáveis, o que confere
rigor matemático à interpretação gerada automaticamente.

Linha de base ponderada (2026-10-14 — ver DEVELOPMENT.md): pelo mesmo
Corolário, SHAP_ij = coef_j · (x_ij − média_j). O LinearExplainer usa a média
SIMPLES das linhas como linha de base, mas o modelo é WLS — então, quando a
coluna de peso existe, a média usada é a ponderada por QT_ALUNOS (mesmo peso
do ajuste). Com pesos iguais, o resultado coincide com o LinearExplainer.
"""
import re
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import patsy
import shap
from statsmodels.regression.linear_model import RegressionResultsWrapper


def compute_shap(
    result: RegressionResultsWrapper,
    df: pd.DataFrame,
    x_vars: List[str],
    weight_col: Optional[str] = "QT_ALUNOS",
) -> Tuple[np.ndarray, List[str]]:
    """
    Calcula os valores SHAP via LinearExplainer sobre o modelo OLS ajustado.

    Usa a matriz de design completa (via patsy) para tratar corretamente
    termos de interação (ex: QE_RENDA:QE_HORAS_ESTUDO). O LinearExplainer
    recebe (coef, intercept) extraídos do resultado statsmodels.

    Parameters
    ----------
    result : RegressionResultsWrapper
        Resultado do OLS (statsmodels).
    df : pd.DataFrame
        DataFrame com os dados de entrada (pré-processado).
    x_vars : list[str]
        Variáveis independentes base (sem termos de interação).
    weight_col : str, optional
        Coluna de peso para a linha de base (padrão: "QT_ALUNOS", o mesmo
        peso do WLS). Se None ou ausente, usa o LinearExplainer (média simples).

    Returns
    -------
    shap_values : np.ndarray  (n_obs × n_features_design)
    feature_names : list[str]  — nomes das colunas da matriz de design
    """
    formula_rhs = result.model.formula.split("~")[1].strip()

    # Extrai todas as colunas referenciadas na fórmula (inclui variáveis de interações)
    # Usar só x_vars falharia se a fórmula contiver interações com variáveis fora de x_vars
    formula_cols = list({v for v in re.findall(r'\b([A-Za-z_]\w*)\b', formula_rhs)
                         if v in df.columns})
    usar_peso = bool(weight_col) and weight_col in df.columns
    cols = formula_cols + ([weight_col] if usar_peso and weight_col not in formula_cols else [])
    df_clean = df[cols].dropna()

    X_dm = patsy.dmatrix(formula_rhs, df_clean, return_type="dataframe")
    X_features = X_dm.drop(columns=["Intercept"], errors="ignore")

    feature_names = list(X_features.columns)
    coef = result.params.drop("Intercept", errors="ignore").reindex(feature_names).values
    intercept = float(result.params.get("Intercept", 0.0))

    if usar_peso:
        return compute_shap_weighted(X_features, coef, df_clean[weight_col].values), feature_names

    explainer = shap.LinearExplainer((coef, intercept), X_features)
    return explainer.shap_values(X_features), feature_names


def compute_shap_weighted(
    X_features: pd.DataFrame,
    coef: np.ndarray,
    weights: np.ndarray,
) -> np.ndarray:
    """SHAP exato de um modelo linear com linha de base = média ponderada das features."""
    mu = np.average(X_features.values, axis=0, weights=weights)
    return coef * (X_features.values - mu)


def get_shap_summary(
    shap_values: np.ndarray,
    feature_names: List[str],
) -> pd.DataFrame:
    """
    Retorna o impacto médio absoluto de cada variável (base do beeswarm/bar plot).

    Returns
    -------
    pd.DataFrame
        Colunas: variavel, shap_mean_abs — ordenado do maior para o menor impacto.
    """
    mean_abs = np.abs(shap_values).mean(axis=0)
    return (
        pd.DataFrame({"variavel": feature_names, "shap_mean_abs": mean_abs})
        .sort_values("shap_mean_abs", ascending=False)
        .reset_index(drop=True)
    )


def get_top_factors(shap_summary: pd.DataFrame, n: int = 3) -> dict:
    """
    Retorna os top-N fatores de maior impacto positivo e negativo.
    Usado para geração de texto interpretativo automático no relatório.
    """
    top_positive = shap_summary.head(n)["variavel"].tolist()
    top_negative = shap_summary.tail(n)["variavel"].tolist()
    return {"top_positive": top_positive, "top_negative": top_negative}
