"""
Camada 6 — Diagnóstico de resíduos.

Executa os testes de pressupostos do modelo OLS/WLS:
  - Normalidade dos resíduos: Shapiro-Wilk (scipy.stats)
  - Homocedasticidade: Breusch-Pagan (statsmodels)

Também prepara os dados para o gráfico interativo de resíduos vs. fitted.

Usa `result.wresid` (resíduo "whitened"/ponderado) em vez de `result.resid`
em todo o módulo. Para OLS simples os dois são idênticos (peso = 1), então
isso não muda nada quando não há ponderação. Para WLS (padrão desde
2026-08-27 — ver modules/modeling.py), a suposição de homocedasticidade dos
testes vale sobre o resíduo ponderado, não sobre o resíduo bruto: testar o
resíduo bruto de um modelo WLS reintroduziria exatamente a heterocedasticidade
ligada ao tamanho do curso que a ponderação foi feita para corrigir, dando um
diagnóstico inconsistente com os gráficos.
"""
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import RegressionResultsWrapper
from statsmodels.stats.diagnostic import het_breuschpagan


_SHAPIRO_MAX_N = 5000  # scipy avisa que p-valor não é confiável para n > 5000


def run_diagnostics(result: RegressionResultsWrapper) -> dict:
    """
    Executa Shapiro-Wilk e Breusch-Pagan sobre os resíduos do modelo ajustado.

    Nota sobre Shapiro-Wilk com n > 5000: o teste se torna extremamente sensível
    a desvios mínimos da normalidade, rejeitando H0 mesmo quando a distribuição
    é praticamente normal. Para n > 5000, o resultado é reportado com aviso;
    a análise visual do QQ-plot e o Teorema Central do Limite (n >> 30) são
    evidências complementares mais robustas nesse regime amostral.

    Returns
    -------
    dict com chaves:
      shapiro_stat, shapiro_pvalue, shapiro_normal (bool), shapiro_confiavel (bool)
      bp_stat, bp_pvalue, bp_homocedastic (bool)
    """
    residuals = result.wresid.values
    n = len(residuals)

    # Shapiro-Wilk: usa amostra de 5000 quando n > limite para resultado confiável
    if n > _SHAPIRO_MAX_N:
        rng = np.random.default_rng(seed=42)
        sample = rng.choice(residuals, size=_SHAPIRO_MAX_N, replace=False)
        sw_stat, sw_pvalue = stats.shapiro(sample)
        shapiro_confiavel = False
    else:
        sw_stat, sw_pvalue = stats.shapiro(residuals)
        shapiro_confiavel = True

    # Testa o resíduo ponderado (wresid) contra as variáveis ORIGINAIS (exog, não
    # wexog): a coluna de intercepto de wexog deixa de ser constante após a
    # ponderação (vira sqrt(peso) por linha), o que quebra a checagem interna do
    # het_breuschpagan ("exog must have a constant column"). Para OLS sem peso,
    # exog == wexog, então este comportamento não muda.
    bp_stat, bp_pvalue, _, _ = het_breuschpagan(residuals, result.model.exog)

    return {
        "shapiro_stat":       round(float(sw_stat), 6),
        "shapiro_pvalue":     round(float(sw_pvalue), 6),
        "shapiro_normal":     float(sw_pvalue) >= 0.05,
        "shapiro_confiavel":  shapiro_confiavel,
        "shapiro_n_usado":    min(n, _SHAPIRO_MAX_N),
        "bp_stat":            round(float(bp_stat), 6),
        "bp_pvalue":          round(float(bp_pvalue), 6),
        "bp_homocedastic":    float(bp_pvalue) >= 0.05,
    }


def get_qqplot_data(result: RegressionResultsWrapper) -> pd.DataFrame:
    """
    Retorna DataFrame com quantis teóricos e amostrais para QQ-plot.
    Colunas: theoretical (quantis normais), sample (resíduos ordenados), line_y (reta de referência)
    """
    residuals = result.wresid.values
    (osm, osr), (slope, intercept, _) = stats.probplot(residuals)
    return pd.DataFrame({
        "theoretical": osm,
        "sample":      osr,
        "line_y":      slope * osm + intercept,
    })


def get_residuals_plot_data(result: RegressionResultsWrapper) -> pd.DataFrame:
    """
    Retorna DataFrame com resíduos e valores preditos para plotagem.

    Colunas: fitted (valores preditos), residual (ponderado — wresid;
    idêntico ao resíduo bruto quando o modelo é OLS sem peso),
    residual_std (padronizado)
    """
    fitted = result.fittedvalues
    residuals = result.wresid
    std_resid = residuals / residuals.std()

    return pd.DataFrame({
        "fitted":       fitted.values,
        "residual":     residuals.values,
        "residual_std": std_resid.values,
    })
