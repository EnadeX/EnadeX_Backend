"""
Camada 8 — Gerador de relatório técnico em PDF.

Produz um relatório acessível para não-especialistas, com legendas,
textos explicativos e linguagem clara em cada seção.
"""
import io
import platform
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF

_OUTPUT_DIR = Path(__file__).parent.parent / "outputs"

# Fonte Unicode: Arial no Windows, Liberation Sans no Linux (Streamlit Cloud)
if platform.system() == "Windows":
    _FONT_REGULAR = Path("C:/Windows/Fonts/arial.ttf")
    _FONT_BOLD    = Path("C:/Windows/Fonts/arialbd.ttf")
else:
    _FONT_REGULAR = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")
    _FONT_BOLD    = Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")

_USE_UNICODE = _FONT_REGULAR.exists()

# Paleta de cores
_COR_AZUL    = (41,  98, 168)
_COR_VERDE   = (40, 167,  69)
_COR_AMARELO = (255, 193,  7)
_COR_VERMELHO= (220,  53,  30)
_COR_CINZA   = (108, 117, 125)
_COR_FUNDO   = (245, 247, 250)
_COR_TITULO  = (33,  37,  41)


# ══════════════════════════════════════════════════════════════════════════════
# Classe base
# ══════════════════════════════════════════════════════════════════════════════

