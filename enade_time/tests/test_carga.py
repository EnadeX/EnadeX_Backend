"""
Eixo de carga (scripts/15_benchmark_carga.py): os mesmos bytes nas três estratégias e o
destino dedicado conferido contra a fato. Os testes que gravam usam só o Postgres local e a
tabela descartável tbl_enade_time_fato_bench; pulados sem o banco.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_CAMINHO = Path(__file__).resolve().parents[1] / "scripts" / "15_benchmark_carga.py"
_spec = importlib.util.spec_from_file_location("benchmark_carga", _CAMINHO)
carga = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(carga)


@pytest.fixture(scope="module")
def dados():
    return carga.preparar_dados()


def test_o_id_e_o_ordinal_da_linha_no_csv(dados):
    texto, df_up = dados
    linhas = texto.splitlines()
    assert len(linhas) == len(df_up) == carga.LINHAS
    assert [int(l.split(";", 1)[0]) for l in linhas[:3]] == [1, 2, 3]
    assert int(linhas[-1].split(";", 1)[0]) == carga.LINHAS
    assert list(df_up.columns) == carga.COLUNAS


def test_copy_e_upsert_partem_dos_mesmos_valores(dados):
    texto, df_up = dados
    primeira = texto.splitlines()[0].split(";")
    linha = df_up.iloc[0]
    assert int(primeira[1]) == int(linha["nu_ano"]) and int(primeira[2]) == int(linha["co_curso"])


def test_copy_local_deixa_a_tabela_dedicada_identica_a_fato(conn, dados):
    texto, _ = dados
    ctl = carga._m12.conectar_local()
    try:
        dt, rtt, payload, host = carga.carregar_copy_local(ctl, texto)
        with ctl.cursor() as cur:
            n_bench, md5_bench = carga.md5_tabela(cur, carga.TABELA_BENCH)
            n_fato, md5_fato = carga.md5_tabela(cur, "tbl_enade_time_fato")
        ctl.rollback()
    finally:
        ctl.close()
    assert n_bench == n_fato == carga.LINHAS
    assert md5_bench == md5_fato  # mesmas linhas, mesmos ids, mesmos valores
    assert dt > 0 and rtt > 0 and payload == len(texto.encode("utf-8")) and "5432" in host


def test_a_fato_publicada_nao_e_tocada_pela_carga(conn, dados):
    texto, _ = dados
    ctl = carga._m12.conectar_local()
    try:
        with ctl.cursor() as cur:
            antes = carga.md5_tabela(cur, "tbl_enade_time_fato")
        ctl.rollback()
        carga.carregar_copy_local(ctl, texto)
        with ctl.cursor() as cur:
            depois = carga.md5_tabela(cur, "tbl_enade_time_fato")
        ctl.rollback()
    finally:
        ctl.close()
    assert antes == depois


def test_estrategia_desconhecida_e_recusada(monkeypatch):
    monkeypatch.setattr("sys.argv", ["15_benchmark_carga.py", "--estrategias", "inexistente"])
    with pytest.raises(SystemExit, match="desconhecidas"):
        carga.main()
