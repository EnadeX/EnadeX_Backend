"""
O verificador de números (docs/geradores/verificar_numeros.py) só protege o documento se
reconhecer os tokens. Um `\\b` depois de "×" fazia a regex de speedup nunca casar (depois de
"×" não há fronteira de palavra), e nenhum speedup era conferido contra as views.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_CAMINHO = Path(__file__).resolve().parents[1] / "docs" / "geradores" / "verificar_numeros.py"
_spec = importlib.util.spec_from_file_location("verificar_numeros", _CAMINHO)
verificar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verificar)


@pytest.mark.parametrize("texto,esperado", [
    ("speedup mediano de 2,7010× em relação", ["2,7010"]),
    ("chegou a 2,70× (mín–máx 2,53×–2,92×).", ["2,70", "2,53", "2,92"]),
    ("S = 1,5750×", ["1,5750"]),
    ("2,7010 ×", ["2,7010"]),
    ("fim de frase 3,01×.", ["3,01"]),
])
def test_regex_de_speedup_reconhece_o_simbolo_no_fim_do_token(texto, esperado):
    assert verificar.RE_X.findall(texto) == esperado


@pytest.mark.parametrize("texto", [
    "versão 1,2xpto",      # letra depois do x: não é speedup
    "24.967 inscrições",   # sem símbolo
    "ano 2021",
])
def test_regex_de_speedup_nao_casa_o_que_nao_e_speedup(texto):
    assert verificar.RE_X.findall(texto) == []
