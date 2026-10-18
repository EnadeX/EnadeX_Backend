"""
Teste "golden": roda os 12 cenários da rodada v2 pela API (/hipotese), OFFLINE, sobre a base
congelada em tests/fixtures/base_705_cursos.csv, e compara com os números de referência de
tests/fixtures/golden_v2.json (os mesmos que saíram da interface web em 2026-10-14).

É a rede de segurança das mudanças futuras: se algum resultado mudar sem que ninguém tenha
alterado a metodologia de propósito, este teste quebra. Não regenere os arquivos de fixture
para "consertar" o teste — ver tests/fixtures/gerar_fixtures.py.

Rodar a partir de e_xplainenade/:
    python -m unittest discover -s tests -v
"""
import json
import math
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import patsy
import scipy
import statsmodels

RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(FIXTURES))

from gerar_fixtures import carregar_base  # noqa: E402
from modules import etl, loader  # noqa: E402

GOLDEN = json.loads((FIXTURES / "golden_v2.json").read_text(encoding="utf-8"))
BASE = carregar_base()
VERSOES = {"pandas": pd.__version__, "numpy": np.__version__, "statsmodels": statsmodels.__version__,
           "scipy": scipy.__version__, "patsy": patsy.__version__}

# Mesma máquina → resultados idênticos; em outra máquina (BLAS/versões) pode haver ruído de ~1e-12.
REL_TOL, ABS_TOL = 1e-8, 1e-12


def _cache_offline() -> dict:
    """Pré-popula o cache do loader com a base congelada, no formato que o ETL entregaria.
    O recorte por curso (CC/SI) equivale a agregar só aqueles cursos: a agregação é por curso."""
    return {
        None: BASE.copy(),
        (4004,): BASE[BASE["CO_GRUPO"] == 4004].reset_index(drop=True),
        (4006,): BASE[BASE["CO_GRUPO"] == 4006].reset_index(drop=True),
    }


def _cliente():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import e_xplainenade_rotas as rotas

    app = FastAPI()
    app.include_router(rotas.router)
    return TestClient(app)


class TestFixture(unittest.TestCase):
    def test_base_congelada(self):
        self.assertEqual(BASE.shape, (705, 22))
        self.assertEqual(int(BASE.isna().sum().sum()), 0)
        self.assertEqual(BASE["CO_CURSO"].nunique(), 705)
        # CURSO_SI coerente com CO_GRUPO (1 = SI/4006, 0 = CC/4004)
        self.assertTrue(((BASE["CO_GRUPO"] == 4006).astype(int) == BASE["CURSO_SI"]).all())
        self.assertEqual(int((BASE["CO_GRUPO"] == 4004).sum()), 319)
        self.assertEqual(int((BASE["CO_GRUPO"] == 4006).sum()), 386)

    def test_golden_cobre_os_12_cenarios(self):
        self.assertEqual(len(GOLDEN), 12)
        self.assertEqual(sorted(GOLDEN)[0], "01_principal")
        self.assertEqual(sorted(GOLDEN)[-1], "12_principal_com_curso")


class TestGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = _cliente()

    def setUp(self):
        patcher = mock.patch.dict(loader._supabase_cache, _cache_offline(), clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Garante que nenhum teste toca o Supabase.
        recusa = mock.patch.object(etl, "load_raw", side_effect=AssertionError("não deve consultar o Supabase"))
        recusa.start()
        self.addCleanup(recusa.stop)

    def _comparar(self, esperado, obtido, caminho):
        if isinstance(esperado, dict):
            self.assertIsInstance(obtido, dict, caminho)
            self.assertEqual(set(esperado), set(obtido), caminho)
            for k in esperado:
                self._comparar(esperado[k], obtido[k], f"{caminho}.{k}")
        elif isinstance(esperado, list):
            self.assertIsInstance(obtido, list, caminho)
            self.assertEqual(len(esperado), len(obtido), caminho)
            for i, (e, o) in enumerate(zip(esperado, obtido)):
                self._comparar(e, o, f"{caminho}[{i}]")
        elif isinstance(esperado, bool) or isinstance(esperado, str) or esperado is None:
            self.assertEqual(esperado, obtido, caminho)
        else:
            self.assertTrue(math.isclose(esperado, obtido, rel_tol=REL_TOL, abs_tol=ABS_TOL),
                            f"{caminho}: esperado {esperado!r}, obtido {obtido!r}")

    def test_cenarios_da_v2(self):
        for nome, ref in GOLDEN.items():
            with self.subTest(cenario=nome):
                r = self.cliente.post("/api/e-xplainenade/hipotese", json=ref["pedido"])
                self.assertEqual(r.status_code, 200, r.text[:300])
                j = r.json()
                self.assertEqual(j["formula"], ref["formula"])
                for campo, esperado in ref["esperado"].items():
                    self._comparar(esperado, j[campo], f"{nome}.{campo}")
                rep = j["reprodutibilidade"]
                self.assertEqual(rep["n_cursos_base"], ref["n_cursos_base"])
                # O hash depende do formato com que o pandas imprime os floats: só é comparável
                # quando as versões das bibliotecas são as mesmas da rodada que o gerou.
                if all(VERSOES[k] == v for k, v in ref["versoes"].items()):
                    self.assertEqual(rep["hash_base_sha256"], ref["hash_base_sha256"], f"{nome}: hash da base")

    def test_resultado_deterministico(self):
        pedido = GOLDEN["03_completo"]["pedido"]
        a = self.cliente.post("/api/e-xplainenade/hipotese", json=pedido).json()
        b = self.cliente.post("/api/e-xplainenade/hipotese", json=pedido).json()
        self.assertEqual(a["reprodutibilidade"]["hash_base_sha256"], b["reprodutibilidade"]["hash_base_sha256"])
        for campo in ("model_metrics", "coef_table", "comparison_table", "vif_table", "shap_summary"):
            self.assertEqual(a[campo], b[campo], campo)


if __name__ == "__main__":
    unittest.main()
