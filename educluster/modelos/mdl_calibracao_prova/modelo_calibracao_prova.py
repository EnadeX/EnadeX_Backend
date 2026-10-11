import os

import pandas as pd

from educluster.educluster_config import (
    ORIGEM_PADRAO,
    ESCALA_PERCEPCAO_PROVA,
    RANDOM_STATE,
    ROTULOS_PERCEPCAO_PROVA,
)
from educluster.educluster_dados import carregar_arq3
from educluster.educluster_preparo import derivar_area

DIRETORIO_MODELO = os.path.dirname(os.path.abspath(__file__))

ITEM_DIFICULDADE_FG = "CO_RS_I1"
ITEM_DIFICULDADE_CE = "CO_RS_I2"

QUADRANTES = {
    (True, True): "confianca_confirmada",
    (True, False): "confianca_excessiva",
    (False, True): "insegura_mas_capaz",
    (False, False): "dificuldade_reconhecida",
}


def preparar_dados_calibracao(origem: str = ORIGEM_PADRAO) -> pd.DataFrame:
    df = derivar_area(carregar_arq3(origem))
    base = df[df["NT_GER"].notna()].copy()

    for item in (ITEM_DIFICULDADE_FG, ITEM_DIFICULDADE_CE):
        base[f"{item}_escala"] = base[item].map(ESCALA_PERCEPCAO_PROVA)

    base["dificuldade_percebida"] = base[
        [f"{ITEM_DIFICULDADE_FG}_escala", f"{ITEM_DIFICULDADE_CE}_escala"]
    ].mean(axis=1)

    base = base.dropna(subset=["dificuldade_percebida", "area"])

    grupo = base.groupby("area")["NT_GER"]
    base["desempenho_z"] = (base["NT_GER"] - grupo.transform("mean")) / grupo.transform("std")
    base["percentil_na_area"] = grupo.rank(pct=True)

    print(f"[educluster] {len(base)} estudantes com nota e percepcao da prova")
    return base


def classificar_calibracao(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()
    corte_dificuldade = df["dificuldade_percebida"].median()

    achou_facil = df["dificuldade_percebida"] <= corte_dificuldade
    foi_bem = df["desempenho_z"] > 0

    df["achou_facil"] = achou_facil
    df["foi_bem"] = foi_bem
    df["calibracao"] = [QUADRANTES[(f, b)] for f, b in zip(achou_facil, foi_bem)]
    return df


def perfilar_calibracao(df_classificado: pd.DataFrame) -> pd.DataFrame:
    perfil = df_classificado.groupby("calibracao").agg(
        estudantes=("NT_GER", "size"),
        dificuldade_percebida=("dificuldade_percebida", "mean"),
        NT_GER=("NT_GER", "mean"),
        NT_FG=("NT_FG", "mean"),
        NT_CE=("NT_CE", "mean"),
        desempenho_z=("desempenho_z", "mean"),
    ).round(3).sort_values("estudantes", ascending=False)

    print("\n[educluster] PERFIS DE CALIBRACAO METACOGNITIVA")
    print(perfil.to_string())
    return perfil


def medir_calibracao(df_classificado: pd.DataFrame) -> dict:
    correlacao = df_classificado["dificuldade_percebida"].corr(df_classificado["desempenho_z"])
    descalibrados = df_classificado["calibracao"].isin(["confianca_excessiva", "insegura_mas_capaz"]).mean()

    por_nivel = df_classificado.groupby("dificuldade_percebida").agg(
        estudantes=("NT_GER", "size"), NT_GER=("NT_GER", "mean")
    ).round(2)

    metricas = {
        "n_estudantes": int(len(df_classificado)),
        "correlacao_dificuldade_desempenho": round(float(correlacao), 4),
        "taxa_descalibrados": round(float(descalibrados), 4),
        "itens_usados": {
            ITEM_DIFICULDADE_FG: ROTULOS_PERCEPCAO_PROVA[ITEM_DIFICULDADE_FG],
            ITEM_DIFICULDADE_CE: ROTULOS_PERCEPCAO_PROVA[ITEM_DIFICULDADE_CE],
        },
        "escala": "1 = muito facil, 5 = muito dificil",
        "desempenho_padronizado_dentro_da_area": True,
    }

    print(f"\n[educluster] correlacao dificuldade percebida vs desempenho: {correlacao:.4f}")
    print(f"[educluster] taxa de estudantes descalibrados: {descalibrados:.1%}")
    print("\n[educluster] nota media por nivel de dificuldade percebida:")
    print(por_nivel.to_string())
    return metricas


def educluster_modelo_calibracao_prova(origem: str = ORIGEM_PADRAO) -> pd.DataFrame:
    print("[educluster] A3: calibracao entre percepcao da prova e desempenho real")
    df = classificar_calibracao(preparar_dados_calibracao(origem))
    perfil = perfilar_calibracao(df)
    medir_calibracao(df)
    perfil.to_csv(os.path.join(DIRETORIO_MODELO, "perfil_calibracao.csv"))
    return df


if __name__ == "__main__":
    educluster_modelo_calibracao_prova()
