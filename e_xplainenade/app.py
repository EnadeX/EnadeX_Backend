"""
Camada 9 — Interface e orquestração (Streamlit).

Layout linear: todas as 7 etapas numa única página vertical.
Cada seção aparece progressivamente conforme os pré-requisitos são atendidos:
  - Etapa 1: sempre visível
  - Etapa 2: aparece após base carregada
  - Etapas 3–7: aparecem após modelagem executada
"""
import json
import uuid
import itertools

import pandas as pd
import streamlit as st

from config.variable_map import (
    CODE_TO_LABEL, VALUE_LABELS,
    Y_OPTS, X_OPTS, CODE_TO_UI_LABEL, CURSO_OPTS, IES_OPTS, X_CATEGORIAS,
)
from modules import loader
from modules.hypothesis import build_hypothesis
from modules.modeling import fit_ols, get_coefficients_table, get_model_metrics
from modules.multicollinearity import (
    compute_vif, has_multicollinearity, get_variable_to_remove,
    VIF_MODERADO, VIF_SEVERO,
)
from modules.residuals import get_residuals_plot_data, get_qqplot_data, run_diagnostics
from modules.explainability import compute_shap, get_shap_summary
from modules.report import generate_report
from modules.interpretation import (
    label as _label, p_fmt as _p_fmt,
    interpretar_modelo as _interpretar_modelo,
    interpretar_vif as _interpretar_vif,
    interpretar_residuos as _interpretar_residuos,
    interpretar_shap as _interpretar_shap,
)

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="E-XplainENADE",
    page_icon="E",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS Global ────────────────────────────────────────────────────────────────
st.markdown("""
<style>

/* ── Layout base ─────────────────────────────────────────────────────── */
.block-container {
    padding-top: 1.4rem !important;
    padding-bottom: 3rem !important;
    max-width: 1160px !important;
}

/* ── Sistema de sombras (variáveis reutilizáveis via inline style) ───── */
/* shadow-sm  : 0 1px 3px rgba(15,23,42,.06), 0 4px 16px rgba(15,23,42,.04)  */
/* shadow-md  : 0 2px 6px rgba(15,23,42,.07), 0 8px 24px rgba(15,23,42,.06)  */

/* ── Cards Streamlit (st.container border=True) ──────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 16px !important;
    box-shadow: 0 1px 3px rgba(15,23,42,.06), 0 4px 16px rgba(15,23,42,.04) !important;
    background: #ffffff !important;
    padding: 4px 8px !important;
}

/* ── Hero ────────────────────────────────────────────────────────────── */
.exn-hero {
    border-radius: 24px;
    border: 1px solid #1e293b;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #2d1b69 100%);
    color: white;
    padding: 30px 36px;
    margin-bottom: 8px;
    box-shadow: 0 8px 32px rgba(15,23,42,.18);
}
.exn-hero h1 {
    font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em;
    margin: 0 0 8px 0; color: white; line-height: 1.2;
}
.exn-hero p {
    color: #cbd5e1; font-size: 14px; line-height: 1.65;
    margin: 0 0 22px 0; max-width: 640px;
}
.exn-meta-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
}
.exn-meta-card {
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.07);
    padding: 14px 16px;
}
.exn-meta-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: #94a3b8; font-weight: 600; }
.exn-meta-value { font-size: 15px; font-weight: 700; margin-top: 5px; color: white; }
.exn-meta-sub   { font-size: 11px; color: #64748b; margin-top: 3px; }

/* ── Etapa header ────────────────────────────────────────────────────── */
.exn-step {
    display: flex; align-items: center; gap: 16px;
    border-radius: 16px;
    border: 1px solid #e2e8f0;
    border-left: 5px solid #7c3aed;
    background: #ffffff;
    padding: 16px 22px;
    box-shadow: 0 1px 3px rgba(15,23,42,.06), 0 4px 16px rgba(15,23,42,.04);
    margin-bottom: 22px;
}
.exn-step-num {
    width: 36px; height: 36px; border-radius: 50%;
    background: #7c3aed; color: white; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 15px;
    box-shadow: 0 2px 8px rgba(124,58,237,.35);
}
.exn-step-title { font-size: 17px; font-weight: 700; color: #1e1b4b; line-height: 1.2; }
.exn-step-desc  { font-size: 13px; color: #7c3aed; margin-top: 3px; font-weight: 500; }

/* ── Pills ───────────────────────────────────────────────────────────── */
.exn-pill {
    display: inline-flex; align-items: center; border-radius: 9999px;
    padding: 3px 11px; font-size: 12px; font-weight: 600;
    letter-spacing: 0.01em; white-space: nowrap;
}
.pill-violet { border: 1px solid #ddd6fe; background: #f5f3ff; color: #6d28d9; }
.pill-blue   { border: 1px solid #bfdbfe; background: #eff6ff; color: #1e40af; }
.pill-green  { border: 1px solid #bbf7d0; background: #f0fdf4; color: #166534; }
.pill-amber  { border: 1px solid #fde68a; background: #fffbeb; color: #92400e; }
.pill-fuchsia{ border: 1px solid #f5d0fe; background: #fdf4ff; color: #86198f; }
.pill-slate  { border: 1px solid #cbd5e1; background: #f1f5f9; color: #475569; }

/* ── Filter label (dentro de st.container) ───────────────────────────── */
.exn-filter-label {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.09em; color: #7c3aed; margin-bottom: 10px;
    padding-bottom: 8px; border-bottom: 1px solid #ede9fe;
}

/* ── Var group header ────────────────────────────────────────────────── */
.exn-var-group-header {
    font-size: 13px; font-weight: 600; color: #475569;
    margin-bottom: 8px; margin-top: 4px;
    display: flex; align-items: center; gap: 8px;
}

/* ── Section divider ─────────────────────────────────────────────────── */
.exn-section-divider {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 40px 0 36px 0;
}

/* ── Expanders ───────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    background: #ffffff !important;
    box-shadow: 0 1px 3px rgba(15,23,42,.04) !important;
}

/* ── Streamlit alerts ────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
}

/* ── Streamlit dataframe ─────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    overflow: hidden;
}

/* ── Oculta sidebar e seta ───────────────────────────────────────────── */
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* ── Remove padding extra do block-container interno ─────────────────── */
.main .block-container > div:first-child { padding-top: 0 !important; }

</style>
""", unsafe_allow_html=True)