class _PDF(FPDF):
    def __init__(self):
        super().__init__()
        if _USE_UNICODE:
            self.add_font("Arial",  fname=str(_FONT_REGULAR))
            self.add_font("Arial", style="B", fname=str(_FONT_BOLD))
            self._f = "Arial"
        else:
            self._f = "Helvetica"
        self.set_margins(15, 20, 15)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_fill_color(*_COR_AZUL)
        self.rect(0, 0, 210, 12, "F")
        self.set_font(self._f, "B", 10)
        self.set_text_color(255, 255, 255)
        self.set_xy(15, 2)
        self.cell(0, 8, "E-XplainENADE  -  Relatorio de Analise Estatistica", align="L")
        self.set_text_color(*_COR_TITULO)
        self.ln(14)

    def footer(self):
        self.set_y(-13)
        self.set_font(self._f, size=8)
        self.set_text_color(*_COR_CINZA)
        self.cell(0, 8, f"Pagina {self.page_no()}", align="C")
        self.set_text_color(*_COR_TITULO)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def titulo_secao(self, numero: str, titulo: str):
        """Cabeçalho de seção com fundo colorido."""
        self.ln(4)
        self.set_fill_color(*_COR_AZUL)
        self.set_text_color(255, 255, 255)
        self.set_font(self._f, "B", 11)
        self.cell(0, 9, f"  {numero}. {titulo}", fill=True,
                  new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*_COR_TITULO)
        self.ln(2)

    def caixa_contexto(self, texto: str):
        """Caixa cinza claro com texto explicativo."""
        self.set_fill_color(*_COR_FUNDO)
        self.set_font(self._f, size=9)
        self.set_text_color(*_COR_CINZA)
        x = self.get_x()
        self.multi_cell(0, 5, texto, fill=True, border=0,
                        new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*_COR_TITULO)
        self.ln(2)

    def caixa_destaque(self, texto: str, cor: tuple = None):
        """Caixa destacada (verde por padrão) para interpretações."""
        r, g, b = cor or (212, 237, 218)
        self.set_fill_color(r, g, b)
        self.set_font(self._f, size=10)
        self.multi_cell(0, 6, texto, fill=True, border=0,
                        new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def metrica(self, label: str, valor: str, largura: float = 55):
        """Bloco de métrica estilo cartão."""
        self.set_fill_color(*_COR_FUNDO)
        self.set_font(self._f, "B", 16)
        self.set_text_color(*_COR_AZUL)
        x, y = self.get_x(), self.get_y()
        self.cell(largura, 10, valor, align="C")
        self.set_xy(x, y + 10)
        self.set_font(self._f, size=8)
        self.set_text_color(*_COR_CINZA)
        self.cell(largura, 5, label, align="C")
        self.set_text_color(*_COR_TITULO)

    def th(self, texto: str, w: float, align: str = "C"):
        """Célula de cabeçalho de tabela."""
        self.set_fill_color(*_COR_AZUL)
        self.set_text_color(255, 255, 255)
        self.set_font(self._f, "B", 9)
        self.cell(w, 7, texto, border=1, fill=True, align=align)
        self.set_text_color(*_COR_TITULO)

    def td(self, texto: str, w: float, align: str = "L",
           fill_color: tuple = None, bold: bool = False):
        """Célula de dado de tabela."""
        if fill_color:
            self.set_fill_color(*fill_color)
        else:
            self.set_fill_color(255, 255, 255)
        self.set_font(self._f, "B" if bold else "", 9)
        self.cell(w, 6, str(texto)[:40], border=1,
                  fill=True, align=align)

    def img_buf(self, fig) -> io.BytesIO:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf


# ══════════════════════════════════════════════════════════════════════════════
# Gráficos
# ══════════════════════════════════════════════════════════════════════════════

def _grafico_shap(shap_summary, code_to_label: Dict) -> plt.Figure:
    labels = [
        " x ".join(code_to_label.get(p, p) for p in v.split(":"))
        if ":" in v else code_to_label.get(v, v)
        for v in shap_summary["variavel"]
    ]
    values = shap_summary["shap_mean_abs"].values

    fig, ax = plt.subplots(figsize=(7, max(3, len(labels) * 0.55)))
    bars = ax.barh(labels[::-1], values[::-1],
                   color=plt.cm.Blues(np.linspace(0.45, 0.85, len(values))))
    ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
    ax.set_xlabel("Influencia media na nota (pontos)", fontsize=9)
    ax.set_title("Quais fatores mais influenciam a nota?", fontsize=10, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def _grafico_residuos(plot_data) -> plt.Figure:
    from scipy import stats

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Resíduos vs fitted
    ax = axes[0]
    ax.scatter(plot_data["fitted"], plot_data["residual"],
               alpha=0.25, s=8, color="#4a90d9")
    ax.axhline(0, color="red", linestyle="--", linewidth=1.2)
    ax.set_xlabel("Nota prevista pelo modelo", fontsize=9)
    ax.set_ylabel("Erro do modelo (residuo)", fontsize=9)
    ax.set_title("Dispersao dos Erros\n(pontos devem ficar espalhados ao redor da linha vermelha)",
                 fontsize=9, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # QQ-plot
    ax2 = axes[1]
    residuals = plot_data["residual"].values
    (osm, osr), (slope, intercept, _) = stats.probplot(residuals)
    ax2.scatter(osm, osr, alpha=0.25, s=8, color="#4a90d9")
    ax2.plot(osm, slope * osm + intercept,
             color="red", linestyle="--", linewidth=1.2)
    ax2.set_xlabel("Padrao teorico esperado", fontsize=9)
    ax2.set_ylabel("Erros reais do modelo", fontsize=9)
    ax2.set_title("Grafico de Normalidade dos Erros\n(pontos devem seguir a linha vermelha)",
                  fontsize=9, fontweight="bold")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Renderizador de texto com markdown simples para fpdf2
# ══════════════════════════════════════════════════════════════════════════════

def _strip_inline(texto: str) -> str:
    """Remove marcadores **negrito** inline, mantendo o texto."""
    return re.sub(r'\*\*(.+?)\*\*', r'\1', texto)


def _render_interpretacao(pdf, texto: str) -> None:
    """
    Renderiza o texto de interpretação automática com formatação nativa fpdf2.

    Regras de parsing:
      - Linha vazia          → espaço vertical
      - Linha só com **...** → cabeçalho de seção (negrito azul)
      - Linha começa com •   → bullet com indentação
      - Demais linhas        → parágrafo normal
    """
    _AZUL_TEXTO  = (29,  78, 137)
    _CINZA_TEXTO = (75,  85,  99)
    _NORMAL      = (33,  37,  41)
    _INDENT      = 6   # mm de indentação dos bullets

    for linha in texto.split("\n"):
        linha = linha.strip()

        if not linha:
            pdf.ln(3)
            continue

        # Cabeçalho de seção: toda a linha é **texto** ou **texto:**
        if re.match(r'^\*\*.+\*\*:?$', linha):
            header = _strip_inline(linha).rstrip(":")
            pdf.set_font(pdf._f, "B", 10)
            pdf.set_text_color(*_AZUL_TEXTO)
            pdf.ln(1)
            pdf.multi_cell(0, 6, header + ":", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*_NORMAL)
            pdf.set_font(pdf._f, "", 10)

        # Bullet
        elif linha.startswith("•"):
            content = _strip_inline(linha[1:].strip())
            pdf.set_font(pdf._f, "", 10)
            pdf.set_text_color(*_NORMAL)
            # Primeira célula invisível para indentação
            pdf.cell(_INDENT)
            pdf.multi_cell(0, 5.5, "•  " + content,
                           new_x="LMARGIN", new_y="NEXT")

        # Parágrafo normal
        else:
            content = _strip_inline(linha)
            pdf.set_font(pdf._f, "", 10)
            pdf.set_text_color(*_NORMAL)
            pdf.multi_cell(0, 6, content, new_x="LMARGIN", new_y="NEXT")


# ══════════════════════════════════════════════════════════════════════════════
# Função pública
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(session: Dict[str, Any], filename: str = "relatorio.pdf") -> Path:
    """
    Gera relatório PDF acessível a partir do dicionário de sessão.

    Chaves esperadas: exec_id, config, formula, y_label,
    model_metrics, coef_table, vif_table, residuals_diag,
    shap_summary, interpretacao_modelo, interpretacao_residuos,
    interpretacao_shap, plot_data
    """
    from config.variable_map import CODE_TO_LABEL
    from modules.multicollinearity import VIF_MODERADO, VIF_SEVERO

    pdf = _PDF()
    pdf.add_page()

    y_label  = session.get("y_label", "Nota Geral")
    filtros  = session.get("config", {}).get("filtros", {})
    hoje     = date.today().strftime("%d/%m/%Y")

    # ── Capa ──────────────────────────────────────────────────────────────────
    pdf.set_font(pdf._f, "B", 18)
    pdf.set_text_color(*_COR_AZUL)
    pdf.cell(0, 12, "Relatorio de Analise Estatistica", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf._f, size=11)
    pdf.set_text_color(*_COR_CINZA)
    pdf.cell(0, 7, f"Microdados ENADE 2021  |  Gerado em {hoje}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_COR_TITULO)
    pdf.ln(6)

    # ── 1. Poder explicativo ──────────────────────────────────────────────────
    metrics = session.get("model_metrics", {})
    if metrics:
        pdf.titulo_secao("1", f"Quanto o modelo explica a {y_label}?")

        pdf.caixa_contexto(
            "O 'Poder Explicativo' (R2) mostra qual percentual da variacao (ponderada "
            "pelo tamanho de cada curso) nas notas e explicado pelos fatores selecionados. "
            "Quanto mais alto, melhor o modelo descreve a realidade dos dados."
        )

        # Métricas em linha — y0 fixo para garantir alinhamento das três colunas
        r2_pct = f"{metrics['r2']*100:.1f}%"
        n      = f"{metrics['n_obs']:,}"
        r2adj  = f"{metrics['r2_adj']:.4f}"

        y0 = pdf.get_y()
        pdf.set_xy(15,  y0); pdf.metrica("Poder Explicativo (R2)", r2_pct, 60)
        pdf.set_xy(75,  y0); pdf.metrica("Cursos Analisados",      n,      60)
        pdf.set_xy(135, y0); pdf.metrica("R2 Ajustado",            r2adj,  60)
        pdf.set_xy(15, y0 + 17)
        pdf.ln(4)

        # A interpretacao completa e exibida apos a tabela de coeficientes (Secao 2)

    # ── 2. Efeito de cada fator ───────────────────────────────────────────────
    coef = session.get("coef_table")
    if coef is not None:
        pdf.titulo_secao("2", f"Efeito de cada fator na {y_label}")

        pdf.caixa_contexto(
            "Como ler esta tabela:\n"
            "  Efeito: quanto a nota muda, em media, a cada nivel a mais neste fator\n"
            "  Direcao: se o fator aumenta (↑) ou diminui (↓) a nota do curso\n"
            "  Confiavel?: 'Sim' = efeito improvavel de ser coincidencia (p < 0,05)\n"
            "  IC 95%: intervalo onde o efeito verdadeiro esta em 95% das vezes"
        )

        # Cabeçalho
        widths = [62, 22, 22, 22, 18, 34]
        headers = ["Fator", "Efeito", "Direcao", "Confiavel?", "P-valor", "IC 95%"]
        for h, w in zip(headers, widths):
            pdf.th(h, w)
        pdf.ln()

        for _, row in coef.iterrows():
            var = str(row["variavel"])
            if var == "Intercept":
                continue
            label = " x ".join(CODE_TO_LABEL.get(p, p) for p in var.split(":")) \
                    if ":" in var else CODE_TO_LABEL.get(var, var)
            c, p  = row["coeficiente"], row["p_valor"]
            sig   = p < 0.05
            p_str = "< 0,001" if p < 0.001 else f"{p:.3f}".replace(".", ",")
            ic    = f"[{row['ic_inf_95']:.2f} ; {row['ic_sup_95']:.2f}]"
            fill  = (212, 237, 218) if sig else (255, 255, 255)

            vals = [
                label[:38],
                f"{c:+.2f}",
                "Aumenta" if c > 0 else "Diminui",
                "Sim" if sig else "Nao",
                p_str,
                ic,
            ]
            aligns = ["L", "C", "C", "C", "C", "C"]
            for v, w, a in zip(vals, widths, aligns):
                pdf.td(v, w, a, fill_color=fill)
            pdf.ln()

        pdf.ln(2)
        pdf.set_font(pdf._f, size=8)
        pdf.set_text_color(*_COR_CINZA)
        pdf.cell(0, 5, "Legenda: verde = efeito comprovado (p < 0,05)  |  "
                       "IC 95% = intervalo de confianca de 95%",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_COR_TITULO)
        pdf.ln(4)

        # 2.2 Interpretação automática (formato TCC)
        interp = session.get("interpretacao_modelo", "")
        if interp:
            pdf.ln(2)
            # Cabeçalho da subseção com fundo azul claro
            pdf.set_fill_color(235, 245, 255)
            pdf.set_draw_color(196, 220, 255)
            pdf.set_font(pdf._f, "B", 10)
            pdf.set_text_color(*_COR_AZUL)
            pdf.cell(0, 8, "  Interpretacao Automatica dos Resultados",
                     fill=True, border=1, new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(0, 0, 0)
            pdf.set_text_color(*_COR_TITULO)
            pdf.ln(3)
            _render_interpretacao(pdf, interp)
            pdf.ln(2)

    # ── 3. Correlação entre variáveis (VIF) ──────────────────────────────────
    vif = session.get("vif_table")
    if vif is not None:
        pdf.titulo_secao("3", "Correlacao entre as Variaveis (VIF)")

        pdf.caixa_contexto(
            "O que e esta analise: verifica se as variaveis escolhidas sao muito parecidas "
            "entre si. Quando duas variaveis andam sempre juntas (ex: renda e escolaridade da mae), "
            "os coeficientes ficam instáveis e menos confiáveis.\n\n"
            "Como interpretar:\n"
            "  Verde  (VIF <= 5): sem problema\n"
            "  Amarelo (VIF 5-10): atencao — correlacao moderada\n"
            "  Vermelho (VIF > 10): problema — considere remover a variavel"
        )

        widths_v = [90, 30, 60]
        for h, w in zip(["Fator", "VIF", "Situacao"], widths_v):
            pdf.th(h, w)
        pdf.ln()

        for _, row in vif.iterrows():
            label = CODE_TO_LABEL.get(row["variavel"], row["variavel"])
            v     = row["vif"]
            if v > VIF_SEVERO:
                fill = (255, 204, 204)
                sit  = "Problema (VIF > 10)"
            elif v > VIF_MODERADO:
                fill = (255, 243, 205)
                sit  = "Atencao (VIF > 5)"
            else:
                fill = (212, 237, 218)
                sit  = "OK"
            pdf.td(label[:42], 90, "L", fill)
            pdf.td(f"{v:.2f}", 30, "C", fill)
            pdf.td(sit, 60, "L", fill)
            pdf.ln()

        pdf.ln(4)
        interp_vif = session.get("interpretacao_vif", "")
        if interp_vif:
            fill_cor = (212, 237, 218) if "OK" in interp_vif or "ok" in interp_vif \
                       else (255, 243, 205)
            pdf.caixa_destaque(interp_vif, fill_cor)

    # ── 4. Diagnóstico de Resíduos ───────────────────────────────────────────
    diag = session.get("residuals_diag", {})
    if diag:
        pdf.add_page()
        pdf.titulo_secao("4", "Diagnostico de Residuos")

        pdf.caixa_contexto(
            "Testes formais que verificam se os pressupostos do modelo sao atendidos "
            "(sobre os residuos ponderados pelo tamanho de cada curso).\n\n"
            "Normalidade (Shapiro-Wilk): H0 = residuos seguem distribuicao normal.\n"
            "Homocedasticidade (Breusch-Pagan): H0 = variancia dos erros e constante.\n"
            "Nivel de significancia adotado: 5% (alpha = 0,05)."
        )

        sw_ok    = diag["shapiro_normal"]
        bp_ok    = diag["bp_homocedastic"]
        sw_n     = diag.get("shapiro_n_usado", 5000)
        sw_conf  = diag.get("shapiro_confiavel", True)
        n_obs    = session.get("model_metrics", {}).get("n_obs", 0)

        def _pfmt(p: float) -> str:
            return "< 0,001" if p < 0.001 else f"{p:.3f}".replace(".", ",")

        sw_note = f" (amostra {sw_n:,})" if not sw_conf else ""
        sw_h0   = "Residuos normalmente distribuidos"
        bp_h0   = "Variancia dos erros e constante"

        # Tabela formal de testes
        widths_t = [44, 66, 24, 22, 24]
        for h, w in zip(["Teste", "H0 (hipotese nula)", "Estat.", "p-valor", "Decisao"],
                        widths_t):
            pdf.th(h, w, align="C")
        pdf.ln()

        for (nome, h0, stat, pval, ok) in [
            (f"Shapiro-Wilk{sw_note}", sw_h0,
             f"{diag['shapiro_stat']:.4f}", _pfmt(diag["shapiro_pvalue"]), sw_ok),
            ("Breusch-Pagan", bp_h0,
             f"{diag['bp_stat']:.4f}",    _pfmt(diag["bp_pvalue"]),      bp_ok),
        ]:
            fill = (212, 237, 218) if ok else (255, 243, 205)
            decisao = "Nao rejeita" if ok else "Rejeita"
            pdf.td(nome,    widths_t[0], "L", fill)
            pdf.td(h0,      widths_t[1], "L", fill)
            pdf.td(stat,    widths_t[2], "C", fill)
            pdf.td(pval,    widths_t[3], "C", fill, bold=True)
            pdf.td(decisao, widths_t[4], "C", fill, bold=True)
            pdf.ln()

        pdf.ln(5)

        # Mensagens de diagnóstico específicas
        if not bp_ok:
            contexto_n = (
                f" Com n = {n_obs:,}, o teste e altamente sensivel e detecta "
                f"variacoes minimas de variancia."
                if n_obs > 5000 else ""
            )
            msg_bp = (
                f"Indicios de heterocedasticidade detectados "
                f"(Breusch-Pagan p {_pfmt(diag['bp_pvalue'])}).{contexto_n} "
                f"Os coeficientes continuam nao-viesados, mas os erros-padrao e "
                f"p-valores podem estar subestimados. Considere: transformacao da "
                f"variavel dependente (ex: escala logaritmica) ou uso de erros-padrao "
                f"robustos a heterocedasticidade (HC3)."
            )
            pdf.caixa_destaque(msg_bp, (255, 243, 205))

        if not sw_ok:
            if not sw_conf:
                msg_sw = (
                    f"Leve desvio de normalidade nos residuos "
                    f"(Shapiro-Wilk p {_pfmt(diag['shapiro_pvalue'])}, "
                    f"avaliado em amostra de {sw_n:,} obs.). "
                    f"Com n = {n_obs:,}, o Teorema Central do Limite garante a validade "
                    f"assintotica dos estimadores. Impacto pratico minimo."
                )
                pdf.caixa_destaque(msg_sw, (219, 234, 254))
            else:
                msg_sw = (
                    f"Indicios de nao-normalidade dos residuos "
                    f"(Shapiro-Wilk p {_pfmt(diag['shapiro_pvalue'])}). "
                    f"Intervalos de confianca e p-valores podem estar afetados. "
                    f"Verifique outliers ou considere transformacao da variavel dependente."
                )
                pdf.caixa_destaque(msg_sw, (255, 243, 205))

        if sw_ok and bp_ok:
            msg_ok = (
                f"Todos os pressupostos verificados. Residuos normalmente distribuidos "
                f"(Shapiro-Wilk p {_pfmt(diag['shapiro_pvalue'])}) e variancia constante "
                f"(Breusch-Pagan p {_pfmt(diag['bp_pvalue'])}). "
                f"O modelo e metodologicamente adequado para estes dados."
            )
            pdf.caixa_destaque(msg_ok, (212, 237, 218))

        # Gráficos de resíduos
        plot_data = session.get("plot_data")
        if plot_data is not None:
            pdf.ln(3)
            fig = _grafico_residuos(plot_data)
            buf = pdf.img_buf(fig)
            pdf.image(buf, w=178)

            pdf.ln(2)
            pdf.set_font(pdf._f, size=8)
            pdf.set_text_color(*_COR_CINZA)
            pdf.multi_cell(0, 5,
                "Grafico da esquerda: pontos espalhados em volta de y = 0 indicam "
                "homocedasticidade (variancia constante dos erros).\n"
                "Grafico da direita (QQ-plot): pontos proximos a linha diagonal indicam "
                "distribuicao normal dos residuos. Desvios nas extremidades indicam "
                "erros maiores para notas muito altas ou muito baixas.",
                new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*_COR_TITULO)

    # ── 5. Quais fatores mais influenciam (SHAP) ─────────────────────────────
    shap_summary = session.get("shap_summary")
    if shap_summary is not None:
        pdf.add_page()
        pdf.titulo_secao("5", f"Quais fatores mais influenciam a {y_label}?")

        pdf.caixa_contexto(
            "O grafico abaixo mostra a importancia relativa de cada fator. "
            "Quanto maior a barra, maior o impacto daquele fator para explicar "
            "as diferencas de notas entre os cursos.\n\n"
            "Atencao: este grafico mostra O QUANTO cada fator importa (magnitude), "
            "nao a direcao do efeito. Para saber se o fator aumenta ou diminui a nota, "
            "consulte a Secao 2."
        )

        interp_shap = session.get("interpretacao_shap", "")
        if interp_shap:
            clean = interp_shap.replace("**", "")
            pdf.caixa_destaque(clean)

        fig = _grafico_shap(shap_summary, CODE_TO_LABEL)
        buf = pdf.img_buf(fig)
        pdf.image(buf, w=160)

        pdf.ln(2)
        pdf.set_font(pdf._f, size=8)
        pdf.set_text_color(*_COR_CINZA)
        pdf.multi_cell(0, 5,
            "Legenda: o valor ao lado de cada barra indica a influencia media em pontos "
            "— por exemplo, '7,95' significa que este fator esta associado, em media, "
            "a uma diferenca de 7,95 pontos na nota entre cursos com valores "
            "altos e baixos nesta variavel.",
            new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_COR_TITULO)

    # ── 6. Limitações da análise ──────────────────────────────────────────────
    pdf.titulo_secao("6", "Limitacoes da Analise")

    pdf.caixa_contexto(
        "Toda analise estatistica tem limites de validade. Os pontos abaixo "
        "delimitam o alcance das conclusoes deste relatorio."
    )

    limitacoes = [
        "Associacao nao e causalidade: os coeficientes indicam relacoes "
        "estatisticas entre variaveis, nao efeitos causais comprovados.",
        "Modelo linear: o WLS captura relacoes lineares; efeitos nao-lineares "
        "ou de limiar nao sao representados.",
        "Recorte especifico: ENADE 2021, Brasil inteiro, cursos de "
        "Ciencia da Computacao e Sistemas de Informacao, dados agregados por "
        "curso (nao por estudante individual) — generalizacoes para outros "
        "anos, cursos ou para o nivel individual do estudante exigem cautela "
        "(risco de falacia ecologica).",
        "Variaveis omitidas: fatores nao incluidos no modelo (ex: qualidade da "
        "IES, trajetoria escolar previa) podem influenciar os resultados.",
        "Variaveis ordinais (renda, escolaridade, horas de estudo) foram "
        "tratadas como continuas, convencao aceita em pesquisa educacional, "
        "mas que assume intervalos equivalentes entre niveis.",
        "Modelo ponderado (WLS): cursos com mais alunos presentes pesam mais no "
        "ajuste do que cursos com poucos alunos, pois suas medias sao "
        "estatisticamente mais confiaveis — os testes de residuos desta secao "
        "avaliam o residuo ja ponderado, nao o residuo bruto.",
    ]
    pdf.set_font(pdf._f, "", 10)
    pdf.set_text_color(*_COR_TITULO)
    for item in limitacoes:
        pdf.cell(6)
        pdf.multi_cell(0, 5.5, "-  " + item, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # ── Bloco de rastreabilidade (fim do relatório) ───────────────────────────
    pdf.ln(6)
    pdf.set_fill_color(*_COR_FUNDO)
    pdf.set_draw_color(220, 220, 220)
    pdf.set_font(pdf._f, "B", 8)
    pdf.set_text_color(*_COR_CINZA)
    pdf.cell(0, 6, "  Informacoes de rastreabilidade", fill=True, border=1,
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf._f, size=8)
    pdf.set_fill_color(250, 250, 252)
    pdf.multi_cell(0, 5,
        f"  Exec-ID: {session.get('exec_id', 'N/A')}\n"
        f"  Variavel analisada: {y_label}\n"
        f"  Curso: {filtros.get('curso', 'Todos')}  |  "
        f"Tipo de IES: {filtros.get('tipo_ies', 'Todas')}  |  "
        f"Ano: {filtros.get('ano', '2021')}\n"
        f"  Formula: {session.get('formula', 'N/A')}",
        fill=True, border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(0, 0, 0)
    pdf.set_text_color(*_COR_TITULO)

    # ── Rodapé com nota metodológica ─────────────────────────────────────────
    if not filtros:
        filtro_desc = "recorte Brasil inteiro, CC+SI, agregado por curso, conforme filtros da interface"
    else:
        curso_txt = filtros.get("curso", "")
        ies_txt   = filtros.get("tipo_ies", "")
        ano_txt   = filtros.get("ano", "2021")
        partes = ["Brasil inteiro", "agregado por curso"]
        partes.append(
            f"curso: {curso_txt}" if curso_txt and not curso_txt.startswith("Todos")
            else "cursos CC e SI"
        )
        if ies_txt and ies_txt not in ("Todas", ""):
            partes.append(f"IES: {ies_txt.lower()}")
        if ano_txt:
            partes.append(f"ano {ano_txt}")
        filtro_desc = ", ".join(partes)

    pdf.ln(8)
    pdf.set_font(pdf._f, size=8)
    pdf.set_text_color(*_COR_CINZA)
    pdf.multi_cell(0, 5,
        "Nota metodologica: os resultados foram obtidos por regressao linear multipla "
        "ponderada (WLS via statsmodels, peso = QT_ALUNOS) com explicabilidade SHAP "
        "(LinearExplainer, Lundberg & Lee, 2017). "
        f"Os dados sao os Microdados ENADE 2021 (INEP), versao LGPD ({filtro_desc}).",
        new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_COR_TITULO)

    _OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = _OUTPUT_DIR / filename
    pdf.output(str(output_path))
    return output_path
