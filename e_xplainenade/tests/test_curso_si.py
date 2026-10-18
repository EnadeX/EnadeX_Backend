"""
Testes da variável de controle CURSO_SI (2026-10-14 — ver DEVELOPMENT.md).

Rodar a partir de e_xplainenade/:
    python -m unittest discover -s tests -v

Os testes offline usam arquivos brutos sintéticos passando pelo etl.load_raw()
real (só a leitura do Supabase é substituída). O teste de integração confere a
base real e é pulado se o Supabase não estiver acessível.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import etl  # noqa: E402
from modules.hypothesis import build_hypothesis  # noqa: E402

# 5 cursos: 3 de CC (4004) e 2 de SI (4006), 3 estudantes presentes cada.
_CURSOS = {101: "4004", 102: "4004", 103: "4004", 201: "4006", 202: "4006"}


def _arquivos_sinteticos():
    linhas = [(c, g) for c, g in _CURSOS.items() for _ in range(3)]
    cursos = [str(c) for c, _ in linhas]
    # Respostas variam por curso — senão toda média de curso seria igual e a
    # própria validação de variável constante recusaria a hipótese.
    letras = [["A", "B", "C", "D", "E"][(i // 3 + i % 3) % 5] for i in range(len(linhas))]
    arquivos = {
        1: pd.DataFrame({"CO_CURSO": cursos, "CO_GRUPO": [g for _, g in linhas],
                         "CO_REGIAO_CURSO": "3", "CO_CATEGAD": "1"}),
        3: pd.DataFrame({"CO_CURSO": cursos, "NT_GER": [str(40 + i) for i in range(len(cursos))],
                         "NT_FG": "50", "NT_CE": "45", "TP_PRES": "555"}),
    }
    for n, cols_raw, _ in etl._ARQUIVOS_SIMPLES:
        valores = {
            "CO_TURNO_GRADUACAO": ["1", "3", "4"] * len(_CURSOS),
            "TP_SEXO": ["F", "M", "M"] * len(_CURSOS),
            "NU_IDADE": ["22", "25", "30"] * len(_CURSOS),
            "QE_I21": ["A", "B", "A"] * len(_CURSOS),   # só A/B são válidos (Sim/Não)
            "QE_I17": [["A", "B"][(i // 3 + i % 2) % 2] for i in range(len(linhas))],  # A=pública, B=privada
        }.get(cols_raw[0], letras)
        arquivos[n] = pd.DataFrame({"CO_CURSO": cursos, cols_raw[0]: valores})
    return arquivos


def _base_sintetica() -> pd.DataFrame:
    with mock.patch.object(etl, "_read_todos_arquivos", _arquivos_sinteticos):
        return etl.load_raw()


class TestCursoSiOffline(unittest.TestCase):
    def test_valores_binarios_e_referencia_cc(self):
        base = _base_sintetica()
        self.assertEqual(set(base["CURSO_SI"].unique()), {0, 1})
        self.assertTrue((base.loc[base["CO_GRUPO"] == 4004, "CURSO_SI"] == 0).all())  # CC = referência
        self.assertTrue((base.loc[base["CO_GRUPO"] == 4006, "CURSO_SI"] == 1).all())

    def test_contagem_por_grupo(self):
        base = _base_sintetica()
        self.assertEqual(len(base), 5)
        self.assertEqual(int(base["CURSO_SI"].sum()), 2)
        self.assertEqual(int((base["CURSO_SI"] == 0).sum()), 3)

    def test_variavel_constante_no_recorte_gera_erro_claro(self):
        base = _base_sintetica()
        so_cc = base[base["CO_GRUPO"] == 4004]
        with self.assertRaisesRegex(ValueError, "sem variação neste recorte"):
            build_hypothesis("NT_GER", ["QE_RENDA", "CURSO_SI"], [], so_cc)
        # Com os dois cursos a mesma hipótese é válida.
        build_hypothesis("NT_GER", ["QE_RENDA", "CURSO_SI"], [], base)

    def test_api_devolve_400_quando_variavel_e_constante(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import e_xplainenade_rotas as rotas

        base = _base_sintetica()
        so_si = base[base["CO_GRUPO"] == 4006].reset_index(drop=True)
        app = FastAPI()
        app.include_router(rotas.router)
        with mock.patch.object(rotas.loader, "get_dataset_from_supabase", return_value=so_si):
            r = TestClient(app).post("/api/e-xplainenade/hipotese",
                                     json={"y": "NT_GER", "x_vars": ["QE_RENDA", "CURSO_SI"], "grupos": [4006]})
        self.assertEqual(r.status_code, 400)
        self.assertIn("sem variação neste recorte", r.json()["detail"])


class TestCursoSiBaseReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from modules import loader
        try:
            cls.base = loader.get_dataset_from_supabase()
        except RuntimeError as e:
            raise unittest.SkipTest(f"Supabase indisponível: {e}")

    def test_base_real(self):
        b = self.base
        self.assertEqual(set(b["CURSO_SI"].unique()), {0, 1})
        self.assertEqual(int(b["CURSO_SI"].sum()), int((b["CO_GRUPO"] == 4006).sum()))
        self.assertEqual(int((b["CURSO_SI"] == 0).sum()), int((b["CO_GRUPO"] == 4004).sum()))
        self.assertEqual(len(b), 705)


if __name__ == "__main__":
    unittest.main()
