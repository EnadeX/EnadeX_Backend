"""
Geração de texto interpretativo a partir dos resultados do modelo.

Extraído de app.py (2026-08-29): são funções puras (sem dependência de
Streamlit), então tanto o Streamlit quanto a API (e_xplainenade_rotas.py)
usam exatamente o mesmo texto — nenhuma lógica de interpretação deveria
divergir entre as duas interfaces.
"""
from typing import Dict, Optional, Tuple

import pandas as pd

from config.variable_map import CODE_TO_LABEL, CODE_TO_UI_LABEL
from modules.multicollinearity import VIF_MODERADO, VIF_SEVERO


def label(code: str) -> str:
    """Rótulo amigável de uma variável, priorizando o rótulo de UI (X_OPTS/Y_OPTS)."""
    return CODE_TO_UI_LABEL.get(code, CODE_TO_LABEL.get(code, code))


def p_fmt(p: float) -> str:
    if p < 0.001:
        return "< 0,001"
    return f"{p:.3f}".replace(".", ",")


def interpretar_modelo(
    coef_table: pd.DataFrame,
    metrics: dict,
    y_label: str,
    medias_centragem: Optional[Dict[str, float]] = None,
) -> str:
    r2, r2_adj, n = metrics["r2"], metrics["r2_adj"], metrics["n_obs"]
    f_p = metrics.get("f_pvalue", 0)

    linhas = [
        f"O modelo de regressão linear múltipla (WLS, ponderado pelo nº de alunos "
        f"presentes de cada curso — QT_ALUNOS) ajustado com {n:,} cursos do ENADE 2021 "
        f"(CC+SI, Brasil inteiro, dados agregados por curso) "
        f"apresenta R² = {r2:.4f} (R² ajustado = {r2_adj:.4f}), explicando "
        f"**{r2*100:.1f}%** da variância (ponderada) nas notas médias de {y_label}. "
        f"O modelo é globalmente significativo (F, p {p_fmt(f_p)}). "
        f"Os coeficientes descrevem associações entre médias de cursos (dado "
        f"agregado por curso), não o efeito sobre um estudante individual.\n"
    ]

    sig_main, sig_inter, nao_sig = [], [], []
    for _, row in coef_table.iterrows():
        var = str(row["variavel"])
        if var == "Intercept":
            continue
        if row["p_valor"] < 0.05:
            (sig_inter if ":" in var else sig_main).append(row)
        else:
            nao_sig.append(row)

    if sig_main:
        linhas.append("**Efeitos principais estatisticamente significativos (p < 0,05):**")
        for row in sig_main:
            coef, p = row["coeficiente"], row["p_valor"]
            lbl = label(str(row["variavel"]))
            sinal = "positiva" if coef > 0 else "negativa"
            movimento = "um aumento médio" if coef > 0 else "uma redução média"
            linhas.append(
                f"• **{lbl}** apresenta associação {sinal} estatisticamente distinguível de zero "
                f"(β = {coef:+.2f}, p {p_fmt(p)}). "
                f"Cada nível adicional está associado a {movimento} de "
                f"{abs(coef):.2f} pontos na {y_label}."
            )

    if sig_inter:
        linhas.append("\n**Interações estatisticamente significativas:**")
        for row in sig_inter:
            coef, p = row["coeficiente"], row["p_valor"]
            parts = str(row["variavel"]).split(":")
            la, lb = label(parts[0]), label(parts[1])
            if coef < 0:
                linhas.append(
                    f"• A associação de **{la}** com a nota varia conforme **{lb}** "
                    f"(interação estatisticamente distinguível de zero, β = {coef:+.2f}, p {p_fmt(p)}). "
                    f"O sinal negativo indica que a associação de cada fator é menor quando o outro é maior."
                )
            else:
                linhas.append(
                    f"• A associação de **{la}** com a nota varia conforme **{lb}** "
                    f"(interação estatisticamente distinguível de zero, β = {coef:+.2f}, p {p_fmt(p)}). "
                    f"O sinal positivo indica que a associação de cada fator é maior quando o outro é maior."
                )

    if nao_sig:
        nomes = ", ".join(
            label(str(r["variavel"])) for r in nao_sig
            if ":" not in str(r["variavel"])
        )
        if nomes:
            linhas.append(
                f"\n**Sem evidência estatística de associação (p ≥ 0,05):** {nomes}. "
                f"Não foi encontrada associação estatisticamente distinguível de zero "
                f"entre esses fatores e a {y_label}, nesta amostra."
            )

    if medias_centragem:
        lista = ", ".join(
            f"{label(v)} (média {f'{m:.2f}'.replace('.', ',')})"
            for v, m in medias_centragem.items()
        )
        linhas.append(
            f"\n**Variáveis centradas na média:** {lista}. Com as variáveis da "
            f"interação centradas, o coeficiente de cada efeito principal é o efeito "
            f"quando a outra variável está na média dos cursos, e o intercepto é o "
            f"valor predito no curso médio. O teste do termo de interação não muda."
        )

    return "\n".join(linhas)


