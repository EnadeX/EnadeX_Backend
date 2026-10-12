"""
Torna e_xplainenade/ importável como pacote de fora (ex: de um api_main.py
central na raiz do EnadeX): `from e_xplainenade.e_xplainenade_rotas import router`.

Todo o código interno (e_xplainenade_rotas.py, modules/*, config/*) usa imports
absolutos como `from config.variable_map import ...` e `from modules import
loader` — corretos quando o processo roda de dentro desta pasta
(`python e_xplainenade_rotas.py`, o uso principal), mas que quebram se alguém
importar este pacote a partir de outro diretório (`config`/`modules` não
seriam encontrados como pacotes de topo nesse caso). Em vez de reescrever
todo import interno para relativo, este __init__.py adiciona a própria pasta
ao sys.path na hora do import — resolve os dois casos com uma mudança só.
"""
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
