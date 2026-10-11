import os

import pandas as pd

from educluster.educluster_config import (
    ORIGEM_PADRAO,
    CODIGOS_ABANDONO,
    CODIGOS_SITUACAO_DISCURSIVA,
    SITUACAO_DISCURSIVAS,
)
from educluster.educluster_dados import carregar_arq3
from educluster.educluster_preparo import derivar_area

DIRETORIO_MODELO = os.path.dirname(os.path.abspath(__file__))

PERFIS = {
    (True, True): "sabe_e_escreve",
    (True, False): "sabe_mas_nao_escreve",
    (False, True): "escreve_mas_nao_domina",
    (False, False): "dificuldade_ampla",
}


def preparar_dados_situacao(origem: str = ORIGEM_PADRAO) -> pd.DataFrame:
    df = derivar_area(carregar_arq3(origem))
    base = df[df["NT_GER"].notna()].copy()

    for coluna in SITUACAO_DISCURSIVAS:
        base[coluna] = base[coluna].astype(str)

    situacoes = base[SITUACAO_DISCURSIVAS]
    consideradas = situacoes.isin(list(CODIGOS_SITUACAO_DISCURSIVA.keys()))
    abandonadas = situacoes.isin(CODIGOS_ABANDONO)

    base["discursivas_consideradas"] = consideradas.sum(axis=1)
    base["discursivas_abandonadas"] = abandonadas.sum(axis=1)
    base["discursivas_validas"] = (situacoes == "555").sum(axis=1)

    base = base[base["discursivas_consideradas"] > 0].copy()
    base["taxa_abandono"] = base["discursivas_abandonadas"] / base["discursivas_consideradas"]

    grupo = base.groupby("area")["NT_OBJ_CE"]
    base["objetiva_z"] = (base["NT_OBJ_CE"] - grupo.transform("mean")) / grupo.transform("std")

    print(f"[educluster] {len(base)} estudantes com discursivas consideradas")
    return base.dropna(subset=["objetiva_z", "taxa_abandono"])


def distribuir_situacoes(df_base: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for coluna in SITUACAO_DISCURSIVAS:
        contagem = df_base[coluna].value_counts()
        total = contagem.sum()
        for codigo, rotulo in CODIGOS_SITUACAO_DISCURSIVA.items():
            quantidade = int(contagem.get(codigo, 0))
            linhas.append({
                "questao": coluna,
                "codigo": codigo,
                "situacao": rotulo,
                "estudantes": quantidade,
                "percentual": round(100 * quantidade / total, 2) if total else 0.0,
            })
    tabela = pd.DataFrame(linhas)
    print("\n[educluster] SITUACAO DAS QUESTOES DISCURSIVAS")
    print(tabela.pivot(index="questao", columns="situacao", values="percentual").round(1).to_string())
    return tabela


def classificar_perfis_discursivos(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()
    domina_conteudo = df["objetiva_z"] > 0
    entrega_discursiva = df["taxa_abandono"] <= 0

    df["domina_conteudo"] = domina_conteudo
    df["entrega_discursiva"] = entrega_discursiva
    df["perfil_discursivo"] = [PERFIS[(d, e)] for d, e in zip(domina_conteudo, entrega_discursiva)]
    return df


def perfilar_situacao(df_classificado: pd.DataFrame) -> pd.DataFrame:
    perfil = df_classificado.groupby("perfil_discursivo").agg(
        estudantes=("NT_GER", "size"),
        taxa_abandono=("taxa_abandono", "mean"),
        NT_OBJ_CE=("NT_OBJ_CE", "mean"),
        NT_DIS_CE=("NT_DIS_CE", "mean"),
        NT_OBJ_FG=("NT_OBJ_FG", "mean"),
        NT_DIS_FG=("NT_DIS_FG", "mean"),
        NT_GER=("NT_GER", "mean"),
    ).round(2).sort_values("estudantes", ascending=False)

    print("\n[educluster] PERFIS DE ENTREGA DISCURSIVA")
    print(perfil.to_string())
    return perfil


def medir_situacao(df_classificado: pd.DataFrame) -> dict:
    abandono_medio = df_classificado["taxa_abandono"].mean()
    zerados_por_branco = (df_classificado["taxa_abandono"] == 1).mean()
    sabe_mas_nao_escreve = (df_classificado["perfil_discursivo"] == "sabe_mas_nao_escreve").mean()

    metricas = {
        "n_estudantes": int(len(df_classificado)),
        "taxa_abandono_media": round(float(abandono_medio), 4),
        "abandonaram_todas": round(float(zerados_por_branco), 4),
        "sabe_mas_nao_escreve": round(float(sabe_mas_nao_escreve), 4),
        "codigos": CODIGOS_SITUACAO_DISCURSIVA,
        "definicao_abandono": "questao em branco, resposta nula ou divergente da tematica",
    }

    print(f"\n[educluster] taxa media de abandono discursivo: {abandono_medio:.1%}")
    print(f"[educluster] abandonaram todas as discursivas: {zerados_por_branco:.1%}")
    print(f"[educluster] dominam o conteudo mas abandonam a discursiva: {sabe_mas_nao_escreve:.1%}")
    return metricas


def educluster_modelo_situacao_discursiva(origem: str = ORIGEM_PADRAO) -> pd.DataFrame:
    print("[educluster] A4: desistencia versus erro conceitual nas questoes discursivas")
    base = preparar_dados_situacao(origem)
    distribuir_situacoes(base)
    df = classificar_perfis_discursivos(base)
    perfil = perfilar_situacao(df)
    medir_situacao(df)
    perfil.to_csv(os.path.join(DIRETORIO_MODELO, "perfil_situacao_discursiva.csv"))
    return df


if __name__ == "__main__":
    educluster_modelo_situacao_discursiva()
