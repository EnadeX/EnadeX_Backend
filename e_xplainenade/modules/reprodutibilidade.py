"""
Metadados de reprodutibilidade de uma execução (2026-10-14 — ver DEVELOPMENT.md).

O Exec-ID + JSON de configuração só funcionam como protocolo de
reprodutibilidade se registrarem o que de fato determina o resultado: a base
exata usada no ajuste (hash SHA-256), as versões das bibliotecas e se houve
alguma etapa estocástica. O cache em memória do loader não é versionado — é
o hash que garante que duas execuções usaram a mesma base.
"""
import hashlib
import platform
from typing import List, Optional

import pandas as pd

from modules.residuals import _SHAPIRO_MAX_N


def hash_dataframe(df: pd.DataFrame, cols: List[str]) -> str:
    """
    SHA-256 das linhas/colunas usadas no ajuste.

    Ordena por CO_CURSO (a ordem de chegada das páginas do Supabase não é
    garantida) e arredonda para 10 casas — médias calculadas em outra ordem
    podem diferir no último bit sem que a base seja de fato diferente.
    """
    cols = sorted(set(cols) | ({"CO_CURSO"} if "CO_CURSO" in df.columns else set()))
    base = df[cols].dropna()
    if "CO_CURSO" in base.columns:
        base = base.sort_values("CO_CURSO")
    base = base.reset_index(drop=True).round(10)
    digest = hashlib.sha256(base.to_csv(index=False).encode("utf-8"))
    return digest.hexdigest()


def versoes() -> dict:
    import numpy
    import patsy
    import scipy
    import shap
    import statsmodels
    return {
        "python":      platform.python_version(),
        "pandas":      pd.__version__,
        "numpy":       numpy.__version__,
        "statsmodels": statsmodels.__version__,
        "scipy":       scipy.__version__,
        "shap":        shap.__version__,
        "patsy":       patsy.__version__,
    }


def descrever_aleatoriedade(n_obs: int) -> Optional[str]:
    """
    A única etapa estocástica do pipeline é a amostragem do Shapiro-Wilk
    (modules/residuals.py), que só ocorre para n > 5000. Abaixo disso, nenhuma
    semente é usada e declarar uma no relatório seria enganoso.
    """
    if n_obs > _SHAPIRO_MAX_N:
        return f"seed 42 — amostragem de {_SHAPIRO_MAX_N} resíduos para o Shapiro-Wilk (n > {_SHAPIRO_MAX_N})"
    return None
