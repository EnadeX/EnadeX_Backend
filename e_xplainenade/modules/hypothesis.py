"""
Camada 3 — Definição formal da hipótese analítica.

Responsável por receber a hipótese do usuário (Y, X, interações),
validar as variáveis contra o DataFrame disponível e gerar a fórmula
OLS no formato statsmodels (ex: 'NT_GER ~ QE_RENDA + QE_ESC_MAE').
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd


@dataclass
class HypothesisConfig:
    """Configuração formal de uma hipótese analítica."""
    y: str
    x_vars: List[str]
    interactions: List[Tuple[str, str]] = field(default_factory=list)

    def to_formula(self) -> str:
        """
        Gera a fórmula OLS no formato statsmodels.
        Ex: 'NT_GER ~ QE_RENDA + QE_ESC_MAE + QE_RENDA:QE_HORAS_ESTUDO'
        """
        terms = list(self.x_vars)
        for a, b in self.interactions:
            terms.append(f"{a}:{b}")
        return f"{self.y} ~ {' + '.join(terms)}"


def build_hypothesis(
    y: str,
    x_vars: List[str],
    interactions: Optional[List[Tuple[str, str]]] = None,
    df: Optional[pd.DataFrame] = None,
) -> HypothesisConfig:
    """
    Constrói e valida uma HypothesisConfig.

    Parameters
    ----------
    y : str
        Variável dependente (ex: 'NT_GER', 'NT_FG', 'NT_CE').
    x_vars : list[str]
        Lista de variáveis independentes.
    interactions : list of (str, str), optional
        Pares de variáveis para termos de interação.
    df : pd.DataFrame, optional
        Se fornecido, valida que todas as variáveis existem no DataFrame.

    Returns
    -------
    HypothesisConfig
    """
    _interactions = interactions or []

    if df is not None:
        vars_interacoes = [v for par in _interactions for v in par]
        missing = [v for v in [y] + x_vars + vars_interacoes if v not in df.columns]
        if missing:
            raise ValueError(f"Variáveis não encontradas no DataFrame: {sorted(set(missing))}")

    return HypothesisConfig(y=y, x_vars=x_vars, interactions=_interactions)