# ── Constantes de UI ──────────────────────────────────────────────────────────
# Y_OPTS, X_OPTS, CODE_TO_UI_LABEL, CURSO_OPTS, IES_OPTS, X_CATEGORIAS agora
# vêm de config/variable_map.py (compartilhadas com e_xplainenade_rotas.py).

ANOS_OPTS = {"2021": True, "2019": False, "2018": False, "2017": False}

_PREFIXOS_NAO_ANALITICOS = ("DS_", "CO_RS_I", "NU_ITEM_", "TP_PR_", "TP_SFG_", "TP_SCE_")
_MIN_REGISTROS = 50

def _n_vars_analiticas(df: pd.DataFrame) -> int:
    return sum(1 for c in df.columns
               if not any(c.startswith(p) for p in _PREFIXOS_NAO_ANALITICOS))

DEFAULT_X = ["Renda Familiar", "Escolaridade da Mãe", "Horas de Estudo por Semana"]

@st.cache_data(show_spinner=False)
def _carregar_dados(grupos_tuple, ies_filter_tuple):
    """Carrega a base agregada por curso a partir do Supabase, aplicando os filtros da UI."""
    grupos     = list(grupos_tuple)     if grupos_tuple     else None
    ies_filter = list(ies_filter_tuple) if ies_filter_tuple else None
    return loader.get_dataset_from_supabase(grupos=grupos, ies_filter=ies_filter)


# ── Exec-ID da sessão ─────────────────────────────────────────────────────────
if "exec_id" not in st.session_state:
    st.session_state.exec_id = str(uuid.uuid4())


# ── Funções auxiliares ────────────────────────────────────────────────────────
# _label e _p_fmt agora vêm de modules.interpretation (import com alias no topo).

