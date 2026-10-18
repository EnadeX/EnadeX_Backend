"""
Testes da fonte do relatório PDF (2026-10-18 — ver DEVELOPMENT.md).

Sem a Arial/Liberation no caminho esperado, o report.py caía para a Helvetica,
que não tem "↑", "×", "ρ"…, e /relatorio devolvia 500 (ex.: Linux sem o pacote
da Liberation). Agora a última candidata é a DejaVu Sans do matplotlib.

Rodar a partir de e_xplainenade/:
    python -m unittest discover -s tests -v
"""
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import report  # noqa: E402
from test_curso_si import _base_sintetica  # noqa: E402


class TestFonteRelatorio(unittest.TestCase):
    def test_reserva_dejavu_existe(self):
        reg, bold = report._FONTES_CANDIDATAS[-1]
        self.assertEqual(reg.name, "DejaVuSans.ttf")
        self.assertTrue(reg.exists() and bold.exists())
        self.assertTrue(report._USE_UNICODE)

    def test_relatorio_com_fonte_reserva(self):
        """Simula uma máquina sem Arial/Liberation: o PDF tem de sair, com os símbolos."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from pypdf import PdfReader

        import e_xplainenade_rotas as rotas

        app = FastAPI()
        app.include_router(rotas.router)
        reg, bold = report._FONTES_CANDIDATAS[-1]
        with mock.patch.object(report, "_FONT_REGULAR", reg), \
                mock.patch.object(report, "_FONT_BOLD", bold), \
                mock.patch.object(rotas.loader, "get_dataset_from_supabase", return_value=_base_sintetica()):
            r = TestClient(app).post("/api/e-xplainenade/relatorio",
                                     json={"y": "NT_GER", "x_vars": ["QE_RENDA", "CURSO_SI"]})
        self.assertEqual(r.status_code, 200)
        pdf = PdfReader(io.BytesIO(r.content))
        texto = " ".join(p.extract_text() for p in pdf.pages)
        self.assertIn("↑", texto)  # caractere que a Helvetica não codifica
        fontes = {f.get_object()["/BaseFont"] for f in pdf.pages[0]["/Resources"]["/Font"].values()}
        self.assertTrue(any("DejaVu" in f for f in fontes), fontes)


if __name__ == "__main__":
    unittest.main()
