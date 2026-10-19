"""
Testes da validação de entrada da API (F1 do plano, 2026-10-18 — ver DEVELOPMENT.md).

Antes da F1, a API aceitava qualquer coluna da base: NT_GER como preditora de si mesma dava
R² = 1,000, NT_FG dava 0,72, CO_GRUPO (código nominal) entrava como número, recorte vazio ou
com 1 curso respondia "variável sem variação" e um `grupos` inexistente fazia as 13 consultas
ao Supabase (~10 s) para devolver 503 "tabelas não populadas".

Tudo offline: base congelada de tests/fixtures + `etl.load_raw` trocado por uma exceção, o que
também prova que entrada inválida é recusada ANTES de consultar o Supabase.

Rodar a partir de e_xplainenade/:
    python -m unittest discover -s tests -v
"""
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.hypothesis import avisos_amostra, build_hypothesis, normalizar_hipotese  # noqa: E402
from test_golden import GOLDEN, _cache_offline, _cliente  # noqa: E402

B = ["QE_RENDA", "QE_ESC_MAE", "QE_HORAS_ESTUDO"]


class TestNormalizacao(unittest.TestCase):
    def assertErro(self, trecho, *args):
        with self.assertRaises(ValueError) as ctx:
            normalizar_hipotese(*args)
        self.assertIn(trecho, str(ctx.exception))

    def test_y_invalido(self):
        self.assertErro("dependente inválida", "XXX", B)
        self.assertErro("dependente inválida", "QE_RENDA", B)  # uma variável explicativa não é Y

    def test_y_nao_pode_ser_preditora(self):
        self.assertErro("não permitida", "NT_GER", B + ["NT_GER"])

    def test_notas_numero_de_alunos_e_codigos_nominais_ficam_de_fora(self):
        for ruim in ("NT_FG", "NT_CE", "QT_ALUNOS", "CO_GRUPO", "CO_REGIAO", "CO_CURSO", "XXX"):
            with self.subTest(variavel=ruim):
                self.assertErro("não permitida", "NT_GER", B + [ruim])

    def test_sem_explicativas(self):
        self.assertErro("ao menos uma", "NT_GER", [])

    def test_todas_as_opcoes_da_interface_sao_aceitas(self):
        from config.variable_map import X_OPTS, Y_OPTS
        for y in Y_OPTS.values():
            normalizar_hipotese(y, list(X_OPTS.values()))

    def test_repeticoes_sao_removidas_com_aviso_e_a_ordem_e_preservada(self):
        y, x, inter, avisos = normalizar_hipotese("NT_GER", ["QE_ESC_MAE", "QE_RENDA", "QE_ESC_MAE"])
        self.assertEqual(x, ["QE_ESC_MAE", "QE_RENDA"])
        self.assertEqual(len(avisos), 1)
        self.assertIn("repetida", avisos[0])

    def test_interacao_da_variavel_com_ela_mesma(self):
        self.assertErro("mesma variável", "NT_GER", B, [("QE_RENDA", "QE_RENDA")])

    def test_interacao_exige_as_duas_variaveis_em_x(self):
        self.assertErro("exige que as duas", "NT_GER", B, [("QE_RENDA", "TP_SEXO")])

    def test_interacao_repetida_ou_invertida_vira_uma(self):
        _, _, inter, avisos = normalizar_hipotese(
            "NT_GER", B, [("QE_RENDA", "QE_ESC_MAE"), ("QE_ESC_MAE", "QE_RENDA"), ("QE_RENDA", "QE_ESC_MAE")])
        self.assertEqual(inter, [("QE_RENDA", "QE_ESC_MAE")])
        self.assertEqual(len(avisos), 1)

    def test_hipotese_valida_nao_gera_avisos(self):
        self.assertEqual(normalizar_hipotese("NT_GER", B, [("QE_RENDA", "QE_ESC_MAE")])[3], [])