def _coef_table_display(coef_table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in coef_table.iterrows():
        var = str(row["variavel"])
        if var == "Intercept":
            continue
        lbl = " × ".join(_label(p) for p in var.split(":")) if ":" in var else _label(var)
        coef, p = row["coeficiente"], row["p_valor"]
        rows.append({
            "Fator":          lbl,
            "Efeito na Nota": f"{coef:+.2f}",
            "Direção":        "↑ Aumenta" if coef > 0 else "↓ Diminui",
            "Confiável?":     "Sim" if p < 0.05 else "Não",
            "P-valor":        _p_fmt(p),
            "IC 95%":         f"[{row['ic_inf_95']:.2f} ; {row['ic_sup_95']:.2f}]",
        })
    return pd.DataFrame(rows)


# Funções de interpretação (_interpretar_modelo/_vif/_residuos/_shap) migraram
# para modules/interpretation.py (import com alias no topo do arquivo).

# ── Estilos de tabela ─────────────────────────────────────────────────────────

def _style_vif(df: pd.DataFrame):
    vif_col = "VIF" if "VIF" in df.columns else "vif"
    def color_row(row):
        v = row[vif_col]
        if v > VIF_SEVERO:
            bg, txt = "#c0392b", "#ffffff"
        elif v > VIF_MODERADO:
            bg, txt = "#f39c12", "#212529"
        else:
            bg, txt = "#27ae60", "#ffffff"
        return [f"background-color: {bg}; color: {txt}; font-weight: bold"] * len(row)
    return df.style.apply(color_row, axis=1).format({vif_col: "{:.2f}"})


def _style_coef_display(df: pd.DataFrame):
    def color(row):
        ok = row["Confiável?"] == "Sim"
        bg = "#1e8449" if ok else "#616a6b"
        return [f"background-color: {bg}; color: #ffffff; font-size: 13px"] * len(row)
    return df.style.apply(color, axis=1)


# ── Componentes visuais ───────────────────────────────────────────────────────

def _hero():
    exec_id_short = st.session_state.exec_id[:8]
    df_loaded  = "df" in st.session_state
    model_done = "model_result" in st.session_state

    status_badge = (
        '<span class="exn-pill" style="background:rgba(16,185,129,0.18);'
        'border:1px solid rgba(16,185,129,0.35);color:#6ee7b7;">Base carregada</span>'
        if df_loaded else
        '<span class="exn-pill" style="background:rgba(255,255,255,0.08);'
        'border:1px solid rgba(255,255,255,0.15);color:#94a3b8;">Aguardando dados</span>'
    )
    model_badge = (
        '<span class="exn-pill" style="background:rgba(139,92,246,0.22);'
        'border:1px solid rgba(139,92,246,0.38);color:#c4b5fd;">Modelo pronto</span>'
        if model_done else ""
    )
    st.markdown(f"""
    <div class="exn-hero">
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;">
        <span class="exn-pill" style="background:rgba(255,255,255,0.1);
              border:1px solid rgba(255,255,255,0.15);color:#e2e8f0;">
          Hipóteses e Modelagem Explicável
        </span>
        {status_badge}
        {model_badge}
      </div>
      <h1>E-XplainENADE</h1>
      <p>Modelagem estatística multivariada explicável dos microdados ENADE.
         Defina hipóteses, ajuste modelos WLS, diagnostique pressupostos
         e interprete resultados com SHAP — reprodutível e rastreável.</p>
      <div class="exn-meta-grid">
        <div class="exn-meta-card">
          <div class="exn-meta-label">Método</div>
          <div class="exn-meta-value">Regressão WLS</div>
          <div class="exn-meta-sub">confirmatório · ponderado · statsmodels</div>
        </div>
        <div class="exn-meta-card">
          <div class="exn-meta-label">Explicabilidade</div>
          <div class="exn-meta-value">SHAP Linear</div>
          <div class="exn-meta-sub">Lundberg &amp; Lee, 2017</div>
        </div>
        <div class="exn-meta-card">
          <div class="exn-meta-label">Exec-ID</div>
          <div class="exn-meta-value">{exec_id_short}…</div>
          <div class="exn-meta-sub">seed 42 · reprodutível</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _etapa_header(numero: int, titulo: str, descricao: str = ""):
    desc_html = f"<div class='exn-step-desc'>{descricao}</div>" if descricao else ""
    st.markdown(f"""
    <div class="exn-step">
      <div class="exn-step-num">{numero}</div>
      <div style="flex:1;">
        <div class="exn-step-title">{titulo}</div>
        {desc_html}
      </div>
      <span class="exn-pill pill-violet">E-XplainENADE</span>
    </div>
    """, unsafe_allow_html=True)


def _section_divider():
    st.markdown('<hr class="exn-section-divider">', unsafe_allow_html=True)


def _metric_row(items: list):
    """items: [(valor, label, tipo)] — tipo in {dark, violet, blue, slate, green}"""
    _shadow = "0 1px 3px rgba(15,23,42,.07), 0 6px 20px rgba(15,23,42,.05)"
    color_map = {
        "dark":   ("#0f172a", "white",   "#64748b", ""),
        "violet": ("#f5f3ff", "#3b0764", "#7c3aed", "border:1px solid #ddd6fe;"),
        "blue":   ("#eff6ff", "#1e3a8a", "#3b82f6", "border:1px solid #bfdbfe;"),
        "slate":  ("#ffffff", "#1e293b", "#64748b", "border:1px solid #e2e8f0;"),
        "green":  ("#f0fdf4", "#14532d", "#16a34a", "border:1px solid #bbf7d0;"),
    }
    cols = st.columns(len(items), gap="small")
    for col, (valor, lbl, tipo) in zip(cols, items):
        bg, txt, lbl_c, border = color_map.get(tipo, color_map["slate"])
        col.markdown(f"""
        <div style="border-radius:16px;background:{bg};padding:18px 20px;
                    {border}box-shadow:{_shadow};">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:.09em;
                      font-weight:700;color:{lbl_c};margin-bottom:8px;">{lbl}</div>
          <div style="font-size:22px;font-weight:800;color:{txt};
                      letter-spacing:-0.01em;line-height:1;">{valor}</div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HERO + botão Nova Análise
# ══════════════════════════════════════════════════════════════════════════════
_hero()

_, _col_reset = st.columns([5, 1])
with _col_reset:
    if st.button("Nova Análise", use_container_width=True,
                 help="Limpa a sessão e reinicia do zero"):
        for key in list(st.session_state.keys()):
            if key != "exec_id":
                del st.session_state[key]
        st.session_state.exec_id = str(uuid.uuid4())
        st.rerun()

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 1 — Seleção de Base  (sempre visível)
# ══════════════════════════════════════════════════════════════════════════════
_etapa_header(1, "Seleção de Base",
              "Escolha o recorte a ser analisado — os dados já fazem parte do sistema")

# ── Fonte de dados (Supabase) ─────────────────────────────────────────────────
# Sem checagem prévia de arquivo local: a base agora vem do banco compartilhado
# do ecossistema EnadeX. Se as tabelas ainda não tiverem dados, o erro aparece
# de forma amigável ao clicar em "Carregar Base" (ver bloco abaixo).
with st.container(border=True):
    st.markdown('<div class="exn-filter-label">Base de dados (Supabase)</div>',
                unsafe_allow_html=True)
    st.markdown(
        "**Microdados ENADE 2021 (INEP/LGPD)** · Brasil inteiro · "
        "Ciência da Computação + Sistemas de Informação · **agregado por curso** "
        "(médias/proporções calculadas sobre os estudantes presentes de cada curso)"
    )
    st.caption(
        "Fonte: banco de dados compartilhado do ecossistema EnadeX (Supabase), "
        "tabelas `tbl_arq1_2021` … `tbl_arq29_2021` — agregadas por `CO_CURSO` em "
        "tempo real a cada carregamento (`modules/etl.py::load_raw_from_supabase`). "
        "Cada linha representa um **curso**, não um estudante individual — ver "
        "seção de limitações do relatório para o porquê dessa granularidade."
    )

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ── Filtros ───────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3, gap="medium")

with col1:
    with st.container(border=True):
        st.markdown('<div class="exn-filter-label">Ano</div>', unsafe_allow_html=True)
        ano_sel = st.radio("Ano", options=list(ANOS_OPTS.keys()),
                           label_visibility="collapsed")
        if not ANOS_OPTS[ano_sel]:
            st.caption(f"Testes iniciais apenas para o ano de 2021.")

with col2:
    with st.container(border=True):
        st.markdown('<div class="exn-filter-label">Curso</div>', unsafe_allow_html=True)
        curso_sel = st.radio("Curso", options=list(CURSO_OPTS.keys()),
                             label_visibility="collapsed")

with col3:
    with st.container(border=True):
        st.markdown('<div class="exn-filter-label">Tipo de IES</div>', unsafe_allow_html=True)
        ies_sel = st.radio("Tipo de IES", options=list(IES_OPTS.keys()),
                           label_visibility="collapsed")

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ── Carregar ──────────────────────────────────────────────────────────────────
ano_ok = ANOS_OPTS[ano_sel]

if st.button("Carregar Base", type="primary", disabled=not ano_ok):
    grupos     = CURSO_OPTS[curso_sel]
    ies_filter = IES_OPTS[ies_sel]

    with st.spinner("Consultando o Supabase e agregando por curso..."):
        try:
            df = _carregar_dados(
                tuple(grupos) if grupos else (),
                tuple(ies_filter) if ies_filter else (),
            )
        except RuntimeError as e:
            st.error(f"**Não foi possível carregar a base do Supabase.**\n\n{e}")
            df = None

    if df is not None:
        st.session_state.df = df
        st.session_state.filtros = {
            "ano": ano_sel, "curso": curso_sel, "tipo_ies": ies_sel,
            "grupos": grupos, "ies_filter": ies_filter,
        }
        for k in ["model_result", "model_metrics", "coef_table", "vif_table",
                  "residuals_diag", "shap_values", "shap_summary", "hypothesis",
                  "formula", "y_label", "config", "shap_visivel"]:
            st.session_state.pop(k, None)

if not ano_ok:
    st.info("Selecione o ano **2021** para carregar os dados disponíveis.")

if "df" in st.session_state:
    df = st.session_state.df
    n_analiticas = _n_vars_analiticas(df)

    if len(df) == 0:
        st.error("Nenhum curso encontrado com os filtros selecionados.")
        st.stop()
    elif len(df) < _MIN_REGISTROS:
        st.warning(
            f"Base carregada com apenas **{len(df)} cursos** — insuficiente para "
            f"análise estatística confiável (mínimo: {_MIN_REGISTROS}). Amplie os filtros."
        )
    else:
        st.success(f"Base carregada com **{len(df):,} cursos** · "
                   f"**{n_analiticas}** variáveis analíticas disponíveis.")

    nt_vals  = df["NT_GER"].dropna()
    ausentes = df.isnull().mean().mul(100).round(1)
    total_alunos = int(df["QT_ALUNOS"].sum()) if "QT_ALUNOS" in df.columns else None

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _metric_row([
        (f"{len(df):,}",
         "Cursos na base", "dark"),
        (f"{total_alunos:,}" if total_alunos is not None else "N/A",
         "Estudantes Representados", "violet"),
        (f"{nt_vals.mean():.2f}" if len(nt_vals) > 0 else "N/A",
         "Média Nota Geral", "blue"),
        (f"{nt_vals.std():.2f}" if len(nt_vals) > 1 else "N/A",
         "Desvio Padrão", "slate"),
        (f"{ausentes.max():.1f}%",
         "Máx. % Ausentes", "green"),
    ])
    st.caption(
        "Cada linha da base representa um **curso** — as médias/proporções são "
        "calculadas sobre os estudantes presentes daquele curso, não sobre o "
        "estudante individual (ver DEVELOPMENT.md para o porquê dessa granularidade)."
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    col_e, col_f = st.columns(2, gap="medium")
    with col_e.expander("Distribuição por Tipo de IES (nº de cursos)"):
        ies_counts = df["TP_CATEGAD_BIN"].value_counts().rename(VALUE_LABELS.get("TP_CATEGAD_BIN", {}))
        st.dataframe(ies_counts.rename("nº de cursos"), use_container_width=True)
        n_nao_classificado = df["TP_CATEGAD_BIN"].isna().sum()
        if n_nao_classificado:
            st.caption(
                f"{n_nao_classificado} curso(s) com categoria administrativa "
                f"'Especial' (INEP), não classificada como Pública/Privada."
            )
    with col_f.expander("Perfil médio de turno (% de alunos)"):
        turno_medio = (df[["CO_TURNO_V", "CO_TURNO_N", "CO_TURNO_I"]].mean() * 100).round(1)
        turno_medio = turno_medio.rename({
            "CO_TURNO_V": "Vespertino", "CO_TURNO_N": "Noturno", "CO_TURNO_I": "Integral",
        })
        st.dataframe(turno_medio.rename("% médio de alunos").to_frame(), use_container_width=True)
        st.caption("Matutino é a referência — não somado (100% − soma das demais colunas).")
    with st.expander("% de dados ausentes por variável (top 10)"):
        st.dataframe(
            ausentes[ausentes > 0].sort_values(ascending=False).head(10)
            .rename("% ausente").to_frame(),
            use_container_width=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 2 — Definição da Hipótese  (aparece após base carregada)
# ══════════════════════════════════════════════════════════════════════════════
if "df" not in st.session_state or len(st.session_state.df) < _MIN_REGISTROS:
    st.stop()

df = st.session_state.df

_section_divider()
_etapa_header(2, "Definição da Hipótese",
              "Selecione Y (nota a modelar), X (preditores) e interações a testar")

# 2.1 Variável dependente
with st.container(border=True):
    st.markdown('<div class="exn-filter-label">Variável Dependente (Y) — nota a modelar</div>',
                unsafe_allow_html=True)
    y_label = st.radio("Y", options=list(Y_OPTS.keys()),
                       horizontal=True, label_visibility="collapsed")
    y_var = Y_OPTS[y_label]

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# 2.2 Variáveis independentes
st.markdown('<div style="font-size:13px;font-weight:700;color:#374151;'
            'margin-bottom:10px;">Variáveis Independentes (X)</div>',
            unsafe_allow_html=True)

x_disponiveis = {lbl: cod for lbl, cod in X_OPTS.items() if cod in df.columns}
x_selecionados_labels = []
cat_items = list(X_CATEGORIAS.items())

col_L, col_R = st.columns(2, gap="medium")

for col, grupo_items in [(col_L, cat_items[:1]), (col_R, cat_items[1:])]:
    with col:
        for nome_grupo, info in grupo_items:
            with st.container(border=True):
                st.markdown(
                    f'<div class="exn-var-group-header">'
                    f'<span class="exn-pill {info["pill"]}">{nome_grupo}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                for lbl in info["vars"]:
                    if lbl not in x_disponiveis:
                        continue
                    if st.checkbox(lbl, value=(lbl in DEFAULT_X), key=f"x_{lbl}"):
                        x_selecionados_labels.append(lbl)

x_vars = [x_disponiveis[lbl] for lbl in x_selecionados_labels if lbl in x_disponiveis]

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# 2.3 Interações
with st.container(border=True):
    st.markdown('<div class="exn-filter-label">Interações entre variáveis (opcional)</div>',
                unsafe_allow_html=True)
    interactions = []
    if len(x_vars) >= 2:
        pairs = list(itertools.combinations(x_selecionados_labels, 2))
        inter_cols = st.columns(min(len(pairs), 3), gap="small")
        for i, (la, lb) in enumerate(pairs):
            ca, cb = x_disponiveis[la], x_disponiveis[lb]
            if inter_cols[i % len(inter_cols)].checkbox(f"{la} × {lb}",
                                                         key=f"inter_{la}_{lb}"):
                interactions.append((ca, cb))
    else:
        st.caption("Selecione ao menos 2 variáveis independentes para habilitar interações.")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

if x_vars:
    _cod_to_lbl = {v: k for k, v in x_disponiveis.items()}
    preview = f"{y_label}  ←  {' + '.join(x_selecionados_labels)}"
    if interactions:
        inter_legivel = " + ".join(
            f"{_cod_to_lbl.get(a, a)} × {_cod_to_lbl.get(b, b)}"
            for a, b in interactions
        )
        preview += f"  +  [{inter_legivel}]"
    st.info(f"**Modelo a executar:** {preview}")

if st.button("Executar Modelagem", type="primary", disabled=(len(x_vars) == 0)):
    hyp = build_hypothesis(y_var, x_vars, interactions, df)
    try:
        # Abordagem confirmatória: o WLS é ajustado na base completa do recorte,
        # ponderado por QT_ALUNOS (nº de alunos presentes de cada curso — cursos
        # maiores têm médias mais estáveis e pesam mais no ajuste).
        # Não há divisão treino/teste — a inferência (p-valores, IC 95%) usa
        # todas as observações, como é padrão em modelagem estatística inferencial.
        with st.spinner("WLS → VIF → resíduos → SHAP…"):
            result     = fit_ols(hyp, df)
            metrics    = get_model_metrics(result)
            coef_table = get_coefficients_table(result)
            vif_table  = compute_vif(df, x_vars, formula=hyp.to_formula())
            diag       = run_diagnostics(result)
            shap_vals, feat_names = compute_shap(result, df, x_vars)
            shap_sum   = get_shap_summary(shap_vals, feat_names)

    except Exception as e:
        st.error(
            f"Não foi possível executar a modelagem.\n\n"
            f"**Causa provável:** variáveis com valores insuficientes para o modelo.\n\n"
            f"**Sugestão:** remova algumas variáveis ou amplie os filtros da base.\n\n"
            f"Detalhe técnico: `{type(e).__name__}: {e}`"
        )
        st.stop()

    st.session_state.update({
        "hypothesis":     hyp,
        "formula":        hyp.to_formula(),
        "y_label":        y_label,
        "model_result":   result,
        "model_metrics":  metrics,
        "coef_table":     coef_table,
        "vif_table":      vif_table,
        "residuals_diag": diag,
        "shap_values":    shap_vals,
        "shap_summary":   shap_sum,
        "shap_visivel":   False,
        "config": {
            "exec_id":      st.session_state.exec_id,
            "seed":         42,
            "fonte_dados":  "Supabase (tbl_arq1_2021 ... tbl_arq29_2021, agregado por CO_CURSO)",
            "y":            hyp.y,
            "x_vars":       hyp.x_vars,
            "interactions": [list(par) for par in hyp.interactions],
            "formula":      hyp.to_formula(),
            "filtros":      st.session_state.get("filtros", {}),
        },
    })
    st.success("Modelagem concluída! Os resultados aparecem abaixo.")
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ETAPAS 3–7  (aparecem após modelagem executada)
# ══════════════════════════════════════════════════════════════════════════════
if "model_result" not in st.session_state:
    st.stop()

import plotly.express as px

metrics    = st.session_state.model_metrics
coef_table = st.session_state.coef_table
y_label    = st.session_state.get("y_label", "Nota Geral")
vif        = st.session_state.vif_table
diag       = st.session_state.residuals_diag
shap_sum   = st.session_state.shap_summary

# ── 3. Modelagem e Diagnóstico ────────────────────────────────────────────────
_section_divider()
_etapa_header(3, "Modelagem e Diagnóstico",
              "Coeficientes WLS, poder explicativo e interpretação automática")

_metric_row([
    (f"{metrics['r2']*100:.1f}%",  f"Poder Explicativo (R²) — {y_label}",   "dark"),
    (f"{metrics['r2_adj']:.4f}",   "R² Ajustado",                            "violet"),
    (f"p {_p_fmt(metrics['f_pvalue'])}", "Significância Global (Teste F)",   "blue"),
    (f"{metrics['n_obs']:,}",      "Cursos no Modelo (N)",                   "slate"),
])
st.caption(
    "Modelo ajustado por **WLS** (mínimos quadrados ponderados), com peso = "
    "nº de alunos presentes de cada curso (`QT_ALUNOS`) — cursos com mais "
    "alunos têm médias mais estáveis e pesam mais no ajuste do que cursos "
    "com poucos alunos presentes."
)

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("**3.1 — Efeito de cada fator na nota**")
    st.caption(
        "Verde = efeito comprovado (p < 0,05)  ·  "
        "↑ Aumenta / ↓ Diminui = direção do efeito  ·  "
        "IC 95% = intervalo de confiança"
    )
    st.dataframe(
        _style_coef_display(_coef_table_display(coef_table)),
        use_container_width=True, hide_index=True,
    )
    with st.expander("Como ler esta tabela?"):
        st.markdown("""
- **Efeito na Nota**: quanto a nota muda, em média, a cada nível a mais nesta variável
- **Confiável?**: p < 0,05 = efeito improvável de ser acaso | caso contrário = sem evidência suficiente
- **P-valor**: abaixo de 0,05 é considerado estatisticamente significativo
- **IC 95%**: intervalo onde o efeito verdadeiro está em 95% das análises repetidas
        """)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("**3.2 — Interpretação automática**")
    st.markdown(_interpretar_modelo(coef_table, metrics, y_label))


# ── 4. Multicolinearidade (VIF) ───────────────────────────────────────────────
_section_divider()
_etapa_header(4, "Multicolinearidade (VIF)",
              "Detecta correlação excessiva entre preditores — VIF > 10 indica problema")

with st.expander("O que é esta análise?"):
    st.markdown("""
Quando duas variáveis são muito parecidas entre si, os coeficientes ficam instáveis.

| Cor | VIF | Significado |
|---|---|---|
| Verde | ≤ 5 | Sem problema — variáveis independentes |
| Amarelo | 5–10 | Atenção — correlação moderada |
| Vermelho | > 10 | Problema — considere remover a variável |
    """)

display_vif = vif.copy()
display_vif["variavel"] = display_vif["variavel"].apply(_label)
display_vif = display_vif.rename(columns={"variavel": "Fator", "vif": "VIF", "alerta": "Situação"})

with st.container(border=True):
    st.dataframe(_style_vif(display_vif), use_container_width=True, hide_index=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
vif_status, vif_msg = _interpretar_vif(vif)
if vif_status == "ok":
    st.success(vif_msg)
else:
    st.warning(vif_msg)
    remove_var = get_variable_to_remove(vif)
    if st.button(f"Remover '{_label(remove_var)}' e Reexecutar", type="primary",
                 key="btn_remove_vif"):
        hyp   = st.session_state.hypothesis
        new_x = [v for v in hyp.x_vars if v != remove_var]
        if not new_x:
            st.error("Não é possível remover — nenhuma variável restaria no modelo.")
            st.stop()
        new_interactions = [(a, b) for a, b in hyp.interactions
                            if a != remove_var and b != remove_var]
        new_hyp = build_hypothesis(hyp.y, new_x, new_interactions, df)
        with st.spinner("Reexecutando modelo..."):
            result     = fit_ols(new_hyp, df)
            m          = get_model_metrics(result)
            ct         = get_coefficients_table(result)
            vt         = compute_vif(df, new_x, formula=new_hyp.to_formula())
            dg         = run_diagnostics(result)
            sv, fn     = compute_shap(result, df, new_x)
            ss         = get_shap_summary(sv, fn)
        st.session_state.update({
            "hypothesis": new_hyp, "formula": new_hyp.to_formula(),
            "model_result": result, "model_metrics": m, "coef_table": ct,
            "vif_table": vt, "residuals_diag": dg, "shap_values": sv,
            "shap_summary": ss, "shap_visivel": False,
        })
        st.success(f"Variável '{_label(remove_var)}' removida. Modelo reexecutado.")
        st.rerun()


# ── 5. Diagnóstico de Resíduos ────────────────────────────────────────────────
_section_divider()
_etapa_header(5, "Diagnóstico de Resíduos",
              "Testes formais de normalidade e homocedasticidade dos resíduos do modelo")

with st.expander("O que são estes testes e por que importam?"):
    st.markdown("""
Os pressupostos do modelo WLS exigem que os resíduos ponderados (erros do modelo,
já ajustados pelo peso de cada curso) sejam:

1. **Normalmente distribuídos** — verificado pelo teste de Shapiro-Wilk e QQ-plot.
   - H₀: os resíduos seguem distribuição normal.
   - Rejeitar H₀ (p < 0,05) indica desvio da normalidade.

2. **Homocedásticos** (variância constante) — verificado pelo teste de Breusch-Pagan.
   - H₀: a variância dos erros é constante para todos os valores preditos.
   - Rejeitar H₀ (p < 0,05) indica **heterocedasticidade**.

> **Nota com n > 5.000:** o Teorema Central do Limite garante que os estimadores
> continuam válidos assintoticamente mesmo com desvios leves da normalidade.
    """)

# ── Tabela formal de testes ───────────────────────────────────────────────────
sw_n    = diag.get("shapiro_n_usado", 5000)
sw_note = f"(amostra de {sw_n:,})" if not diag.get("shapiro_confiavel", True) else ""

testes_df = pd.DataFrame([
    {
        "Teste":         f"Shapiro-Wilk {sw_note}",
        "H₀":            "Resíduos normalmente distribuídos",
        "Estatística":   f"{diag['shapiro_stat']:.4f}",
        "p-valor":       _p_fmt(diag['shapiro_pvalue']),
        "Decisão":       "Não rejeita H₀" if diag["shapiro_normal"] else "Rejeita H₀",
    },
    {
        "Teste":         "Breusch-Pagan",
        "H₀":            "Variância dos erros é constante (homocedasticidade)",
        "Estatística":   f"{diag['bp_stat']:.4f}",
        "p-valor":       _p_fmt(diag['bp_pvalue']),
        "Decisão":       "Não rejeita H₀" if diag["bp_homocedastic"] else "Rejeita H₀",
    },
])

def _style_testes(df: pd.DataFrame):
    def color_row(row):
        ok = "Não rejeita" in row["Decisão"]
        bg  = "#f0fdf4" if ok else "#fff7ed"
        txt = "#14532d" if ok else "#92400e"
        return [f"background-color: {bg}; color: {txt}; font-weight: 600"
                if col == "Decisão" else f"color: #1e293b"
                for col in df.columns]
    return df.style.apply(color_row, axis=1)

with st.container(border=True):
    st.markdown("**Resultados dos Testes Formais**")
    st.dataframe(_style_testes(testes_df), use_container_width=True, hide_index=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ── Mensagens de diagnóstico específicas (formato TCC) ────────────────────────
n_obs = metrics["n_obs"]

if not diag["bp_homocedastic"]:
    # Com n > 5.000, o BP rejeita facilmente desvios mínimos — adicionar contexto
    contexto_n = (
        f" Com n = {n_obs:,}, o teste é altamente sensível e detecta "
        f"variações pequenas de variância que têm impacto prático mínimo."
        if n_obs > 5000 else ""
    )
    st.warning(
        f"**Indícios de heterocedasticidade detectados** "
        f"(Breusch-Pagan p {_p_fmt(diag['bp_pvalue'])}).{contexto_n} "
        f"A variância dos erros não é constante entre os grupos — os coeficientes "
        f"continuam não-viesados, mas os erros-padrão e p-valores podem estar subestimados. "
        f"**Considere:** transformação da variável dependente (ex: escala logarítmica) "
        f"ou uso de erros-padrão robustos à heterocedasticidade (HC3)."
    )

if not diag["shapiro_normal"]:
    if not diag.get("shapiro_confiavel", True):
        st.info(
            f"**Leve desvio de normalidade nos resíduos** "
            f"(Shapiro-Wilk p {_p_fmt(diag['shapiro_pvalue'])}, "
            f"avaliado em amostra de {sw_n:,} observações). "
            f"Com n = {n_obs:,}, o **Teorema Central do Limite** garante a "
            f"validade assintótica dos estimadores — este resultado tem impacto mínimo "
            f"nas inferências e não invalida o modelo."
        )
    else:
        st.warning(
            f"**Indícios de não-normalidade dos resíduos** "
            f"(Shapiro-Wilk p {_p_fmt(diag['shapiro_pvalue'])}). "
            f"Os intervalos de confiança e p-valores podem estar afetados. "
            f"Verifique a presença de outliers ou considere transformação da variável dependente."
        )

if diag["shapiro_normal"] and diag["bp_homocedastic"]:
    st.success(
        f"**Todos os pressupostos verificados.** "
        f"Resíduos normalmente distribuídos (Shapiro-Wilk p {_p_fmt(diag['shapiro_pvalue'])}) "
        f"e variância constante (Breusch-Pagan p {_p_fmt(diag['bp_pvalue'])}). "
        f"O modelo é metodologicamente adequado para estes dados."
    )

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# ── Gráficos ──────────────────────────────────────────────────────────────────
with st.container(border=True):
    col_g1, col_g2 = st.columns(2, gap="medium")
    plot_data = get_residuals_plot_data(st.session_state.model_result)

    fig_res = px.scatter(
        plot_data, x="fitted", y="residual",
        labels={"fitted": "Valores Preditos", "residual": "Resíduos"},
        title="Resíduos vs. Valores Preditos",
        opacity=0.3, color_discrete_sequence=["#7c3aed"],
    )
    fig_res.add_hline(y=0, line_dash="dash", line_color="#ef4444", line_width=1.5)
    fig_res.update_layout(paper_bgcolor="white", plot_bgcolor="#fafafa",
                          margin=dict(t=44, b=20, l=20, r=20))
    col_g1.plotly_chart(fig_res, use_container_width=True)
    col_g1.caption("Pontos espalhados aleatoriamente em volta de y = 0 indicam homocedasticidade.")

    qq_data = get_qqplot_data(st.session_state.model_result)
    fig_qq = px.scatter(
        qq_data, x="theoretical", y="sample",
        labels={"theoretical": "Quantis Teóricos (Normal)", "sample": "Quantis Amostrais"},
        title="QQ-Plot dos Resíduos",
        opacity=0.3, color_discrete_sequence=["#7c3aed"],
    )
    fig_qq.add_scatter(
        x=qq_data["theoretical"], y=qq_data["line_y"],
        mode="lines", line=dict(color="#ef4444", dash="dash", width=1.5),
        name="Referência Normal", showlegend=False,
    )
    fig_qq.update_layout(paper_bgcolor="white", plot_bgcolor="#fafafa",
                         margin=dict(t=44, b=20, l=20, r=20))
    col_g2.plotly_chart(fig_qq, use_container_width=True)
    col_g2.caption("Pontos próximos à linha diagonal indicam distribuição normal dos resíduos.")


# ── 6. Explicabilidade (SHAP) ─────────────────────────────────────────────────
_section_divider()
_etapa_header(6, "Explicabilidade (SHAP)",
              "Importância de cada fator na nota — SHAP LinearExplainer")

st.markdown(
    "A análise SHAP revela **quais fatores mais influenciam** a nota e o **quanto** "
    "cada um contribui para as diferenças entre os cursos."
)

if st.button("Ver Explicabilidade SHAP", type="primary", key="btn_shap"):
    st.session_state["shap_visivel"] = True

if st.session_state.get("shap_visivel", False):
    display_shap = shap_sum.copy()
    display_shap["variavel"] = display_shap["variavel"].apply(
        lambda v: " × ".join(_label(p) for p in v.split(":")) if ":" in v else _label(v)
    )
    display_shap = display_shap.rename(columns={"shap_mean_abs": "Influência média (pontos)"})

    with st.container(border=True):
        fig = px.bar(
            display_shap,
            x="Influência média (pontos)", y="variavel",
            orientation="h",
            labels={"variavel": ""},
            title=f"Importância dos Fatores — {y_label}",
            color="Influência média (pontos)",
            color_continuous_scale=[[0, "#ede9fe"], [0.5, "#8b5cf6"], [1, "#4c1d95"]],
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
            paper_bgcolor="white", plot_bgcolor="white",
            margin=dict(t=48, b=16, l=8, r=24),
            font=dict(size=13),
        )
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Como ler este gráfico?"):
            st.markdown("""
- **Barra maior** = esse fator faz mais diferença na nota entre os cursos
- O número indica, em média, **quantos pontos** são atribuíveis a cada fator
- Não diz a direção (se aumenta ou diminui) — para isso, veja a Etapa 3
            """)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.success(_interpretar_shap(shap_sum, y_label))


# ── 7. Relatório PDF ──────────────────────────────────────────────────────────
_section_divider()
_etapa_header(7, "Relatório Técnico PDF",
              "Gera documento com todos os resultados, gráficos e interpretações")

formula_str = st.session_state.get("formula", "N/A")
_metric_row([
    (st.session_state.exec_id[:16] + "…", "Exec-ID da Sessão",  "dark"),
    (formula_str[:44] + ("…" if len(formula_str) > 44 else ""),
     "Fórmula do Modelo", "violet"),
])

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# ── Registro de configuração (.json) — reprodutibilidade ─────────────────────
config_atual = st.session_state.get("config", {})
config_json = json.dumps(config_atual, ensure_ascii=False, indent=2)

col_pdf, col_cfg = st.columns(2, gap="medium")

with col_cfg:
    st.download_button(
        label="Baixar Configuração (.json)",
        data=config_json,
        file_name=f"config_{st.session_state.exec_id[:8]}.json",
        mime="application/json",
        key="btn_download_config",
        help="Registro completo da execução: Exec-ID, seed, fórmula, variáveis, "
             "interações e filtros — suficiente para replicar esta análise.",
        use_container_width=True,
    )

with col_pdf:
    gerar_pdf = st.button("Gerar Relatório PDF", type="primary", key="btn_pdf",
                          use_container_width=True)

if gerar_pdf:
    with st.spinner("Gerando PDF..."):
        path = generate_report(
            session={
                "exec_id":                st.session_state.exec_id,
                "config":                 config_atual,
                "formula":                st.session_state.get("formula", ""),
                "model_metrics":          metrics,
                "coef_table":             coef_table,
                "vif_table":              vif,
                "residuals_diag":         diag,
                "shap_summary":           shap_sum,
                "y_label":                y_label,
                "interpretacao_modelo":   _interpretar_modelo(coef_table, metrics, y_label),
                "interpretacao_vif":      _interpretar_vif(vif)[1],
                "interpretacao_residuos": _interpretar_residuos(diag),
                "interpretacao_shap":     _interpretar_shap(shap_sum, y_label),
                "plot_data":              get_residuals_plot_data(st.session_state.model_result),
            },
            filename=f"relatorio_{st.session_state.exec_id[:8]}.pdf",
        )
    st.success(f"Relatório gerado: `{path.name}`")
    with open(path, "rb") as f:
        st.download_button(
            label="Baixar PDF",
            data=f,
            file_name=path.name,
            mime="application/pdf",
            type="primary",
            key="btn_download_pdf",
        )
