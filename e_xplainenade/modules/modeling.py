"""
Camada 4 — Engine de modelagem estatística (WLS/OLS).

Ajusta o modelo de regressão linear múltipla via statsmodels, extrai
coeficientes, p-valores e IC 95%, e gera interpretação textual.

Escolha de statsmodels (não scikit-learn): o E-XplainENADE é confirmatório,
não preditivo. O objetivo é testar hipóteses sobre relações entre variáveis,
o que requer p-valores, IC e testes de hipótese — ausentes no scikit-learn.

WLS por padrão (não OLS simples): cada linha da base é um CURSO, agregado a
partir de um número diferente de estudantes presentes (QT_ALUNOS). A média
de um curso com 2 presentes é muito mais ruidosa que a de um curso com 200 —
tratá-las como igualmente confiáveis (OLS simples) é estatisticamente
incorreto e mascara heterocedasticidade ligada ao tamanho do curso (achado
registrado no DEVELOPMENT.md, 2026-08-27: variáveis que pareciam sem efeito
em OLS simples — ex. Situação de Trabalho — tornam-se significativas ao
ponderar por QT_ALUNOS). `fit_ols()` ajusta WLS sempre que `weight_col`
existir no DataFrame; caso contrário, cai para OLS simples (equivalente a
pesos iguais).
"""
from typing import Optional

import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.regression.linear_model import RegressionResultsWrapper

from modules.hypothesis import HypothesisConfig


def fit_ols(
    hypothesis: HypothesisConfig,
    df: pd.DataFrame,
    weight_col: Optional[str] = "QT_ALUNOS",
) -> RegressionResultsWrapper:
    """
    Ajusta o modelo de regressão a partir de uma hipótese e um DataFrame.

    Parameters
    ----------
    hypothesis : HypothesisConfig
        Hipótese com Y, X e interações; formula gerada automaticamente.
    df : pd.DataFrame
        DataFrame pré-processado (base agregada por curso).
    weight_col : str, optional
        Nome da coluna de peso (nº de alunos por curso). Se presente em
        `df`, ajusta WLS ponderado por essa coluna (padrão: "QT_ALUNOS").
        Se None ou ausente do DataFrame, ajusta OLS simples.

    Returns
    -------
    RegressionResultsWrapper
        Objeto de resultado do statsmodels com coeficientes, p-valores e IC.
        Mesma interface para OLS e WLS — todo o restante do pipeline
        (VIF, resíduos, SHAP, relatório) funciona sem alteração.
    """
    formula = hypothesis.to_formula()
    if weight_col and weight_col in df.columns:
        model = smf.wls(formula=formula, data=df, weights=df[weight_col])
    else:
        model = smf.ols(formula=formula, data=df)
    return model.fit()


def get_coefficients_table(result: RegressionResultsWrapper) -> pd.DataFrame:
    """
    Extrai tabela de coeficientes com p-valores e IC 95%.

    Returns
    -------
    pd.DataFrame
        Colunas: variável, coeficiente, erro_padrao, t_stat, p_valor, ic_inf, ic_sup
    """
    summary = result.summary2().tables[1].reset_index()
    summary.columns = ["variavel", "coeficiente", "erro_padrao", "t_stat",
                        "p_valor", "ic_inf_95", "ic_sup_95"]
    return summary


def get_model_metrics(result: RegressionResultsWrapper) -> dict:
    """Retorna R², R² ajustado, AIC, BIC e n observações."""
    return {
        "r2":          round(float(result.rsquared), 4),
        "r2_adj":      round(float(result.rsquared_adj), 4),
        "aic":         round(float(result.aic), 2),
        "bic":         round(float(result.bic), 2),
        "n_obs":       int(result.nobs),
        "f_stat":      round(float(result.fvalue), 4),
        "f_pvalue":    round(float(result.f_pvalue), 6),
    }