class TestRegraDeAmostra(unittest.TestCase):
    """build_hypothesis recusa n <= k+1; avisos_amostra aplica a regra de Green sem bloquear."""

    @classmethod
    def setUpClass(cls):
        from test_golden import BASE
        cls.base = BASE

    def test_recorte_vazio(self):
        with self.assertRaisesRegex(ValueError, "Nenhum curso atende"):
            build_hypothesis("NT_GER", B, [], self.base.iloc[0:0])

    def test_amostra_insuficiente(self):
        # k = 3 termos -> 4 parâmetros; com 4 cursos não há graus de liberdade nos resíduos.
        with self.assertRaisesRegex(ValueError, "Amostra insuficiente: 4 curso"):
            build_hypothesis("NT_GER", B, [], self.base.iloc[:4])
        build_hypothesis("NT_GER", B, [], self.base.iloc[:5])  # n = k + 2 já ajusta

    def test_avisos_de_green(self):
        hyp = build_hypothesis("NT_GER", B, [], self.base.iloc[:20])
        avisos = avisos_amostra(hyp, self.base.iloc[:20])
        self.assertEqual(len(avisos), 2)
        self.assertIn("107", avisos[0])  # 104 + k, com k = 3
        self.assertIn("74", avisos[1])   # 50 + 8k
        # Entre os dois limiares: só o aviso dos coeficientes.
        self.assertEqual(len(avisos_amostra(hyp, self.base.iloc[:90])), 1)
        # Amostra grande: nenhum aviso.
        self.assertEqual(avisos_amostra(hyp, self.base), [])


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = _cliente()

    def setUp(self):
        from modules import etl, loader
        p = mock.patch.dict(loader._supabase_cache, _cache_offline(), clear=True)
        p.start()
        self.addCleanup(p.stop)
        # Se algum caminho tentar consultar o Supabase, o teste quebra com esta mensagem.
        r = mock.patch.object(etl, "load_raw", side_effect=AssertionError("consultou o Supabase"))
        r.start()
        self.addCleanup(r.stop)

    def hipotese(self, **corpo):
        return self.cliente.post("/api/e-xplainenade/hipotese", json={"y": "NT_GER", "x_vars": B, **corpo})

    def test_entradas_invalidas_dao_400_sem_consultar_o_supabase(self):
        casos = {
            "y fora de Y_OPTS": ({"y": "XXX"}, "dependente inválida"),
            "y também em x": ({"x_vars": B + ["NT_GER"]}, "não permitida"),
            "nota como preditora": ({"x_vars": B + ["NT_FG"]}, "não permitida"),
            "código nominal": ({"x_vars": B + ["CO_GRUPO"]}, "não permitida"),
            "nº de alunos": ({"x_vars": B + ["QT_ALUNOS"]}, "não permitida"),
            "interação a×a": ({"interactions": [["QE_RENDA", "QE_RENDA"]]}, "mesma variável"),
            "interação fora de X": ({"interactions": [["QE_RENDA", "TP_SEXO"]]}, "exige que as duas"),
            "curso inexistente": ({"grupos": [9999]}, "inválido"),
            "curso sem dados (4005)": ({"grupos": [4005]}, "inválido"),
            "tipo de IES inexistente": ({"ies_filter": [5]}, "inválido"),
        }
        for nome, (corpo, trecho) in casos.items():
            with self.subTest(caso=nome):
                r = self.hipotese(**corpo)
                self.assertEqual(r.status_code, 400, r.text[:200])
                self.assertIn(trecho, r.json()["detail"])

    def test_endpoints_de_dataset_validam_o_recorte(self):
        r = self.cliente.get("/api/e-xplainenade/dataset/resumo", params={"grupos": 9999})
        self.assertEqual(r.status_code, 400)
        r = self.cliente.get("/api/e-xplainenade/dataset/resumo", params={"ies": 7})
        self.assertEqual(r.status_code, 400)
        # O refresh exige token (F3); com o token certo, o recorte inválido é recusado com 400.
        with mock.patch.dict("os.environ", {"EXPLAINENADE_REFRESH_TOKEN": "t"}):
            r = self.cliente.post("/api/e-xplainenade/dataset/refresh", json={"grupos": [9999]},
                                  headers={"X-Refresh-Token": "t"})
        self.assertEqual(r.status_code, 400)

    def test_recorte_vazio_e_recorte_de_um_curso(self):
        r = self.hipotese(min_alunos=100000)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Nenhum curso atende", r.json()["detail"])
        r = self.hipotese(min_alunos=150)  # só 1 curso passa
        self.assertEqual(r.status_code, 400)
        self.assertIn("Amostra insuficiente", r.json()["detail"])
        self.assertNotIn("sem variação", r.json()["detail"])

    def test_variavel_constante_continua_com_a_mensagem_propria(self):
        r = self.hipotese(x_vars=B + ["CURSO_SI"], grupos=[4004])
        self.assertEqual(r.status_code, 400)
        self.assertIn("sem variação neste recorte", r.json()["detail"])

    def test_cenarios_de_referencia_nao_geram_avisos(self):
        for nome, ref in GOLDEN.items():
            with self.subTest(cenario=nome):
                r = self.cliente.post("/api/e-xplainenade/hipotese", json=ref["pedido"])
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["avisos"], [])

    def test_amostra_pequena_ajusta_e_avisa(self):
        r = self.hipotese(min_alunos=100)  # 11 cursos para 3 termos
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["model_metrics"]["n_obs"], 11)
        self.assertEqual(len(j["avisos"]), 2)
        self.assertTrue(all("Green" in a for a in j["avisos"]))

    def test_repeticoes_sao_normalizadas_e_o_resultado_e_o_mesmo(self):
        base = self.hipotese().json()
        rep = self.hipotese(x_vars=B + ["QE_RENDA"],
                            interactions=[["QE_RENDA", "QE_ESC_MAE"], ["QE_ESC_MAE", "QE_RENDA"]]).json()
        sem_rep = self.hipotese(interactions=[["QE_RENDA", "QE_ESC_MAE"]]).json()
        self.assertEqual(rep["formula"], sem_rep["formula"])
        self.assertEqual(rep["formula"].count("QE_RENDA:QE_ESC_MAE"), 1)
        self.assertEqual(rep["model_metrics"], sem_rep["model_metrics"])
        self.assertEqual(rep["coef_table"], sem_rep["coef_table"])
        self.assertEqual(len(rep["avisos"]), 2)
        self.assertEqual(base["avisos"], [])
        self.assertNotEqual(base["model_metrics"], rep["model_metrics"])  # a interação mudou o modelo

    def test_relatorio_pdf_mostra_os_avisos(self):
        from pypdf import PdfReader

        from modules import report

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(report, "_OUTPUT_DIR", Path(tmp)):
            r = self.cliente.post("/api/e-xplainenade/relatorio",
                                  json={"y": "NT_GER", "x_vars": B, "min_alunos": 100})
        self.assertEqual(r.status_code, 200)
        texto = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
        self.assertIn("Avisos sobre este modelo", texto)
        self.assertIn("Green", texto)

    def test_relatorio_sem_avisos_nao_tem_a_caixa(self):
        from pypdf import PdfReader

        from modules import report

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(report, "_OUTPUT_DIR", Path(tmp)):
            r = self.cliente.post("/api/e-xplainenade/relatorio", json={"y": "NT_GER", "x_vars": B})
        self.assertEqual(r.status_code, 200)
        texto = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages)
        self.assertNotIn("Avisos sobre este modelo", texto)


if __name__ == "__main__":
    unittest.main()