def _rotulo_termo(var: str) -> str:
    return " × ".join(label(p) for p in var.split(":")) if ":" in var else label(var)


def interpretar_sensibilidade(comparison_table: pd.DataFrame, cov_type: str = "HC3") -> str:
    """Frase-resumo da comparação WLS × OLS (clássico × robusto)."""
    termos = comparison_table[comparison_table["variavel"] != "Intercept"]
    sinal = termos[termos["sinal_diverge"]]
    signif = termos[termos["signif_diverge"]]

    if sinal.empty and signif.empty:
        return (
            f"Os resultados são robustos à ponderação: nenhum fator muda de sinal "
            f"entre o WLS (ponderado por QT_ALUNOS) e o OLS sem pesos, nem de "
            f"significância a 5% com erros-padrão robustos ({cov_type})."
        )

    # Inversão de sinal só pesa na conclusão se o termo for significativo em
    # algum dos ajustes; entre duas estimativas próximas de zero, não muda nada.
    algum_sig = (sinal[["p_wls", "p_wls_robust", "p_ols", "p_ols_robust"]] < 0.05).any(axis=1)
    sinal_relevante, sinal_irrelevante = sinal[algum_sig], sinal[~algum_sig]

    partes = []
    if not sinal_relevante.empty:
        nomes = ", ".join(f"**{_rotulo_termo(v)}**" for v in sinal_relevante["variavel"])
        partes.append(f"Mudam de sinal entre WLS e OLS sem pesos: {nomes}.")
    if not sinal_irrelevante.empty:
        nomes = ", ".join(f"**{_rotulo_termo(v)}**" for v in sinal_irrelevante["variavel"])
        partes.append(
            f"Também mudam de sinal, mas sem significância em nenhum dos ajustes "
            f"(estimativas próximas de zero, a conclusão não muda): {nomes}."
        )
    if sinal_relevante.empty and signif.empty:
        return " ".join(partes)
    if not signif.empty:
        itens = [
            f"**{_rotulo_termo(r['variavel'])}** (p WLS robusto {p_fmt(r['p_wls_robust'])}, "
            f"p OLS robusto {p_fmt(r['p_ols_robust'])})"
            for _, r in signif.iterrows()
        ]
        partes.append(
            f"Mudam de significância a 5% com erros-padrão robustos ({cov_type}): "
            + "; ".join(itens) + "."
        )
    partes.append(
        "Para esses fatores, a conclusão depende da ponderação — reporte os dois "
        "ajustes e interprete com cautela."
    )
    return " ".join(partes)


def interpretar_ponderacao(diag_ols: dict) -> str:
    """Explica, a partir do OLS sem pesos, se há evidência que justifique o WLS."""
    rho = f"{diag_ols['spearman_rho']:+.3f}".replace(".", ",")
    sp = p_fmt(diag_ols["spearman_pvalue"])
    bp = (
        f"Breusch-Pagan do OLS sem pesos: p {p_fmt(diag_ols['bp_pvalue'])} "
        f"({'não rejeita' if diag_ols['bp_homocedastic'] else 'rejeita'} a homocedasticidade)."
    )
    if diag_ols["erro_cai_com_tamanho"]:
        return (
            f"No OLS sem pesos, o tamanho do erro diminui com o nº de alunos do curso "
            f"(Spearman |resíduo| × QT_ALUNOS: ρ = {rho}, p {sp}): cursos pequenos têm "
            f"médias mais ruidosas, o que justifica ponderar por QT_ALUNOS. " + bp
        )
    return (
        f"No OLS sem pesos, não há evidência de que o erro diminua com o nº de alunos "
        f"do curso (Spearman |resíduo| × QT_ALUNOS: ρ = {rho}, p {sp}). A ponderação "
        f"por QT_ALUNOS não é exigida por esse diagnóstico — compare os ajustes na "
        f"tabela de sensibilidade. " + bp
    )


