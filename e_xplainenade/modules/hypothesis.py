"""
Camada 3 — Definição formal da hipótese analítica.

Responsável por receber a hipótese do usuário (Y, X, interações),
validar as variáveis contra o DataFrame disponível e gerar a fórmula
OLS no formato statsmodels (ex: 'NT_GER ~ QE_RENDA + QE_ESC_MAE').

Centragem (2026-10-14 — ver DEVELOPMENT.md): quando a hipótese tem termos de
interação, center_for_interactions() centra na média as variáveis envolvidas
antes do ajuste (Afshartous e Preston, 2011). O teste do termo a:b não muda,
mas o coeficiente de cada efeito principal passa a ser o efeito no curso
médio da outra variável, e o VIF dos efeitos principais deixa de ser inflado
pela correlação estrutural entre a, b e a:b.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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

    def variables(self) -> List[str]:
        """Todas as colunas usadas pela fórmula (Y, X e variáveis das interações)."""
        cols = [self.y] + list(self.x_vars)
        for par in self.interactions:
            cols.extend(par)
        return list(dict.fromkeys(cols))


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

        # Variável constante no recorte (ex: CURSO_SI com o filtro "só CC") deixa
        # a matriz de design singular — falha com mensagem clara, antes do ajuste.
        from config.variable_map import CODE_TO_LABEL, CODE_TO_UI_LABEL
        usados = df[list(dict.fromkeys([y] + x_vars + vars_interacoes))].dropna()
        constantes = [v for v in dict.fromkeys(x_vars + vars_interacoes) if usados[v].nunique() <= 1]
        if constantes:
            nomes = ", ".join(CODE_TO_UI_LABEL.get(v, CODE_TO_LABEL.get(v, v)) for v in constantes)
            raise ValueError(
                f"Variável sem variação neste recorte: {nomes} (todos os cursos têm o mesmo "
                f"valor). Remova-a da hipótese ou amplie o filtro."
            )

    return HypothesisConfig(y=y, x_vars=x_vars, interactions=_interactions)


def center_for_interactions(
    hyp: HypothesisConfig,
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Centra na média (simples, entre cursos) só as variáveis que aparecem em
    alguma interação, mantendo os mesmos nomes de coluna — rótulos, VIF e
    SHAP continuam funcionando sem alteração.

    A média é calculada sobre os cursos que de fato entram no ajuste (linhas
    completas em todas as variáveis da fórmula), não sobre a base inteira.
    Variáveis binárias também são centradas, por consistência.

    Returns
    -------
    (df_centrado, medias) — `medias` é {} quando não há interações; nesse caso
    o DataFrame original é devolvido sem cópia.
    """
    cols = sorted({v for par in hyp.interactions for v in par})
    if not cols:
        return df, {}

    usados = df[hyp.variables()].dropna().index
    df_c = df.copy()
    medias: Dict[str, float] = {}
    for c in cols:
        m = float(df_c.loc[usados, c].mean())
        df_c[c] = df_c[c] - m
        medias[c] = m
    return df_c, medias
