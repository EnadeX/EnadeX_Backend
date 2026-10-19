"""
Testes de robustez e operação (F3 do plano, 2026-10-19 — ver DEVELOPMENT.md).

  * cache: UMA carga do Supabase serve qualquer recorte (antes: cada recorte refazia as 13 consultas)
  * duas requisições frias simultâneas consultam o Supabase uma só vez
  * /relatorio: PDF em pasta temporária apagada após o envio (antes: acumulava em outputs/)
  * /dataset/refresh: exige token; desligado se a variável de ambiente não existir
  * erro interno: mensagem genérica com referência; detalhe só no log (antes: "TipoDaExcecao: ...")
  * colinearidade perfeita é recusada (antes: coeficientes arbitrários, sem aviso)
  * compute_vif não esconde mais falhas atrás de um fallback silencioso

Tudo offline, sobre a base congelada de tests/fixtures.

Rodar a partir de e_xplainenade/:
    python -m unittest discover -s tests -v
"""
import io
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import etl, loader  # noqa: E402
from test_golden import BASE, _cliente  # noqa: E402

B = ["QE_RENDA", "QE_ESC_MAE", "QE_HORAS_ESTUDO"]


def _base_com_funil() -> pd.DataFrame:
    df = BASE.copy()
    df.attrs["funil"] = {"cursos_recorte": 753, "cursos_com_nota": 707}
    return df


