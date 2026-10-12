"""
Geração de texto interpretativo a partir dos resultados do modelo.

Extraído de app.py (2026-08-29): são funções puras (sem dependência de
Streamlit), então tanto o Streamlit quanto a API (e_xplainenade_rotas.py)
usam exatamente o mesmo texto — nenhuma lógica de interpretação deveria
divergir entre as duas interfaces.
"""
from typing import Tuple

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


def interpretar_modelo(coef_table: pd.DataFrame, metrics: dict, y_label: str) -> str:
    r2, r2_adj, n = metrics["r2"], metrics["r2_adj"], metrics["n_obs"]
    f_p = metrics.get("f_pvalue", 0)

    linhas = [
        f"O modelo de regressão linear múltipla (WLS, ponderado pelo nº de alunos "
        f"presentes de cada curso — QT_ALUNOS) ajustado com {n:,} cursos do ENADE 2021 "
        f"(CC+SI, Brasil inteiro, dados agregados por curso) "
        f"apresenta R² = {r2:.4f} (R² ajustado = {r2_adj:.4f}), explicando "
        f"**{r2*100:.1f}%** da variância (ponderada) nas notas médias de {y_label}. "
        f"O modelo é globalmente significativo (F, p {p_fmt(f_p)}).\n"
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
            sinal = "positivo" if coef > 0 else "negativo"
            movimento = "aumento" if coef > 0 else "redução"
            linhas.append(
                f"• **{lbl}** apresenta efeito {sinal} significativo "
                f"(β = {coef:+.2f}, p {p_fmt(p)}). "
                f"Cada nível adicional está associado a um {movimento} médio de "
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
                    f"• O efeito de **{la}** é moderado por **{lb}** "
                    f"(interação significativa, β = {coef:+.2f}, p {p_fmt(p)}). "
                    f"O sinal negativo indica atenuação mútua dos efeitos individuais."
                )
            else:
                linhas.append(
                    f"• O efeito de **{la}** é amplificado por **{lb}** "
                    f"(interação significativa, β = {coef:+.2f}, p {p_fmt(p)}). "
                    f"Os dois fatores se reforçam mutuamente."
                )

    if nao_sig:
        nomes = ", ".join(
            label(str(r["variavel"])) for r in nao_sig
            if ":" not in str(r["variavel"])
        )
        if nomes:
            linhas.append(
                f"\n**Sem efeito estatisticamente significativo (p ≥ 0,05):** {nomes}. "
                f"Esses fatores não apresentaram associação comprovada com a {y_label} "
                f"nesta amostra."
            )

    return "\n".join(linhas)


def interpretar_vif(vif_table: pd.DataFrame) -> Tuple[str, str]:
    prob = vif_table[vif_table["vif"] > VIF_MODERADO]
    if prob.empty:
        return "ok", (
            "Nenhum problema de correlação entre variáveis detectado. "
            "Os coeficientes do modelo são confiáveis."
        )
    worst = prob.sort_values("vif", ascending=False).iloc[0]
    nivel = "alto" if worst["vif"] > VIF_SEVERO else "moderado"
    return "warning", (
        f"**{label(worst['variavel'])}** tem correlação {nivel} com as outras variáveis "
        f"(VIF = {worst['vif']:.1f}). "
        f"Isso pode tornar o coeficiente desta variável pouco confiável. "
        f"Recomenda-se removê-la do modelo."
    )


def interpretar_residuos(diag: dict) -> str:
    from modules.residuals import _SHAPIRO_MAX_N
    partes = []
    if diag["shapiro_normal"]:
        partes.append(
            "**Distribuição dos erros:** Os erros do modelo seguem um padrão normal — "
            "erros pequenos são mais comuns e erros grandes são raros. Isso é o esperado."
        )
    else:
        nota = (f" (avaliado em amostra de {_SHAPIRO_MAX_N:,} cursos)"
                if not diag.get("shapiro_confiavel", True) else "")
        partes.append(
            f"**Distribuição dos erros:** Os erros não seguem exatamente um padrão normal{nota}. "
            f"Com mais de {_SHAPIRO_MAX_N:,} observações, isso tem impacto pequeno na validade dos resultados."
        )
    if diag["bp_homocedastic"]:
        partes.append(
            "**Consistência dos erros:** O modelo erra de forma parecida para todos os grupos. "
            "Isso indica que os resultados são igualmente confiáveis para diferentes perfis."
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
