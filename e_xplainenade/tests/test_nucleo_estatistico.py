"""
Testes do núcleo estatístico (F2 do plano, 2026-10-19 — ver DEVELOPMENT.md).

Diferente do golden (que compara o pipeline com os números que ele mesmo produziu), aqui cada
resultado é conferido contra um CÁLCULO INDEPENDENTE, escrito com álgebra de matrizes em numpy
puro — então um erro conceitual no pipeline (peso errado, grau de liberdade errado, erro-padrão
robusto errado) é pego mesmo que nunca tenha mudado.

  WLS/OLS    beta, erro-padrão, t, p, IC 95%, R², R² ajustado, F — à mão
  HC3        erro-padrão e p robustos — à mão, sobre os dados "branqueados" (sqrt(w) X)
  VIF        1 / (1 - R²_j) pela regressão de cada X nos demais
  centragem  identidades algébricas entre o modelo com e sem centragem
  SHAP       aditividade e média ponderada zero
  hash       determinismo, invariância à ordem das linhas e sensibilidade a mudanças reais
  textos     nenhuma afirmação de "comprovação" nas interpretações (Mudança 2, 2026-10-14)
  Supabase   paginação ordenada, nulos, tentativas de reconexão
  ETL        presentes, nota zero, CO_CATEGAD = 7 e funil

Tudo offline. Rodar a partir de e_xplainenade/:
    python -m unittest discover -s tests -v
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.explainability import compute_shap  # noqa: E402
from modules.hypothesis import HypothesisConfig, build_hypothesis, center_for_interactions  # noqa: E402
from modules.modeling import (  # noqa: E402
    fit_ols, fit_variants, get_coefficients_table, get_comparison_table, get_model_metrics,
)
from modules.multicollinearity import compute_vif, get_variable_to_remove, has_multicollinearity  # noqa: E402
from modules.reprodutibilidade import hash_dataframe  # noqa: E402
from test_golden import BASE, GOLDEN, _cache_offline, _cliente  # noqa: E402

X5 = ["QE_RENDA", "QE_ESC_MAE", "QE_HORAS_ESTUDO", "QE_TRABALHO", "TP_CATEGAD_BIN"]
REL, ABS = 1e-8, 1e-10


def _design(df, cols):
    return np.column_stack([np.ones(len(df))] + [df[c].to_numpy(float) for c in cols])


def manual(df, y, cols, ponderado=True):
    """WLS (ou OLS) e HC3 à mão. Devolve tudo o que o pipeline reporta."""
    X, yv = _design(df, cols), df[y].to_numpy(float)
    w = df["QT_ALUNOS"].to_numpy(float) if ponderado else np.ones(len(df))
    n, p = X.shape
    XtWX = X.T @ (w[:, None] * X)
    inv = np.linalg.inv(XtWX)
    beta = inv @ (X.T @ (w * yv))
    resid = yv - X @ beta
    sigma2 = np.sum(w * resid ** 2) / (n - p)
    se = np.sqrt(np.diag(sigma2 * inv))
    t = beta / se
    gl = n - p
    ybar = np.sum(w * yv) / np.sum(w)
    r2 = 1 - np.sum(w * resid ** 2) / np.sum(w * (yv - ybar) ** 2)
    # HC3 sobre os dados branqueados (statsmodels: cov_type="HC3", z normal)
    Xs, ys = np.sqrt(w)[:, None] * X, np.sqrt(w) * yv
    inv_s = np.linalg.inv(Xs.T @ Xs)
    e = ys - Xs @ beta
    h = np.einsum("ij,jk,ik->i", Xs, inv_s, Xs)
    meio = Xs.T @ (((e / (1 - h)) ** 2)[:, None] * Xs)
    se3 = np.sqrt(np.diag(inv_s @ meio @ inv_s))
    return dict(
        beta=beta, se=se, t=t, p=2 * stats.t.sf(np.abs(t), gl), gl=gl, r2=r2,
        r2_adj=1 - (1 - r2) * (n - 1) / gl, f=(r2 / (p - 1)) / ((1 - r2) / gl), n=n,
        ic_inf=beta - stats.t.ppf(0.975, gl) * se, ic_sup=beta + stats.t.ppf(0.975, gl) * se,
        se_hc3=se3, p_hc3=2 * stats.norm.sf(np.abs(beta / se3)), resid=resid, w=w, X=X,
    )


class TestWlsOlsHc3ContraCalculoManual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hyp = build_hypothesis("NT_GER", X5, [], BASE)
        cls.v = fit_variants(cls.hyp, BASE)
        cls.m_wls = manual(BASE, "NT_GER", X5, ponderado=True)
        cls.m_ols = manual(BASE, "NT_GER", X5, ponderado=False)

    def assertVec(self, got, esperado, nome):
        np.testing.assert_allclose(np.asarray(got, float), esperado, rtol=REL, atol=ABS, err_msg=nome)

    def test_wls_coeficientes_ep_t_p_e_ic(self):
        t = get_coefficients_table(self.v["wls"], robust_result=self.v["wls_robust"])
        m = self.m_wls
        self.assertEqual(list(t["variavel"]), ["Intercept"] + X5)
        self.assertVec(t["coeficiente"], m["beta"], "beta")
        self.assertVec(t["erro_padrao"], m["se"], "erro-padrão clássico")
        self.assertVec(t["t_stat"], m["t"], "t")
        self.assertVec(t["p_valor"], m["p"], "p-valor (t com n-k-1 gl)")
        self.assertVec(t["ic_inf_95"], m["ic_inf"], "IC inferior")
        self.assertVec(t["ic_sup_95"], m["ic_sup"], "IC superior")

    def test_wls_erro_padrao_e_p_robustos_hc3(self):
        t = get_coefficients_table(self.v["wls"], robust_result=self.v["wls_robust"])
        self.assertVec(t["erro_padrao_robusto"], self.m_wls["se_hc3"], "EP HC3")
        self.assertVec(t["p_valor_robusto"], self.m_wls["p_hc3"], "p HC3 (z normal)")

    def test_ols_sem_pesos_classico_e_hc3(self):
        c = get_comparison_table(self.v).set_index("variavel")
        m = self.m_ols
        nomes = ["Intercept"] + X5
        self.assertVec(c.loc[nomes, "coef_ols"], m["beta"], "beta OLS")
        self.assertVec(c.loc[nomes, "ep_ols"], m["se"], "EP OLS")
        self.assertVec(c.loc[nomes, "p_ols"], m["p"], "p OLS")
        self.assertVec(c.loc[nomes, "ep_ols_robust"], m["se_hc3"], "EP HC3 OLS")
        self.assertVec(c.loc[nomes, "p_ols_robust"], m["p_hc3"], "p HC3 OLS")

    def test_coeficientes_nao_mudam_com_o_erro_robusto(self):
        for a, b in (("wls", "wls_robust"), ("ols", "ols_robust")):
            np.testing.assert_array_equal(self.v[a].params.to_numpy(), self.v[b].params.to_numpy())

    def test_metricas_r2_r2_ajustado_f_e_n(self):
        met = get_model_metrics(self.v["wls"])
        m = self.m_wls
        self.assertEqual(met["n_obs"], m["n"])
        self.assertAlmostEqual(met["r2"], m["r2"], places=4)       # a função arredonda a 4 casas
        self.assertAlmostEqual(met["r2_adj"], m["r2_adj"], places=4)
        self.assertAlmostEqual(met["f_stat"], m["f"], places=3)
        self.assertLess(met["f_pvalue"], 1e-6)

    def test_o_peso_importa_wls_e_ols_diferem(self):
        self.assertGreater(np.max(np.abs(self.m_wls["beta"] - self.m_ols["beta"])), 0.05)

    def test_flags_de_divergencia_seguem_a_definicao(self):
        c = get_comparison_table(self.v)
        for _, r in c.iterrows():
            self.assertEqual(r["sinal_diverge"], bool(np.sign(r["coef_wls"]) != np.sign(r["coef_ols"])))
            self.assertEqual(r["signif_diverge"], bool((r["p_wls_robust"] < 0.05) != (r["p_ols_robust"] < 0.05)))

    def test_flag_de_sinal_detecta_inversao_provocada(self):
        """
        Dois grupos com a MESMA distribuição de x e a mesma média de y, mas relações opostas:
        A sobe com x (peso 1, 100 linhas), B desce com x (peso 200, 40 linhas). O OLS pooled dá
        inclinação positiva (A tem mais linhas); o WLS é dominado pelo peso de B e dá negativa.
        """
        a = pd.DataFrame({"x": np.linspace(0, 1, 100)})
        a["y"], a["QT_ALUNOS"] = 10 * a["x"], 1.0
        b = pd.DataFrame({"x": np.linspace(0, 1, 40)})
        b["y"], b["QT_ALUNOS"] = 10 - 10 * b["x"], 200.0
        df = pd.concat([a, b], ignore_index=True)
        c = get_comparison_table(fit_variants(HypothesisConfig(y="y", x_vars=["x"]), df)).set_index("variavel")
        self.assertLess(c.loc["x", "coef_wls"], 0)
        self.assertGreater(c.loc["x", "coef_ols"], 0)
        self.assertTrue(c.loc["x", "sinal_diverge"])


class TestVifContraCalculoManual(unittest.TestCase):
    def test_vif_e_um_sobre_um_menos_r2_da_regressao_nos_demais(self):
        cols = X5
        tabela = compute_vif(BASE, cols, formula=build_hypothesis("NT_GER", cols, [], BASE).to_formula())
        got = dict(zip(tabela["variavel"], tabela["vif"]))
        for j, c in enumerate(cols):
            outros = np.column_stack([np.ones(len(BASE))] + [BASE[o].to_numpy(float) for o in cols if o != c])
            yj = BASE[c].to_numpy(float)
            coef, *_ = np.linalg.lstsq(outros, yj, rcond=None)
            r2 = 1 - np.sum((yj - outros @ coef) ** 2) / np.sum((yj - yj.mean()) ** 2)
            self.assertAlmostEqual(got[c], 1 / (1 - r2), places=2, msg=c)  # a tabela arredonda a 3 casas

    def test_limiares_e_helpers(self):
        t = pd.DataFrame({"variavel": ["a", "b", "c"], "vif": [3.0, 12.0, 7.0], "alerta": ["", "", ""]})
        self.assertEqual(get_variable_to_remove(t), "b")
        self.assertTrue(has_multicollinearity(t))
        ok = t.assign(vif=[1.0, 2.0, 5.0])
        self.assertIsNone(get_variable_to_remove(ok))
        self.assertFalse(has_multicollinearity(ok))  # 5,0 não passa do limiar (> 5)


class TestCentragem(unittest.TestCase):
    """Identidades: centrar não muda o ajuste, só reparametriza."""

    @classmethod
    def setUpClass(cls):
        cls.hyp = build_hypothesis("NT_GER", ["QE_RENDA", "QE_HORAS_ESTUDO", "QE_ESC_MAE"], [("QE_RENDA", "QE_HORAS_ESTUDO")], BASE)
        cls.dfc, cls.medias = center_for_interactions(cls.hyp, BASE)
        cls.raw, cls.cen = fit_ols(cls.hyp, BASE).params, fit_ols(cls.hyp, cls.dfc).params
        cls.ma, cls.mb = cls.medias["QE_RENDA"], cls.medias["QE_HORAS_ESTUDO"]
        cls.i = "QE_RENDA:QE_HORAS_ESTUDO"

    def test_a_media_usada_e_a_media_simples_dos_cursos(self):
        self.assertAlmostEqual(self.ma, BASE["QE_RENDA"].mean(), places=12)
        self.assertAlmostEqual(self.mb, BASE["QE_HORAS_ESTUDO"].mean(), places=12)
        self.assertAlmostEqual(float(self.dfc["QE_RENDA"].mean()), 0.0, places=10)

    def test_so_as_variaveis_da_interacao_sao_centradas(self):
        self.assertEqual(set(self.medias), {"QE_RENDA", "QE_HORAS_ESTUDO"})
        pd.testing.assert_series_equal(self.dfc["QE_ESC_MAE"], BASE["QE_ESC_MAE"])

    def test_o_termo_de_interacao_e_o_r2_nao_mudam(self):
        self.assertAlmostEqual(self.cen[self.i], self.raw[self.i], places=9)
        r_raw, r_cen = fit_ols(self.hyp, BASE), fit_ols(self.hyp, self.dfc)
        self.assertAlmostEqual(r_raw.rsquared, r_cen.rsquared, places=12)
        np.testing.assert_allclose(r_raw.fittedvalues, r_cen.fittedvalues, rtol=1e-10)
        self.assertAlmostEqual(r_raw.pvalues[self.i], r_cen.pvalues[self.i], places=10)

    def test_efeito_principal_centrado_e_o_efeito_na_media_da_outra(self):
        # y = b0 + ba·a + bb·b + bab·a·b  →  efeito de a na média de b: ba + bab·mb
        self.assertAlmostEqual(self.cen["QE_RENDA"], self.raw["QE_RENDA"] + self.raw[self.i] * self.mb, places=8)
        self.assertAlmostEqual(self.cen["QE_HORAS_ESTUDO"], self.raw["QE_HORAS_ESTUDO"] + self.raw[self.i] * self.ma, places=8)

    def test_intercepto_centrado_e_o_valor_predito_no_curso_medio(self):
        esperado = (self.raw["Intercept"] + self.raw["QE_RENDA"] * self.ma + self.raw["QE_HORAS_ESTUDO"] * self.mb
                    + self.raw[self.i] * self.ma * self.mb)
        self.assertAlmostEqual(self.cen["Intercept"], esperado, places=8)

    def test_sem_interacao_nada_e_centrado(self):
        hyp = build_hypothesis("NT_GER", ["QE_RENDA", "QE_ESC_MAE"], [], BASE)
        df, medias = center_for_interactions(hyp, BASE)
        self.assertEqual(medias, {})
        self.assertIs(df, BASE)

    def test_centragem_derruba_o_vif_estrutural_da_interacao(self):
        f = self.hyp.to_formula()
        antes = compute_vif(BASE, self.hyp.x_vars, formula=f).set_index("variavel")["vif"]
        depois = compute_vif(self.dfc, self.hyp.x_vars, formula=f).set_index("variavel")["vif"]
        self.assertGreater(antes[self.i], 10)
        self.assertLess(depois[self.i], 5)
        self.assertLess(depois["QE_RENDA"], antes["QE_RENDA"])


class TestShap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hyp = build_hypothesis("NT_GER", X5, [], BASE)
        cls.res = fit_ols(cls.hyp, BASE)
        cls.shap, cls.nomes = compute_shap(cls.res, BASE, X5)
        cls.w = BASE["QT_ALUNOS"].to_numpy(float)
        cls.X = BASE[X5].to_numpy(float)
        cls.coef = cls.res.params.drop("Intercept").reindex(X5).to_numpy()

    def test_ordem_das_colunas(self):
        self.assertEqual(self.nomes, X5)

    def test_shap_e_coef_vezes_desvio_da_media_ponderada(self):
        mu = np.average(self.X, axis=0, weights=self.w)
        np.testing.assert_allclose(self.shap, self.coef * (self.X - mu), rtol=1e-10, atol=1e-12)

    def test_media_ponderada_de_cada_coluna_e_zero(self):
        np.testing.assert_allclose(np.average(self.shap, axis=0, weights=self.w), 0.0, atol=1e-10)

    def test_aditividade_soma_dos_shap_e_a_predicao_menos_a_predicao_media(self):
        pred = self.res.fittedvalues.to_numpy()
        np.testing.assert_allclose(self.shap.sum(axis=1), pred - np.average(pred, weights=self.w), rtol=1e-8, atol=1e-9)


class TestHash(unittest.TestCase):
    COLS = ["NT_GER", "QE_RENDA", "QT_ALUNOS"]

    def test_deterministico(self):
        self.assertEqual(hash_dataframe(BASE, self.COLS), hash_dataframe(BASE.copy(), self.COLS))

    def test_nao_depende_da_ordem_das_linhas(self):
        embaralhada = BASE.sample(frac=1.0, random_state=1)
        self.assertEqual(hash_dataframe(BASE, self.COLS), hash_dataframe(embaralhada, self.COLS))

    def test_ignora_ruido_de_ponto_flutuante_muito_abaixo_do_arredondamento(self):
        # O hash arredonda a 10 casas; um ruído de 1e-13 só atravessaria uma fronteira de
        # arredondamento por azar (~1e-3 por valor) — por isso perturbo poucos valores.
        ruidosa = BASE.copy()
        ruidosa.loc[ruidosa.index[:5], "NT_GER"] += 1e-13
        self.assertEqual(hash_dataframe(BASE, self.COLS), hash_dataframe(ruidosa, self.COLS))

    def test_muda_quando_um_valor_muda_de_verdade(self):
        alterada = BASE.copy()
        alterada.loc[alterada.index[10], "NT_GER"] += 1e-6
        self.assertNotEqual(hash_dataframe(BASE, self.COLS), hash_dataframe(alterada, self.COLS))

    def test_muda_quando_uma_linha_some_e_ignora_colunas_nao_listadas(self):
        self.assertNotEqual(hash_dataframe(BASE, self.COLS), hash_dataframe(BASE.iloc[1:], self.COLS))
        outra = BASE.copy()
        outra["TP_SEXO"] = 0.0
        self.assertEqual(hash_dataframe(BASE, self.COLS), hash_dataframe(outra, self.COLS))


class TestDiagnosticos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hyp = build_hypothesis("NT_GER", X5, [], BASE)
        cls.v = fit_variants(cls.hyp, BASE)

    def test_shapiro_e_breusch_pagan_do_resido_ponderado(self):
        from statsmodels.stats.diagnostic import het_breuschpagan

        from modules.residuals import run_diagnostics

        d = run_diagnostics(self.v["wls"])
        sw = stats.shapiro(self.v["wls"].wresid.to_numpy())
        bp = het_breuschpagan(self.v["wls"].wresid.to_numpy(), self.v["wls"].model.exog)
        self.assertAlmostEqual(d["shapiro_pvalue"], sw.pvalue, places=5)
        self.assertAlmostEqual(d["bp_pvalue"], bp[1], places=5)
        self.assertTrue(d["shapiro_confiavel"])
        self.assertEqual(d["shapiro_n_usado"], len(BASE))

    def test_spearman_do_ols_sem_pesos(self):
        from modules.residuals import diagnose_weighting

        r = diagnose_weighting(self.v["ols"], BASE)
        rho, p = stats.spearmanr(np.abs(self.v["ols"].resid.to_numpy()), BASE["QT_ALUNOS"].to_numpy())
        self.assertAlmostEqual(r["spearman_rho"], rho, places=5)
        self.assertAlmostEqual(r["spearman_pvalue"], p, places=5)
        self.assertEqual(r["erro_cai_com_tamanho"], bool(rho < 0 and p < 0.05))

    def test_erro_que_diminui_com_o_tamanho_e_detectado(self):
        from modules.residuals import diagnose_weighting

        rng = np.random.default_rng(3)
        n = 400
        w = rng.integers(1, 200, n).astype(float)
        x = rng.normal(size=n)
        y = 2 * x + rng.normal(size=n) / np.sqrt(w)      # variância ∝ 1/w: o caso que justifica o WLS
        df = pd.DataFrame({"y": y, "x": x, "QT_ALUNOS": w})
        r = diagnose_weighting(fit_variants(HypothesisConfig(y="y", x_vars=["x"]), df)["ols"], df)
        self.assertTrue(r["erro_cai_com_tamanho"])
        self.assertLess(r["spearman_rho"], -0.3)

    def test_shapiro_acima_de_5000_usa_amostra_reprodutivel(self):
        from modules.residuals import run_diagnostics

        rng = np.random.default_rng(0)
        n = 6000
        df = pd.DataFrame({"y": rng.normal(size=n), "x": rng.normal(size=n), "QT_ALUNOS": np.ones(n)})
        res = fit_variants(HypothesisConfig(y="y", x_vars=["x"]), df)["wls"]
        d1, d2 = run_diagnostics(res), run_diagnostics(res)
        self.assertFalse(d1["shapiro_confiavel"])
        self.assertEqual(d1["shapiro_n_usado"], 5000)
        self.assertEqual(d1, d2)  # semente fixa: mesma amostra, mesmo p-valor


class TestTextosEmLinguagemDeAssociacao(unittest.TestCase):
    """Nenhum texto automático afirma 'comprovação' (Mudança 2, 2026-10-14)."""

    PROIBIDO = re.compile(r"comprovad|garant|confiáv|confiav|efeito causal|adequado para estes dados", re.I)

    @classmethod
    def setUpClass(cls):
        cls.cliente = _cliente()

    def test_interpretacoes_dos_12_cenarios(self):
        with mock.patch.dict("modules.loader._supabase_cache", _cache_offline(), clear=True):
            for nome, ref in GOLDEN.items():
                j = self.cliente.post("/api/e-xplainenade/hipotese", json=ref["pedido"]).json()
                for campo in [k for k in j if k.startswith("interpretacao_")] + ["avisos"]:
                    texto = " ".join(j[campo]) if isinstance(j[campo], list) else j[campo]
                    self.assertIsNone(self.PROIBIDO.search(texto), f"{nome}.{campo}: {texto[:120]}")

    def test_aviso_de_dado_agregado_aparece_uma_vez_na_interpretacao_do_modelo(self):
        with mock.patch.dict("modules.loader._supabase_cache", _cache_offline(), clear=True):
            j = self.cliente.post("/api/e-xplainenade/hipotese", json=GOLDEN["03_completo"]["pedido"]).json()
        self.assertEqual(j["interpretacao_modelo"].count("médias de cursos"), 1)

    def test_variantes_do_texto_do_vif(self):
        from modules.interpretation import interpretar_vif

        def t(vifs):
            return pd.DataFrame({"variavel": ["QE_RENDA", "QE_ESC_MAE"][:len(vifs)], "vif": vifs, "alerta": [""] * len(vifs)})

        ok = interpretar_vif(t([1.2, 4.9]))
        self.assertEqual(ok[0], "ok")
        self.assertIn("Não foi detectada multicolinearidade relevante", ok[1])
        mod = interpretar_vif(t([1.2, 7.0]))
        self.assertEqual(mod[0], "warning")
        self.assertIn("moderada", mod[1])
        sev = interpretar_vif(t([15.0, 7.0]))
        self.assertIn("severa", sev[1])
        for _, txt in (ok, mod, sev):
            self.assertIsNone(self.PROIBIDO.search(txt))

    def test_ramos_do_texto_de_residuos(self):
        from modules.interpretation import interpretar_residuos

        base = dict(bp_homocedastic=True, bp_pvalue=0.3, shapiro_pvalue=0.004, shapiro_n_usado=705)
        normal = interpretar_residuos({**base, "shapiro_normal": True, "shapiro_confiavel": True})
        self.assertIn("seguem um padrão normal", normal)
        pequeno = interpretar_residuos({**base, "shapiro_normal": False, "shapiro_confiavel": True})
        self.assertIn("705 cursos", pequeno)
        self.assertNotIn("5.000", pequeno)  # o texto antigo dizia "mais de 5.000 observações" para n = 705
        grande = interpretar_residuos({**base, "shapiro_normal": False, "shapiro_confiavel": False})
        self.assertIn("5.000", grande)

    def test_sensibilidade_so_alarma_quando_a_conclusao_muda(self):
        from modules.interpretation import interpretar_sensibilidade

        def linha(v, cw, co, pw, po):
            return dict(variavel=v, coef_wls=cw, coef_ols=co, p_wls=pw, p_wls_robust=pw, p_ols=po, p_ols_robust=po,
                        sinal_diverge=(cw > 0) != (co > 0), signif_diverge=(pw < .05) != (po < .05))

        robusto = interpretar_sensibilidade(pd.DataFrame([linha("QE_RENDA", 4, 3, .001, .001)]))
        self.assertIn("robustos à ponderação", robusto)
        irrelevante = interpretar_sensibilidade(pd.DataFrame([linha("QE_RENDA:QE_ESC_MAE", -.06, .36, .97, .77)]))
        self.assertIn("a conclusão não muda", irrelevante)
        self.assertNotIn("depende da ponderação", irrelevante)
        relevante = interpretar_sensibilidade(pd.DataFrame([linha("QE_ESC_MAE", -2, 1, .03, .4)]))
        self.assertIn("depende da ponderação", relevante)


class TestSupabaseClient(unittest.TestCase):
    """fetch_table com um cliente falso: paginação, nulos e reconexão."""

    class _Resposta:
        def __init__(self, data):
            self.data = data

    class _Consulta:
        def __init__(self, cliente):
            self.c, self.ordem, self.faixa = cliente, None, None

        def select(self, cols):
            return self

        def eq(self, col, val):
            return self

        def order(self, col):
            self.ordem = col
            self.c.ordens.append(col)
            return self

        def range(self, a, b):
            self.faixa = (a, b)
            return self

        def execute(self):
            self.c.chamadas += 1
            if self.c.falhas:
                self.c.falhas -= 1
                raise self.c.excecao
            a, b = self.faixa
            return TestSupabaseClient._Resposta(self.c.linhas[a:b + 1])

    class _Cliente:
        def __init__(self, linhas, falhas=0, excecao=None):
            self.linhas, self.falhas, self.excecao = linhas, falhas, excecao
            self.chamadas, self.ordens = 0, []

        def table(self, nome):
            return TestSupabaseClient._Consulta(self)

    def _fetch(self, cliente, **kw):
        from modules import supabase_client as sc

        with mock.patch.object(sc, "_client", return_value=cliente), mock.patch.object(sc.time, "sleep"):
            return sc.fetch_table("tbl_x", **kw)

    def test_paginacao_ordenada_devolve_todas_as_linhas_na_ordem(self):
        linhas = [{"id": i, "v": f"x{i}"} for i in range(1, 9)]
        cliente = self._Cliente(linhas)
        df = self._fetch(cliente, page_size=3)
        self.assertEqual(list(df["id"]), [str(i) for i in range(1, 9)])
        self.assertEqual(cliente.chamadas, 3)             # 3 + 3 + 2
        self.assertEqual(set(cliente.ordens), {"id"})      # toda página pede ORDER BY id

    def test_pagina_cheia_no_final_pede_mais_uma_e_para(self):
        cliente = self._Cliente([{"id": i} for i in range(6)])
        self.assertEqual(len(self._fetch(cliente, page_size=3)), 6)
        self.assertEqual(cliente.chamadas, 3)             # a 3ª página veio vazia

    def test_nulo_continua_nulo_e_nao_vira_o_texto_nan(self):
        df = self._fetch(self._Cliente([{"id": 1, "v": None}, {"id": 2, "v": "a"}]))
        self.assertTrue(df["v"].isna().iloc[0])
        self.assertNotIn("nan", list(df["v"].dropna()))
        self.assertEqual(df["v"].iloc[1], "a")

    def test_valores_viram_texto(self):
        df = self._fetch(self._Cliente([{"id": 1, "v": 4.5, "w": 3}]))
        self.assertEqual((df["v"].iloc[0], df["w"].iloc[0]), ("4.5", "3"))

    def test_reconecta_depois_de_queda_transitoria(self):
        import httpx

        cliente = self._Cliente([{"id": 1}], falhas=2, excecao=httpx.ConnectError("caiu"))
        df = self._fetch(cliente)
        self.assertEqual(len(df), 1)
        self.assertEqual(cliente.chamadas, 3)             # 2 falhas + 1 sucesso

    def test_desiste_depois_de_3_quedas_com_mensagem_da_tabela(self):
        import httpx

        cliente = self._Cliente([{"id": 1}], falhas=99, excecao=httpx.ConnectError("caiu"))
        with self.assertRaisesRegex(RuntimeError, "tbl_x"):
            self._fetch(cliente)
        self.assertEqual(cliente.chamadas, 3)

    def test_erro_que_nao_e_de_rede_nao_e_repetido(self):
        cliente = self._Cliente([{"id": 1}], falhas=99, excecao=ValueError("tabela inexistente"))
        with self.assertRaisesRegex(RuntimeError, "tbl_x"):
            self._fetch(cliente)
        self.assertEqual(cliente.chamadas, 1)


class TestEtl(unittest.TestCase):
    """etl.load_raw sobre arquivos brutos sintéticos (a mesma fábrica do test_curso_si)."""

    def _base(self, ajustar=None):
        from modules import etl
        from test_curso_si import _arquivos_sinteticos

        arquivos = _arquivos_sinteticos()
        if ajustar:
            ajustar(arquivos)
        with mock.patch.object(etl, "_read_todos_arquivos", lambda: arquivos):
            return etl.load_raw()

    def test_so_presentes_com_nota_positiva_contam(self):
        def ajustar(a):
            a[3].loc[0:2, "TP_PRES"] = ["555", "222", "555"]   # o 2º faltou
            a[3].loc[0:2, "NT_GER"] = ["40", "41", "0"]         # o 3º tem nota 0 (sem prova válida)

        base = self._base(ajustar).set_index("CO_CURSO")
        self.assertEqual(int(base.loc[101, "QT_ALUNOS"]), 1)
        self.assertAlmostEqual(float(base.loc[101, "NT_GER"]), 40.0)
        self.assertEqual(int(base.loc[102, "QT_ALUNOS"]), 3)

    def test_categoria_especial_e_excluida_e_contada_no_funil(self):
        def ajustar(a):
            a[1].loc[a[1]["CO_CURSO"] == "103", "CO_CATEGAD"] = "7"

        base = self._base(ajustar)
        self.assertNotIn(103, set(base["CO_CURSO"]))
        funil = base.attrs["funil"]
        self.assertEqual(funil["cursos_excluidos_categad"], 1)
        self.assertEqual(funil["cursos_com_nota"], 13)
        self.assertEqual(funil["cursos_final"], len(base))
        self.assertEqual(len(base), 12)
        self.assertFalse(base["TP_CATEGAD_BIN"].isna().any())

    def test_curso_ausente_de_um_dos_arquivos_sai_no_inner_join(self):
        def ajustar(a):
            a[14] = a[14][a[14]["CO_CURSO"] != "104"].reset_index(drop=True)

        base = self._base(ajustar)
        self.assertNotIn(104, set(base["CO_CURSO"]))
        self.assertEqual(len(base), 12)

    def test_cada_linha_e_um_curso(self):
        base = self._base()
        self.assertTrue(base["CO_CURSO"].is_unique)
        self.assertEqual(len(base), 13)
        self.assertIn("CURSO_SI", base.columns)


if __name__ == "__main__":
    unittest.main()
