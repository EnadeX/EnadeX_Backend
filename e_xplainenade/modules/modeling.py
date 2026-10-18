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

Sensibilidade (2026-10-14 — ver DEVELOPMENT.md): em dados agrupados, ponderar
pelo tamanho do grupo só é eficiente sob uma condição específica sobre o erro
(Dickens, 1990; Solon, Haider e Wooldridge, 2013). Por isso fit_variants()
ajusta, ao lado do WLS principal, o OLS sem pesos e as duas versões com
erros-padrão robustos (HC3), e get_comparison_table() aponta os termos cujo
sinal ou significância mudam entre os ajustes. O WLS clássico continua sendo
o modelo principal (VIF, resíduos e SHAP usam ele).
"""
from typing import Dict, Optional

import numpy as np
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


COV_TYPE_ROBUSTO = "HC3"  # conservador para n ≈ 700 cursos


def fit_variants(
    hypothesis: HypothesisConfig,
    df: pd.DataFrame,
    weight_col: str = "QT_ALUNOS",
    cov_type: str = COV_TYPE_ROBUSTO,
) -> Dict[str, RegressionResultsWrapper]:
    """
    Ajusta as quatro variantes usadas na análise de sensibilidade:
    wls (principal, EP clássico), wls_robust, ols (sem pesos) e ols_robust.

    Os coeficientes de wls/wls_robust (e de ols/ols_robust) são idênticos —
    só os erros-padrão e p-valores mudam.
    """
    formula = hypothesis.to_formula()
    wls = smf.wls(formula=formula, data=df, weights=df[weight_col])
    ols = smf.ols(formula=formula, data=df)
    return {
        "wls":        wls.fit(),
        "wls_robust": wls.fit(cov_type=cov_type),
        "ols":        ols.fit(),
        "ols_robust": ols.fit(cov_type=cov_type),
    }


def get_comparison_table(variants: Dict[str, RegressionResultsWrapper]) -> pd.DataFrame:
    """
    Uma linha por termo do modelo: coef/EP/p de cada variante, mais duas flags —
    `sinal_diverge` (WLS × OLS com sinais opostos) e `signif_diverge` (o termo
    é significativo a 5% em um dos ajustes robustos e não no outro).
    """
    rows = []
    for term in variants["wls"].params.index:
        r = {"variavel": term}
        for k, res in variants.items():
            r[f"coef_{k}"] = float(res.params[term])
            r[f"ep_{k}"] = float(res.bse[term])
            r[f"p_{k}"] = float(res.pvalues[term])
        r["sinal_diverge"] = bool(np.sign(r["coef_wls"]) != np.sign(r["coef_ols"]))
        r["signif_diverge"] = bool((r["p_wls_robust"] < 0.05) != (r["p_ols_robust"] < 0.05))
        rows.append(r)
    return pd.DataFrame(rows)


def get_coefficients_table(
    result: RegressionResultsWrapper,
    robust_result: Optional[RegressionResultsWrapper] = None,
) -> pd.DataFrame:
    """
    Extrai tabela de coeficientes com p-valores e IC 95%.

    Se `robust_result` (o mesmo modelo ajustado com cov_type robusto) for
    passado, acrescenta as colunas `erro_padrao_robusto` e `p_valor_robusto`.

    Returns
    -------
    pd.DataFrame
        Colunas: variável, coeficiente, erro_padrao, t_stat, p_valor, ic_inf, ic_sup
        (+ erro_padrao_robusto, p_valor_robusto)
    """
    summary = result.summary2().tables[1].reset_index()
    summary.columns = ["variavel", "coeficiente", "erro_padrao", "t_stat",
                        "p_valor", "ic_inf_95", "ic_sup_95"]
    if robust_result is not None:
        summary["erro_padrao_robusto"] = summary["variavel"].map(robust_result.bse).astype(float)
        summary["p_valor_robusto"] = summary["variavel"].map(robust_result.pvalues).astype(float)
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
