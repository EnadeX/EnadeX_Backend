"""
Camada 5 — Diagnóstico de multicolinearidade (VIF).

Calcula o Fator de Inflação da Variância (VIF) para cada preditor do modelo,
incluindo termos de interação quando a fórmula é fornecida.
Emite alertas em dois níveis: VIF > 5 (moderado) e VIF > 10 (severo).
Permite remoção interativa da variável com maior VIF e reexecução automática.
"""
from typing import List, Optional

import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor

VIF_MODERADO = 5.0
VIF_SEVERO = 10.0


def compute_vif(
    df: pd.DataFrame,
    x_vars: List[str],
    formula: Optional[str] = None,
) -> pd.DataFrame:
    """
    Calcula o VIF para cada preditor do modelo.

    Quando `formula` é fornecida, a matriz de design é construída via patsy
    (incluindo termos de interação). Sem ela, calcula apenas sobre `x_vars`.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame pré-processado.
    x_vars : list[str]
        Variáveis independentes (efeitos principais).
    formula : str, optional
        Fórmula completa do modelo (ex: 'NT_GER ~ A + B + A:B').
        Se fornecida, os termos de interação são incluídos no diagnóstico.

    Returns
    -------
    pd.DataFrame
        Colunas: variavel, vif, alerta
        alerta: 'ok' | 'moderado (VIF > 5)' | 'severo (VIF > 10)'
    """
    from statsmodels.tools.tools import add_constant

    if formula is not None:
        # Constrói a design matrix completa (inclui interações) via patsy
        import patsy
        rhs = formula.split("~", 1)[1].strip()
        try:
            X_pat = patsy.dmatrix(rhs, data=df, return_type="dataframe")
            # Remove a coluna Intercept — VIF é calculado nos preditores
            X_pat = X_pat.drop(columns=[c for c in X_pat.columns
                                        if c.lower() in ("intercept", "const")],
                               errors="ignore")
            X_pat = X_pat.dropna()
            X_full = add_constant(X_pat, has_constant="add")
            term_names = X_pat.columns.tolist()
            vif_values = [
                variance_inflation_factor(X_full.values, i + 1)
                for i in range(len(term_names))
            ]
            return _build_vif_table(term_names, vif_values)
        except Exception:
            pass  # fallback para o modo sem fórmula

    # Modo sem fórmula: só efeitos principais
    subset = df[x_vars].dropna()
    # add_constant necessário para VIF correto em modelos com intercepto
    X = add_constant(subset, has_constant="raise" if "const" in subset.columns else "add")
    vif_values = [
        variance_inflation_factor(X.values, i + 1)  # +1 para pular const
        for i in range(len(x_vars))
    ]
    return _build_vif_table(x_vars, vif_values)


def _build_vif_table(names: List[str], vif_values: List[float]) -> pd.DataFrame:
    def _label(v: float) -> str:
        if v > VIF_SEVERO:
            return "severo (VIF > 10)"
        if v > VIF_MODERADO:
            return "moderado (VIF > 5)"
        return "ok"

    return pd.DataFrame({
        "variavel": names,
        "vif":      [round(v, 3) for v in vif_values],
        "alerta":   [_label(v) for v in vif_values],
    })


def get_variable_to_remove(vif_table: pd.DataFrame) -> str:
    """
    Retorna o nome da variável com maior VIF acima do limiar moderado.
    Retorna None se todas estiverem dentro do limiar.
    """
    problematic = vif_table[vif_table["vif"] > VIF_MODERADO]
    if problematic.empty:
        return None
    return problematic.sort_values("vif", ascending=False).iloc[0]["variavel"]


def has_multicollinearity(vif_table: pd.DataFrame) -> bool:
    """Retorna True se alguma variável tem VIF > limiar moderado."""
    return (vif_table["vif"] > VIF_MODERADO).any()
