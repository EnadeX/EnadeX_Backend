"""
Camada de dados (enade_time_dados.py): credenciais, lotes, nova tentativa e inteiros sem ".0".
Os testes de escrita usam um util_db falso (nada sai da máquina); o de leitura real contra o
Supabase só roda com SUPABASE_URL/SUPABASE_KEY (chave pública) no ambiente.
"""

from __future__ import annotations

import base64
import json
import os

import pandas as pd
import pytest

from enade_time import enade_time_dados as dados


def _jwt(papel: str) -> str:
    corpo = base64.urlsafe_b64encode(json.dumps({"role": papel}).encode()).decode().rstrip("=")
    return f"cabecalho.{corpo}.assinatura"


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "meuprojeto")
    monkeypatch.setenv("SUPABASE_KEY", "sb_publishable_abc")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)


@pytest.mark.parametrize("chave,papel", [
    ("sb_secret_xyz", "service_role"),
    ("sb_publishable_xyz", "anon"),
    (_jwt("service_role"), "service_role"),
    (_jwt("anon"), "anon"),
    ("qualquer-coisa", "desconhecido"),
])
def test_papel_da_chave(chave, papel):
    assert dados.papel_da_chave(chave) == papel


def test_credenciais_validas(env):
    assert dados.credenciais() == ("https://meuprojeto.supabase.co", "sb_publishable_abc")


@pytest.mark.parametrize("ref,fragmento", [
    ("", "SUPABASE_URL não definida"),
    ("https://meuprojeto.supabase.co", "só a referência"),
    ("meu.projeto", "só a referência"),
])
def test_credenciais_url_invalida(env, monkeypatch, ref, fragmento):
    monkeypatch.setenv("SUPABASE_URL", ref)
    with pytest.raises(dados.CredenciaisInvalidas, match=fragmento):
        dados.credenciais()


def test_credenciais_recusam_chave_de_servico(env, monkeypatch):
    monkeypatch.setenv("SUPABASE_KEY", "sb_secret_abc")
    with pytest.raises(dados.CredenciaisInvalidas, match="chave de serviço"):
        dados.credenciais()
    assert dados.credenciais(permitir_chave_de_servico=True)[1] == "sb_secret_abc"


def test_inteiros_com_nulo_saem_sem_ponto_zero():
    df = pd.DataFrame({"co_munic_curso": [2806701, None, 1100015], "media_nt_ger": [50.0, None, 63.8]})
    assert df["co_munic_curso"].dtype == "float64"  # o problema: inteiro com NaN vira float
    saida = dados.normalizar_inteiros(df, ["co_munic_curso", "coluna_inexistente"])
    registros = json.loads(saida.to_json(orient="records"))
    assert [r["co_munic_curso"] for r in registros] == [2806701, None, 1100015]
    assert "2806701.0" not in saida.to_json(orient="records")
    assert registros[0]["media_nt_ger"] == 50.0  # nota continua decimal


def test_upsert_em_lotes_de_2000(env, monkeypatch):
    enviados = []
    monkeypatch.setattr("util.util_db.upsert_supabase", lambda lote, tabela, url, chave: enviados.append(len(lote)) or True)
    df = pd.DataFrame({"id": range(4_500), "co_curso": [1] * 4_500})
    assert dados.upsert_lotes(df, "tbl_x", colunas_inteiras=["id", "co_curso"]) == 4_500
    assert enviados == [2_000, 2_000, 500]


def test_upsert_repete_o_lote_que_falhou(env, monkeypatch):
    chamadas = {"n": 0}

    def instavel(lote, tabela, url, chave):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise ConnectionError("rede caiu")
        return True

    monkeypatch.setattr("util.util_db.upsert_supabase", instavel)
    df = pd.DataFrame({"id": range(10)})
    assert dados.upsert_lotes(df, "tbl_x", espera=0) == 10
    assert chamadas["n"] == 2


def test_upsert_desiste_depois_das_tentativas_e_diz_qual_lote(env, monkeypatch):
    def sempre_falha(lote, tabela, url, chave):
        raise ConnectionError("fora do ar")

    monkeypatch.setattr("util.util_db.upsert_supabase", sempre_falha)
    with pytest.raises(RuntimeError, match=r"lote 1 .* após 3 tentativas"):
        dados.upsert_lotes(pd.DataFrame({"id": range(5)}), "tbl_x", espera=0)


def test_conferencia_de_contagem(env, monkeypatch):
    monkeypatch.setattr("util.util_db.upsert_supabase", lambda *a, **k: True)
    monkeypatch.setattr(dados, "contar", lambda tabela: 7)
    df = pd.DataFrame({"id": range(10)})
    with pytest.raises(RuntimeError, match="o servidor tem 7 linhas, esperado 10"):
        dados.upsert_lotes(df, "tbl_x", esperado_total=10)
    assert dados.upsert_lotes(df, "tbl_x", esperado_total=7) == 10


@pytest.mark.skipif(
    not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")),
    reason="leitura real: defina SUPABASE_URL (referência) e SUPABASE_KEY (chave pública)",
)
def test_leitura_real_da_fato_publicada():
    df = dados.ler_tabela("tbl_enade_time_fato")
    assert len(df) == 24_967
    assert df["nu_ano"].value_counts().to_dict() == {2008: 8740, 2005: 5748, 2021: 3091, 2017: 2537, 2011: 2463, 2014: 2388}
    assert int(df["media_nt_ger"].isna().sum()) == 192
    cursos = dados.ler_tabela("v_enade_time_curso_ano")
    assert len(cursos) == 582


def test_decimais_vao_com_o_mesmo_arredondamento_do_copy():
    """43.53125 é empate exato em binário: o "%.4f" do COPY (etapa 06) dá 43.5312, mas se o número
    for como float no JSON o NUMERIC(7,4) do PostgreSQL arredonda para 43.5313. Como texto já
    arredondado, o PostgREST grava o mesmo que o COPY."""
    import json

    empate = 43.53125
    assert f"{empate:.4f}" == "43.5312"  # o que o COPY da etapa 06 grava
    df = pd.DataFrame({"id": [1, 2], "media_nt_fg": [empate, float("nan")]})

    padrao = json.loads(df.to_json(orient="records"))
    assert padrao[0]["media_nt_fg"] == 43.53125  # chega como número; o PostgreSQL arredondaria para 43.5313

    texto = json.loads(dados.normalizar_decimais(df, ["media_nt_fg"]).to_json(orient="records"))
    assert texto[0]["media_nt_fg"] == "43.5312"
    assert texto[1]["media_nt_fg"] is None  # falta de valor continua sendo null
    assert texto[0]["id"] == 1  # as demais colunas não mudam