class TestCache(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(loader._supabase_cache, {}, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def test_uma_carga_serve_qualquer_recorte(self):
        with mock.patch.object(etl, "load_raw", return_value=_base_com_funil()) as carga:
            loader.get_dataset_from_supabase()
            loader.get_dataset_from_supabase(grupos=[4004])
            loader.get_dataset_from_supabase(grupos=[4006])
            loader.get_dataset_from_supabase(grupos=[4004, 4006], ies_filter=[0], min_alunos=10)
            self.assertEqual(carga.call_count, 1)

    def test_recorte_por_curso_e_o_filtro_da_base_completa(self):
        with mock.patch.object(etl, "load_raw", return_value=_base_com_funil()):
            for grupo in (4004, 4006):
                got = loader.get_dataset_from_supabase(grupos=[grupo])
                esperado = BASE[BASE["CO_GRUPO"] == grupo].reset_index(drop=True)
                pd.testing.assert_frame_equal(got, esperado, check_exact=True)
                self.assertEqual(got.attrs["funil"]["cursos_apos_curso"], len(esperado))
            tudo = loader.get_dataset_from_supabase(grupos=[4004, 4006])
            self.assertEqual(len(tudo), 705)

    def test_o_retorno_e_uma_copia(self):
        with mock.patch.object(etl, "load_raw", return_value=_base_com_funil()):
            a = loader.get_dataset_from_supabase()
            a["NT_GER"] = -1.0
            a.attrs["funil"]["x"] = 1
            b = loader.get_dataset_from_supabase()
            self.assertNotEqual(float(b["NT_GER"].iloc[0]), -1.0)
            self.assertNotIn("x", b.attrs["funil"])

    def test_force_refresh_recarrega(self):
        with mock.patch.object(etl, "load_raw", return_value=_base_com_funil()) as carga:
            loader.get_dataset_from_supabase()
            loader.get_dataset_from_supabase(force_refresh=True)
            self.assertEqual(carga.call_count, 2)

    def test_base_vazia_nao_fica_em_cache(self):
        with mock.patch.object(etl, "load_raw", return_value=BASE.iloc[0:0]) as carga:
            with self.assertRaisesRegex(RuntimeError, "Nenhum curso retornado"):
                loader.get_dataset_from_supabase()
            with self.assertRaises(RuntimeError):
                loader.get_dataset_from_supabase()
            self.assertEqual(carga.call_count, 2)  # tentou de novo: a falha não foi memorizada

    def test_duas_cargas_frias_simultaneas_consultam_uma_vez(self):
        chamadas = []

        def carga_lenta(*a, **k):
            chamadas.append(1)
            time.sleep(0.4)
            return _base_com_funil()

        resultados, erros = [], []

        def trabalhador():
            try:
                resultados.append(len(loader.get_dataset_from_supabase()))
            except Exception as e:  # pragma: no cover
                erros.append(e)

        with mock.patch.object(etl, "load_raw", side_effect=carga_lenta):
            ts = [threading.Thread(target=trabalhador) for _ in range(8)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        self.assertEqual(erros, [])
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(resultados, [705] * 8)


class _ApiBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = _cliente()

    def setUp(self):
        p = mock.patch.dict(loader._supabase_cache, {None: _base_com_funil()}, clear=True)
        p.start()
        self.addCleanup(p.stop)
        r = mock.patch.object(etl, "load_raw", side_effect=AssertionError("consultou o Supabase"))
        r.start()
        self.addCleanup(r.stop)


class TestRelatorioTemporario(_ApiBase):
    def test_pdf_vai_para_pasta_temporaria_apagada_apos_o_envio(self):
        from pypdf import PdfReader

        import e_xplainenade_rotas as rotas
        from modules import report

        criadas = []
        real = tempfile.mkdtemp

        def registrar(**k):
            d = real(**k)
            criadas.append(Path(d))
            return d

        with tempfile.TemporaryDirectory() as padrao, \
                mock.patch.object(report, "_OUTPUT_DIR", Path(padrao)), \
                mock.patch.object(rotas.tempfile, "mkdtemp", side_effect=registrar):
            r = self.cliente.post("/api/e-xplainenade/relatorio", json={"y": "NT_GER", "x_vars": B})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(os.listdir(padrao), [], "nada deve sobrar na pasta padrão de saída")
        self.assertEqual(len(criadas), 1)
        self.assertFalse(criadas[0].exists(), "a pasta temporária deve ser apagada depois do envio")
        self.assertGreater(len(PdfReader(io.BytesIO(r.content)).pages), 3)
        self.assertIn("relatorio_api_", r.headers["content-disposition"])

    def test_falha_ao_gerar_o_pdf_da_500_generico_e_limpa_a_pasta(self):
        import e_xplainenade_rotas as rotas

        criadas = []
        real = tempfile.mkdtemp

        def registrar(**k):
            d = real(**k)
            criadas.append(Path(d))
            return d

        with mock.patch.object(rotas, "generate_report", side_effect=RuntimeError("segredo-interno-xyz")), \
                mock.patch.object(rotas.tempfile, "mkdtemp", side_effect=registrar), \
                self.assertLogs("e_xplainenade", level="ERROR") as log:
            r = self.cliente.post("/api/e-xplainenade/relatorio", json={"y": "NT_GER", "x_vars": B})
        self.assertEqual(r.status_code, 500)
        self.assertIn("ref.", r.json()["detail"])
        self.assertNotIn("RuntimeError", r.json()["detail"])
        self.assertNotIn("segredo-interno-xyz", r.json()["detail"])
        self.assertIn("segredo-interno-xyz", "\n".join(log.output))  # o detalhe fica no log
        self.assertFalse(criadas[0].exists())


class TestRefreshComToken(_ApiBase):
    URL = "/api/e-xplainenade/dataset/refresh"

    def _env_sem_token(self):
        env = {k: v for k, v in os.environ.items() if k != "EXPLAINENADE_REFRESH_TOKEN"}
        return mock.patch.dict(os.environ, env, clear=True)

    def test_desligado_sem_a_variavel_de_ambiente(self):
        with self._env_sem_token():
            r = self.cliente.post(self.URL, json={}, headers={"X-Refresh-Token": "qualquer"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("desabilitada", r.json()["detail"])

    def test_sem_cabecalho_ou_com_token_errado(self):
        with mock.patch.dict(os.environ, {"EXPLAINENADE_REFRESH_TOKEN": "certo"}):
            self.assertEqual(self.cliente.post(self.URL, json={}).status_code, 403)
            r = self.cliente.post(self.URL, json={}, headers={"X-Refresh-Token": "errado"})
            self.assertEqual(r.status_code, 403)
            self.assertIn("inválido", r.json()["detail"])

    def test_com_o_token_certo_recarrega(self):
        with mock.patch.dict(os.environ, {"EXPLAINENADE_REFRESH_TOKEN": "certo"}), \
                mock.patch.object(etl, "load_raw", return_value=_base_com_funil()) as carga:
            r = self.cliente.post(self.URL, json={}, headers={"X-Refresh-Token": "certo"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["n_cursos"], 705)
        self.assertEqual(carga.call_count, 1)


class TestErroInterno(_ApiBase):
    def test_excecao_inesperada_da_500_generico_com_referencia(self):
        import e_xplainenade_rotas as rotas

        with mock.patch.object(rotas, "fit_variants", side_effect=RuntimeError("detalhe-secreto-abc")), \
                self.assertLogs("e_xplainenade", level="ERROR") as log:
            r = self.cliente.post("/api/e-xplainenade/hipotese", json={"y": "NT_GER", "x_vars": B})
        self.assertEqual(r.status_code, 500)
        detalhe = r.json()["detail"]
        self.assertIn("ref.", detalhe)
        self.assertNotIn("RuntimeError", detalhe)
        self.assertNotIn("detalhe-secreto-abc", detalhe)
        ref = detalhe.split("ref. ")[1].split(")")[0]
        saida = "\n".join(log.output)
        self.assertIn(ref, saida)                       # a referência liga a resposta ao log
        self.assertIn("detalhe-secreto-abc", saida)     # e o traceback está lá
        self.assertIn("Traceback", saida)


class TestColinearidadePerfeita(unittest.TestCase):
    def _base_colinear(self):
        df = BASE.copy()
        df["QE_ESC_PAI"] = df["QE_ESC_MAE"] * 2.0  # PAI = 2 x MAE
        df.attrs["funil"] = {}
        return df

    def test_api_recusa_com_400_e_aponta_os_termos(self):
        with mock.patch.dict(loader._supabase_cache, {None: self._base_colinear()}, clear=True):
            r = _cliente().post("/api/e-xplainenade/hipotese",
                                json={"y": "NT_GER", "x_vars": ["QE_RENDA", "QE_ESC_MAE", "QE_ESC_PAI"]})
        self.assertEqual(r.status_code, 400)
        d = r.json()["detail"]
        self.assertIn("Colinearidade perfeita", d)
        self.assertIn("Escolaridade da Mãe", d)
        self.assertIn("Escolaridade do Pai", d)
        self.assertNotIn("Renda Familiar", d)  # a variável inocente não é acusada

    def test_fit_ols_do_streamlit_tambem_recusa(self):
        from modules.hypothesis import build_hypothesis
        from modules.modeling import fit_ols

        df = self._base_colinear()
        hyp = build_hypothesis("NT_GER", ["QE_RENDA", "QE_ESC_MAE", "QE_ESC_PAI"], [], df)
        with self.assertRaisesRegex(ValueError, "Colinearidade perfeita"):
            fit_ols(hyp, df)

    def test_correlacao_alta_mas_nao_perfeita_continua_aceita(self):
        import numpy as np

        df = BASE.copy()
        # Quase 2 x MAE, mas com ruído próprio: NÃO é combinação linear exata (VIF enorme, porém
        # finito). Cuidado: somar um múltiplo de outra coluna (ex.: RENDA) continua sendo
        # combinação linear exata — foi o primeiro rascunho deste teste, e o detector acertou.
        ruido = np.random.default_rng(0).normal(size=len(df)) * 0.01
        df["QE_ESC_PAI"] = df["QE_ESC_MAE"] * 2.0 + ruido
        from modules.hypothesis import build_hypothesis
        from modules.modeling import fit_ols

        hyp = build_hypothesis("NT_GER", ["QE_RENDA", "QE_ESC_MAE", "QE_ESC_PAI"], [], df)
        fit_ols(hyp, df)  # não levanta


class TestVifSemFallbackSilencioso(unittest.TestCase):
    def test_formula_invalida_levanta_em_vez_de_cair_em_silencio(self):
        import patsy

        from modules.multicollinearity import compute_vif

        with self.assertRaises(patsy.PatsyError):
            compute_vif(BASE, B, formula="NT_GER ~ QE_RENDA + COLUNA_QUE_NAO_EXISTE")

    def test_com_formula_o_vif_inclui_os_termos_de_interacao(self):
        from modules.multicollinearity import compute_vif

        t = compute_vif(BASE, B, formula="NT_GER ~ QE_RENDA + QE_ESC_MAE + QE_RENDA:QE_ESC_MAE")
        self.assertIn("QE_RENDA:QE_ESC_MAE", list(t["variavel"]))  # o fallback antigo o omitiria

    def test_sem_formula_continua_funcionando(self):
        from modules.multicollinearity import compute_vif

        self.assertEqual(list(compute_vif(BASE, B)["variavel"]), B)


class TestSaidaDoRelatorio(unittest.TestCase):
    def test_output_dir_explicito_nao_toca_a_pasta_padrao(self):
        from modules import report

        sessao = {"exec_id": "t", "y_label": "Nota Geral", "formula": "NT_GER ~ x", "config": {}}
        with tempfile.TemporaryDirectory() as destino, tempfile.TemporaryDirectory() as padrao, \
                mock.patch.object(report, "_OUTPUT_DIR", Path(padrao)):
            caminho = report.generate_report(sessao, filename="a.pdf", output_dir=Path(destino))
            self.assertEqual(caminho, Path(destino) / "a.pdf")
            self.assertTrue(caminho.exists())
            self.assertEqual(os.listdir(padrao), [])


if __name__ == "__main__":
    unittest.main()
