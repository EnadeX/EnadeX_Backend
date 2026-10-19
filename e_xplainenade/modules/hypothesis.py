"""
Camada 3 — Definição formal da hipótese analítica.

Responsável por receber a hipótese do usuário (Y, X, interações), VALIDAR e normalizar
(normalizar_hipotese), conferir contra o DataFrame disponível e gerar a fórmula OLS no
formato statsmodels (ex: 'NT_GER ~ QE_RENDA + QE_ESC_MAE').

Validação (2026-10-18 — F1 do plano, ver DEVELOPMENT.md). A tela só oferece as variáveis
certas, mas a API aceitava qualquer coluna da base: NT_GER como preditora de si mesma dava
R² = 1,000; NT_FG (que compõe a nota geral) dava 0,72; CO_GRUPO, um código nominal, entrava
como número. Agora Y ∈ Y_OPTS e X ∈ X_OPTS (a mesma lista que a interface usa), sem
repetições, e toda interação tem de ser entre duas variáveis distintas que estejam em X.

Amostra: build_hypothesis() recusa o caso impossível de ajustar (n ≤ k + 1) e
avisos_amostra() devolve avisos, sem bloquear, pela regra de Green (1991): n ≥ 50 + 8k para
testar o R² geral e n ≥ 104 + k para testar os coeficientes (já usada em 2026-08-26).

Centragem (2026-10-14): quando a hipótese tem termos de interação, center_for_interactions()
centra na média as variáveis envolvidas antes do ajuste (Afshartous e Preston, 2011). O teste
do termo a:b não muda, mas o coeficiente de cada efeito principal passa a ser o efeito no
curso médio da outra variável, e o VIF dos efeitos principais deixa de ser inflado pela
correlação estrutural entre a, b e a:b.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config.variable_map import CODE_TO_LABEL, CODE_TO_UI_LABEL, X_OPTS, Y_OPTS

# Regra de Green (1991): tamanho mínimo recomendado da amostra, com k = nº de termos do modelo.
GREEN_R2 = (50, 8)      # n >= 50 + 8k  para testar o R² geral
GREEN_COEF = (104, 1)   # n >= 104 + k  para testar coeficientes individuais


def _rotulo(codigo: str) -> str:
    return CODE_TO_UI_LABEL.get(codigo, CODE_TO_LABEL.get(codigo, codigo))


def _lista(codigos) -> str:
    return ", ".join(f"{_rotulo(c)} ({c})" if _rotulo(c) != c else c for c in codigos)


@dataclass
class HypothesisConfig:
    """Configuração formal de uma hipótese analítica."""
    y: str
    x_vars: List[str]
    interactions: List[Tuple[str, str]] = field(default_factory=list)
    # Avisos da normalização (ex: variável repetida removida); não entram na comparação.
    avisos: List[str] = field(default_factory=list, compare=False)

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

    @property
    def n_termos(self) -> int:
        """k: efeitos principais + interações (todas as variáveis são numéricas: 1 coeficiente por termo)."""
        return len(self.x_vars) + len(self.interactions)


def normalizar_hipotese(
    y: str,
    x_vars: List[str],
    interactions: Optional[List[Tuple[str, str]]] = None,
) -> Tuple[str, List[str], List[Tuple[str, str]], List[str]]:
    """
    Valida e normaliza uma hipótese. Não precisa do DataFrame (por isso pode rodar ANTES da
    consulta ao Supabase, que leva ~10 s a frio).

    Returns
    -------
    (y, x_vars, interactions, avisos) — X sem repetições (ordem preservada) e interações sem
    repetição (o par (a, b) é igual a (b, a)). `avisos` descreve o que foi removido.

    Raises
    ------
    ValueError com mensagem clara (a API devolve 400).
    """
    permitidas_y, permitidas_x = set(Y_OPTS.values()), set(X_OPTS.values())
    avisos: List[str] = []

    if y not in permitidas_y:
        raise ValueError(f"Variável dependente inválida: {y!r}. Opções: {_lista(Y_OPTS.values())}.")

    if not x_vars:
        raise ValueError("Escolha ao menos uma variável explicativa.")
    invalidas = [v for v in dict.fromkeys(x_vars) if v not in permitidas_x]
    if invalidas:
        raise ValueError(
            f"Variável(is) explicativa(s) não permitida(s): {', '.join(invalidas)}. Só são aceitas as "
            f"variáveis oferecidas pela interface (GET /opcoes): notas, nº de alunos e códigos nominais "
            f"ficam de fora, porque fariam parte do próprio resultado ou não têm escala numérica."
        )

    x_unicas = list(dict.fromkeys(x_vars))
    if len(x_unicas) < len(x_vars):
        repetidas = [v for v in x_unicas if x_vars.count(v) > 1]
        avisos.append(f"Variável explicativa repetida, mantida uma vez: {_lista(repetidas)}.")

    pares: List[Tuple[str, str]] = []
    vistos = set()
    removidas: List[str] = []
    for a, b in (interactions or []):
        if a == b:
            raise ValueError(
                f"Interação inválida: {_rotulo(a)} × {_rotulo(a)} é a mesma variável; uma interação "
                f"precisa de duas variáveis diferentes."
            )
        fora = [v for v in (a, b) if v not in x_unicas]
        if fora:
            raise ValueError(
                f"Interação {_rotulo(a)} × {_rotulo(b)} exige que as duas variáveis estejam entre as "
                f"explicativas; faltam: {_lista(fora)}."
            )
        chave = frozenset((a, b))
        if chave in vistos:
            removidas.append(f"{_rotulo(a)} × {_rotulo(b)}")
            continue
        vistos.add(chave)
        pares.append((a, b))
    if removidas:
        avisos.append(f"Interação repetida (ou com a ordem invertida), mantida uma vez: {', '.join(removidas)}.")

    return y, x_unicas, pares, avisos


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
        Variável dependente (uma de Y_OPTS: 'NT_GER', 'NT_FG', 'NT_CE').
    x_vars : list[str]
        Variáveis independentes (de X_OPTS).
    interactions : list of (str, str), optional
        Pares de variáveis para termos de interação (ambas devem estar em x_vars).
    df : pd.DataFrame, optional
        Se fornecido, confere também o recorte: variáveis presentes, recorte não vazio,
        amostra suficiente para ajustar e nenhuma variável constante.

    Returns
    -------
    HypothesisConfig (com `avisos` da normalização)

    Raises
    ------
    ValueError com mensagem clara.
    """
    y, x_vars, interactions, avisos = normalizar_hipotese(y, x_vars, interactions)
    hyp = HypothesisConfig(y=y, x_vars=x_vars, interactions=interactions, avisos=avisos)

    if df is not None:
        faltando = [v for v in hyp.variables() if v not in df.columns]
        if faltando:
            raise ValueError(f"Variáveis não encontradas no DataFrame: {sorted(set(faltando))}")

        # Mesmas linhas que o statsmodels usa (descarta qualquer linha com NaN na fórmula).
        usados = df[hyp.variables()].dropna()
        n, k = len(usados), hyp.n_termos
        if n == 0:
            raise ValueError(
                "Nenhum curso atende aos filtros escolhidos (ou nenhum tem dados completos nas "
                "variáveis desta hipótese). Amplie o recorte ou reduza o corte de presentes."
            )
        if n <= k + 1:
            raise ValueError(
                f"Amostra insuficiente: {n} curso(s) com dados completos para {k} termo(s) "
                f"({k + 1} parâmetros com o intercepto). É preciso mais cursos do que parâmetros. "
                f"Amplie o recorte, reduza o corte de presentes ou remova variáveis."
            )

        # Variável constante no recorte (ex: CURSO_SI com o filtro "só CC") deixa a matriz de
        # design singular — falha com mensagem clara, antes do ajuste.
        constantes = [v for v in dict.fromkeys(hyp.x_vars + [v for par in hyp.interactions for v in par])
                      if usados[v].nunique() <= 1]
        if constantes:
            raise ValueError(
                f"Variável sem variação neste recorte: {', '.join(_rotulo(v) for v in constantes)} "
                f"(todos os cursos têm o mesmo valor). Remova-a da hipótese ou amplie o filtro."
            )

    return hyp


def avisos_amostra(hyp: HypothesisConfig, df: pd.DataFrame) -> List[str]:
    """
    Avisos (que NÃO bloqueiam) sobre o tamanho da amostra, pela regra de Green (1991).
    Chamar depois de build_hypothesis(..., df), que já recusou o caso impossível.
    """
    n, k = len(df[hyp.variables()].dropna()), hyp.n_termos
    avisos = []
    minimo_coef = GREEN_COEF[0] + GREEN_COEF[1] * k
    minimo_r2 = GREEN_R2[0] + GREEN_R2[1] * k
    if n < minimo_coef:
        avisos.append(
            f"Amostra pequena para este modelo: {n} cursos e {k} termos. Pela regra de Green (1991) "
            f"seriam recomendados ao menos {minimo_coef} cursos para testar os coeficientes "
            f"individuais; os p-valores e intervalos de confiança podem ser pouco confiáveis."
        )
    if n < minimo_r2:
        avisos.append(
            f"Pela regra de Green (1991), o teste do R² geral pede ao menos {minimo_r2} cursos "
            f"({n} disponíveis): o R² deste modelo pode estar superestimado."
        )
    return avisos


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
