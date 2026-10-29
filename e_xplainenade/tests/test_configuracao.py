"""
Registro formal da execução em JSON + Exec-ID ligado ao PDF (2026-10-29).

O requisito 2.3 do artigo pede "registro formal de decisões e configurações em arquivo
estruturado (JSON)" com um identificador único de execução (Exec-ID). O Streamlit já baixava
`config_<id>.json`; a interface web só baixava o PDF. Agora `/hipotese` devolve `exec_id` e a
`configuracao` (o mesmo dicionário que o PDF imprime na rastreabilidade) e `/relatorio` aceita
esse `exec_id`, de modo que o JSON e o PDF da MESMA execução têm o mesmo identificador.

Tudo offline, sobre a base congelada. Rodar a partir de e_xplainenade/:
    python -m unittest discover -s tests -v
"""
import io
import json
import re
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import etl, loader  # noqa: E402
from test_golden import GOLDEN, _cache_offline, _cliente  # noqa: E402

B = ["QE_RENDA", "QE_ESC_MAE", "QE_HORAS_ESTUDO"]
CORPO = {"y": "NT_GER", "x_vars": B}
CHAVES_ESPERADAS = {
    "exec_id", "gerado_em", "y", "x_vars", "interactions", "formula", "avisos",
    "fonte_dados", "filtros", "funil_cursos", "n_cursos_base", "n_obs_modelo", "hash_base_sha256",
    "cov_type", "medias_centragem", "aleatoriedade", "versoes",
}


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cliente = _cliente()

    def setUp(self):
        p = mock.patch.dict(loader._supabase_cache, _cache_offline(), clear=True)
        p.start()
        self.addCleanup(p.stop)
        r = mock.patch.object(etl, "load_raw", side_effect=AssertionError("consultou o Supabase"))
        r.start()
        self.addCleanup(r.stop)

    def hipotese(self, **extra):
        return self.cliente.post("/api/e-xplainenade/hipotese", json={**CORPO, **extra})

    def texto_pdf(self, **extra):
        from pypdf import PdfReader

        r = self.cliente.post("/api/e-xplainenade/relatorio", json={**CORPO, **extra})
        self.assertEqual(r.status_code, 200)
        return re.sub(r"\s+", " ", " ".join(p.extract_text() for p in PdfReader(io.BytesIO(r.content)).pages))


class TestConfiguracaoJson(_Base):
    def test_hipotese_devolve_exec_id_uuid_e_configuracao(self):
        j = self.hipotese().json()
        self.assertEqual(str(uuid.UUID(j["exec_id"])), j["exec_id"])
        self.assertEqual(set(j["configuracao"]), CHAVES_ESPERADAS)
        self.assertEqual(j["configuracao"]["exec_id"], j["exec_id"])

    def test_cada_execucao_tem_um_exec_id_novo(self):
        self.assertNotEqual(self.hipotese().json()["exec_id"], self.hipotese().json()["exec_id"])

    def test_a_configuracao_descreve_a_hipotese_exatamente(self):
        for nome in ("01_principal", "02_interacao_renda_horas", "07_so_cc", "11_completo_com_curso"):
            with self.subTest(cenario=nome):
                pedido = GOLDEN[nome]["pedido"]
                j = self.cliente.post("/api/e-xplainenade/hipotese", json=pedido).json()
                cfg = j["configuracao"]
                self.assertEqual(cfg["formula"], j["formula"])
                self.assertEqual(cfg["y"], pedido["y"])
                self.assertEqual(cfg["x_vars"], pedido["x_vars"])
                self.assertEqual(cfg["interactions"], pedido["interactions"])
                self.assertEqual(cfg["filtros"]["grupos"], pedido["grupos"])
                self.assertEqual(cfg["filtros"]["min_alunos"], pedido["min_alunos"])
                self.assertRegex(cfg["hash_base_sha256"], r"^[0-9a-f]{64}$")

    def test_configuracao_e_json_puro_e_sobrevive_a_ida_e_volta(self):
        cfg = self.hipotese().json()["configuracao"]
        self.assertEqual(json.loads(json.dumps(cfg, ensure_ascii=False)), cfg)
        # data/hora em UTC, ISO 8601
        self.assertRegex(cfg["gerado_em"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")

    def test_registra_o_que_foi_normalizado_e_os_avisos(self):
        j = self.hipotese(x_vars=B + ["QE_RENDA"], min_alunos=100).json()
        self.assertEqual(j["configuracao"]["x_vars"], B)                       # repetição removida
        self.assertEqual(j["configuracao"]["avisos"], j["avisos"])
        self.assertGreaterEqual(len(j["avisos"]), 3)                           # repetição + 2 de Green
        self.assertEqual(j["configuracao"]["filtros"]["min_alunos"], 100)

    def test_reprodutibilidade_continua_identica_dentro_da_configuracao(self):
        j = self.hipotese().json()
        for k, v in j["reprodutibilidade"].items():
            self.assertEqual(j["configuracao"][k], v, k)


class TestExecIdLigaJsonEPdf(_Base):
    def test_exec_id_enviado_e_repetido_pelo_servidor(self):
        eid = str(uuid.uuid4())
        j = self.hipotese(exec_id=eid).json()
        self.assertEqual(j["exec_id"], eid)
        self.assertEqual(j["configuracao"]["exec_id"], eid)

    def test_pdf_leva_o_exec_id_da_execucao_exibida(self):
        eid = str(uuid.uuid4())
        texto = self.texto_pdf(exec_id=eid)
        self.assertIn(f"Exec-ID: {eid}", texto)

    def test_json_e_pdf_da_mesma_execucao_compartilham_exec_id_e_hash(self):
        j = self.hipotese().json()
        texto = self.texto_pdf(exec_id=j["exec_id"])
        self.assertIn(f"Exec-ID: {j['exec_id']}", texto)
        self.assertIn(j["configuracao"]["hash_base_sha256"], texto)
        self.assertIn(j["configuracao"]["formula"], texto)

    def test_sem_exec_id_o_pdf_gera_um_proprio_como_antes(self):
        texto = self.texto_pdf()
        achado = re.search(r"Exec-ID: ([0-9a-f-]{36})", texto)
        self.assertIsNotNone(achado)
        self.assertEqual(str(uuid.UUID(achado.group(1))), achado.group(1))

    def test_exec_id_malformado_e_recusado(self):
        for ruim in ("123", "nao-e-um-uuid", "../../etc/passwd", "g" * 36, ""):
            with self.subTest(exec_id=ruim):
                r = self.cliente.post("/api/e-xplainenade/hipotese", json={**CORPO, "exec_id": ruim})
                self.assertEqual(r.status_code, 422, r.text[:200])

    def test_exec_id_nao_vira_nome_de_arquivo_fora_da_pasta_temporaria(self):
        # O nome do PDF usa só os 8 primeiros caracteres, já validados como hexadecimal.
        eid = "abcdef12-0000-4000-8000-000000000000"
        r = self.cliente.post("/api/e-xplainenade/relatorio", json={**CORPO, "exec_id": eid})
        self.assertEqual(r.status_code, 200)
        self.assertIn("relatorio_api_abcdef12.pdf", r.headers["content-disposition"])


if __name__ == "__main__":
    unittest.main()