def interpretar_vif(vif_table: pd.DataFrame) -> Tuple[str, str]:
    prob = vif_table[vif_table["vif"] > VIF_MODERADO]
    if prob.empty:
        return "ok", (
            "Não foi detectada multicolinearidade relevante pelos limiares usados "
            "(todos os VIF ≤ 5)."
        )
    worst = prob.sort_values("vif", ascending=False).iloc[0]
    nivel = "severa" if worst["vif"] > VIF_SEVERO else "moderada"
    return "warning", (
        f"Pelos limiares usados, **{label(worst['variavel'])}** apresenta multicolinearidade "
        f"{nivel} com as outras variáveis (VIF = {worst['vif']:.1f}; moderado > 5, severo > 10). "
        f"Isso infla o erro-padrão do coeficiente desta variável e torna a estimativa instável. "
        f"Considere removê-la do modelo."
    )


def interpretar_residuos(diag: dict) -> str:
    from modules.residuals import _SHAPIRO_MAX_N
    partes = []
    if diag["shapiro_normal"]:
        partes.append(
            "**Distribuição dos erros:** Os erros do modelo seguem um padrão normal — "
            "erros pequenos são mais comuns e erros grandes são raros. Isso é o esperado."
        )
    elif not diag.get("shapiro_confiavel", True):
        # n > 5000: o teste rodou numa amostra e é sensível a desvios mínimos.
        limite = f"{_SHAPIRO_MAX_N:,}".replace(",", ".")
        partes.append(
            f"**Distribuição dos erros:** Os erros não seguem exatamente um padrão normal "
            f"(Shapiro-Wilk p {p_fmt(diag['shapiro_pvalue'])}, avaliado em amostra de {limite} "
            f"observações). Com mais de {limite} observações, o teste acusa desvios mínimos e o "
            f"impacto na validade dos resultados é pequeno."
        )
    else:
        # Até 2026-10-14 este ramo dizia "Com mais de 5.000 observações..." mesmo
        # com n de algumas centenas de cursos (ver DEVELOPMENT.md).
        n = diag.get("shapiro_n_usado")
        partes.append(
            f"**Distribuição dos erros:** Os erros não seguem exatamente um padrão normal "
            f"(Shapiro-Wilk p {p_fmt(diag['shapiro_pvalue'])}, {n} cursos). Os intervalos de "
            f"confiança e os p-valores podem ser afetados — confira o QQ-plot para ver se o "
            f"desvio está concentrado nos extremos."
        )
    if diag["bp_homocedastic"]:
        partes.append(
            "**Consistência dos erros:** O modelo erra de forma parecida para todos os grupos. "
            "Não há indício de que a precisão das estimativas varie entre perfis de curso."
        )
    else:
        partes.append(
            f"**Consistência dos erros:** O modelo erra mais para alguns grupos do que para outros "
            f"(p {p_fmt(diag['bp_pvalue'])}). "
            f"Os intervalos de confiança podem ser menos precisos para grupos extremos."
        )
    return "\n\n".join(partes)


def interpretar_shap(shap_summary: pd.DataFrame, y_label: str) -> str:
    if shap_summary.empty:
        return ""
    top = shap_summary.iloc[0]
    second = shap_summary.iloc[1] if len(shap_summary) > 1 else None
    label_top = (" × ".join(label(p) for p in top["variavel"].split(":"))
                 if ":" in top["variavel"] else label(top["variavel"]))
    msg = (
        f"O fator que **mais influencia** a {y_label} é **{label_top}** "
        f"— a diferença entre cursos com valores altos e baixos neste fator "
        f"representa, em média, {top['shap_mean_abs']:.1f} pontos na nota."
    )
    if second is not None:
        label_2 = (" × ".join(label(p) for p in second["variavel"].split(":"))
                   if ":" in second["variavel"] else label(second["variavel"]))
        msg += (f" Em segundo lugar aparece **{label_2}** "
                f"(impacto médio de {second['shap_mean_abs']:.1f} pontos).")
    msg += " O gráfico mostra todos os fatores ordenados do mais para o menos influente."
    return msg
