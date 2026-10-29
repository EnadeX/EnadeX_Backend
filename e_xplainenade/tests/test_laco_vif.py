"""
Laço de multicolinearidade: detectar → o usuário remove a variável de maior VIF → recalcular.

Critério de sucesso do artigo (2.4): "correta detecção de multicolinearidade, identificando
variáveis com VIF superior ao limiar e recalculando o modelo automaticamente após a remoção
solicitada pelo usuário". Nos dados reais do ENADE 2021 (CC+SI) NENHUM modelo chega a VIF > 5
depois da centragem (máximo 4,38 nos 12 cenários), então o laço nunca dispara por si só. Este
teste o exercita de ponta a ponta com colinearidade CONTROLADA — a escolaridade do pai vira
2 × a da mãe + ruído, quase perfeita, mas não exata (a exata é recusada: ver test_operacao).

A escolha da variável a remover replica `removerVariavelProblematica()` do frontend: a de
maior VIF entre as que não estão "ok".

Tudo offline. Rodar a partir de e_xplainenade/:
    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import etl, loader  # noqa: E402
from modules.multicollinearity import VIF_MODERADO, VIF_SEVERO  # noqa: E402
from test_golden import BASE, _cliente  # noqa: E402

X = ["QE_RENDA", "QE_ESC_MAE", "QE_ESC_PAI"]


def _base_quase_colinear():
    df = BASE.copy()
    ruido = np.random.default_rng(0).normal(size=len(df)) * 0.01
    df["QE_ESC_PAI"] = df["QE_ESC_MAE"] * 2.0 + ruido  # quase 2 x MAE, sem ser combinação exata
    df.attrs["funil"] = {}
    return df


class TestLacoVif(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = _cliente()

    def setUp(self):
        p = mock.patch.dict(loader._supabase_cache, {None: _base_quase_colinear()}, clear=True)
        p.start()
        self.addCleanup(p.stop)
        r = mock.patch.object(etl, "load_raw", side_effect=AssertionError("consultou o Supabase"))
        r.start()
        self.addCleanup(r.stop)

    def hipotese(self, x_vars):
        r = self.cliente.post("/api/e-xplainenade/hipotese", json={"y": "NT_GER", "x_vars": x_vars})
        self.assertEqual(r.status_code, 200, r.text[:300])
        return r.json()

    @staticmethod
    def pior_variavel(j):
        """O que o botão 'Remover variável de maior VIF e reexecutar' escolhe."""
        problematicas = [r for r in j["vif_table"] if r["alerta"] != "ok"]
        return max(problematicas, key=lambda r: r["vif"])["variavel"] if problematicas else None

    def test_o_alerta_aponta_exatamente_o_par_colinear(self):
        j = self.hipotese(X)
        severas = {r["variavel"] for r in j["vif_table"] if r["alerta"].startswith("severo")}
        self.assertEqual(severas, {"QE_ESC_MAE", "QE_ESC_PAI"})
        self.assertEqual(next(r for r in j["vif_table"] if r["variavel"] == "QE_RENDA")["alerta"], "ok")
        self.assertTrue(all(r["vif"] > VIF_SEVERO for r in j["vif_table"] if r["variavel"] in severas))
        self.assertIn("severa", j["interpretacao_vif"])
        self.assertIn("Considere removê-la", j["interpretacao_vif"])

    def test_remover_a_de_maior_vif_e_recalcular_resolve(self):
        antes = self.hipotese(X)
        pior = self.pior_variavel(antes)
        self.assertIn(pior, {"QE_ESC_MAE", "QE_ESC_PAI"})

        depois = self.hipotese([v for v in X if v != pior])
        self.assertEqual(len(depois["vif_table"]), 2)
        self.assertTrue(all(r["alerta"] == "ok" for r in depois["vif_table"]))
        self.assertTrue(all(r["vif"] <= VIF_MODERADO for r in depois["vif_table"]))
        self.assertIn("Não foi detectada multicolinearidade relevante", depois["interpretacao_vif"])
        self.assertIsNone(self.pior_variavel(depois))  # o botão deixaria de aparecer
        # A variável removida era redundante: o poder explicativo quase não muda.
        self.assertAlmostEqual(antes["model_metrics"]["r2"], depois["model_metrics"]["r2"], delta=0.01)

    def test_o_modelo_recalculado_e_o_mesmo_que_a_hipotese_sem_a_variavel(self):
        pior = self.pior_variavel(self.hipotese(X))
        restantes = [v for v in X if v != pior]
        a, b = self.hipotese(restantes), self.hipotese(restantes)
        self.assertEqual(a["coef_table"], b["coef_table"])
        self.assertNotIn(pior, a["formula"])

    def test_sem_colinearidade_o_laco_nao_dispara(self):
        # Mesmas três variáveis, base real (sem o par colinear): nada a remover.
        with mock.patch.dict(loader._supabase_cache, {None: BASE.copy()}, clear=True):
            j = self.hipotese(X)
        self.assertIsNone(self.pior_variavel(j))
        self.assertTrue(all(r["vif"] < VIF_MODERADO for r in j["vif_table"]))


if __name__ == "__main__":
    unittest.main()
